## Iteration D — Kubernetes (Minikube) Deployment

This iteration deploys the API to a local Kubernetes cluster (Minikube) with readiness/liveness probes, resource requests/limits, and optional CPU autoscaling (HPA). Observability (Prometheus, Grafana, MLflow) can continue to run via Compose, or you can install them in-cluster separately.

What’s included
- Namespace: `calories` (k8s/namespace.yaml)
- ConfigMap for env/thread caps (k8s/configmap.yaml)
- Deployment + Service for API (k8s/deployment.yaml, k8s/service.yaml)
- HPA on CPU utilization (k8s/hpa.yaml) — requires metrics-server

Prerequisites
- Minikube + kubectl installed
- metrics-server addon enabled for HPA: `minikube addons enable metrics-server`

Start Clean (recommended)
If you have services from earlier iterations running, free ports and stop background tasks to avoid conflicts.

1) Stop background port-forward (if previously started)
```
make k8s-port-forward-stop
```

2) Stop Docker Compose stacks (API and observability)
```
make compose-down
make compose-down-observe
```

3) Stop local FastAPI service (if started via make serve)
```
pkill -f "uvicorn service.app:app" || true
```

4) Free host ports if needed (replace 8000 with your chosen port)
```
# View processes on port 8000
lsof -i :8000 || true
# Kill processes by PID (use with care)
kill -9 <PID>
```

5) Reset or restart Minikube if the API server is unreachable
```
make k8s-status
make k8s-up          # starts cluster if stopped
# If problems persist:
minikube stop && minikube start --driver=docker
# As a last resort (removes the cluster):
# minikube delete && minikube start --driver=docker
```

0) Ensure Minikube is running and kubectl context is set
```
make k8s-status
make k8s-up        # starts cluster if stopped (no CPU/mem change on existing cluster)
make k8s-context   # sets kubectl to use minikube context
```

1) Build and load image into Minikube
```
make k8s-build-img
```

2) Apply manifests
```
make k8s-apply
kubectl -n calories get pods
```

3) Port-forward to access the API
Port-forward runs continuously; keep it open in a separate terminal, or run it in the background. If port 8000 is busy on the host, choose a different port using HOST_PORT.

Option A — foreground (blocks):
```
make k8s-port-forward        # forwards localhost:8000 -> service 8000 until Ctrl+C
```

Option B — background (easier):
```
HOST_PORT=8010 make k8s-port-forward-bg     # example mapping host 8010 -> service 8000
# when done:
make k8s-port-forward-stop
```

4) Validate
- Important: curl the forwarded host port (8000 by default, or whatever you set via HOST_PORT).

Default (host port 8000):
```
curl -sS http://127.0.0.1:8000/healthz
curl -sS -X POST http://127.0.0.1:8000/predict -H 'Content-Type: application/json' -d '{"id":1,"Gender":"male","Age":25,"Height":180,"Weight":75,"Duration":30,"Heart_Rate":120,"Body_Temp":37.0}'
```

If you used a custom port (e.g., HOST_PORT=8010):
```
curl -sS http://127.0.0.1:8010/healthz
curl -sS -X POST http://127.0.0.1:8010/predict -H 'Content-Type: application/json' -d '{"id":1,"Gender":"male","Age":25,"Height":180,"Weight":75,"Duration":30,"Heart_Rate":120,"Body_Temp":37.0}'
```

Tip: to confirm the tunnel is active, tail the log: `tail -n 20 logs/log_kpf.txt`

5) Optional — Autoscaling
- Ensure metrics-server is enabled in Minikube: `minikube addons enable metrics-server`
- The provided HPA (k8s/hpa.yaml) targets 70% CPU utilization (based on resource requests/limits). To view:
```
kubectl -n calories get hpa
```

6) Optional — Observability
- For simplicity, keep using the Compose-based Prometheus/Grafana/MLflow stack from Iteration C while the API runs in K8s. Point traffic to the K8s port-forward so metrics populate.
- If you prefer in-cluster observability, install `kube-prometheus-stack` via Helm and configure a scrape for the `api` service (not included here).

7) Cleanup
```
make k8s-delete
```

Notes
- The Deployment sets resource requests/limits and caps thread env vars via ConfigMap to use ~half CPU by default. Adjust in k8s/configmap.yaml and k8s/deployment.yaml.
- The image reference `calories-api:local` is loaded into Minikube via `minikube image load`.
