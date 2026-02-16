"""Tests for the theme loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from radar.themes.loader import (
    ThemeData,
    get_available_themes,
    hex_to_rgba,
    load_theme,
)


class TestHexToRgba:
    def test_6_digit(self) -> None:
        assert hex_to_rgba("#FF0000") == (255, 0, 0, 255)

    def test_8_digit(self) -> None:
        assert hex_to_rgba("#FF000080") == (255, 0, 0, 128)

    def test_3_digit(self) -> None:
        assert hex_to_rgba("#F00") == (255, 0, 0, 255)

    def test_4_digit(self) -> None:
        assert hex_to_rgba("#F008") == (255, 0, 0, 136)

    def test_no_hash(self) -> None:
        assert hex_to_rgba("00FF00") == (0, 255, 0, 255)

    def test_invalid_length(self) -> None:
        with pytest.raises(ValueError):
            hex_to_rgba("#12345")

    def test_white(self) -> None:
        assert hex_to_rgba("#FFFFFF") == (255, 255, 255, 255)

    def test_black(self) -> None:
        assert hex_to_rgba("#000000") == (0, 0, 0, 255)


class TestLoadTheme:
    def test_load_valid_theme(self, tmp_themes_dir: Path) -> None:
        theme = load_theme("test", tmp_themes_dir)
        assert theme.name == "Test"
        assert len(theme.colors) >= 18

    def test_theme_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_theme("nonexistent", tmp_path)

    def test_color_values_are_tuples(self, tmp_themes_dir: Path) -> None:
        theme = load_theme("test", tmp_themes_dir)
        for key, value in theme.colors.items():
            assert isinstance(value, tuple), f"Color '{key}' is not a tuple"
            assert len(value) == 4, f"Color '{key}' doesn't have 4 components"

    def test_animation_defaults(self, tmp_themes_dir: Path) -> None:
        theme = load_theme("test", tmp_themes_dir)
        assert theme.transition_ms == 200
        assert theme.fade_ms == 150

    def test_missing_colors_warns(self, tmp_path: Path) -> None:
        themes_dir = tmp_path / "themes"
        themes_dir.mkdir()
        minimal = {"name": "Minimal", "colors": {"background": "#000000"}}
        (themes_dir / "minimal.json").write_text(json.dumps(minimal))

        theme = load_theme("minimal", themes_dir)
        assert theme.name == "Minimal"
        assert "background" in theme.colors

    def test_invalid_color_handled(self, tmp_path: Path) -> None:
        themes_dir = tmp_path / "themes"
        themes_dir.mkdir()
        bad_theme = {
            "name": "Bad",
            "colors": {
                "background": "#000000",
                "invalid_color": "not-a-color",
            },
        }
        (themes_dir / "bad.json").write_text(json.dumps(bad_theme))

        # Should load without raising
        theme = load_theme("bad", themes_dir)
        assert "background" in theme.colors
        assert "invalid_color" not in theme.colors


class TestThemeData:
    def test_color_with_fallback(self) -> None:
        theme = ThemeData()
        color = theme.color("nonexistent_key")
        assert color == (255, 255, 255, 255)  # fallback to white

    def test_color_exists(self) -> None:
        theme = ThemeData(colors={"test": (100, 200, 50, 255)})
        assert theme.color("test") == (100, 200, 50, 255)


class TestGetAvailableThemes:
    def test_returns_theme_names(self, tmp_themes_dir: Path) -> None:
        themes = get_available_themes(tmp_themes_dir)
        assert "test" in themes

    def test_empty_dir(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty_themes"
        empty.mkdir()
        themes = get_available_themes(empty)
        assert themes == []

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        themes = get_available_themes(tmp_path / "nope")
        assert themes == []
