"""Chiller runtime engine for COP map based Configuration Library equipment."""

from dataclasses import dataclass
from typing import Any

from equipment_curve_reader import EquipmentCurvePreview, preview_from_curve_dict


class ChillerEngineValidationError(ValueError):
    """Raised when a chiller curve or operating point cannot be evaluated."""


@dataclass
class ChillerEngine:
    """Evaluate chiller power from a CEFT/load-ratio COP map."""

    equipment_id: str = "CHILLER"
    curve_data: Any = None
    source_workbook: str | None = None
    source_sheet: str = "Solver_Curve"

    def calculate(
        self,
        required_cooling_capacity_kW,
        rated_chiller_capacity_kW,
        CEFT_C,
    ):
        """Return chiller runtime power and COP for a required cooling load."""
        required_capacity = _to_float(required_cooling_capacity_kW, "required_cooling_capacity_kW")
        rated_capacity = _to_float(rated_chiller_capacity_kW, "rated_chiller_capacity_kW")
        if rated_capacity <= 0:
            raise ChillerEngineValidationError("rated_chiller_capacity_kW must be greater than 0.")
        if required_capacity < 0:
            raise ChillerEngineValidationError("required_cooling_capacity_kW must be greater than or equal to 0.")

        load_ratio = required_capacity / rated_capacity
        cop = lookup_chiller_cop(self.curve_data, CEFT_C=CEFT_C, load_ratio=load_ratio, equipment_id=self.equipment_id)
        if cop <= 0:
            raise ChillerEngineValidationError(f"Invalid chiller COP: {cop}")
        return {
            "chiller_power_kW": required_capacity / cop,
            "chiller_COP": cop,
            "chiller_load_ratio": load_ratio,
            "chiller_capacity_kW": rated_capacity,
            "chiller_curve_source": "configuration_library_solver_curve",
        }


def calculate_chiller_power(
    curve_data,
    required_cooling_capacity_kW,
    rated_chiller_capacity_kW,
    CEFT_C,
    equipment_id="CHILLER",
):
    """Convenience wrapper for one-shot chiller runtime calculation."""
    return ChillerEngine(equipment_id=equipment_id, curve_data=curve_data).calculate(
        required_cooling_capacity_kW=required_cooling_capacity_kW,
        rated_chiller_capacity_kW=rated_chiller_capacity_kW,
        CEFT_C=CEFT_C,
    )


def lookup_chiller_cop(curve_data, CEFT_C, load_ratio, equipment_id="CHILLER"):
    """Return interpolated COP from a CEFT/load-ratio COP map."""
    rows = _cop_rows(curve_data, equipment_id)
    ceft = _to_float(CEFT_C, "CEFT_C")
    load = _to_float(load_ratio, "load_ratio")
    cefts = sorted({row["CEFT_C"] for row in rows})
    loads = sorted({row["load_ratio"] for row in rows})
    ceft = _clamp(ceft, cefts[0], cefts[-1])
    load = _clamp(load, loads[0], loads[-1])
    clo, chi = _bounds(cefts, ceft)
    llo, lhi = _bounds(loads, load)
    grid = {(row["CEFT_C"], row["load_ratio"]): row for row in rows}
    corners = {(c, l): grid.get((c, l)) for c in (clo, chi) for l in (llo, lhi)}
    missing = [point for point, row in corners.items() if row is None]
    if missing:
        raise ChillerEngineValidationError(f"Missing chiller COP interpolation neighbors for {equipment_id}: {missing}")
    lower_line = _linear(llo, lhi, corners[(clo, llo)]["COP_kW_per_kW"], corners[(clo, lhi)]["COP_kW_per_kW"], load)
    upper_line = _linear(llo, lhi, corners[(chi, llo)]["COP_kW_per_kW"], corners[(chi, lhi)]["COP_kW_per_kW"], load)
    return _linear(clo, chi, lower_line, upper_line, ceft)


def _cop_rows(curve_data, equipment_id):
    rows = _extract_rows(curve_data, equipment_id)
    parsed_rows = []
    seen = set()
    for index, row in enumerate(rows, start=1):
        parsed = {
            "CEFT_C": _to_float(row.get("CEFT_C"), f"{equipment_id} row {index} CEFT_C"),
            "load_ratio": _to_float(row.get("load_ratio"), f"{equipment_id} row {index} load_ratio"),
            "COP_kW_per_kW": _to_float(row.get("COP_kW_per_kW"), f"{equipment_id} row {index} COP_kW_per_kW"),
        }
        point = (parsed["CEFT_C"], parsed["load_ratio"])
        if point in seen:
            raise ChillerEngineValidationError(f"Duplicate chiller COP point for {equipment_id}: {point}")
        seen.add(point)
        parsed_rows.append(parsed)
    if not parsed_rows:
        raise ChillerEngineValidationError(f"Missing chiller COP map for {equipment_id}.")
    cefts = sorted({row["CEFT_C"] for row in parsed_rows})
    loads = sorted({row["load_ratio"] for row in parsed_rows})
    if len(parsed_rows) != len(cefts) * len(loads):
        raise ChillerEngineValidationError(f"Chiller COP map grid is incomplete for {equipment_id}.")
    return parsed_rows


def _extract_rows(curve_data, equipment_id):
    if isinstance(curve_data, EquipmentCurvePreview):
        if curve_data.errors:
            raise ChillerEngineValidationError("; ".join(curve_data.errors))
        return list(curve_data.solver_curve_rows or [])
    if isinstance(curve_data, list):
        return list(curve_data)
    if isinstance(curve_data, dict):
        rows = curve_data.get("points")
        if not isinstance(rows, list):
            rows = curve_data.get("data")
        if isinstance(rows, list):
            return list(rows)
        preview = preview_from_curve_dict(equipment_id, curve_data)
        if preview.errors:
            raise ChillerEngineValidationError("; ".join(preview.errors))
        return list(preview.solver_curve_rows or [])
    raise ChillerEngineValidationError(f"Missing chiller COP map for {equipment_id}.")


def _bounds(values, target):
    values = sorted(values)
    if len(values) == 1:
        return values[0], values[0]
    if target <= values[0]:
        return values[0], values[0]
    if target >= values[-1]:
        return values[-1], values[-1]
    for index in range(len(values) - 1):
        if values[index] <= target <= values[index + 1]:
            return values[index], values[index + 1]
    raise ChillerEngineValidationError(f"Could not find interpolation bounds for {target}.")


def _linear(x0, x1, y0, y1, x):
    if x0 == x1:
        return y0
    return y0 + (y1 - y0) * ((x - x0) / (x1 - x0))


def _clamp(value, lower, upper):
    return max(lower, min(upper, value))


def _to_float(value, label):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ChillerEngineValidationError(f"Invalid numeric value for {label}: {value!r}") from None
