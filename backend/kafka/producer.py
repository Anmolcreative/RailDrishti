from kafka import KafkaProducer
import json, time, random, urllib.request, os
from datetime import datetime

producer = KafkaProducer(
    bootstrap_servers=["localhost:9092"],
    value_serializer=lambda x: json.dumps(x).encode("utf-8")
)

# Load config and station data
with open("backend/data/api_config.json") as f:
    config = json.load(f)

with open("backend/data/raildrishti_stations.json") as f:
    station_data = json.load(f)

RAPIDAPI_KEY = config["rapidapi_key"]
RAPIDAPI_HOST = config["rapidapi_host"]
INDIANRAIL_KEY = config.get("indianrail_key", "")

# Real trains per corridor from PRD
CORRIDOR_TRAINS = {
    "BPL-ET":   ["12155", "12156", "11071", "11072", "12967", "12968"],
    "NDLS-MGS": ["12301", "12302", "12309", "12310", "12381", "12382", "12627", "12628"],
    "HWH-DHN":  ["12259", "12260", "13005", "13006", "12819", "12820"]
}

# Load live corridor stations
LIVE_STATIONS = {}
for corridor_id, corridor in station_data["live_corridors"].items():
    for s in corridor["stations"]:
        LIVE_STATIONS[s["code"]] = s

# Load simulated stations
SIM_STATIONS = [s for s in station_data["simulated_stations"]["stations"] if s.get("lat") and s.get("lng")]

# Weather cache — 15 min for simulated as per PRD
weather_cache = {}
last_weather_update = {}

def get_weather(code, lat, lng):
    now = time.time()
    if code not in last_weather_update or now - last_weather_update[code] > 900:
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current=temperature_2m,rain,windspeed_10m,weathercode"
            with urllib.request.urlopen(url, timeout=3) as r:
                d = json.loads(r.read())["current"]
                # Map weather to PRD conditions
                code_val = d.get("weathercode", 0)
                if code_val >= 95:
                    condition = "STORM"
                    speed_cap = 20
                elif code_val >= 61:
                    condition = "RAIN"
                    speed_cap = 80
                elif code_val >= 45:
                    condition = "DENSE_FOG"
                    speed_cap = 40
                else:
                    condition = "CLEAR"
                    speed_cap = 110
                weather_cache[code] = {
                    "temperature_c": d["temperature_2m"],
                    "rain": d["rain"],
                    "windspeed": d["windspeed_10m"],
                    "condition": condition,
                    "max_speed_kmh": speed_cap
                }
                last_weather_update[code] = now
        except:
            weather_cache[code] = {"condition": "CLEAR", "max_speed_kmh": 110}
    return weather_cache.get(code, {"condition": "CLEAR", "max_speed_kmh": 110})

def get_live_train(train_number):
    # Try indianrailapi.com first
    if INDIANRAIL_KEY:
        try:
            today = datetime.now().strftime("%Y%m%d")
            url = f"http://indianrailapi.com/api/v2/livetrainstatus/apikey/{INDIANRAIL_KEY}/trainnumber/{train_number}/date/{today}/"
            with urllib.request.urlopen(url, timeout=5) as r:
                data = json.loads(r.read())
                if data.get("ResponseCode") == "200":
                    return data
        except Exception as e:
            print("indianrailapi error: " + str(e))
    # Fallback to RapidAPI
    try:
        today = datetime.now().strftime("%Y%m%d")
        url = f"https://indian-railway-irctc.p.rapidapi.com/api/trains/v1/train/status?departure_date={today}&isH5=true&client=web&train_number={train_number}"
        req = urllib.request.Request(url)
        req.add_header("x-rapidapi-key", RAPIDAPI_KEY)
        req.add_header("x-rapidapi-host", RAPIDAPI_HOST)
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            if data.get("status"):
                return data
    except Exception as e:
        print("rapidapi error: " + str(e))
    return None

print("RailDrishti Producer started")
print("Live corridors: 2s feed | Simulated: 15min feed")

last_sim_update = 0

while True:
    loop_start = time.time()

    # --- LIVE CORRIDORS — every 2 seconds as per PRD ---
    for corridor_id, trains in CORRIDOR_TRAINS.items():
        corridor_key = corridor_id.replace("-", "_")
        corridor_stations = station_data["live_corridors"].get(corridor_key, {}).get("stations", [])
        for train_no in trains:
            live_data = get_live_train(train_no)
            if live_data:
                msg = {
                    "train_id": train_no,
                    "corridor": corridor_id,
                    "data_source": "live_api",
                    "live_response": live_data,
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                # Realistic fallback simulation
                station = random.choice(corridor_stations) if corridor_stations else {}
                msg = {
                    "train_id": train_no,
                    "corridor": corridor_id,
                    "data_source": "simulated_fallback",
                    "current_station_code": station.get("code", "UNK"),
                    "current_speed_kmh": random.randint(60, 110),
                    "delay_min": round(random.gauss(8.3, 2.0), 1),
                    "congestion_score": station.get("congestion_score", 0.5),
                    "priority_flag": 3,
                    "timestamp": datetime.utcnow().isoformat()
                }
            producer.send("train-status", msg)
            print("LIVE: " + train_no + " | " + corridor_id + " | " + msg["data_source"])

    producer.flush()

    # --- SIMULATED STATIONS — every 15 minutes as per PRD ---
    now = time.time()
    if now - last_sim_update >= 900:
        print("--- Simulated station tick ---")
        for s in SIM_STATIONS:
            weather = get_weather(s["code"], s["lat"], s["lng"])
            msg = {
                "train_id": "SIM-" + s["code"],
                "station_code": s["code"],
                "station_name": s["name"],
                "lat": s["lat"] + random.gauss(0, 0.005),
                "lng": s["lng"] + random.gauss(0, 0.005),
                "speed": random.randint(40, int(weather["max_speed_kmh"])),
                "delay_min": round(random.gauss(0, 2.0), 1),
                "congestion_score": s["congestion_score"],
                "platforms": s["platforms"],
                "data_source": "simulated",
                "weather": weather,
                "timestamp": datetime.utcnow().isoformat()
            }
            producer.send("train-status", msg)
        producer.flush()
        last_sim_update = now
        print("Simulated tick done — " + str(len(SIM_STATIONS)) + " stations sent")

    # Sleep 2 seconds for next live corridor cycle
    elapsed = time.time() - loop_start
    sleep_time = max(0, 2 - elapsed)
    time.sleep(sleep_time)