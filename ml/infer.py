"""
RailDrishti — infer.py
Accepts stations_100.json → runs GNN → returns train recommendations.

Usage:
    python infer.py
    from infer import predict; result = predict(stations_data)
"""

import json
import math
import torch
from model.gnn_model import RailGNN


# ── Constants ──────────────────────────────────────────────────────────────────
EDGE_DISTANCE_THRESHOLD_KM = 500   # connect stations within 500 km
MAX_TRAINS = 400.0                 # for normalisation
LAT_MIN, LAT_MAX = 8.0, 37.0      # India bounding box
LNG_MIN, LNG_MAX = 68.0, 97.0


# ── Geo helper ─────────────────────────────────────────────────────────────────
def _haversine_km(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * \
        math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))


# ── Input parsing ──────────────────────────────────────────────────────────────
def _parse_stations(stations_data):
    """
    Accepts:
      - dict with key "stations_100" (full JSON file)
      - plain list of station dicts
    Returns normalised node_features tensor + edge_index tensor.
    """
    if isinstance(stations_data, dict):
        stations = stations_data.get("stations_100", [])
    elif isinstance(stations_data, list):
        stations = stations_data
    else:
        raise ValueError("stations_data must be dict (full JSON) or list of station dicts")

    if not stations:
        raise ValueError("No station data found")

    # Build node feature matrix: [congestion, trains_norm, lat_norm, lng_norm]
    features = []
    for s in stations:
        congestion  = float(s.get("congestion", 0.5))
        trains_norm = float(s.get("trains", 50)) / MAX_TRAINS
        lat_norm    = (float(s.get("lat", 23.0)) - LAT_MIN) / (LAT_MAX - LAT_MIN)
        lng_norm    = (float(s.get("lng", 78.0)) - LNG_MIN) / (LNG_MAX - LNG_MIN)
        # clamp to [0,1]
        features.append([
            max(0.0, min(1.0, congestion)),
            max(0.0, min(1.0, trains_norm)),
            max(0.0, min(1.0, lat_norm)),
            max(0.0, min(1.0, lng_norm)),
        ])

    # Build edge_index from geographic proximity
    src_nodes, dst_nodes = [], []
    n = len(stations)
    for i in range(n):
        for j in range(i + 1, n):
            dist = _haversine_km(
                stations[i].get("lat", 0), stations[i].get("lng", 0),
                stations[j].get("lat", 0), stations[j].get("lng", 0)
            )
            if dist <= EDGE_DISTANCE_THRESHOLD_KM:
                src_nodes += [i, j]
                dst_nodes += [j, i]

    x = torch.tensor(features, dtype=torch.float)
    if src_nodes:
        edge_index = torch.tensor([src_nodes, dst_nodes], dtype=torch.long)
    else:
        edge_index = torch.zeros((2, 0), dtype=torch.long)

    return x, edge_index, stations


# ── Main predict function ──────────────────────────────────────────────────────
def predict(stations_data=None):
    """
    Parameters
    ----------
    stations_data : dict | list | None
        Full stations_100.json dict, or list of station dicts.
        Defaults to loading data/stations_100.json if None.

    Returns
    -------
    dict
        {
          "total_stations": int,
          "total_trains": int,
          "recommendations": [
            {
              "train_id": "TN001",
              "station": "Bhopal Jn",
              "station_id": 0,
              "congestion_score": 0.734,
              "action": "slow_down" | "hold" | "maintain",
              "recommended_speed": 45 | 20 | 60,
              "status": "critical" | "at_risk" | "on_time"
            },
            ...
          ],
          "model": "RailDrishti GNN v1"
        }
    """
    # Default: load from file
    if stations_data is None:
        import os
        data_path = os.path.join(os.path.dirname(__file__), "data", "stations_100.json")
        with open(data_path, "r") as f:
            stations_data = json.load(f)

    x, edge_index, stations = _parse_stations(stations_data)

    # Load model (4 input features)
    model = RailGNN(in_feat=4, hid_dim=32, out_dim=1)
    model.eval()

    # Try loading saved weights if available
    import os
    weights_path = os.path.join(os.path.dirname(__file__), "model", "raildrishti_gnn.pt")
    if os.path.exists(weights_path):
        model.load_state_dict(torch.load(weights_path, map_location="cpu"))

    with torch.no_grad():
        output = model(x, edge_index)   # shape: (N, 1)

    scores = output.squeeze(1).tolist()
    if isinstance(scores, float):
        scores = [scores]

    # Normalise scores to [0, 1] using sigmoid
    def sigmoid(v):
        return 1.0 / (1.0 + math.exp(-v))

    recommendations = []
    total_trains = 0

    for i, raw_score in enumerate(scores):
        s = stations[i]
        score = sigmoid(raw_score)

        # Blend model score with actual congestion for realism
        blended = 0.6 * score + 0.4 * float(s.get("congestion", 0.5))
        blended = round(blended, 3)

        # Thresholds
        if blended > 0.75:
            action = "slow_down"
            speed  = 45
            status = "critical"
        elif blended > 0.50:
            action = "hold"
            speed  = 30
            status = "at_risk"
        else:
            action = "maintain"
            speed  = 60
            status = "on_time"

        num_trains = int(s.get("trains", 1))
        total_trains += num_trains

        # Generate one recommendation entry per station (represents lead train)
        recommendations.append({
            "train_id":         f"TN{str(i+1).zfill(3)}",
            "station":          s.get("name", f"Station{i}"),
            "station_id":       s.get("id", i),
            "congestion_score": blended,
            "action":           action,
            "recommended_speed":speed,
            "status":           status,
            "trains_at_station":num_trains
        })

    return {
        "total_stations":  len(recommendations),
        "total_trains":    total_trains,
        "recommendations": recommendations,
        "model":           "RailDrishti GNN v1"
    }


# ── CLI test ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    result = predict()
    print(json.dumps(result, indent=2))
    critical = [r for r in result["recommendations"] if r["status"] == "critical"]
    at_risk  = [r for r in result["recommendations"] if r["status"] == "at_risk"]
    print(f"\n✅ infer.py working!")
    print(f"   Stations: {result['total_stations']} | Trains: {result['total_trains']}")
    print(f"   Critical: {len(critical)} | At Risk: {len(at_risk)}")