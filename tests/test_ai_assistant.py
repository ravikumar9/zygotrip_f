import types

import pytest
from rest_framework.test import APIClient

from apps.ai.services import TravelAssistantService


class _DummyUsage:
    input_tokens = 10
    output_tokens = 5


class _DummyTextBlock:
    type = 'text'
    text = 'Here are hotel options.'


class _DummyResponse:
    stop_reason = 'end_turn'
    content = [_DummyTextBlock()]
    usage = _DummyUsage()


@pytest.mark.django_db
def test_tool_execution_calls_django_service(monkeypatch, user_factory):
    user = user_factory()

    class DummyClient:
        class messages:
            @staticmethod
            def create(**kwargs):
                return _DummyResponse()

    monkeypatch.setattr('anthropic.Anthropic', lambda api_key=None: DummyClient())
    monkeypatch.setattr('django.conf.settings.ANTHROPIC_API_KEY', 'test-key')

    result = TravelAssistantService().chat(user=user, user_message='Find hotels in Goa')
    assert 'response' in result


@pytest.mark.django_db
def test_session_history_persisted(monkeypatch, user_factory):
    user = user_factory()

    class DummyClient:
        class messages:
            @staticmethod
            def create(**kwargs):
                return _DummyResponse()

    monkeypatch.setattr('anthropic.Anthropic', lambda api_key=None: DummyClient())
    monkeypatch.setattr('django.conf.settings.ANTHROPIC_API_KEY', 'test-key')

    result = TravelAssistantService().chat(user=user, user_message='Plan trip to Jaipur')
    from apps.ai.models import ConversationSession

    session = ConversationSession.objects.get(uuid=result['session_id'])
    assert len(session.messages) >= 1


@pytest.mark.django_db
def test_rate_limit_enforced(user_factory):
    user = user_factory()
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/v1/ai/chat/', {'message': ''}, format='json')
    assert response.status_code == 400
