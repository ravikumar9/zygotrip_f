"""
Production readiness check — validates environment, settings, and infrastructure
before deploying to production.

Usage:
    python manage.py check_production_readiness
    python manage.py check_production_readiness --strict  (exit 1 on warnings)
"""
import os
import socket

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Validate production readiness: environment variables, security settings, database, Redis.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--strict',
            action='store_true',
            help='Treat warnings as errors (exit 1)',
        )

    def handle(self, *args, **options):
        errors = []
        warnings = []
        passed = []

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('  PRODUCTION READINESS CHECK')
        self.stdout.write('=' * 60 + '\n')

        # ── 1. SECRET_KEY ──────────────────────────────────────────
        if settings.SECRET_KEY == 'unsafe-dev-key':
            errors.append('DJANGO_SECRET_KEY is not set (using unsafe-dev-key)')
        else:
            passed.append('SECRET_KEY is configured')

        # ── 2. DEBUG ───────────────────────────────────────────────
        if settings.DEBUG:
            warnings.append('DEBUG is True — must be False in production')
        else:
            passed.append('DEBUG is False')

        # ── 3. ALLOWED_HOSTS ──────────────────────────────────────
        hosts = settings.ALLOWED_HOSTS
        if not hosts or hosts == ['127.0.0.1', 'localhost', 'testserver']:
            warnings.append('ALLOWED_HOSTS is default (localhost only)')
        else:
            passed.append(f'ALLOWED_HOSTS = {hosts}')

        # ── 4. Database connectivity ──────────────────────────────
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            passed.append('PostgreSQL connection OK')
        except Exception as exc:
            errors.append(f'Database connection failed: {exc}')

        # ── 5. Redis connectivity ─────────────────────────────────
        redis_host = getattr(settings, 'REDIS_HOST', 'redis')
        redis_port = int(getattr(settings, 'REDIS_PORT', 6379))
        try:
            sock = socket.create_connection((redis_host, redis_port), timeout=2)
            sock.close()
            passed.append(f'Redis reachable at {redis_host}:{redis_port}')
        except OSError:
            warnings.append(f'Redis unreachable at {redis_host}:{redis_port} — caching will fall back to LocMemCache')

        # ── 6. Security headers ───────────────────────────────────
        for setting_name, expected, label in [
            ('SECURE_SSL_REDIRECT', True, 'SSL redirect'),
            ('SECURE_HSTS_SECONDS', lambda v: v >= 31536000, 'HSTS >= 1 year'),
            ('SESSION_COOKIE_SECURE', True, 'Secure session cookies'),
            ('CSRF_COOKIE_SECURE', True, 'Secure CSRF cookies'),
            ('SECURE_CONTENT_TYPE_NOSNIFF', True, 'X-Content-Type-Options nosniff'),
            ('X_FRAME_OPTIONS', 'DENY', 'X-Frame-Options DENY'),
        ]:
            value = getattr(settings, setting_name, None)
            ok = expected(value) if callable(expected) else value == expected
            if ok:
                passed.append(f'{label}: {value}')
            else:
                msg = f'{label}: {setting_name}={value!r} (expected={expected!r} when DEBUG=False)'
                if settings.DEBUG:
                    warnings.append(msg + ' [OK in DEBUG mode]')
                else:
                    errors.append(msg)

        # ── 7. CORS ───────────────────────────────────────────────
        origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])
        if not origins:
            warnings.append('CORS_ALLOWED_ORIGINS is empty')
        else:
            passed.append(f'CORS origins: {len(origins)} configured')

        # ── 8. Payment gateway credentials ────────────────────────
        payment_vars = [
            ('CASHFREE_APP_ID', settings.CASHFREE_APP_ID),
            ('STRIPE_SECRET_KEY', settings.STRIPE_SECRET_KEY),
        ]
        for name, value in payment_vars:
            if value:
                passed.append(f'{name} is configured')
            else:
                warnings.append(f'{name} is empty — gateway will be unavailable')

        # ── 9. SMS backend ────────────────────────────────────────
        sms_backend = getattr(settings, 'SMS_BACKEND', 'console')
        if sms_backend == 'console':
            warnings.append('SMS_BACKEND=console — OTP messages go to console only')
        else:
            passed.append(f'SMS_BACKEND={sms_backend}')

        # ── 10. Celery ────────────────────────────────────────────
        if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            warnings.append('CELERY_TASK_ALWAYS_EAGER is True — tasks run synchronously')
        else:
            passed.append('Celery is in async mode')

        # ── 11. OTP debug code ────────────────────────────────────
        if getattr(settings, 'OTP_DEBUG_CODE', None) and not settings.DEBUG:
            errors.append('OTP_DEBUG_CODE is set in a non-DEBUG environment — security risk')
        elif getattr(settings, 'OTP_DEBUG_CODE', None):
            warnings.append('OTP_DEBUG_CODE is set (acceptable in DEBUG mode)')
        else:
            passed.append('OTP_DEBUG_CODE is not set')

        # ── 12. Pending migrations ────────────────────────────────
        try:
            from django.core.management import call_command
            from io import StringIO
            out = StringIO()
            call_command('showmigrations', '--plan', stdout=out)
            plan_output = out.getvalue()
            unapplied = [line for line in plan_output.splitlines() if '[ ]' in line]
            if unapplied:
                errors.append(f'{len(unapplied)} unapplied migration(s): {"; ".join(u.strip() for u in unapplied[:5])}')
            else:
                passed.append('All migrations applied')
        except Exception as exc:
            warnings.append(f'Could not check migrations: {exc}')

        # ── Report ────────────────────────────────────────────────
        self.stdout.write('\n--- PASSED ---')
        for p in passed:
            self.stdout.write(self.style.SUCCESS(f'  [OK]  {p}'))

        if warnings:
            self.stdout.write('\n--- WARNINGS ---')
            for w in warnings:
                self.stdout.write(self.style.WARNING(f'  [!!]  {w}'))

        if errors:
            self.stdout.write('\n--- ERRORS ---')
            for e in errors:
                self.stdout.write(self.style.ERROR(f'  [XX]  {e}'))

        self.stdout.write('\n' + '=' * 60)
        total = len(passed) + len(warnings) + len(errors)
        self.stdout.write(f'  {len(passed)}/{total} passed  |  {len(warnings)} warnings  |  {len(errors)} errors')
        self.stdout.write('=' * 60 + '\n')

        if errors or (options['strict'] and warnings):
            self.stderr.write(self.style.ERROR('Production readiness check FAILED.\n'))
            raise SystemExit(1)

        if warnings:
            self.stdout.write(self.style.WARNING('Production readiness check PASSED WITH WARNINGS.\n'))
        else:
            self.stdout.write(self.style.SUCCESS('Production readiness check PASSED.\n'))
