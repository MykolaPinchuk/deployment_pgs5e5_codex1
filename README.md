# Local Deployment — Streamed Model Serving (Iteration A)

This repo deploys the DS handout model (in `handout_from DS_agent/`) as a local FastAPI service with streamed requests, delayed feedback, and basic Prometheus metrics. The handout directory is not modified.

## Prerequisites
- Python 3.10+
- (Optional) `make`

## Setup
1) Create a virtualenv and install dependencies:

```
make install
```

2) Train the model to produce `model.joblib` and `metrics.json` in the handout directory:

```
make train
```

## Run the Service

Start the FastAPI service (uses half of your CPU threads by default):

```
make serve
```

Endpoints:
- `GET /healthz` — liveness/readiness
- `POST /predict` — single record per SCHEMA; returns `{id, Calories}`
- `POST /feedback` — delayed ground truth `{id, Calories, ts?}`
- `GET /metrics` — Prometheus text metrics (infra + DS rolling metrics)

Environment variables (optional):
- `HANDOUT_DIR` — path to handout directory (default: `./handout_from DS_agent`)
- `MODEL_PATH` — path to `model.joblib` (default: `HANDOUT_DIR/model.joblib`)
- `PREDICTION_WINDOW_SECONDS` — rolling metrics window (default: 300)
- `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `XGBOOST_NUM_THREADS` — set to cap threads

## Stream Simulation

The simulator streams records from `handout_from DS_agent/data_sample/train.csv`, sends predictions to `/predict`, and then sends ground-truth feedback to `/feedback` after a delay. Bursty cycles are supported.

Run a short demo simulation (10s feedback delay for quick validation):

```
make simulate-stream
```

Or run manually with custom parameters:

```
.venv/bin/python tools/sim_stream.py \
  --url http://127.0.0.1:8000 \
  --data "handout_from DS_agent/data_sample/train.csv" \
  --limit 300 \
  --feedback-delay 300 \
  --cycles 3 \
  --burst-rps 20 \
  --burst-duration 5 \
  --idle-duration 25
```

## What to Expect
- `/metrics` includes:
  - Infra: request count, latency histogram, error rate.
  - DS: predicted value histogram/mean, feedback lag histogram, rolling 5‑min RMSLE/MAE, coverage.
- During simulation, predictions appear immediately; feedback arrives after the configured delay and DS metrics update accordingly.

## Troubleshooting
- `Model artifact not found`: run `make train` first to create `model.joblib`.
- Import/serialization errors: ensure the handout dir exists and is readable; the service adds it to `sys.path` so the artifact can deserialize.
- High CPU usage: thread caps are set to half your CPU threads by default; tune env vars if needed.

## Next Iterations
- Iteration B will add packaging, unit tests, Docker, and Compose with `/metrics` exposed.
- Iteration C will add Prometheus, Grafana, and MLflow in Compose.
- Iteration D will deploy to Minikube.
- Iteration E will run a massive burst stress test and validate autoscaling.

## Validate Iteration A (in-process, no network needed)

Use the in‑process validator to confirm the service startup, a single predict + feedback, and metrics aggregation with a strict 60s timeout.

Checklist:
- 1) Install deps: `make install`
- 2) Train model: `make train` (creates `handout_from DS_agent/model.joblib`)
- 3) Run validator: `make validate-a`
  - Expected log snippets (tail of `logs/validate_iteration_a.log`):
    - `Startup: model loaded OK`
    - `healthz: {'status': 'ok'}`
    - `predict: {'id': <int>, 'Calories': <float>}`
    - Metrics sample contains `app_rolling_rmsle_5m`, `app_rolling_mae_5m`, `app_feedback_coverage_5m`

Optional (if your environment allows localhost HTTP):
- Start service: `make serve` (runs on `127.0.0.1:8000`)
- Run stream sim with short feedback delay: `make simulate-stream`
- Inspect metrics at: `http://127.0.0.1:8000/metrics`

Notes:
- The validator avoids HTTP and runs the FastAPI handlers directly; it logs every step and enforces a hard timeout.
- If you set `ALLOW_STARTUP_FAILURE=0` in the environment, service startup will fail fast if the model is missing/invalid.

## Quick Commands
- Install: `make install`
- Train: `make train`
- Validate (no network): `make validate-a`
- Serve (optional): `make serve`
- Stream simulate (optional): `make simulate-stream`
