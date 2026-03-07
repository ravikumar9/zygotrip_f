"""
Request Logging Middleware
PHASE 5: Failure prevention
PHASE 6: Enhanced structured logging with request_id, user_id, endpoint, latency
"""
import logging
import time
import uuid
from django.utils import timezone

logger = logging.getLogger('request_logger')


class RequestLoggingMiddleware:
    """
    PHASE 6: Enhanced request logging with structured fields
    Logs: request_id (UUID), user_id, endpoint, latency
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Generate unique request ID (UUID)
        request_id = str(uuid.uuid4())
        request._request_id = request_id  # Store on request object
        
        # Start time
        start_time = time.time()
        
        # Extract user information
        user_id = None
        username = 'anonymous'
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_id = request.user.id
            username = request.user.username or request.user.email or str(user_id)
        
        # Extract endpoint information
        endpoint = f"{request.method} {request.path}"
        
        # Log incoming request
        logger.info(
            f"[{request_id[:8]}] {endpoint}",
            extra={
                'request_id': request_id,
                'user_id': user_id,
                'username': username,
                'method': request.method,
                'endpoint': request.path,
                'full_path': request.get_full_path(),
                'ip': self._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
                'timestamp': timezone.now().isoformat()
            }
        )
        
        # Process request
        response = self.get_response(request)
        
        # Calculate latency in milliseconds
        latency_ms = round((time.time() - start_time) * 1000, 2)
        
        # Attach request_id to response headers
        response['X-Request-ID'] = request_id
        
        # Log response with structured fields
        log_level = logging.INFO if response.status_code < 400 else logging.WARNING
        logger.log(
            log_level,
            f"[{request_id[:8]}] {endpoint} - {response.status_code} ({latency_ms}ms)",
            extra={
                'request_id': request_id,
                'user_id': user_id,
                'username': username,
                'method': request.method,
                'endpoint': request.path,
                'status_code': response.status_code,
                'latency': latency_ms,
                'latency_ms': latency_ms,  # Backwards compatibility
                'duration_ms': latency_ms,  # Backwards compatibility
                'timestamp': timezone.now().isoformat()
            }
        )
        
        return response
    
    def _get_client_ip(self, request):
        """Get client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip