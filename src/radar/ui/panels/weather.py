"""
Weather panel — gauge-style dashboard for real-time weather data.

Displays temperature, wind, pressure, humidity, and conditions
with animated transitions and unit-aware formatting.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

import dearpygui.dearpygui as dpg

from radar.ui.viewport import get_header_font

if TYPE_CHECKING:
    from radar.data.weather import WeatherData
    from radar.themes.loader import ThemeData

logger = logging.getLogger(__name__)


class WeatherPanel:
    """Real-time weather dashboard panel."""

    def __init__(
        self,
        theme: ThemeData,
        city_index: CityIndex | None = None,
        location_name: str = "",
        on_location_change: callable = None,
    ) -> None:
        self._theme = theme
        self._city_index = city_index
        self._location = location_name
        self._on_location_change = on_location_change
        self._container_tag: int | str | None = None
        self._data: WeatherData | None = None

        # Individual value tags for efficient updates
        self._tags: dict[str, int | str] = {}
        
        # Search state
        self._search_results: list[Any] = []

    def set_location_name(self, name: str) -> None:
        """Update displayed location name."""
        self._location = name
        if "location" in self._tags:
            dpg.set_value(self._tags["location"], name)

    def _on_search_change(self, sender: int | str, query: str) -> None:
        """Handle search input sensing."""
        if not self._city_index or not query or len(query) < 2:
            dpg.configure_item("city_results", show=False)
            return

        results = self._city_index.search(query, limit=8)
        self._search_results = results
        
        if not results:
            dpg.configure_item("city_results", show=False)
            return

        items = [c.display_name for c in results]
        try:
            dpg.configure_item("city_results", items=items, show=True)
            # Reset selection so it doesn't auto-select first item visually
            dpg.set_value("city_results", "") 
        except Exception:
            pass

    def _on_city_select(self, sender: int | str, app_data: str) -> None:
        """Handle city selection from dropdown."""
        dpg.configure_item("city_results", show=False)
        dpg.set_value("city_search", "")  # Clear search

        # Find selected city object
        selected_city = next(
            (c for c in self._search_results if c.display_name == app_data), None
        )
        
        if selected_city and self._on_location_change:
            self._on_location_change(
                selected_city.latitude,
                selected_city.longitude,
                selected_city.short_name
            )

    def build(self, parent: int | str) -> None:
        """Create the weather panel UI layout."""
        with dpg.child_window(parent=parent, border=True) as container:
            self._container_tag = container

            # Header
            with dpg.group(horizontal=True):
                header_font = get_header_font()
                header = dpg.add_text("[WXA] WEATHER STATION")
                if header_font:
                    dpg.bind_item_font(header, header_font)
                dpg.add_spacer(width=-1)
                self._tags["location"] = dpg.add_text(
                    self._location, color=self._theme.color("text_dim")
                )

            dpg.add_separator()
            
            # Search Bar
            dpg.add_input_text(
                tag="city_search",
                hint="Search city (e.g. 'Tokyo' or 'Paris, FR')",
                width=-1,
                callback=self._on_search_change,
                on_enter=True, # Also trigger on enter
            )
            
            # Overlay listbox for search results (initially hidden)
            # We place it before next items so it pushes them down (simpler than overlay layer)
            dpg.add_listbox(
                tag="city_results",
                items=[],
                width=-1,
                num_items=5,
                show=False,
                callback=self._on_city_select,
            )

            # Condition summary
            with dpg.group(horizontal=True):
                self._tags["condition"] = dpg.add_text(
                    "—  Awaiting data...",
                    color=self._theme.color("primary"),
                )

            dpg.add_spacer(height=6)

            # Temperature row
            with dpg.group(horizontal=True):
                dpg.add_text("TEMP       ", color=self._theme.color("text_dim"))
                self._tags["temp"] = dpg.add_text("—", color=self._theme.color("text_bright"))
                dpg.add_spacer(width=20)
                dpg.add_text("FEELS LIKE ", color=self._theme.color("text_dim"))
                self._tags["feels"] = dpg.add_text("—", color=self._theme.color("text"))

            dpg.add_spacer(height=3)

            # Wind row 
            with dpg.group(horizontal=True):
                dpg.add_text("WIND       ", color=self._theme.color("text_dim"))
                self._tags["wind"] = dpg.add_text("—", color=self._theme.color("text_bright"))
                dpg.add_spacer(width=20)
                dpg.add_text("GUSTS      ", color=self._theme.color("text_dim"))
                self._tags["gusts"] = dpg.add_text("—", color=self._theme.color("text"))

            dpg.add_spacer(height=3)

            # Wind direction row 
            with dpg.group(horizontal=True):
                dpg.add_text("DIRECTION  ", color=self._theme.color("text_dim"))
                self._tags["wind_dir"] = dpg.add_text("—", color=self._theme.color("text_bright"))
                dpg.add_spacer(width=20)
                dpg.add_text("COMPASS    ", color=self._theme.color("text_dim"))
                self._tags["compass"] = dpg.add_text("—", color=self._theme.color("primary"))

            dpg.add_spacer(height=3)

            # Pressure row 
            with dpg.group(horizontal=True):
                dpg.add_text("PRESSURE   ", color=self._theme.color("text_dim"))
                self._tags["pressure"] = dpg.add_text("—", color=self._theme.color("text_bright"))
                dpg.add_spacer(width=20)
                dpg.add_text("HUMIDITY   ", color=self._theme.color("text_dim"))
                self._tags["humidity"] = dpg.add_text("—", color=self._theme.color("text_bright"))

            dpg.add_spacer(height=3)

            # Additional row 
            with dpg.group(horizontal=True):
                dpg.add_text("CLOUD      ", color=self._theme.color("text_dim"))
                self._tags["cloud"] = dpg.add_text("—", color=self._theme.color("text"))
                dpg.add_spacer(width=20)
                dpg.add_text("PRECIP     ", color=self._theme.color("text_dim"))
                self._tags["precip"] = dpg.add_text("—", color=self._theme.color("text"))

            dpg.add_spacer(height=3)

            # Elevation 
            with dpg.group(horizontal=True):
                dpg.add_text("ELEVATION  ", color=self._theme.color("text_dim"))
                self._tags["elevation"] = dpg.add_text("—", color=self._theme.color("text"))
                dpg.add_spacer(width=20)
                dpg.add_text("DAY/NIGHT  ", color=self._theme.color("text_dim"))
                self._tags["daynight"] = dpg.add_text("—", color=self._theme.color("text"))

            dpg.add_spacer(height=8)
            dpg.add_separator()

            # Wind compass visualization 
            dpg.add_spacer(height=4)
            with dpg.group(horizontal=True):
                dpg.add_spacer(width=20)
                with dpg.drawlist(width=120, height=120) as compass:
                    self._tags["compass_draw"] = compass
                    self._draw_compass(0)

    def _draw_compass(self, direction: int) -> None:
        """Draw a simple wind direction compass."""
        tag = self._tags.get("compass_draw")
        if tag is None:
            return

        dpg.delete_item(tag, children_only=True)

        cx, cy = 60, 60
        radius = 50
        primary = self._theme.color("primary")
        dim = self._theme.color("text_dim")
        border = self._theme.color("border")

        # Circle
        dpg.draw_circle((cx, cy), radius, color=border, parent=tag)
        dpg.draw_circle((cx, cy), 3, color=dim, fill=dim, parent=tag)

        # Cardinal labels
        for label, angle, dx, dy in [
            ("N", 0, -4, -radius - 12), ("S", 180, -3, radius + 4),
            ("E", 90, radius + 4, -4), ("W", 270, -radius - 14, -4),
        ]:
            dpg.draw_text((cx + dx, cy + dy), label, color=dim, size=12, parent=tag)

        # Direction arrow
        angle_rad = math.radians(direction - 90)  # 0° = North
        arrow_len = radius - 8
        ax = cx + arrow_len * math.cos(angle_rad)
        ay = cy + arrow_len * math.sin(angle_rad)
        dpg.draw_arrow((ax, ay), (cx, cy), color=primary, thickness=2, size=8, parent=tag)

    def update(self, data: WeatherData) -> None:
        """Refresh all weather values."""
        self._data = data

        dpg.set_value(self._tags["condition"], f"   {data.weather_description}")
        dpg.set_value(self._tags["temp"], f"{data.temperature:.1f}{data.temp_unit}")
        dpg.set_value(self._tags["feels"], f"{data.feels_like:.1f}{data.temp_unit}")
        dpg.set_value(self._tags["wind"], f"{data.wind_speed:.1f} {data.speed_unit}")
        dpg.set_value(self._tags["gusts"], f"{data.wind_gusts:.1f} {data.speed_unit}")
        dpg.set_value(self._tags["wind_dir"], f"{data.wind_direction}°")
        dpg.set_value(self._tags["compass"], data.wind_cardinal)
        dpg.set_value(self._tags["pressure"], f"{data.pressure:.1f} {data.pressure_unit}")
        dpg.set_value(self._tags["humidity"], f"{data.humidity}%")
        dpg.set_value(self._tags["cloud"], f"{data.cloud_cover}%")
        dpg.set_value(
            self._tags["precip"],
            f"{data.precipitation:.1f} {'in' if data.units == 'imperial' else 'mm'}",
        )
        dpg.set_value(self._tags["elevation"], f"{data.elevation:.0f} m")
        dpg.set_value(self._tags["daynight"], "DAY" if data.is_day else "NGHT")

        # Update compass
        self._draw_compass(data.wind_direction)

        # Color temperature based on value (cold → hot)
        temp_c = data.temperature if data.units == "metric" else (data.temperature - 32) * 5 / 9
        if temp_c < 0:
            color = (100, 150, 255, 255)
        elif temp_c < 15:
            color = (100, 200, 255, 255)
        elif temp_c < 25:
            color = self._theme.color("success")
        elif temp_c < 35:
            color = self._theme.color("warning")
        else:
            color = self._theme.color("danger")
        dpg.configure_item(self._tags["temp"], color=color)

    def update_theme(self, theme: ThemeData, soft: bool = False) -> None:
        """Apply a new theme to the panel."""
        self._theme = theme
        if self._data and not soft:
            self.update(self._data)
        elif self._data and soft:
            # Re-apply color logic for temperature specifically 
            temp_c = self._data.temperature if self._data.units == "metric" else (self._data.temperature - 32) * 5 / 9
            if temp_c < 0:
                color = (100, 150, 255, 255)
            elif temp_c < 15:
                color = (100, 200, 255, 255)
            elif temp_c < 25:
                color = self._theme.color("success")
            elif temp_c < 35:
                color = self._theme.color("warning")
            else:
                color = self._theme.color("danger")
            if "temp" in self._tags and dpg.does_item_exist(self._tags["temp"]):
                dpg.configure_item(self._tags["temp"], color=color)

