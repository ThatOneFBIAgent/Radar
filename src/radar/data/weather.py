"""
Weather data fetcher — Open-Meteo API.

Provides async fetching, unit conversion, and typed weather models.
No API key required.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Literal

import aiohttp

logger = logging.getLogger(__name__)

_OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"


# Data model
@dataclass(frozen=True, slots=True)
class WeatherData:
    """Current weather snapshot."""

    temperature: float        # °C or °F
    feels_like: float         # °C or °F (apparent temperature)
    wind_speed: float         # km/h or mph
    wind_direction: int       # degrees (0-360)
    wind_gusts: float         # km/h or mph
    pressure: float           # hPa
    humidity: int             # percentage
    cloud_cover: int          # percentage
    precipitation: float      # mm or inches
    elevation: float          # meters
    is_day: bool
    weather_code: int         # WMO weather interpretation code
    units: str = "metric"

    @property
    def wind_cardinal(self) -> str:
        """Convert wind direction degrees to cardinal direction."""
        directions = [
            "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
        ]
        idx = round(self.wind_direction / 22.5) % 16
        return directions[idx]

    @property
    def weather_description(self) -> str:
        """Human-readable weather description from WMO code."""
        codes: dict[int, str] = {
            0: "Clear sky",
            1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Fog", 48: "Rime fog",
            51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
            56: "Freezing drizzle (light)", 57: "Freezing drizzle",
            61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
            66: "Freezing rain (light)", 67: "Freezing rain",
            71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
            77: "Snow grains",
            80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
            85: "Slight snow showers", 86: "Heavy snow showers",
            95: "Thunderstorm", 96: "Thunderstorm w/ slight hail",
            99: "Thunderstorm w/ heavy hail",
        }
        return codes.get(self.weather_code, f"Code {self.weather_code}")

    @property
    def temp_unit(self) -> str:
        return "°F" if self.units == "imperial" else "°C"

    @property
    def speed_unit(self) -> str:
        return "mph" if self.units == "imperial" else "km/h"

    @property
    def pressure_unit(self) -> str:
        return "hPa"


@dataclass(frozen=True, slots=True)
class ForecastEntry:
    """Single hourly forecast entry."""

    time: str
    temperature: float
    precipitation_probability: int
    weather_code: int
    wind_speed: float

    @property
    def weather_description(self) -> str:
        return WeatherData.weather_description.fget(self)  # type: ignore[attr-defined]


# Unit conversion
def _c_to_f(c: float) -> float:
    return round(c * 9 / 5 + 32, 1)


def _kmh_to_mph(kmh: float) -> float:
    return round(kmh * 0.621371, 1)


def _mm_to_inches(mm: float) -> float:
    return round(mm * 0.0393701, 2)


# Fetcher
class WeatherFetcher:
    """Async weather data fetcher from Open-Meteo.

    Usage:
        fetcher = WeatherFetcher(lat, lon)
        data = await fetcher.fetch()
    """

    def __init__(
        self,
        latitude: float,
        longitude: float,
        units: Literal["metric", "imperial"] = "metric",
    ) -> None:
        self._lat = latitude
        self._lon = longitude
        self._units = units
        self._session: aiohttp.ClientSession | None = None
        self._last_data: WeatherData | None = None
        self._last_fetch: float = 0.0

    def set_location(self, lat: float, lon: float) -> None:
        """Update target location and force next fetch to run immediately."""
        self._lat = lat
        self._lon = lon
        self._last_fetch = 0.0  # Force immediate refresh
        logger.info("Weather location updated to %.4f, %.4f", lat, lon)

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"User-Agent": "Radar/0.1 (weather-monitor)"},
            )
        return self._session

    async def fetch(self) -> WeatherData | None:
        """Fetch current weather data. Returns None on error (keeps last)."""
        session = await self._ensure_session()

        params = {
            "latitude": self._lat,
            "longitude": self._lon,
            "current": ",".join([
                "temperature_2m",
                "apparent_temperature",
                "relative_humidity_2m",
                "wind_speed_10m",
                "wind_direction_10m",
                "wind_gusts_10m",
                "surface_pressure",
                "cloud_cover",
                "precipitation",
                "weather_code",
                "is_day",
            ]),
            "timezone": "auto",
        }

        try:
            async with session.get(_OPEN_METEO_BASE, params=params) as resp:
                resp.raise_for_status()
                raw = await resp.json(content_type=None)
                self._last_fetch = time.monotonic()
        except aiohttp.ClientError as e:
            logger.error("Weather fetch failed: %s", e)
            return self._last_data
        except Exception as e:
            logger.error("Unexpected weather fetch error: %s", e)
            return self._last_data

        try:
            current = raw["current"]
            elevation = raw.get("elevation", 0.0)

            temp = float(current["temperature_2m"])
            feels = float(current["apparent_temperature"])
            wind = float(current["wind_speed_10m"])
            gusts = float(current.get("wind_gusts_10m", 0))
            precip = float(current.get("precipitation", 0))

            if self._units == "imperial":
                temp = _c_to_f(temp)
                feels = _c_to_f(feels)
                wind = _kmh_to_mph(wind)
                gusts = _kmh_to_mph(gusts)
                precip = _mm_to_inches(precip)

            data = WeatherData(
                temperature=temp,
                feels_like=feels,
                wind_speed=wind,
                wind_direction=int(current.get("wind_direction_10m", 0)),
                wind_gusts=gusts,
                pressure=float(current.get("surface_pressure", 0)),
                humidity=int(current.get("relative_humidity_2m", 0)),
                cloud_cover=int(current.get("cloud_cover", 0)),
                precipitation=precip,
                elevation=elevation,
                is_day=bool(current.get("is_day", 1)),
                weather_code=int(current.get("weather_code", 0)),
                units=self._units,
            )

            self._last_data = data
            logger.info(
                "Weather update: %.1f%s, %s, wind %.1f %s %s",
                data.temperature, data.temp_unit,
                data.weather_description,
                data.wind_speed, data.speed_unit, data.wind_cardinal,
            )
            return data

        except (KeyError, TypeError, ValueError) as e:
            logger.error("Weather parsing error: %s", e)
            return self._last_data

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
