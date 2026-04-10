"""
RailDrishti — export_onnx.py
Exports trained GNN to ONNX for backend serving.
Run: python export_onnx.py
"""

import os
import torch
from model.gnn_model import RailGNN


if __name__ == "__main__":
    model = RailGNN(in_feat=4, hid_dim=32, out_dim=1)
    model.eval()

    # Load trained weights if they exist
    weights = "model/raildrishti_gnn.pt"
    if os.path.exists(weights):
        model.load_state_dict(torch.load(weights, map_location="cpu"))
        print(f"✅ Loaded weights from {weights}")
    else:
        print("⚠️  No saved weights found — exporting untrained model (run train_gnn.py first)")

    # Dummy inputs matching stations_100 size (100 nodes, 4 features)
    dummy_x     = torch.randn(100, 4)
    dummy_edges = torch.zeros(2, 10, dtype=torch.long)

    os.makedirs("model", exist_ok=True)
    out_path = "model/raildrishti_gnn.onnx"

    torch.onnx.export(
        model,
        (dummy_x, dummy_edges),
        out_path,
        input_names  = ["node_features", "edge_index"],
        output_names = ["congestion_scores"],
        dynamic_axes = {
            "node_features":   {0: "num_nodes"},
            "congestion_scores": {0: "num_nodes"},
        },
        opset_version=11,
    )
    print(f"✅ ONNX exported → {out_path}")
    print(f"   Input:  node_features (N, 4), edge_index (2, E)")
    print(f"   Output: congestion_scores (N, 1)")