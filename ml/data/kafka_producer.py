
import json

producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda x: json.dumps(x).encode('utf-8')
)

def get_live_train_data():
    return [
        {"train_id": "TN001", "station": "Bhopal",
         "lat": 23.2599, "lng": 77.4126,
         "speed": 60, "delay": 45,
         "congestion": 0.8, "trains": 80,
         "weather_visibility": 0.9},
        {"train_id": "TN002", "station": "Obaidullaganj",
         "lat": 22.9500, "lng": 77.6200,
         "speed": 70, "delay": 20,
         "congestion": 0.5, "trains": 40,
         "weather_visibility": 0.85},
        {"train_id": "TN003", "station": "Hoshangabad",
         "lat": 22.7500, "lng": 77.7200,
         "speed": 55, "delay": 30,
         "congestion": 0.6, "trains": 50,
         "weather_visibility": 0.8},
        {"train_id": "TN004", "station": "Itarsi",
         "lat": 22.6139, "lng": 77.7631,
         "speed": 45, "delay": 45,
         "congestion": 0.9, "trains": 80,
         "weather_visibility": 0.75},
        {"train_id": "TN005", "station": "Pune",
         "lat": 18.5204, "lng": 73.8567,
         "speed": 75, "delay": 10,
         "congestion": 0.9, "trains": 15,
         "weather_visibility": 0.95},
        {"train_id": "TN006", "station": "Hyderabad",
         "lat": 17.3850, "lng": 78.4867,
         "speed": 65, "delay": 15,
         "congestion": 0.4, "trains": 6,
         "weather_visibility": 0.9},
        {"train_id": "TN007", "station": "Bangalore",
         "lat": 12.9716, "lng": 77.5946,
         "speed": 60, "delay": 12,
         "congestion": 0.5, "trains": 8,
         "weather_visibility": 0.88},
        {"train_id": "TN008", "station": "Surat",
         "lat": 21.1702, "lng": 72.8311,
         "speed": 80, "delay": 5,
         "congestion": 0.1, "trains": 2,
         "weather_visibility": 0.92},
        {"train_id": "TN009", "station": "Jaipur",
         "lat": 26.9124, "lng": 75.7873,
         "speed": 50, "delay": 25,
         "congestion": 0.7, "trains": 10,
         "weather_visibility": 0.7},
        {"train_id": "TN010", "station": "Lucknow",
         "lat": 26.8467, "lng": 80.9462,
         "speed": 68, "delay": 18,
         "congestion": 0.3, "trains": 5,
         "weather_visibility": 0.82}
    ]

def send_to_kafka():
    trains = get_live_train_data()
    for train in trains:
        producer.send('train-status', {
            'train_id': train['train_id'],
            'lat': train['lat'],
            'lng': train['lng'],
            'speed': train['speed'],
            'delay': train['delay']
        })
    producer.flush()
    print("✅ All trains sent to Kafka topic: train-status")

if __name__ == "__main__":
    send_to_kafka()