from functools import wraps

from rest_framework.response import Response
from rest_framework import status

from apps.core.platform_settings import get_platform_settings


SERVICE_FIELD_MAP = {
    'hotels': 'hotels_enabled',
    'buses': 'buses_enabled',
    'cabs': 'cabs_enabled',
    'packages': 'packages_enabled',
    'flights': 'flights_enabled',
    'activities': 'activities_enabled',
    'ai': 'ai_assistant_enabled',
    'loyalty': 'loyalty_enabled',
    'promos': 'promos_enabled',
    'bookings': 'bookings_enabled',
    'payments': 'payments_enabled',
}


def _service_disabled_response(service_name):
    return Response(
        {
            'success': False,
            'error': {
                'code': 'service_disabled',
                'message': f'{service_name} services are currently disabled by platform admin.',
            },
        },
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def require_service_enabled(service_name):
    """Decorator for DRF function/class-based views to gate disabled services."""
    field_name = SERVICE_FIELD_MAP.get(service_name, f'{service_name}_enabled')

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            settings_obj = get_platform_settings()
            if not getattr(settings_obj, field_name, True):
                return _service_disabled_response(service_name)
            return view_func(*args, **kwargs)

        return wrapped

    return decorator
