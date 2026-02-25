"""
Status bar — bottom bar with system info, timestamps, and controls.

Displays: last update time, connection status, active theme,
polling interval, UTC clock, and theme selector.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

import dearpygui.dearpygui as dpg

from radar.themes.loader import ThemeData, get_available_themes

logger = logging.getLogger(__name__)


class StatusBar:
    """Bottom status bar with system information and controls."""

    def __init__(
        self,
        theme: ThemeData,
        available_themes: list[str] | None = None,
        on_theme_change: Callable[[str], None] | None = None,
        on_retry: Callable[[], None] | None = None,
    ) -> None:
        self._theme = theme
        self._available = available_themes or get_available_themes()
        self._on_theme_change = on_theme_change
        self._on_retry = on_retry
        self._tags: dict[str, int | str] = {}

    def _status_clicked(self, sender: int | str, app_data: Any, user_data: Any) -> None:
        if self._on_retry:
            self._on_retry()

    def build(self, parent: int | str) -> None:
        """Create the status bar layout."""
        with dpg.child_window(
            parent=parent,
            border=True,
            height=32,
            no_scrollbar=True,
        ):
            with dpg.group(horizontal=True):
                with dpg.item_handler_registry() as hr:
                    dpg.add_item_clicked_handler(callback=self._status_clicked)

                # Connection indicator
                self._tags["status"] = dpg.add_text(
                    "(*) ONLINE", color=self._theme.color("success")
                )
                dpg.bind_item_handler_registry(self._tags["status"], hr)

                dpg.add_text(" | ", color=self._theme.color("border"))

                # Last update
                dpg.add_text("LAST:", color=self._theme.color("text_dim"))
                self._tags["last_eq"] = dpg.add_text(
                    "—", color=self._theme.color("text")
                )

                dpg.add_text(" | ", color=self._theme.color("border"))

                # UTC Clock
                dpg.add_text("UTC:", color=self._theme.color("text_dim"))
                self._tags["clock"] = dpg.add_text(
                    "00:00:00", color=self._theme.color("primary")
                )

                dpg.add_text(" | ", color=self._theme.color("border"))

                # Active theme
                dpg.add_text("THEME:", color=self._theme.color("text_dim"))

                if self._available:
                    default_idx = 0
                    if self._theme.name.lower() in [t.lower() for t in self._available]:
                        default_idx = [t.lower() for t in self._available].index(
                            self._theme.name.lower()
                        )

                    self._tags["theme_combo"] = dpg.add_combo(
                        items=self._available,
                        default_value=self._available[default_idx],
                        width=120,
                        callback=self._theme_changed,
                    )

                dpg.add_text(" | ", color=self._theme.color("border"))

                # FPS
                dpg.add_text("FPS:", color=self._theme.color("text_dim"))
                self._tags["fps"] = dpg.add_text(
                    "—", color=self._theme.color("text")
                )

    def _theme_changed(self, sender: int | str, value: str) -> None:
        """Handle theme combo box change."""
        if self._on_theme_change:
            self._on_theme_change(value)

    def update_clock(self) -> None:
        """Update the UTC clock display (call each frame or periodically)."""
        now = datetime.now(timezone.utc)
        if "clock" in self._tags:
            dpg.set_value(self._tags["clock"], now.strftime("%H:%M:%S"))

    def update_fps(self, fps: float) -> None:
        """Update the FPS counter."""
        if "fps" in self._tags:
            dpg.set_value(self._tags["fps"], f"{fps:.0f}")

    def set_last_earthquake_update(self, timestamp: str) -> None:
        """Update the last earthquake fetch timestamp."""
        if "last_eq" in self._tags:
            dpg.set_value(self._tags["last_eq"], timestamp)

    def set_status(self, state: str) -> None:
        """Set connection status indicator."""
        if "status" in self._tags:
            if state == "ONLINE":
                dpg.set_value(self._tags["status"], "(*) ONLINE")
                dpg.configure_item(self._tags["status"], color=self._theme.color("success"))
            elif state == "OFFLINE":
                dpg.set_value(self._tags["status"], "(*) OFFLINE")
                dpg.configure_item(self._tags["status"], color=self._theme.color("danger"))
            elif state == "CONNECTING":
                dpg.set_value(self._tags["status"], "(*) CONNECTING...")
                dpg.configure_item(self._tags["status"], color=self._theme.color("warning"))

    def update_theme(self, theme: ThemeData, soft: bool = False) -> None:
        """Apply a new theme to the status bar."""
        self._theme = theme

        # Update static colors
        if self._tags.get("theme_combo") and dpg.does_item_exist(self._tags["theme_combo"]):
             pass # Combo colors handled globally by theme

        if "status" in self._tags and dpg.does_item_exist(self._tags["status"]):
            current = dpg.get_value(self._tags["status"])
            if "ONLINE" in str(current):
                color = self._theme.color("success")
            elif "OFFLINE" in str(current):
                color = self._theme.color("danger")
            else:
                color = self._theme.color("warning")
            dpg.configure_item(self._tags["status"], color=color)
