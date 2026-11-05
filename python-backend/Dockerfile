# ── Python Backend — ffinn API ───────────────────────────────────────────────
FROM python:3.12-slim

# Build tools needed by some native wheels (e.g. asyncpg on non-standard arches)
# `curl` is included for the HEALTHCHECK probe.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first so Docker caches this layer independently
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create an unprivileged user and hand over /app + the uploads volume so the
# server never runs as root (defence-in-depth against container escape bugs).
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin app \
    && mkdir -p /app/uploads \
    && chown -R app:app /app

USER app

# Port that uvicorn will listen on
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/monitoring/health || exit 1

# Run Alembic migrations then start the ASGI server.
# 'exec' replaces the shell so uvicorn gets PID 1 and handles signals correctly.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
