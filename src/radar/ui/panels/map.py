"""
Map panel — simplified world map with earthquake event plotting.

Uses DearPyGui drawlist to render a Mercator-projected world outline
(either as vector lines or a high-accuracy dot matrix) and plot
earthquake locations as color-coded circles.
"""

from __future__ import annotations

import logging
import math
import time
import json
from typing import TYPE_CHECKING
from pathlib import Path

import dearpygui.dearpygui as dpg

from radar.ui.viewport import get_header_font

if TYPE_CHECKING:
    from radar.data.earthquake import EarthquakeEvent
    from radar.themes.loader import ThemeData

from radar.config import DATA_DIR

logger = logging.getLogger(__name__)

# Load high-resolution world map polygons
_COASTLINE_POLYGONS: list[list[tuple[float, float]]] = []
try:
    _poly_path = DATA_DIR / "world_polygons.json"
    if _poly_path.exists():
        with open(_poly_path, "r") as f:
            _COASTLINE_POLYGONS = json.load(f)
            logger.info(f"Loaded {len(_COASTLINE_POLYGONS)} map polygons.")
    else:
        logger.warning(f"world_polygons.json not found at {_poly_path}")
except Exception as e:
    logger.error(f"Failed to load world map polygons: {e}")

# High-resolution map caching for speed
_GEO_CACHE: dict[tuple[int, int], bool] = {}
_POLY_BBOXES: list[tuple[float, float, float, float] | None] = []

def _init_bboxes():
    for poly in _COASTLINE_POLYGONS:
        if not poly:
            _POLY_BBOXES.append(None)
            continue
        minx = min(p[0] for p in poly)
        maxx = max(p[0] for p in poly)
        miny = min(p[1] for p in poly)
        maxy = max(p[1] for p in poly)
        _POLY_BBOXES.append((minx, maxx, miny, maxy))

if _COASTLINE_POLYGONS and not _POLY_BBOXES:
    _init_bboxes()


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
        # Check bounding box first for fast rejection if desired (omitted for brevity)
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
        on_click: callable = None,
    ) -> None:
        self._theme = theme
        self._on_hover = on_hover
        self._on_click = on_click
        self._draw_tag: int | str | None = None
        self._static_layer: int | str | None = None
        self._dynamic_layer: int | str | None = None
        self._container_tag: int | str | None = None
        self._width = 100
        self._height = 100
        self._events: list[EarthquakeEvent] = []
        self._land_mask: list[tuple[float, float]] = []  # Cached pixel coordinates for dots
        self._water_mask: list[tuple[float, float]] = []
        
        self._new_events: dict[str, float] = {}
        self._user_lat: float | None = None
        self._user_lon: float | None = None
        
        # Radar sweep animation state
        self._last_sweep_angle = 0.0
        
        # Resize debounce state
        self._dirty = False
        self._last_resize_time = 0.0

        # Selection state
        self._selected_id: str | None = None
        self._last_hovered_id: str | None = None  # Track to avoid re-firing callbacks

        # Felt warning state
        self._felt_warning: bool = False
        self._felt_warning_tag: int | str | None = None

    def set_user_location(self, lat: float, lon: float) -> None:
        """Update the reference location for map pin."""
        self._user_lat = lat
        self._user_lon = lon

    def resize(self, width: int, height: int) -> None:
        """Update panel dimensions, mark as dirty to debounce recalculations."""
        if width == self._width and height == self._height:
            return

        self._width = width
        self._height = height
        self._dirty = True
        self._last_resize_time = time.monotonic()

        if self._draw_tag and dpg.does_item_exist(self._draw_tag):
            dpg.configure_item(self._draw_tag, width=width, height=height)

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
                lon = (x / self._width) * 360 - 180
                
                y_max = _lat_to_mercator_y(85)
                y_merc = (1 - y / self._height) * (2 * y_max) - y_max
                
                lat_rad = 2 * (math.atan(math.exp(y_merc)) - math.pi / 4)
                lat = math.degrees(lat_rad)

                # Use 0.5 degree grid cache to speed up ray casting!
                # Since TUI dots are typically 1-5 degrees apart, 0.5 is plenty of precision.
                lon_i = int((lon + 180) * 2)
                lat_i = int((lat + 90) * 2)
                key = (lon_i, lat_i)
                
                if key in _GEO_CACHE:
                    is_land = _GEO_CACHE[key]
                else:
                    is_land = False
                    for i, bbox in enumerate(_POLY_BBOXES):
                        if bbox is None: continue
                        minx, maxx, miny, maxy = bbox
                        if lon >= minx and lon <= maxx and lat >= miny and lat <= maxy:
                            if _is_point_in_polygons(lon, lat, [_COASTLINE_POLYGONS[i]]):
                                is_land = True
                                break
                    _GEO_CACHE[key] = is_land

                if is_land:
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
                
                # Felt warning indicator (hidden by default)
                self._felt_warning_tag = dpg.add_text(
                    " ! [GROUND MOTION POSSIBLE]", color=self._theme.color("danger"), show=False
                )
                if header_font:
                    dpg.bind_item_font(self._felt_warning_tag, header_font)

            dpg.add_separator()

            with dpg.drawlist(width=100, height=100) as draw:
                self._draw_tag = draw
                self._static_layer = dpg.add_draw_layer()
                self._dynamic_layer = dpg.add_draw_layer()

            self._draw_base_map()

    def _draw_base_map(self) -> None:
        """Render the TUI-style Dot Matrix world map."""
        if self._static_layer is None:
            return

        dpg.delete_item(self._static_layer, children_only=True)

        border = self._theme.color("border")
        surface = self._theme.color("surface")
        text_dim = self._theme.color("text_dim")
        accent = self._theme.color("primary")

        # Background
        dpg.draw_rectangle(
            (0, 0), (self._width, self._height),
            color=border, fill=surface, parent=self._static_layer,
        )

        char_water = self._theme.map_water_char
        char_land = self._theme.map_land_char
        char_size = 12 if char_water in (".", "·") else 14

        # Draw Water Dots (Dim)
        water_color = (*text_dim[:3], 40)
        for px, py in self._water_mask:
            dpg.draw_text((px, py), char_water, color=water_color, size=char_size, parent=self._static_layer)

        # Draw Land Dots (Bright/Accent)
        land_color = (*accent[:3], 150)
        for px, py in self._land_mask:
            dpg.draw_text((px, py), char_land, color=land_color, size=char_size, parent=self._static_layer)

        # Grid lines (Very Subtle)
        grid_color = (*border[:3], 40)
        for lon in range(-180, 181, 45):
            x = ((lon + 180) / 360) * self._width
            dpg.draw_line((x, 0), (x, self._height), color=grid_color, parent=self._static_layer)
        for lat in range(-60, 81, 30):
            _, y = self._geo_to_pixel(0, lat)
            dpg.draw_line((0, y), (self._width, y), color=grid_color, parent=self._static_layer)

    # Note: Radar sweep line drawing is split into `update_animations`.
    # `update` is for data, `update_animations` runs every frame for sweeps.

    def update(self, events: list[EarthquakeEvent], new_ids: list[str] | None = None) -> None:
        """Plot earthquake events and handle interactions."""
        self._events = events
        
        if new_ids:
            now = time.monotonic()
            for eid in new_ids:
                self._new_events[eid] = now
                
        # Static base drawing is separated and should not be wiped away every time an event is added.
        self.update_animations()

    def update_animations(self) -> None:
        """Called every frame to update animated map elements like radar sweeps."""
        if self._dynamic_layer is None or not dpg.does_item_exist(self._dynamic_layer):
            return

        # 0. Handle resize debounce
        if self._dirty:
            now = time.monotonic()
            if now - self._last_resize_time > 0.15:  # 150ms debounce
                self._recalculate_masks()
                self._dirty = False
                self._draw_base_map() # Redraw static layer ONCE after resize completes
            else:
                # Still resizing, fast-return to keep UI responsive
                return

        # 1. Clean dynamic layers (Sweep line + Events)
        dpg.delete_item(self._dynamic_layer, children_only=True)

        # 2. Draw Radar Sweep (if enabled)
        if self._theme.map_radar_sweep:
            center_x, center_y = self._width / 2, self._height / 2
            # Use full hypotenuse to ensure the trailing triangle easily covers all corners
            radius = math.hypot(self._width, self._height)
            
            # Sweep angle based on time (1 full rotation every 4 seconds)
            t = time.monotonic()
            angle = (t % 4.0) / 4.0 * math.pi * 2
            
            base_sweep_color = self._theme.colors.get("map_sweep", self._theme.color("success"))
            sweep_color = (*base_sweep_color[:3], 180)
            
            end_x = center_x + math.cos(angle) * radius
            end_y = center_y + math.sin(angle) * radius
            
            # Draw the bright active leading line
            dpg.draw_line((center_x, center_y), (end_x, end_y), color=sweep_color, thickness=2, parent=self._dynamic_layer)
            
            # Draw the trailing gradient (approximated with a polygon)
            trail_angle = angle - 0.5  # About 30 degrees trailing
            trail_x = center_x + math.cos(trail_angle) * radius
            trail_y = center_y + math.sin(trail_angle) * radius
            
            trail_color = (*base_sweep_color[:3], 30)
            dpg.draw_triangle(
                (center_x, center_y), (end_x, end_y), (trail_x, trail_y),
                color=(0, 0, 0, 0), fill=trail_color, parent=self._dynamic_layer
            )

        # 3. Draw Events & tooltips
        self._update_hover()
        
        # 4. Draw expanding pulses for new events
        now = time.monotonic()
        # Waves take up to an hour to fully propagate across the world map
        self._new_events = {k: v for k, v in self._new_events.items() if (now - v) < 3600.0}
        
        for eid, spawn_time in self._new_events.items():
            event = next((e for e in self._events if e.id == eid), None)
            if not event:
                continue
            
            # Simulate wave travel distance until magnitude attenuates down to ~1.0
            effective_mag = max(0.0, event.magnitude - 1.0)
            
            # Peak radius scaled physically. Earth circ. ~40,000km plotted on map width.
            # Convert 40,000 km to pixels to get our dynamic px/km ratio
            px_per_km = self._width / 40075.0 if self._width > 0 else 0.02
            
            # Attenuation target distance (approx km scale roughly based on magnitude squared)
            # A M9.0 quake might be "felt" roughly 1500-2000 km away.
            target_distance_km = 20.0 * (effective_mag ** 2.2) 
            target_radius = 10.0 + (target_distance_km * px_per_km)
            
            # Realistic wave velocity (P-waves ~6 km/s, multiplied x 4 time scale = 24 km/s visual)
            speed_km_sec = 24.0 
            speed_px_sec = speed_km_sec * px_per_km
            
            wave_duration = max(4.0, (target_radius - 10.0) / max(0.001, speed_px_sec))
            
            elapsed = now - spawn_time
            if elapsed > wave_duration:
                continue
                
            progress = min(1.0, elapsed / wave_duration) # 0 to 1
            
            x, y = self._geo_to_pixel(event.longitude, event.latitude)
            
            # Primary P-Wave
            radius_p = 10.0 + progress * (target_radius - 10.0)
            
            # Fade out using an easing curve so waves stay sharp before cleanly dissolving
            alpha_p = max(0, min(255, int(255 * (1.0 - (progress ** 1.5)))))
            
            pulse_color = self._theme.color("primary")
            if event.magnitude >= 4.5:
                 pulse_color = self._theme.color("danger")
            elif event.magnitude >= 3.0:
                 pulse_color = self._theme.color("magnitude_mid")
            
            # Fill the inner area with a very faint, trailing background color
            fill_alpha = int(alpha_p * 0.15)
            
            dpg.draw_circle(
                (x, y), 
                radius_p, 
                color=(*pulse_color[:3], alpha_p), 
                fill=(*pulse_color[:3], fill_alpha), 
                thickness=2, 
                parent=self._dynamic_layer
            )

        # 5. Draw user location pin
        if self._user_lat is not None and self._user_lon is not None:
            ux, uy = self._geo_to_pixel(self._user_lon, self._user_lat)
            pin_color = self._theme.color("primary")
            
            dpg.draw_circle((ux, uy), 4, color=pin_color, fill=pin_color, parent=self._dynamic_layer)
            t = (now % 2.0) / 2.0
            r = 4 + t * 10
            a = int(255 * (1 - t))
            dpg.draw_circle((ux, uy), r, color=(*pin_color[:3], a), parent=self._dynamic_layer)

    def _update_hover(self) -> None:
        """Check for mouse hover and draw tooltip."""
        if self._dynamic_layer is None:
            return

        # 1. Hit Test
        hovered: EarthquakeEvent | None = None
        mouse_x, mouse_y = 0.0, 0.0
        
        # Only perform hit tests if the mouse is physically over the map panel
        if self._draw_tag and dpg.is_item_hovered(self._draw_tag):
            try:
                mouse_x, mouse_y = dpg.get_drawing_mouse_pos()
            except AttributeError:
                mouse_x, mouse_y = dpg.get_mouse_pos(local=True)

            # Simple proximity check (squared distance for speed)
            for event in reversed(self._events):
                x, y = self._geo_to_pixel(event.longitude, event.latitude)
                dist_sq = (mouse_x - x) ** 2 + (mouse_y - y) ** 2
                if dist_sq < 100:  # 10px radius
                    hovered = event
                    break

        # Notify hover callback only on changes
        hovered_id = hovered.id if hovered else None
        if hovered_id != self._last_hovered_id:
            self._last_hovered_id = hovered_id
            if self._on_hover:
                self._on_hover(hovered_id)  # None signals unhover
             
        # Handle click
        if dpg.is_mouse_button_clicked(dpg.mvMouseButton_Left) and self._draw_tag and dpg.is_item_hovered(self._draw_tag):
            if self._on_click:
                if hovered:
                    self._on_click(hovered.id)
                elif self._selected_id:
                    # Clicked empty space on map — deselect
                    self._on_click(None)

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
            is_selected = self._selected_id and event.id == self._selected_id
            if (hovered and event.id == hovered.id) or is_selected:
                thickness = 3 if is_selected else 2
                ring_color = self._theme.color("text_bright")
                
                # Selected event gets a pulsating highlight
                if is_selected:
                    pulse = (math.sin(time.monotonic() * 5.0) + 1.0) / 2.0  # 0 to 1
                    thickness = 2 + int(pulse * 3)
                    ring_color = (*ring_color[:3], 150 + int(pulse * 105))

                dpg.draw_circle((x, y), radius + 4, color=ring_color, thickness=thickness, parent=self._dynamic_layer)
                fill = (*color[:3], 220 if is_selected else 200) # Brighter fill
            else:
                fill = (*color[:3], 100)

            dpg.draw_circle((x, y), radius, color=color, fill=fill, thickness=2, parent=self._dynamic_layer)
            
            # Crosshair
            ch_thickness = 2 if is_selected else 1
            ch_color = (*color[:3], 255 if is_selected else 200)
            dpg.draw_line((x-4, y), (x+4, y), color=ch_color, thickness=ch_thickness, parent=self._dynamic_layer)
            dpg.draw_line((x, y-4), (x, y+4), color=ch_color, thickness=ch_thickness, parent=self._dynamic_layer)

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
        dpg.draw_rectangle((tx, ty), (tx + 160, ty + 46), color=border, fill=bg, parent=self._dynamic_layer)
        dpg.draw_rectangle((tx + 2, ty + 2), (tx + 4, ty + 44), color=mag_color, fill=mag_color, parent=self._dynamic_layer)

        # Text
        dpg.draw_text((tx + 12, ty + 4), f"M {event.magnitude:.1f}", color=mag_color, size=16, parent=self._dynamic_layer)
        dpg.draw_text((tx + 12, ty + 24), event.place[:22], color=text, size=13, parent=self._dynamic_layer)

    def set_selection(self, event_id: str | None) -> None:
        """Set the current selected event ID for persistent highlighting."""
        self._selected_id = event_id
        logger.debug("Map selection set to: %s", self._selected_id)

    def set_felt_warning(self, active: bool) -> None:
        """Enable or disable the blinking FELT warning on the header."""
        self._felt_warning = active
        if self._felt_warning_tag and dpg.does_item_exist(self._felt_warning_tag):
            if active:
                # Blink: toggle visibility based on time (~2Hz)
                blink = int(time.monotonic() * 4) % 2 == 0
                dpg.configure_item(self._felt_warning_tag, show=blink)
                # Pulse the color: danger with varying alpha
                pulse = (math.sin(time.monotonic() * 6) + 1.0) / 2.0
                alpha = int(150 + pulse * 105)
                base_color = self._theme.color("danger")
                dpg.configure_item(
                    self._felt_warning_tag, color=(*base_color[:3], alpha)
                )
            else:
                dpg.configure_item(self._felt_warning_tag, show=False)

    def update_theme(self, theme: ThemeData, soft: bool = False) -> None:
        """Apply a new theme and redraw."""
        self._theme = theme
        self._draw_base_map()
        if self._events:
            self.update(self._events)
