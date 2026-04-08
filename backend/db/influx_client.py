from influxdb_client import InfluxDBClient

def get_client():
    client = InfluxDBClient(
        url="http://localhost:8086",
        token="your-token",
        org="raildrishti"
    )
    return client