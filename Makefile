.PHONY: install train predict serve simulate-stream validate-a

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

predict:
	$(VENVPY) "handout_from DS_agent/predict.py"

serve:
	HANDOUT_DIR="$(PWD)/handout_from DS_agent" \
	MODEL_PATH="$(PWD)/handout_from DS_agent/model.joblib" \
	OMP_NUM_THREADS=$$(python3 -c 'import os;print(max(1,(os.cpu_count() or 2)//2))') \
	MKL_NUM_THREADS=$$(python3 -c 'import os;print(max(1,(os.cpu_count() or 2)//2))') \
	XGBOOST_NUM_THREADS=$$(python3 -c 'import os;print(max(1,(os.cpu_count() or 2)//2))') \
	$(VENVPY) -m uvicorn service.app:app --host 0.0.0.0 --port 8000

simulate-stream:
	$(VENVPY) tools/sim_stream.py --url http://127.0.0.1:8000 --feedback-delay 10 --cycles 2 --burst-rps 20 --burst-duration 5 --idle-duration 10 --limit 200

validate-a:
	PYTHONUNBUFFERED=1 timeout 60s $(VENVPY) tools/validate_iteration_a.py || true; \
	 echo 'Logs:'; tail -n 100 logs/validate_iteration_a.log || true
