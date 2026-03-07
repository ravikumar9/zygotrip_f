import json
import logging
import time
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

access_logger = logging.getLogger("access")


class StructuredLoggingMiddleware(MiddlewareMixin):
    """
    Structured logging middleware that logs all requests in JSON format.
    Captures request and response details for monitoring.
    """

    def process_request(self, request):
        request._start_time = time.time()
        request._client_ip = self.get_client_ip(request)
        return None

    def process_response(self, request, response):
        start_time = getattr(request, "_start_time", time.time())
        duration = (time.time() - start_time) * 1000

        log_data = {
            "timestamp": time.time(),
            "method": request.method,
            "path": request.path,
            "ip": getattr(request, "_client_ip", self.get_client_ip(request)),
            "status_code": response.status_code,
            "duration_ms": round(duration, 2),
            "user_id": request.user.id if request.user.is_authenticated else None,
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:200],
            "referer": request.META.get("HTTP_REFERER", ""),
        }

        if response.status_code >= 500:
            access_logger.error(json.dumps(log_data))
        elif response.status_code >= 400:
            access_logger.warning(json.dumps(log_data))
        else:
            access_logger.info(json.dumps(log_data))

        if settings.DEBUG:
            response["X-Request-ID"] = f"{request._client_ip}-{int(start_time * 1000)}"
            response["X-Process-Time"] = str(round(duration, 2))

        return response

    @staticmethod
    def get_client_ip(request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip
