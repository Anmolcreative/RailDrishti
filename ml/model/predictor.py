"""
predictor.py — Fast inference combining PPO policy + GNN embeddings.
Target: <50ms end-to-end latency per prediction.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from ml.config import (
    OBS_FEATURE_DIM, GNN_OUTPUT_DIM, MAX_INFERENCE_LATENCY_MS,
    MODEL_DIR,
)
from ml.model.rail_gnn import RailGCN, load_gnn
from ml.model.corridor_graph import get_corridor_graph
from ml.model.feature_engineer import get_feature_engineer
from ml.data.station_loader import get_station_loader

logger = logging.getLogger(__name__)

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


# ---------------------------------------------------------------------------
# Prediction output
# ---------------------------------------------------------------------------

@dataclass
class DelayPrediction:
    """Per-station delay prediction with confidence and action recommendation."""
    station_code: str
    predicted_delay_min: float
    confidence: float             # 0-1
    recommended_action: str       # "hold" | "speed_up" | "reroute" | "priority"
    action_urgency: float         # 0-1
    timestamp: float              # unix timestamp
    inference_ms: float           # latency for this prediction

    def to_dict(self) -> dict:
        return {
            "station": self.station_code,
            "delay_min": round(self.predicted_delay_min, 1),
            "confidence": round(self.confidence, 3),
            "action": self.recommended_action,
            "urgency": round(self.action_urgency, 3),
            "inference_ms": round(self.inference_ms, 2),
        }


@dataclass
class PredictionBatch:
    """Batch of predictions for all stations."""
    predictions: Dict[str, DelayPrediction] = field(default_factory=dict)
    total_inference_ms: float = 0.0
    graph_embedding: Optional[np.ndarray] = None
    episode_id: str = ""

    def top_k_delayed(self, k: int = 5) -> List[DelayPrediction]:
        """Return k stations with highest predicted delay."""
        return sorted(
            self.predictions.values(),
            key=lambda p: p.predicted_delay_min,
            reverse=True,
        )[:k]

    def critical_stations(self, threshold_min: float = 30.0) -> List[str]:
        """Return station codes with predicted delay > threshold."""
        return [
            code for code, pred in self.predictions.items()
            if pred.predicted_delay_min > threshold_min
        ]


# ---------------------------------------------------------------------------
# Action policy (lightweight MLP on top of GNN embeddings)
# ---------------------------------------------------------------------------

if HAS_TORCH:
    import torch.nn as nn
    import torch.nn.functional as F

    class ActionPolicy(nn.Module):
        """
        Lightweight MLP action head.
        Input: GNN node embedding (out_dim) + delay scalar + urgency
        Output: action logits (4 actions)
        """
        ACTIONS = ["hold", "speed_up", "reroute", "priority"]

        def __init__(self, embedding_dim: int = GNN_OUTPUT_DIM):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(embedding_dim + 2, 64),
                nn.ReLU(),
                nn.Linear(64, 32),
                nn.ReLU(),
                nn.Linear(32, len(self.ACTIONS)),
            )

        def forward(self, emb, delay_norm, time_pressure):
            x = torch.cat([emb, delay_norm.unsqueeze(-1), time_pressure.unsqueeze(-1)], dim=-1)
            return self.net(x)

        def predict_action(self, emb_np: np.ndarray, delay: float, urgency: float) -> Tuple[str, float]:
            with torch.no_grad():
                emb_t = torch.tensor(emb_np, dtype=torch.float32).unsqueeze(0)
                d_t = torch.tensor([min(delay, 180) / 180], dtype=torch.float32)
                u_t = torch.tensor([urgency], dtype=torch.float32)
                logits = self.forward(emb_t, d_t, u_t)
                probs = F.softmax(logits, dim=-1).squeeze().numpy()
            action_idx = int(np.argmax(probs))
            return self.ACTIONS[action_idx], float(probs[action_idx])

else:
    class ActionPolicy:  # type: ignore
        ACTIONS = ["hold", "speed_up", "reroute", "priority"]

        def __init__(self, *args, **kwargs):
            pass

        def predict_action(self, emb_np, delay, urgency):
            # Simple heuristic fallback
            if delay > 60:
                return "reroute", 0.8
            elif delay > 30:
                return "priority", 0.7
            elif delay > 10:
                return "speed_up", 0.6
            return "hold", 0.9

        def train(self, mode=True): return self
        def eval(self): return self
        def parameters(self): return iter([])


# ---------------------------------------------------------------------------
# Predictor
# ---------------------------------------------------------------------------

class Predictor:
    """
    Main inference engine.
    Combines GNN forward pass + action policy to produce per-station
    delay predictions and operational recommendations in <50ms.
    """

    def __init__(self, gnn_path: Optional[str] = None):
        self._gnn: RailGCN = load_gnn(gnn_path)
        self._policy = ActionPolicy()
        self._graph = get_corridor_graph()
        self._loader = get_station_loader()
        self._engineer = get_feature_engineer()

        # Precompute static tensors
        self._edge_index_np = self._graph.edge_index()  # (2, E)
        self._base_node_feats = self._graph.node_features()   # (N, 4)

        if HAS_TORCH:
            self._edge_index_t = torch.tensor(self._edge_index_np, dtype=torch.long)
            self._gnn.eval()

        # Latency tracking
        self._latency_history: List[float] = []
        self._prediction_count = 0

        logger.info(
            f"Predictor ready — {self._loader.count()} stations, "
            f"{'PyTorch' if HAS_TORCH else 'NumPy'} backend"
        )

    def predict(
        self,
        station_delays: Dict[str, float],
        weather_obs: Optional[dict] = None,
        cascade_stations: Optional[Dict[str, int]] = None,
        train_counts: Optional[Dict[str, int]] = None,
        intervention_set: Optional[set] = None,
    ) -> PredictionBatch:
        """
        Full inference pipeline.
        Returns PredictionBatch with all station predictions.
        Target latency: <50ms.
        """
        t_start = time.perf_counter()

        # 1. Feature engineering
        X = self._engineer.build_node_features(
            station_delays=station_delays,
            weather_obs=weather_obs,
            cascade_stations=cascade_stations,
            train_counts=train_counts,
            intervention_set=intervention_set,
        )  # (N, 48)

        # 2. GNN forward pass
        if HAS_TORCH:
            X_t = torch.tensor(X, dtype=torch.float32)
            out = self._gnn.forward(X_t, self._edge_index_t)
            delay_preds = out["delay_pred"].detach().squeeze(-1).numpy()
            node_embs = out["node_embeddings"].detach().numpy()
            graph_emb = out["graph_embedding"].detach().numpy().squeeze()
        else:
            out = self._gnn.forward(X, self._edge_index_np)
            delay_preds = out["delay_pred"].flatten()
            node_embs = out["node_embeddings"]
            graph_emb = out["graph_embedding"].flatten()

        # 3. Build predictions + actions
        ordered = self._loader.all_list()
        predictions: Dict[str, DelayPrediction] = {}
        t_gnn = time.perf_counter()

        for station in ordered:
            i = station.index
            pred_delay = float(delay_preds[i])
            emb = node_embs[i]

            # Urgency: blend predicted delay with cascade risk
            cascade_risk = cascade_stations.get(station.code, 0) > 0 if cascade_stations else False
            urgency = min(1.0, pred_delay / 60.0 + (0.3 if cascade_risk else 0.0))

            action, confidence = self._policy.predict_action(emb, pred_delay, urgency)

            predictions[station.code] = DelayPrediction(
                station_code=station.code,
                predicted_delay_min=round(max(0.0, pred_delay), 1),
                confidence=confidence,
                recommended_action=action,
                action_urgency=urgency,
                timestamp=t_start,
                inference_ms=0.0,  # filled below
            )

        t_end = time.perf_counter()
        total_ms = (t_end - t_start) * 1000

        # Fill inference time
        for pred in predictions.values():
            pred.inference_ms = total_ms

        self._latency_history.append(total_ms)
        self._prediction_count += 1

        if total_ms > MAX_INFERENCE_LATENCY_MS:
            logger.warning(f"Inference latency {total_ms:.1f}ms exceeds budget {MAX_INFERENCE_LATENCY_MS}ms")

        batch = PredictionBatch(
            predictions=predictions,
            total_inference_ms=total_ms,
            graph_embedding=graph_emb,
        )

        logger.debug(
            f"Prediction #{self._prediction_count}: {total_ms:.1f}ms, "
            f"{len(batch.critical_stations())} critical stations"
        )
        return batch

    def predict_single(self, station_code: str, context: Dict[str, float]) -> DelayPrediction:
        """Quick single-station prediction (uses full graph for context)."""
        batch = self.predict(context)
        return batch.predictions.get(
            station_code,
            DelayPrediction(
                station_code=station_code,
                predicted_delay_min=0.0,
                confidence=0.0,
                recommended_action="hold",
                action_urgency=0.0,
                timestamp=time.time(),
                inference_ms=0.0,
            ),
        )

    @property
    def avg_latency_ms(self) -> float:
        if not self._latency_history:
            return 0.0
        return float(np.mean(self._latency_history[-100:]))  # rolling 100

    @property
    def p95_latency_ms(self) -> float:
        if not self._latency_history:
            return 0.0
        return float(np.percentile(self._latency_history[-100:], 95))

    @property
    def stats(self) -> dict:
        return {
            "prediction_count": self._prediction_count,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "backend": "pytorch" if HAS_TORCH else "numpy",
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_predictor: Optional[Predictor] = None


def get_predictor(gnn_path: Optional[str] = None) -> Predictor:
    global _predictor
    if _predictor is None:
        _predictor = Predictor(gnn_path=gnn_path)
    return _predictor