import logging
import os

logger = logging.getLogger(__name__)


def initialize_firebase():
    """
    Initialize Firebase Admin SDK once at startup.
    Safe to call multiple times - checks firebase_admin._apps before init.
    Skips silently if credentials not configured (dev/CI environments).
    """
    creds_path = os.getenv('FIREBASE_CREDENTIALS_PATH', '')
    project_id = os.getenv('FCM_PROJECT_ID', '')

    if not creds_path and not project_id:
        logger.warning(
            'Firebase: FIREBASE_CREDENTIALS_PATH and FCM_PROJECT_ID not set - '
            'push notifications disabled. Set these env vars in production.'
        )
        return

    try:
        import firebase_admin
        from firebase_admin import credentials

        if firebase_admin._apps:
            return  # already initialized

        if creds_path and os.path.exists(creds_path):
            cred = credentials.Certificate(creds_path)
        else:
            cred = credentials.ApplicationDefault()

        firebase_admin.initialize_app(
            cred,
            {'projectId': project_id} if project_id else {}
        )
        logger.info('Firebase Admin SDK initialized (project=%s)', project_id or 'default')

    except ImportError:
        logger.warning('firebase-admin not installed - push notifications disabled')
    except Exception as exc:
        logger.exception('Firebase Admin init failed - push notifications disabled: %s', exc)
