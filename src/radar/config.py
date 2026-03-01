"""
Configuration loader and validation for Radar.

Loads config.toml, validates fields, and provides typed access
to all configuration values via Pydantic models.
"""

from __future__ import annotations

import logging
import tomllib
import os
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# Resolve paths. 
# PROJECT_ROOT: Points to the internal bundled assets (_internal in PyInstaller)
# BASE_DIR: Points to the directory containing the .exe
# USER_DATA_DIR: Persistent, writable directory for user config and logs
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    PROJECT_ROOT = Path(sys._MEIPASS)
    BASE_DIR = Path(sys.executable).parent
    
    # AppData for persistent storage on Windows
    _appdata = os.environ.get("LOCALAPPDATA")
    USER_DATA_DIR = Path(_appdata) / "Radar" if _appdata else BASE_DIR / "data"
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    BASE_DIR = PROJECT_ROOT
    USER_DATA_DIR = BASE_DIR

DATA_DIR = PROJECT_ROOT / "src" / "radar" / "data" if not getattr(sys, "frozen", False) else PROJECT_ROOT / "radar" / "data"
LOG_DIR = USER_DATA_DIR / "logs"

# Ensure directories exist
for d in [USER_DATA_DIR, LOG_DIR]:
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

def _resolve_writable_config() -> Path:
    """Determine the best path for configuration persistence."""
    portable = BASE_DIR / "config.toml"
    if portable.exists():
        return portable
    
    # If not present, check if we can write to the EXE directory (Portable Mode)
    try:
        test_file = BASE_DIR / ".write_test"
        test_file.touch()
        test_file.unlink()
        return portable
    except Exception:
        # Fallback to AppData (Installed Mode)
        return USER_DATA_DIR / "config.toml"

DEFAULT_CONFIG_PATH = _resolve_writable_config()

# Themes and Sounds: Separate internal (bundled) and external (user-writable)
INTERNAL_THEMES_DIR = PROJECT_ROOT / "themes"
EXTERNAL_THEMES_DIR = USER_DATA_DIR / "themes"
THEMES_DIR = EXTERNAL_THEMES_DIR # Alias for legacy support

INTERNAL_SOUND_DIR = PROJECT_ROOT / "sound"
EXTERNAL_SOUND_DIR = USER_DATA_DIR / "sound"
SOUND_DIR = EXTERNAL_SOUND_DIR # Alias for legacy support

# Ensure external asset dirs exist
for d in [EXTERNAL_THEMES_DIR, EXTERNAL_SOUND_DIR]:
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

ASSETS_DIR = PROJECT_ROOT / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"

def get_resource_path(relative_path: str | Path) -> Path:
    """Get the absolute path to a resource, supporting both dev and PyInstaller modes."""
    # If the path is already absolute, return it
    p = Path(relative_path)
    if p.is_absolute():
        return p

    # If frozen, look in _internal (PROJECT_ROOT)
    if getattr(sys, "frozen", False):
        return PROJECT_ROOT / relative_path

    # In development, we need to handle paths relative to the project root
    # or handle them as they were intended.
    # For simplicity, we assume PROJECT_ROOT is the base.
    return PROJECT_ROOT / relative_path

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
    split_x: float = Field(default=0.6, ge=0.2, le=0.8)
    split_y: float = Field(default=0.6, ge=0.2, le=0.8)
    start_maximized: bool = False
    animations: bool = True
    animation_speed: float = Field(default=1.0, ge=0.1, le=5.0)


class AudioConfig(BaseModel):
    enabled: bool = True
    volume: float = Field(default=0.7, ge=0.0, le=1.0)
    felt_radius_km: float = Field(default=300.0, ge=0.0)
    felt_warning_duration_s: int = Field(default=240, ge=0)
    sfx_delays: dict[str, float] = Field(default={
        "level_0": 1.2,
        "level_1": 1.7,
        "level_2": 2.3,
        "level_3": 2.3,
        "felt": 9.0,
        "update": 0.5
    })


class DebugConfig(BaseModel):
    mock_feed_file: str = ""


class RadarConfig(BaseModel):
    general: GeneralConfig = GeneralConfig()
    earthquake: EarthquakeConfig = EarthquakeConfig()
    weather: WeatherConfig = WeatherConfig()
    ui: UIConfig = UIConfig()
    audio: AudioConfig = AudioConfig()
    debug: DebugConfig = DebugConfig()


# Loader
def load_config(path: Path | None = None) -> RadarConfig:
    """Load and validate configuration from a TOML file.

    Validates top-level sections individually to be resilient against
    partial configuration errors.
    """
    config_path = path or DEFAULT_CONFIG_PATH

    # If the chosen config file doesn't exist, try to copy the internal bundled one as a template
    if not config_path.exists():
        internal_template = PROJECT_ROOT / "config.toml"
        if internal_template.exists():
            try:
                import shutil
                shutil.copy2(internal_template, config_path)
                logger.info("Created user config from template: %s", config_path)
            except Exception as e:
                logger.warning("Could not create config template: %s", e)

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
        "ui": UIConfig,
        "audio": AudioConfig,
        "debug": DebugConfig,
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


def save_config(config: RadarConfig, path: Path | None = None) -> bool:
    """Save the configuration to a TOML file.

    Manually serializes the Pydantic model to TOML format to avoid extra dependencies.
    """
    config_path = path or DEFAULT_CONFIG_PATH
    try:
        lines = [
            "# ╔══════════════════════════════════════════════════════════╗",
            "# ║                RADAR — Configuration                     ║",
            "# ╠══════════════════════════════════════════════════════════╣",
            "# ║  Edit this file to customize application behavior.       ║",
            "# ║  Restart the application after changes (except themes).  ║",
            "# ║  NOTE: Manual comments are lost on save. See README.md.  ║",
            "# ╚══════════════════════════════════════════════════════════╝",
            "",
        ]

        # Use model_dump to get a dict, then manually format sections
        data = config.model_dump()

        for section, values in data.items():
            if not values:
                continue
            lines.append(f"[{section}]")
            for key, val in values.items():
                if isinstance(val, str):
                    lines.append(f'{key} = "{val}"')
                elif isinstance(val, bool):
                    lines.append(f"{key} = {str(val).lower()}")
                elif isinstance(val, dict):
                    # Simple dict formatting (for sfx_delays)
                    dict_str = ", ".join([f'"{k}" = {v}' for k, v in val.items()])
                    lines.append(f"{key} = {{{dict_str}}}")
                else:
                    lines.append(f"{key} = {val}")
            lines.append("")

        with open(config_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        logger.info("Saved config to %s", config_path)
        return True
    except Exception as e:
        logger.error("Failed to save config to %s: %s", config_path, e)
        return False
