"""
apps/core/telemetry.py
─────────────────────
OpenTelemetry integration for ZygoTrip.

Instruments:
  • Django (requests, DB queries, cache operations)
  • Redis / django-redis
  • Celery tasks
  • Manual span helpers for booking + search flows

Usage — in zygotrip_project/settings.py:

    from apps.core.telemetry import setup_telemetry
    setup_telemetry()   # idempotent — safe to call at import time

Environment variables:
    OTEL_EXPORTER_OTLP_ENDPOINT   e.g. http://otel-collector:4317
    OTEL_SERVICE_NAME              default: zygotrip-api
    OTEL_ENVIRONMENT               default: production
    OTEL_TRACES_SAMPLE_RATE        0.0-1.0, default: 1.0
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Generator

logger = logging.getLogger(__name__)

_tracer = None
_setup_done = False


def _otel_available() -> bool:
    try:
        import opentelemetry  # noqa: F401
        return True
    except ImportError:
        return False


def _get_tracer():
    global _tracer
    if _tracer is None:
        if _otel_available():
            from opentelemetry import trace
            _tracer = trace.get_tracer("zygotrip", schema_url="https://opentelemetry.io/schemas/1.21.0")
        else:
            _tracer = _NoopTracer()
    return _tracer


def setup_telemetry() -> None:
    """Configure OpenTelemetry SDK with OTLP gRPC exporter. Idempotent."""
    global _setup_done
    if _setup_done:
        return
    _setup_done = True

    if not _otel_available():
        logger.info("[telemetry] opentelemetry packages not installed — skipping OTel setup")
        return

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if not endpoint:
        logger.info("[telemetry] OTEL_EXPORTER_OTLP_ENDPOINT not set — using no-op exporter")
        return

    try:
        _configure_sdk(endpoint)
        logger.info("[telemetry] OpenTelemetry configured — endpoint=%s", endpoint)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[telemetry] Setup failed — telemetry disabled: %s", exc)


def _configure_sdk(endpoint: str) -> None:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, DEPLOYMENT_ENVIRONMENT

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    except ImportError:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # type: ignore[no-redef]

    service_name = os.environ.get("OTEL_SERVICE_NAME", "zygotrip-api")
    environment  = os.environ.get("OTEL_ENVIRONMENT", "production")
    sample_rate  = float(os.environ.get("OTEL_TRACES_SAMPLE_RATE", "1.0"))

    resource = Resource.create({
        SERVICE_NAME: service_name,
        DEPLOYMENT_ENVIRONMENT: environment,
    })

    if sample_rate >= 1.0:
        from opentelemetry.sdk.trace.sampling import ALWAYS_ON
        sampler = ALWAYS_ON
    elif sample_rate <= 0.0:
        from opentelemetry.sdk.trace.sampling import ALWAYS_OFF
        sampler = ALWAYS_OFF
    else:
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
        sampler = TraceIdRatioBased(sample_rate)

    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    provider = TracerProvider(resource=resource, sampler=sampler)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _instrument_libraries()


def _instrument_libraries() -> None:
    _try_instrument("opentelemetry.instrumentation.django",   "DjangoInstrumentor")
    _try_instrument("opentelemetry.instrumentation.redis",    "RedisInstrumentor")
    _try_instrument("opentelemetry.instrumentation.celery",   "CeleryInstrumentor")
    _try_instrument("opentelemetry.instrumentation.requests", "RequestsInstrumentor")


def _try_instrument(module_path: str, class_name: str) -> None:
    try:
        import importlib
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        cls().instrument()
        logger.debug("[telemetry] Instrumented: %s", class_name)
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.debug("[telemetry] Could not instrument %s: %s", class_name, exc)


# ── Public helpers ────────────────────────────────────────────────────────────

@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> Generator[Any, None, None]:
    """
    Context manager that creates a child OTel span.

    Usage::

        with trace_span("pricing.compute", {"property_id": "abc", "nights": 3}):
            result = pricing_service.compute(...)

    No-op if OTel is unavailable or not configured.
    """
    if not _otel_available():
        yield None
        return

    from opentelemetry import trace
    from opentelemetry.trace import StatusCode

    tracer = _get_tracer()
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, str(v) if not isinstance(v, (bool, int, float, str)) else v)
        try:
            yield span
        except Exception as exc:
            span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            raise


def record_booking_event(
    booking_uuid: str,
    event: str,
    **kwargs: Any,
) -> None:
    """Add a structured event to the current active span."""
    if not _otel_available():
        return
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        span.add_event(event, attributes={
            "booking.uuid": booking_uuid,
            **{k: str(v) for k, v in kwargs.items()},
        })
    except Exception:  # noqa: BLE001
        pass


def record_search_event(
    query: str,
    result_count: int,
    cache_hit: bool,
    latency_ms: float,
) -> None:
    """Add a search event to the current active span."""
    if not _otel_available():
        return
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        span.set_attribute("search.query", query[:200])
        span.set_attribute("search.result_count", result_count)
        span.set_attribute("search.cache_hit", cache_hit)
        span.set_attribute("search.latency_ms", latency_ms)
    except Exception:  # noqa: BLE001
        pass


def get_trace_id() -> str:
    """Return current W3C trace-id (hex) or '' if no active span."""
    if not _otel_available():
        return ""
    try:
        from opentelemetry import trace
        ctx = trace.get_current_span().get_span_context()
        if ctx and ctx.is_valid:
            return format(ctx.trace_id, "032x")
    except Exception:  # noqa: BLE001
        pass
    return ""


# ── Django Middleware ─────────────────────────────────────────────────────────

class OtelLoggingMiddleware:
    """
    Injects trace-id into every request/response.

    Add to MIDDLEWARE in settings.py (after SecurityMiddleware):

        MIDDLEWARE = [
            'django.middleware.security.SecurityMiddleware',
            'apps.core.telemetry.OtelLoggingMiddleware',
            ...
        ]

    Sets request.trace_id and X-Trace-Id response header.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        trace_id = get_trace_id()
        request.trace_id = trace_id
        response = self.get_response(request)
        if trace_id:
            response["X-Trace-Id"] = trace_id
        return response


# ── Noop fallback ─────────────────────────────────────────────────────────────

class _NoopTracer:
    def start_as_current_span(self, *_args, **_kwargs):
        from contextlib import nullcontext
        return nullcontext(enter_result=None)


# Auto-setup on import when env var is present
if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
    setup_telemetry()
