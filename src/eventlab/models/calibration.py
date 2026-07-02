from __future__ import annotations

import math
from dataclasses import dataclass

from eventlab.utils import clamp


@dataclass(frozen=True)
class CalibrationBin:
    lower: float
    upper: float
    count: int
    mean_prediction: float
    empirical_rate: float

    def as_dict(self) -> dict[str, object]:
        return {
            "lower": self.lower,
            "upper": self.upper,
            "count": self.count,
            "mean_prediction": round(self.mean_prediction, 4),
            "empirical_rate": round(self.empirical_rate, 4),
        }


def brier_score(predictions: list[float], outcomes: list[int]) -> float:
    _validate_equal_length(predictions, outcomes)
    return sum((p - y) ** 2 for p, y in zip(predictions, outcomes)) / len(predictions)


def log_loss(predictions: list[float], outcomes: list[int]) -> float:
    _validate_equal_length(predictions, outcomes)
    losses = []
    for p, y in zip(predictions, outcomes):
        clipped = clamp(p, 1e-6, 1.0 - 1e-6)
        losses.append(-(y * math.log(clipped) + (1 - y) * math.log(1.0 - clipped)))
    return sum(losses) / len(losses)


def calibration_curve(predictions: list[float], outcomes: list[int], bins: int = 5) -> list[CalibrationBin]:
    _validate_equal_length(predictions, outcomes)
    results: list[CalibrationBin] = []
    width = 1.0 / bins
    for index in range(bins):
        lower = index * width
        upper = 1.0 if index == bins - 1 else (index + 1) * width
        pairs = []
        for p, y in zip(predictions, outcomes):
            in_bin = lower <= p <= upper if index == bins - 1 else lower <= p < upper
            if in_bin:
                pairs.append((p, y))
        if not pairs:
            results.append(CalibrationBin(lower, upper, 0, 0.0, 0.0))
            continue
        mean_prediction = sum(p for p, _ in pairs) / len(pairs)
        empirical_rate = sum(y for _, y in pairs) / len(pairs)
        results.append(CalibrationBin(lower, upper, len(pairs), mean_prediction, empirical_rate))
    return results


def _validate_equal_length(predictions: list[float], outcomes: list[int]) -> None:
    if not predictions or len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must be non-empty and equal length")
