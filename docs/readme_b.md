## Iteration B — Tests and Docker/Compose Validation (Self‑Contained)

This guide explains exactly how to validate Iteration B. Iteration B adds:
- A minimal test that validates service startup, `/predict`, `/feedback`, and `/metrics` in‑process (no network).
- A containerized API (Dockerfile + docker‑compose) with resource caps and health checks.

The DS handout is in `handout_from DS_agent/` and is not modified.

### Prerequisites
- Python 3.10+
- Docker + Docker Compose
- Optional: `make`

### 0) Install dependencies
```
make install
```

### 1) Ensure a model artifact exists
You need `handout_from DS_agent/model.joblib` for both tests and the image.

- Quick path:
```
make train
```
- No‑leakage path for streaming later (optional):
```
make holdout
make train-wo-holdout
```

### 2) Run tests (in‑process, no network)
Validates that the service can load the model, score one record, accept feedback, and expose DS metrics.
```
make test
```
Expected:
- 1 test passes: `tests/test_service_direct.py`.
- Warnings about joblib running in serial mode are OK in local sandboxes.

### 3) Build and run the container (Docker/Compose)
Build the image and start the API with resource caps:
```
make docker-build
make compose-up   # or: docker compose up -d
```

Validate the container by calling the API:
```
# Health
curl -sS http://127.0.0.1:8000/healthz

# Example /predict payload (id is client-provided and echoed back)
curl -sS -X POST http://127.0.0.1:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{
    "id": 123,
    "Gender": "male",
    "Age": 25,
    "Height": 180,
    "Weight": 75,
    "Duration": 30,
    "Heart_Rate": 120,
    "Body_Temp": 37.0
  }'

# Metrics (Prometheus text format)
curl -sS http://127.0.0.1:8000/metrics | head -n 40
```

Stop the stack when done:
```
make compose-down   # or: docker compose down -v --remove-orphans
```

Port already in use?
- If `make compose-up` fails with an error like `address already in use` on port 8000, either stop the process using port 8000 or run Compose on a different host port. Example:
```
HOST_PORT=8010 make compose-up
curl -sS http://127.0.0.1:8010/healthz
```

### What’s included in Iteration B
- Tests: `tests/test_service_direct.py`
- API: `service/app.py` (FastAPI) with endpoints: `/healthz`, `/predict`, `/feedback`, `/metrics`.
- Dockerfile: `docker/Dockerfile`
- Compose: `docker-compose.yml`
- Makefile shortcuts: `make test`, `make docker-build`, `make compose-up`, `make compose-down`

### Notes and Troubleshooting
- Resource caps:
  - Compose CPU/thread caps can be tuned with env vars: `API_CPUS`, `OMP_THREADS`.
  - The service also caps XGBoost/BLAS threads to ~half your host threads by default when run via `make serve`.
- Model updates:
  - The image bundles the current `handout_from DS_agent/model.joblib` at build time. If you retrain, rebuild the image to pick up the new model.
- Localhost/ports:
  - If port `8000` is busy, change the published port in `docker-compose.yml` or stop the conflicting process.
- Network restrictions:
  - If your environment blocks localhost HTTP, the in‑process tests (`make test`) still validate the core service logic without the network.
