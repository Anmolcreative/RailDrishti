"""
obs_builder.py — Gymnasium observation wrapper.
Converts raw delay/weather/timetable state into the 48-feature GNN observation.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from ml.config import OBS_FEATURE_DIM
from ml.data.station_loader import get_station_loader
from ml.model.corridor_graph import get_corridor_graph
from ml.model.feature_engineer import get_feature_engineer

logger = logging.getLogger(__name__)


@dataclass
class RailObservation:
    """
    Full observation for one environment step.
    Passed to the GNN + PPO policy.
    """
    node_features: np.ndarray          # (N, 48)
    edge_index: np.ndarray             # (2, E)
    edge_attr: np.ndarray              # (E, 3)
    graph_embedding: Optional[np.ndarray] = None  # (output_dim,) from GNN
    delay_stats: Optional[np.ndarray] = None       # (10,) summary stats
    station_codes: Optional[List[str]] = None

    def to_flat_dict(self) -> dict:
        """Return dict for PPO (flat vectors, no sparse tensors)."""
        return {
            "node_features": self.node_features,
            "graph_embedding": self.graph_embedding,
            "delay_stats": self.delay_stats,
        }


class ObsBuilder:
    """
    Builds RailObservation from environment state dicts.
    Used by the RL environment on every step.
    """

    def __init__(self):
        self._loader = get_station_loader()
        self._graph = get_corridor_graph()
        self._engineer = get_feature_engineer()
        self._edge_index = self._graph.edge_index()   # precomputed
        self._edge_attr = self._graph.edge_attr()
        self._station_codes = [s.code for s in self._loader.all_list()]

    def build(
        self,
        station_delays: Dict[str, float],
        weather_obs: Optional[dict] = None,
        cascade_stations: Optional[Dict[str, int]] = None,
        train_counts: Optional[Dict[str, int]] = None,
        intervention_set: Optional[set] = None,
    ) -> RailObservation:
        """
        Build full observation.

        Args:
            station_delays: {station_code: delay_min}
            weather_obs: {station_code: WeatherObservation}
            cascade_stations: {station_code: cascade_generation}
            train_counts: {station_code: n_trains_expected}
            intervention_set: set of station codes with active interventions
        """
        node_features = self._engineer.build_node_features(
            station_delays=station_delays,
            weather_obs=weather_obs,
            cascade_stations=cascade_stations,
            train_counts=train_counts,
            intervention_set=intervention_set,
        )  # (N, 48)

        delay_stats = self._compute_delay_stats(station_delays)

        return RailObservation(
            node_features=node_features,
            edge_index=self._edge_index,
            edge_attr=self._edge_attr,
            graph_embedding=None,   # filled by GNN predictor
            delay_stats=delay_stats,
            station_codes=self._station_codes,
        )

    def build_from_live_events(self, events: list) -> RailObservation:
        """
        Build observation from a list of LiveEvent objects.
        Aggregates delays per station.
        """
        station_delays: Dict[str, float] = {}
        train_counts: Dict[str, int] = {}

        for event in events:
            code = getattr(event, "station_code", None)
            if not code:
                continue
            delay = getattr(event, "delay_min", 0.0)
            station_delays[code] = max(station_delays.get(code, 0.0), delay)
            train_counts[code] = train_counts.get(code, 0) + 1

        return self.build(
            station_delays=station_delays,
            train_counts=train_counts,
        )

    def build_from_synthetic_state(self, state) -> RailObservation:
        """Build from a SyntheticDelayState."""
        cascade_stations = {
            e.station_code: e.cascade_generation
            for e in state.delay_events
            if e.cause == "cascade"
        }
        return self.build(
            station_delays=state.station_delays,
            cascade_stations=cascade_stations,
        )

    @staticmethod
    def _compute_delay_stats(station_delays: Dict[str, float]) -> np.ndarray:
        """
        Compute 10 summary statistics about current delay distribution.
        These supplement the per-node features in the PPO observation.
        """
        if not station_delays:
            return np.zeros(10, dtype=np.float32)

        delays = np.array(list(station_delays.values()), dtype=np.float32)
        delays_norm = np.clip(delays, 0, 180) / 180.0

        return np.array([
            float(np.mean(delays_norm)),
            float(np.std(delays_norm)),
            float(np.max(delays_norm)),
            float(np.min(delays_norm)),
            float(np.percentile(delays_norm, 25)),
            float(np.percentile(delays_norm, 75)),
            float(np.percentile(delays_norm, 95)),
            float(np.sum(delays > 30) / max(len(delays), 1)),  # fraction > 30min
            float(np.sum(delays > 60) / max(len(delays), 1)),  # fraction > 60min
            float(np.sum(delays > 0) / max(len(delays), 1)),   # fraction any delay
        ], dtype=np.float32)

    def get_observation_space_shape(self) -> dict:
        """Return observation space shape info for Gymnasium."""
        n = self._loader.count()
        e = self._edge_index.shape[1]
        return {
            "node_features": (n, OBS_FEATURE_DIM),
            "edge_index": (2, e),
            "edge_attr": (e, 3),
            "delay_stats": (10,),
        }

    def reset(self):
        """Reset internal state (call at episode start)."""
        self._engineer.reset_history()
        self._engineer.reset_interventions()


# Singleton
_builder: Optional[ObsBuilder] = None


def get_obs_builder() -> ObsBuilder:
    global _builder
    if _builder is None:
        _builder = ObsBuilder()
    return _builder