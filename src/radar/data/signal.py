"""
Signal processing utilities — Python interface to C extension.

Provides optimized smoothing and vector math via the _radar_signal C module.
"""

from __future__ import annotations

import logging
from typing import Sequence

try:
    from _radar_signal import ffi, lib
    _HAS_SIGNAL = True
except ImportError:
    _HAS_SIGNAL = False

logger = logging.getLogger(__name__)

if _HAS_SIGNAL:
    logger.info("C signal accelerator (_radar_signal) loaded and active")
else:
    logger.debug("C signal accelerator not available — using pure Python fallbacks")


def ema_smooth(data: Sequence[float], alpha: float) -> list[float]:
    """Exponential Moving Average (EMA) smoothing.
    
    Smooths a sequence of numbers using:
    out[i] = alpha * data[i] + (1 - alpha) * out[i-1]
    
    Args:
        data: Input sequence of floats.
        alpha: Smoothing factor (0.0 = max smooth, 1.0 = no smoothing).
    """
    if not data:
        return []
        
    if not _HAS_SIGNAL:
        # Pure Python fallback
        out = [float(data[0])]
        for val in data[1:]:
            out.append(alpha * val + (1.0 - alpha) * out[-1])
        return out

    # C implementation via CFFI
    count = len(data)
    # Convert input to double array
    c_in = ffi.new("double[]", data)
    c_out = ffi.new("double[]", count)
    
    lib.ema_smooth(c_in, count, alpha, c_out)
    
    # Extract results
    return [float(c_out[i]) for i in range(count)]


def wma_smooth(data: Sequence[float], window: int) -> list[float]:
    """Weighted Moving Average (WMA) smoothing."""
    if not data:
        return []
        
    if not _HAS_SIGNAL:
        # Pure Python fallback (simplified)
        out = []
        for i in range(len(data)):
            lookback = max(0, i - window + 1)
            subset = data[lookback : i + 1]
            weights = range(1, len(subset) + 1)
            weighted_sum = sum(v * w for v, w in zip(subset, weights))
            out.append(weighted_sum / sum(weights))
        return out

    count = len(data)
    c_in = ffi.new("double[]", data)
    c_out = ffi.new("double[]", count)
    
    lib.wma_smooth(c_in, count, window, c_out)
    return [float(c_out[i]) for i in range(count)]


def compute_magnitude(x: Sequence[float], y: Sequence[float], z: Sequence[float]) -> list[float]:
    """Compute vector magnitude sqrt(x^2 + y^2 + z^2) for three components."""
    count = min(len(x), len(y), len(z))
    if count == 0:
        return []

    if not _HAS_SIGNAL:
        import math
        return [math.sqrt(x[i]**2 + y[i]**2 + z[i]**2) for i in range(count)]

    c_x = ffi.new("double[]", x[:count])
    c_y = ffi.new("double[]", y[:count])
    c_z = ffi.new("double[]", z[:count])
    c_out = ffi.new("double[]", count)
    
    lib.compute_magnitude(c_x, c_y, c_z, count, c_out)
    return [float(c_out[i]) for i in range(count)]
