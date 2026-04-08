from kafka import KafkaProducer
import json

def get_producer():
    producer = KafkaProducer(
        bootstrap_servers='localhost:9092',
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    return producer

def send_train_status(train_data: dict):
    """
    Sends train status to Kafka topic: train-status
    train_data format: {train_id, lat, lng, speed, delay}
    """
    producer = get_producer()
    producer.send('train-status', train_data)
    producer.flush()
    print(f"Sent to Kafka: {train_data}")

# Test
if __name__ == "__main__":
    send_train_status({
        "train_id": "TN001",
        "lat": 19.0760,
        "lng": 72.8777,
        "speed": 60,
        "delay": 5
    })