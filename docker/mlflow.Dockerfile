FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN pip install --no-cache-dir mlflow==2.14.1

ENV BACKEND_STORE_URI=sqlite:///mlflow.db \
    ARTIFACT_ROOT=/mlruns \
    MLFLOW_HOST=0.0.0.0 \
    MLFLOW_PORT=5000

EXPOSE 5000

CMD ["sh", "-c", "mlflow server --host $MLFLOW_HOST --port $MLFLOW_PORT --backend-store-uri $BACKEND_STORE_URI --serve-artifacts --artifacts-destination $ARTIFACT_ROOT"]
