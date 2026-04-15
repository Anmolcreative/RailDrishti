"""
RailDrishti — train_gnn.py
Train RailGNN on synthetic station-delay snapshots using ml/data/synthetic_delays.csv.
Run: python train_gnn.py
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

from model.gnn_model import RailGNN


STATION_CODE_MAP = {
    "ET": "Itarsi Jn",
    "BPL": "Bhopal Jn",
    "NDLS": "New Delhi",
    "MGS": "Mughalsarai Jn",
    "HWH": "Howrah Jn",
    "DHN": "Dhanbad Jn",
}

EDGE_DISTANCE_THRESHOLD_KM = 1200
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "model")


class StationGraphDataset(Dataset):
    def __init__(self, samples):
        self.inputs = torch.tensor(np.stack([sample[0] for sample in samples]), dtype=torch.float32)
        self.targets = torch.tensor(np.stack([sample[1] for sample in samples]), dtype=torch.float32)

    def __len__(self):
        return len(self.inputs)

    def __getitem__(self, idx):
        return self.inputs[idx], self.targets[idx]


def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2.0) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2.0) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def build_station_graph(station_codes):
    path = os.path.join(DATA_DIR, "stations_100.json")
    with open(path) as f:
        data = json.load(f)

    stations = []
    for code in station_codes:
        name = STATION_CODE_MAP[code]
        match = [s for s in data["stations_100"] if s.get("name") == name]
        if not match:
            raise ValueError(f"Station name not found in graph: {name}")
        stations.append(match[0])

    src = []
    dst = []
    for i in range(len(stations)):
        for j in range(i + 1, len(stations)):
            dist = haversine_km(
                stations[i]["lat"], stations[i]["lng"],
                stations[j]["lat"], stations[j]["lng"],
            )
            if dist <= EDGE_DISTANCE_THRESHOLD_KM:
                src.extend([i, j])
                dst.extend([j, i])

    if len(src) == 0:
        raise ValueError("No graph edges created. Check threshold value.")

    return torch.tensor([src, dst], dtype=torch.long), stations


def build_snapshot_features(row):
    delay_norm = min(row["delay_minutes"] / 90.0, 1.0)
    speed_norm = min(row["speed_kmh"] / 120.0, 1.0)
    hour_rad = 2 * math.pi * (float(row["hour_of_day"]) % 24) / 24.0
    hour_sin = math.sin(hour_rad)
    hour_cos = math.cos(hour_rad)
    weather = float(row["weather_severity"])
    platform = float(row["platform_free"])
    headway = min(float(row["headway_min"]) / 120.0, 1.0)
    priority = (float(row["priority"]) - 1.0) / 2.0

    return [
        delay_norm,
        speed_norm,
        hour_sin,
        hour_cos,
        weather,
        platform,
        headway,
        priority,
    ]


def build_dataset(df, station_codes, samples=5000, random_seed=42):
    groups = {code: df[df["station_code"] == code] for code in station_codes}
    for code, group in groups.items():
        if group.empty:
            raise ValueError(f"No training rows for station code: {code}")

    rng = np.random.default_rng(random_seed)
    samples_data = []

    for _ in range(samples):
        rows = [group.sample(n=1, replace=True, random_state=int(rng.integers(1_000_000))).iloc[0] for group in groups.values()]
        node_features = [build_snapshot_features(row) for row in rows]
        targets = [[float(row["congestion_score"])] for row in rows]
        samples_data.append((node_features, targets))

    return StationGraphDataset(samples_data)


def train_gnn(
    epochs=25,
    samples=6000,
    lr=1e-3,
    hidden_dim=64,
    report_every=5,
):
    station_codes = ["BPL", "ET", "NDLS", "MGS", "DHN", "HWH"]
    print("Preparing station graph and synthetic dataset...")

    df = pd.read_csv(os.path.join(DATA_DIR, "synthetic_delays.csv"))
    edge_index, stations = build_station_graph(station_codes)
    dataset = build_dataset(df, station_codes, samples=samples)

    train_size = int(len(dataset) * 0.8)
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = torch.utils.data.random_split(
        dataset, [train_size, val_size], generator=torch.Generator().manual_seed(123)
    )

    train_loader = DataLoader(train_dataset, batch_size=1, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=1)

    in_feat = dataset.inputs.shape[-1]
    model = RailGNN(in_feat=in_feat, hid_dim=hidden_dim, out_dim=1)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    print(f"Training RailGNN with {len(train_dataset)} examples and {in_feat} input features...")
    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        for batch_x, batch_y in train_loader:
            batch_x = batch_x.squeeze(0)
            batch_y = batch_y.squeeze(0).squeeze(-1)
            optimizer.zero_grad()
            output = model(batch_x, edge_index).squeeze(1)
            loss = loss_fn(output, batch_y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        train_loss = total_loss / len(train_loader)

        if epoch % report_every == 0 or epoch == epochs:
            model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for batch_x, batch_y in val_loader:
                    batch_x = batch_x.squeeze(0)
                    batch_y = batch_y.squeeze(0).squeeze(-1)
                    output = model(batch_x, edge_index).squeeze(1)
                    val_loss += loss_fn(output, batch_y).item()
            val_loss /= len(val_loader)
            print(f"   Epoch {epoch:02d} | train_loss={train_loss:.4f} | val_loss={val_loss:.4f}")

    os.makedirs(MODEL_DIR, exist_ok=True)
    model_path = os.path.join(MODEL_DIR, "raildrishti_gnn.pt")
    torch.save(model.state_dict(), model_path)
    print(f"\nGNN trained and saved -> {model_path}")

    print("\nSample eval from validation set:")
    model.eval()
    with torch.no_grad():
        sample_x, sample_y = val_dataset[0]
        predictions = model(sample_x, edge_index).squeeze(1).tolist()
    print(f"   target scores: {[round(float(v),3) for v in sample_y.squeeze(-1).tolist()]}")
    print(f"   predicted scores: {[round(float(v),3) for v in predictions]}")


if __name__ == "__main__":
    train_gnn()
