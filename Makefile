.PHONY: install train train-wo-holdout holdout predict serve simulate-stream validate-a docker-build compose-up compose-down compose-down-observe test train-mlflow compose-up-observe k8s-up k8s-status k8s-context k8s-build-img k8s-apply k8s-delete k8s-port-forward k8s-port-forward-bg k8s-port-forward-stop k8s-restart

PY := python3
PIP := pip3

VENV := .venv
VENVPY := $(VENV)/bin/python
VENVPIP := $(VENV)/bin/pip
URL ?= http://127.0.0.1:8000

install:
	python3 -m venv $(VENV)
	$(VENVPIP) install --upgrade pip
	$(VENVPIP) install -r requirements.txt

train:
	$(VENVPY) "handout_from DS_agent/train.py"

holdout:
	mkdir -p data/holdout
	$(VENVPY) tools/make_holdout.py --size 500

train-wo-holdout: holdout
	# Train using the derived train.csv without holdout rows
	$(VENVPY) "handout_from DS_agent/train.py" --data-dir "$(PWD)/data/holdout"

predict:
	$(VENVPY) "handout_from DS_agent/predict.py"

serve:
	HANDOUT_DIR="$(PWD)/handout_from DS_agent" \
	MODEL_PATH="$(PWD)/handout_from DS_agent/model.joblib" \
	OMP_NUM_THREADS=$$(python3 -c 'import os;print(max(1,(os.cpu_count() or 2)//2))') \
	MKL_NUM_THREADS=$$(python3 -c 'import os;print(max(1,(os.cpu_count() or 2)//2))') \
	XGBOOST_NUM_THREADS=$$(python3 -c 'import os;print(max(1,(os.cpu_count() or 2)//2))') \
	$(VENVPY) -m uvicorn service.app:app --host 0.0.0.0 --port 8000

simulate-stream: holdout
	$(VENVPY) tools/sim_stream.py --url $(URL) --feedback-delay 10 --cycles 2 --burst-rps 20 --burst-duration 5 --idle-duration 10 --limit 200

validate-a:
	PYTHONUNBUFFERED=1 timeout 60s $(VENVPY) tools/validate_iteration_a.py || true; \
	 echo 'Logs:'; tail -n 100 logs/validate_iteration_a.log || true

MLFLOW_TRACKING_URI ?= http://127.0.0.1:5000

train-mlflow:
	MLFLOW_TRACKING_URI=$(MLFLOW_TRACKING_URI) $(VENVPY) tools/train_mlflow.py --run-name local-train

compose-up-observe:
	docker compose -f docker-compose.yml -f docker-compose.observability.yml up -d --build --force-recreate

compose-down-observe:
	docker compose -f docker-compose.yml -f docker-compose.observability.yml down -v --remove-orphans

# Kubernetes / Minikube
K8S_NS ?= calories
HOST_PORT ?= 8000

k8s-status:
	minikube status || true

k8s-up:
	# Start minikube if not running; do not change CPU/memory on existing cluster
	@if ! minikube status | grep -q "host: Running"; then \
		echo "Starting Minikube..."; \
		minikube start --driver=docker; \
	else \
		echo "Minikube already running"; \
	fi

k8s-restart:
	minikube stop || true
	minikube start --driver=docker

k8s-context:
	kubectl config use-context minikube

k8s-build-img:
	# Build and load the API image into Minikube
	docker build -f docker/Dockerfile -t calories-api:local .
	minikube image load calories-api:local

k8s-apply:
	# Ensure cluster is up before applying
	$(MAKE) k8s-up
	$(MAKE) k8s-context
	kubectl apply -f k8s/namespace.yaml
	kubectl apply -f k8s/configmap.yaml
	kubectl apply -f k8s/deployment.yaml
	kubectl apply -f k8s/service.yaml
	kubectl apply -f k8s/hpa.yaml || true

k8s-delete:
	kubectl delete -f k8s/hpa.yaml --ignore-not-found
	kubectl delete -f k8s/service.yaml --ignore-not-found
	kubectl delete -f k8s/deployment.yaml --ignore-not-found
	kubectl delete -f k8s/configmap.yaml --ignore-not-found
	kubectl delete -f k8s/namespace.yaml --ignore-not-found

k8s-port-forward:
	kubectl -n $(K8S_NS) port-forward svc/api $(HOST_PORT):8000

k8s-port-forward-bg:
	@mkdir -p logs
	@echo "Starting kubectl port-forward in background (logs/log_kpf.txt, PID in .kpf.pid)"
	@nohup kubectl -n $(K8S_NS) port-forward svc/api $(HOST_PORT):8000 > logs/log_kpf.txt 2>&1 & echo $$! > .kpf.pid; sleep 1; tail -n 5 logs/log_kpf.txt || true

k8s-port-forward-stop:
	@[ -f .kpf.pid ] && kill $$(cat .kpf.pid) && rm -f .kpf.pid && echo "Stopped background port-forward" || echo "No background port-forward PID file found"

docker-build:
	docker build -f docker/Dockerfile -t calories-api:local .

compose-up:
	docker compose up --build -d

compose-down:
	docker compose down -v --remove-orphans

test:
	$(VENVPY) -m pytest -q
