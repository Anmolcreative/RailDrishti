FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY backend/inference_server.py .
COPY ml/feature_engineering.py .
COPY ml/model/ ./ml/model/

EXPOSE 8000

CMD ["python", "inference_server.py"]
