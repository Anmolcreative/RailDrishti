from kafka import KafkaProducer
import json, time, random, urllib.request, os

producer = KafkaProducer(
    bootstrap_servers=["localhost:9092"],
    value_serializer=lambda x: json.dumps(x).encode("utf-8")
)

# Load 100 stations from file
with open("backend/data/stations.json") as f:
    data = json.load(f)

STATIONS = data["stations_100"]

# Give each station a simulated train ID and movement state
for s in STATIONS:
    s["train_id"] = f"TN{s['id']:03d}"
    s["current_lat"] = s["lat"]
    s["current_lng"] = s["lng"]

def get_weather(lat, lng):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current=temperature_2m,rain,windspeed_10m"
        with urllib.request.urlopen(url, timeout=3) as r:
            d = json.loads(r.read())
            c = d["current"]
            return {"temperature": c["temperature_2m"], "rain": c["rain"], "windspeed": c["windspeed_10m"]}
    except:
        return {"temperature": None, "rain": None, "windspeed": None}

print("RailDrishti Producer - streaming 100 stations...")

while True:
    for s in STATIONS:
        s["current_lat"] += random.uniform(-0.005, 0.005)
        s["current_lng"] += random.uniform(-0.005, 0.005)
        weather = get_weather(round(s["current_lat"], 6), round(s["current_lng"], 6))
        message = {
            "train_id":   s["train_id"],
            "station":    s["name"],
            "lat":        round(s["current_lat"], 6),
            "lng":        round(s["current_lng"], 6),
            "speed":      random.randint(40, 120),
            "delay":      random.randint(0, 30),
            "congestion": s["congestion"],
            "timestamp":  time.time(),
            "weather":    weather
        }
        producer.send("train-status", message)
        print("Sent: " + s["train_id"] + " | " + s["name"] + " | speed=" + str(message["speed"]))
    producer.flush()
    time.sleep(5)