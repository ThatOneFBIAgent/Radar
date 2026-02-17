"""
Layout management — resizable splitters and dynamic sizing.

Provides ratio-based splitters that work with DearPyGui's item handlers
to allow user-resizable panels.
"""

from __future__ import annotations

import logging
from typing import Callable

import dearpygui.dearpygui as dpg

logger = logging.getLogger(__name__)


class LayoutManager:
    """Manages panel sizes and splitter positions."""

    def __init__(
        self,
        on_resize: Callable[[], None],
        initial_split_x: float = 0.6,
        initial_split_y: float = 0.6,
    ) -> None:
        self._split_x = initial_split_x  # Ratio for earthquake / weather width
        self._split_y = initial_split_y  # Ratio for top / map height
        self._on_resize = on_resize
        self._width = 800
        self._height = 600

        self._dragging_x = False
        self._dragging_y = False

        # Tags
        self.split_x_tag = "splitter_x"
        self.split_y_tag = "splitter_y"

    def setup_handlers(self) -> None:
        """Register resize handlers for the viewport."""
        with dpg.item_handler_registry(tag="viewport_resize_handler"):
            dpg.add_item_resize_handler(callback=self._handle_viewport_resize)

        dpg.bind_item_handler_registry("primary_window", "viewport_resize_handler")

        # Global input handler for drag release
        with dpg.handler_registry(tag="global_input_handler"):
            dpg.add_mouse_release_handler(callback=self._on_mouse_release)

    def draw_splitters(self, parent: int | str) -> None:
        """Draw the draggable splitter handles."""
        # Vertical splitter (horizontal line separating top/bottom)
        # We draw a thin rectangle that acts as the handle
        y_pos = int(self._height * self._split_y)
        
        # Invisble button for hit testing / dragging
        dpg.add_button(
            tag=self.split_y_tag,
            parent=parent,
            pos=(0, y_pos - 4),
            width=self._width,
            height=8,
            label="",
            show=True,
        )
        # Style it to be invisible but intractable, or use a theme color
        with dpg.theme() as theme:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (100, 100, 100, 100))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (150, 150, 150, 150))
        dpg.bind_item_theme(self.split_y_tag, theme)

        # Register drag handler for Y splitter
        with dpg.item_handler_registry(tag="split_y_handler"):
            dpg.add_item_active_handler(callback=self._on_drag_y)
        dpg.bind_item_handler_registry(self.split_y_tag, "split_y_handler")

        # Horizontal splitter (vertical line separating EQ/WX)
        x_pos = int(self._width * self._split_x)
        
        dpg.add_button(
            tag=self.split_x_tag,
            parent=parent,
            pos=(x_pos - 4, 0),
            width=8,
            height=y_pos, # Only goes down to the Y splitter
            label="",
            show=True,
        )
        with dpg.theme() as theme_x:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (100, 100, 100, 100))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (150, 150, 150, 150))
        dpg.bind_item_theme(self.split_x_tag, theme_x)

        # Register drag handler for X splitter
        with dpg.item_handler_registry(tag="split_x_handler"):
            dpg.add_item_active_handler(callback=self._on_drag_x)
        dpg.bind_item_handler_registry(self.split_x_tag, "split_x_handler")

    def _handle_viewport_resize(self, sender: int | str, app_data: Any) -> None:
        """Update internal dimensions on window resize."""
        # Reserve a small safety buffer to prevent scrollbars from triggering
        # if content touches the exact edge of the viewport.
        self._width = dpg.get_viewport_width()
        self._height = dpg.get_viewport_height() - 40  # 40px safety margin to ensure status bar is visible
        self._update_splitter_positions()
        self._on_resize()

    def _on_drag_x(self, sender: int | str, app_data: Any) -> None:
        """Handle horizontal splitter drag."""
        self._dragging_x = True
        mouse_x = dpg.get_mouse_pos(local=False)[0]
        # Clamp between 20% and 80%
        ratio = max(0.2, min(0.8, mouse_x / self._width))
        if abs(ratio - self._split_x) > 0.001:
            self._split_x = ratio
            self._update_splitter_positions()
            self._on_resize()

    def _on_drag_y(self, sender: int | str, app_data: Any) -> None:
        """Handle vertical splitter drag."""
        self._dragging_y = True
        mouse_y = dpg.get_mouse_pos(local=False)[1]
        # Clamp between 20% and 80%
        ratio = max(0.2, min(0.8, mouse_y / self._height))
        if abs(ratio - self._split_y) > 0.001:
            self._split_y = ratio
            self._update_splitter_positions()
            self._on_resize()

    def _on_mouse_release(self, sender: int | str, app_data: Any) -> None:
        self._dragging_x = False
        self._dragging_y = False

    def _update_splitter_positions(self) -> None:
        """Move the splitter widgets to their new coordinates."""
        if dpg.does_item_exist(self.split_y_tag):
            y_pos = int(self._height * self._split_y)
            dpg.configure_item(self.split_y_tag, width=self._width, pos=(0, y_pos - 4))
        
        if dpg.does_item_exist(self.split_x_tag):
            x_pos = int(self._width * self._split_x)
            y_pos = int(self._height * self._split_y)
            dpg.configure_item(self.split_x_tag, height=y_pos, pos=(x_pos - 4, 0))

    def get_total_size(self) -> tuple[int, int]:
        """Return the total viewport (width, height)."""
        return self._width, self._height

    # Geometry Getters

    def get_eq_size(self) -> tuple[int, int]:
        """Return (width, height) for earthquake panel."""
        w = int(self._width * self._split_x) - 4
        h = int(self._height * self._split_y) - 4
        return max(1, w), max(1, h)

    def get_wx_size(self) -> tuple[int, int]:
        """Return (width, height) for weather panel."""
        start_x = int(self._width * self._split_x) + 4
        w = self._width - start_x
        h = int(self._height * self._split_y) - 4
        return max(1, w), max(1, h)

    def get_map_size(self) -> tuple[int, int]:
        """Return (width, height) for map panel."""
        start_y = int(self._height * self._split_y) + 4
        h = self._height - start_y - 36  # -32 for status bar + 4px safety gap
        return self._width, max(1, h)

    def get_wx_pos(self) -> tuple[int, int]:
        """Return top-left (x, y) for weather panel."""
        return int(self._width * self._split_x) + 4, 0

    def get_map_pos(self) -> tuple[int, int]:
        """Return top-left (x, y) for map panel."""
        return 0, int(self._height * self._split_y) + 4
