"""AI assistant service for ZygoTrip travel planning."""
import logging
import uuid

from django.conf import settings

from apps.ai.models import AIUsageLog, ConversationSession
from apps.ai.tools import TRAVEL_TOOLS, execute_tool

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are Zygo, ZygoTrip's friendly AI travel assistant. "
    "Help users find hotels, flights, and plan trips in India. Be concise. "
    "Always confirm before booking. Never call create_booking tools without the user "
    "explicitly saying they want to book."
)


class TravelAssistantService:
    def _get_session(self, user, session_id):
        if session_id:
            try:
                return ConversationSession.objects.get(uuid=session_id, user=user)
            except ConversationSession.DoesNotExist:
                pass
        return ConversationSession.objects.create(user=user, messages=[])

    def _content_to_text(self, content):
        parts = []
        for block in content:
            if getattr(block, 'type', '') == 'text' and getattr(block, 'text', ''):
                parts.append(block.text)
        return '\n'.join(parts).strip()

    def _serialize_block(self, block):
        block_type = getattr(block, 'type', '')
        if block_type == 'text':
            return {'type': 'text', 'text': getattr(block, 'text', '')}
        if block_type == 'tool_use':
            return {
                'type': 'tool_use',
                'id': getattr(block, 'id', ''),
                'name': getattr(block, 'name', ''),
                'input': dict(getattr(block, 'input', {}) or {}),
            }
        return {'type': block_type}

    def _serialize_content(self, content):
        return [self._serialize_block(block) for block in content]

    def chat(self, user, user_message, session_id=None):
        session = self._get_session(user, session_id)
        messages = list(session.messages)
        messages.append({'role': 'user', 'content': user_message})

        client = None
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=getattr(settings, 'ANTHROPIC_API_KEY', ''))
        except Exception as exc:
            logger.exception('Anthropic client init failed: %s', exc)
            raise

        input_tokens = 0
        output_tokens = 0
        final_text = ''

        while True:
            response = client.messages.create(
                model='claude-sonnet-4-6',
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=TRAVEL_TOOLS,
                messages=messages,
            )
            input_tokens += getattr(response.usage, 'input_tokens', 0)
            output_tokens += getattr(response.usage, 'output_tokens', 0)

            messages.append({'role': 'assistant', 'content': self._serialize_content(response.content)})

            if response.stop_reason == 'tool_use':
                tool_results = []
                for block in response.content:
                    if getattr(block, 'type', '') != 'tool_use':
                        continue
                    result = execute_tool(block.name, user, **dict(block.input or {}))
                    tool_results.append(
                        {
                            'type': 'tool_result',
                            'tool_use_id': block.id,
                            'content': str(result),
                        }
                    )
                messages.append({'role': 'user', 'content': tool_results})
                continue

            final_text = self._content_to_text(response.content)
            break

        session.messages = messages
        session.save(update_fields=['messages', 'updated_at'])

        AIUsageLog.objects.create(
            user=user,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model='claude-sonnet-4-6',
        )

        suggested_actions = ['search_hotels', 'search_flights', 'apply_promo']
        return {
            'response': final_text,
            'session_id': str(session.uuid),
            'suggested_actions': suggested_actions,
        }


travel_assistant_service = TravelAssistantService()
