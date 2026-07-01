# syntax=docker/dockerfile:1.6
# -----------------------------------------------------------------------------
# BreatheSafe - Cloud Run container
# Single image serves the FastAPI backend + the static frontend SPA.
# Port 8080 (Cloud Run default; also what uvicorn binds to via $PORT).
# -----------------------------------------------------------------------------

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080

WORKDIR /app

# System deps (kept minimal; build-base is for any wheel that needs compiling)
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the project. Layout must match what the app expects:
#   /app/backend/...
#   /app/frontend/...
#   /app/backend/data/processed/...
COPY backend/   ./backend/
COPY frontend/  ./frontend/

# Cloud Run sends $PORT; uvicorn reads it. Single worker is fine for a
# 0-1 instance demo. Timeout 0 = request-based, not CPU-based.
EXPOSE 8080

# Healthcheck is provided by /health on the app itself; Cloud Run
# will use it as the startup + liveness probe.
CMD ["uvicorn", "backend.api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--proxy-headers", \
     "--forwarded-allow-ips=*", \
     "--log-level", "info"]
