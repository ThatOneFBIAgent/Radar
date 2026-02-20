"""
Theme loader — validates and applies JSON theme files to DearPyGui.

Converts the human-friendly JSON schema into DearPyGui theme
component calls. Supports hex colors (3, 4, 6, and 8 digit).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import dearpygui.dearpygui as dpg

from radar.config import THEMES_DIR

logger = logging.getLogger(__name__)

# ── Required color keys ────────────────────────────────────────
REQUIRED_COLORS = {
    "background", "surface", "primary", "accent",
    "text", "text_dim", "text_bright",
    "success", "warning", "danger", "border",
    "header", "row_even", "row_odd",
    "magnitude_low", "magnitude_mid", "magnitude_high", "magnitude_severe",
}


# ── Hex → RGBA conversion ─────────────────────────────────────
def hex_to_rgba(hex_color: str) -> tuple[int, int, int, int]:
    """Convert a hex color string to an RGBA tuple (0-255).

    Supports formats: #RGB, #RGBA, #RRGGBB, #RRGGBBAA
    """
    h = hex_color.lstrip("#")
    length = len(h)

    if length == 3:
        r, g, b = (int(c * 2, 16) for c in h)
        return (r, g, b, 255)
    elif length == 4:
        r, g, b, a = (int(c * 2, 16) for c in h)
        return (r, g, b, a)
    elif length == 6:
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        return (r, g, b, 255)
    elif length == 8:
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        a = int(h[6:8], 16)
        return (r, g, b, a)
    else:
        raise ValueError(f"Invalid hex color: {hex_color}")


# ── Theme data ─────────────────────────────────────────────────
@dataclass
class ThemeData:
    """Parsed and validated theme data ready for application."""

    name: str = "Default"
    description: str = ""
    colors: dict[str, tuple[int, int, int, int]] = field(default_factory=dict)
    border_style: str = "thin"
    border_radius: int = 4
    border_thickness: int = 1
    transition_ms: int = 200
    fade_ms: int = 150
    pulse_ms: int = 1200
    highlight_decay_ms: int = 3000
    font_size: int = 15
    line_spacing: float = 1.4
    header_scale: float = 1.3
    map_land_char: str = "+"
    map_water_char: str = "·"
    map_radar_sweep: bool = False
    _source_path: Path | None = None

    def color(self, key: str) -> tuple[int, int, int, int]:
        """Get a color by key, with fallback to white."""
        return self.colors.get(key, (255, 255, 255, 255))


# ── Loading ────────────────────────────────────────────────────
def load_theme(name: str, themes_dir: Path | None = None) -> ThemeData:
    """Load a theme JSON file by name and return validated ThemeData."""
    directory = themes_dir or THEMES_DIR
    path = directory / f"{name}.json"

    if not path.exists():
        logger.error("Theme file not found: %s", path)
        raise FileNotFoundError(f"Theme file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    return _parse_theme(raw, path)


def _parse_theme(raw: dict, source: Path) -> ThemeData:
    """Parse raw JSON dict into ThemeData."""
    theme = ThemeData(
        name=raw.get("name", source.stem),
        description=raw.get("description", ""),
        _source_path=source,
    )

    # ── Colors ──
    raw_colors = raw.get("colors", {})
    missing = REQUIRED_COLORS - set(raw_colors.keys())
    if missing:
        logger.warning("Theme '%s' missing colors: %s", theme.name, missing)

    for key, hex_val in raw_colors.items():
        try:
            theme.colors[key] = hex_to_rgba(hex_val)
        except ValueError as e:
            logger.warning("Theme '%s' bad color '%s': %s", theme.name, key, e)

    # ── Borders ──
    borders = raw.get("borders", {})
    theme.border_style = borders.get("style", "thin")
    theme.border_radius = borders.get("radius", 4)
    theme.border_thickness = borders.get("thickness", 1)

    # ── Animation ──
    anim = raw.get("animation", {})
    theme.transition_ms = anim.get("transition_ms", 200)
    theme.fade_ms = anim.get("fade_ms", 150)
    theme.pulse_ms = anim.get("pulse_ms", 1200)
    theme.highlight_decay_ms = anim.get("highlight_decay_ms", 3000)

    # ── Typography ──
    typo = raw.get("typography", {})
    theme.font_size = typo.get("font_size", 15)
    theme.line_spacing = typo.get("line_spacing", 1.4)
    theme.header_scale = typo.get("header_scale", 1.3)

    # ── Custom Configs ──
    theme.map_land_char = raw.get("map_land_char", "+")
    theme.map_water_char = raw.get("map_water_char", "·")
    theme.map_radar_sweep = raw.get("map_radar_sweep", False)

    logger.info("Loaded theme: %s (%d colors)", theme.name, len(theme.colors))
    return theme


def get_available_themes(themes_dir: Path | None = None) -> list[str]:
    """Return list of available theme names (without .json extension)."""
    directory = themes_dir or THEMES_DIR
    if not directory.exists():
        return []
    return sorted(p.stem for p in directory.glob("*.json"))


# ── DearPyGui application ─────────────────────────────────────
_active_theme_tag: int | str | None = None


def apply_theme(theme: ThemeData) -> int | str:
    """Create and bind a DearPyGui global theme from ThemeData.

    Returns the theme tag for later reference.
    """
    global _active_theme_tag

    # Delete previous theme if exists
    if _active_theme_tag is not None:
        try:
            dpg.delete_item(_active_theme_tag)
        except Exception:
            pass

    with dpg.theme() as theme_tag:
        with dpg.theme_component(dpg.mvAll):
            # ── Window / Frame backgrounds ──
            dpg.add_theme_color(
                dpg.mvThemeCol_WindowBg, theme.color("background"), category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_ChildBg, theme.color("surface"), category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_PopupBg, theme.color("surface"), category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_MenuBarBg, theme.color("header"), category=dpg.mvThemeCat_Core
            )

            # ── Text ──
            dpg.add_theme_color(
                dpg.mvThemeCol_Text, theme.color("text"), category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_TextDisabled, theme.color("text_dim"), category=dpg.mvThemeCat_Core
            )

            # ── Borders ──
            dpg.add_theme_color(
                dpg.mvThemeCol_Border, theme.color("border"), category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_BorderShadow, (0, 0, 0, 0), category=dpg.mvThemeCat_Core
            )

            # ── Frames (inputs, combo boxes, etc.) ──
            dpg.add_theme_color(
                dpg.mvThemeCol_FrameBg, theme.color("surface"), category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_FrameBgHovered, theme.color("surface_alt") if "surface_alt" in theme.colors else theme.color("surface"),
                category=dpg.mvThemeCat_Core,
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_FrameBgActive, theme.color("primary"), category=dpg.mvThemeCat_Core
            )

            # ── Title bar ──
            dpg.add_theme_color(
                dpg.mvThemeCol_TitleBg, theme.color("header"), category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_TitleBgActive, theme.color("surface"), category=dpg.mvThemeCat_Core
            )

            # ── Tabs ──
            dpg.add_theme_color(
                dpg.mvThemeCol_Tab, theme.color("surface"), category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_TabHovered, theme.color("primary"), category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_TabActive, theme.color("primary"), category=dpg.mvThemeCat_Core
            )

            # ── Buttons ──
            dpg.add_theme_color(
                dpg.mvThemeCol_Button, theme.color("surface"), category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_ButtonHovered, theme.color("primary"), category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_ButtonActive, theme.color("accent"), category=dpg.mvThemeCat_Core
            )

            # ── Headers (collapsing headers, table headers) ──
            dpg.add_theme_color(
                dpg.mvThemeCol_Header, theme.color("header"), category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_HeaderHovered, theme.color("primary"), category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_HeaderActive, theme.color("accent"), category=dpg.mvThemeCat_Core
            )

            # ── Scrollbar ──
            dpg.add_theme_color(
                dpg.mvThemeCol_ScrollbarBg, theme.color("background"), category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_ScrollbarGrab,
                theme.color("scrollbar") if "scrollbar" in theme.colors else theme.color("border"),
                category=dpg.mvThemeCat_Core,
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_ScrollbarGrabHovered, theme.color("primary"),
                category=dpg.mvThemeCat_Core,
            )

            # ── Separator ──
            dpg.add_theme_color(
                dpg.mvThemeCol_Separator, theme.color("border"), category=dpg.mvThemeCat_Core
            )

            # ── Check mark / slider ──
            dpg.add_theme_color(
                dpg.mvThemeCol_CheckMark, theme.color("primary"), category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_SliderGrab, theme.color("primary"), category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_SliderGrabActive, theme.color("accent"),
                category=dpg.mvThemeCat_Core,
            )

            # ── Table ──
            dpg.add_theme_color(
                dpg.mvThemeCol_TableHeaderBg, theme.color("header"), category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_TableRowBg, theme.color("row_even"), category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_TableRowBgAlt, theme.color("row_odd"), category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_TableBorderStrong, theme.color("border"),
                category=dpg.mvThemeCat_Core,
            )
            dpg.add_theme_color(
                dpg.mvThemeCol_TableBorderLight, theme.color("border"),
                category=dpg.mvThemeCat_Core,
            )

            # ── Style ──
            dpg.add_theme_style(
                dpg.mvStyleVar_FrameRounding, theme.border_radius, category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_style(
                dpg.mvStyleVar_WindowRounding, theme.border_radius, category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_style(
                dpg.mvStyleVar_ChildRounding, theme.border_radius, category=dpg.mvThemeCat_Core
            )
            dpg.add_theme_style(
                dpg.mvStyleVar_FrameBorderSize, theme.border_thickness,
                category=dpg.mvThemeCat_Core,
            )
            dpg.add_theme_style(
                dpg.mvStyleVar_ItemSpacing, 8, int(8 * theme.line_spacing),
                category=dpg.mvThemeCat_Core,
            )
            dpg.add_theme_style(
                dpg.mvStyleVar_ScrollbarSize, 10, category=dpg.mvThemeCat_Core
            )

    dpg.bind_theme(theme_tag)
    _active_theme_tag = theme_tag
    logger.info("Applied theme: %s", theme.name)
    return theme_tag


def transition_theme(old_theme: ThemeData, new_theme: ThemeData, progress: float) -> ThemeData:
    """Create a temporary ThemeData object representing the interpolated colors."""
    from radar.ui.animations import lerp_color, lerp

    # Make progress safe
    t = max(0.0, min(1.0, progress))

    # Fast path: if t is 0 or 1
    if t <= 0.0:
        return old_theme
    if t >= 1.0:
        return new_theme

    interp_theme = ThemeData(
        name=f"Transition",
        border_style=new_theme.border_style,
        border_radius=int(lerp(old_theme.border_radius, new_theme.border_radius, t)),
        border_thickness=int(lerp(old_theme.border_thickness, new_theme.border_thickness, t)),
        font_size=int(lerp(old_theme.font_size, new_theme.font_size, t)),
        line_spacing=lerp(old_theme.line_spacing, new_theme.line_spacing, t),
        header_scale=lerp(old_theme.header_scale, new_theme.header_scale, t),
        map_land_char=new_theme.map_land_char,
        map_water_char=new_theme.map_water_char,
        map_radar_sweep=new_theme.map_radar_sweep,
    )

    # Collect all common keys
    all_keys = set(old_theme.colors.keys()) | set(new_theme.colors.keys())

    for key in all_keys:
        old_color = old_theme.color(key)
        new_color = new_theme.color(key)
        interp_theme.colors[key] = lerp_color(old_color, new_color, t)

    return interp_theme

