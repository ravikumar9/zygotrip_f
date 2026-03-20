"""
ASGI config for ZygoTrip — supports both HTTP and WebSocket (Django Channels).
"""
import os
import django
import importlib.util
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zygotrip_project.settings')
django.setup()

if importlib.util.find_spec('channels') is None:
    application = get_asgi_application()
else:
    # Import after django.setup() so apps are ready
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.auth import AuthMiddlewareStack
    from apps.realtime.routing import websocket_urlpatterns

    application = ProtocolTypeRouter({
        'http': get_asgi_application(),
        'websocket': AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        ),
    })
