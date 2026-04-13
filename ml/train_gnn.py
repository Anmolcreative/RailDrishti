"""
RailDrishti — train_gnn.py
Quick GNN sanity test + saves initial weights.
Run: python train_gnn.py
"""

import torch
import torch.nn as nn
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from model.gnn_model import RailGNN


def build_tensors_from_json(path="data/stations_100.json"):
    with open(path) as f:
        data = json.load(f)
    stations = data["stations_100"]

    MAX_TRAINS = 400.0
    LAT_MIN, LAT_MAX = 8.0, 37.0
    LNG_MIN, LNG_MAX = 68.0, 97.0

    features = []
    for s in stations:
        features.append([
            float(s.get("congestion", 0.5)),
            float(s.get("trains", 50)) / MAX_TRAINS,
            (float(s.get("lat", 23.0)) - LAT_MIN) / (LAT_MAX - LAT_MIN),
            (float(s.get("lng", 78.0)) - LNG_MIN) / (LNG_MAX - LNG_MIN),
        ])

    # Simple chain edges: 0-1-2-...-99
    n = len(stations)
    src = list(range(n - 1)) + list(range(1, n))
    dst = list(range(1, n)) + list(range(n - 1))
    return (
        torch.tensor(features, dtype=torch.float),
        torch.tensor([src, dst], dtype=torch.long),
        torch.tensor([s["congestion"] for s in stations], dtype=torch.float),
    )


if __name__ == "__main__":
    print("🔧 Loading stations_100.json ...")
    x, edge_index, targets = build_tensors_from_json()
    print(f"   Nodes: {x.shape[0]} | Features: {x.shape[1]} | Edges: {edge_index.shape[1]}")

    model = RailGNN(in_feat=4, hid_dim=32, out_dim=1)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()

    print("\n📉 Training GNN (50 epochs) ...")
    for epoch in range(1, 51):
        model.train()
        optimizer.zero_grad()
        out = model(x, edge_index).squeeze(1)
        loss = loss_fn(out, targets)
        loss.backward()
        optimizer.step()
        if epoch % 10 == 0:
            print(f"   Epoch {epoch:02d} | Loss: {loss.item():.4f}")

    # Save weights
    os.makedirs("model", exist_ok=True)
    torch.save(model.state_dict(), "model/raildrishti_gnn.pt")
    print("\n✅ GNN trained and saved → model/raildrishti_gnn.pt")
    print(f"   Sample output (first 5 nodes): {out[:5].tolist()}")