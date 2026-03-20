import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='ConversationSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('session_id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ('messages', models.JSONField(blank=True, default=list)),
                ('title', models.CharField(blank=True, max_length=200)),
                ('is_archived', models.BooleanField(db_index=True, default=False)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ai_conversations',
                    to=settings.AUTH_USER_MODEL,
                    db_index=True,
                )),
            ],
            options={'app_label': 'ai_assistant', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='AIUsageLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('tokens_used', models.PositiveIntegerField(default=0)),
                ('cost_usd', models.DecimalField(decimal_places=6, default=0, max_digits=10)),
                ('endpoint', models.CharField(default='chat', max_length=100)),
                ('user', models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ai_usage_logs',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('session', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='usage_logs',
                    to='ai_assistant.conversationsession',
                )),
            ],
            options={'app_label': 'ai_assistant', 'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='conversationsession',
            index=models.Index(fields=['user', '-created_at'], name='ai_sess_user_idx'),
        ),
        migrations.AddIndex(
            model_name='aiusagelog',
            index=models.Index(fields=['user', '-created_at'], name='ai_usage_user_idx'),
        ),
    ]
