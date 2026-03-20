"""Firebase bootstrap for server-side FCM usage."""
import json
import logging
import os

logger = logging.getLogger('zygotrip.firebase')


def initialize_firebase_app():
    """Initialize Firebase Admin if credentials are configured.

    This is idempotent and safe to call multiple times.
    """
    try:
        import firebase_admin
        from firebase_admin import credentials
    except Exception as exc:
        logger.info('firebase-admin not installed; push will remain best-effort. err=%s', exc)
        return None

    if firebase_admin._apps:
        return firebase_admin.get_app()

    creds_path = os.getenv('FIREBASE_CREDENTIALS_PATH', '').strip()
    creds_json = os.getenv('FIREBASE_CREDENTIALS_JSON', '').strip()

    try:
        if creds_path:
            app = firebase_admin.initialize_app(credentials.Certificate(creds_path))
            logger.info('Firebase initialized using FIREBASE_CREDENTIALS_PATH')
            return app

        if creds_json:
            cert_dict = json.loads(creds_json)
            app = firebase_admin.initialize_app(credentials.Certificate(cert_dict))
            logger.info('Firebase initialized using FIREBASE_CREDENTIALS_JSON')
            return app

        logger.info('Firebase credentials not configured; push will remain best-effort.')
        return None
    except Exception as exc:
        logger.warning('Firebase initialization skipped: %s', exc)
        return None
