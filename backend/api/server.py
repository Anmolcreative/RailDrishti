"""RailDrishti API gateway for frontend integration and realtime events."""

import asyncio
import json
import os
import threading
import time
from typing import Any, Dict, List

import redis
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from kafka import KafkaConsumer

from ml.predictor import load_model, predict_payload

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

app = FastAPI(title="RailDrishti API Gateway", version="0.1.0")

_websocket_clients: List[WebSocket] = []
_event_loop = None
_scraper_health: Dict[str, Any] = {
    "status": "ok",
    "source": "simulated",
    "last_success": 0,
    "last_failure": None,
}


class PredictionRequest(BaseModel):
    train_id: str = Field(...)
    train_no: int = Field(...)
    station_code: str = Field(...)
    delay_minutes: float = Field(...)
    speed_kmh: float = Field(...)
    hour_of_day: int = Field(..., ge=0, le=23)
    weather_severity: float = Field(..., ge=0.0, le=1.0)
    platform_free: int = Field(..., ge=0, le=1)
    headway_min: float = Field(...)
    priority: int = Field(..., ge=1, le=3)
    congestion_score: float = Field(..., ge=0.0, le=1.0)


class PredictionResponse(BaseModel):
    train_id: str
    predicted_action: str
    confidence: float
    shap_top5: List[str]
    status: str = "ok"


@app.on_event("startup")
def startup_event() -> None:
    global _event_loop
    _event_loop = asyncio.get_event_loop()
    load_model()
    thread = threading.Thread(target=consume_kafka_train_status, daemon=True)
    thread.start()


def broadcast(event: Dict[str, Any]) -> None:
    if _event_loop is None:
        return
    message = json.dumps(event)
    for websocket in list(_websocket_clients):
        asyncio.run_coroutine_threadsafe(websocket.send_text(message), _event_loop)


def consume_kafka_train_status() -> None:
    try:
        consumer = KafkaConsumer(
            "train-status",
            bootstrap_servers=[KAFKA_BROKER],
            value_deserializer=lambda x: json.loads(x.decode("utf-8")),
            auto_offset_reset="latest",
            consumer_timeout_ms=1000,
        )
    except Exception:
        return

    for message in consumer:
        data = message.value
        key = f"train:{data.get('train_id', 'unknown')}"
        redis_client.setex(key, 30, json.dumps(data))
        _scraper_health.update({"last_success": int(time.time()), "source": data.get("data_source", "unknown")})
        broadcast({"type": "train_status", "payload": data})


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "backend": True, "redis": redis_client.ping()}


@app.get("/api/scraper/health")
def scraper_health() -> Dict[str, Any]:
    return _scraper_health


@app.get("/api/train-status")
def list_train_status() -> List[Dict[str, Any]]:
    keys = [k.decode("utf-8") if isinstance(k, bytes) else k for k in redis_client.keys("train:*")]
    values = []
    for key in keys:
        raw = redis_client.get(key)
        if raw:
            values.append(json.loads(raw))
    return values


@app.get("/api/train-status/{train_id}")
def get_train_status(train_id: str) -> Dict[str, Any]:
    raw = redis_client.get(f"train:{train_id}")
    if not raw:
        raise HTTPException(status_code=404, detail="Train status not found")
    return json.loads(raw)


@app.post("/api/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest) -> PredictionResponse:
    result = predict_payload(request.dict())
    return PredictionResponse(**result)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    _websocket_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _websocket_clients.remove(websocket)
