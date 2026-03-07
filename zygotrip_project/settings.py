from pathlib import Path
import logging
import os
import socket

BASE_DIR = Path(__file__).resolve().parent.parent


# ======================================================
# CORE - PRODUCTION SECURITY
# ======================================================

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-dev-key")

# DEBUG MODE - default to safe local development unless explicitly disabled
DEBUG = os.getenv("DEBUG", "true").lower() in {"1", "true", "yes"}

if SECRET_KEY == "unsafe-dev-key" and not DEBUG:
    import sys
    print(
        "\n[CRITICAL] DJANGO_SECRET_KEY is not set! "
        "Running with an unsafe dev key in a non-DEBUG environment is a security risk.\n",
        file=sys.stderr,
    )
    raise RuntimeError(
        "Set the DJANGO_SECRET_KEY environment variable before running in production."
    )

# ALLOWED_HOSTS - Must be explicitly configured in production
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost,testserver").split(",")

# CSP: unsafe-inline is a necessary dev convenience but should be tightened in
# production by adding a nonce-based approach. Tracked as TODO: prod-csp-hardening.
SECURE_CONTENT_SECURITY_POLICY = {
    "default-src": ("'self'",),
    # CSP nonce injection handled by NonceMiddleware in production
    "script-src": ("'self'", "'unsafe-inline'") if DEBUG else ("'self'",),
    "style-src": ("'self'", "'unsafe-inline'", "https://fonts.googleapis.com") if DEBUG else ("'self'", "https://fonts.googleapis.com"),
    "font-src": ("'self'", "https://fonts.gstatic.com"),
    "img-src": ("'self'", "data:", "https:"),
}

# HTTPS enforcement in production
# FORCE SAFE DEV MODE: When DEBUG=True, disable all SSL
SECURE_SSL_REDIRECT = False if DEBUG else True
SESSION_COOKIE_SECURE = False if DEBUG else True
CSRF_COOKIE_SECURE = False if DEBUG else True
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000  # 1 year in production only
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

# Additional security headers
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

# Log safe dev mode
if DEBUG:
    print("=" * 60)
    print("[DEV] RUNNING IN SAFE DEV MODE (LOCAL TESTING)")
    print("=" * 60)
    print("[OK] SSL redirect disabled")
    print("[OK] Secure cookies disabled")
    print("[OK] HSTS disabled")
    print("[OK] Celery eager execution enabled")
    print("=" * 60)


# ======================================================
# INSTALLED APPS
# ======================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "django_extensions",

    # project apps
    "apps.accounts",
    "apps.core",
    "apps.search",
    "apps.hotels",
    "apps.rooms",
    "apps.meals",
    "apps.pricing",
    "apps.booking",
    "apps.payments",
    "apps.wallet",
    "apps.promos",
    "apps.buses",
    "apps.packages",
    "apps.cabs",
    "apps.inventory",
    "apps.offers",
    "apps.dashboard_owner",
    "apps.dashboard_admin",
    "apps.dashboard_finance",

    # celery
    "django_celery_beat",
    "django_celery_results",
]


# ======================================================
# MIDDLEWARE
# ======================================================

MIDDLEWARE = [
    # CorsMiddleware must be first — before any response-generating middleware
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "apps.core.production.RequestIDMiddleware",  # Request tracing
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    "apps.core.middleware.GlobalExceptionMiddleware",
    "apps.core.middleware.RateLimitMiddleware",
    "apps.core.gateway_middleware.APIGatewayMiddleware",  # Section 18: API Gateway Protection
    "apps.core.middleware.StructuredLoggingMiddleware",
    "apps.core.production.SlowRequestMiddleware",  # Performance monitoring
    "apps.core.metrics.MetricsMiddleware",  # S15: Prometheus request instrumentation
    "apps.core.feature_flags.FeatureFlagMiddleware",  # S14: Feature flags per request
]


ROOT_URLCONF = "zygotrip_project.urls"
APPEND_SLASH = False
WSGI_APPLICATION = "zygotrip_project.wsgi.application"


# ======================================================
# TEMPLATES
# ======================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# ======================================================
# DATABASE - FORCE POSTGRESQL ONLY
# ======================================================

POSTGRES_DB = os.getenv("POSTGRES_DB", "zygotrip")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": POSTGRES_DB,
        "USER": POSTGRES_USER,
        "PASSWORD": POSTGRES_PASSWORD,
        "HOST": POSTGRES_HOST,
        "PORT": POSTGRES_PORT,
        # CONN_MAX_AGE: reuse connections across requests (seconds).
        # 600s for production; set to 0 in tests.
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "600" if not DEBUG else "60")),
        # PostgreSQL-specific options for production performance
        "OPTIONS": {
            # statement_timeout: kill queries running >10 s
            "options": "-c statement_timeout=10000",
        },
    }
}

# ── Read Replica (Section 15) ─────────────────────────────────────────────
# Set DB_REPLICA_HOST to enable a read-replica for search / analytics queries.
_REPLICA_HOST = os.getenv("DB_REPLICA_HOST", "")
if _REPLICA_HOST:
    DATABASES["replica"] = {
        **DATABASES["default"],
        "HOST": _REPLICA_HOST,
        "PORT": os.getenv("DB_REPLICA_PORT", POSTGRES_PORT),
        "CONN_MAX_AGE": int(os.getenv("DB_REPLICA_CONN_MAX_AGE", "600")),
        "OPTIONS": {
            "options": "-c statement_timeout=15000 -c default_transaction_read_only=on",
        },
    }
    DATABASE_ROUTERS = ['zygotrip_project.db_router.ReadReplicaRouter']


# ======================================================
# PASSWORD VALIDATORS
# ======================================================

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ======================================================
# INTERNATIONALIZATION
# ======================================================

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"

USE_I18N = True
USE_TZ = True

CURRENCY_CODE = "INR"
CURRENCY_SYMBOL = "â‚¹"
REGION_DEFAULT = "IN"


# ======================================================
# STATIC + MEDIA
# ======================================================

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
WHITENOISE_MANIFEST_STRICT = False

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# ======================================================
# AUTH
# ======================================================

AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "core:home"


# ======================================================
# BUSINESS LOGIC
# ======================================================
# NOTE: Canonical pricing logic lives in apps.pricing.pricing_service.
# These constants are kept for legacy views only. Do NOT use for new code.
# Actual fee: 5% capped at ₹500.  GST: 5% (tariff ≤₹7500), 18% above.

SERVICE_FEE_RATE = 0.05          # 5% (capped at ₹500 in pricing_service)
GST_RATE_LOW = 0.05              # tariff ≤ ₹7,500 per night
GST_RATE_HIGH = 0.18             # tariff > ₹7,500 per night
# DEPRECATED — do not use flat GST_RATE for new code
GST_RATE = GST_RATE_LOW


# ======================================================
# REDIS CACHE
# ======================================================

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
USE_REDIS_CACHE = os.getenv("USE_REDIS_CACHE", "false").lower() in {"1", "true", "yes"}

def _redis_available(host, port):
    try:
        socket.create_connection((host, int(port)), timeout=0.3).close()
        return True
    except OSError:
        logging.getLogger("zygotrip").warning(
            "Redis unreachable. Falling back to local memory cache.")
        return False

if USE_REDIS_CACHE and _redis_available(REDIS_HOST, REDIS_PORT):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/1",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "zygotrip-fallback",
        }
    }


# ======================================================
# CELERY
# ======================================================

CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/2"

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 1800
CELERY_RESULT_EXPIRES = 3600

# PHASE 9: FORCE SAFE DEV MODE - Disable Celery beat in DEBUG, run tasks eagerly
if DEBUG:
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    CELERY_BEAT_SCHEDULE = {}  # Disable all scheduled tasks in dev
else:
    CELERY_TASK_ALWAYS_EAGER = False
    CELERY_TASK_EAGER_PROPAGATES = False
    CELERY_BEAT_SCHEDULE = {
        "release-expired-booking-holds": {
            "task": "apps.core.tasks.release_expired_booking_holds",
            "schedule": 120.0,  # Every 2 minutes
        },
        "release-expired-inventory-holds": {
            "task": "apps.inventory.tasks.release_expired_inventory_holds",
            "schedule": 120.0,  # Every 2 minutes
        },
        "cleanup-expired-bookings": {
            "task": "apps.core.tasks.cleanup_expired_bookings",
            "schedule": 300.0,  # Every 5 minutes
        },
        "generate-daily-reports": {
            "task": "apps.core.tasks.generate_daily_reports",
            "schedule": 86400.0,  # Daily
        },
        "compute-daily-analytics": {
            "task": "apps.core.tasks.compute_daily_analytics",
            "schedule": 86400.0,  # Daily
        },
        "update-property-rankings": {
            "task": "apps.core.tasks.bulk_update_property_rankings",
            "schedule": 86400.0,  # Daily
        },
        # ── Section 14: Inventory sync workers ──
        "recompute-inventory-pools": {
            "task": "apps.core.tasks.recompute_inventory_pools",
            "schedule": 300.0,  # Every 5 minutes
        },
        "supplier-availability-sync": {
            "task": "apps.core.tasks.supplier_availability_sync",
            "schedule": 600.0,  # Every 10 minutes
        },
        "sync-search-index": {
            "task": "apps.core.tasks.sync_search_index",
            "schedule": 1800.0,  # Every 30 minutes
        },
        "flush-stale-cache": {
            "task": "apps.core.tasks.flush_stale_cache_entries",
            "schedule": 900.0,  # Every 15 minutes
        },
        # ── Section 13: Payment reconciliation ──
        "reconcile-payments": {
            "task": "apps.core.tasks.reconcile_gateway_transactions",
            "schedule": 900.0,  # Every 15 minutes
        },
        # ── Section 6: Revenue optimization (demand forecasting) ──
        "demand-forecasting": {
            "task": "apps.core.tasks.run_demand_forecasting",
            "schedule": 86400.0,  # Daily at 2 AM
        },
        "quality-scoring": {
            "task": "apps.core.tasks.compute_quality_scores",
            "schedule": 86400.0,  # Daily at 3 AM
        },
        "competitor-price-scan": {
            "task": "apps.core.tasks.competitor_price_scan",
            "schedule": 86400.0,  # Daily at 4 AM
        },
        # ── S2: Price Lock TTL enforcement ──
        "expire-stale-price-locks": {
            "task": "booking.expire_stale_price_locks",
            "schedule": 120.0,  # Every 2 minutes
        },
        "expire-abandoned-contexts": {
            "task": "booking.expire_abandoned_contexts",
            "schedule": 300.0,  # Every 5 minutes
        },
        # ── S3/S4: Cache warming (popular cities + rate cache) ──
        "warm-popular-city-caches": {
            "task": "apps.core.tasks.warm_popular_city_caches",
            "schedule": 3600.0,  # Every hour
        },
        "refresh-rate-cache-bulk": {
            "task": "apps.core.tasks.refresh_rate_cache_bulk",
            "schedule": 3600.0,  # Every hour
        },
        # ── S5: Missing webhook detection ──
        "detect-missing-webhooks": {
            "task": "apps.core.tasks.detect_missing_webhooks",
            "schedule": 900.0,  # Every 15 minutes
        },
        # ── S5/S9: Inconsistent booking state fixer ──
        "fix-inconsistent-booking-states": {
            "task": "apps.core.tasks.fix_inconsistent_booking_states",
            "schedule": 900.0,  # Every 15 minutes
        },
        # ── S10: Fraud scan ──
        "scheduled-fraud-scan": {
            "task": "apps.core.tasks.scheduled_fraud_scan",
            "schedule": 1800.0,  # Every 30 minutes
        },
    }


# ======================================================
# LOGGING
# ======================================================

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Configure handlers based on environment
# Development: console only (avoids file locking issues on Windows)
# Production: console + rotating file
if DEBUG:
    LOGGING_HANDLERS = ["console"]
else:
    LOGGING_HANDLERS = ["console", "file"]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "apps.core.logging_formatters.JSONFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "zygotrip.log",
            "maxBytes": 10485760,
            "backupCount": 5,
            "formatter": "json",
        },
    },
    "loggers": {
        "django": {
            "handlers": LOGGING_HANDLERS,
            "level": "INFO",
            "propagate": False,
        },
        "zygotrip": {
            "handlers": LOGGING_HANDLERS,
            "level": "DEBUG",
            "propagate": False,
        },
        "zygotrip.api": {
            "handlers": LOGGING_HANDLERS,
            "level": "INFO",
            "propagate": False,
        },
        "access": {
            "handlers": LOGGING_HANDLERS,
            "level": "INFO",
            "propagate": False,
        },
    },
}


# ======================================================
# RATE LIMIT
# ======================================================

RATE_LIMIT_CONFIG = {
    "enabled": True,   # FIXED: Rate limiting must be ON by default
    "window_size": 60,
    "requests_per_window": {
        "default": 100,
        "search": 50,
        "booking": 20,
        "payment": 10,
    },
    "redis_key_prefix": "ratelimit:",
}


# ======================================================
# DEFAULT FIELD
# ======================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ======================================================
# FEATURE FLAGS - MARKETPLACE FEATURES
# ======================================================

FEATURE_FLAGS = {
    # Core features
    'FLIGHTS_ENABLED': False,
    'TRAINS_ENABLED': False,
    'CABS_ENABLED': True,
    'HOTELS_ENABLED': True,
    'BUSES_ENABLED': True,
    'PACKAGES_ENABLED': True,

    # Marketplace features
    'PROPERTY_IMAGES_ENABLED': True,
    'ROOM_TYPES_ENABLED': True,
    'MEAL_PLANS_ENABLED': True,
    'PROPERTY_OFFERS_ENABLED': True,
    'RATING_BREAKDOWN_ENABLED': True,
    'CATEGORIES_ENABLED': True,

    # Advanced features
    'OWNER_DASHBOARD_UPLOADS': True,
    'DYNAMIC_PRICING': True,
    'MULTI_IMAGE_GALLERY': True,
    'OFFER_SYSTEM': True,
    'ADVANCED_FILTERS': True,
}

# django-extensions already in INSTALLED_APPS above (removed stray append)

# ======================================================
# DJANGO REST FRAMEWORK
# ======================================================

REST_FRAMEWORK = {
    # Pagination: standardised across all API endpoints
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,

    # Authentication: JWT (primary) + session (admin/browsable API fallback)
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],

    # Permissions: read-only for unauthenticated, full for authenticated
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],

    # Filtering, ordering, search via django-filter
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],

    # Standardised JSON renderer only (no browsable API in production)
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ] if not DEBUG else [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],

    # Throttling (integrates with existing RATE_LIMIT_CONFIG)
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/minute',
        'user': '300/minute',
        'otp': '30/hour',
        'payment': '10/minute',
        'auth': '20/minute',
        'login_bruteforce': '5/minute',
        'webhook': '60/minute',
        'search': '100/minute',
    },

    # Versioning: URL-based (/api/v1/...)
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1'],

    # Exception handling: return structured error responses
    'EXCEPTION_HANDLER': 'apps.core.api_validators.drf_exception_handler',
}


# ======================================================
# JWT AUTHENTICATION (Simple JWT)
# ======================================================

from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',
}


# ======================================================
# PAYMENT GATEWAY CREDENTIALS
# Set these in environment variables for production
# ======================================================

CASHFREE_APP_ID = os.getenv('CASHFREE_APP_ID', '')
CASHFREE_SECRET_KEY = os.getenv('CASHFREE_SECRET_KEY', '')
CASHFREE_ENV = os.getenv('CASHFREE_ENV', 'sandbox')  # 'sandbox' or 'production'

STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')

PAYTM_MERCHANT_ID = os.getenv('PAYTM_MERCHANT_ID', '')
PAYTM_MERCHANT_KEY = os.getenv('PAYTM_MERCHANT_KEY', '')
PAYTM_ENV = os.getenv('PAYTM_ENV', 'staging')  # 'staging' or 'production'

# Payment callback URLs (used by gateway SDKs)
PAYMENT_SUCCESS_URL = os.getenv('PAYMENT_SUCCESS_URL', 'http://localhost:3000/booking/confirmation')
PAYMENT_CANCEL_URL = os.getenv('PAYMENT_CANCEL_URL', 'http://localhost:3000/payment/cancelled')
CASHFREE_WEBHOOK_SECRET = os.getenv('CASHFREE_WEBHOOK_SECRET', '')

# ======================================================
# OTP & SMS CONFIGURATION
# ======================================================

SMS_BACKEND = os.getenv('SMS_BACKEND', 'console')  # 'console', 'twilio', 'msg91'
OTP_EXPIRY_MINUTES = int(os.getenv('OTP_EXPIRY_MINUTES', '5'))
MAX_OTP_PER_HOUR = int(os.getenv('MAX_OTP_PER_HOUR', '5'))
OTP_DEBUG_CODE = os.getenv('OTP_DEBUG_CODE', '123456') if DEBUG else None  # Fixed code for dev

# Twilio (if SMS_BACKEND='twilio')
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
TWILIO_FROM_NUMBER = os.getenv('TWILIO_FROM_NUMBER', '')

# MSG91 (if SMS_BACKEND='msg91')
MSG91_AUTH_KEY = os.getenv('MSG91_AUTH_KEY', '')
MSG91_TEMPLATE_ID = os.getenv('MSG91_TEMPLATE_ID', '')

# ======================================================
# CORS — Cross-Origin Resource Sharing
# Required when Next.js (localhost:3000) calls Django
# (127.0.0.1:8000) directly (baseURL: http://127.0.0.1:8000/api/v1)
# ======================================================

_raw_cors_origins = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000"
)
CORS_ALLOWED_ORIGINS = [o.strip() for o in _raw_cors_origins.split(",") if o.strip()]

# Allow cookies / Authorization header to be sent cross-origin
CORS_ALLOW_CREDENTIALS = True

# CSRF trusted origins — must match CORS_ALLOWED_ORIGINS for cookie auth
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS.copy()

# Expose Authorization header to JS for token-refresh flows
CORS_EXPOSE_HEADERS = ["Authorization"]

# Preflight cache: 10 minutes
CORS_PREFLIGHT_MAX_AGE = 600


# ======================================================
# SENTRY — Error Tracking & Performance Monitoring
# ======================================================

SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN and not DEBUG:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.redis import RedisIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[
                DjangoIntegration(transaction_style="url"),
                CeleryIntegration(),
                RedisIntegration(),
            ],
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            send_default_pii=False,
            environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
            release=os.getenv("GIT_SHA", "unknown"),
        )
    except ImportError:
        logging.getLogger("zygotrip").warning(
            "SENTRY_DSN is set but sentry-sdk is not installed. pip install sentry-sdk"
        )
