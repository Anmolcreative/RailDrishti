from kafka import KafkaProducer
import json
import time
import random
import urllib.request

producer = KafkaProducer(
    bootstrap_servers=["localhost:9092"],
    value_serializer=lambda x: json.dumps(x).encode("utf-8")
)

TRAINS = [
    {"train_id": "TN001", "name": "Rajdhani Express", "lat": 19.0760, "lng": 72.8777},
    {"train_id": "TN002", "name": "Shatabdi Express", "lat": 28.6139, "lng": 77.2090},
    {"train_id": "TN003", "name": "Duronto Express",  "lat": 22.5726, "lng": 88.3639},
    {"train_id": "TN004", "name": "Garib Rath",       "lat": 17.3850, "lng": 78.4867},
    {"train_id": "TN005", "name": "Jan Shatabdi",     "lat": 13.0827, "lng": 80.2707},
]

def get_weather(lat, lng):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current=temperature_2m,rain,windspeed_10m"
        with urllib.request.urlopen(url, timeout=3) as r:
            data = json.loads(r.read())
            current = data["current"]
            return {
                "temperature": current["temperature_2m"],
                "rain":        current["rain"],
                "windspeed":   current["windspeed_10m"]
            }
    except:
        return {"temperature": None, "rain": None, "windspeed": None}

print("🚂 RailDrishti Producer started — streaming train data with weather...")

while True:
    for train in TRAINS:
        train["lat"] += random.uniform(-0.01, 0.01)
        train["lng"] += random.uniform(-0.01, 0.01)

        weather = get_weather(round(train["lat"], 6), round(train["lng"], 6))

        message = {
            "train_id":    train["train_id"],
            "name":        train["name"],
            "lat":         round(train["lat"], 6),
            "lng":         round(train["lng"], 6),
            "speed":       random.randint(40, 120),
            "delay":       random.randint(0, 30),
            "timestamp":   time.time(),
            "weather":     weather
        }

        producer.send("train-status", message)
        print(f"📡 {message['train_id']} | speed={message['speed']} | delay={message['delay']}min | temp={weather['temperature']}°C | rain={weather['rain']}mm")

    producer.flush()
    time.sleep(3)
