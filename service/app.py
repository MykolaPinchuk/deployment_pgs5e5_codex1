import os
import sys
import time
import logging
import traceback
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, field_validator
from starlette.middleware.base import BaseHTTPMiddleware

# Prometheus metrics
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)


# --------------------
# Config
# --------------------
HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, os.pardir))

DEFAULT_HANDOUT_DIR = os.path.join(ROOT, "handout_from DS_agent")
HANDOUT_DIR = os.environ.get("HANDOUT_DIR", DEFAULT_HANDOUT_DIR)
MODEL_PATH = os.environ.get(
    "MODEL_PATH", os.path.join(HANDOUT_DIR, "model.joblib")
)
PREDICTION_WINDOW_SECONDS = int(os.environ.get("PREDICTION_WINDOW_SECONDS", "300"))
ALLOW_STARTUP_FAILURE = os.environ.get("ALLOW_STARTUP_FAILURE", "1") == "1"

# Threading controls (honored by xgboost/BLAS if set before import/use)
_half_threads = max(1, os.cpu_count() // 2 if os.cpu_count() else 1)
os.environ.setdefault("OMP_NUM_THREADS", str(_half_threads))
os.environ.setdefault("MKL_NUM_THREADS", str(_half_threads))
os.environ.setdefault("XGBOOST_NUM_THREADS", str(_half_threads))


# --------------------
# Schemas
# --------------------
class PredictRecord(BaseModel):
    id: int
    Age: float
    Height: float
    Weight: float
    Duration: float
    Heart_Rate: float
    Body_Temp: float
    Gender: Optional[str] = None
    Sex: Optional[str] = None

    @field_validator("Sex")
    @classmethod
    def _norm_sex(cls, v):
        return v

    @field_validator("Gender")
    @classmethod
    def _norm_gender(cls, v):
        return v

    @field_validator("Body_Temp")
    @classmethod
    def _validate_temp(cls, v):
        # basic sanity; allow realistic human body temp range
        return float(v)

    @field_validator("Heart_Rate")
    @classmethod
    def _validate_hr(cls, v):
        return float(v)

    @field_validator("Duration")
    @classmethod
    def _validate_duration(cls, v):
        return float(v)

    @field_validator("Height")
    @classmethod
    def _validate_height(cls, v):
        return float(v)

    @field_validator("Weight")
    @classmethod
    def _validate_weight(cls, v):
        return float(v)

    @field_validator("Age")
    @classmethod
    def _validate_age(cls, v):
        return float(v)

    @field_validator("Gender", "Sex")
    @classmethod
    def _normalize_case(cls, v):
        if v is None:
            return v
        s = str(v).strip().lower()
        if s in ("m", "male"):
            return "male"
        if s in ("f", "female"):
            return "female"
        return str(v)

    @field_validator("Sex")
    @classmethod
    def _require_gender_or_sex(cls, v, info):
        # Pydantic v2: to enforce one-of, validate in model_post_init
        return v

    def model_post_init(self, __context):
        if self.Gender is None and self.Sex is None:
            raise ValueError("One of 'Gender' or 'Sex' must be provided")


class FeedbackRecord(BaseModel):
    id: int
    Calories: float
    ts: Optional[float] = None  # epoch seconds when ground truth observed


# --------------------
# Metrics and state
# --------------------
REQUEST_COUNT = Counter(
    "app_requests_total", "Total HTTP requests", ["route", "method", "status"]
)
REQUEST_LATENCY = Histogram(
    "app_request_latency_seconds", "Request latency seconds", ["route", "method"]
)
PRED_VALUE = Histogram(
    "app_pred_calories", "Predicted calories value"
)
FEEDBACK_LAG = Histogram(
    "app_feedback_lag_seconds", "Seconds between prediction and feedback"
)
ROLLING_RMSLE_5M = Gauge("app_rolling_rmsle_5m", "Rolling RMSLE over last 5 minutes")
ROLLING_MAE_5M = Gauge("app_rolling_mae_5m", "Rolling MAE over last 5 minutes")
COVERAGE_5M = Gauge(
    "app_feedback_coverage_5m",
    "Fraction of predictions in last 5 minutes that have feedback",
)


class MetricsState:
    def __init__(self, window_seconds: int = 300):
        self.window = window_seconds
        # predictions: id -> (ts_pred, y_pred)
        self.pred_index: Dict[int, Tuple[float, float]] = {}
        self.pred_deque: deque[Tuple[int, float]] = deque()
        # evaluations: deque of (ts_eval, sq_log_err, abs_err)
        self.eval_deque: deque[Tuple[float, float, float]] = deque()
        # matched by id for coverage accounting
        self.matched_ids: Dict[int, float] = {}

    def add_prediction(self, rec_id: int, y_pred: float, ts_pred: Optional[float] = None):
        ts = time.time() if ts_pred is None else ts_pred
        self.pred_index[rec_id] = (ts, y_pred)
        self.pred_deque.append((rec_id, ts))
        PRED_VALUE.observe(float(y_pred))

    def add_feedback(self, rec_id: int, y_true: float, ts_true: Optional[float] = None):
        now = time.time()
        ts_feedback = now if ts_true is None else ts_true
        pred = self.pred_index.get(rec_id)
        if pred is None:
            return  # unknown id; ignore silently
        ts_pred, y_pred = pred
        lag = max(0.0, ts_feedback - ts_pred)
        FEEDBACK_LAG.observe(lag)
        # compute errors
        y_true = float(y_true)
        y_pred = float(y_pred)
        sq_log_err = float((np.log1p(y_true) - np.log1p(y_pred)) ** 2)
        abs_err = float(abs(y_true - y_pred))
        self.eval_deque.append((now, sq_log_err, abs_err))
        self.matched_ids[rec_id] = ts_pred
        self._recompute(now)

    def _recompute(self, now: Optional[float] = None):
        if now is None:
            now = time.time()
        cutoff = now - self.window
        # evict old preds
        while self.pred_deque and self.pred_deque[0][1] < cutoff:
            rid, _ = self.pred_deque.popleft()
            self.pred_index.pop(rid, None)
            self.matched_ids.pop(rid, None)
        # evict old evals
        while self.eval_deque and self.eval_deque[0][0] < cutoff:
            self.eval_deque.popleft()
        # recompute DS aggregates
        n = len(self.eval_deque)
        if n > 0:
            sum_sq = sum(x[1] for x in self.eval_deque)
            sum_abs = sum(x[2] for x in self.eval_deque)
            rmsle = float(np.sqrt(sum_sq / n))
            mae = float(sum_abs / n)
            ROLLING_RMSLE_5M.set(rmsle)
            ROLLING_MAE_5M.set(mae)
        else:
            ROLLING_RMSLE_5M.set(0.0)
            ROLLING_MAE_5M.set(0.0)
        # coverage = matched predictions / total predictions in window
        total_preds = len(self.pred_deque)
        matched = len(self.matched_ids)
        cov = float(matched) / float(total_preds) if total_preds > 0 else 0.0
        COVERAGE_5M.set(cov)


state = MetricsState(PREDICTION_WINDOW_SECONDS)


# --------------------
# Model loading
# --------------------
def load_model(model_path: str, handout_dir: str):
    # Ensure handout dir on sys.path so ModelWrapper class resolves during load
    if handout_dir not in sys.path:
        sys.path.insert(0, handout_dir)
    model = joblib.load(model_path)
    return model


model = None


# --------------------
# App & middleware
# --------------------
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(message)s')
app = FastAPI(title="Calories Prediction Service", version="0.1.0")


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
            status_code = getattr(response, "status_code", 500)
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.perf_counter() - start
            route = request.url.path
            method = request.method
            REQUEST_COUNT.labels(route=route, method=method, status=str(status_code)).inc()
            REQUEST_LATENCY.labels(route=route, method=method).observe(duration)
        return response


app.add_middleware(MetricsMiddleware)


startup_error: Optional[str] = None


@app.on_event("startup")
def _startup():
    global model, startup_error
    logging.info("Startup: HANDOUT_DIR=%s MODEL_PATH=%s", HANDOUT_DIR, MODEL_PATH)
    if not os.path.exists(MODEL_PATH):
        msg = f"Model artifact not found at {MODEL_PATH}. Run training first."
        logging.error(msg)
        if ALLOW_STARTUP_FAILURE:
            startup_error = msg
            return
        raise RuntimeError(msg)
    try:
        model = load_model(MODEL_PATH, HANDOUT_DIR)
        logging.info("Startup: model loaded OK")
    except Exception:
        err = traceback.format_exc()
        logging.error("Startup: model load failed\n%s", err)
        if ALLOW_STARTUP_FAILURE:
            startup_error = err
            model = None
            return
        raise


@app.get("/healthz")
def healthz():
    try:
        ok = model is not None and startup_error is None
    except Exception:
        ok = False
    body = {"status": "ok" if ok else "uninitialized"}
    if startup_error:
        body["error"] = startup_error.splitlines()[-1][:240]
    return body


@app.post("/predict")
def predict(rec: PredictRecord):
    # Convert to DataFrame expected by DS model
    data = rec.model_dump()
    if data.get("Gender") is None and data.get("Sex") is not None:
        data["Gender"] = data["Sex"]
    df = pd.DataFrame([{
        "id": data["id"],
        "Gender": data.get("Gender"),
        "Age": data["Age"],
        "Height": data["Height"],
        "Weight": data["Weight"],
        "Duration": data["Duration"],
        "Heart_Rate": data["Heart_Rate"],
        "Body_Temp": data["Body_Temp"],
    }])
    if model is None:
        return JSONResponse({"error": "model not loaded"}, status_code=503)
    y_hat = float(model.predict(df)[0])
    state.add_prediction(rec.id, y_hat)
    return {"id": rec.id, "Calories": y_hat}


@app.post("/feedback")
def feedback(rec: FeedbackRecord):
    state.add_feedback(rec.id, rec.Calories, ts_true=rec.ts)
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    # scrape-time recompute to keep coverage fresh
    state._recompute()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/")
def root():
    return {"name": "Calories Prediction Service", "version": "0.1.0"}
