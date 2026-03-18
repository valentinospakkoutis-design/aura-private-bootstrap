from __future__ import annotations

import math
from datetime import datetime
from typing import Iterable, List

from meta_engine_v2.schemas import PerformancePoint


def decay_weight(age_days: float, decay_lambda: float) -> float:
    return math.exp(-max(age_days, 0.0) * max(decay_lambda, 0.0))


def weighted_average(values_and_weights: Iterable[tuple[float, float]], default: float = 0.0) -> float:
    total_weight = 0.0
    total_value = 0.0
    for value, weight in values_and_weights:
        safe_weight = max(weight, 0.0)
        total_weight += safe_weight
        total_value += value * safe_weight
    if total_weight <= 0:
        return default
    return total_value / total_weight


def minmax_normalize(value: float, low: float, high: float, default: float = 0.5) -> float:
    if math.isclose(high, low):
        return default
    return clamp((value - low) / (high - low), 0.0, 1.0)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def recent_window(points: List[PerformancePoint], max_points: int) -> List[PerformancePoint]:
    if max_points <= 0:
        return []
    return sorted(points, key=lambda point: point.timestamp)[-max_points:]


def age_days(reference: datetime, timestamp: datetime) -> float:
    return max((reference - timestamp).total_seconds() / 86400.0, 0.0)
