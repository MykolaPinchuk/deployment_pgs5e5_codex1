# syntax=docker/dockerfile:1.7
FROM python:3.10-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install build essentials for scientific stack if needed (kept minimal here)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

# Copy service code and handout (space in path handled by JSON-array COPY)
COPY service /app/service
COPY ["handout_from DS_agent", "/app/handout_from DS_agent"]

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

ENV HANDOUT_DIR=/app/handout_from\ DS_agent \
    MODEL_PATH=/app/handout_from\ DS_agent/model.joblib \
    OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 XGBOOST_NUM_THREADS=2 \
    UVICORN_HOST=0.0.0.0 UVICORN_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s CMD \
    python - << 'PY' || exit 1
import os, sys, json
import requests
url=f"http://{os.environ.get('UVICORN_HOST','127.0.0.1')}:{os.environ.get('UVICORN_PORT','8000')}/healthz"
try:
    r=requests.get(url, timeout=2)
    j=r.json(); assert j.get('status')=='ok'
except Exception as e:
    print('healthcheck failed', e)
    raise
PY

CMD ["python", "-m", "uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8000"]

