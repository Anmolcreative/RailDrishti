from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import httpx

router = APIRouter()

# ============================================================
# REAL STATION DATA — 3 LIVE CORRIDORS
# Source: Anmol's raildish_stations_json (ML Module)
# Feed interval: 2 seconds per station
# ============================================================

CORRIDORS = {
    "BPL-ET": {
        "name": "Bhopal Junction → Itarsi Junction",
        "zone": "WCR",
        "distance_km": 89,
        "stations": [
            {"code": "BPL",  "name": "BHOPAL JN",    "lat": 23.266884, "lng": 77.413143, "congestion": 0.85, "trains_daily": 80,  "platforms": 5, "is_junction": True},
            {"code": "BNI",  "name": "BUDNI",         "lat": 22.787114, "lng": 77.681283, "congestion": 0.45, "trains_daily": 38,  "platforms": 2, "is_junction": False},
            {"code": "PRKD", "name": "POWERKHEDA",    "lat": 22.673479, "lng": 77.747363, "congestion": 0.70, "trains_daily": 52,  "platforms": 2, "is_junction": False},
            {"code": "HBD",  "name": "HOSHANGABAD",   "lat": 22.752740, "lng": 77.715594, "congestion": 0.65, "trains_daily": 55,  "platforms": 3, "is_junction": False},
            {"code": "ET",   "name": "ITARSI JN",     "lat": 22.608258, "lng": 77.767128, "congestion": 0.90, "trains_daily": 110, "platforms": 7, "is_junction": True},
        ]
    },
    "NDLS-MGS": {
        "name": "New Delhi → Mughal Sarai Junction",
        "zone": "NR/NCR/NER",
        "distance_km": 1015,
        "stations": [
            {"code": "NDLS", "name": "NEW DELHI",              "lat": 28.642314, "lng": 77.220004, "congestion": 0.99, "trains_daily": 350, "platforms": 16, "is_junction": False},
            {"code": "HNZM", "name": "DELHI HAZRAT NIZAMUDDIN","lat": 28.587010, "lng": 77.253929, "congestion": 0.92, "trains_daily": 180, "platforms": 8,  "is_junction": False},
            {"code": "FDB",  "name": "FARIDABAD",              "lat": 28.411473, "lng": 77.307348, "congestion": 0.65, "trains_daily": 60,  "platforms": 4,  "is_junction": False},
            {"code": "PWL",  "name": "PALWAL",                 "lat": 28.151841, "lng": 77.342232, "congestion": 0.48, "trains_daily": 38,  "platforms": 3,  "is_junction": False},
            {"code": "MTJ",  "name": "MATHURA JN",             "lat": 27.480145, "lng": 77.673117, "congestion": 0.75, "trains_daily": 78,  "platforms": 5,  "is_junction": True},
            {"code": "AGC",  "name": "AGRA CANTT",             "lat": 27.157992, "lng": 77.990153, "congestion": 0.80, "trains_daily": 90,  "platforms": 6,  "is_junction": False},
            {"code": "TDL",  "name": "TUNDLA JN",              "lat": 27.207747, "lng": 78.233285, "congestion": 0.60, "trains_daily": 52,  "platforms": 4,  "is_junction": True},
            {"code": "ETW",  "name": "ETAWAH",                 "lat": 26.785970, "lng": 79.021502, "congestion": 0.55, "trains_daily": 44,  "platforms": 3,  "is_junction": False},
            {"code": "CNB",  "name": "KANPUR CENTRAL",         "lat": 26.454240, "lng": 80.350966, "congestion": 0.95, "trains_daily": 280, "platforms": 10, "is_junction": True},
            {"code": "ALD",  "name": "ALLAHABAD JN",           "lat": 25.446241, "lng": 81.828816, "congestion": 0.88, "trains_daily": 120, "platforms": 8,  "is_junction": True},
            {"code": "MZP",  "name": "MIRZAPUR",               "lat": 25.134350, "lng": 82.569869, "congestion": 0.52, "trains_daily": 42,  "platforms": 3,  "is_junction": False},
            {"code": "BSB",  "name": "VARANASI JN",            "lat": 25.327281, "lng": 82.986468, "congestion": 0.87, "trains_daily": 115, "platforms": 9,  "is_junction": True},
            {"code": "MGS",  "name": "MUGHAL SARAI JN",        "lat": 25.278149, "lng": 83.119250, "congestion": 0.80, "trains_daily": 90,  "platforms": 8,  "is_junction": True},
        ]
    },
    "HWH-DHN": {
        "name": "Howrah Junction → Dhanbad Junction",
        "zone": "ER/SER",
        "distance_km": 263,
        "stations": [
            {"code": "HWH", "name": "HOWRAH JN",      "lat": 22.584078, "lng": 88.340999, "congestion": 0.98, "trains_daily": 350, "platforms": 23, "is_junction": True},
            {"code": "BWN", "name": "BARDDHAMAN JN",  "lat": 23.249718, "lng": 87.870281, "congestion": 0.65, "trains_daily": 60,  "platforms": 5,  "is_junction": True},
            {"code": "ASN", "name": "ASANSOL JN",     "lat": 23.691441, "lng": 86.975152, "congestion": 0.72, "trains_daily": 70,  "platforms": 6,  "is_junction": True},
            {"code": "DHN", "name": "DHANBAD JN",     "lat": 23.790966, "lng": 86.428956, "congestion": 0.75, "trains_daily": 78,  "platforms": 6,  "is_junction": True},
        ]
    }
}

# ============================================================
# REAL TRAIN DATA — ALL 3 CORRIDORS
# Source: Trains at a Glance 2026 + IITKGP IR Dataset
# ============================================================

TRAINS = [
    # ── BPL-ET CORRIDOR ──────────────────────────────────────
    {
        "id": "11078", "name": "GOA EXPRESS",       "corridor": "BPL-ET",
        "lat": 23.2599,  "lng": 77.4126, "speed": 72,  "delay": 12,
        "departs": "01:30", "arrives": "02:55",
        "from": "Hazrat Nizamuddin", "to": "Madgaon",
        "next_station": "BNI", "status": "delayed",
        "train_type": "MAIL_EXPRESS", "priority": 2
    },
    {
        "id": "12627", "name": "KARNATAKA EXPRESS",  "corridor": "BPL-ET",
        "lat": 22.9800,  "lng": 77.5500, "speed": 85,  "delay": 3,
        "departs": "00:45", "arrives": "02:10",
        "from": "New Delhi", "to": "KSR Bengaluru",
        "next_station": "BNI", "status": "on_time",
        "train_type": "MAIL_EXPRESS", "priority": 2
    },
    {
        "id": "12721", "name": "NIZAMUDDIN EXPRESS", "corridor": "BPL-ET",
        "lat": 23.1200,  "lng": 77.4800, "speed": 60,  "delay": 8,
        "departs": "01:05", "arrives": "02:30",
        "from": "Hyderabad", "to": "Hazrat Nizamuddin",
        "next_station": "BNI", "status": "at_risk",
        "train_type": "MAIL_EXPRESS", "priority": 2
    },
    {
        "id": "12533", "name": "PUSHPAK EXPRESS",    "corridor": "BPL-ET",
        "lat": 22.8500,  "lng": 77.6200, "speed": 78,  "delay": 0,
        "departs": "02:15", "arrives": "03:35",
        "from": "Mumbai LTT", "to": "Lucknow",
        "next_station": "PRKD", "status": "on_time",
        "train_type": "MAIL_EXPRESS", "priority": 2
    },
    {
        "id": "12161", "name": "LASHKAR EXPRESS",    "corridor": "BPL-ET",
        "lat": 23.0500,  "lng": 77.5100, "speed": 55,  "delay": 15,
        "departs": "03:00", "arrives": "04:20",
        "from": "Gwalior", "to": "Mumbai CSMT",
        "next_station": "BNI", "status": "delayed",
        "train_type": "MAIL_EXPRESS", "priority": 2
    },
    {
        "id": "12137", "name": "PUNJAB MAIL",        "corridor": "BPL-ET",
        "lat": 22.7800,  "lng": 77.6800, "speed": 90,  "delay": 9,
        "departs": "04:10", "arrives": "05:25",
        "from": "Firozpur", "to": "Mumbai CSMT",
        "next_station": "ET", "status": "at_risk",
        "train_type": "MAIL_EXPRESS", "priority": 2
    },
    {
        "id": "22691", "name": "RAJDHANI EXPRESS",   "corridor": "BPL-ET",
        "lat": 23.1800,  "lng": 77.4500, "speed": 110, "delay": 0,
        "departs": "05:30", "arrives": "06:40",
        "from": "KSR Bengaluru", "to": "New Delhi",
        "next_station": "BNI", "status": "on_time",
        "train_type": "RAJDHANI", "priority": 3
    },
    {
        "id": "12001", "name": "SHATABDI EXPRESS",   "corridor": "BPL-ET",
        "lat": 22.9200,  "lng": 77.5800, "speed": 100, "delay": 2,
        "departs": "06:15", "arrives": "07:20",
        "from": "Bhopal", "to": "New Delhi",
        "next_station": "PRKD", "status": "on_time",
        "train_type": "SHATABDI", "priority": 3
    },

    # ── NDLS-MGS CORRIDOR ────────────────────────────────────
    {
        "id": "12301", "name": "HOWRAH RAJDHANI",    "corridor": "NDLS-MGS",
        "lat": 28.6423,  "lng": 77.2200, "speed": 130, "delay": 0,
        "departs": "16:55", "arrives": "09:55",
        "from": "New Delhi", "to": "Howrah",
        "next_station": "HNZM", "status": "on_time",
        "train_type": "RAJDHANI", "priority": 3
    },
    {
        "id": "12381", "name": "POORVA EXPRESS",     "corridor": "NDLS-MGS",
        "lat": 27.4801,  "lng": 77.6731, "speed": 85,  "delay": 18,
        "departs": "08:30", "arrives": "05:00",
        "from": "New Delhi", "to": "Howrah",
        "next_station": "AGC", "status": "delayed",
        "train_type": "MAIL_EXPRESS", "priority": 2
    },
    {
        "id": "13005", "name": "AMRITSAR MAIL",      "corridor": "NDLS-MGS",
        "lat": 26.4542,  "lng": 80.3510, "speed": 75,  "delay": 22,
        "departs": "22:15", "arrives": "22:35",
        "from": "Amritsar", "to": "Howrah",
        "next_station": "ALD", "status": "delayed",
        "train_type": "MAIL_EXPRESS", "priority": 2
    },
    {
        "id": "12275", "name": "DURONTO EXPRESS",    "corridor": "NDLS-MGS",
        "lat": 25.4462,  "lng": 81.8288, "speed": 120, "delay": 5,
        "departs": "06:00", "arrives": "17:25",
        "from": "New Delhi", "to": "Howrah",
        "next_station": "BSB", "status": "on_time",
        "train_type": "RAJDHANI", "priority": 3
    },
    {
        "id": "14016", "name": "SADHBHAVNA EXP",     "corridor": "NDLS-MGS",
        "lat": 27.2077,  "lng": 78.2333, "speed": 70,  "delay": 11,
        "departs": "11:45", "arrives": "08:10",
        "from": "Firozpur", "to": "Patna",
        "next_station": "ETW", "status": "at_risk",
        "train_type": "MAIL_EXPRESS", "priority": 2
    },
    {
        "id": "12393", "name": "SAMPOORNA KRANTI",   "corridor": "NDLS-MGS",
        "lat": 25.2781,  "lng": 83.1193, "speed": 110, "delay": 3,
        "departs": "19:45", "arrives": "10:30",
        "from": "New Delhi", "to": "Rajendra Nagar",
        "next_station": "MGS", "status": "on_time",
        "train_type": "MAIL_EXPRESS", "priority": 2
    },

    # ── HWH-DHN CORRIDOR ─────────────────────────────────────
    {
        "id": "12259", "name": "SEALDAH DURONTO",    "corridor": "HWH-DHN",
        "lat": 22.5841,  "lng": 88.3410, "speed": 110, "delay": 0,
        "departs": "08:45", "arrives": "12:15",
        "from": "Sealdah", "to": "New Delhi",
        "next_station": "BWN", "status": "on_time",
        "train_type": "RAJDHANI", "priority": 3
    },
    {
        "id": "12019", "name": "HOWRAH SHATABDI",    "corridor": "HWH-DHN",
        "lat": 23.2497,  "lng": 87.8703, "speed": 100, "delay": 4,
        "departs": "05:55", "arrives": "10:00",
        "from": "Howrah", "to": "Ranchi",
        "next_station": "ASN", "status": "on_time",
        "train_type": "SHATABDI", "priority": 3
    },
    {
        "id": "13351", "name": "DHANBAD EXPRESS",    "corridor": "HWH-DHN",
        "lat": 23.6914,  "lng": 86.9752, "speed": 65,  "delay": 14,
        "departs": "14:20", "arrives": "18:45",
        "from": "Howrah", "to": "Dhanbad",
        "next_station": "DHN", "status": "delayed",
        "train_type": "MAIL_EXPRESS", "priority": 2
    },
    {
        "id": "12360", "name": "PATNA EXPRESS",      "corridor": "HWH-DHN",
        "lat": 23.7910,  "lng": 86.4290, "speed": 80,  "delay": 7,
        "departs": "23:00", "arrives": "08:30",
        "from": "Kolkata", "to": "Patna",
        "next_station": "DHN", "status": "at_risk",
        "train_type": "MAIL_EXPRESS", "priority": 2
    },
]


# ============================================================
# HELPER — derive status label from delay
# ============================================================
def compute_status(delay: int) -> str:
    if delay == 0:
        return "on_time"
    elif delay <= 10:
        return "at_risk"
    else:
        return "delayed"


# ============================================================
# ROUTES
# ============================================================

@router.get("/trains")
def get_all_trains():
    """Return all trains across 3 live corridors."""
    return {
        "total": len(TRAINS),
        "corridors": list(CORRIDORS.keys()),
        "trains": TRAINS
    }


@router.get("/trains/{corridor_id}")
def get_trains_by_corridor(corridor_id: str):
    """Return trains for a specific corridor. E.g. /trains/BPL-ET"""
    corridor_id = corridor_id.upper()
    if corridor_id not in CORRIDORS:
        return {"error": f"Corridor '{corridor_id}' not found. Valid: {list(CORRIDORS.keys())}"}

    corridor_trains = [t for t in TRAINS if t["corridor"] == corridor_id]
    return {
        "corridor": corridor_id,
        "info": CORRIDORS[corridor_id],
        "total_trains": len(corridor_trains),
        "trains": corridor_trains
    }


@router.get("/stations")
def get_all_stations():
    """Return all stations across 3 live corridors."""
    all_stations = []
    for corridor_id, corridor_data in CORRIDORS.items():
        for station in corridor_data["stations"]:
            all_stations.append({**station, "corridor": corridor_id})
    return {
        "total": len(all_stations),
        "stations": all_stations
    }


@router.get("/stations/{corridor_id}")
def get_stations_by_corridor(corridor_id: str):
    """Return stations for a specific corridor. E.g. /stations/NDLS-MGS"""
    corridor_id = corridor_id.upper()
    if corridor_id not in CORRIDORS:
        return {"error": f"Corridor '{corridor_id}' not found. Valid: {list(CORRIDORS.keys())}"}

    return {
        "corridor": corridor_id,
        "info": CORRIDORS[corridor_id],
        "stations": CORRIDORS[corridor_id]["stations"]
    }


@router.get("/corridors")
def get_corridors():
    """Return summary of all 3 live corridors."""
    summary = []
    for corridor_id, data in CORRIDORS.items():
        trains_in_corridor = [t for t in TRAINS if t["corridor"] == corridor_id]
        delayed = [t for t in trains_in_corridor if t["status"] == "delayed"]
        at_risk = [t for t in trains_in_corridor if t["status"] == "at_risk"]

        # highest congestion station in this corridor
        max_congestion_station = max(
            data["stations"], key=lambda s: s["congestion"]
        )

        summary.append({
            "corridor_id": corridor_id,
            "name": data["name"],
            "zone": data["zone"],
            "distance_km": data["distance_km"],
            "total_stations": len(data["stations"]),
            "total_trains": len(trains_in_corridor),
            "delayed_trains": len(delayed),
            "at_risk_trains": len(at_risk),
            "most_congested_station": max_congestion_station["name"],
            "max_congestion_score": max_congestion_station["congestion"],
        })
    return {"corridors": summary}


class OptimizeRequest(BaseModel):
    train_id: Optional[str] = None
    corridor_id: Optional[str] = None


@router.post("/optimize")
async def optimize(request: OptimizeRequest):
    """
    Calls Anmol's ML predict() for AI recommendations.
    Accepts optional train_id or corridor_id to scope the optimization.
    TODO: Replace mock response with real infer.py call once Anmol's module is ready.
    """
    # Filter trains to optimize
    if request.train_id:
        target_trains = [t for t in TRAINS if t["id"] == request.train_id]
    elif request.corridor_id:
        target_trains = [t for t in TRAINS if t["corridor"] == request.corridor_id.upper()]
    else:
        target_trains = TRAINS  # optimize all

    # TODO: replace this block with -> from ml.infer import predict; results = predict(target_trains)
    mock_recommendations = []
    for train in target_trains:
        if train["status"] == "delayed":
            action = "SPEED_UP"
            recommended_speed = min(train["speed"] + 15, 120)
            hold_duration = 0
            minutes_saved = round(train["delay"] * 0.4, 1)
        elif train["status"] == "at_risk":
            action = "SLOW_DOWN"
            recommended_speed = train["speed"] - 10
            hold_duration = 2
            minutes_saved = round(train["delay"] * 0.2, 1)
        else:
            action = "ON_TRACK"
            recommended_speed = train["speed"]
            hold_duration = 0
            minutes_saved = 0.0

        mock_recommendations.append({
            "id": train["id"],
            "name": train["name"],
            "corridor": train["corridor"],
            "current_status": train["status"],
            "current_delay_min": train["delay"],
            "action": action,
            "recommended_speed_kmh": recommended_speed,
            "hold_duration_min": hold_duration,
            "minutes_saved_if_action": minutes_saved,
            "confidence": 0.87,
            "source": "mock — plug in Anmol infer.py"
        })

    total_delay = sum(t["delay"] for t in target_trains)
    total_saved = sum(r["minutes_saved_if_action"] for r in mock_recommendations)

    return {
        "status": "optimization_complete",
        "scope": request.corridor_id or request.train_id or "all_corridors",
        "trains_analyzed": len(target_trains),
        "total_delay_before_min": total_delay,
        "estimated_minutes_saved": round(total_saved, 1),
        "recommendations": mock_recommendations
    }