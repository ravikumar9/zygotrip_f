import pytest
from unittest.mock import patch, MagicMock
from apps.notifications.fcm_service import FCMService
from apps.notifications.models import DeviceToken


class TestFCMService:
    def test_send_to_user_no_tokens_returns_zero(self, user):
        result = FCMService().send_to_user(user, 'Title', 'Body')
        assert result['sent_count'] == 0

    def test_send_to_user_calls_firebase(self, user, db):
        DeviceToken.objects.create(
            user=user, token='test-fcm-token-123',
            platform='android', is_active=True
        )
        with patch('firebase_admin.messaging.send_each_for_multicast') as mock_send:
            mock_resp = MagicMock()
            mock_resp.success_count = 1
            mock_resp.responses = [MagicMock(success=True)]
            mock_send.return_value = mock_resp
            result = FCMService().send_to_user(user, 'Test Title', 'Test Body', {'type': 'test'})
        assert result['sent_count'] == 1
        mock_send.assert_called_once()

    def test_expired_token_marked_inactive(self, user, db):
        token = DeviceToken.objects.create(
            user=user, token='expired-token-abc',
            platform='ios', is_active=True
        )
        with patch('firebase_admin.messaging.send_each_for_multicast') as mock_send:
            mock_resp = MagicMock()
            mock_resp.success_count = 0
            exc_mock = MagicMock()
            exc_mock.__class__.__name__ = 'UnregisteredError'
            mock_resp.responses = [MagicMock(success=False, exception=exc_mock)]
            mock_send.return_value = mock_resp
            FCMService().send_to_user(user, 'Title', 'Body')
        token.refresh_from_db()
        assert token.is_active is False
