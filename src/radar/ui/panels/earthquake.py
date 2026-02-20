"""
Earthquake panel — scrollable event list with color-coded rows.

Renders the live earthquake feed as a sortable table with
magnitude-based coloring and highlight animations for new events.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import math
import time
import dearpygui.dearpygui as dpg

from radar.ui.animations import Highlighter, lerp_color
from radar.ui.viewport import get_header_font

if TYPE_CHECKING:
    from radar.data.earthquake import EarthquakeEvent
    from radar.themes.loader import ThemeData

logger = logging.getLogger(__name__)


class EarthquakePanel:
    """Earthquake event list panel."""

    def __init__(self, theme: ThemeData, highlight_threshold: float = 4.5) -> None:
        self._theme = theme
        self._threshold = highlight_threshold
        self._highlighter = Highlighter(
            decay_ms=theme.highlight_decay_ms,
            pulse_ms=theme.pulse_ms,
        )
        self._events: list[EarthquakeEvent] = []
        self._table_tag: int | str | None = None
        self._container_tag: int | str | None = None
        self._count_tag: int | str | None = None
        self._row_tags: list[int | str] = []
        self._user_lon: float | None = None
        self._highlight_theme: int | str | None = None
        self._mag_themes: dict[str, int | str] = {}
        self._on_click: callable = None
        self._selected_id: str | None = None

        # Scrolling state
        self._scroll_y = 0.0
        self._target_scroll_y = 0.0
        self._scroll_active = False
        self._scroll_start_time = 0.0
        self._scroll_duration = 0.5  # slightly faster
        self._scroll_event_id: str | None = None # Track the active target

    def set_user_location(self, lat: float, lon: float) -> None:
        """Update the reference location for distance calculations."""
        self._user_lat = lat
        self._user_lon = lon

    def _haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate the great circle distance in kilometers between two points."""
        R = 6371.0  # Earth radius in kilometers

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def _mag_color(self, magnitude: float) -> tuple[int, int, int, int]:
        """Get the color for a given magnitude."""
        if magnitude < 3.0:
            return self._theme.color("magnitude_low")
        elif magnitude < 5.0:
            return self._theme.color("magnitude_mid")
        elif magnitude < 7.0:
            return self._theme.color("magnitude_high")
        return self._theme.color("magnitude_severe")

    def build(self, parent: int | str) -> None:
        """Create the earthquake panel UI layout."""
        # Create highlight theme
        with dpg.theme() as self._highlight_theme:
            with dpg.theme_component(dpg.mvTableRow):
                # Use a subtle highlight color (e.g., semi-transparent blueish/white)
                # Or derive from theme if possible. using a hardcoded safe color for now.
                dpg.add_theme_color(dpg.mvThemeCol_TableRowBg, (100, 100, 120, 100))

        # Create themes for magnitude colors
        for level in ["low", "mid", "high", "severe"]:
            with dpg.theme() as theme:
                with dpg.theme_component(dpg.mvSelectable):
                    dpg.add_theme_color(dpg.mvThemeCol_Text, self._theme.color(f"magnitude_{level}"))
                    dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, (0, 0, 0, 0)) # No flash on click
            self._mag_themes[level] = theme

        with dpg.child_window(parent=parent, border=True) as container:
            self._container_tag = container

            # Header
            with dpg.group(horizontal=True):
                header_font = get_header_font()
                self._header_tag = dpg.add_text("[MON] SEISMIC MONITOR")
                if header_font:
                    dpg.bind_item_font(self._header_tag, header_font)

                dpg.add_spacer(width=-1)
                self._count_tag = dpg.add_text("0 events", color=self._theme.color("text_dim"))

            dpg.add_separator()

            # Table
            with dpg.table(
                header_row=True,
                borders_innerH=True,
                borders_outerH=True,
                borders_innerV=True,
                borders_outerV=True,
                row_background=True,
                resizable=True,
                sortable=True,
                scrollY=True,
                policy=dpg.mvTable_SizingStretchProp,
                callback=self._sort_callback, # Added callback for sorting
            ) as table:
                self._table_tag = table

                self._col_tags = {}
                self._col_tags["MAG"] = dpg.add_table_column(label="MAG", init_width_or_weight=0.08)
                self._col_tags["DEPTH"] = dpg.add_table_column(label="DEPTH", init_width_or_weight=0.08)
                self._col_tags["LOCATION"] = dpg.add_table_column(label="LOCATION", init_width_or_weight=0.35)
                self._col_tags["TIME"] = dpg.add_table_column(label="TIME (UTC)", init_width_or_weight=0.20)
                self._col_tags["DISTANCE"] = dpg.add_table_column(label="DIST", init_width_or_weight=0.10)
                self._col_tags["COORDINATES"] = dpg.add_table_column(label="COORDINATES", init_width_or_weight=0.20)
                self._col_tags["TYPE"] = dpg.add_table_column(label="TYPE", init_width_or_weight=0.09)

        # Re-render table
        self.update(self._events)

    def _on_row_clicked(self, sender: int | str, app_data: list, user_data: str) -> None:
        """Handle clicking an earthquake row via selectable."""
        event_id = user_data
        
        # Immediately deselect the selectable itself (we handle selection via row themes)
        dpg.set_value(sender, False)

        if event_id and self._on_click:
            self._on_click(event_id)
            self.highlight_event(event_id)

    def set_on_click(self, callback: callable) -> None:
        """Set the callback for when an earthquake row is clicked."""
        self._on_click = callback

    def _sort_callback(self, sender: int | str, sort_specs: dict | list) -> None:
        """Handle table sort events."""
        if sort_specs is None:
            return

        specs = sort_specs
        if isinstance(sort_specs, dict):
             specs = sort_specs.get("specs")
        
        if not specs:
            return

        # Get the first sort spec (single column sort for now)
        col_id = specs[0][0]
        direction = specs[0][1] # 1 is asc, -1 is desc
        
        # Helper for distance sort
        def dist_sort(e: EarthquakeEvent) -> float:
            if self._user_lat is None or self._user_lon is None:
                return float('inf')
            return self._haversine(self._user_lat, self._user_lon, e.latitude, e.longitude)

        # Sort key map
        key_map = {
            self._col_tags["MAG"]: lambda e: e.magnitude,
            self._col_tags["DEPTH"]: lambda e: e.depth,
            self._col_tags["LOCATION"]: lambda e: e.place,
            self._col_tags["TIME"]: lambda e: e.time,
            self._col_tags["DISTANCE"]: dist_sort,
            self._col_tags["COORDINATES"]: lambda e: e.latitude, # Rough sort by lat?
            self._col_tags["TYPE"]: lambda e: e.mag_type if e.mag_type else "",
        }

        sort_key = key_map.get(col_id)
        if sort_key:
            reverse = direction < 0
            self._events.sort(key=sort_key, reverse=reverse)
            # Re-render table
            self.update(self._events)
            
    def update(self, events: list[EarthquakeEvent], new_ids: list[str] | None = None) -> None:
        """Refresh the table with new event data."""
        self._events = events

        if new_ids:
            self._highlighter.add_many(new_ids)

        # Clear existing rows
        if self._table_tag is not None:
             # Safely delete tracked rows
             for tag in self._row_tags:
                try:
                    if dpg.does_item_exist(tag):
                        dpg.delete_item(tag)
                except Exception:
                    pass # Ignore deletion errors

        self._row_tags.clear()
        self._row_map: dict[str, int | str] = {}

        # Populate rows
        for event in events:
            # Populate rows
            with dpg.table_row(parent=self._table_tag) as row:
                self._row_tags.append(row)
                self._row_map[event.id] = row

                mag_color = self._mag_color(event.magnitude)
                is_significant = event.magnitude >= self._threshold

                # Magnitude Column (Selectable for row interaction)
                with dpg.group(horizontal=True):
                    if is_significant:
                        dpg.add_text("!", color=self._theme.color("danger"))
                    
                    mag_text = f"{event.magnitude:4.1f}" if event.magnitude >= 0 else f"{event.magnitude:4.1f}"
                    # Use a selectable for the whole row interaction
                    sel = dpg.add_selectable(
                        label=mag_text, 
                        callback=self._on_row_clicked, 
                        user_data=event.id,
                        span_columns=True
                    )
                    
                    # Apply color theme based on magnitude
                    level = "low"
                    if event.magnitude >= 7.0: level = "severe"
                    elif event.magnitude >= 5.0: level = "high"
                    elif event.magnitude >= 3.0: level = "mid"
                    
                    dpg.bind_item_theme(sel, self._mag_themes[level])

                # Depth Column
                dpg.add_text(f"{event.depth:.1f} km", color=self._theme.color("text"))

                # Location
                dpg.add_text(
                    event.place[:50],
                    color=self._theme.color("text_bright") if is_significant else self._theme.color("text"),
                )

                # Time
                dpg.add_text(event.time_str, color=self._theme.color("text_dim"))
                
                # Distance Column
                dist_str = "—"
                if self._user_lat is not None and self._user_lon is not None:
                    km = self._haversine(self._user_lat, self._user_lon, event.latitude, event.longitude)
                    dist_str = f"{km:.0f} km"
                dpg.add_text(dist_str, color=self._theme.color("text_dim"))

                # Coordinates
                dpg.add_text(event.coords_str, color=self._theme.color("text_dim"))

                # Type
                dpg.add_text(
                    event.mag_type.upper() if event.mag_type else "—",
                    color=self._theme.color("text_dim"),
                )

        # If we have a selection, re-apply the theme to the new row
        if self._selected_id:
            row = self._row_map.get(self._selected_id)
            if row and dpg.does_item_exist(row):
                dpg.bind_item_theme(row, self._highlight_theme)

        # Update count
        if self._count_tag:
            dpg.set_value(self._count_tag, f"{len(events)} events")

    def highlight_event(self, event_id: str) -> None:
        """Highlight (select) a specific event row."""
        if not self._highlight_theme:
            return

        # Deselect previous
        if self._selected_id:
            prev_row = self._row_map.get(self._selected_id)
            if prev_row and dpg.does_item_exist(prev_row):
                dpg.bind_item_theme(prev_row, 0)

        # Select target
        self._selected_id = event_id
        row = self._row_map.get(event_id)
        if row and dpg.does_item_exist(row):
            dpg.bind_item_theme(row, self._highlight_theme)
            
            # Auto-scroll to row (approximate)
            self.scroll_to(event_id)

    def scroll_to(self, event_id: str) -> None:
        """Initialize a smooth scroll to the specified event."""
        if not self._table_tag or event_id not in self._row_map:
            return
            
        # DEBOUNCE: Don't restart the animation if we are already moving to this target
        if self._scroll_active and self._scroll_event_id == event_id:
            return

        try:
            # Find the visual index of the event
            row_index = -1
            for i, e in enumerate(self._events):
                if e.id == event_id:
                    row_index = i
                    break
            
            if row_index == -1:
                return

            # Fine-tuned row height (24px base + small buffer for margins)
            row_height = 24.5
            self._target_scroll_y = float(row_index * row_height)
            self._scroll_y = float(dpg.get_y_scroll(self._table_tag))
            
            # Use a slightly wider threshold to prevent micro-jitter
            if abs(self._target_scroll_y - self._scroll_y) > 2.0:
                self._scroll_active = True
                self._scroll_event_id = event_id
                self._scroll_start_time = time.monotonic()
                logger.debug("Scrolling to event %s (index %d, target %f)", event_id, row_index, self._target_scroll_y)
            else:
                self._scroll_active = False
        except Exception as e:
            logger.error("Failed to calculate scroll target: %s", e)

    def update_highlights(self) -> None:
        """Update highlight animations (call each frame)."""
        self._highlighter.cleanup()
        
        # Handle smooth scroll animation (Ease In-Out)
        if self._scroll_active and self._table_tag:
            now = time.monotonic()
            elapsed = now - self._scroll_start_time
            t = min(1.0, elapsed / self._scroll_duration)
            
            # Ease in-out cubic
            if t < 0.5:
                interp = 4 * t * t * t
            else:
                interp = 1 - (-2 * t + 2) ** 3 / 2
            
            current_y = self._scroll_y + (self._target_scroll_y - self._scroll_y) * interp
            dpg.set_y_scroll(self._table_tag, current_y)
            
            if t >= 1.0:
                self._scroll_active = False

    def update_theme(self, theme: ThemeData, soft: bool = False) -> None:
        """Apply a new theme to the panel."""
        self._theme = theme
        self._highlighter = Highlighter(
            decay_ms=theme.highlight_decay_ms,
            pulse_ms=theme.pulse_ms,
        )
        # Re-render with current events
        if self._events and not soft:
            self.update(self._events)
