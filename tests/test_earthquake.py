"""Tests for the earthquake data layer."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from radar.data.earthquake import (
    EarthquakeEvent,
    EarthquakeDiff,
    EarthquakeFetcher,
    _parse_features,
    diff_events,
)


class TestParseFeatures:
    def test_parses_valid_geojson(self, sample_geojson: dict) -> None:
        events = _parse_features(sample_geojson)
        assert len(events) == 2

    def test_event_fields(self, sample_geojson: dict) -> None:
        events = _parse_features(sample_geojson)
        e = events[0]
        assert e.id == "us7000abc1"
        assert e.magnitude == 4.5
        assert e.depth == 10.5
        assert e.place == "10km NE of Testville, TX"
        assert e.latitude == 29.76
        assert e.longitude == -95.37
        assert e.felt == 12
        assert e.tsunami is False
        assert e.mag_type == "ml"

    def test_time_parsing(self, sample_geojson: dict) -> None:
        events = _parse_features(sample_geojson)
        assert isinstance(events[0].time, datetime)
        assert events[0].time.tzinfo is not None

    def test_empty_features(self) -> None:
        events = _parse_features({"features": []})
        assert events == []

    def test_missing_features_key(self) -> None:
        events = _parse_features({})
        assert events == []

    def test_malformed_feature_skipped(self) -> None:
        bad_geojson = {
            "features": [
                {"id": "bad", "properties": {}, "geometry": {}},  # missing coordinates
            ]
        }
        events = _parse_features(bad_geojson)
        assert len(events) == 0

    def test_null_magnitude(self) -> None:
        geojson = {
            "features": [
                {
                    "id": "null_mag",
                    "properties": {"mag": None, "place": "Test", "time": 1700000000000},
                    "geometry": {"coordinates": [-95.0, 30.0, 5.0]},
                }
            ]
        }
        events = _parse_features(geojson)
        assert len(events) == 1
        assert events[0].magnitude == 0.0


class TestEarthquakeEvent:
    def test_severity_low(self) -> None:
        e = EarthquakeEvent(
            id="1", magnitude=2.0, depth=5, place="Test",
            time=datetime.now(timezone.utc), latitude=0, longitude=0,
        )
        assert e.severity == "low"

    def test_severity_mid(self) -> None:
        e = EarthquakeEvent(
            id="1", magnitude=4.0, depth=5, place="Test",
            time=datetime.now(timezone.utc), latitude=0, longitude=0,
        )
        assert e.severity == "mid"

    def test_severity_high(self) -> None:
        e = EarthquakeEvent(
            id="1", magnitude=6.0, depth=5, place="Test",
            time=datetime.now(timezone.utc), latitude=0, longitude=0,
        )
        assert e.severity == "high"

    def test_severity_severe(self) -> None:
        e = EarthquakeEvent(
            id="1", magnitude=7.5, depth=5, place="Test",
            time=datetime.now(timezone.utc), latitude=0, longitude=0,
        )
        assert e.severity == "severe"

    def test_coords_str(self) -> None:
        e = EarthquakeEvent(
            id="1", magnitude=3, depth=5, place="Test",
            time=datetime.now(timezone.utc), latitude=29.76, longitude=-95.37,
        )
        assert "N" in e.coords_str
        assert "W" in e.coords_str

    def test_time_str_format(self) -> None:
        t = datetime(2024, 11, 14, 12, 30, 0, tzinfo=timezone.utc)
        e = EarthquakeEvent(
            id="1", magnitude=3, depth=5, place="Test",
            time=t, latitude=0, longitude=0,
        )
        assert e.time_str == "2024-11-14 12:30:00 UTC"


class TestDiffEvents:
    def test_all_new(self) -> None:
        new = [
            EarthquakeEvent(
                id="a", magnitude=3, depth=5, place="A",
                time=datetime.now(timezone.utc), latitude=0, longitude=0,
            ),
        ]
        diff = diff_events([], new)
        assert len(diff.added) == 1
        assert diff.removed == []
        assert diff.unchanged == 0

    def test_all_removed(self) -> None:
        old = [
            EarthquakeEvent(
                id="a", magnitude=3, depth=5, place="A",
                time=datetime.now(timezone.utc), latitude=0, longitude=0,
            ),
        ]
        diff = diff_events(old, [])
        assert diff.added == []
        assert diff.removed == ["a"]
        assert diff.unchanged == 0

    def test_mixed(self) -> None:
        t = datetime.now(timezone.utc)
        old = [
            EarthquakeEvent(id="a", magnitude=3, depth=5, place="A", time=t, latitude=0, longitude=0),
            EarthquakeEvent(id="b", magnitude=3, depth=5, place="B", time=t, latitude=0, longitude=0),
        ]
        new = [
            EarthquakeEvent(id="b", magnitude=3, depth=5, place="B", time=t, latitude=0, longitude=0),
            EarthquakeEvent(id="c", magnitude=3, depth=5, place="C", time=t, latitude=0, longitude=0),
        ]
        diff = diff_events(old, new)
        assert len(diff.added) == 1
        assert diff.added[0].id == "c"
        assert diff.removed == ["a"]
        assert diff.unchanged == 1

    def test_no_change(self) -> None:
        t = datetime.now(timezone.utc)
        events = [
            EarthquakeEvent(id="a", magnitude=3, depth=5, place="A", time=t, latitude=0, longitude=0),
        ]
        diff = diff_events(events, events)
        assert diff.added == []
        assert diff.removed == []
        assert diff.unchanged == 1
