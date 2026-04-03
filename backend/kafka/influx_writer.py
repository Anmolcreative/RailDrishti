from kafka import KafkaConsumer
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import json

# InfluxDB connection
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "raildrishti-token-2026"
INFLUX_ORG = "raildrishti"
INFLUX_BUCKET = "train-data"

client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)

consumer = KafkaConsumer(
    "train-status",
    bootstrap_servers=["localhost:9092"],
    value_deserializer=lambda x: json.loads(x.decode("utf-8"))
)

print("📊 InfluxDB writer started — storing train + weather data...")

for message in consumer:
    data = message.value
    weather = data.get("weather", {})

    point = (
        Point("train_status")
        .tag("train_id", data["train_id"])
        .tag("name", data["name"])
        .field("lat", data["lat"])
        .field("lng", data["lng"])
        .field("speed", float(data["speed"]))
        .field("delay", float(data["delay"]))
    )

    if weather.get("temperature") is not None:
        point = point.field("temperature", float(weather["temperature"]))
    if weather.get("rain") is not None:
        point = point.field("rain", float(weather["rain"]))
    if weather.get("windspeed") is not None:
        point = point.field("windspeed", float(weather["windspeed"]))

    write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
    print(f"✅ Stored: {data['train_id']} | speed={data['speed']} | delay={data['delay']}min | temp={weather.get('temperature')}°C")
