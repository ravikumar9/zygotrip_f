import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zygotrip_project.settings')

app = Celery('zygotrip')

# Load configuration from Django settings with namespace CELERY
app.config_from_object('django.conf:settings', namespace='CELERY')

# Discover tasks from all registered Django apps
app.autodiscover_tasks()

# Task error handling and routing
@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

# Optimize task execution
app.conf.update(
    task_always_eager=False,
    task_eager_propagates=False,
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    task_acks_late=True,
    worker_disable_rate_limits=False,
)

# Scheduled tasks (Celery Beat)
app.conf.beat_schedule = {
    'auto-approve-pending-changes': {
        'task': 'hotels.auto_approve_pending_changes',
        'schedule': crontab(minute='0'),  # Every hour
    },
    'notify-pending-changes': {
        'task': 'hotels.notify_pending_changes',
        'schedule': crontab(hour='9', minute='0'),  # Every day at 9 AM
    },
}
