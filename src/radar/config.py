"""
Configuration loader and validation for Radar.

Loads config.toml, validates fields, and provides typed access
to all configuration values via Pydantic models.
"""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# Default paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.toml"
THEMES_DIR = PROJECT_ROOT / "themes"
ASSETS_DIR = PROJECT_ROOT / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"

# USGS Feed URL map
_USGS_BASE = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary"
USGS_FEEDS: dict[str, str] = {
    "all_hour": f"{_USGS_BASE}/all_hour.geojson",
    "all_day": f"{_USGS_BASE}/all_day.geojson",
    "all_week": f"{_USGS_BASE}/all_week.geojson",
    "all_month": f"{_USGS_BASE}/all_month.geojson",
    "1.0_hour": f"{_USGS_BASE}/1.0_hour.geojson",
    "1.0_day": f"{_USGS_BASE}/1.0_day.geojson",
    "1.0_week": f"{_USGS_BASE}/1.0_week.geojson",
    "1.0_month": f"{_USGS_BASE}/1.0_month.geojson",
    "2.5_hour": f"{_USGS_BASE}/2.5_hour.geojson",
    "2.5_day": f"{_USGS_BASE}/2.5_day.geojson",
    "2.5_week": f"{_USGS_BASE}/2.5_week.geojson",
    "2.5_month": f"{_USGS_BASE}/2.5_month.geojson",
    "4.5_hour": f"{_USGS_BASE}/4.5_hour.geojson",
    "4.5_day": f"{_USGS_BASE}/4.5_day.geojson",
    "4.5_week": f"{_USGS_BASE}/4.5_week.geojson",
    "4.5_month": f"{_USGS_BASE}/4.5_month.geojson",
    "significant_hour": f"{_USGS_BASE}/significant_hour.geojson",
    "significant_day": f"{_USGS_BASE}/significant_day.geojson",
    "significant_week": f"{_USGS_BASE}/significant_week.geojson",
    "significant_month": f"{_USGS_BASE}/significant_month.geojson",
}


# Pydantic config models
class GeneralConfig(BaseModel):
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    units: Literal["metric", "imperial"] = "metric"


class EarthquakeConfig(BaseModel):
    feed: str = "all_hour"
    poll_interval: int = Field(default=60, ge=30)
    highlight_threshold: float = Field(default=4.5, ge=0.0)
    max_display: int = Field(default=100, ge=10)

    @field_validator("feed")
    @classmethod
    def validate_feed(cls, v: str) -> str:
        if v not in USGS_FEEDS:
            raise ValueError(
                f"Unknown feed '{v}'. Valid feeds: {', '.join(sorted(USGS_FEEDS.keys()))}"
            )
        return v

    @property
    def feed_url(self) -> str:
        return USGS_FEEDS[self.feed]


class WeatherConfig(BaseModel):
    latitude: float = Field(default=29.7604, ge=-90.0, le=90.0)
    longitude: float = Field(default=-95.3698, ge=-180.0, le=180.0)
    location_name: str = "Houston, TX"
    poll_interval: int = Field(default=120, ge=60)
    show_forecast: bool = False


class UIConfig(BaseModel):
    theme: str = "obsidian"
    font_size: int = Field(default=15, ge=8, le=48)
    window_width: int = Field(default=1400, ge=0)
    window_height: int = Field(default=900, ge=0)
    start_maximized: bool = False
    animations: bool = True
    animation_speed: float = Field(default=1.0, ge=0.1, le=5.0)


class RadarConfig(BaseModel):
    general: GeneralConfig = GeneralConfig()
    earthquake: EarthquakeConfig = EarthquakeConfig()
    weather: WeatherConfig = WeatherConfig()
    ui: UIConfig = UIConfig()


# Loader
def load_config(path: Path | None = None) -> RadarConfig:
    """Load and validate configuration from a TOML file.

    Validates top-level sections individually to be resilient against
    partial configuration errors.
    """
    config_path = path or DEFAULT_CONFIG_PATH

    if not config_path.exists():
        logger.warning("Config file not found at %s — using defaults", config_path)
        return RadarConfig()

    try:
        with open(config_path, "rb") as f:
            raw = tomllib.load(f)
        logger.info("Loaded config file from %s", config_path)
    except tomllib.TOMLDecodeError as e:
        logger.error("Invalid TOML in %s: %s — using all defaults", config_path, e)
        return RadarConfig()
    except Exception as e:
        logger.error("Failed to read config file %s: %s — using all defaults", config_path, e)
        return RadarConfig()

    # Create a default config as a base
    final_config = RadarConfig()

    # Validate each section individually for resilience
    sections = {
        "general": GeneralConfig,
        "earthquake": EarthquakeConfig,
        "weather": WeatherConfig,
        "ui": UIConfig
    }

    for key, model in sections.items():
        if key in raw and isinstance(raw[key], dict):
            try:
                setattr(final_config, key, model(**raw[key]))
                logger.debug("Validated config section: [%s]", key)
            except Exception as e:
                logger.warning(
                    "Invalid [%s] section in config — keeping defaults for this section. Error: %s",
                    key, e
                )
        elif key in raw:
            logger.warning("Config section [%s] must be a table — keeping defaults", key)

    return final_config
