"""
Celery tasks for inventory management.

Phase 3: Expired hold cleanup runs every 2 minutes.
"""
import logging
from celery import shared_task

logger = logging.getLogger('zygotrip.inventory')


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def release_expired_inventory_holds(self):
    """
    Release all expired inventory holds (TTL 15 min).
    Runs every 2 minutes via Celery Beat.

    Schedule in celery.py:
        'release-expired-holds': {
            'task': 'apps.inventory.tasks.release_expired_inventory_holds',
            'schedule': crontab(minute='*/2'),
        }
    """
    try:
        from apps.inventory.services import release_expired_holds
        released = release_expired_holds()
        if released:
            logger.info(f"Released {released} expired inventory holds")
        return {'released': released}
    except Exception as exc:
        logger.error(f"Failed to release expired holds: {exc}")
        raise self.retry(exc=exc)
