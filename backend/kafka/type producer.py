from kafka import KafkaProducer
import json

producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda x: json.dumps(x).encode('utf-8')
)

# Test message
producer.send('train-status', {
    'train_id': 'TN001',
    'lat': 19.0760,
    'lng': 72.8777,
    'speed': 60,
    'delay': 5
})

print("✅ Message sent to Kafka!")
producer.flush()