"""
RailDrishti — FastAPI ML Inference Server
POST /predict  →  { action, confidence, shap_top5 }
Latency target: < 50ms p99
"""

import os
import json
import time
import logging
import pickle
from contextlib import asynccontextmanager
from typing import Optional

import numpy as np
import shap
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("raildrishti.inference")

# ── Constants ─────────────────────────────────────────────────────────────────
MODEL_PATH  = os.getenv("MODEL_PATH",  "ml/model/lightgbm_recommender.pkl")
SCHEMA_PATH = os.getenv("SCHEMA_PATH", "ml/model/feature_schema.json")
ENCODER_PATH = os.getenv("ENCODER_PATH", "ml/model/label_encoder.pkl")

ACTION_LABELS = ["APPROVE", "HOLD", "REROUTE", "PRIORITY_OVERRIDE"]

# ── Global model state ────────────────────────────────────────────────────────
_model         = None
_feature_names = None
_label_encoder = None
_explainer     = None


def load_artifacts():
    global _model, _feature_names, _label_encoder, _explainer

    log.info("Loading LightGBM model from %s …", MODEL_PATH)
    with open(MODEL_PATH, "rb") as f:
        _model = pickle.load(f)

    log.info("Loading feature schema from %s …", SCHEMA_PATH)
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)
    _feature_names = schema["feature_names"]

    log.info("Loading label encoder from %s …", ENCODER_PATH)
    with open(ENCODER_PATH, "rb") as f:
        _label_encoder = pickle.load(f)

    log.info("Building SHAP TreeExplainer …")
    _explainer = shap.TreeExplainer(_model)

    log.info("All artifacts loaded. Ready to serve predictions.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_artifacts()
    yield
    log.info("Shutting down inference server.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="RailDrishti ML Inference",
    version="2.0.0",
    description="LightGBM multiclass action recommender for Indian Railways",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in prod
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


# ── Request / Response schemas ────────────────────────────────────────────────
class TrainFeatureVector(BaseModel):
    # Core delay / congestion
    delay_minutes:      float = Field(..., ge=0,  description="Current delay in minutes")
    congestion_score:   float = Field(..., ge=0, le=1, description="Corridor congestion 0–1")
    speed_kmh:          float = Field(..., ge=0, le=200)
    trains_ahead:       int   = Field(..., ge=0)
    trailing_gap_min:   float = Field(..., ge=0)

    # Train identity
    train_type:         str   = Field(..., description="EXPRESS|RAJDHANI|PASSENGER|FREIGHT|LOCAL")
    is_vip:             bool  = Field(False)
    is_freight:         bool  = Field(False)

    # Station context
    station_zone:       str   = Field(..., description="CR|ER|NR|NWR|SCR|SR|WR|WCR|ECR|NER|SER")
    station_type:       str   = Field(..., description="JUNCTION|TERMINAL|HALT|WAYSTATION")
    platform_utilisation: float = Field(..., ge=0, le=1)

    # Weather
    weather_state:      int   = Field(..., ge=0, le=4, description="0=Clear 1=Clouds 2=Rain 3=Fog 4=Storm")
    temperature_c:      float = Field(...)
    precipitation_mm:   float = Field(0.0, ge=0)

    # Temporal
    hour_of_day:        int   = Field(..., ge=0, le=23)
    day_of_week:        int   = Field(..., ge=0, le=6)
    is_peak_hour:       bool  = Field(False)

    # Derived / engineered
    delay_velocity:     float = Field(0.0, description="Rate of delay change min/min")
    cascade_risk:       float = Field(..., ge=0, le=1)
    historical_avg_delay: float = Field(0.0, ge=0)

    # Optional metadata (not used in inference, echoed back)
    train_no:           Optional[str] = None
    station_code:       Optional[str] = None
    corridor_id:        Optional[str] = None

    @validator("train_type")
    def validate_train_type(cls, v):
        allowed = {"EXPRESS", "RAJDHANI", "PASSENGER", "FREIGHT", "LOCAL"}
        if v.upper() not in allowed:
            raise ValueError(f"train_type must be one of {allowed}")
        return v.upper()

    @validator("station_zone")
    def validate_zone(cls, v):
        allowed = {"CR","ER","NR","NWR","SCR","SR","WR","WCR","ECR","NER","SER","NFR","SWR","ECoR","SECR"}
        if v.upper() not in allowed:
            raise ValueError(f"station_zone must be one of {allowed}")
        return v.upper()


class SHAPFeature(BaseModel):
    feature: str
    value:   float
    impact:  float


class PredictionResponse(BaseModel):
    action:       str
    action_index: int
    confidence:   float
    probabilities: dict[str, float]
    shap_top5:    list[SHAPFeature]
    latency_ms:   float
    train_no:     Optional[str]
    station_code: Optional[str]
    corridor_id:  Optional[str]


# ── Feature engineering helpers ───────────────────────────────────────────────
TRAIN_TYPE_MAP   = {"EXPRESS": 0, "RAJDHANI": 1, "PASSENGER": 2, "FREIGHT": 3, "LOCAL": 4}
ZONE_MAP         = {"CR":0,"ER":1,"NR":2,"NWR":3,"SCR":4,"SR":5,"WR":6,
                    "WCR":7,"ECR":8,"NER":9,"SER":10,"NFR":11,"SWR":12,"ECoR":13,"SECR":14}
STATION_TYPE_MAP = {"JUNCTION":0,"TERMINAL":1,"HALT":2,"WAYSTATION":3}


def build_feature_vector(req: TrainFeatureVector) -> np.ndarray:
    """Map Pydantic model → numpy array matching training feature order."""
    vec = {
        "delay_minutes":         req.delay_minutes,
        "congestion_score":      req.congestion_score,
        "speed_kmh":             req.speed_kmh,
        "trains_ahead":          float(req.trains_ahead),
        "trailing_gap_min":      req.trailing_gap_min,
        "train_type_enc":        float(TRAIN_TYPE_MAP.get(req.train_type, 0)),
        "is_vip":                float(req.is_vip),
        "is_freight":            float(req.is_freight),
        "station_zone_enc":      float(ZONE_MAP.get(req.station_zone, 0)),
        "station_type_enc":      float(STATION_TYPE_MAP.get(req.station_type, 0)),
        "platform_utilisation":  req.platform_utilisation,
        "weather_state":         float(req.weather_state),
        "temperature_c":         req.temperature_c,
        "precipitation_mm":      req.precipitation_mm,
        "hour_of_day":           float(req.hour_of_day),
        "day_of_week":           float(req.day_of_week),
        "is_peak_hour":          float(req.is_peak_hour),
        "delay_velocity":        req.delay_velocity,
        "cascade_risk":          req.cascade_risk,
        "historical_avg_delay":  req.historical_avg_delay,
    }
    # Ensure ordering matches training schema
    return np.array([[vec[f] for f in _feature_names]])


def compute_shap_top5(feature_vec: np.ndarray, pred_class: int) -> list[SHAPFeature]:
    try:
        shap_values = _explainer.shap_values(feature_vec)
        # shap_values is list[n_classes] of arrays (n_samples, n_features)
        class_shap = shap_values[pred_class][0]
        top_idx    = np.argsort(np.abs(class_shap))[::-1][:5]
        return [
            SHAPFeature(
                feature=_feature_names[i],
                value=float(feature_vec[0, i]),
                impact=float(class_shap[i]),
            )
            for i in top_idx
        ]
    except Exception as e:
        log.warning("SHAP computation failed: %s", e)
        return []


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.post("/predict", response_model=PredictionResponse)
async def predict(req: TrainFeatureVector):
    if _model is None:
        raise HTTPException(503, "Model not loaded")

    t0 = time.perf_counter()

    try:
        fv   = build_feature_vector(req)
        prob = _model.predict_proba(fv)[0]        # shape (4,)
        idx  = int(np.argmax(prob))
        confidence = float(prob[idx])
    except Exception as e:
        log.error("Inference error: %s", e)
        raise HTTPException(500, f"Inference failed: {e}")

    shap_top5 = compute_shap_top5(fv, idx)
    latency   = (time.perf_counter() - t0) * 1000

    log.info(
        "PREDICT train=%s station=%s → %s (%.2f%%) | %.1fms",
        req.train_no, req.station_code, ACTION_LABELS[idx], confidence * 100, latency,
    )

    return PredictionResponse(
        action=ACTION_LABELS[idx],
        action_index=idx,
        confidence=confidence,
        probabilities={label: float(p) for label, p in zip(ACTION_LABELS, prob)},
        shap_top5=shap_top5,
        latency_ms=round(latency, 2),
        train_no=req.train_no,
        station_code=req.station_code,
        corridor_id=req.corridor_id,
    )


@app.get("/health")
async def health():
    return {
        "status":  "ok" if _model is not None else "loading",
        "model":   MODEL_PATH,
        "version": "2.0.0",
    }


@app.get("/schema")
async def schema():
    return {
        "feature_names": _feature_names,
        "action_labels": ACTION_LABELS,
        "n_features":    len(_feature_names) if _feature_names else 0,
    }


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "inference_server:app",
        host="0.0.0.0",
        port=8000,
        workers=1,          # single worker — LightGBM is thread-safe; use Gunicorn for multi
        log_level="info",
        reload=False,
    )