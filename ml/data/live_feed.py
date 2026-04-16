"""
live_feed.py — Real-time live data feed.
2-second polling loop across 3 corridors.
Primary: NTES scraper. Fallback: erail API.
Publishes to Kafka and in-memory queue for inference.
"""

import json
import logging
import queue
import threading
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Callable, Dict, List, Optional

import requests

from ml.config import (
    CORRIDORS, TRAINS, ERAIL_LIVE, LIVE_FEED_INTERVAL_SEC,
    NTES_SCRAPE_INTERVAL_SEC, KAFKA_TOPIC_LIVE, KAFKA_BOOTSTRAP,
    SCRAPER_REQUEST_TIMEOUT, SCRAPER_USER_AGENTS,
)
from ml.data.ntes_scraper import NTESScraper, TrainRunningStatus, get_ntes_scraper

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LiveEvent — the canonical real-time record
# ---------------------------------------------------------------------------

@dataclass
class LiveEvent:
    train_no: str
    train_name: str
    station_code: str
    station_name: str
    delay_min: float
    timestamp: str
    source: str          # "ntes" | "erail" | "railsaarthi" | "cached"
    corridor: str
    is_running: bool = True
    confidence: float = 1.0   # 0-1: how reliable is this reading

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


# ---------------------------------------------------------------------------
# Kafka producer (optional — graceful no-op if kafka-python not installed)
# ---------------------------------------------------------------------------

def _make_kafka_producer():
    try:
        from kafka import KafkaProducer
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",
            retries=3,
            request_timeout_ms=5000,
        )
        logger.info(f"Kafka producer connected to {KAFKA_BOOTSTRAP}")
        return producer
    except ImportError:
        logger.warning("kafka-python not installed — Kafka publishing disabled")
        return None
    except Exception as e:
        logger.warning(f"Kafka connection failed ({e}) — publishing disabled")
        return None


# ---------------------------------------------------------------------------
# LiveFeed
# ---------------------------------------------------------------------------

class LiveFeed:
    """
    Polls NTES scraper (primary) and erail (fallback) for live train running
    status across all 3 corridors every LIVE_FEED_INTERVAL_SEC seconds.

    Events are:
    1. Published to Kafka topic `rail.live.delays`
    2. Put into an in-memory queue for local inference consumers
    3. Accessible via get_latest_delays()
    """

    def __init__(
        self,
        on_event: Optional[Callable[[LiveEvent], None]] = None,
        use_kafka: bool = True,
    ):
        self._scraper: NTESScraper = get_ntes_scraper()
        self._on_event = on_event
        self._event_queue: queue.Queue = queue.Queue(maxsize=10_000)
        self._latest: Dict[str, LiveEvent] = {}  # train_no -> latest event
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._kafka = _make_kafka_producer() if use_kafka else None
        self._poll_count = 0
        self._error_count = 0

        # Track which trains to monitor (all corridor trains)
        self._monitored_trains: List[str] = list(TRAINS.keys())

        # NTES scraping is slower — separate thread, longer interval
        self._ntes_thread: Optional[threading.Thread] = None
        self._ntes_cache: Dict[str, TrainRunningStatus] = {}
        self._ntes_lock = threading.RLock()

    # ------------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------------

    def start(self) -> "LiveFeed":
        """Start background polling threads."""
        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._poll_loop, name="live-feed-erail", daemon=True
        )
        self._thread.start()

        self._ntes_thread = threading.Thread(
            target=self._ntes_scrape_loop, name="live-feed-ntes", daemon=True
        )
        self._ntes_thread.start()

        logger.info(
            f"LiveFeed started — monitoring {len(self._monitored_trains)} trains "
            f"across {len(CORRIDORS)} corridors"
        )
        return self

    def stop(self):
        """Stop all background threads gracefully."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        if self._ntes_thread:
            self._ntes_thread.join(timeout=10)
        if self._kafka:
            try:
                self._kafka.flush(timeout=5)
                self._kafka.close()
            except Exception:
                pass
        logger.info(f"LiveFeed stopped. Total polls: {self._poll_count}, errors: {self._error_count}")

    # ------------------------------------------------------------------
    # Main polling loop (erail — fast, every 2s)
    # ------------------------------------------------------------------

    def _poll_loop(self):
        """Fast 2-second erail polling loop."""
        session = requests.Session()
        session.headers.update({
            "User-Agent": SCRAPER_USER_AGENTS[0],
            "Accept": "application/json, text/plain, */*",
        })

        while not self._stop_event.is_set():
            loop_start = time.time()
            self._poll_count += 1

            for train_no in self._monitored_trains:
                if self._stop_event.is_set():
                    break
                try:
                    event = self._fetch_erail_event(session, train_no)
                    if event:
                        self._dispatch_event(event)
                except Exception as e:
                    self._error_count += 1
                    logger.debug(f"erail poll error for {train_no}: {e}")

            elapsed = time.time() - loop_start
            sleep_time = max(0, LIVE_FEED_INTERVAL_SEC - elapsed)
            self._stop_event.wait(timeout=sleep_time)

    def _fetch_erail_event(
        self, session: requests.Session, train_no: str
    ) -> Optional[LiveEvent]:
        """Fetch current status from erail for one train."""
        today = date.today().strftime("%Y%m%d")
        url = ERAIL_LIVE.format(train_no=train_no, date=today)
        try:
            resp = session.get(url, timeout=SCRAPER_REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.JSONDecodeError:
            return None
        except requests.exceptions.RequestException:
            return None

        # erail response structure
        trains = data.get("Trains", []) if isinstance(data, dict) else []
        if not trains:
            return self._use_ntes_cache(train_no)

        t = trains[0]
        current_station = ""
        current_code = ""
        delay = 0.0

        for stn in t.get("Stations", []):
            status = stn.get("status", "").lower()
            if status in ("at station", "departed"):
                current_station = stn.get("stationName", "")
                current_code = stn.get("stationCode", "")
                delay = float(stn.get("delayDep", 0) or 0)

        if not current_code:
            return self._use_ntes_cache(train_no)

        corridor = self._train_corridor(train_no)
        train_cfg = TRAINS.get(train_no)

        return LiveEvent(
            train_no=train_no,
            train_name=t.get("trainName", train_no) or (train_cfg.name if train_cfg else train_no),
            station_code=current_code,
            station_name=current_station,
            delay_min=delay,
            timestamp=datetime.now(timezone.utc).isoformat(),
            source="erail",
            corridor=corridor,
            is_running=True,
            confidence=0.9,
        )

    # ------------------------------------------------------------------
    # NTES scraping loop (slower, more authoritative)
    # ------------------------------------------------------------------

    def _ntes_scrape_loop(self):
        """NTES scraping every NTES_SCRAPE_INTERVAL_SEC seconds."""
        while not self._stop_event.is_set():
            for train_no in self._monitored_trains:
                if self._stop_event.is_set():
                    break
                try:
                    status = self._scraper.get_train_status(train_no)
                    if status:
                        with self._ntes_lock:
                            self._ntes_cache[train_no] = status
                        event = self._ntes_status_to_event(status)
                        if event:
                            self._dispatch_event(event)
                except Exception as e:
                    logger.debug(f"NTES scrape error for {train_no}: {e}")
            self._stop_event.wait(timeout=NTES_SCRAPE_INTERVAL_SEC)

    def _ntes_status_to_event(self, status: TrainRunningStatus) -> Optional[LiveEvent]:
        """Convert NTES TrainRunningStatus to LiveEvent."""
        if not status.current_station_code:
            return None
        corridor = self._train_corridor(status.train_number)
        return LiveEvent(
            train_no=status.train_number,
            train_name=status.train_name,
            station_code=status.current_station_code,
            station_name=status.current_station,
            delay_min=status.total_delay_min,
            timestamp=status.last_updated,
            source=status.source,
            corridor=corridor,
            is_running=True,
            confidence=1.0,  # NTES is authoritative
        )

    def _use_ntes_cache(self, train_no: str) -> Optional[LiveEvent]:
        """Return last known NTES status for a train."""
        with self._ntes_lock:
            status = self._ntes_cache.get(train_no)
        if status:
            event = self._ntes_status_to_event(status)
            if event:
                event.source = "cached"
                event.confidence = 0.7
            return event
        return None

    # ------------------------------------------------------------------
    # Event dispatch
    # ------------------------------------------------------------------

    def _dispatch_event(self, event: LiveEvent):
        """Route event to queue, Kafka, and callback."""
        with self._lock:
            self._latest[event.train_no] = event

        # In-memory queue
        try:
            self._event_queue.put_nowait(event)
        except queue.Full:
            # Drop oldest
            try:
                self._event_queue.get_nowait()
                self._event_queue.put_nowait(event)
            except queue.Empty:
                pass

        # Kafka
        if self._kafka:
            try:
                self._kafka.send(KAFKA_TOPIC_LIVE, event.to_dict())
            except Exception as e:
                logger.debug(f"Kafka send error: {e}")

        # Callback
        if self._on_event:
            try:
                self._on_event(event)
            except Exception as e:
                logger.error(f"on_event callback error: {e}")

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def get_latest_delays(self) -> Dict[str, float]:
        """Return {train_no: delay_min} for all recently seen trains."""
        with self._lock:
            return {k: v.delay_min for k, v in self._latest.items()}

    def get_latest_events(self) -> Dict[str, LiveEvent]:
        with self._lock:
            return dict(self._latest)

    def get_corridor_delays(self, corridor_key: str) -> Dict[str, float]:
        """Return delays for trains on a specific corridor."""
        corridor = CORRIDORS.get(corridor_key)
        if not corridor:
            return {}
        with self._lock:
            return {
                k: v.delay_min
                for k, v in self._latest.items()
                if v.corridor == corridor_key
            }

    def get_station_delays(self, station_codes: List[str]) -> Dict[str, float]:
        """Return max delay seen at each station across all trains."""
        station_delay: Dict[str, float] = {}
        with self._lock:
            for event in self._latest.values():
                if event.station_code in station_codes:
                    prev = station_delay.get(event.station_code, 0.0)
                    station_delay[event.station_code] = max(prev, event.delay_min)
        return station_delay

    def consume_event(self, timeout: float = 1.0) -> Optional[LiveEvent]:
        """Blocking consume from in-memory queue."""
        try:
            return self._event_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain_queue(self) -> List[LiveEvent]:
        """Non-blocking drain all pending events."""
        events = []
        while True:
            try:
                events.append(self._event_queue.get_nowait())
            except queue.Empty:
                break
        return events

    def get_ntes_status(self, train_no: str) -> Optional[TrainRunningStatus]:
        """Get the raw NTES status for a train."""
        with self._ntes_lock:
            return self._ntes_cache.get(train_no)

    @property
    def stats(self) -> dict:
        return {
            "poll_count": self._poll_count,
            "error_count": self._error_count,
            "monitored_trains": len(self._monitored_trains),
            "active_events": len(self._latest),
            "queue_size": self._event_queue.qsize(),
            "kafka_enabled": self._kafka is not None,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _train_corridor(train_no: str) -> str:
        cfg = TRAINS.get(train_no)
        return cfg.corridor if cfg else "unknown"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_feed: Optional[LiveFeed] = None


def get_live_feed(use_kafka: bool = True) -> LiveFeed:
    global _feed
    if _feed is None:
        _feed = LiveFeed(use_kafka=use_kafka)
    return _feed