"""
rail_gnn.py — 2-layer Graph Convolutional Network for rail delay prediction.
Trains on synthetic + live data, saves/loads checkpoints.
Outputs per-node delay predictions and graph-level embeddings.
"""

import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try importing PyTorch + PyG; provide fallback numpy GCN if unavailable
# ---------------------------------------------------------------------------
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    HAS_TORCH = True
    logger.info(f"PyTorch {torch.__version__} available")
except ImportError:
    HAS_TORCH = False
    logger.warning("PyTorch not installed — using NumPy GCN fallback")

try:
    from torch_geometric.nn import GCNConv, global_mean_pool
    from torch_geometric.data import Data, Batch
    HAS_PYG = True
    logger.info("torch_geometric available")
except ImportError:
    HAS_PYG = False
    logger.warning("torch_geometric not installed — using manual GCN")

from ml.config import (
    GNN_HIDDEN_DIM, GNN_OUTPUT_DIM, GNN_NUM_LAYERS, GNN_DROPOUT,
    OBS_FEATURE_DIM, MODEL_DIR,
)


# ---------------------------------------------------------------------------
# PyTorch-based GCN (preferred)
# ---------------------------------------------------------------------------

if HAS_TORCH and HAS_PYG:

    class RailGCN(nn.Module):
        """
        2-layer Graph Convolutional Network for per-node delay regression.
        Architecture:
          Input (N, 48) → GCNConv → ReLU → Dropout
                        → GCNConv → ReLU → Dropout
                        → Linear → output (N, 1) per-node delay prediction
                        → global_mean_pool → graph embedding (B, output_dim)
        """

        def __init__(
            self,
            in_features: int = OBS_FEATURE_DIM,
            hidden_dim: int = GNN_HIDDEN_DIM,
            out_dim: int = GNN_OUTPUT_DIM,
            num_layers: int = GNN_NUM_LAYERS,
            dropout: float = GNN_DROPOUT,
        ):
            super().__init__()
            self.num_layers = num_layers
            self.dropout = dropout

            # GCN layers
            self.convs = nn.ModuleList()
            self.bns = nn.ModuleList()

            dims = [in_features] + [hidden_dim] * (num_layers - 1) + [out_dim]
            for i in range(num_layers):
                self.convs.append(GCNConv(dims[i], dims[i + 1]))
                self.bns.append(nn.BatchNorm1d(dims[i + 1]))

            # Per-node delay head
            self.delay_head = nn.Sequential(
                nn.Linear(out_dim, 32),
                nn.ReLU(),
                nn.Linear(32, 1),
                nn.Softplus(),   # output >= 0 (delays are non-negative)
            )

            # Graph-level embedding projection
            self.graph_proj = nn.Linear(out_dim, out_dim)

        def forward(
            self,
            x: "torch.Tensor",
            edge_index: "torch.Tensor",
            batch: Optional["torch.Tensor"] = None,
            edge_attr: Optional["torch.Tensor"] = None,
        ) -> Dict[str, "torch.Tensor"]:
            """
            Args:
                x: Node features (N, in_features)
                edge_index: Graph connectivity (2, E)
                batch: Batch vector (N,) — None for single graph
                edge_attr: Edge features (E, feat_dim) — optional
            Returns:
                dict with:
                  'node_embeddings': (N, out_dim)
                  'delay_pred': (N, 1) — predicted delay in minutes (×180)
                  'graph_embedding': (B, out_dim)
            """
            h = x
            for conv, bn in zip(self.convs, self.bns):
                h = conv(h, edge_index)
                h = bn(h)
                h = F.relu(h)
                h = F.dropout(h, p=self.dropout, training=self.training)

            # Per-node delay prediction (0-1, scale ×180 for minutes)
            delay_pred = self.delay_head(h) * 180.0

            # Graph-level embedding
            if batch is None:
                batch = torch.zeros(x.size(0), dtype=torch.long, device=x.device)
            graph_emb = global_mean_pool(h, batch)
            graph_emb = self.graph_proj(graph_emb)

            return {
                "node_embeddings": h,
                "delay_pred": delay_pred,
                "graph_embedding": graph_emb,
            }

        def predict(
            self,
            x: "torch.Tensor",
            edge_index: "torch.Tensor",
        ) -> np.ndarray:
            """Inference: return delay predictions as numpy array."""
            self.eval()
            with torch.no_grad():
                out = self.forward(x, edge_index)
                return out["delay_pred"].squeeze(-1).cpu().numpy()


elif HAS_TORCH and not HAS_PYG:

    class RailGCN(nn.Module):
        """
        Manual GCN implementation (no torch_geometric dependency).
        Uses sparse adjacency matrix multiplication.
        """

        def __init__(
            self,
            in_features: int = OBS_FEATURE_DIM,
            hidden_dim: int = GNN_HIDDEN_DIM,
            out_dim: int = GNN_OUTPUT_DIM,
            num_layers: int = GNN_NUM_LAYERS,
            dropout: float = GNN_DROPOUT,
        ):
            super().__init__()
            self.num_layers = num_layers
            self.dropout = dropout

            self.W = nn.ModuleList()
            dims = [in_features] + [hidden_dim] * (num_layers - 1) + [out_dim]
            for i in range(num_layers):
                self.W.append(nn.Linear(dims[i], dims[i + 1], bias=False))
            self.bns = nn.ModuleList([nn.BatchNorm1d(d) for d in dims[1:]])

            self.delay_head = nn.Sequential(
                nn.Linear(out_dim, 32), nn.ReLU(),
                nn.Linear(32, 1), nn.Softplus(),
            )

        def _gcn_conv(self, A_hat, x, W):
            """A_hat x W — normalized adjacency x features x weights."""
            return F.relu(W(torch.spmm(A_hat, x)))

        @staticmethod
        def _normalize_adj(edge_index, n):
            """Compute symmetric normalized adjacency Â = D^{-1/2} A D^{-1/2}."""
            row, col = edge_index
            deg = torch.zeros(n, device=edge_index.device)
            deg.scatter_add_(0, row, torch.ones(row.size(0), device=edge_index.device))
            deg_inv_sqrt = deg.pow(-0.5)
            deg_inv_sqrt[deg_inv_sqrt == float("inf")] = 0
            val = deg_inv_sqrt[row] * deg_inv_sqrt[col]
            return torch.sparse_coo_tensor(edge_index, val, (n, n))

        def forward(self, x, edge_index, batch=None, edge_attr=None):
            n = x.size(0)
            A_hat = self._normalize_adj(edge_index, n)
            h = x
            for W, bn in zip(self.W, self.bns):
                h = self._gcn_conv(A_hat, h, W)
                h = bn(h)
                h = F.dropout(h, p=self.dropout, training=self.training)
            delay_pred = self.delay_head(h) * 180.0
            graph_emb = h.mean(dim=0, keepdim=True)
            return {
                "node_embeddings": h,
                "delay_pred": delay_pred,
                "graph_embedding": graph_emb,
            }

        def predict(self, x, edge_index):
            self.eval()
            with torch.no_grad():
                out = self.forward(x, edge_index)
                return out["delay_pred"].squeeze(-1).cpu().numpy()


else:
    # -----------------------------------------------------------------------
    # NumPy GCN fallback (no PyTorch required — slower but functional)
    # -----------------------------------------------------------------------
    class RailGCN:  # type: ignore
        """NumPy-based GCN fallback."""

        def __init__(
            self,
            in_features: int = OBS_FEATURE_DIM,
            hidden_dim: int = GNN_HIDDEN_DIM,
            out_dim: int = GNN_OUTPUT_DIM,
            num_layers: int = GNN_NUM_LAYERS,
            dropout: float = GNN_DROPOUT,
        ):
            dims = [in_features] + [hidden_dim] * (num_layers - 1) + [out_dim]
            self.weights = [
                np.random.randn(dims[i], dims[i + 1]).astype(np.float32) * 0.01
                for i in range(num_layers)
            ]
            self.is_trained = False

        def _normalize_adj(self, edge_index: np.ndarray, n: int) -> np.ndarray:
            A = np.zeros((n, n), dtype=np.float32)
            for i in range(edge_index.shape[1]):
                A[edge_index[0, i], edge_index[1, i]] = 1.0
            D = np.diag(A.sum(axis=1) + 1e-6)
            D_inv_sqrt = np.diag(1.0 / np.sqrt(np.diag(D)))
            return D_inv_sqrt @ A @ D_inv_sqrt

        def forward(self, x: np.ndarray, edge_index: np.ndarray, **kwargs) -> dict:
            n = x.shape[0]
            A_hat = self._normalize_adj(edge_index, n)
            h = x
            for W in self.weights:
                h = np.maximum(0, A_hat @ h @ W)  # ReLU
            delay_pred = np.maximum(0, h @ np.random.randn(h.shape[1], 1).astype(np.float32)) * 180
            return {
                "node_embeddings": h,
                "delay_pred": delay_pred,
                "graph_embedding": h.mean(axis=0, keepdims=True),
            }

        def predict(self, x: np.ndarray, edge_index: np.ndarray) -> np.ndarray:
            out = self.forward(x, edge_index)
            return out["delay_pred"].flatten()

        def train(self, mode=True):
            return self

        def eval(self):
            return self

        def parameters(self):
            return iter([])

        def state_dict(self):
            return {"weights": [w.tolist() for w in self.weights]}

        def load_state_dict(self, sd, strict=True):
            if "weights" in sd:
                self.weights = [np.array(w, dtype=np.float32) for w in sd["weights"]]
            self.is_trained = True


# ---------------------------------------------------------------------------
# Training utilities
# ---------------------------------------------------------------------------

def train_gnn(
    model: "RailGCN",
    edge_index: np.ndarray,
    episodes_X: List[np.ndarray],   # list of (N, 48) feature matrices
    episodes_y: List[np.ndarray],   # list of (N,) delay targets
    epochs: int = 50,
    lr: float = 1e-3,
    batch_size: int = 32,
    checkpoint_every: int = 10,
    checkpoint_path: Optional[str] = None,
) -> Dict[str, List[float]]:
    """
    Supervised pre-training of the GCN on synthetic delay data.
    Returns training history dict.
    """
    if not HAS_TORCH:
        logger.warning("PyTorch not available — skipping GNN training")
        return {"loss": []}

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    loss_fn = nn.HuberLoss(delta=10.0)  # robust to large outliers

    ei_t = torch.tensor(edge_index, dtype=torch.long, device=device)

    history: Dict[str, List[float]] = {"loss": [], "val_loss": []}
    best_loss = float("inf")

    logger.info(f"Training GNN on {len(episodes_X)} episodes for {epochs} epochs")

    for epoch in range(epochs):
        model.train()
        epoch_losses = []

        # Shuffle episodes
        indices = np.random.permutation(len(episodes_X))
        for idx in indices:
            X = torch.tensor(episodes_X[idx], dtype=torch.float32, device=device)
            y = torch.tensor(episodes_y[idx], dtype=torch.float32, device=device)

            optimizer.zero_grad()
            out = model(X, ei_t)
            pred = out["delay_pred"].squeeze(-1)
            loss = loss_fn(pred, y)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            epoch_losses.append(loss.item())

        scheduler.step()
        mean_loss = np.mean(epoch_losses)
        history["loss"].append(float(mean_loss))

        if (epoch + 1) % 10 == 0:
            logger.info(f"Epoch {epoch+1}/{epochs} — loss: {mean_loss:.4f}")

        # Checkpoint
        if checkpoint_path and (epoch + 1) % checkpoint_every == 0:
            if mean_loss < best_loss:
                best_loss = mean_loss
                save_gnn(model, checkpoint_path)

    logger.info(f"GNN training complete. Best loss: {best_loss:.4f}")
    return history


def save_gnn(model: "RailGCN", path: Optional[str] = None) -> str:
    """Save model checkpoint. Returns path to saved file."""
    if path is None:
        path = os.path.join(MODEL_DIR, "rail_gnn.pt")
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if HAS_TORCH and hasattr(model, "state_dict"):
        import torch
        torch.save({
            "model_state": model.state_dict(),
            "timestamp": time.time(),
            "config": {
                "in_features": OBS_FEATURE_DIM,
                "hidden_dim": GNN_HIDDEN_DIM,
                "out_dim": GNN_OUTPUT_DIM,
                "num_layers": GNN_NUM_LAYERS,
            },
        }, path)
    else:
        import json
        with open(path.replace(".pt", ".json"), "w") as f:
            json.dump(model.state_dict(), f)

    logger.info(f"GNN saved to {path}")
    return path


def load_gnn(path: Optional[str] = None) -> "RailGCN":
    """Load model from checkpoint. Returns model instance."""
    if path is None:
        path = os.path.join(MODEL_DIR, "rail_gnn.pt")

    model = RailGCN()

    if HAS_TORCH and os.path.exists(path):
        import torch
        checkpoint = torch.load(path, map_location="cpu")
        model.load_state_dict(checkpoint["model_state"])
        logger.info(f"GNN loaded from {path}")
    elif os.path.exists(path.replace(".pt", ".json")):
        import json
        with open(path.replace(".pt", ".json")) as f:
            sd = json.load(f)
        model.load_state_dict(sd)
        logger.info(f"NumPy GNN loaded from {path.replace('.pt', '.json')}")
    else:
        logger.warning(f"No checkpoint found at {path} — using fresh model")

    return model