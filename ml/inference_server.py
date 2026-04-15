"""FastAPI inference server for RailDrishti LightGBM recommendations."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from predictor import load_model, predict_payload, compare_payload

app = FastAPI(title="RailDrishti Inference API", version="0.1.0")


class TrainFeatureInput(BaseModel):
    train_id: str = Field(..., description="Unique train event identifier")
    train_no: int = Field(..., description="Train number")
    station_code: str = Field(..., description="Station code for the event")
    delay_minutes: float = Field(..., description="Current delay in minutes")
    speed_kmh: float = Field(..., description="Current train speed in km/h")
    hour_of_day: int = Field(..., ge=0, le=23, description="Hour of day 0-23")
    weather_severity: float = Field(..., ge=0.0, le=1.0, description="Normalized weather severity")
    platform_free: int = Field(..., ge=0, le=1, description="Platform availability indicator")
    headway_min: float = Field(..., description="Current headway from the previous train in minutes")
    priority: int = Field(..., ge=1, le=3, description="Train priority level")
    congestion_score: float = Field(..., ge=0.0, le=1.0, description="Corridor congestion score")


class PredictionResponse(BaseModel):
    train_id: str
    predicted_action: str
    confidence: float
    shap_top5: list[str]
    status: str = "ok"


class CompareResponse(BaseModel):
    train_id: str
    raildrishti_action: str
    indian_rail_action: str
    match: bool
    confidence: float
    difference: str
    shap_top5: list[str]
    status: str = "ok"


@app.on_event("startup")
def startup_event() -> None:
    load_model()


@app.get("/")
def root() -> dict:
    return {
        "status": "ok",
        "message": "RailDrishti Inference API",
        "endpoints": ["/health", "/predict", "/compare", "/docs"],
    }


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "model_loaded": True}


@app.post("/predict", response_model=PredictionResponse)
def predict(request: TrainFeatureInput) -> PredictionResponse:
    try:
        result = predict_payload(request.dict())
        return PredictionResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/compare", response_model=CompareResponse)
def compare(request: TrainFeatureInput) -> CompareResponse:
    try:
        result = compare_payload(request.dict())
        return CompareResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
