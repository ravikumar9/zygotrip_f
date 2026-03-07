"""
Timeout Protection Middleware
PHASE 5: Failure prevention
"""
import logging
import signal
from django.http import JsonResponse
from django.shortcuts import render

logger = logging.getLogger(__name__)


class TimeoutException(Exception):
    """Custom timeout exception"""
    pass


class TimeoutMiddleware:
    """Add timeout protection to requests"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.timeout_seconds = 30  # 30 second timeout
    
    def __call__(self, request):
        # Skip timeout for admin and static files
        if request.path.startswith('/admin/') or request.path.startswith('/static/'):
            return self.get_response(request)
        
        # Set alarm (Unix only - disabled on Windows)
        try:
            signal.signal(signal.SIGALRM, self._timeout_handler)
            signal.alarm(self.timeout_seconds)
        except (AttributeError, ValueError):
            # SIGALRM not available on Windows - skip timeout
            pass
        
        try:
            response = self.get_response(request)
            return response
        except TimeoutException:
            logger.warning(
                f"Request timeout: {request.method} {request.path}",
                extra={
                    'path': request.path,
                    'method': request.method,
                    'timeout': self.timeout_seconds
                }
            )
            
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({
                    'error': 'Request timeout',
                    'detail': f'Request exceeded {self.timeout_seconds} seconds'
                }, status=504)
            
            return render(request, '504.html', {
                'error': 'Request timeout',
                'timeout': self.timeout_seconds
            }, status=504)
        finally:
            # Cancel alarm
            try:
                signal.alarm(0)
            except (AttributeError, ValueError):
                pass
    
    def _timeout_handler(self, signum, frame):
        """Handle timeout signal"""
        raise TimeoutException("Request timed out")