# ── Stage 1: Builder ─────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Runtime ─────────────────────────────────────────────────
FROM python:3.11-slim

# Metadata
LABEL maintainer="zygotrip-ops" \
      description="ZygoTrip OTA Platform" \
      version="1.0"

# Runtime-only system deps (no gcc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Non-root user for security
RUN groupadd -r zygo && useradd -r -g zygo -d /app -s /sbin/nologin zygo

WORKDIR /app

# Copy application code
COPY --chown=zygo:zygo . .

# Create writable directories
RUN mkdir -p logs media staticfiles && chown -R zygo:zygo logs media staticfiles

# Switch to non-root
USER zygo

# Expose port
EXPOSE 8000

# Health check — hit the liveness endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/ || exit 1

# Production entrypoint (gunicorn via config file)
CMD ["gunicorn", "zygotrip_project.wsgi:application", "--config", "deployment/gunicorn.conf.py"]
