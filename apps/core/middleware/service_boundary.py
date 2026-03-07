"""
Service Boundary Enforcement Middleware
PHASE 6: Architecture hardening - prevent ORM usage in views
"""
import logging
import time
from django.conf import settings
from django.db import connection
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


class ServiceBoundaryMiddleware:
    """
    PHASE 6: Enforce service layer boundaries
    Detects and prevents ORM queries inside view functions
    
    Views should only orchestrate - business logic belongs in services/selectors
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.strict_mode = getattr(settings, 'SERVICE_BOUNDARY_STRICT', False)
        self.enabled = getattr(settings, 'SERVICE_BOUNDARY_ENFORCEMENT', True)
    
    def __call__(self, request):
        if not self.enabled:
            return self.get_response(request)

        query_state = {
            'count': 0,
            'samples': []
        }

        def _query_wrapper(execute, sql, params, many, context):
            start = time.time()
            try:
                return execute(sql, params, many, context)
            finally:
                elapsed = round((time.time() - start), 4)
                query_state['count'] += 1
                if len(query_state['samples']) < 5:
                    query_state['samples'].append({
                        'sql': str(sql)[:200],
                        'time': elapsed
                    })

        # Execute view with query tracking
        with connection.execute_wrapper(_query_wrapper):
            response = self.get_response(request)

        query_count = query_state['count']

        # Check if queries were executed in view layer
        if query_count > 0:
            # Get request ID if available
            request_id = getattr(request, '_request_id', 'unknown')[:8]
            
            # Extract view information
            view_name = self._get_view_name(request)
            
            # Log the violation
            message = (
                f"[{request_id}] SERVICE BOUNDARY VIOLATION: "
                f"{query_count} database queries executed in view '{view_name}' "
                f"({request.method} {request.path})"
            )
            
            # Get sample queries for debugging
            query_details = []
            for i, query in enumerate(query_state['samples'], 1):
                query_details.append(f"  Query {i}: {query['sql']} ({query['time']}s)")
            
            details_str = "\n".join(query_details)
            if query_count > 5:
                details_str += f"\n  ... and {query_count - 5} more queries"
            
            full_message = f"{message}\n{details_str}"
            
            if self.strict_mode:
                # In strict mode, raise an error
                logger.error(full_message)
                raise ImproperlyConfigured(
                    f"Service boundary violation: {query_count} queries in view '{view_name}'. "
                    f"Move database logic to services or selectors."
                )
            else:
                # In permissive mode, just log a warning
                logger.warning(full_message)
                
                # Add header to response for debugging
                response['X-Service-Boundary-Warning'] = f"{query_count} queries in view"
        
        return response
    
    def _get_view_name(self, request):
        """Extract view name from request"""
        try:
            # Try to get the view function name
            if hasattr(request, 'resolver_match') and request.resolver_match:
                view_func = request.resolver_match.func
                
                # Handle class-based views
                if hasattr(view_func, 'view_class'):
                    return f"{view_func.view_class.__module__}.{view_func.view_class.__name__}"
                
                # Handle function-based views
                if hasattr(view_func, '__name__'):
                    module = view_func.__module__ if hasattr(view_func, '__module__') else 'unknown'
                    return f"{module}.{view_func.__name__}"
            
            return f"<unknown view for {request.path}>"
        except Exception as e:
            return f"<error getting view name: {e}>"