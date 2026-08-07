"""Dry cooler runtime engine for ambient capacity/power curves."""

from dataclasses import dataclass
from typing import Any

from equipment_curve_reader import EquipmentCurvePreview, preview_from_curve_dict


class DryCoolerEngineValidationError(ValueError):
    """Raised when a dry cooler curve or operating point cannot be evaluated."""


@dataclass
class DryCoolerEngine:
    """Evaluate dry cooler fan power and capacity from ambient dry bulb data."""

    equipment_id: str = "DRY_COOLER"
    curve_data: Any = None
    capacity_curve_data: Any = None
    source_workbook: str | None = None
    source_sheet: str = "Solver_Curve"

    def calculate(self, required_heat_rejection_kW, ambient_dry_bulb_C):
        """Return dry cooler runtime power and capacity for one operating point."""
        required_heat_rejection = _to_float(required_heat_rejection_kW, "required_heat_rejection_kW")
        if required_heat_rejection < 0:
            raise DryCoolerEngineValidationError("required_heat_rejection_kW must be greater than or equal to 0.")
        capacity_point = lookup_dry_cooler_point(
            self.capacity_curve_data if self.capacity_curve_data is not None else self.curve_data,
            ambient_dry_bulb_C=ambient_dry_bulb_C,
            equipment_id=self.equipment_id,
        )
        power_point = lookup_dry_cooler_power_point(
            self.curve_data,
            ambient_dry_bulb_C=ambient_dry_bulb_C,
            equipment_id=self.equipment_id,
        )
        available_capacity = capacity_point["dry_cooler_capacity_kW"]
        if available_capacity <= 0:
            raise DryCoolerEngineValidationError(f"Invalid dry cooler capacity: {available_capacity}")
        return {
            "dry_cooler_power_kW": power_point["dry_cooler_power_kW"],
            "dry_cooler_capacity_kW": available_capacity,
            "dry_cooler_capacity_ratio": required_heat_rejection / available_capacity,
            "dry_cooler_curve_source": "configuration_library_solver_curve",
            **power_point,
        }


def lookup_dry_cooler_power_point(curve_data, ambient_dry_bulb_C, equipment_id="DRY_COOLER"):
    rows = _temperature_power_rows(curve_data, equipment_id)
    raw_temperature = _to_float(ambient_dry_bulb_C, "ambient_dry_bulb_C")
    temperatures = [row["outdoor_dry_bulb_C"] for row in rows]
    lookup_temperature = _clamp(raw_temperature, temperatures[0], temperatures[-1])
    lo, hi = _bounds(temperatures, lookup_temperature)
    row_lo = next(row for row in rows if row["outdoor_dry_bulb_C"] == lo)
    row_hi = next(row for row in rows if row["outdoor_dry_bulb_C"] == hi)
    return {
        "dry_cooler_power_kW": _linear(lo, hi, row_lo["power_kW"], row_hi["power_kW"], lookup_temperature),
        "dry_cooler_outdoor_temperature_raw_C": raw_temperature,
        "dry_cooler_lookup_temperature_C": lookup_temperature,
        "dry_cooler_curve_min_temperature_C": temperatures[0],
        "dry_cooler_curve_max_temperature_C": temperatures[-1],
        "dry_cooler_temperature_clamped_low": raw_temperature < temperatures[0],
        "dry_cooler_temperature_clamped_high": raw_temperature > temperatures[-1],
    }


def _temperature_power_rows(curve_data, equipment_id):
    rows = _extract_rows(curve_data, equipment_id)
    parsed = []
    for index, row in enumerate(rows, start=1):
        try:
            temperature = float(row.get("outdoor_dry_bulb_C"))
            power = float(row.get("power_kW"))
        except (TypeError, ValueError):
            continue
        parsed.append({"outdoor_dry_bulb_C": temperature, "power_kW": power})
    parsed.sort(key=lambda row: row["outdoor_dry_bulb_C"])
    if not parsed:
        raise DryCoolerEngineValidationError(f"Missing dry cooler temperature power curve for {equipment_id}.")
    if any(right["outdoor_dry_bulb_C"] <= left["outdoor_dry_bulb_C"] for left, right in zip(parsed, parsed[1:])):
        raise DryCoolerEngineValidationError(f"{equipment_id} outdoor_dry_bulb_C must be strictly increasing.")
    return parsed


def calculate_dry_cooler_power(
    curve_data,
    required_heat_rejection_kW,
    ambient_dry_bulb_C,
    equipment_id="DRY_COOLER",
    capacity_curve_data=None,
):
    """Convenience wrapper for one-shot dry cooler runtime calculation."""
    return DryCoolerEngine(
        equipment_id=equipment_id,
        curve_data=curve_data,
        capacity_curve_data=capacity_curve_data,
    ).calculate(
        required_heat_rejection_kW=required_heat_rejection_kW,
        ambient_dry_bulb_C=ambient_dry_bulb_C,
    )


def lookup_dry_cooler_point(curve_data, ambient_dry_bulb_C, equipment_id="DRY_COOLER"):
    """Return interpolated dry cooler capacity and fan power at ambient dry bulb."""
    rows = _dry_cooler_rows(curve_data, equipment_id)
    ambient = _to_float(ambient_dry_bulb_C, "ambient_dry_bulb_C")
    ambients = [row["Outdoor_Dry_Bulb_C"] for row in rows]
    ambient = _clamp(ambient, ambients[0], ambients[-1])
    lo, hi = _bounds(ambients, ambient)
    row_lo = _row_by_ambient(rows, lo)
    row_hi = _row_by_ambient(rows, hi)
    if row_lo is None or row_hi is None:
        raise DryCoolerEngineValidationError(f"Missing dry cooler interpolation neighbors for {equipment_id}.")
    capacity = _linear(
        lo,
        hi,
        row_lo["Heat_Rejection_Capacity_kW"],
        row_hi["Heat_Rejection_Capacity_kW"],
        ambient,
    )
    fan_power = _linear(
        lo,
        hi,
        row_lo["Estimated_Fan_Power_kW"],
        row_hi["Estimated_Fan_Power_kW"],
        ambient,
    )
    return {
        "dry_cooler_power_kW": fan_power,
        "dry_cooler_capacity_kW": capacity,
        "ambient_dry_bulb_C": ambient,
    }


def _dry_cooler_rows(curve_data, equipment_id):
    rows = _extract_rows(curve_data, equipment_id)
    by_ambient = {}
    for index, row in enumerate(rows, start=1):
        parsed = {
            "Outdoor_Dry_Bulb_C": _to_float(
                row.get("Outdoor_Dry_Bulb_C") if row.get("Outdoor_Dry_Bulb_C") is not None else row.get("Ambient_C"),
                f"{equipment_id} row {index} Outdoor_Dry_Bulb_C",
            ),
            "Heat_Rejection_Capacity_kW": _to_float(
                row.get("Heat_Rejection_Capacity_kW") if row.get("Heat_Rejection_Capacity_kW") is not None else row.get("Heat_Rejection_kW"),
                f"{equipment_id} row {index} Heat_Rejection_Capacity_kW",
            ),
            "Estimated_Fan_Power_kW": _to_float(
                row.get("Estimated_Fan_Power_kW") if row.get("Estimated_Fan_Power_kW") is not None else row.get("Estimated_Total_Fan_Power_kW"),
                f"{equipment_id} row {index} Estimated_Fan_Power_kW",
            ),
            "Solver_Use": str(row.get("Solver_Use") or ""),
        }
        ambient = parsed["Outdoor_Dry_Bulb_C"]
        existing = by_ambient.get(ambient)
        if existing is None or _is_primary(parsed) and not _is_primary(existing):
            by_ambient[ambient] = parsed
    parsed_rows = list(by_ambient.values())
    if not parsed_rows:
        raise DryCoolerEngineValidationError(f"Missing dry cooler ambient capacity curve for {equipment_id}.")
    return sorted(parsed_rows, key=lambda row: row["Outdoor_Dry_Bulb_C"])


def _is_primary(row):
    return str(row.get("Solver_Use") or "").strip().lower() == "primary"


def _extract_rows(curve_data, equipment_id):
    if isinstance(curve_data, EquipmentCurvePreview):
        if curve_data.errors:
            raise DryCoolerEngineValidationError("; ".join(curve_data.errors))
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
            raise DryCoolerEngineValidationError("; ".join(preview.errors))
        return list(preview.solver_curve_rows or [])
    raise DryCoolerEngineValidationError(f"Missing dry cooler ambient capacity curve for {equipment_id}.")


def _row_by_ambient(rows, ambient):
    return next((row for row in rows if row["Outdoor_Dry_Bulb_C"] == ambient), None)


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
    raise DryCoolerEngineValidationError(f"Could not find interpolation bounds for {target}.")


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
        raise DryCoolerEngineValidationError(f"Invalid numeric value for {label}: {value!r}") from None
