#!/bin/bash
set -euo pipefail

# ── Wait for PostgreSQL ──────────────────────────────────────────────
echo "[entrypoint] Waiting for PostgreSQL..."
until python -c "
import psycopg2, os, sys
try:
    psycopg2.connect(
        dbname=os.environ['POSTGRES_DB'],
        user=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PASSWORD'],
        host=os.environ.get('POSTGRES_HOST', 'postgres'),
        port=os.environ.get('POSTGRES_PORT', '5432'),
        connect_timeout=3
    ).close()
    sys.exit(0)
except Exception as e:
    print(f'  PostgreSQL not ready: {e}')
    sys.exit(1)
" 2>/dev/null; do
    sleep 2
done
echo "[entrypoint] PostgreSQL is ready."

# ── Wait for Redis ───────────────────────────────────────────────────
echo "[entrypoint] Waiting for Redis..."
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"
until python -c "
import socket, os, sys
try:
    s = socket.create_connection(('${REDIS_HOST}', int('${REDIS_PORT}')), timeout=3)
    s.close()
    sys.exit(0)
except Exception as e:
    print(f'  Redis not ready: {e}')
    sys.exit(1)
" 2>/dev/null; do
    sleep 2
done
echo "[entrypoint] Redis is ready."

# ── Run database migrations ──────────────────────────────────────────
echo "[entrypoint] Running database migrations..."
python manage.py migrate --noinput

# ── Collect static files (idempotent) ───────────────────────────────
echo "[entrypoint] Collecting static files..."
python manage.py collectstatic --noinput --clear

# ── Create default superuser if not exists ───────────────────────────
if [ -n "${DJANGO_SUPERUSER_EMAIL:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    echo "[entrypoint] Ensuring superuser exists..."
    python manage.py shell -c "
from apps.accounts.models import User
if not User.objects.filter(email='${DJANGO_SUPERUSER_EMAIL}').exists():
    User.objects.create_superuser(
        email='${DJANGO_SUPERUSER_EMAIL}',
        password='${DJANGO_SUPERUSER_PASSWORD}',
        full_name='Admin'
    )
    print('  Superuser created.')
else:
    print('  Superuser already exists.')
"
fi

echo "[entrypoint] Starting application..."
exec "$@"
