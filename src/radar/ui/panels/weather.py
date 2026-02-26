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

from radar.ui.viewport import get_header_font, get_large_font

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
        self._width: int = 400
        self._height: int = 800
        
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
                dpg.add_text(" | ", color=self._theme.color("border"))
                self._tags["location"] = dpg.add_text(
                    self._location.upper(), color=self._theme.color("primary")
                )
                if header_font:
                    dpg.bind_item_font(self._tags["location"], header_font)

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

            # Hero Section (Temp & Condition)
            with dpg.group(horizontal=True):
                large_font = get_large_font()
                
                # Temperature Block
                with dpg.group():
                    self._tags["temp"] = dpg.add_text("—", color=self._theme.color("text_bright"))
                    if large_font:
                        dpg.bind_item_font(self._tags["temp"], large_font)
                        
                    with dpg.group(horizontal=True):
                        dpg.add_text("FEELS LIKE", color=self._theme.color("text_dim"))
                        dpg.add_spacer(width=5)
                        self._tags["feels"] = dpg.add_text("—", color=self._theme.color("text"))

                dpg.add_spacer(width=30)

                # Condition Block
                with dpg.group():
                    dpg.add_spacer(height=6) # alignment tweak
                    self._tags["condition"] = dpg.add_text(
                        "Awaiting data...", color=self._theme.color("primary")
                    )
                    with dpg.group(horizontal=True):
                        dpg.add_text("CLOUD", color=self._theme.color("text_dim"))
                        dpg.add_spacer(width=5)
                        self._tags["cloud"] = dpg.add_text("—", color=self._theme.color("text"))
                        dpg.add_spacer(width=15)
                        dpg.add_text("DAY/NIGHT", color=self._theme.color("text_dim"))
                        dpg.add_spacer(width=5)
                        self._tags["daynight"] = dpg.add_text("—", color=self._theme.color("text"))

            dpg.add_spacer(height=10)
            dpg.add_separator()
            dpg.add_spacer(height=10)

            # Data Grid via Table
            with dpg.table(
                header_row=False,
                policy=dpg.mvTable_SizingFixedFit,
                borders_innerH=False,
                borders_outerH=False,
                borders_innerV=False,
                borders_outerV=False,
                pad_outerX=True,
            ):
                dpg.add_table_column(init_width_or_weight=80)   # Label 1
                dpg.add_table_column(init_width_or_weight=130)  # Value 1 (widened for Pressure text)
                dpg.add_table_column(init_width_or_weight=20)   # Spacer
                dpg.add_table_column(init_width_or_weight=80)   # Label 2
                dpg.add_table_column(init_width_or_weight=80)   # Value 2

                # Row 1: Wind
                with dpg.table_row():
                    dpg.add_text("WIND", color=self._theme.color("text_dim"))
                    self._tags["wind"] = dpg.add_text("—", color=self._theme.color("text_bright"))
                    dpg.add_spacer()
                    dpg.add_text("GUSTS", color=self._theme.color("text_dim"))
                    self._tags["gusts"] = dpg.add_text("—", color=self._theme.color("text"))

                # Row 2: Wind Dir
                with dpg.table_row():
                    dpg.add_text("DIRECTION", color=self._theme.color("text_dim"))
                    self._tags["wind_dir"] = dpg.add_text("—", color=self._theme.color("text_bright"))
                    dpg.add_spacer()
                    dpg.add_text("COMPASS", color=self._theme.color("text_dim"))
                    self._tags["compass"] = dpg.add_text("—", color=self._theme.color("primary"))

                # Row 3: Atmos
                with dpg.table_row():
                    dpg.add_text("PRESSURE", color=self._theme.color("text_dim"))
                    self._tags["pressure"] = dpg.add_text("—", color=self._theme.color("text_bright"))
                    dpg.add_spacer()
                    dpg.add_text("HUMIDITY", color=self._theme.color("text_dim"))
                    self._tags["humidity"] = dpg.add_text("—", color=self._theme.color("text_bright"))

                # Row 4: Moisture / Elevation
                with dpg.table_row():
                    dpg.add_text("PRECIP", color=self._theme.color("text_dim"))
                    self._tags["precip"] = dpg.add_text("—", color=self._theme.color("text"))
                    dpg.add_spacer()
                    dpg.add_text("ELEVATION", color=self._theme.color("text_dim"))
                    self._tags["elevation"] = dpg.add_text("—", color=self._theme.color("text"))

            dpg.add_spacer(height=10)
            dpg.add_separator()

            # Dynamic Wind compass visualization
            with dpg.group(tag="compass_container"):
                with dpg.drawlist(width=self._width, height=self._width) as compass:
                    self._tags["compass_draw"] = compass
                    self._draw_compass(0)

    def resize(self, width: int, height: int) -> None:
        """Called when layout splitters move or window resizes."""
        self._width = width
        self._height = height
        
        # Calculate remaining height for compass (approx 220px taken by hero + grid)
        # To keep it completely circular we match width/height exactly
        compass_size = max(150, min(width - 40, height - 220))
        
        if "compass_draw" in self._tags and dpg.does_item_exist(self._tags["compass_draw"]):
            dpg.configure_item(self._tags["compass_draw"], width=width, height=compass_size)
            
            # Redraw center points and radius based on new dimensions
            if self._data:
                self._draw_compass(self._data.wind_direction)
            else:
                self._draw_compass(0)

    def _draw_compass(self, direction: int, scale: float = 1.0) -> None:
        """Draw a simple wind direction compass."""
        tag = self._tags.get("compass_draw")
        if tag is None:
            return

        dpg.delete_item(tag, children_only=True)

        if "compass_draw" not in self._tags: return
        try:
            draw_w = dpg.get_item_width(self._tags["compass_draw"])
            draw_h = dpg.get_item_height(self._tags["compass_draw"])
        except Exception:
            draw_w = 200
            draw_h = 200

        # Center in available drawlist space
        cx, cy = draw_w / 2, draw_h / 2
        # Base the radius on the smallest dimension to ensure it stays fully circular
        base_radius = (min(draw_w, draw_h) / 2) - 40
        radius = base_radius * scale

        primary = self._theme.color("primary")
        dim = self._theme.color("text_dim")
        border = self._theme.color("border")

        # Pulse ring (drawn first so it's beneath everything)
        if scale > 1.0:
            # Alpha fades out as pulse expands
            alpha = max(0, min(255, int(255 * (1.1 - scale) * 10))) 
            dpg.draw_circle((cx, cy), radius * 1.05, color=(primary[0], primary[1], primary[2], alpha), thickness=2, parent=tag)

        # Circle bounds
        dpg.draw_circle((cx, cy), base_radius, color=border, thickness=2, parent=tag)
        dpg.draw_circle((cx, cy), base_radius * 0.7, color=(border[0], border[1], border[2], 50), thickness=1, parent=tag)
        dpg.draw_circle((cx, cy), 3, color=dim, fill=dim, parent=tag)
        
        # Grid lines (crosshairs)
        dpg.draw_line((cx, cy - base_radius), (cx, cy + base_radius), color=(border[0], border[1], border[2], 80), parent=tag)
        dpg.draw_line((cx - base_radius, cy), (cx + base_radius, cy), color=(border[0], border[1], border[2], 80), parent=tag)
        
        for deg in range(0, 360, 45):
            rad = math.radians(deg)
            x_inner = cx + (base_radius * 0.9) * math.sin(rad)
            y_inner = cy - (base_radius * 0.9) * math.cos(rad)
            x_outer = cx + base_radius * math.sin(rad)
            y_outer = cy - base_radius * math.cos(rad)
            dpg.draw_line((x_inner, y_inner), (x_outer, y_outer), color=border, parent=tag)

        # Cardinal labels (use base_radius so text doesn't jiggle)
        for label, angle, dx, dy in [
            ("N", 0, -4, -base_radius - 18), ("S", 180, -3, base_radius + 4),
            ("E", 90, base_radius + 8, -6), ("W", 270, -base_radius - 18, -6),
        ]:
            dpg.draw_text((cx + dx, cy + dy), label, color=dim, size=14, parent=tag)

        # Direction arrow mapping 0 to North (top)
        angle_rad = math.radians(direction - 90)
        arrow_len = base_radius * 0.85
        ax = cx + arrow_len * math.cos(angle_rad)
        ay = cy + arrow_len * math.sin(angle_rad)
        
        # Tri-point chevron arrow for thicker aesthetics
        # Scales slightly with pulse
        dpg.draw_arrow((ax, ay), (cx, cy), color=primary, thickness=int(3*scale), size=int(12*scale), parent=tag)

    def trigger_update_pulse(self) -> None:
        """Starts a visual scale animation pulse on the compass."""
        self._pulse_frame = 0
        self._is_pulsing = True

    def _frame_tick(self) -> None:
        """Called every frame by the main app loop to handle animations."""
        if getattr(self, '_is_pulsing', False) and self._data and "compass_draw" in self._tags:
            self._pulse_frame += 1
            if self._pulse_frame > 30: # Frames to run
                self._is_pulsing = False
                self._draw_compass(self._data.wind_direction, scale=1.0)
                return
            
            # Math sin curve from 0->PI creates a 1.0 -> 1.08 -> 1.0 bump
            progress = self._pulse_frame / 30.0
            scale_bump = 1.0 + (math.sin(progress * math.pi) * 0.08)
            
            self._draw_compass(self._data.wind_direction, scale=scale_bump)

    def update(self, data: WeatherData) -> None:
        """Refresh all weather values."""
        self._data = data

        dpg.set_value(self._tags["condition"], data.weather_description.upper())
        dpg.set_value(self._tags["temp"], f"{data.temperature:.1f}{data.temp_unit}")
        dpg.set_value(self._tags["feels"], f"{data.feels_like:.1f}{data.temp_unit}")
        dpg.set_value(self._tags["wind"], f"{data.wind_speed:.1f} {data.speed_unit}")
        dpg.set_value(self._tags["gusts"], f"{data.wind_gusts:.1f} {data.speed_unit}")
        dpg.set_value(self._tags["wind_dir"], f"{data.wind_direction}°")
        dpg.set_value(self._tags["compass"], data.wind_cardinal)
        
        # Calculate standardized pressure relative to elevation
        # ISA (International Standard Atmosphere) normal pressure decays with height
        # P = P0 * (1 - L*h/T0) ^ (g*M / (R*L))
        # Approximation: roughly 1.2 hPa drop per 10 meters of elevation at low alts
        p_normal = 1013.25 * ((1 - (0.0065 * data.elevation) / 288.15) ** 5.255)
        
        if data.pressure < p_normal - 4:
            p_trend = "LOW"
        elif data.pressure > p_normal + 4:
            p_trend = "HIGH"
        else:
            p_trend = "NORMAL"

        dpg.set_value(self._tags["pressure"], f"{data.pressure:.1f} {data.pressure_unit} ({p_trend})")
        
        dpg.set_value(self._tags["humidity"], f"{data.humidity}%")
        dpg.set_value(self._tags["cloud"], f"{data.cloud_cover}%")
        dpg.set_value(
            self._tags["precip"],
            f"{data.precipitation:.1f} {'in' if data.units == 'imperial' else 'mm'}",
        )
        dpg.set_value(self._tags["elevation"], f"{data.elevation:.0f} m")
        dpg.set_value(self._tags["daynight"], "DAY" if data.is_day else "NGHT")

        # Update compass and trigger the visual pulse
        self._draw_compass(data.wind_direction)
        self.trigger_update_pulse()

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

