"""Tests for Rust accelerator fallback behavior.

Verifies that the pure-Python parser produces equivalent results
to what the Rust module would return, ensuring correctness of
the fallback path.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from radar.data.earthquake import _parse_features, diff_events, EarthquakeEvent


class TestPurePythonParsing:
    """Ensure the pure-Python parser works correctly as a fallback."""

    def test_full_feature_parsing(self, sample_geojson: dict) -> None:
        events = _parse_features(sample_geojson)
        assert len(events) == 2

        # First event
        e1 = events[0]
        assert e1.id == "us7000abc1"
        assert e1.magnitude == 4.5
        assert e1.depth == 10.5
        assert e1.latitude == 29.76
        assert e1.longitude == -95.37

        # Second event
        e2 = events[1]
        assert e2.id == "us7000abc2"
        assert e2.magnitude == 2.1

    def test_graceful_malformed_handling(self) -> None:
        """Parser should skip malformed entries without crashing."""
        mixed = {
            "features": [
                {
                    "id": "good",
                    "properties": {"mag": 3.0, "place": "Test", "time": 1700000000000},
                    "geometry": {"coordinates": [-95, 30, 5]},
                },
                # Missing geometry.coordinates
                {
                    "id": "bad",
                    "properties": {"mag": 2.0},
                    "geometry": {},
                },
            ]
        }
        events = _parse_features(mixed)
        assert len(events) == 1
        assert events[0].id == "good"


class TestDiffConsistency:
    """Verify diff engine produces correct results."""

    def test_diffing_large_sets(self) -> None:
        t = datetime.now(timezone.utc)
        old = [
            EarthquakeEvent(id=f"e{i}", magnitude=3, depth=5, place=f"P{i}",
                          time=t, latitude=0, longitude=0)
            for i in range(100)
        ]
        new = [
            EarthquakeEvent(id=f"e{i}", magnitude=3, depth=5, place=f"P{i}",
                          time=t, latitude=0, longitude=0)
            for i in range(50, 150)  # 50 overlap, 50 new
        ]

        diff = diff_events(old, new)
        assert len(diff.added) == 50
        assert len(diff.removed) == 50
        assert diff.unchanged == 50
