from kafka import KafkaConsumer
import json

def start_consumer():
    """
    Listens to Kafka topic: optimized-route
    Receives: {train_id, new_path[], eta}
    """
    consumer = KafkaConsumer(
        'optimized-route',
        bootstrap_servers='localhost:9092',
        value_deserializer=lambda v: json.loads(v.decode('utf-8')),
        auto_offset_reset='earliest',
        group_id='raildrishti-backend'
    )

    print("Listening to optimized-route topic...")
    for message in consumer:
        data = message.value
        print(f"Received optimized route: {data}")
        # TODO: update train state with new route

if __name__ == "__main__":
    start_consumer()