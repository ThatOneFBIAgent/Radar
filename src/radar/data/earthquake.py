"""
Earthquake data fetcher — USGS GeoJSON API.

Provides async fetching, diff-based updates, and typed event models.
Optionally delegates JSON parsing to the Rust accelerator module.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import aiohttp

logger = logging.getLogger(__name__)

# Try Rust accelerator, fall back to pure Python───────────
try:
    from radar_accel import parse_geojson as _rust_parse, filter_by_magnitude as _rust_filter
    _USE_RUST = True
    logger.info("Rust accelerator (radar_accel) loaded")
except ImportError:
    _USE_RUST = False
    logger.debug("Rust accelerator not available — using pure Python parser")


# Data model───────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class EarthquakeEvent:
    """Single earthquake event from the USGS feed."""

    id: str
    magnitude: float
    depth: float           # km
    place: str
    time: datetime
    latitude: float
    longitude: float
    url: str = ""
    felt: int | None = None
    tsunami: bool = False
    mag_type: str = ""

    @property
    def time_str(self) -> str:
        """Human-readable UTC timestamp."""
        return self.time.strftime("%Y-%m-%d %H:%M:%S UTC")

    @property
    def coords_str(self) -> str:
        """Formatted lat/lon string."""
        lat_dir = "N" if self.latitude >= 0 else "S"
        lon_dir = "E" if self.longitude >= 0 else "W"
        return f"{abs(self.latitude):.3f}°{lat_dir}  {abs(self.longitude):.3f}°{lon_dir}"

    @property
    def severity(self) -> str:
        """Severity category based on magnitude."""
        if self.magnitude < 3.0:
            return "low"
        elif self.magnitude < 5.0:
            return "mid"
        elif self.magnitude < 7.0:
            return "high"
        return "severe"


# Pure-Python parser───────────────────────────────────────
def _parse_features(raw_json: dict) -> list[EarthquakeEvent]:
    """Parse USGS GeoJSON features into EarthquakeEvent list."""
    events: list[EarthquakeEvent] = []
    features = raw_json.get("features", [])

    for feat in features:
        try:
            props = feat["properties"]
            geom = feat["geometry"]
            coords = geom["coordinates"]  # [lon, lat, depth]

            ts = props.get("time", 0)
            event_time = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)

            events.append(EarthquakeEvent(
                id=feat["id"],
                magnitude=float(props.get("mag", 0) or 0),
                depth=float(coords[2]) if len(coords) > 2 else 0.0,
                place=props.get("place", "Unknown"),
                time=event_time,
                latitude=float(coords[1]),
                longitude=float(coords[0]),
                url=props.get("url", ""),
                felt=props.get("felt"),
                tsunami=bool(props.get("tsunami", 0)),
                mag_type=props.get("magType", ""),
            ))
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Skipping malformed earthquake feature: %s", e)
            continue

    return events


# Diff engine──────────────────────────────────────────────
@dataclass
class EarthquakeDiff:
    """Result of comparing two event snapshots."""

    added: list[EarthquakeEvent] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)    # IDs
    unchanged: int = 0


def diff_events(
    old: list[EarthquakeEvent],
    new: list[EarthquakeEvent],
) -> EarthquakeDiff:
    """Compute the diff between old and new event lists."""
    old_ids = {e.id for e in old}
    new_ids = {e.id for e in new}
    new_map = {e.id: e for e in new}

    added = [new_map[eid] for eid in (new_ids - old_ids)]
    removed = list(old_ids - new_ids)
    unchanged = len(old_ids & new_ids)

    return EarthquakeDiff(added=added, removed=removed, unchanged=unchanged)


# Fetcher──────────────────────────────────────────────────
class EarthquakeFetcher:
    """Async earthquake data fetcher with diff-based updates.

    Usage:
        fetcher = EarthquakeFetcher(feed_url)
        events, diff = await fetcher.fetch()
    """

    def __init__(self, feed_url: str, max_display: int = 100, mock_feed_file: str = "") -> None:
        self._feed_url = feed_url
        self._max_display = max_display
        self._mock_feed_file = mock_feed_file
        self._previous: list[EarthquakeEvent] = []
        self._session: aiohttp.ClientSession | None = None
        self._last_fetch: float = 0.0

        # Mock drip state: pre-parsed events released one per fetch
        self._mock_pool: list[EarthquakeEvent] = []
        self._mock_released: list[EarthquakeEvent] = []
        self._mock_loaded = False

        if self._mock_feed_file:
            logger.warning("DEBUG MODE: Using mock feed file: %s", self._mock_feed_file)

    def _load_mock_pool(self) -> None:
        """Pre-load and parse the mock GeoJSON file into the drip pool."""
        import json
        from pathlib import Path

        mock_path = Path(self._mock_feed_file)
        if not mock_path.is_absolute():
            from radar.config import BASE_DIR
            mock_path = BASE_DIR / mock_path

        try:
            with open(mock_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            all_events = _parse_features(raw)
            # Reverse so we pop from the end (oldest first, newest last)
            self._mock_pool = list(reversed(all_events))
            self._mock_loaded = True
            logger.info(
                "Mock feed loaded: %d events queued for drip release", len(self._mock_pool)
            )
        except FileNotFoundError:
            logger.error("Mock feed file not found: %s", mock_path)
            self._mock_loaded = True  # Don't retry
        except Exception as e:
            logger.error("Failed to load mock feed: %s", e)
            self._mock_loaded = True

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"User-Agent": "Radar/0.1 (earthquake-monitor)"},
            )
        return self._session

    async def fetch(self) -> tuple[list[EarthquakeEvent], EarthquakeDiff]:
        """Fetch latest events and return (full_list, diff).

        On network errors, returns the previous snapshot with an empty diff.
        If a mock_feed_file is configured, drips one event per fetch cycle.
        """
        # ── Mock drip path ──
        if self._mock_feed_file:
            if not self._mock_loaded:
                self._load_mock_pool()

            if self._mock_pool:
                # Release one event from the pool
                new_event = self._mock_pool.pop()
                self._mock_released.append(new_event)
                logger.info(
                    "Mock drip: released M%.1f '%s' (%d remaining)",
                    new_event.magnitude, new_event.place, len(self._mock_pool),
                )
            
            self._last_fetch = time.monotonic()
            events = list(self._mock_released)
            events.sort(key=lambda e: e.time, reverse=True)
            events = events[:self._max_display]

            diff = diff_events(self._previous, events)
            self._previous = events
            return events, diff

        else:
            # ── Live USGS feed ──
            session = await self._ensure_session()

            try:
                async with session.get(self._feed_url) as resp:
                    resp.raise_for_status()
                    raw = await resp.json(content_type=None)
                    self._last_fetch = time.monotonic()
            except aiohttp.ClientError as e:
                logger.error("Earthquake fetch failed: %s", e)
                return self._previous, EarthquakeDiff()
            except Exception as e:
                logger.error("Unexpected earthquake fetch error: %s", e)
                return self._previous, EarthquakeDiff()

        # Parse
        if _USE_RUST:
            try:
                import json as _json
                # Rust returns a list of QuakeEvent objects (which have time_ms instead of time)
                raw_events = _rust_parse(_json.dumps(raw))
                events = [
                    EarthquakeEvent(
                        id=e.id,
                        magnitude=e.magnitude,
                        depth=e.depth,
                        place=e.place,
                        time=datetime.fromtimestamp(e.time_ms / 1000, tz=timezone.utc),
                        latitude=e.latitude,
                        longitude=e.longitude,
                        url=e.url,
                        felt=e.felt,
                        tsunami=e.tsunami,
                        mag_type=e.mag_type,
                    )
                    for e in raw_events
                ]
            except Exception as e:
                logger.warning("Rust parser failed, falling back to Python: %s", e)
                events = _parse_features(raw)
        else:
            events = _parse_features(raw)


        # Sort by time descending, limit
        events.sort(key=lambda e: e.time, reverse=True)
        events = events[: self._max_display]

        # Diff
        diff = diff_events(self._previous, events)
        self._previous = events

        if diff.added:
            logger.info(
                "Earthquake update: +%d new, -%d removed, %d unchanged",
                len(diff.added), len(diff.removed), diff.unchanged,
            )

        return events, diff

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
