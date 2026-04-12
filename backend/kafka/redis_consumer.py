from kafka import KafkaConsumer
import redis, json

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

consumer = KafkaConsumer(
    "train-status",
    bootstrap_servers=["localhost:9092"],
    value_deserializer=lambda x: json.loads(x.decode("utf-8"))
)

print("Redis consumer started")

for message in consumer:
    data = message.value
    key = "train:" + data["train_id"]
    r.setex(key, 30, json.dumps(data))
    print("Cached: " + key)
