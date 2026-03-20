"""WebSocket consumers for booking status and user notifications."""
import json
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from rest_framework_simplejwt.tokens import AccessToken


class BookingStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.booking_uuid = self.scope['url_route']['kwargs']['booking_uuid']
        self.group_name = f'booking_{self.booking_uuid}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            payload = json.loads(text_data or '{}')
        except Exception:
            payload = {}
        if payload.get('type') == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))

    async def booking_update(self, event):
        await self.send_update(event)

    async def send_update(self, data):
        await self.send(
            text_data=json.dumps(
                {
                    'status': data.get('status'),
                    'updated_at': data.get('updated_at'),
                    'message': data.get('message', ''),
                }
            )
        )


class UserNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        token = self._get_query_token()
        user_id = await self._resolve_user_id(token)
        if not user_id:
            await self.close(code=4001)
            return

        self.user_id = user_id
        self.group_name = f'user_{self.user_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            payload = json.loads(text_data or '{}')
        except Exception:
            payload = {}
        if payload.get('type') == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))

    async def user_notification(self, event):
        await self.send(text_data=json.dumps(event.get('payload', {})))

    def _get_query_token(self):
        query_string = self.scope.get('query_string', b'').decode('utf-8')
        params = parse_qs(query_string)
        return (params.get('token') or [None])[0]

    @database_sync_to_async
    def _resolve_user_id(self, token):
        if not token:
            return None
        try:
            validated = AccessToken(token)
            return validated.get('user_id')
        except Exception:
            return None
