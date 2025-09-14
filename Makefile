.PHONY: install train train-wo-holdout holdout predict serve simulate-stream validate-a docker-build compose-up compose-down test

PY := python3
PIP := pip3

VENV := .venv
VENVPY := $(VENV)/bin/python
VENVPIP := $(VENV)/bin/pip

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
	$(VENVPY) tools/sim_stream.py --url http://127.0.0.1:8000 --feedback-delay 10 --cycles 2 --burst-rps 20 --burst-duration 5 --idle-duration 10 --limit 200

validate-a:
	PYTHONUNBUFFERED=1 timeout 60s $(VENVPY) tools/validate_iteration_a.py || true; \
	 echo 'Logs:'; tail -n 100 logs/validate_iteration_a.log || true

docker-build:
	docker build -f docker/Dockerfile -t calories-api:local .

compose-up:
	docker compose up --build -d

compose-down:
	docker compose down -v --remove-orphans

test:
	$(VENVPY) -m pytest -q
