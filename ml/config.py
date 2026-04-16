"""
config.py — Central configuration for Rail GNN Delay Prediction System
All constants, API endpoints, corridor metadata, feature definitions.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODEL_DIR = os.path.join(BASE_DIR, "model", "checkpoints")
LOG_DIR = os.path.join(BASE_DIR, "logs")
TENSORBOARD_DIR = os.path.join(LOG_DIR, "tensorboard")

for _d in [DATA_DIR, MODEL_DIR, LOG_DIR, TENSORBOARD_DIR]:
    os.makedirs(_d, exist_ok=True)

# ---------------------------------------------------------------------------
# API ENDPOINTS
# ---------------------------------------------------------------------------

# Open-Meteo — free, no key required
WEATHER_API_BASE = "https://api.open-meteo.com/v1/forecast"
WEATHER_PARAMS = [
    "temperature_2m", "precipitation", "windspeed_10m",
    "weathercode", "visibility", "cloudcover", "relativehumidity_2m",
]

# NTES (National Train Enquiry System) — public scraping endpoints
NTES_BASE_URL = "https://enquiry.indianrail.gov.in/mntes/"
NTES_TRAIN_STATUS_URL = "https://enquiry.indianrail.gov.in/mntes/q?opt=TR&trainNo={train_no}"
NTES_STATION_URL = "https://enquiry.indianrail.gov.in/mntes/q?opt=SP&stnCode={station_code}"
NTES_LIVE_STATUS_URL = "https://enquiry.indianrail.gov.in/ntes/trainRunning?trainNo={train_no}&date={date}"

# erail API (supplementary)
ERAIL_BASE = "https://erail.in/rail/getTrains.aspx"
ERAIL_LIVE = "https://erail.in/rail/getTrainStatus.aspx?TrainNo={train_no}&Date={date}"

# Railsaarthi (backup live data)
RAILSAARTHI_BASE = "https://railsaarthi.in/train-running-status/{train_no}"

# ---------------------------------------------------------------------------
# KAFKA
# ---------------------------------------------------------------------------
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
KAFKA_TOPIC_LIVE = "rail.live.delays"
KAFKA_TOPIC_COMMANDS = "rail.ops.commands"
KAFKA_TOPIC_PREDICTIONS = "rail.ml.predictions"
KAFKA_GROUP_ID = "rail-gnn-consumer"
KAFKA_POLL_TIMEOUT_MS = 1000

# ---------------------------------------------------------------------------
# MODEL HYPERPARAMETERS
# ---------------------------------------------------------------------------
GNN_HIDDEN_DIM = 128
GNN_OUTPUT_DIM = 64
GNN_NUM_LAYERS = 2
GNN_DROPOUT = 0.2

# Feature vector size (must match feature_engineer.py output)
OBS_FEATURE_DIM = 48

# PPO
PPO_LR = 3e-4
PPO_GAMMA = 0.99
PPO_EPS_CLIP = 0.2
PPO_EPOCHS = 10
PPO_BATCH_SIZE = 64
PPO_TOTAL_TIMESTEPS = 1_000_000
PPO_ROLLOUT_STEPS = 2048
PPO_VALUE_COEF = 0.5
PPO_ENTROPY_COEF = 0.01
PPO_MAX_GRAD_NORM = 0.5
PPO_GAE_LAMBDA = 0.95

# Inference latency budget (ms)
MAX_INFERENCE_LATENCY_MS = 50

# ---------------------------------------------------------------------------
# CORRIDOR METADATA
# ---------------------------------------------------------------------------

@dataclass
class CorridorConfig:
    name: str
    code: str
    stations: List[str]          # ordered station codes
    key_junctions: List[str]     # junction station codes
    total_distance_km: float
    avg_speed_kmh: float
    typical_trains_per_day: int
    coordinates: Dict[str, Tuple[float, float]]  # stn_code -> (lat, lon)

CORRIDORS: Dict[str, CorridorConfig] = {
    "delhi_mumbai": CorridorConfig(
        name="Delhi–Mumbai Corridor",
        code="DLI-BCT",
        stations=[
            "NDLS", "MTJ", "AGC", "GWL", "JHS", "BPL", "ET",
            "KNW", "RTM", "VDA", "BRC", "ADI", "ST", "BVI", "CSTM",
        ],
        key_junctions=["AGC", "JHS", "BPL", "BRC", "ADI"],
        total_distance_km=1384,
        avg_speed_kmh=95,
        typical_trains_per_day=48,
        coordinates={
            "NDLS": (28.6424, 77.2196), "MTJ": (27.4924, 77.6737),
            "AGC": (27.1767, 78.0081), "GWL": (26.2265, 78.1756),
            "JHS": (25.4484, 78.5685), "BPL": (23.2599, 77.4126),
            "ET":  (22.7604, 76.7174), "KNW": (22.0667, 76.3500),
            "RTM": (23.3341, 75.0367), "VDA": (22.3003, 73.2072),
            "BRC": (22.3167, 73.1833), "ADI": (23.0225, 72.5714),
            "ST":  (21.1702, 72.8311), "BVI": (19.4551, 72.7860),
            "CSTM":(18.9398, 72.8354),
        },
    ),
    "delhi_howrah": CorridorConfig(
        name="Delhi–Howrah Corridor",
        code="NDLS-HWH",
        stations=[
            "NDLS", "CNB", "ALD", "MGS", "DDU", "ARA", "PNBE",
            "GAYA", "DHN", "ASN", "BWN", "HWH",
        ],
        key_junctions=["CNB", "ALD", "MGS", "PNBE", "DHN"],
        total_distance_km=1441,
        avg_speed_kmh=90,
        typical_trains_per_day=52,
        coordinates={
            "NDLS": (28.6424, 77.2196), "CNB": (26.4499, 80.3319),
            "ALD":  (25.4358, 81.8463), "MGS": (25.1547, 83.1235),
            "DDU":  (25.1422, 83.4425), "ARA": (25.5563, 84.6622),
            "PNBE": (25.6073, 85.1376), "GAYA": (24.7955, 84.9994),
            "DHN":  (23.7956, 86.4304), "ASN": (23.6780, 86.9720),
            "BWN":  (23.2324, 87.8615), "HWH": (22.5852, 88.3426),
        },
    ),
    "chennai_mumbai": CorridorConfig(
        name="Chennai–Mumbai Corridor",
        code="MAS-CSTM",
        stations=[
            "MAS", "AJJ", "RU", "KPD", "JTJ", "SA", "ED",
            "CBE", "PGT", "SRR", "CLT", "MAQ", "MAO", "CSTM",
        ],
        key_junctions=["AJJ", "JTJ", "CBE", "SRR", "MAO"],
        total_distance_km=1279,
        avg_speed_kmh=85,
        typical_trains_per_day=36,
        coordinates={
            "MAS":  (13.0827, 80.2707), "AJJ":  (13.2104, 79.6895),
            "RU":   (13.6293, 79.4177), "KPD":  (12.9281, 79.3161),
            "JTJ":  (12.5667, 78.5833), "SA":   (11.6643, 78.1460),
            "ED":   (11.3512, 77.7172), "CBE":  (11.0168, 76.9558),
            "PGT":  (10.7867, 76.6548), "SRR":  (11.2588, 75.8370),
            "CLT":  (11.2514, 75.7803), "MAQ":  (12.8698, 74.8420),
            "MAO":  (15.0057, 74.0147), "CSTM": (18.9398, 72.8354),
        },
    ),
}

# All unique station codes across all corridors
ALL_STATION_CODES: List[str] = list({
    s for c in CORRIDORS.values() for s in c.stations
})

# ---------------------------------------------------------------------------
# TRAIN SCHEDULES (Trains at a Glance 2026 — representative subset)
# ---------------------------------------------------------------------------

@dataclass
class TrainConfig:
    number: str
    name: str
    corridor: str
    origin: str
    destination: str
    departure: str   # HH:MM
    arrival: str     # HH:MM
    days: List[str]  # Mon Tue Wed Thu Fri Sat Sun / Daily

TRAINS: Dict[str, TrainConfig] = {
    # Delhi–Mumbai
    "12951": TrainConfig("12951", "Mumbai Rajdhani", "delhi_mumbai", "NDLS", "CSTM", "16:55", "08:35", ["Daily"]),
    "12953": TrainConfig("12953", "August Kranti Rajdhani", "delhi_mumbai", "NDLS", "CSTM", "17:40", "10:22", ["Daily"]),
    "12909": TrainConfig("12909", "Garib Rath", "delhi_mumbai", "NDLS", "CSTM", "15:30", "07:35", ["Mon","Wed","Fri","Sun"]),
    "12137": TrainConfig("12137", "Punjab Mail", "delhi_mumbai", "CSTM", "NDLS", "19:05", "14:45", ["Daily"]),
    "19019": TrainConfig("19019", "Dehradun Express", "delhi_mumbai", "BDTS", "DDN", "23:00", "22:45", ["Daily"]),

    # Delhi–Howrah
    "12301": TrainConfig("12301", "Howrah Rajdhani", "delhi_howrah", "NDLS", "HWH", "17:00", "09:55", ["Daily"]),
    "12303": TrainConfig("12303", "Poorva Express", "delhi_howrah", "NDLS", "HWH", "08:00", "06:45", ["Mon","Wed","Sat"]),
    "12305": TrainConfig("12305", "Rajdhani Via Patna", "delhi_howrah", "NDLS", "HWH", "22:30", "19:40", ["Daily"]),
    "13005": TrainConfig("13005", "Amritsar HWH Express", "delhi_howrah", "ASR", "HWH", "11:25", "13:30", ["Daily"]),
    "12381": TrainConfig("12381", "Poorabiya Express", "delhi_howrah", "NDLS", "HWH", "19:55", "18:55", ["Daily"]),

    # Chennai–Mumbai
    "11041": TrainConfig("11041", "Mumbai Express", "chennai_mumbai", "MAS", "CSTM", "12:50", "23:00", ["Daily"]),
    "16331": TrainConfig("16331", "Trivandrum Express", "chennai_mumbai", "TVC", "CSTM", "13:50", "06:20", ["Mon","Thu"]),
    "16613": TrainConfig("16613", "Coimbatore Express", "chennai_mumbai", "CBE", "CSTM", "20:15", "09:55", ["Daily"]),
    "12621": TrainConfig("12621", "Tamil Nadu Express", "chennai_mumbai", "MAS", "NDLS", "22:00", "07:40", ["Daily"]),
    "12163": TrainConfig("12163", "Chennai Dadar Express", "chennai_mumbai", "MAS", "DR", "23:45", "23:15", ["Tue","Fri"]),
}

# ---------------------------------------------------------------------------
# DELAY SIMULATION PARAMETERS
# ---------------------------------------------------------------------------
DELAY_MEAN_MIN = 0.0          # minutes
DELAY_STD_MIN = 12.0          # Gaussian std
DELAY_MAX_MIN = 180.0         # cap
CASCADE_PROPAGATION_HOURS = 4
CASCADE_DAMPENING = 0.65      # each hop multiplies delay by this factor
JUNCTION_CASCADE_MULTIPLIER = 1.3  # junctions amplify cascades

# ---------------------------------------------------------------------------
# REWARD SHAPING
# ---------------------------------------------------------------------------
REWARD_TIME_SAVED_PER_MIN = 1.0
REWARD_CASCADE_PREVENTED = 5.0
REWARD_ON_TIME_BONUS = 2.0
PENALTY_CANCELLED_TRAIN = -10.0
PENALTY_SAFETY_VIOLATION = -50.0

# ---------------------------------------------------------------------------
# NTES SCRAPER CONFIG
# ---------------------------------------------------------------------------
SCRAPER_REQUEST_TIMEOUT = 10   # seconds
SCRAPER_RETRY_ATTEMPTS = 3
SCRAPER_RETRY_BACKOFF = 2.0    # seconds
SCRAPER_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
]
SCRAPER_RATE_LIMIT_DELAY = 1.5  # seconds between requests
SCRAPER_SESSION_ROTATE_EVERY = 50  # rotate session after N requests

# ---------------------------------------------------------------------------
# LIVE FEED CONFIG
# ---------------------------------------------------------------------------
LIVE_FEED_INTERVAL_SEC = 2      # erail polling
SIMULATED_FEED_INTERVAL_SEC = 900  # 15 minutes
NTES_SCRAPE_INTERVAL_SEC = 30   # NTES scraping cadence

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"