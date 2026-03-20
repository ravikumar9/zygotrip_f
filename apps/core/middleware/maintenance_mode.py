from django.http import JsonResponse, HttpResponse

from ..platform_settings import get_platform_settings


class MaintenanceModeMiddleware:
    """Block non-admin traffic when platform maintenance mode is enabled."""

    EXEMPT_PREFIXES = (
        "/admin/",
        "/api/health/",
        "/api/v1/platform/config/",
        "/api/schema/",
        "/api/docs/",
        "/api/redoc/",
        "/static/",
        "/media/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or "/"

        if path.startswith(self.EXEMPT_PREFIXES):
            return self.get_response(request)

        settings_obj = get_platform_settings()
        if not settings_obj.maintenance_mode:
            return self.get_response(request)

        user = getattr(request, "user", None)
        if user and user.is_authenticated and (user.is_staff or user.is_superuser):
            return self.get_response(request)

        message = settings_obj.maintenance_message or "Platform is under maintenance."
        if path.startswith("/api/"):
            return JsonResponse(
                {
                    "success": False,
                    "error": {
                        "code": "maintenance_mode",
                        "message": message,
                    },
                },
                status=503,
            )

        return HttpResponse(message, status=503)
