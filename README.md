# Local Deployment — Streamed Model Serving

This repo deploys the DS handout model (in `handout_from DS_agent/`) as a local FastAPI service with streamed requests, delayed feedback, and basic Prometheus metrics. The handout directory is not modified.

Docs moved into `docs/`:
- Iteration A: `docs/readme_a.md`
- Iteration B: `docs/readme_b.md`

Quick links:
- Validate A (no network): `make validate-a`
- Validate B tests: `make test`
- Docker build: `make docker-build`; bring up API: `make compose-up`
- Observability stack (Prom, Grafana, MLflow): `make compose-up-observe`

See detailed instructions in the per-iteration docs.

## Validation Checklist (Pick A or B)

Option A — In‑process (no network, fastest):
- make validate-a
- Inspect tail of logs/validate_iteration_a.log and confirm:
  - "Startup: model loaded OK"
  - healthz status ok
  - predict returns an id and a float Calories
  - metrics sample shows app_rolling_rmsle_5m, app_rolling_mae_5m, app_feedback_coverage_5m

Option B — HTTP service + streaming (holdout, no leakage):
- make holdout
- make train-wo-holdout
- make serve (keep it running)
- In a second terminal: make simulate-stream
- Verify:
  - curl -sS http://127.0.0.1:8000/healthz returns {"status":"ok"}
  - /metrics shows infra and DS metrics while simulation runs

Endpoints (service):
- `GET /healthz` — liveness/readiness
- `POST /predict` — single record per SCHEMA; returns `{id, Calories}`
- `POST /feedback` — delayed ground truth `{id, Calories, ts?}`
- `GET /metrics` — Prometheus text metrics (infra + DS rolling metrics)
- `GET /info` — service, model, and env metadata

## Stream Simulation (Holdout, no leakage)

The simulator streams records from a derived holdout set outside the handout directory (`data/holdout/holdout.csv`), sends predictions to `/predict`, and then sends ground-truth feedback to `/feedback` after a delay. Bursty cycles are supported.

First, generate the holdout files (default 500 rows for holdout, rest for training):

```
make holdout
```

Optional: train without holdout leakage by pointing training to the derived data folder:

```
make train-wo-holdout
```

Run a short demo simulation (10s feedback delay for quick validation):

```
make simulate-stream
```

Or run manually with custom parameters (point `--data` to your holdout file):

```
.venv/bin/python tools/sim_stream.py \
  --url http://127.0.0.1:8000 \
  --data "data/holdout/holdout.csv" \
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
 - Connection errors during `make simulate-stream`: ensure `make serve` is running in another terminal, confirm the URL/port (`--url`), and check for firewall restrictions. If HTTP is blocked in your environment, use `make validate-a` instead.
 - Using holdout properly: always run `make holdout` first and use `make train-wo-holdout` to avoid training on rows used for streaming simulation.
 - Port already in use: change `--port` in `make serve` or stop the other process.

## /predict Examples

Example curl request with a valid payload. The `id` is a client-provided identifier that will be echoed back and used to correlate later feedback.

```
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
```

Sample response:

```
{"id": 123, "Calories": 198.42}
```

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
 - Logs are written to logs/validate_iteration_a.log and to stdout.

## Quick Commands
- Install: `make install`
- Train: `make train`
- Validate (no network): `make validate-a`
- Serve: `make serve`
- Holdout (no leakage): `make holdout`
- Train without holdout: `make train-wo-holdout`
- Stream simulate: `make simulate-stream`

## Docker and Compose

Build the API image and run it with resource caps and metrics:

```
make docker-build
docker compose up -d
# or: make compose-up
```

Then call the API:

```
curl -sS http://127.0.0.1:8000/healthz
curl -sS -X POST http://127.0.0.1:8000/predict -H 'Content-Type: application/json' -d '{"id":1,"Gender":"male","Age":25,"Height":180,"Weight":75,"Duration":30,"Heart_Rate":120,"Body_Temp":37.0}'
```

Stop the stack:

```
docker compose down -v --remove-orphans
# or: make compose-down
```

Notes:
- CPU/thread caps are configurable via env: `API_CPUS`, `OMP_THREADS`.
- The image bundles the handout and model; retrain locally and rebuild to update.

Port already in use?
- If `docker compose up` fails with `address already in use` on port 8000, either stop whatever is on port 8000 (e.g., a local `make serve`) or run Compose on a different host port:

```
HOST_PORT=8010 docker compose up -d
curl -sS http://127.0.0.1:8010/healthz
```
