"""
Production Hardening — Reusable Retry Utility with Exponential Backoff.

Provides a decorator and function for retrying external API calls with:
  - Configurable max retries, base delay, max delay
  - Exponential backoff with jitter
  - Integration with CircuitBreaker
  - Structured logging of each attempt

Usage:
    @retry_with_backoff(max_retries=3, base_delay=1.0, exceptions=(ConnectionError, Timeout))
    def call_external_api():
        ...

    # Or as a function:
    result = retry_call(call_external_api, args=(arg1,), max_retries=3)
"""
import functools
import logging
import random
import time
from typing import Callable, Tuple, Type

logger = logging.getLogger('zygotrip.retry')


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    circuit_breaker_name: str = '',
):
    """
    Decorator for retrying functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
        backoff_factor: Multiplier for each subsequent delay
        jitter: Add random jitter to prevent thundering herd
        exceptions: Tuple of exception types to catch and retry
        circuit_breaker_name: Optional circuit breaker service name for integration
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            breaker = None
            if circuit_breaker_name:
                from apps.core.production import CircuitBreaker
                breaker = CircuitBreaker(circuit_breaker_name)

            last_exception = None
            for attempt in range(max_retries + 1):
                # Check circuit breaker
                if breaker and not breaker.can_execute():
                    logger.warning(
                        'Circuit breaker open for %s, failing fast',
                        circuit_breaker_name,
                    )
                    from apps.core.production import CircuitBreakerOpen
                    raise CircuitBreakerOpen(f'Circuit open for {circuit_breaker_name}')

                try:
                    result = func(*args, **kwargs)
                    if breaker:
                        breaker.record_success()
                    if attempt > 0:
                        logger.info(
                            '%s succeeded after %d retries',
                            func.__qualname__, attempt,
                        )
                    return result

                except exceptions as exc:
                    last_exception = exc
                    if breaker:
                        breaker.record_failure()

                    if attempt >= max_retries:
                        logger.error(
                            '%s failed after %d attempts: %s',
                            func.__qualname__, attempt + 1, exc,
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        '%s attempt %d/%d failed (%s), retrying in %.1fs',
                        func.__qualname__, attempt + 1, max_retries + 1,
                        type(exc).__name__, delay,
                    )
                    time.sleep(delay)

            raise last_exception  # Should not reach here, but safety net

        return wrapper
    return decorator


def retry_call(
    func: Callable,
    args=(),
    kwargs=None,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Call a function with retry logic (functional style, no decorator needed).

    Returns the function's return value on success.
    Raises the last exception on exhaustion.
    """
    kwargs = kwargs or {}

    @retry_with_backoff(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        exceptions=exceptions,
    )
    def _inner():
        return func(*args, **kwargs)

    return _inner()
