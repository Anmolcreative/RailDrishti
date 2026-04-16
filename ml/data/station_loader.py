"""
station_loader.py — Loads and merges all 100 stations across 3 corridors.
Provides unified station index, adjacency lists, and graph-ready structures.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from ml.config import CORRIDORS, ALL_STATION_CODES, CorridorConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Extra stations (beyond the 3-corridor core) to reach ~100 total
# These are major intermediate/nearby stations on Indian rail network
# ---------------------------------------------------------------------------

EXTENDED_STATIONS: Dict[str, Tuple[float, float]] = {
    # North India
    "LKO":  (26.8467, 80.9462),  "LJN": (26.8467, 80.9462),
    "ALJN": (27.8974, 78.0880),  "FBD": (28.4089, 77.3178),
    "GZB":  (28.6692, 77.4538),  "DLI": (28.6597, 77.2296),
    "PNP":  (29.3891, 77.0146),  "SRE": (29.9795, 77.5540),
    "RKSH": (29.9784, 77.5591),  "HW":  (29.9457, 78.1642),
    "RMB":  (30.1500, 78.0000),  "MB":  (28.9845, 77.7064),
    "KGM":  (29.2183, 79.5130),  "BE":  (27.9775, 79.1341),
    "BSB":  (25.3176, 82.9739),  "MZP": (25.1471, 82.5698),
    "GKP":  (26.7605, 83.3731),  "CPR": (25.7835, 85.7834),
    "MFP":  (26.1197, 85.3910),  "SPJ": (25.8745, 85.7801),
    "DBG":  (26.1522, 85.8983),  "SHC": (25.5571, 87.2600),
    "KIR":  (25.5484, 87.5813),  "NJP": (26.7050, 88.3602),
    "MLDT": (25.5372, 88.1309),  "BHW": (25.0000, 89.0000),

    # West India
    "RTM":  (23.3341, 75.0367),  "MKC": (22.7000, 75.9000),
    "KOTA": (25.1803, 75.8367),  "AII": (26.4499, 74.6399),
    "JU":   (26.2389, 73.0243),  "BKN": (28.0667, 73.3167),
    "BTI":  (29.0000, 72.0000),  "FIROZPUR": (30.9355, 74.6139),
    "ASR":  (31.6340, 74.8723),  "JAT": (32.7266, 74.8580),
    "UMB":  (30.5665, 76.9235),  "CDG": (30.7333, 76.7794),
    "LDH":  (30.9010, 75.8573),  "JRC": (31.3260, 75.5763),

    # South India
    "YPR":  (13.0194, 77.5628),  "SBC": (12.9779, 77.5713),
    "BNC":  (12.9783, 77.5908),  "MYS": (12.2958, 76.6394),
    "HAS":  (13.7300, 76.1000),  "UBL": (15.3490, 75.1160),
    "GNT":  (16.3007, 80.4428),  "BZA": (16.5193, 80.6480),
    "VSKP": (17.6868, 83.2185),  "BVRT": (18.4386, 83.8673),
    "PALASA": (18.7726, 84.4149),"VZM": (18.1070, 83.4298),
    "RJY":  (17.0005, 81.7799),  "EE":  (16.7200, 81.0958),
    "MTM":  (16.4369, 80.5150),  "NS":  (15.8500, 79.9833),
    "NDKD": (15.5167, 78.4833),  "KC":  (15.4300, 78.4800),
    "GTL":  (15.1563, 77.2720),  "DMM": (14.4426, 76.6321),
    "DVG":  (14.4667, 75.9170),  "ASK": (13.6720, 76.6270),
    "TK":   (13.3450, 77.1020),  "BAND": (12.8728, 77.6011),
    "KJM":  (13.0197, 77.6466),  "WFD": (12.9833, 77.5833),

    # East India
    "TATA": (22.8046, 86.2029),  "CKP": (22.6033, 86.1562),
    "KGP":  (22.3459, 87.3192),  "NLS": (21.9000, 86.5000),
    "BBS":  (20.2961, 85.8245),  "CTC": (20.4625, 85.8830),
    "BHC":  (22.1826, 84.7643),  "ROU": (22.2604, 84.8536),
    "JSME": (24.0000, 86.9167),  "GMO": (23.7995, 86.4261),
    "HZB":  (23.9947, 85.3553),  "RNC": (23.3441, 85.3096),
    "GAY":  (24.7955, 84.9994),
}


# ---------------------------------------------------------------------------
# Station record
# ---------------------------------------------------------------------------

@dataclass
class Station:
    code: str
    name: str
    lat: float
    lon: float
    corridors: List[str] = field(default_factory=list)   # corridor keys
    is_junction: bool = False
    index: int = 0                                        # 0-based node index in graph
    adjacent: List[str] = field(default_factory=list)    # adjacent station codes

    def to_dict(self) -> dict:
        return {
            "code": self.code, "name": self.name,
            "lat": self.lat, "lon": self.lon,
            "corridors": self.corridors, "is_junction": self.is_junction,
            "index": self.index, "adjacent": self.adjacent,
        }


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class StationLoader:
    """
    Loads and merges all stations across corridors and extended list.
    Provides graph-ready adjacency structures.
    """

    def __init__(self):
        self._stations: Dict[str, Station] = {}
        self._built = False

    def build(self) -> "StationLoader":
        """Build the station registry. Call once at startup."""
        self._load_corridor_stations()
        self._load_extended_stations()
        self._assign_indices()
        self._build_adjacency()
        self._built = True
        logger.info(
            f"StationLoader built: {len(self._stations)} stations, "
            f"{sum(1 for s in self._stations.values() if s.is_junction)} junctions"
        )
        return self

    def _load_corridor_stations(self):
        """Load stations from corridor configs."""
        for corridor_key, corridor in CORRIDORS.items():
            for code in corridor.stations:
                coords = corridor.coordinates.get(code, (0.0, 0.0))
                if code not in self._stations:
                    self._stations[code] = Station(
                        code=code,
                        name=self._code_to_name(code),
                        lat=coords[0],
                        lon=coords[1],
                        corridors=[corridor_key],
                        is_junction=code in corridor.key_junctions,
                    )
                else:
                    s = self._stations[code]
                    if corridor_key not in s.corridors:
                        s.corridors.append(corridor_key)
                    if code in corridor.key_junctions:
                        s.is_junction = True

    def _load_extended_stations(self):
        """Load extended stations (non-corridor but network-relevant)."""
        for code, (lat, lon) in EXTENDED_STATIONS.items():
            if code not in self._stations:
                self._stations[code] = Station(
                    code=code,
                    name=self._code_to_name(code),
                    lat=lat,
                    lon=lon,
                    corridors=[],
                    is_junction=False,
                )

    def _assign_indices(self):
        """Assign 0-based integer index to each station (for tensor ops)."""
        for i, (code, station) in enumerate(sorted(self._stations.items())):
            station.index = i

    def _build_adjacency(self):
        """Build adjacency lists from ordered corridor station lists."""
        for corridor_key, corridor in CORRIDORS.items():
            stns = corridor.stations
            for i, code in enumerate(stns):
                if code not in self._stations:
                    continue
                station = self._stations[code]
                if i > 0 and stns[i - 1] not in station.adjacent:
                    station.adjacent.append(stns[i - 1])
                if i < len(stns) - 1 and stns[i + 1] not in station.adjacent:
                    station.adjacent.append(stns[i + 1])

    @staticmethod
    def _code_to_name(code: str) -> str:
        """Generate a human-readable name from station code."""
        KNOWN_NAMES = {
            "NDLS": "New Delhi", "CSTM": "Chhatrapati Shivaji Mumbai",
            "HWH": "Howrah", "MAS": "Chennai Central", "BPL": "Bhopal Jn",
            "ADI": "Ahmedabad", "BRC": "Vadodara", "PNBE": "Patna Jn",
            "CNB": "Kanpur Central", "ALD": "Allahabad/Prayagraj",
            "MGS": "Mughal Sarai/DDU", "AGC": "Agra Cantt", "GWL": "Gwalior",
            "JHS": "Jhansi", "CBE": "Coimbatore", "SRR": "Shoranur",
            "LKO": "Lucknow", "ASR": "Amritsar", "JAT": "Jammu Tawi",
            "RNC": "Ranchi", "BBS": "Bhubaneswar", "VSKP": "Visakhapatnam",
            "SBC": "KSR Bengaluru", "YPR": "Yeshvantpur", "MYS": "Mysuru",
        }
        return KNOWN_NAMES.get(code, f"{code} Jn" if len(code) <= 3 else code)

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def get(self, code: str) -> Optional[Station]:
        return self._stations.get(code)

    def all(self) -> Dict[str, Station]:
        return dict(self._stations)

    def all_list(self) -> List[Station]:
        return sorted(self._stations.values(), key=lambda s: s.index)

    def count(self) -> int:
        return len(self._stations)

    def junctions(self) -> List[Station]:
        return [s for s in self._stations.values() if s.is_junction]

    def corridor_stations(self, corridor_key: str) -> List[Station]:
        corridor = CORRIDORS.get(corridor_key)
        if not corridor:
            return []
        return [self._stations[c] for c in corridor.stations if c in self._stations]

    def get_index(self, code: str) -> int:
        s = self._stations.get(code)
        return s.index if s else -1

    def index_to_code(self) -> Dict[int, str]:
        return {s.index: s.code for s in self._stations.values()}

    def adjacency_list(self) -> Dict[str, List[str]]:
        return {code: s.adjacent for code, s in self._stations.items()}

    def edge_list(self) -> List[Tuple[int, int]]:
        """Return list of (src_idx, dst_idx) undirected edges for PyTorch Geometric."""
        edges: Set[Tuple[int, int]] = set()
        for station in self._stations.values():
            for adj_code in station.adjacent:
                adj = self._stations.get(adj_code)
                if adj:
                    a, b = station.index, adj.index
                    edges.add((min(a, b), max(a, b)))
        # Return both directions for undirected graph
        result = []
        for a, b in edges:
            result.append((a, b))
            result.append((b, a))
        return sorted(result)

    def coordinate_matrix(self) -> List[Tuple[float, float]]:
        """Ordered (lat, lon) for each station by index."""
        ordered = self.all_list()
        return [(s.lat, s.lon) for s in ordered]

    def __contains__(self, code: str) -> bool:
        return code in self._stations

    def __len__(self) -> int:
        return len(self._stations)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_loader: Optional[StationLoader] = None


def get_station_loader() -> StationLoader:
    global _loader
    if _loader is None:
        _loader = StationLoader().build()
    return _loader