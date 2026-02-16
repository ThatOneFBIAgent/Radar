"""
Earthquake panel — scrollable event list with color-coded rows.

Renders the live earthquake feed as a sortable table with
magnitude-based coloring and highlight animations for new events.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

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
        self._header_tag: int | str | None = None
        self._count_tag: int | str | None = None
        self._row_tags: list[int | str] = []

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
        with dpg.child_window(parent=parent, border=True) as container:
            self._container_tag = container

            # Header
            with dpg.group(horizontal=True):
                header_font = get_header_font()
                self._header_tag = dpg.add_text("⚡ SEISMIC MONITOR")
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
            ) as table:
                self._table_tag = table

                dpg.add_table_column(label="MAG", init_width_or_weight=0.08)
                dpg.add_table_column(label="DEPTH", init_width_or_weight=0.08)
                dpg.add_table_column(label="LOCATION", init_width_or_weight=0.35)
                dpg.add_table_column(label="TIME (UTC)", init_width_or_weight=0.20)
                dpg.add_table_column(label="COORDINATES", init_width_or_weight=0.20)
                dpg.add_table_column(label="TYPE", init_width_or_weight=0.09)

    def update(self, events: list[EarthquakeEvent], new_ids: list[str] | None = None) -> None:
        """Refresh the table with new event data."""
        self._events = events

        if new_ids:
            self._highlighter.add_many(new_ids)

        # Clear existing rows
        if self._table_tag is not None:
            for tag in self._row_tags:
                try:
                    dpg.delete_item(tag)
                except Exception:
                    pass
        self._row_tags.clear()

        # Populate rows
        for event in events:
            with dpg.table_row(parent=self._table_tag) as row:
                self._row_tags.append(row)

                mag_color = self._mag_color(event.magnitude)
                is_significant = event.magnitude >= self._threshold

                # Magnitude
                mag_text = f" {event.magnitude:5.1f} " if event.magnitude >= 0 else f"{event.magnitude:5.1f} "
                tag = dpg.add_text(mag_text, color=mag_color)
                if is_significant:
                    dpg.add_text("▲", color=self._theme.color("danger"), before=tag)

                # Depth
                dpg.add_text(f"{event.depth:.1f} km", color=self._theme.color("text"))

                # Location
                dpg.add_text(
                    event.place[:50],
                    color=self._theme.color("text_bright") if is_significant else self._theme.color("text"),
                )

                # Time
                dpg.add_text(event.time_str, color=self._theme.color("text_dim"))

                # Coordinates
                dpg.add_text(event.coords_str, color=self._theme.color("text_dim"))

                # Type
                dpg.add_text(
                    event.mag_type.upper() if event.mag_type else "—",
                    color=self._theme.color("text_dim"),
                )

        # Update count
        if self._count_tag:
            dpg.set_value(self._count_tag, f"{len(events)} events")

    def update_highlights(self) -> None:
        """Update highlight animations (call each frame)."""
        self._highlighter.cleanup()

    def update_theme(self, theme: ThemeData) -> None:
        """Apply a new theme to the panel."""
        self._theme = theme
        self._highlighter = Highlighter(
            decay_ms=theme.highlight_decay_ms,
            pulse_ms=theme.pulse_ms,
        )
        # Re-render with current events
        if self._events:
            self.update(self._events)
