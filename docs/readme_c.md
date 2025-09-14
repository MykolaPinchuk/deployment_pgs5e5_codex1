## Iteration C — Observability + Registry (Prometheus, Grafana, MLflow)

This iteration adds a local observability stack and MLflow tracking/registry using Docker Compose.

What’s included
- Prometheus scraping API metrics at `/metrics` (job: `api`)
- Grafana with a pre-provisioned Prometheus datasource
- MLflow server (SQLite backend, local artifact store `./mlruns`)
- API `/info` endpoint with model and environment metadata
- `tools/train_mlflow.py` wrapper to log params/metrics/artifacts to MLflow without changing handout code

Prerequisites
- Docker + Docker Compose
- Model artifact exists (run `make train` or `make train-wo-holdout`)

1) Start API + Observability
```
make docker-build
make compose-up-observe    # rebuilds and recreates services (includes MLflow artifact serving)
```
Services and ports:
- API: http://127.0.0.1:8000
- Prometheus: http://127.0.0.1:9090 (targets should include `api:8000`)
- Grafana: http://127.0.0.1:3000 (login `admin` / `admin`)
- MLflow: http://127.0.0.1:5000

Port 8000 already in use?
```
HOST_PORT=8010 make compose-up-observe
curl -sS http://127.0.0.1:8010/healthz
```

2) Validate API and Metrics
- Health: `curl -sS http://127.0.0.1:8000/healthz`
- Info: `curl -sS http://127.0.0.1:8000/info`
- Prometheus: open `Status -> Targets`; the `api` scrape is UP
- Optional: In Grafana, add panels for `app_requests_total`, `app_request_latency_seconds_bucket`, `app_pred_calories_bucket`, `app_feedback_lag_seconds_bucket`, `app_rolling_rmsle_5m`, etc.

3) Generate Traffic (so you see data)
- The metrics populate when the API receives requests. Send traffic to the containerized API:
```
# If you used HOST_PORT=8010, substitute that port in the URL
URL=http://127.0.0.1:8000 make simulate-stream
```
- Or send a few manual requests:
```
for i in $(seq 1 20); do \
  curl -sS -X POST http://127.0.0.1:8000/predict -H 'Content-Type: application/json' \
    -d '{"id":'"$i"',"Gender":"male","Age":25,"Height":180,"Weight":75,"Duration":30,"Heart_Rate":120,"Body_Temp":37.0}' >/dev/null; \
done
```
- After traffic, in Prometheus try queries like:
  - `sum by (route) (rate(app_requests_total[1m]))`
  - `histogram_quantile(0.95, sum by (le) (rate(app_request_latency_seconds_bucket[1m])))`
  - `app_rolling_rmsle_5m`

4) Log a Training Run to MLflow
Option A (server mode; requires compose-up-observe running):
```
export MLFLOW_TRACKING_URI=http://127.0.0.1:5000
make train-mlflow
```
Then open MLflow UI and check the run: parameters (from config.yaml), metrics (from metrics.json), and artifacts (model.joblib, config.yaml, metrics.json).
If you previously saw a PermissionError for `/mlruns`, re-run after updating the stack — the MLflow server now serves artifacts over HTTP, so the client no longer tries to write to `/mlruns` locally.

Option B (file store, no server):
```
export MLFLOW_TRACKING_URI=file:./mlruns
make train-mlflow
```

5) Tear Down
```
make compose-down
```

Notes
- The wrapper calls the handout `train.py` as a subprocess to respect the “don’t edit handout” constraint.
- The API `/info` endpoint includes `MLFLOW_TRACKING_URI` when set.
