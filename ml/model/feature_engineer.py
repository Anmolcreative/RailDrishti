"""
feature_engineer.py — 48-feature vector construction for each GNN node (station).
Combines delay, weather, temporal, graph-structural, and timetable features.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np

from ml.config import OBS_FEATURE_DIM, CORRIDORS
from ml.data.station_loader import get_station_loader, Station
from ml.data.weather_client import WeatherObservation
from ml.model.corridor_graph import get_corridor_graph

logger = logging.getLogger(__name__)

# Total features per node — must equal OBS_FEATURE_DIM (48)
# Feature breakdown:
#   [0]     current_delay_min (normalized 0-180)
#   [1]     delay_5min_ago (normalized)
#   [2]     delay_delta (current - previous)
#   [3]     delay_is_cascaded (binary)
#   [4]     cascade_generation (0-5, normalized)
#   [5]     temperature_c (normalized 0-50)
#   [6]     precipitation_mm (normalized 0-50)
#   [7]     windspeed_kmh (normalized 0-100)
#   [8]     visibility_norm (0-1)
#   [9]     cloudcover_pct (0-1)
#   [10]    humidity_pct (0-1)
#   [11]    weather_delay_impact (0-1)
#   [12]    is_adverse_weather (binary)
#   [13]    hour_sin  (time encoding)
#   [14]    hour_cos
#   [15]    day_of_week_sin
#   [16]    day_of_week_cos
#   [17]    is_rush_hour (binary)
#   [18]    is_night (binary)
#   [19]    lat_norm
#   [20]    lon_norm
#   [21]    is_junction (binary)
#   [22]    node_degree_norm
#   [23]    num_corridors (0-3, normalized)
#   [24]    trains_expected_next_30min (normalized 0-20)
#   [25]    trains_delayed_at_station (normalized 0-20)
#   [26]    avg_halt_time_min (normalized 0-30)
#   [27]    neighbour_avg_delay (mean delay of adjacent stations)
#   [28]    neighbour_max_delay (max delay among adjacent stations)
#   [29]    neighbour_min_delay
#   [30]    upstream_delay_mean (stations "before" in corridor)
#   [31]    downstream_delay_mean (stations "after" in corridor)
#   [32]    cascade_risk_score (0-1: prob of being hit by cascade)
#   [33]    total_trains_passing_daily (normalized 0-60)
#   [34]    distance_from_origin_norm (corridor-normalized)
#   [35]    distance_to_destination_norm
#   [36]    avg_speed_corridor_norm (0-1)
#   [37]    congestion_index (0-1: fraction of trains delayed)
#   [38]    intervention_active (binary: action taken at this station)
#   [39]    time_since_last_delay_norm (0-1)
#   [40]    delay_trend (slope of last 3 readings)
#   [41]    corridor_id_0 (one-hot delhi_mumbai)
#   [42]    corridor_id_1 (one-hot delhi_howrah)
#   [43]    corridor_id_2 (one-hot chennai_mumbai)
#   [44]    is_origin_station (binary)
#   [45]    is_terminus_station (binary)
#   [46]    platform_congestion (0-1)
#   [47]    reliability_score (historical on-time %)

FEATURE_NAMES = [
    "current_delay_norm", "delay_5min_ago_norm", "delay_delta",
    "is_cascaded", "cascade_gen_norm",
    "temperature_norm", "precipitation_norm", "windspeed_norm",
    "visibility_norm", "cloudcover", "humidity", "weather_impact", "is_adverse",
    "hour_sin", "hour_cos", "dow_sin", "dow_cos", "is_rush_hour", "is_night",
    "lat_norm", "lon_norm", "is_junction", "degree_norm", "num_corridors_norm",
    "trains_expected_norm", "trains_delayed_norm", "avg_halt_norm",
    "nbr_avg_delay", "nbr_max_delay", "nbr_min_delay",
    "upstream_delay_mean", "downstream_delay_mean", "cascade_risk",
    "daily_trains_norm", "dist_from_origin_norm", "dist_to_dest_norm",
    "avg_speed_norm", "congestion_index", "intervention_active",
    "time_since_delay_norm", "delay_trend",
    "corridor_delhi_mumbai", "corridor_delhi_howrah", "corridor_chennai_mumbai",
    "is_origin", "is_terminus", "platform_congestion", "reliability_score",
]
assert len(FEATURE_NAMES) == OBS_FEATURE_DIM, \
    f"Feature count mismatch: {len(FEATURE_NAMES)} != {OBS_FEATURE_DIM}"

CORRIDOR_KEYS = ["delhi_mumbai", "delhi_howrah", "chennai_mumbai"]


class FeatureEngineer:
    """
    Constructs the 48-dimensional feature vector for each station node.
    Called by obs_builder.py on every environment step.
    """

    def __init__(self):
        self._loader = get_station_loader()
        self._graph = get_corridor_graph()
        self._delay_history: Dict[str, List[float]] = {}   # stn -> last 5 readings
        self._last_delay_time: Dict[str, float] = {}       # stn -> unix timestamp
        self._intervention_active: Dict[str, bool] = {}    # stn -> True if action taken
        self._reliability: Dict[str, float] = {}           # stn -> historical on-time %

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def build_node_features(
        self,
        station_delays: Dict[str, float],
        weather_obs: Optional[Dict[str, WeatherObservation]] = None,
        cascade_stations: Optional[Dict[str, int]] = None,   # stn -> cascade generation
        train_counts: Optional[Dict[str, int]] = None,
        intervention_set: Optional[set] = None,
    ) -> np.ndarray:
        """
        Build feature matrix X of shape (N, 48) for all stations.

        Args:
            station_delays: {station_code: current_delay_min}
            weather_obs: {station_code: WeatherObservation}
            cascade_stations: {station_code: cascade_generation} for stations in cascade
            train_counts: {station_code: n_trains_expected}
            intervention_set: set of station codes with active interventions
        """
        now = datetime.now(timezone.utc)
        ordered_stations = self._loader.all_list()
        n = len(ordered_stations)

        X = np.zeros((n, OBS_FEATURE_DIM), dtype=np.float32)

        for station in ordered_stations:
            i = station.index
            features = self._build_single(
                station=station,
                current_delay=station_delays.get(station.code, 0.0),
                all_delays=station_delays,
                weather=weather_obs.get(station.code) if weather_obs else None,
                cascade_gen=cascade_stations.get(station.code, 0) if cascade_stations else 0,
                is_cascaded=station.code in (cascade_stations or {}),
                train_count=train_counts.get(station.code, 0) if train_counts else 0,
                intervention_active=(station.code in (intervention_set or set())),
                now=now,
            )
            X[i] = features

        return X

    def _build_single(
        self,
        station: Station,
        current_delay: float,
        all_delays: Dict[str, float],
        weather: Optional[WeatherObservation],
        cascade_gen: int,
        is_cascaded: bool,
        train_count: int,
        intervention_active: bool,
        now: datetime,
    ) -> np.ndarray:
        """Build 48-feature vector for a single station."""
        code = station.code
        f = np.zeros(OBS_FEATURE_DIM, dtype=np.float32)

        # --- Delay features [0-4] ---
        history = self._delay_history.get(code, [])
        prev_delay = history[-1] if history else 0.0
        f[0] = min(current_delay, 180.0) / 180.0
        f[1] = min(prev_delay, 180.0) / 180.0
        f[2] = np.tanh((current_delay - prev_delay) / 30.0)  # delta, bounded
        f[3] = 1.0 if is_cascaded else 0.0
        f[4] = min(cascade_gen, 5) / 5.0

        # Update history
        history = (history + [current_delay])[-5:]
        self._delay_history[code] = history
        if current_delay > 0:
            self._last_delay_time[code] = now.timestamp()

        # --- Weather features [5-12] ---
        if weather:
            f[5]  = min(weather.temperature_c, 50.0) / 50.0
            f[6]  = min(weather.precipitation_mm, 50.0) / 50.0
            f[7]  = min(weather.windspeed_kmh, 100.0) / 100.0
            f[8]  = min(weather.visibility_m, 10000.0) / 10000.0
            f[9]  = weather.cloudcover_pct / 100.0
            f[10] = weather.humidity_pct / 100.0
            f[11] = float(weather.delay_impact_score())
            f[12] = 1.0 if weather.is_adverse else 0.0
        else:
            # Default to mild conditions
            f[5], f[8], f[9], f[10] = 0.5, 1.0, 0.3, 0.5

        # --- Temporal features [13-18] ---
        hour = now.hour
        dow = now.weekday()
        f[13] = np.sin(2 * np.pi * hour / 24)
        f[14] = np.cos(2 * np.pi * hour / 24)
        f[15] = np.sin(2 * np.pi * dow / 7)
        f[16] = np.cos(2 * np.pi * dow / 7)
        f[17] = 1.0 if hour in (7, 8, 9, 17, 18, 19, 20) else 0.0
        f[18] = 1.0 if hour < 5 or hour >= 23 else 0.0

        # --- Spatial / structural features [19-23] ---
        f[19] = (station.lat - 8.0) / (37.0 - 8.0)
        f[20] = (station.lon - 68.0) / (97.0 - 68.0)
        f[21] = 1.0 if station.is_junction else 0.0
        graph_node = self._graph._nodes.get(code)
        degree = graph_node.degree if graph_node else 0
        max_degree = 6
        f[22] = min(degree, max_degree) / max_degree
        f[23] = len(station.corridors) / 3.0

        # --- Timetable features [24-26] ---
        f[24] = min(train_count, 20) / 20.0
        delayed_trains = sum(
            1 for ev_code, ev_delay in all_delays.items()
            if ev_code == code and ev_delay > 5
        )
        f[25] = min(delayed_trains, 20) / 20.0
        # Average halt time for this station
        halt = self._avg_halt_at(code)
        f[26] = min(halt, 30.0) / 30.0

        # --- Neighbour features [27-29] ---
        nbr_delays = [
            all_delays.get(nbr, 0.0)
            for nbr in self._graph.get_neighbors(code)
        ]
        if nbr_delays:
            f[27] = min(np.mean(nbr_delays), 180.0) / 180.0
            f[28] = min(np.max(nbr_delays), 180.0) / 180.0
            f[29] = min(np.min(nbr_delays), 180.0) / 180.0
        else:
            f[27] = f[28] = f[29] = 0.0

        # --- Upstream / Downstream delay [30-31] ---
        upstream, downstream = self._up_downstream_delays(code, all_delays)
        f[30] = min(upstream, 180.0) / 180.0
        f[31] = min(downstream, 180.0) / 180.0

        # --- Cascade risk [32] ---
        f[32] = self._cascade_risk(code, all_delays)

        # --- Traffic [33] ---
        daily_trains = self._daily_train_count(code)
        f[33] = min(daily_trains, 60) / 60.0

        # --- Distance features [34-36] ---
        dist_orig, dist_dest, speed = self._distance_features(code)
        f[34] = dist_orig
        f[35] = dist_dest
        f[36] = speed

        # --- Congestion index [37] ---
        f[37] = self._congestion_index(all_delays)

        # --- Intervention [38] ---
        f[38] = 1.0 if intervention_active else 0.0
        if intervention_active:
            self._intervention_active[code] = True

        # --- Time since last delay [39] ---
        last_t = self._last_delay_time.get(code)
        if last_t:
            elapsed_hours = (now.timestamp() - last_t) / 3600.0
            f[39] = min(1.0, elapsed_hours / 24.0)
        else:
            f[39] = 1.0

        # --- Delay trend [40] ---
        if len(history) >= 2:
            f[40] = np.tanh((history[-1] - history[0]) / 30.0)
        else:
            f[40] = 0.0

        # --- Corridor one-hot [41-43] ---
        for ci, ck in enumerate(CORRIDOR_KEYS):
            f[41 + ci] = 1.0 if ck in station.corridors else 0.0

        # --- Terminal flags [44-45] ---
        f[44] = 1.0 if self._is_origin(code) else 0.0
        f[45] = 1.0 if self._is_terminus(code) else 0.0

        # --- Platform congestion [46] ---
        f[46] = self._platform_congestion(code, all_delays)

        # --- Reliability score [47] ---
        f[47] = self._reliability.get(code, 0.75)

        return f

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    @staticmethod
    def _avg_halt_at(code: str) -> float:
        """Lookup average halt time from timetable (fallback: 2 min)."""
        try:
            from ml.data.timetable_loader import get_timetable_loader
            loader = get_timetable_loader()
            halts = []
            for sch in loader.trains_at_station(code):
                stop = sch.get_stop(code)
                if stop:
                    halts.append(stop.halt_min)
            return float(np.mean(halts)) if halts else 2.0
        except Exception:
            return 2.0

    def _up_downstream_delays(
        self, code: str, all_delays: Dict[str, float]
    ) -> tuple:
        """
        For each corridor containing this station, compute mean delay
        of stations before (upstream) and after (downstream).
        """
        upstream_delays = []
        downstream_delays = []
        for ck, corridor in CORRIDORS.items():
            stns = corridor.stations
            if code not in stns:
                continue
            idx = stns.index(code)
            for s in stns[:idx]:
                if s in all_delays:
                    upstream_delays.append(all_delays[s])
            for s in stns[idx + 1:]:
                if s in all_delays:
                    downstream_delays.append(all_delays[s])
        up = float(np.mean(upstream_delays)) if upstream_delays else 0.0
        down = float(np.mean(downstream_delays)) if downstream_delays else 0.0
        return up, down

    @staticmethod
    def _cascade_risk(code: str, all_delays: Dict[str, float]) -> float:
        """
        Heuristic cascade risk: fraction of upstream/adjacent stations delayed > 10 min.
        """
        try:
            graph = get_corridor_graph()
            neighbors = graph.get_neighbors(code)
            if not neighbors:
                return 0.0
            high_delay = sum(1 for n in neighbors if all_delays.get(n, 0) > 10)
            return high_delay / len(neighbors)
        except Exception:
            return 0.0

    @staticmethod
    def _daily_train_count(code: str) -> int:
        """Count trains passing through this station per day."""
        count = 0
        for corridor in CORRIDORS.values():
            if code in corridor.stations:
                count += corridor.typical_trains_per_day
        return count

    @staticmethod
    def _distance_features(code: str) -> tuple:
        """Return (dist_from_origin_norm, dist_to_dest_norm, speed_norm) for the primary corridor."""
        for ck, corridor in CORRIDORS.items():
            if code in corridor.stations:
                stns = corridor.stations
                idx = stns.index(code)
                n = len(stns)
                seg = corridor.total_distance_km / max(n - 1, 1)
                dist_from = idx * seg
                dist_to = (n - 1 - idx) * seg
                total = corridor.total_distance_km
                speed = corridor.avg_speed_kmh / 120.0  # normalize to 120 kmh max
                return (
                    dist_from / max(total, 1.0),
                    dist_to / max(total, 1.0),
                    min(speed, 1.0),
                )
        return 0.0, 0.0, 0.5

    @staticmethod
    def _congestion_index(all_delays: Dict[str, float]) -> float:
        """Fraction of all delayed stations with delay > 5 min."""
        if not all_delays:
            return 0.0
        n_delayed = sum(1 for d in all_delays.values() if d > 5)
        return n_delayed / len(all_delays)

    @staticmethod
    def _is_origin(code: str) -> bool:
        return any(c.stations[0] == code for c in CORRIDORS.values())

    @staticmethod
    def _is_terminus(code: str) -> bool:
        return any(c.stations[-1] == code for c in CORRIDORS.values())

    @staticmethod
    def _platform_congestion(code: str, all_delays: Dict[str, float]) -> float:
        """Proxy: normalized delay at this station vs max across all."""
        if not all_delays:
            return 0.0
        max_d = max(all_delays.values()) or 1.0
        return min(all_delays.get(code, 0.0) / max_d, 1.0)

    def set_reliability(self, code: str, score: float):
        """Update historical reliability score for a station."""
        self._reliability[code] = max(0.0, min(1.0, score))

    def reset_interventions(self):
        """Clear all active intervention flags (call after episode reset)."""
        self._intervention_active.clear()

    def reset_history(self):
        """Clear delay history (call at episode start)."""
        self._delay_history.clear()
        self._last_delay_time.clear()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_engineer: Optional[FeatureEngineer] = None


def get_feature_engineer() -> FeatureEngineer:
    global _engineer
    if _engineer is None:
        _engineer = FeatureEngineer()
    return _engineer