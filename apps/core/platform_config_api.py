from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.core.platform_settings import get_platform_settings


@api_view(['GET'])
@permission_classes([AllowAny])
def platform_config_view(request):
    settings_obj = get_platform_settings()
    services = {
        'hotels': settings_obj.hotels_enabled,
        'buses': settings_obj.buses_enabled,
        'cabs': settings_obj.cabs_enabled,
        'packages': settings_obj.packages_enabled,
        'flights': settings_obj.flights_enabled,
        'activities': settings_obj.activities_enabled,
        'ai': settings_obj.ai_assistant_enabled,
        'loyalty': settings_obj.loyalty_enabled,
        'promos': settings_obj.promos_enabled,
    }

    return Response(
        {
            'success': True,
            'data': {
                'platform_name': settings_obj.platform_name,
                'maintenance_mode': settings_obj.maintenance_mode,
                'maintenance_message': settings_obj.maintenance_message,
                'bookings_enabled': settings_obj.bookings_enabled,
                'payments_enabled': settings_obj.payments_enabled,
                'services': services,
                'support': {
                    'email': settings_obj.support_email,
                    'phone': settings_obj.support_phone,
                },
                'currency': settings_obj.default_currency,
                'system_notice': settings_obj.system_notice,
                'app_versions': {
                    'min_android': settings_obj.min_app_version_android,
                    'min_ios': settings_obj.min_app_version_ios,
                },
            },
        }
    )
