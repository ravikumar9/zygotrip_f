"""
Global Exception Handler Middleware
PHASE 5: Failure prevention
PHASE 6: Standardized error response format
"""
import logging
import traceback
import uuid
from django.http import JsonResponse
from django.shortcuts import render
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import OperationalError, IntegrityError
from decimal import InvalidOperation

logger = logging.getLogger(__name__)


class GlobalExceptionMiddleware:
    """
    PHASE 6: Enhanced exception handling with standardized response format
    Format: {success: false, error_code: "...", message: "...", trace_id: "..."}
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            return self.handle_exception(request, e)
    
    def handle_exception(self, request, exception):
        """Handle different exception types with standardized format"""
        
        # Generate trace ID from request or create new one
        trace_id = getattr(request, '_request_id', str(uuid.uuid4()))
        
        # Sanitize POST data — strip sensitive fields before logging
        SENSITIVE_FIELDS = {'password', 'token', 'refresh', 'secret', 'otp', 'code', 'credit_card', 'cvv'}
        safe_post = {}
        if request.method == 'POST':
            for key, val in request.POST.items():
                safe_post[key] = '***REDACTED***' if key.lower() in SENSITIVE_FIELDS else val

        # Log the exception with trace_id
        logger.error(
            f"[{trace_id[:8]}] Unhandled exception: {type(exception).__name__}",
            exc_info=True,
            extra={
                'trace_id': trace_id,
                'user': getattr(request, 'user', None),
                'user_id': getattr(request.user, 'id', None) if hasattr(request, 'user') and request.user.is_authenticated else None,
                'path': request.path,
                'method': request.method,
                'GET': dict(request.GET),
                'POST': safe_post,
            }
        )
        
        # Determine response based on exception type
        if isinstance(exception, PermissionDenied):
            return self._handle_permission_denied(request, exception, trace_id)
        
        elif isinstance(exception, ValidationError):
            return self._handle_validation_error(request, exception, trace_id)
        
        elif isinstance(exception, (OperationalError, IntegrityError)):
            return self._handle_database_error(request, exception, trace_id)
        
        elif isinstance(exception, (ValueError, InvalidOperation, TypeError)):
            return self._handle_value_error(request, exception, trace_id)
        
        else:
            return self._handle_generic_error(request, exception, trace_id)
    
    def _create_error_response(self, error_code, message, trace_id, status_code, details=None):
        """
        PHASE 6: Standardized error response format
        """
        response_data = {
            'success': False,
            'error_code': error_code,
            'message': message,
            'trace_id': trace_id
        }
        
        if details:
            response_data['details'] = details
        
        return JsonResponse(response_data, status=status_code)
    
    def _handle_permission_denied(self, request, exception, trace_id):
        """Handle permission denied"""
        if request.headers.get('Accept') == 'application/json' or request.path.startswith('/api/'):
            return self._create_error_response(
                error_code='PERMISSION_DENIED',
                message=str(exception) or 'You do not have permission to perform this action',
                trace_id=trace_id,
                status_code=403
            )
        
        return render(request, '403.html', {
            'error': str(exception) or 'Permission denied',
            'trace_id': trace_id
        }, status=403)
    
    def _handle_validation_error(self, request, exception, trace_id):
        """Handle validation errors"""
        details = None
        if hasattr(exception, 'message_dict'):
            details = exception.message_dict
        elif hasattr(exception, 'messages'):
            details = exception.messages
        
        if request.headers.get('Accept') == 'application/json' or request.path.startswith('/api/'):
            return self._create_error_response(
                error_code='VALIDATION_ERROR',
                message='Validation failed',
                trace_id=trace_id,
                status_code=400,
                details=details or str(exception)
            )
        
        return render(request, '400.html', {
            'error': 'Validation failed',
            'details': str(exception),
            'trace_id': trace_id
        }, status=400)
    
    def _handle_database_error(self, request, exception, trace_id):
        """Handle database errors"""
        logger.critical(
            f"[{trace_id[:8]}] Database error: {type(exception).__name__}: {str(exception)}",
            exc_info=True
        )
        
        if request.headers.get('Accept') == 'application/json' or request.path.startswith('/api/'):
            return self._create_error_response(
                error_code='DATABASE_ERROR',
                message='Service temporarily unavailable',
                trace_id=trace_id,
                status_code=503
            )
        
        return render(request, '503.html', {
            'error': 'Service temporarily unavailable',
            'trace_id': trace_id
        }, status=503)
    
    def _handle_value_error(self, request, exception, trace_id):
        """Handle value/type errors"""
        if request.headers.get('Accept') == 'application/json' or request.path.startswith('/api/'):
            return self._create_error_response(
                error_code='INVALID_INPUT',
                message=str(exception) or 'Invalid input provided',
                trace_id=trace_id,
                status_code=400
            )
        
        return render(request, '400.html', {
            'error': 'Invalid input',
            'details': str(exception),
            'trace_id': trace_id
        }, status=400)
    
    def _handle_generic_error(self, request, exception, trace_id):
        """Handle all other errors"""
        if request.headers.get('Accept') == 'application/json' or request.path.startswith('/api/'):
            return self._create_error_response(
                error_code='INTERNAL_ERROR',
                message='An unexpected error occurred',
                trace_id=trace_id,
                status_code=500
            )
        
        return render(request, '500.html', {
            'error': 'Something went wrong',
            'support': 'Please contact support if this persists',
            'trace_id': trace_id
        }, status=500)