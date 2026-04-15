import json
import os
import random
import time
from typing import Dict

import requests
from kafka import KafkaProducer

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
API_CONFIG_PATH = os.getenv("API_CONFIG_PATH", "backend/data/api_config.json")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST")

producer = KafkaProducer(
    bootstrap_servers=[KAFKA_BROKER],
    value_serializer=lambda x: json.dumps(x).encode("utf-8"),
)

with open(API_CONFIG_PATH) as f:
    config = json.load(f)

LIVE_CORRIDOR_TRAINS = config.get("live_corridors", {})
if not RAPIDAPI_KEY:
    RAPIDAPI_KEY = config.get("rapidapi_key")
if not RAPIDAPI_HOST:
    RAPIDAPI_HOST = config.get("rapidapi_host")

# Load Anmol's station data
with open("backend/data/raildrishti_stations.json") as f:
    station_data = json.load(f)

SIM_STATIONS = {
    s["code"]: s
    for s in station_data.get("simulated_stations", {}).get("stations", [])
    if s.get("lat") and s.get("lng")
}

weather_cache: Dict[str, Dict] = {}
last_weather_update: Dict[str, float] = {}

def get_weather(station_code: str, lat: float, lng: float) -> Dict[str, float]:
    now = time.time()
    if station_code not in last_weather_update or now - last_weather_update[station_code] > 600:
        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}"
                "&current_weather=true"
            )
            response = requests.get(url, timeout=7)
            response.raise_for_status()
            data = response.json()
            current = data.get("current_weather", {})
            weather_cache[station_code] = {
                "temperature": current.get("temperature"),
                "windspeed": current.get("windspeed"),
                "weather_code": current.get("weathercode"),
            }
            last_weather_update[station_code] = now
        except Exception:
            weather_cache[station_code] = {"temperature": None, "windspeed": None, "weather_code": None}
    return weather_cache.get(station_code, {})

def get_live_train_status(train_number: str) -> Dict:
    if not RAPIDAPI_KEY or not RAPIDAPI_HOST:
        return None
    try:
        url = "https://indian-railway-irctc.p.rapidapi.com/api/trains/v1/train/status"
        params = {"departure_date": "20250717", "isH5": "true", "client": "web"}
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": RAPIDAPI_HOST,
            "Content-Type": "application/json",
        }
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None

print("RailDrishti producer starting — live / fallback / simulated train-status feed")

while True:
    # --- LIVE CORRIDORS ---
    for corridor_id, train_numbers in LIVE_CORRIDOR_TRAINS.items():
        for train_no in train_numbers:
            live_data = get_live_train_status(train_no)
            if live_data:
                message = {
                    "train_id": train_no,
                    "corridor": corridor_id,
                    "data_source": "live_api",
                    "raw": live_data,
                    "timestamp": time.time()
                }
            else:
                # Fallback to simulation if API fails
                message = {
                    "train_id": train_no,
                    "corridor": corridor_id,
                    "data_source": "simulated_fallback",
                    "speed": random.randint(60, 120),
                    "delay": random.randint(0, 20),
                    "timestamp": time.time()
                }
            producer.send("train-status", message)
            print("LIVE: " + train_no + " | " + corridor_id + " | source=" + message["data_source"])

    # --- SIMULATED STATIONS ---
    for code, s in SIM_STATIONS.items():
        weather = get_weather(code, s["lat"], s["lng"])
        message = {
            "train_id": "SIM-" + code,
            "station_code": code,
            "station_name": s["name"],
            "lat": s["lat"] + random.uniform(-0.005, 0.005),
            "lng": s["lng"] + random.uniform(-0.005, 0.005),
            "speed": random.randint(40, 120),
            "delay": random.randint(0, 30),
            "congestion": s["congestion_score"],
            "platforms": s["platforms"],
            "data_source": "simulated",
            "weather": weather,
            "timestamp": time.time()
        }
        producer.send("train-status", message)
        print("SIM: " + code + " | " + s["name"] + " | delay=" + str(message["delay"]))

    producer.flush()
    print("--- Cycle complete, waiting 60s ---")
    time.sleep(60)