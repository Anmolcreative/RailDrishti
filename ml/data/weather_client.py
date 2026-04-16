"""
weather_client.py — Open-Meteo FREE weather API client (no key required).
Fetches current + 24h forecast for any lat/lon.
Integrates with corridor station coordinates from config.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import requests

from ml.config import (
    WEATHER_API_BASE, WEATHER_PARAMS,
    CORRIDORS, SCRAPER_REQUEST_TIMEOUT, SCRAPER_RETRY_ATTEMPTS,
    SCRAPER_RETRY_BACKOFF,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes (stdlib only — avoids heavy deps)
# ---------------------------------------------------------------------------

class WeatherObservation:
    """Snapshot of weather at a station at a point in time."""
    __slots__ = [
        "station_code", "latitude", "longitude", "timestamp",
        "temperature_c", "precipitation_mm", "windspeed_kmh",
        "weathercode", "visibility_m", "cloudcover_pct",
        "humidity_pct", "is_adverse",
    ]

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self) -> dict:
        return {s: getattr(self, s) for s in self.__slots__}

    def delay_impact_score(self) -> float:
        """
        Heuristic 0-1 score: how much might this weather delay trains?
        Used as one feature in the 48-feature vector.
        """
        score = 0.0
        score += min(self.precipitation_mm / 50.0, 1.0) * 0.4
        score += min(self.windspeed_kmh / 80.0, 1.0) * 0.25
        score += (1.0 - min(self.visibility_m / 5000.0, 1.0)) * 0.2
        score += (self.cloudcover_pct / 100.0) * 0.05
        # WMO weather code penalties (fog=45-48, snow=71-77, thunderstorm=95-99)
        wc = self.weathercode or 0
        if wc in range(45, 49):   # fog
            score += 0.3
        elif wc in range(71, 78): # snow
            score += 0.4
        elif wc in range(95, 100): # thunderstorm
            score += 0.5
        return min(score, 1.0)


# ---------------------------------------------------------------------------
# Low-level HTTP helper
# ---------------------------------------------------------------------------

def _get_with_retry(url: str, params: dict, timeout: int = SCRAPER_REQUEST_TIMEOUT) -> Optional[dict]:
    """GET with exponential backoff retries."""
    for attempt in range(SCRAPER_RETRY_ATTEMPTS):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            logger.warning(f"HTTP error on attempt {attempt+1}: {e}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error on attempt {attempt+1}: {e}")
        if attempt < SCRAPER_RETRY_ATTEMPTS - 1:
            time.sleep(SCRAPER_RETRY_BACKOFF * (2 ** attempt))
    return None


# ---------------------------------------------------------------------------
# Core client
# ---------------------------------------------------------------------------

class WeatherClient:
    """
    Fetches weather from Open-Meteo for a set of station coordinates.
    Caches results to avoid hammering the API.
    """

    CACHE_TTL_SEC = 300  # 5 minutes

    def __init__(self):
        self._cache: Dict[str, Tuple[float, WeatherObservation]] = {}

    def _is_cache_valid(self, station_code: str) -> bool:
        if station_code not in self._cache:
            return False
        cached_at, _ = self._cache[station_code]
        return (time.time() - cached_at) < self.CACHE_TTL_SEC

    def fetch_station(
        self,
        station_code: str,
        lat: float,
        lon: float,
        force_refresh: bool = False,
    ) -> Optional[WeatherObservation]:
        """Fetch current weather for a single station."""
        if not force_refresh and self._is_cache_valid(station_code):
            return self._cache[station_code][1]

        params = {
            "latitude": lat,
            "longitude": lon,
            "current": ",".join(WEATHER_PARAMS),
            "timezone": "Asia/Kolkata",
            "forecast_days": 1,
        }

        data = _get_with_retry(WEATHER_API_BASE, params)
        if not data or "current" not in data:
            logger.error(f"Weather fetch failed for {station_code} ({lat},{lon})")
            return None

        cur = data["current"]

        obs = WeatherObservation(
            station_code=station_code,
            latitude=lat,
            longitude=lon,
            timestamp=datetime.now(timezone.utc).isoformat(),
            temperature_c=float(cur.get("temperature_2m", 25.0)),
            precipitation_mm=float(cur.get("precipitation", 0.0)),
            windspeed_kmh=float(cur.get("windspeed_10m", 0.0)),
            weathercode=int(cur.get("weathercode", 0)),
            visibility_m=float(cur.get("visibility", 10000.0)),
            cloudcover_pct=float(cur.get("cloudcover", 0.0)),
            humidity_pct=float(cur.get("relativehumidity_2m", 50.0)),
            is_adverse=False,
        )
        obs.is_adverse = obs.delay_impact_score() > 0.35

        self._cache[station_code] = (time.time(), obs)
        logger.debug(f"Weather fetched for {station_code}: score={obs.delay_impact_score():.2f}")
        return obs

    def fetch_corridor(self, corridor_code: str) -> Dict[str, WeatherObservation]:
        """Fetch weather for all stations on a corridor."""
        if corridor_code not in CORRIDORS:
            raise ValueError(f"Unknown corridor: {corridor_code}")

        corridor = CORRIDORS[corridor_code]
        results: Dict[str, WeatherObservation] = {}

        for stn in corridor.stations:
            coords = corridor.coordinates.get(stn)
            if not coords:
                logger.warning(f"No coordinates for {stn}, skipping weather")
                continue
            obs = self.fetch_station(stn, coords[0], coords[1])
            if obs:
                results[stn] = obs
            # Small delay to be polite to the free API
            time.sleep(0.3)

        logger.info(
            f"Weather fetched for corridor {corridor_code}: "
            f"{len(results)}/{len(corridor.stations)} stations"
        )
        return results

    def fetch_all_corridors(self) -> Dict[str, WeatherObservation]:
        """Fetch weather for every unique station across all corridors."""
        all_obs: Dict[str, WeatherObservation] = {}
        for corridor_code in CORRIDORS:
            obs = self.fetch_corridor(corridor_code)
            all_obs.update(obs)
        return all_obs

    def get_adverse_stations(self, obs_map: Dict[str, WeatherObservation]) -> List[str]:
        """Return station codes with adverse weather conditions."""
        return [code for code, obs in obs_map.items() if obs.is_adverse]

    def get_delay_impact_vector(
        self, obs_map: Dict[str, WeatherObservation], station_order: List[str]
    ) -> List[float]:
        """
        Return ordered list of delay_impact_score values for given stations.
        Stations with no data default to 0.0.
        """
        return [
            obs_map[s].delay_impact_score() if s in obs_map else 0.0
            for s in station_order
        ]

    def invalidate_cache(self, station_code: Optional[str] = None):
        """Invalidate cache for one station or all stations."""
        if station_code:
            self._cache.pop(station_code, None)
        else:
            self._cache.clear()


# ---------------------------------------------------------------------------
# Convenience singleton
# ---------------------------------------------------------------------------
_client: Optional[WeatherClient] = None


def get_weather_client() -> WeatherClient:
    global _client
    if _client is None:
        _client = WeatherClient()
    return _client


def fetch_station_weather(station_code: str, lat: float, lon: float) -> Optional[WeatherObservation]:
    return get_weather_client().fetch_station(station_code, lat, lon)


def fetch_all_weather() -> Dict[str, WeatherObservation]:
    return get_weather_client().fetch_all_corridors()