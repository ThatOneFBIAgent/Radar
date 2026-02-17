"""
Map panel — simplified world map with earthquake event plotting.

Uses DearPyGui drawlist to render a Mercator-projected world outline
(either as vector lines or a high-accuracy dot matrix) and plot
earthquake locations as color-coded circles.
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
_COASTLINE_SEGMENTS: list[list[tuple[float, float]]] = [
    # North America
    [(-170, 65), (-168, 55), (-160, 60), (-150, 61), (-140, 60),
     (-130, 55), (-125, 49), (-125, 40), (-120, 35), (-117, 33),
     (-110, 30), (-105, 25), (-100, 20), (-95, 18), (-90, 20),
     (-85, 15), (-83, 10), (-80, 8), (-78, 18), (-82, 25), (-80, 27),
     (-82, 30), (-75, 36), (-73, 40), (-70, 42), (-67, 45), (-64, 47),
     (-60, 47), (-55, 50), (-57, 52), (-55, 55), (-60, 55),
     (-65, 60), (-70, 63), (-80, 64), (-95, 70), (-120, 72),
     (-140, 70), (-165, 65), (-170, 65)],
    # South America
    [(-80, 8), (-77, 0), (-80, -5), (-75, -15), (-70, -20),
     (-65, -25), (-57, -35), (-65, -55), (-70, -55),
     (-75, -50), (-75, -45), (-73, -40), (-70, -30),
     (-65, -20), (-60, -10), (-50, 0), (-45, -3),
     (-40, -10), (-35, -15), (-38, -20), (-45, -25),
     (-48, -30), (-53, -33), (-57, -35), (-80, 8)],
    # Europe
    [(-10, 36), (-5, 36), (0, 38), (3, 43), (-2, 44),
     (-9, 43), (-10, 37), (-10, 36)],
    [(3, 43), (5, 44), (10, 44), (13, 45), (15, 38),
     (18, 40), (20, 40), (25, 38), (28, 37), (30, 36),
     (25, 36), (20, 38), (15, 38), (10, 40), (5, 42), (3, 43)],
    [(10, 55), (12, 56), (15, 55), (20, 55), (25, 58),
     (28, 60), (30, 60), (30, 70), (20, 70), (15, 68),
     (5, 62), (5, 58), (8, 55), (10, 55)],
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
     (150, 50), (155, 55), (160, 60), (170, 63), (180, 65),
     (180, 75), (140, 75), (80, 75), (30, 75), (30, 36)],
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


def _is_point_in_polygons(lon: float, lat: float, polygons: list[list[tuple[float, float]]]) -> bool:
    """Check if a coordinate is inside any of the provided polygons using ray casting."""
    for poly in polygons:
        inside = False
        n = len(poly)
        if n < 3:
            continue
        p1x, p1y = poly[0]
        for i in range(1, n + 1):
            p2x, p2y = poly[i % n]
            if lat > min(p1y, p2y):
                if lat <= max(p1y, p2y):
                    if lon <= max(p1x, p2x):
                        if p1y != p2y:
                            xints = (lat - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or lon <= xints:
                            inside = not inside
            p1x, p1y = p2x, p2y
        if inside:
            return True
    return False


class MapPanel:
    """World map with Dot Matrix TUI aesthetic and earthquake plotting."""

    def __init__(
        self,
        theme: ThemeData,
        on_hover: callable = None,
    ) -> None:
        self._theme = theme
        self._on_hover = on_hover
        self._draw_tag: int | str | None = None
        self._container_tag: int | str | None = None
        self._width = 100
        self._height = 100
        self._events: list[EarthquakeEvent] = []
        self._land_mask: list[tuple[float, float]] = []  # Cached pixel coordinates for dots
        self._water_mask: list[tuple[float, float]] = []

    def resize(self, width: int, height: int) -> None:
        """Update panel dimensions, re-calculate dot matrix, and redraw."""
        if width == self._width and height == self._height:
            return

        self._width = width
        self._height = height
        self._recalculate_masks()

        if self._draw_tag and dpg.does_item_exist(self._draw_tag):
            dpg.configure_item(self._draw_tag, width=width, height=height)
            self._draw_base_map()
            if self._events:
                self.update(self._events)

    def _recalculate_masks(self) -> None:
        """Scan the viewport and identify which dots fall on land vs water."""
        self._land_mask = []
        self._water_mask = []

        if self._width <= 0 or self._height <= 0:
            return

        # Adaptive grid spacing (dots approx every 8-12 pixels)
        spacing = max(8, min(14, int(self._width / 80)))
        
        # We sample Lon/Lat for each grid point
        for x in range(0, int(self._width), spacing):
            for y in range(0, int(self._height), spacing):
                # Reverse projection: Pixels to Geo
                # This is a bit tricky, but we can approximate:
                lon = (x / self._width) * 360 - 180
                
                # Mercator inverse for Lat
                y_max = _lat_to_mercator_y(85)
                # y = (1 - (y_merc + y_max) / (2 * y_max)) * height
                # y / height = 1 - (y_merc + y_max) / (2 * y_max)
                # (y_merc + y_max) / (2 * y_max) = 1 - y / height
                # y_merc = (1 - y / height) * (2 * y_max) - y_max
                y_merc = (1 - y / self._height) * (2 * y_max) - y_max
                
                # y_merc = log(tan(pi/4 + lat/2))
                # exp(y_merc) = tan(pi/4 + lat/2)
                # atan(exp(y_merc)) = pi/4 + lat/2
                # lat = 2 * (atan(exp(y_merc)) - pi/4)
                lat_rad = 2 * (math.atan(math.exp(y_merc)) - math.pi / 4)
                lat = math.degrees(lat_rad)

                if _is_point_in_polygons(lon, lat, _COASTLINE_SEGMENTS):
                    self._land_mask.append((float(x), float(y)))
                else:
                    self._water_mask.append((float(x), float(y)))

    def _geo_to_pixel(self, lon: float, lat: float) -> tuple[float, float]:
        """Convert geographic coordinates to pixel coordinates."""
        x = ((lon + 180) / 360) * self._width
        y_merc = _lat_to_mercator_y(lat)
        y_max = _lat_to_mercator_y(85)
        y = (1 - (y_merc + y_max) / (2 * y_max)) * self._height
        return x, y

    def build(self, parent: int | str) -> None:
        """Create the map panel UI layout."""
        with dpg.child_window(parent=parent, border=True, no_scrollbar=True, no_scroll_with_mouse=True) as container:
            self._container_tag = container

            with dpg.group(horizontal=True):
                header_font = get_header_font()
                header = dpg.add_text("[SCAN] SEISMIC SCANNER")
                if header_font:
                    dpg.bind_item_font(header, header_font)

            dpg.add_separator()

            with dpg.drawlist(width=100, height=100) as draw:
                self._draw_tag = draw

            self._draw_base_map()

    def _draw_base_map(self) -> None:
        """Render the TUI-style Dot Matrix world map."""
        if self._draw_tag is None:
            return

        dpg.delete_item(self._draw_tag, children_only=True)

        border = self._theme.color("border")
        surface = self._theme.color("surface")
        text_dim = self._theme.color("text_dim")
        accent = self._theme.color("primary")

        # Background
        dpg.draw_rectangle(
            (0, 0), (self._width, self._height),
            color=border, fill=surface, parent=self._draw_tag,
        )

        # Draw Water Dots (Dim)
        water_color = (*text_dim[:3], 30)
        for px, py in self._water_mask:
            dpg.draw_text((px, py), ".", color=water_color, size=12, parent=self._draw_tag)

        # Draw Land Dots (Bright/Accent)
        land_color = (*accent[:3], 120)
        for px, py in self._land_mask:
            dpg.draw_text((px, py), "o", color=land_color, size=10, parent=self._draw_tag)

        # Grid lines (Very Subtle)
        grid_color = (*border[:3], 40)
        for lon in range(-180, 181, 45):
            x = ((lon + 180) / 360) * self._width
            dpg.draw_line((x, 0), (x, self._height), color=grid_color, parent=self._draw_tag)
        for lat in range(-60, 81, 30):
            _, y = self._geo_to_pixel(0, lat)
            dpg.draw_line((0, y), (self._width, y), color=grid_color, parent=self._draw_tag)

    def update(self, events: list[EarthquakeEvent]) -> None:
        """Plot earthquake events and handle interactions."""
        self._events = events
        self._draw_base_map()
        self._update_hover()

    def _update_hover(self) -> None:
        """Check for mouse hover and draw tooltip."""
        if self._draw_tag is None:
            return

        # 1. Hit Test
        mouse_x, mouse_y = dpg.get_mouse_pos(local=True)
        hovered: EarthquakeEvent | None = None
        
        # Simple proximity check (squared distance for speed)
        # Check in reverse order (draw order) to pick top-most
        for event in reversed(self._events):
            x, y = self._geo_to_pixel(event.longitude, event.latitude)
            dist_sq = (mouse_x - x) ** 2 + (mouse_y - y) ** 2
            # Radius approx 6px + buffer
            if dist_sq < 100:  # 10px radius
                hovered = event
                break

        # Notify callback if hover changed (simple debounce could be added here if needed)
        if self._on_hover and hovered:
             self._on_hover(hovered.id)

        # 2. Draw Events (with highlight)
        for event in self._events:
            x, y = self._geo_to_pixel(event.longitude, event.latitude)
            radius = max(3, min(14, event.magnitude * 2.0))

            if event.magnitude < 3.0:
                color = self._theme.color("magnitude_low")
            elif event.magnitude < 5.0:
                color = self._theme.color("magnitude_mid")
            elif event.magnitude < 7.0:
                color = self._theme.color("magnitude_high")
            else:
                color = self._theme.color("magnitude_severe")

            # Highlight hovered event
            if hovered and event.id == hovered.id:
                dpg.draw_circle((x, y), radius + 4, color=self._theme.color("text_bright"), thickness=2, parent=self._draw_tag)
                fill = (*color[:3], 200) # Brighter fill
            else:
                fill = (*color[:3], 100)

            dpg.draw_circle((x, y), radius, color=color, fill=fill, thickness=2, parent=self._draw_tag)
            
            # Crosshair
            ch_color = (*color[:3], 200)
            dpg.draw_line((x-4, y), (x+4, y), color=ch_color, thickness=1, parent=self._draw_tag)
            dpg.draw_line((x, y-4), (x, y+4), color=ch_color, thickness=1, parent=self._draw_tag)

        # 3. Draw Tooltip
        if hovered:
            self._draw_tooltip(hovered, mouse_x, mouse_y)

    def _draw_tooltip(self, event: EarthquakeEvent, x: float, y: float) -> None:
        """Render a custom tooltip for the hovered event."""
        # Offset tooltip to not cover the dot
        tx, ty = x + 12, y + 12
        
        bg = self._theme.color("surface")
        border = self._theme.color("border")
        text = self._theme.color("text_bright")
        
        # Determine magnitude color
        if event.magnitude < 3.0:
            mag_color = self._theme.color("magnitude_low")
        elif event.magnitude < 5.0:
            mag_color = self._theme.color("magnitude_mid")
        elif event.magnitude < 7.0:
            mag_color = self._theme.color("magnitude_high")
        else:
            mag_color = self._theme.color("magnitude_severe")

        # Background box (approximate size)
        dpg.draw_rectangle((tx, ty), (tx + 160, ty + 46), color=border, fill=bg, parent=self._draw_tag)
        dpg.draw_rectangle((tx + 2, ty + 2), (tx + 4, ty + 44), color=mag_color, fill=mag_color, parent=self._draw_tag)

        # Text
        dpg.draw_text((tx + 12, ty + 4), f"M {event.magnitude:.1f}", color=mag_color, size=16, parent=self._draw_tag)
        dpg.draw_text((tx + 12, ty + 24), event.place[:22], color=text, size=13, parent=self._draw_tag)

    def update_theme(self, theme: ThemeData) -> None:
        """Apply a new theme and redraw."""
        self._theme = theme
        self._draw_base_map()
        if self._events:
            self.update(self._events)
