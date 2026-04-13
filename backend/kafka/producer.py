from kafka import KafkaProducer
import json, time, random, urllib.request, urllib.error, os

producer = KafkaProducer(
    bootstrap_servers=["localhost:9092"],
    value_serializer=lambda x: json.dumps(x).encode("utf-8")
)

# Load config
with open("backend/data/api_config.json") as f:
    config = json.load(f)

RAPIDAPI_KEY = config["rapidapi_key"]
RAPIDAPI_HOST = config["rapidapi_host"]
LIVE_CORRIDOR_TRAINS = config["live_corridors"]

# Load Anmol's station data
with open("backend/data/raildrishti_stations.json") as f:
    station_data = json.load(f)

LIVE_STATIONS = {}
for corridor_id, corridor in station_data["live_corridors"].items():
    for s in corridor["stations"]:
        LIVE_STATIONS[s["code"]] = s

SIM_STATIONS = {}
for s in station_data["simulated_stations"]["stations"]:
    if s.get("lat") and s.get("lng"):
        SIM_STATIONS[s["code"]] = s

# Weather cache — update every 10 min for simulated
weather_cache = {}
last_weather_update = {}

def get_weather(station_code, lat, lng):
    now = time.time()
    if station_code not in last_weather_update or now - last_weather_update[station_code] > 600:
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current=temperature_2m,rain,windspeed_10m"
            with urllib.request.urlopen(url, timeout=3) as r:
                d = json.loads(r.read())
                c = d["current"]
                weather_cache[station_code] = {
                    "temperature": c["temperature_2m"],
                    "rain": c["rain"],
                    "windspeed": c["windspeed_10m"]
                }
                last_weather_update[station_code] = now
        except:
            weather_cache[station_code] = {"temperature": None, "rain": None, "windspeed": None}
    return weather_cache.get(station_code, {})

def get_live_train_status(train_number):
    try:
        url = f"https://indian-railway-irctc.p.rapidapi.com/api/trains/v1/train/status?departure_date=20250717&isH5=true&client=web"
        req = urllib.request.Request(url)
        req.add_header("x-rapidapi-key", RAPIDAPI_KEY)
        req.add_header("x-rapidapi-host", RAPIDAPI_HOST)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())
    except:
        return None

print("RailDrishti Producer - 3 live corridors + 100 simulated stations...")

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