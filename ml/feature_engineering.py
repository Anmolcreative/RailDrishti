"""RailDrishti ML feature engineering.
Builds LightGBM-ready tabular features from synthetic delay data.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
RAW_DATA = DATA_DIR / "synthetic_delays.csv"

CORRIDOR_MAP = {
    "ET": "BPL-ET",
    "BPL": "BPL-ET",
    "NDLS": "NDLS-MGS",
    "MGS": "NDLS-MGS",
    "HWH": "HWH-DHN",
    "DHN": "HWH-DHN",
}

ZONE_MAP = {
    "ET": "Central",
    "BPL": "Central",
    "NDLS": "Northern",
    "MGS": "Northern",
    "HWH": "Eastern",
    "DHN": "Eastern",
}

VIP_TRAINS = {22691, 12001, 12301, 12311, 12259, 12721}

ACTION_ORDER = [
    "APPROVE",
    "HOLD",
    "REROUTE",
    "PRIORITY_OVERRIDE",
]

CATEGORICAL_COLUMNS = [
    "station_code",
    "corridor_id",
    "zone_id",
    "train_type",
    "weather_state",
]

FEATURE_COLUMNS = [
    "delay_minutes",
    "corridor_congestion_score",
    "trains_ahead_count",
    "speed_deviation_pct",
    "hour_sin",
    "hour_cos",
    "day_of_week_sin",
    "day_of_week_cos",
    "weather_severity",
    "platform_free",
    "headway_min",
    "priority",
    "is_vip_train",
    "historical_avg_delay_min",
    "conflict_flag",
    "station_code",
    "corridor_id",
    "zone_id",
    "train_type",
    "weather_state",
]

TRAIN_TYPE_MAP = {
    3: "RAJDHANI",
    2: "MAIL_EXPRESS",
    1: "PASSENGER",
}

EXPECTED_SPEED = {
    "RAJDHANI": 90.0,
    "MAIL_EXPRESS": 75.0,
    "PASSENGER": 60.0,
    "DURONTO": 85.0,
    "SHATABDI": 85.0,
    "OTHER": 70.0,
}


def load_raw_data(path: Path = None) -> pd.DataFrame:
    if path is None:
        path = RAW_DATA
    return pd.read_csv(path)


def map_train_type(priority: int, train_no: int) -> str:
    if priority == 3:
        return "RAJDHANI"
    if priority == 2:
        return "MAIL_EXPRESS"
    if priority == 1:
        return "PASSENGER"
    if train_no in VIP_TRAINS:
        return "RAJDHANI"
    return "OTHER"


def map_weather_state(severity: float) -> str:
    if severity < 0.1:
        return "CLEAR"
    if severity < 0.3:
        return "CLOUDS"
    if severity < 0.6:
        return "RAIN"
    if severity < 0.8:
        return "FOG"
    return "STORM"


def compute_speed_deviation(row: pd.Series) -> float:
    expected = EXPECTED_SPEED.get(row["train_type"], EXPECTED_SPEED["OTHER"])
    return (row["speed_kmh"] - expected) / expected


def compute_target_action(row: pd.Series) -> str:
    if row["is_vip_train"] and row["delay_minutes"] > 0 and row["corridor_congestion_score"] > 0.6:
        return "PRIORITY_OVERRIDE"
    if row["conflict_flag"] or row["corridor_congestion_score"] > 0.6:
        return "REROUTE"
    if 5 <= row["delay_minutes"] <= 15 or 0.4 <= row["congestion_score"] <= 0.6:
        return "HOLD"
    return "APPROVE"


def build_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    data = df.copy()
    data["corridor_id"] = data["station_code"].map(CORRIDOR_MAP).fillna("UNKNOWN")
    data["zone_id"] = data["station_code"].map(ZONE_MAP).fillna("UNKNOWN")
    data["train_type"] = data.apply(lambda row: map_train_type(int(row["priority"]), int(row["train_no"])), axis=1)
    data["weather_state"] = data["weather_severity"].apply(map_weather_state)
    data["is_vip_train"] = data["train_no"].astype(int).isin(VIP_TRAINS) | (data["priority"] == 3)

    data["corridor_congestion_score"] = (
        data["congestion_score"]
        + 0.08 * (data["delay_minutes"] > 10).astype(float)
        + 0.12 * (data["headway_min"] < 10).astype(float)
    )
    data["corridor_congestion_score"] = data["corridor_congestion_score"].clip(0.0, 1.0)

    data["trains_ahead_count"] = np.clip((30.0 / (data["headway_min"] + 1.0)).round().astype(int), 1, 8)
    data["speed_deviation_pct"] = data.apply(compute_speed_deviation, axis=1)
    data["historical_avg_delay_min"] = data.groupby("train_no")["delay_minutes"].transform("mean")
    data["conflict_flag"] = (
        (data["delay_minutes"] > 15)
        | (data["congestion_score"] > 0.75)
        | (data["headway_min"] < 8)
    )

    data["hour_sin"] = np.sin(2 * np.pi * (data["hour_of_day"] % 24) / 24.0)
    data["hour_cos"] = np.cos(2 * np.pi * (data["hour_of_day"] % 24) / 24.0)
    data["day_of_week"] = (data["train_no"].astype(int) % 7).astype(int)
    data["day_of_week_sin"] = np.sin(2 * np.pi * data["day_of_week"] / 7.0)
    data["day_of_week_cos"] = np.cos(2 * np.pi * data["day_of_week"] / 7.0)

    data["action"] = data.apply(compute_target_action, axis=1)

    features = data[FEATURE_COLUMNS].copy()
    for col in CATEGORICAL_COLUMNS:
        features[col] = features[col].astype("category")

    target = data["action"].astype("category")
    return features, target


def save_feature_schema(path: Path) -> None:
    schema = {
        "feature_columns": FEATURE_COLUMNS,
        "categorical_columns": CATEGORICAL_COLUMNS,
        "action_order": ACTION_ORDER,
    }
    path.write_text(json.dumps(schema, indent=2))


def load_feature_schema(path: Path) -> Dict[str, List[str]]:
    return json.loads(Path(path).read_text())


def build_inference_features(payload: Dict) -> pd.DataFrame:
    df = pd.DataFrame([payload])
    df["station_code"] = df["station_code"].astype(str)
    df["corridor_id"] = df["station_code"].map(CORRIDOR_MAP).fillna("UNKNOWN")
    df["zone_id"] = df["station_code"].map(ZONE_MAP).fillna("UNKNOWN")
    df["train_type"] = df.apply(lambda row: map_train_type(int(row["priority"]), int(row["train_no"])), axis=1)
    df["weather_state"] = df["weather_severity"].apply(map_weather_state)
    df["is_vip_train"] = df["train_no"].astype(int).isin(VIP_TRAINS) | (df["priority"] == 3)
    df["corridor_congestion_score"] = (
        df["congestion_score"]
        + 0.08 * (df["delay_minutes"] > 10).astype(float)
        + 0.12 * (df["headway_min"] < 10).astype(float)
    ).clip(0.0, 1.0)
    df["trains_ahead_count"] = np.clip((30.0 / (df["headway_min"] + 1.0)).round().astype(int), 1, 8)
    df["speed_deviation_pct"] = df.apply(compute_speed_deviation, axis=1)
    df["historical_avg_delay_min"] = df["delay_minutes"]
    df["conflict_flag"] = (
        (df["delay_minutes"] > 15)
        | (df["congestion_score"] > 0.75)
        | (df["headway_min"] < 8)
    )
    df["hour_sin"] = np.sin(2 * np.pi * (df["hour_of_day"] % 24) / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * (df["hour_of_day"] % 24) / 24.0)
    df["day_of_week"] = (df["train_no"].astype(int) % 7).astype(int)
    df["day_of_week_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7.0)
    df["day_of_week_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7.0)

    features = df[FEATURE_COLUMNS].copy()
    for col in CATEGORICAL_COLUMNS:
        features[col] = features[col].astype("category")
    return features
