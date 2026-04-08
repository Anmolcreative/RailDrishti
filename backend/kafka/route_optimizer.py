from kafka import KafkaConsumer, KafkaProducer
import json
import time
import random

# This consumer reads train-status and simulates
# what the ML model will publish to optimized-route

producer = KafkaProducer(
    bootstrap_servers=["localhost:9092"],
    value_serializer=lambda x: json.dumps(x).encode("utf-8")
)

consumer = KafkaConsumer(
    "train-status",
    bootstrap_servers=["localhost:9092"],
    value_deserializer=lambda x: json.loads(x.decode("utf-8"))
)

print("🧠 Route optimizer listening on train-status...")

for message in consumer:
    data = message.value

    # Simulate ML decision — if delay > 15 mins, issue speed advisory
    if data["delay"] > 15:
        route_decision = {
            "train_id":   data["train_id"],
            "new_path":   ["StationA", "StationB", "StationC"],
            "advised_speed": min(data["speed"] + 20, 120),
            "eta":        time.time() + 1800,
            "reason":     "delay_recovery",
            "timestamp":  time.time()
        }

        producer.send("optimized-route", route_decision)
        producer.flush()
        print(f"✅ Route issued: {data['train_id']} | new speed={route_decision['advised_speed']} | reason={route_decision['reason']}")
    else:
        print(f"✅ {data['train_id']} on track — no action needed")
