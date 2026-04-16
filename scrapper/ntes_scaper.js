"""
ntes_scraper.py — NTES (National Train Enquiry System) website scraper.
Extracts real-time train running status, delays, and station-wise data
by scraping enquiry.indianrail.gov.in with robust session management,
anti-bot rotation, and structured output.

Merged into the pipeline: live_feed.py calls NTESScraper.get_train_status()
as primary source; erail is used as fallback.
"""

import json
import logging
import random
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup

from ml.config import (
    NTES_BASE_URL, NTES_TRAIN_STATUS_URL, NTES_STATION_URL,
    SCRAPER_REQUEST_TIMEOUT, SCRAPER_RETRY_ATTEMPTS, SCRAPER_RETRY_BACKOFF,
    SCRAPER_USER_AGENTS, SCRAPER_RATE_LIMIT_DELAY, SCRAPER_SESSION_ROTATE_EVERY,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class StationPassage:
    """A train's passage record at a single station."""
    station_code: str
    station_name: str
    scheduled_arrival: Optional[str]    # HH:MM
    scheduled_departure: Optional[str]  # HH:MM
    actual_arrival: Optional[str]
    actual_departure: Optional[str]
    delay_arrival_min: float            # negative = early
    delay_departure_min: float
    platform: Optional[str]
    status: str                         # "Departed" | "At Station" | "Expected" | "Skipped"
    distance_km: Optional[float]
    day_of_journey: int                 # 1-indexed


@dataclass
class TrainRunningStatus:
    """Full running status of a train as scraped from NTES."""
    train_number: str
    train_name: str
    journey_date: str           # YYYY-MM-DD
    current_station: str
    current_station_code: str
    last_updated: str           # ISO timestamp
    stations: List[StationPassage] = field(default_factory=list)
    total_delay_min: float = 0.0
    source: str = "ntes"        # "ntes" | "erail" | "railsaarthi" | "simulated"
    raw_html: Optional[str] = None  # stored for debugging

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw_html", None)
        return d

    def stations_with_delay(self) -> List[StationPassage]:
        return [s for s in self.stations if s.delay_arrival_min > 0]


@dataclass
class StationLiveBoard:
    """All trains currently at / expected at a station in next 2 hours."""
    station_code: str
    station_name: str
    fetched_at: str
    entries: List[dict] = field(default_factory=list)  # {train_no, name, arr, dep, delay, platform}


# ---------------------------------------------------------------------------
# Session manager
# ---------------------------------------------------------------------------

class _SessionManager:
    """Rotates requests.Session and User-Agent to reduce blocking."""

    def __init__(self):
        self._session: Optional[requests.Session] = None
        self._request_count = 0
        self._rotate()

    def _rotate(self):
        if self._session:
            self._session.close()
        self._session = requests.Session()
        ua = random.choice(SCRAPER_USER_AGENTS)
        self._session.headers.update({
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": NTES_BASE_URL,
        })
        self._request_count = 0
        logger.debug(f"Session rotated, UA: {ua[:60]}…")

    def get(self, url: str, **kwargs) -> requests.Response:
        self._request_count += 1
        if self._request_count >= SCRAPER_SESSION_ROTATE_EVERY:
            self._rotate()
        kwargs.setdefault("timeout", SCRAPER_REQUEST_TIMEOUT)
        return self._session.get(url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        self._request_count += 1
        if self._request_count >= SCRAPER_SESSION_ROTATE_EVERY:
            self._rotate()
        kwargs.setdefault("timeout", SCRAPER_REQUEST_TIMEOUT)
        return self._session.post(url, **kwargs)


# ---------------------------------------------------------------------------
# HTML parsers
# ---------------------------------------------------------------------------

def _parse_delay(text: Optional[str]) -> float:
    """Parse delay text like '+12 min', '-5 min', 'Right Time' → float minutes."""
    if not text:
        return 0.0
    text = text.strip().lower()
    if "right time" in text or text in ("", "-", "n/a"):
        return 0.0
    m = re.search(r"([+-]?\d+)", text)
    if m:
        return float(m.group(1))
    return 0.0


def _parse_time(text: Optional[str]) -> Optional[str]:
    """Normalise time strings to HH:MM."""
    if not text:
        return None
    text = text.strip()
    m = re.search(r"(\d{1,2})[:\.](\d{2})", text)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    return None


def _parse_ntes_train_status(html: str, train_no: str) -> Optional[TrainRunningStatus]:
    """
    Parse the NTES train running status HTML page.
    The site uses table-based layout; we parse the schedule table.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Extract train name from page title / header
    train_name = train_no
    title_el = soup.find("div", class_=re.compile(r"train.*name|trainName|heading", re.I))
    if not title_el:
        title_el = soup.find("h2") or soup.find("h3")
    if title_el:
        train_name = title_el.get_text(strip=True)

    # Find schedule table — look for table rows with station data
    stations: List[StationPassage] = []
    current_station = ""
    current_station_code = ""

    # NTES uses a table with class "table" or id containing "station"
    tables = soup.find_all("table")
    schedule_table = None
    for tbl in tables:
        headers = [th.get_text(strip=True).lower() for th in tbl.find_all("th")]
        if any(h in headers for h in ["station", "stn", "arr", "dep", "delay"]):
            schedule_table = tbl
            break

    if not schedule_table:
        # Fallback: look for divs with station data (newer NTES AJAX layout)
        schedule_table = soup.find("div", id=re.compile(r"station|schedule|timetable", re.I))

    if schedule_table:
        rows = schedule_table.find_all("tr")
        for i, row in enumerate(rows[1:], 1):  # skip header
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if len(cells) < 4:
                continue

            # Typical columns: Day | Station | Arr | Dep | Halt | Dist | PF | Status | Delay
            stn_code = ""
            stn_name = cells[1] if len(cells) > 1 else ""

            # Extract station code from anchor or bracket notation
            stn_anchor = row.find("a")
            if stn_anchor:
                href = stn_anchor.get("href", "")
                code_m = re.search(r"stn[Cc]ode=([A-Z]+)", href)
                stn_code = code_m.group(1) if code_m else ""
                stn_name = stn_anchor.get_text(strip=True)

            # Try to find code in parentheses
            if not stn_code:
                p = re.search(r"\(([A-Z]{2,6})\)", stn_name)
                stn_code = p.group(1) if p else stn_name[:4].upper()

            sched_arr = _parse_time(cells[2] if len(cells) > 2 else None)
            sched_dep = _parse_time(cells[3] if len(cells) > 3 else None)
            dist_str = cells[5] if len(cells) > 5 else ""
            pf_str = cells[6] if len(cells) > 6 else None
            status_str = cells[7] if len(cells) > 7 else "Expected"
            delay_str = cells[8] if len(cells) > 8 else None

            try:
                dist = float(re.sub(r"[^\d.]", "", dist_str)) if dist_str else None
            except ValueError:
                dist = None

            delay = _parse_delay(delay_str)
            actual_arr = None
            actual_dep = None
            if sched_arr and delay:
                # Approximate actual time (full parsing would need HH:MM arithmetic)
                actual_arr = sched_arr  # simplified
            if sched_dep and delay:
                actual_dep = sched_dep

            # Detect current station (highlighted row / specific class)
            row_classes = " ".join(row.get("class", [])).lower()
            is_current = any(k in row_classes for k in ["current", "running", "active", "highlight"])

            passage = StationPassage(
                station_code=stn_code,
                station_name=stn_name,
                scheduled_arrival=sched_arr,
                scheduled_departure=sched_dep,
                actual_arrival=actual_arr,
                actual_departure=actual_dep,
                delay_arrival_min=delay,
                delay_departure_min=delay,
                platform=pf_str,
                status=status_str,
                distance_km=dist,
                day_of_journey=int(cells[0]) if cells[0].isdigit() else 1,
            )
            stations.append(passage)

            if is_current:
                current_station = stn_name
                current_station_code = stn_code

    # Overall delay is the delay at the latest departed/at-station row
    total_delay = 0.0
    for s in reversed(stations):
        if s.status.lower() in ("departed", "at station"):
            total_delay = s.delay_departure_min
            if not current_station:
                current_station = s.station_name
                current_station_code = s.station_code
            break

    status = TrainRunningStatus(
        train_number=train_no,
        train_name=train_name,
        journey_date=date.today().isoformat(),
        current_station=current_station or "Unknown",
        current_station_code=current_station_code,
        last_updated=datetime.now(timezone.utc).isoformat(),
        stations=stations,
        total_delay_min=total_delay,
        source="ntes",
        raw_html=None,
    )
    return status


def _parse_ntes_station_board(html: str, station_code: str) -> Optional[StationLiveBoard]:
    """Parse NTES station live board HTML."""
    soup = BeautifulSoup(html, "html.parser")

    station_name = station_code
    h = soup.find(["h2", "h3", "h4"])
    if h:
        station_name = h.get_text(strip=True)

    entries = []
    tables = soup.find_all("table")
    for tbl in tables:
        rows = tbl.find_all("tr")
        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 4:
                continue
            entries.append({
                "train_no": cells[0],
                "train_name": cells[1] if len(cells) > 1 else "",
                "arr": _parse_time(cells[2]) if len(cells) > 2 else None,
                "dep": _parse_time(cells[3]) if len(cells) > 3 else None,
                "delay_min": _parse_delay(cells[4] if len(cells) > 4 else None),
                "platform": cells[5] if len(cells) > 5 else None,
            })

    return StationLiveBoard(
        station_code=station_code,
        station_name=station_name,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        entries=entries,
    )


# ---------------------------------------------------------------------------
# Main scraper class
# ---------------------------------------------------------------------------

class NTESScraper:
    """
    High-level NTES scraper.
    Primary data source for real-time train running status.
    Provides fallback chain: NTES → erail → railsaarthi → simulated.
    """

    def __init__(self):
        self._session_mgr = _SessionManager()
        self._request_count = 0
        self._last_request_time = 0.0

    def _rate_limit(self):
        """Enforce rate limit between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < SCRAPER_RATE_LIMIT_DELAY:
            time.sleep(SCRAPER_RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def _get(self, url: str, params: Optional[dict] = None) -> Optional[requests.Response]:
        """Fetch URL with retry logic."""
        self._rate_limit()
        for attempt in range(SCRAPER_RETRY_ATTEMPTS):
            try:
                resp = self._session_mgr.get(url, params=params)
                resp.raise_for_status()
                self._request_count += 1
                logger.debug(f"GET {url} → {resp.status_code} ({len(resp.content)} bytes)")
                return resp
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    wait = SCRAPER_RETRY_BACKOFF * (3 ** attempt)
                    logger.warning(f"Rate limited, waiting {wait}s")
                    time.sleep(wait)
                else:
                    logger.warning(f"HTTP error attempt {attempt+1}: {e}")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Connection error attempt {attempt+1}: {e}")
                time.sleep(SCRAPER_RETRY_BACKOFF * (2 ** attempt))
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on attempt {attempt+1} for {url}")
                time.sleep(SCRAPER_RETRY_BACKOFF)
        logger.error(f"All {SCRAPER_RETRY_ATTEMPTS} attempts failed for {url}")
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_train_status(
        self, train_no: str, journey_date: Optional[str] = None
    ) -> Optional[TrainRunningStatus]:
        """
        Fetch live running status for a train.
        Tries NTES first, falls back to erail, then railsaarthi.
        """
        if not journey_date:
            journey_date = date.today().strftime("%d-%m-%Y")

        status = self._fetch_ntes_status(train_no, journey_date)
        if status and status.stations:
            return status

        logger.info(f"NTES failed for {train_no}, trying erail fallback")
        status = self._fetch_erail_status(train_no, journey_date)
        if status and status.stations:
            return status

        logger.info(f"erail failed for {train_no}, trying railsaarthi fallback")
        status = self._fetch_railsaarthi_status(train_no)
        return status

    def get_station_board(self, station_code: str) -> Optional[StationLiveBoard]:
        """Fetch live departure/arrival board for a station."""
        url = NTES_STATION_URL.format(station_code=station_code)
        resp = self._get(url)
        if not resp:
            return None
        board = _parse_ntes_station_board(resp.text, station_code)
        return board

    def get_corridor_delays(self, station_codes: List[str]) -> Dict[str, float]:
        """
        Bulk fetch current delays for all trains passing through stations.
        Returns dict: {train_no: current_delay_min}
        """
        delays: Dict[str, float] = {}
        for stn in station_codes:
            board = self.get_station_board(stn)
            if board:
                for entry in board.entries:
                    train_no = entry.get("train_no", "")
                    if train_no and train_no not in delays:
                        delays[train_no] = float(entry.get("delay_min", 0.0))
        return delays

    # ------------------------------------------------------------------
    # Private fetchers
    # ------------------------------------------------------------------

    def _fetch_ntes_status(
        self, train_no: str, journey_date: str
    ) -> Optional[TrainRunningStatus]:
        """Scrape NTES train running status page."""
        # NTES uses a form POST or GET with specific params
        url = f"{NTES_BASE_URL}q"
        params = {
            "opt": "TR",
            "trainNo": train_no,
            "dt": journey_date,
        }
        resp = self._get(url, params=params)
        if not resp:
            return None

        try:
            status = _parse_ntes_train_status(resp.text, train_no)
            if status:
                status.source = "ntes"
            return status
        except Exception as e:
            logger.error(f"NTES parse error for {train_no}: {e}", exc_info=True)
            return None

    def _fetch_erail_status(
        self, train_no: str, journey_date: str
    ) -> Optional[TrainRunningStatus]:
        """
        Fetch from erail API as fallback.
        erail returns JSON with train running status.
        """
        from ml.config import ERAIL_LIVE
        # erail expects date in YYYYMMDD
        date_fmt = ""
        try:
            dt = datetime.strptime(journey_date, "%d-%m-%Y")
            date_fmt = dt.strftime("%Y%m%d")
        except ValueError:
            date_fmt = date.today().strftime("%Y%m%d")

        url = ERAIL_LIVE.format(train_no=train_no, date=date_fmt)
        resp = self._get(url)
        if not resp:
            return None

        try:
            data = resp.json()
        except Exception:
            # erail sometimes returns XML or HTML
            return self._parse_erail_html(resp.text, train_no)

        return self._parse_erail_json(data, train_no, journey_date)

    def _parse_erail_json(
        self, data: dict, train_no: str, journey_date: str
    ) -> Optional[TrainRunningStatus]:
        """Parse erail JSON response."""
        if not data or "Trains" not in data:
            return None

        trains = data.get("Trains", [])
        if not trains:
            return None

        train_data = trains[0]
        stations = []
        for stn in train_data.get("Stations", []):
            delay_a = float(stn.get("delayArr", 0) or 0)
            delay_d = float(stn.get("delayDep", 0) or 0)
            passage = StationPassage(
                station_code=stn.get("stationCode", ""),
                station_name=stn.get("stationName", ""),
                scheduled_arrival=_parse_time(stn.get("arrivalTime")),
                scheduled_departure=_parse_time(stn.get("departureTime")),
                actual_arrival=_parse_time(stn.get("actualArrival")),
                actual_departure=_parse_time(stn.get("actualDeparture")),
                delay_arrival_min=delay_a,
                delay_departure_min=delay_d,
                platform=stn.get("platform"),
                status=stn.get("status", "Expected"),
                distance_km=stn.get("distance"),
                day_of_journey=int(stn.get("dayCount", 1)),
            )
            stations.append(passage)

        total_delay = max((s.delay_departure_min for s in stations), default=0.0)
        current = next(
            (s for s in stations if s.status.lower() in ("at station", "departed")),
            stations[-1] if stations else None,
        )

        return TrainRunningStatus(
            train_number=train_no,
            train_name=train_data.get("trainName", train_no),
            journey_date=journey_date,
            current_station=current.station_name if current else "",
            current_station_code=current.station_code if current else "",
            last_updated=datetime.now(timezone.utc).isoformat(),
            stations=stations,
            total_delay_min=total_delay,
            source="erail",
        )

    def _parse_erail_html(
        self, html: str, train_no: str
    ) -> Optional[TrainRunningStatus]:
        """Fallback: parse erail HTML response."""
        return _parse_ntes_train_status(html, train_no)

    def _fetch_railsaarthi_status(
        self, train_no: str
    ) -> Optional[TrainRunningStatus]:
        """Last resort: railsaarthi.in scraping."""
        from ml.config import RAILSAARTHI_BASE
        url = RAILSAARTHI_BASE.format(train_no=train_no)
        resp = self._get(url)
        if not resp:
            return None
        try:
            status = _parse_ntes_train_status(resp.text, train_no)
            if status:
                status.source = "railsaarthi"
            return status
        except Exception as e:
            logger.error(f"Railsaarthi parse error for {train_no}: {e}")
            return None

    # ------------------------------------------------------------------
    # Bulk helpers for the live feed
    # ------------------------------------------------------------------

    def bulk_train_status(
        self, train_numbers: List[str]
    ) -> Dict[str, TrainRunningStatus]:
        """Fetch status for multiple trains; returns dict keyed by train_no."""
        results = {}
        for tn in train_numbers:
            status = self.get_train_status(tn)
            if status:
                results[tn] = status
            time.sleep(SCRAPER_RATE_LIMIT_DELAY)
        return results

    def current_delay_for_train(self, train_no: str) -> float:
        """Quick helper: current delay in minutes for a train."""
        status = self.get_train_status(train_no)
        if status:
            return status.total_delay_min
        return 0.0

    @property
    def total_requests_made(self) -> int:
        return self._request_count


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_scraper: Optional[NTESScraper] = None


def get_ntes_scraper() -> NTESScraper:
    global _scraper
    if _scraper is None:
        _scraper = NTESScraper()
    return _scraper