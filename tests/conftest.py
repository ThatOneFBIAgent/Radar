"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def sample_geojson() -> dict:
    """Minimal valid USGS GeoJSON response."""
    return {
        "type": "FeatureCollection",
        "metadata": {"generated": 1700000000000, "count": 2},
        "features": [
            {
                "type": "Feature",
                "id": "us7000abc1",
                "properties": {
                    "mag": 4.5,
                    "place": "10km NE of Testville, TX",
                    "time": 1700000000000,
                    "magType": "ml",
                    "felt": 12,
                    "tsunami": 0,
                    "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000abc1",
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [-95.37, 29.76, 10.5],
                },
            },
            {
                "type": "Feature",
                "id": "us7000abc2",
                "properties": {
                    "mag": 2.1,
                    "place": "5km S of Smalltown, CA",
                    "time": 1699999000000,
                    "magType": "md",
                    "felt": None,
                    "tsunami": 0,
                    "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000abc2",
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [-118.24, 34.05, 5.0],
                },
            },
        ],
    }


@pytest.fixture
def sample_weather_response() -> dict:
    """Minimal valid Open-Meteo response."""
    return {
        "latitude": 29.76,
        "longitude": -95.36,
        "elevation": 12.0,
        "current": {
            "time": "2024-11-14T12:00",
            "temperature_2m": 22.5,
            "apparent_temperature": 21.0,
            "relative_humidity_2m": 65,
            "wind_speed_10m": 15.5,
            "wind_direction_10m": 180,
            "wind_gusts_10m": 25.0,
            "surface_pressure": 1013.25,
            "cloud_cover": 40,
            "precipitation": 0.0,
            "weather_code": 2,
            "is_day": 1,
        },
    }


@pytest.fixture
def tmp_themes_dir(tmp_path: Path) -> Path:
    """Create a temporary themes directory with a test theme."""
    themes_dir = tmp_path / "themes"
    themes_dir.mkdir()

    theme = {
        "name": "Test",
        "description": "Test theme",
        "colors": {
            "background": "#0D0D0D",
            "surface": "#1A1A2E",
            "surface_alt": "#16213E",
            "primary": "#00D4FF",
            "accent": "#FF6B35",
            "text": "#E0E0E0",
            "text_dim": "#666680",
            "text_bright": "#FFFFFF",
            "success": "#00FF88",
            "warning": "#FFD700",
            "danger": "#FF3366",
            "border": "#2A2A4A",
            "header": "#0F0F1E",
            "row_even": "#12122A",
            "row_odd": "#16163A",
            "magnitude_low": "#00FF88",
            "magnitude_mid": "#FFD700",
            "magnitude_high": "#FF8C00",
            "magnitude_severe": "#FF3366",
        },
        "borders": {"style": "thin", "radius": 4, "thickness": 1},
        "animation": {
            "transition_ms": 200,
            "fade_ms": 150,
            "pulse_ms": 1200,
            "highlight_decay_ms": 3000,
        },
        "typography": {"font_size": 15, "line_spacing": 1.4, "header_scale": 1.3},
    }

    (themes_dir / "test.json").write_text(json.dumps(theme))
    return themes_dir
