# Iteration A — Service + Stream Simulation (Self‑Contained)

This document explains how to validate Iteration A of the local deployment. Iteration A provides a FastAPI service with `/predict`, delayed `/feedback`, and Prometheus metrics, plus a stream simulator. The DS handout is in `handout_from DS_agent/` and is NOT modified.

## Prerequisites
- Python 3.10+
- Optional: `make`

## Setup
1) Install dependencies:
```
make install
```
2) Train the model to produce `model.joblib` and `metrics.json` in the handout directory:
```
make train
```

## Validation Checklist (Pick A or B)

Option A — In‑process (no network, fastest):
- `make validate-a`
- Inspect tail of `logs/validate_iteration_a.log` and confirm:
  - "Startup: model loaded OK"
  - healthz status ok
  - predict returns an id and a float Calories
  - metrics sample shows app_rolling_rmsle_5m, app_rolling_mae_5m, app_feedback_coverage_5m

Option B — HTTP service + streaming (holdout, no leakage):
- `make holdout`
- `make train-wo-holdout`
- `make serve` (keep it running)
- In a second terminal: `make simulate-stream`
- Verify:
  - `curl -sS http://127.0.0.1:8000/healthz` returns `{"status":"ok"}`
  - `/metrics` shows infra and DS metrics while simulation runs

## /predict Example
```
curl -sS -X POST http://127.0.0.1:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"id":123,"Gender":"male","Age":25,"Height":180,"Weight":75,"Duration":30,"Heart_Rate":120,"Body_Temp":37.0}'
```

## Troubleshooting
- `Model artifact not found`: run `make train` first to create `model.joblib`.
- Import/serialization errors: ensure the handout dir exists and is readable; the service adds it to `sys.path` so the artifact can deserialize.
- High CPU usage: thread caps are set to half your CPU threads by default; tune env vars if needed.
- Connection errors during `make simulate-stream`: ensure `make serve` is running, confirm the URL/port, and check firewall. If HTTP is blocked, use `make validate-a` instead.
- Using holdout properly: always run `make holdout` first and use `make train-wo-holdout` to avoid training on rows used for streaming simulation.

