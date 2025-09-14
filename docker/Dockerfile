# syntax=docker/dockerfile:1.7
FROM python:3.10-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Keep image minimal; rely on wheels (no build tools needed)

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

# Lightweight healthcheck using stdlib only (no extra deps)
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s CMD \
    python -c "import os,urllib.request,json;\
u=f'http://{os.environ.get('UVICORN_HOST','127.0.0.1')}:{os.environ.get('UVICORN_PORT','8000')}/healthz';\
d=urllib.request.urlopen(u,timeout=2).read();\
assert json.loads(d).get('status')=='ok'" || exit 1

CMD ["python", "-m", "uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8000"]
