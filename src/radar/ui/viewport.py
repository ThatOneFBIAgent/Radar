"""
Viewport setup — window creation, font loading, and layout management.

Creates the main DearPyGui viewport with the TUI-inspired layout.
"""

from __future__ import annotations

import logging
from pathlib import Path

import dearpygui.dearpygui as dpg

from radar.config import RadarConfig, FONTS_DIR, ASSETS_DIR

logger = logging.getLogger(__name__)

# Font setup
_font_registry_tag: int | str | None = None
_default_font_tag: int | str | None = None
_header_font_tag: int | str | None = None
_large_font_tag: int | str | None = None


def _setup_fonts(font_size: int, header_scale: float) -> None:
    """Load JetBrains Mono (or fallback) into DearPyGui font registry."""
    global _font_registry_tag, _default_font_tag, _header_font_tag, _large_font_tag

    font_path = FONTS_DIR / "JetBrainsMono-Regular.ttf"
    header_size = int(font_size * header_scale)
    large_size = int(font_size * (header_scale * 1.5))

    with dpg.font_registry() as reg:
        _font_registry_tag = reg

        if font_path.exists():
            # Create fonts and load character ranges
            _default_font_tag = dpg.add_font(str(font_path), font_size)
            _header_font_tag = dpg.add_font(str(font_path), header_size)
            _large_font_tag = dpg.add_font(str(font_path), large_size)
            
            # Add character ranges to both fonts for better Unicode support
            for tag in [_default_font_tag, _header_font_tag, _large_font_tag]:
                dpg.add_font_range_hint(dpg.mvFontRangeHint_Default, parent=tag)
                
                # Explicitly add Latin-1 Supplement (0080-00FF)
                # and useful block/shape characters for TUI
                dpg.add_font_range(0x00A0, 0x00FF, parent=tag)  # Latin-1 Supplement (includes ·)
                dpg.add_font_range(0x2580, 0x259F, parent=tag)  # Block Elements (includes █, ░)
                dpg.add_font_range(0x25A0, 0x25FF, parent=tag)  # Geometric Shapes (includes ■)

            logger.info("Loaded font: JetBrainsMono @ %dpx with extended Unicode support", font_size)
        else:
            # Use built-in ProggyClean as fallback
            _default_font_tag = None
            _header_font_tag = None
            _large_font_tag = None
            logger.warning(
                "JetBrainsMono not found at %s — using default font. "
                "Download from https://www.jetbrains.com/lp/mono/",
                font_path,
            )

    if _default_font_tag:
        dpg.bind_font(_default_font_tag)


def get_header_font() -> int | str | None:
    """Return the header font tag, or None for default."""
    return _header_font_tag


def get_large_font() -> int | str | None:
    """Return the large font tag, or None for default."""
    return _large_font_tag


# Viewport creation
def create_viewport(config: RadarConfig) -> None:
    """Initialize DearPyGui context and create the viewport."""
    dpg.create_context()

    width = config.ui.window_width or 1400
    height = config.ui.window_height or 900

    dpg.create_viewport(
        title="RADAR - Seismic & Weather Monitor",
        width=width,
        height=height,
        min_width=900,
        min_height=600,
        resizable=True,
    )

    _setup_fonts(config.ui.font_size, 1.3)
    
    # Icon setup — prefer .ico on Windows for proper title bar / taskbar display
    icon_path = ASSETS_DIR / "icon.ico"
    if not icon_path.exists():
        icon_path = ASSETS_DIR / "icon.png"
    
    if icon_path.exists():
        try:
            dpg.set_viewport_small_icon(str(icon_path))
            dpg.set_viewport_large_icon(str(icon_path))
            logger.info("Loaded window icon: %s", icon_path)
        except Exception as e:
            logger.warning("Failed to set window icon: %s", e)

    logger.info("Viewport created: %dx%d", width, height)


def setup_viewport() -> None:
    """Finalize viewport setup (call after windows are created)."""
    dpg.setup_dearpygui()
    dpg.show_viewport()


def maximize_viewport() -> None:
    """Maximize the viewport window."""
    dpg.maximize_viewport()


# Cleanup
def destroy_viewport() -> None:
    """Tear down DearPyGui."""
    try:
        dpg.destroy_context()
    except Exception:
        pass
