"""Tests for the weather data layer."""

from __future__ import annotations

import pytest

from radar.data.weather import WeatherData, WeatherFetcher, _c_to_f, _kmh_to_mph, _mm_to_inches


class TestUnitConversion:
    def test_celsius_to_fahrenheit(self) -> None:
        assert _c_to_f(0) == 32.0
        assert _c_to_f(100) == 212.0
        assert _c_to_f(-40) == -40.0

    def test_kmh_to_mph(self) -> None:
        result = _kmh_to_mph(100)
        assert 62.0 <= result <= 62.2

    def test_mm_to_inches(self) -> None:
        result = _mm_to_inches(25.4)
        assert 0.99 <= result <= 1.01


class TestWeatherData:
    def test_wind_cardinal_north(self) -> None:
        data = WeatherData(
            temperature=20, feels_like=18, wind_speed=10,
            wind_direction=0, wind_gusts=15, pressure=1013,
            humidity=50, cloud_cover=20, precipitation=0,
            elevation=10, is_day=True, weather_code=0,
        )
        assert data.wind_cardinal == "N"

    def test_wind_cardinal_south(self) -> None:
        data = WeatherData(
            temperature=20, feels_like=18, wind_speed=10,
            wind_direction=180, wind_gusts=15, pressure=1013,
            humidity=50, cloud_cover=20, precipitation=0,
            elevation=10, is_day=True, weather_code=0,
        )
        assert data.wind_cardinal == "S"

    def test_wind_cardinal_east(self) -> None:
        data = WeatherData(
            temperature=20, feels_like=18, wind_speed=10,
            wind_direction=90, wind_gusts=15, pressure=1013,
            humidity=50, cloud_cover=20, precipitation=0,
            elevation=10, is_day=True, weather_code=0,
        )
        assert data.wind_cardinal == "E"

    def test_weather_description_known_code(self) -> None:
        data = WeatherData(
            temperature=20, feels_like=18, wind_speed=10,
            wind_direction=0, wind_gusts=15, pressure=1013,
            humidity=50, cloud_cover=20, precipitation=0,
            elevation=10, is_day=True, weather_code=0,
        )
        assert data.weather_description == "Clear sky"

    def test_weather_description_unknown_code(self) -> None:
        data = WeatherData(
            temperature=20, feels_like=18, wind_speed=10,
            wind_direction=0, wind_gusts=15, pressure=1013,
            humidity=50, cloud_cover=20, precipitation=0,
            elevation=10, is_day=True, weather_code=999,
        )
        assert "999" in data.weather_description

    def test_temp_unit_metric(self) -> None:
        data = WeatherData(
            temperature=20, feels_like=18, wind_speed=10,
            wind_direction=0, wind_gusts=15, pressure=1013,
            humidity=50, cloud_cover=20, precipitation=0,
            elevation=10, is_day=True, weather_code=0, units="metric",
        )
        assert data.temp_unit == "°C"

    def test_temp_unit_imperial(self) -> None:
        data = WeatherData(
            temperature=68, feels_like=65, wind_speed=10,
            wind_direction=0, wind_gusts=15, pressure=1013,
            humidity=50, cloud_cover=20, precipitation=0,
            elevation=10, is_day=True, weather_code=0, units="imperial",
        )
        assert data.temp_unit == "°F"

    def test_speed_unit(self) -> None:
        metric = WeatherData(
            temperature=20, feels_like=18, wind_speed=10,
            wind_direction=0, wind_gusts=15, pressure=1013,
            humidity=50, cloud_cover=20, precipitation=0,
            elevation=10, is_day=True, weather_code=0, units="metric",
        )
        assert metric.speed_unit == "km/h"

        imperial = WeatherData(
            temperature=20, feels_like=18, wind_speed=10,
            wind_direction=0, wind_gusts=15, pressure=1013,
            humidity=50, cloud_cover=20, precipitation=0,
            elevation=10, is_day=True, weather_code=0, units="imperial",
        )
        assert imperial.speed_unit == "mph"
