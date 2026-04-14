"""Small numeric helpers for positioning heuristics."""

from __future__ import annotations

import math
from typing import Any


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize(value: float, min_v: float, max_v: float) -> float:
    if max_v <= min_v:
        return 0.5
    clamped = max(min_v, min(value, max_v))
    return (clamped - min_v) / (max_v - min_v)


def sigmoid(x: float) -> float:
    if x > 30:
        return 1.0
    if x < -30:
        return 0.0
    return float(1.0 / (1.0 + math.exp(-x)))


def percentile_rank(value: float, samples: list[float]) -> float:
    if not samples:
        return 0.5
    arr = sorted(samples)
    below = sum(1 for x in arr if x < value)
    return below / max(1, len(arr))
