"""AI conversation persistence and usage tracking."""
import uuid

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class ConversationSession(TimeStampedModel):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_sessions')
    messages = models.JSONField(default=list, blank=True)

    class Meta:
        app_label = 'ai_assistant'
        ordering = ['-updated_at']

    def __str__(self):
        return f"ConversationSession({self.uuid}, user={self.user_id})"


class AIUsageLog(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_usage_logs')
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    model = models.CharField(max_length=100, default='claude-sonnet-4-6')

    class Meta:
        app_label = 'ai_assistant'
        ordering = ['-created_at']

    def __str__(self):
        return f"AIUsageLog(user={self.user_id}, model={self.model})"
