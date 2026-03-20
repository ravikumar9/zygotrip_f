from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/booking/(?P<booking_uuid>[0-9a-f-]+)/status/$', consumers.BookingStatusConsumer.as_asgi()),
    re_path(r'^ws/notifications/$', consumers.UserNotificationConsumer.as_asgi()),
]
