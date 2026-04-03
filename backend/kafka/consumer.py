from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'train-status',
    bootstrap_servers=['localhost:9092'],
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

print("✅ Listening for train updates...")
for message in consumer:
    print("Received:", message.value)