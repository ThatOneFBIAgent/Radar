"""
Map panel — simplified world map with earthquake event plotting.

Uses DearPyGui drawlist to render a Mercator-projected world outline
and plot earthquake locations as color-coded circles.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

import dearpygui.dearpygui as dpg

from radar.ui.viewport import get_header_font

if TYPE_CHECKING:
    from radar.data.earthquake import EarthquakeEvent
    from radar.themes.loader import ThemeData

logger = logging.getLogger(__name__)

# Simplified world coastline data (lon, lat pairs for major landmasses)
# This is a minimal set of coastline points for visual reference
_COASTLINE_SEGMENTS: list[list[tuple[float, float]]] = [
    # North America (simplified outline)
    [(-170, 65), (-168, 55), (-160, 60), (-150, 61), (-140, 60),
     (-130, 55), (-125, 49), (-125, 40), (-120, 35), (-117, 33),
     (-110, 30), (-105, 25), (-100, 20), (-95, 18), (-90, 20),
     (-85, 15), (-83, 10), (-80, 8)],
    # North America East
    [(-80, 8), (-78, 18), (-82, 25), (-80, 27), (-82, 30),
     (-75, 36), (-73, 40), (-70, 42), (-67, 45), (-64, 47),
     (-60, 47), (-55, 50), (-57, 52), (-55, 55), (-60, 55),
     (-65, 60), (-70, 63), (-80, 64), (-95, 70), (-120, 72),
     (-140, 70), (-165, 65), (-170, 65)],
    # South America
    [(-80, 8), (-77, 0), (-80, -5), (-75, -15), (-70, -20),
     (-65, -25), (-57, -35), (-65, -55), (-70, -55),
     (-75, -50), (-75, -45), (-73, -40), (-70, -30),
     (-65, -20), (-60, -10), (-50, 0), (-45, -3),
     (-40, -10), (-35, -15), (-38, -20), (-45, -25),
     (-48, -30), (-53, -33), (-57, -35)],
    # Europe
    [(-10, 36), (-5, 36), (0, 38), (3, 43), (-2, 44),
     (-9, 43), (-10, 37)],
    [(3, 43), (5, 44), (10, 44), (13, 45), (15, 38),
     (18, 40), (20, 40), (25, 38), (28, 37), (30, 36)],
    [(10, 55), (12, 56), (15, 55), (20, 55), (25, 58),
     (28, 60), (30, 60), (30, 70), (20, 70), (15, 68),
     (5, 62), (5, 58), (8, 55), (10, 55)],
    [(-10, 50), (-5, 50), (0, 51), (2, 52), (5, 54),
     (8, 55)],
    # Africa
    [(-15, 10), (-17, 15), (-12, 25), (-5, 36), (10, 37),
     (30, 32), (35, 30), (40, 12), (50, 12), (45, 0),
     (40, -10), (35, -25), (28, -33), (18, -35), (15, -30),
     (12, -18), (10, -5), (5, 5), (0, 5), (-5, 5),
     (-15, 10)],
    # Asia (simplified)
    [(30, 36), (35, 37), (40, 42), (45, 42), (50, 38),
     (55, 27), (60, 25), (65, 25), (70, 20), (75, 15),
     (80, 7), (80, 15), (85, 20), (90, 22), (95, 18),
     (100, 14), (105, 10), (110, 20), (115, 23), (120, 25),
     (125, 30), (130, 33), (135, 35), (140, 40), (145, 45),
     (150, 50), (155, 55), (160, 60), (170, 63), (180, 65)],
    [(30, 60), (40, 70), (60, 72), (80, 70), (100, 72),
     (120, 70), (140, 62), (160, 60), (170, 63)],
    # Australia
    [(115, -35), (120, -35), (130, -32), (138, -33),
     (145, -38), (150, -37), (153, -28), (150, -22),
     (145, -15), (140, -12), (135, -12), (130, -13),
     (125, -15), (120, -18), (115, -22), (112, -25),
     (115, -35)],
]


def _lat_to_mercator_y(lat: float) -> float:
    """Convert latitude to Mercator Y (clamped to ±85°)."""
    lat = max(-85, min(85, lat))
    lat_rad = math.radians(lat)
    return math.log(math.tan(math.pi / 4 + lat_rad / 2))


class MapPanel:
    """Simplified world map with earthquake event plotting."""

    def __init__(self, theme: ThemeData) -> None:
        self._theme = theme
        self._draw_tag: int | str | None = None
        self._container_tag: int | str | None = None
        self._width = 100  # Placeholder, updated by resize()
        self._height = 100
        self._events: list[EarthquakeEvent] = []

    def resize(self, width: int, height: int) -> None:
        """Update panel dimensions and redraw."""
        self._width = width
        self._height = height
        if self._draw_tag and dpg.does_item_exist(self._draw_tag):
            dpg.configure_item(self._draw_tag, width=width, height=height)
            self._draw_base_map()
            if self._events:
                self.update(self._events)

    def _geo_to_pixel(self, lon: float, lat: float) -> tuple[float, float]:
        """Convert geographic coordinates to pixel coordinates."""
        x = ((lon + 180) / 360) * self._width
        # Mercator projection
        y_merc = _lat_to_mercator_y(lat)
        y_max = _lat_to_mercator_y(85)
        y = (1 - (y_merc + y_max) / (2 * y_max)) * self._height
        return x, y

    def build(self, parent: int | str) -> None:
        """Create the map panel UI layout."""
        with dpg.child_window(parent=parent, border=True) as container:
            self._container_tag = container

            # Header
            with dpg.group(horizontal=True):
                header_font = get_header_font()
                header = dpg.add_text("🌍 SEISMIC MAP")
                if header_font:
                    dpg.bind_item_font(header, header_font)

            dpg.add_separator()

            # Drawing canvas
            # Initial size doesn't matter, will be resized immediately
            with dpg.drawlist(width=100, height=100) as draw:
                self._draw_tag = draw

            self._draw_base_map()

    def _draw_base_map(self) -> None:
        """Render the world coastline outline."""
        if self._draw_tag is None:
            return

        dpg.delete_item(self._draw_tag, children_only=True)

        border = self._theme.color("border")
        surface = self._theme.color("surface")

        # Background
        dpg.draw_rectangle(
            (0, 0), (self._width, self._height),
            color=border, fill=surface, parent=self._draw_tag,
        )

        # Grid lines
        dim = (*self._theme.color("border")[:3], 40)
        for lon in range(-180, 181, 30):
            x = ((lon + 180) / 360) * self._width
            dpg.draw_line((x, 0), (x, self._height), color=dim, parent=self._draw_tag)
        for lat in range(-60, 81, 30):
            _, y = self._geo_to_pixel(0, lat)
            dpg.draw_line((0, y), (self._width, y), color=dim, parent=self._draw_tag)

        # Coastlines
        coast_color = (*self._theme.color("text_dim")[:3], 100)
        for segment in _COASTLINE_SEGMENTS:
            points = [self._geo_to_pixel(lon, lat) for lon, lat in segment]
            for i in range(len(points) - 1):
                dpg.draw_line(
                    points[i], points[i + 1],
                    color=coast_color, thickness=1,
                    parent=self._draw_tag,
                )

    def update(self, events: list[EarthquakeEvent]) -> None:
        """Plot earthquake events on the map."""
        self._events = events
        self._draw_base_map()

        if self._draw_tag is None:
            return

        for event in events:
            x, y = self._geo_to_pixel(event.longitude, event.latitude)

            # Size based on magnitude
            radius = max(2, min(12, event.magnitude * 1.5))

            # Color based on magnitude
            if event.magnitude < 3.0:
                color = self._theme.color("magnitude_low")
            elif event.magnitude < 5.0:
                color = self._theme.color("magnitude_mid")
            elif event.magnitude < 7.0:
                color = self._theme.color("magnitude_high")
            else:
                color = self._theme.color("magnitude_severe")

            # Semi-transparent fill
            fill = (*color[:3], 80)

            dpg.draw_circle(
                (x, y), radius,
                color=color, fill=fill,
                parent=self._draw_tag,
            )

    def update_theme(self, theme: ThemeData) -> None:
        """Apply a new theme and redraw."""
        self._theme = theme
        self._draw_base_map()
        if self._events:
            self.update(self._events)
