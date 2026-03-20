"""API v1 views for AI assistant chat."""
import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.services import travel_assistant_service
from apps.core.service_guard import require_service_enabled

logger = logging.getLogger(__name__)


class ChatView(APIView):
    permission_classes = [IsAuthenticated]

    @require_service_enabled('ai')
    def post(self, request):
        message = (request.data.get('message') or '').strip()
        session_id = request.data.get('session_id')
        if not message:
            return Response({'error': 'message is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = travel_assistant_service.chat(
                user=request.user,
                user_message=message,
                session_id=session_id,
            )
        except Exception as exc:
            logger.exception('AI chat failed: %s', exc)
            return Response({'error': 'AI assistant unavailable'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(
            {
                'response': result['response'],
                'session_id': result['session_id'],
                'suggested_actions': result['suggested_actions'],
            },
            status=status.HTTP_200_OK,
        )
