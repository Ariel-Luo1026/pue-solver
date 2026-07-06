"""Common performance curve interfaces for future calculators."""

from dataclasses import dataclass

from calculators.common.interpolation import interpolate_1d, interpolate_2d


@dataclass
class CurveResult:
    value: float | None
    source: str | None = None
    warning: str | None = None


@dataclass
class PerformanceCurve:
    curve_id: str
    points: list
    curve_type: str = "1d"
    metadata: dict | None = None


class CurveInterpolator:
    """Small callable interface around PerformanceCurve."""

    def __init__(self, curve):
        self.curve = curve

    def evaluate(self, *independent_variables):
        if self.curve.curve_type == "2d":
            value = interpolate_2d(self.curve.points, *independent_variables[:2])
        else:
            value = interpolate_1d(self.curve.points, independent_variables[0])
        return CurveResult(value=value, source=self.curve.curve_id)
