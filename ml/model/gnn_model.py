"""
RailDrishti GNN Model
No torch_geometric dependency — pure PyTorch.
Node features: [congestion, trains_norm, lat_norm, lng_norm] → 4 features
"""

import torch
import torch.nn as nn


class RailGNN(nn.Module):
    def __init__(self, in_feat=4, hid_dim=32, out_dim=1):
        super().__init__()
        self.fc1 = nn.Linear(in_feat, hid_dim)
        self.fc2 = nn.Linear(hid_dim, hid_dim)
        self.fc3 = nn.Linear(hid_dim, out_dim)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.1)

    def forward(self, x, edge_index):
        # Simple message passing: aggregate neighbor features
        x = self._aggregate_neighbors(x, edge_index)
        x = self.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.relu(self.fc2(x))
        x = self.fc3(x)
        return x

    def _aggregate_neighbors(self, x, edge_index):
        """Mean-pool neighbor features into each node."""
        num_nodes = x.size(0)
        agg = x.clone()
        if edge_index.numel() == 0:
            return agg
        src, dst = edge_index[0], edge_index[1]
        for node in range(num_nodes):
            mask = dst == node
            if mask.sum() > 0:
                neighbor_feats = x[src[mask]]
                agg[node] = (x[node] + neighbor_feats.mean(0)) / 2
        return agg