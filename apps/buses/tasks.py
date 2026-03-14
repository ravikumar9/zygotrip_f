"""Bus app Celery tasks: seat lock enforcement."""
import logging
from celery import shared_task

logger = logging.getLogger('zygotrip.buses.tasks')


@shared_task
def release_expired_seat_locks():
    """Release bus seats with expired TTL locks. Runs every minute."""
    try:
        from apps.buses.models import BusSeat
        count = BusSeat.release_expired_locks()
        if count:
            logger.info('Released %d expired bus seat locks', count)
        return {'released': count}
    except Exception as exc:
        logger.error('release_expired_seat_locks failed: %s', exc)
        return {'error': str(exc)}
