# Deployment Plan — PS S5E5 Calorie Prediction (Local Only)

This plan defines an iterative, production‑like local deployment for the DS handout in `handout_from DS_agent/`. We will not modify anything inside that directory; all service, tooling, infra, and docs live outside it.

## Goals and Constraints
- Do not touch `handout_from DS_agent/` code or files.
- Start simple; validate end‑to‑end serving quickly, then add observability and infra.
- Stream‑only simulation drawn from training data, with delayed ground truth (5 minutes) for near‑real‑time DS metrics.
- Cap infra to ~50% of home PC CPU threads via service/thread/env limits and container/K8s resource limits.
- Local only: Docker/Compose first, then Minikube for a prod‑like environment.

## Iteration A (Merged 1+2): Service + Stream Simulation
Deliverables
- `service/app.py` (FastAPI):
  - `GET /healthz` — liveness/readiness.
  - `POST /predict` — accepts a single record (JSON) per SCHEMA; returns `{id, Calories}`.
  - `POST /feedback` — accepts ground truth for a prior prediction: `{id, Calories, ts?}`.
- Basic Prometheus metrics exposed at `/metrics` (Prometheus text format; infra + DS metrics).
- `tools/sim_stream.py` — stream simulator:
  - Reads records from `handout_from DS_agent/data_sample/train.csv`.
  - Sends one record at a time to `/predict` (stream mode only).
  - Schedules feedback calls to `/feedback` after a configurable delay (default 5 minutes).
  - Supports bursty cycles: e.g., 20 rps for 5s, idle 25s, repeat.
- `requirements.txt` and `Makefile` targets:
  - `make serve` (run FastAPI with uvicorn), `make simulate-stream`, `make train`, `make predict`.

Metrics (exported via `/metrics`)
- Infra: request count by route, latency histogram, error rate.
- DS:
  - Predicted calories histogram and rolling mean.
  - Feedback lag histogram.
  - Rolling 5‑min RMSLE and MAE (computed only for predictions that have received feedback).
  - Coverage ratio over 5‑min window: matched feedback / predictions.

Resource Policy
- Limit to half CPU threads via env (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `XGBOOST_NUM_THREADS`).
- Configure uvicorn workers/threads accordingly.

Validation
- `/healthz` returns 200; `/predict` returns a scalar per record.
- Stream simulator runs, produces predictions, then feedback arrives 5 minutes later; DS metrics update.

## Iteration B (Merged 3+4): Packaging + Docker + Compose
Deliverables
- Packaging to import DS handout cleanly without modifying it (sys.path bootstrap or thin wrapper module).
- Unit tests: schema validation, `/predict` and `/feedback` flows, DS metrics computation.
- Containerization: `docker/Dockerfile` (python‑slim, non‑root, healthcheck) and `docker-compose.yml`:
  - CPU caps ≈ half cores; env sets thread limits.
  - Structured JSON logs to stdout.
  - `/metrics` exposed for scraping later.

Validation
- `docker compose up` serves API; `simulate-stream` against container works; metrics endpoint responds.

## Iteration C (5): Observability + Registry
Deliverables
- Prometheus + Grafana in Compose:
  - Prometheus scrapes API `/metrics`.
  - Grafana dashboard panels:
    - Infra: req rate, p95/p99 latency, error rate.
    - DS: predicted value histogram, rolling mean, coverage, 5‑min RMSLE/MAE, feedback lag.
- MLflow server (file store + artifact dir) in Compose.
- Instrument `handout_from DS_agent/train.py` runs via MLflow: log params, metrics, artifacts; register model.
- API `/info` returns model version/build metadata (e.g., git SHA, model timestamp, MLflow run).

Validation
- Grafana reachable; Prometheus shows scrape OK; dashboard populated during simulation.
- MLflow UI shows runs; model artifact and metrics present.

## Iteration D (6): Minikube (Prod‑like)
Deliverables
- Kubernetes manifests (or Helm/Kustomize):
  - API Deployment/Service with readiness/liveness probes; resource requests/limits ≈ half CPU.
  - ConfigMap/Secret for env.
  - HPA on CPU (optional custom metrics later).
  - Prometheus/Grafana stack and MLflow in cluster; Ingress or port‑forward instructions.
- Build image locally and load into Minikube (`minikube image load`).

Validation
- Pods healthy; `/healthz` ready; metrics scraped; Grafana dashboards live.
- Simulation against cluster service; DS metrics update with delayed feedback.

## Iteration E (New): Massive Burst + Autoscaling
Deliverables
- Extend `tools/sim_stream.py` to high‑concurrency (asyncio) stress mode.
- Target high QPS bursts (e.g., 200–500 rps locally), observe:
  - Error rate, p95/p99 latency, saturation indicators.
  - HPA scale out/in and stability.

Success Criteria
- Error rate low; latency within budget; autoscaling reacts appropriately and stabilizes.

## Simulation (Stream‑Only) Details
- Source: `handout_from DS_agent/data_sample/train.csv` (id + features + target).
- Predict flow: send a single record to `/predict`, capture `{id, ts_pred, y_hat}`.
- Feedback flow: after 5 minutes (configurable for dev), send `{id, Calories, ts_true}` to `/feedback`.
- Correlation: by `id` (simulator preserves mapping); service updates rolling DS metrics when feedback is received.
- Rolling windows: maintain 5‑minute TTL buffers in memory and recompute aggregate metrics periodically.

## Directory Layout (New Assets Only)
- `plan.md` — this document.
- `service/` — FastAPI app, config, minimal package bootstrap.
- `tools/` — simulators, helper scripts (no handout changes).
- `docker/`, `docker-compose.yml` — containerization and local stack.
- `k8s/` — manifests or Helm/Kustomize for Minikube.
- `requirements.txt`, `Makefile` — developer ergonomics.

## Make Targets (Initial Set)
- `make serve` — run FastAPI locally with capped threads.
- `make simulate-stream` — run stream simulator with burst options and feedback delay.
- `make train` — run handout training.
- `make predict` — run handout batch predict (optional helper).
- Later:
  - `make docker-build`, `make compose-up`, `make compose-down`.
  - `make k8s-apply`, `make k8s-destroy`, `make stress-test`.

## Validation Summary per Iteration
- A: Local service up; stream + feedback loop functioning; infra + DS metrics exposed.
- B: Container runs with resource caps; tests pass; metrics endpoint healthy.
- C: Prom/Grafana dashboards show live infra and DS metrics; MLflow tracks training and model registry; `/info` exposes model metadata.
- D: Minikube deployment healthy; HPA optional; simulation drives dashboards.
- E: Stress scenarios validate latency/error budgets and autoscaling behavior.

