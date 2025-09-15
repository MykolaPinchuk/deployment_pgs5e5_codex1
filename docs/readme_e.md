## Iteration E — Stress Test & Autoscaling Validation

This iteration validates the API under bursty, high-QPS load and observes latency/error characteristics and (optionally) K8s autoscaling.

What’s included
- Stress tool: `tools/stress_burst.py` (async HTTP load generator)
- Make targets:
  - `make stress-local` — hits `URL` (default `http://127.0.0.1:8000`)
  - `make stress-k8s` — requires `HOST_PORT` set to forwarded port
  - `make stress-asgi` — in-process load (no network), quick sanity

Prerequisites
- API running locally (Iteration A/B) or via K8s (Iteration D)
- For K8s/HPA tests: metrics-server enabled and HPA applied

1) Generate load (local / Compose)
```
# Default URL is http://127.0.0.1:8000; override with URL=...
make stress-local
```
Output includes issued/ok/err and latency p50/p95/p99.

2) Generate load (K8s via port-forward)
```
# Ensure port-forward is running (from Iteration D):
HOST_PORT=8010 make k8s-port-forward-bg

# Run stress against forwarded port
HOST_PORT=8010 make stress-k8s

# Stop port-forward when done
make k8s-port-forward-stop
```

3) Observe metrics
- Prometheus queries (Iteration C):
  - `sum by (route) (rate(app_requests_total[1m]))`
  - `histogram_quantile(0.95, sum by (le) (rate(app_request_latency_seconds_bucket[1m])))`
  - DS: `app_rolling_rmsle_5m`
- Grafana: create panels with the above metrics; watch during load.

4) Validate autoscaling (optional)
```
kubectl -n calories get hpa -w
kubectl -n calories get deploy/api -w
```
While `make stress-k8s` is running, watch HPA target utilization and replica count. With the provided `requests.cpu: 250m` and HPA target 70%, sustained CPU > ~175m should trigger scale out.

5) Troubleshooting
- Ensure the correct port is used:
  - Local: default 8000, or set `URL=http://127.0.0.1:<port>`
  - K8s: use `HOST_PORT` (the host side of the port-forward)
- If you receive connection errors, confirm the API is reachable and the tunnel is active (`tail -n 20 logs/log_kpf.txt`).
- Reduce RPS/concurrency if your machine becomes saturated.

