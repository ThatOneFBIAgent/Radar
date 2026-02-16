"""Tests for the configuration system."""

from __future__ import annotations

from pathlib import Path

import pytest

from radar.config import (
    EarthquakeConfig,
    GeneralConfig,
    RadarConfig,
    UIConfig,
    WeatherConfig,
    load_config,
)


class TestGeneralConfig:
    def test_defaults(self) -> None:
        cfg = GeneralConfig()
        assert cfg.log_level == "INFO"
        assert cfg.units == "metric"

    def test_invalid_log_level(self) -> None:
        with pytest.raises(Exception):
            GeneralConfig(log_level="INVALID")  # type: ignore

    def test_valid_units(self) -> None:
        cfg = GeneralConfig(units="imperial")
        assert cfg.units == "imperial"


class TestEarthquakeConfig:
    def test_defaults(self) -> None:
        cfg = EarthquakeConfig()
        assert cfg.feed == "all_hour"
        assert cfg.poll_interval == 60
        assert cfg.highlight_threshold == 4.5

    def test_feed_url_property(self) -> None:
        cfg = EarthquakeConfig(feed="2.5_day")
        assert "2.5_day" in cfg.feed_url

    def test_invalid_feed(self) -> None:
        with pytest.raises(Exception):
            EarthquakeConfig(feed="nonexistent_feed")

    def test_poll_interval_minimum(self) -> None:
        with pytest.raises(Exception):
            EarthquakeConfig(poll_interval=10)


class TestWeatherConfig:
    def test_defaults(self) -> None:
        cfg = WeatherConfig()
        assert cfg.latitude == 29.7604
        assert cfg.longitude == -95.3698

    def test_latitude_bounds(self) -> None:
        with pytest.raises(Exception):
            WeatherConfig(latitude=100.0)

    def test_longitude_bounds(self) -> None:
        with pytest.raises(Exception):
            WeatherConfig(longitude=200.0)


class TestUIConfig:
    def test_defaults(self) -> None:
        cfg = UIConfig()
        assert cfg.theme == "obsidian"
        assert cfg.font_size == 15

    def test_font_size_bounds(self) -> None:
        with pytest.raises(Exception):
            UIConfig(font_size=2)
        with pytest.raises(Exception):
            UIConfig(font_size=100)


class TestLoadConfig:
    def test_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "nonexistent.toml")
        assert isinstance(cfg, RadarConfig)
        assert cfg.general.log_level == "INFO"

    def test_valid_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[general]\nlog_level = "DEBUG"\nunits = "imperial"\n'
            "[earthquake]\nfeed = \"2.5_day\"\npoll_interval = 120\n"
        )
        cfg = load_config(config_file)
        assert cfg.general.log_level == "DEBUG"
        assert cfg.general.units == "imperial"
        assert cfg.earthquake.feed == "2.5_day"
        assert cfg.earthquake.poll_interval == 120

    def test_invalid_toml_returns_defaults(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.toml"
        config_file.write_text("this is not valid toml {{{}}")
        cfg = load_config(config_file)
        assert isinstance(cfg, RadarConfig)

    def test_partial_config(self, tmp_path: Path) -> None:
        """Config with only some sections filled should use defaults for rest."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('[ui]\ntheme = "phosphor"\n')
        cfg = load_config(config_file)
        assert cfg.ui.theme == "phosphor"
        assert cfg.earthquake.feed == "all_hour"  # default
