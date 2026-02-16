"""
Animation helpers for smooth UI transitions.

Provides lerp, pulse, and fade calculations that work
with DearPyGui's frame-based update loop.
"""

from __future__ import annotations

import math
import time


class AnimationTimer:
    """Tracks time-based animation progress."""

    def __init__(self) -> None:
        self._start = time.monotonic()

    def elapsed_ms(self) -> float:
        return (time.monotonic() - self._start) * 1000

    def reset(self) -> None:
        self._start = time.monotonic()


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b by factor t (0.0 → 1.0)."""
    t = max(0.0, min(1.0, t))
    return a + (b - a) * t


def lerp_color(
    c1: tuple[int, int, int, int],
    c2: tuple[int, int, int, int],
    t: float,
) -> tuple[int, int, int, int]:
    """Interpolate between two RGBA color tuples."""
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
        int(c1[3] + (c2[3] - c1[3]) * t),
    )


def ease_out_cubic(t: float) -> float:
    """Cubic ease-out for smooth deceleration."""
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def ease_in_out_sine(t: float) -> float:
    """Sine ease-in-out for gentle transitions."""
    t = max(0.0, min(1.0, t))
    return -(math.cos(math.pi * t) - 1) / 2


def pulse(elapsed_ms: float, period_ms: float, min_val: float = 0.3, max_val: float = 1.0) -> float:
    """Pulsing animation — returns a value oscillating between min_val and max_val.

    Uses a sine wave for smooth pulsation.
    """
    phase = (elapsed_ms % period_ms) / period_ms
    sine = (math.sin(phase * 2 * math.pi - math.pi / 2) + 1) / 2
    return min_val + (max_val - min_val) * sine


def fade_out(elapsed_ms: float, duration_ms: float) -> float:
    """Returns opacity (1.0 → 0.0) over the given duration."""
    if elapsed_ms >= duration_ms:
        return 0.0
    return 1.0 - ease_out_cubic(elapsed_ms / duration_ms)


class Highlighter:
    """Manages event highlight states with automatic decay."""

    def __init__(self, decay_ms: float = 3000.0, pulse_ms: float = 1200.0) -> None:
        self._decay_ms = decay_ms
        self._pulse_ms = pulse_ms
        self._highlights: dict[str, float] = {}  # id → start time

    def add(self, event_id: str) -> None:
        """Mark an event for highlighting."""
        self._highlights[event_id] = time.monotonic()

    def add_many(self, event_ids: list[str]) -> None:
        """Mark multiple events for highlighting."""
        now = time.monotonic()
        for eid in event_ids:
            self._highlights[eid] = now

    def get_intensity(self, event_id: str) -> float:
        """Get current highlight intensity (0.0 = none, 1.0 = full).

        Combines pulse with decay for a naturally fading highlight.
        """
        if event_id not in self._highlights:
            return 0.0

        elapsed = (time.monotonic() - self._highlights[event_id]) * 1000
        if elapsed > self._decay_ms:
            del self._highlights[event_id]
            return 0.0

        decay = fade_out(elapsed, self._decay_ms)
        pulsation = pulse(elapsed, self._pulse_ms, 0.5, 1.0)
        return decay * pulsation

    def cleanup(self) -> None:
        """Remove expired highlights."""
        now = time.monotonic()
        expired = [
            eid for eid, start in self._highlights.items()
            if (now - start) * 1000 > self._decay_ms
        ]
        for eid in expired:
            del self._highlights[eid]
