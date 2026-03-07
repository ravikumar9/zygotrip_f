"""
Gunicorn configuration for ZygoTrip OTA Platform.

Tuned for a 2-4 vCPU production server behind nginx reverse proxy.
Override via environment variables:
    GUNICORN_WORKERS, GUNICORN_THREADS, GUNICORN_BIND, WEB_CONCURRENCY
"""

import multiprocessing
import os

# ── Bind ─────────────────────────────────────────────────────────────
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")

# ── Workers ──────────────────────────────────────────────────────────
# Formula: 2 * CPU + 1  (safe default for I/O-heavy OTA workloads)
workers = int(os.getenv("WEB_CONCURRENCY", os.getenv(
    "GUNICORN_WORKERS", str(multiprocessing.cpu_count() * 2 + 1)
)))
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", "4"))

# ── Timeouts ─────────────────────────────────────────────────────────
timeout = 30            # Kill worker if request takes >30s
graceful_timeout = 10   # Time to finish in-flight requests on restart
keepalive = 5           # Keepalive seconds (nginx upstream)

# ── Limits ───────────────────────────────────────────────────────────
max_requests = 1000           # Recycle workers to prevent memory leaks
max_requests_jitter = 100     # Stagger recycling to avoid thundering herd

# ── Logging ──────────────────────────────────────────────────────────
accesslog = "-"              # stdout (collected by Docker/container runtime)
errorlog = "-"               # stderr
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sμs'

# ── Security ─────────────────────────────────────────────────────────
# Forward proxy headers (trusted nginx)
forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "*")
proxy_protocol = False

# ── Preload ──────────────────────────────────────────────────────────
preload_app = True  # Load app before forking — saves memory via CoW

# ── Server hooks ─────────────────────────────────────────────────────
def on_starting(server):
    server.log.info("ZygoTrip gunicorn starting (workers=%s, threads=%s)", workers, threads)

def worker_int(worker):
    worker.log.info("Worker received INT or QUIT signal")

def worker_abort(worker):
    worker.log.warning("Worker received SIGABRT (timeout?)")
