"""Generic equipment Solver_Curve lookup utilities."""

from dataclasses import dataclass, field
from typing import Any

from equipment_curve_reader import (
    ELECTRICAL_EFFICIENCY,
    ELECTRICAL_LOSS_FRACTION,
    ELECTRICAL_LOSS_POWER,
    ONE_DIMENSIONAL_POWER,
    TWO_DIMENSIONAL_POWER,
)


@dataclass(frozen=True)
class EquipmentOperatingPoint:
    load_ratio: float
    ambient_C: float | None = None
    base_power_kW: float | None = None


@dataclass
class EquipmentLookupResult:
    equipment_id: str
    curve_type: str
    load_ratio: float | None = None
    ambient_C: float | None = None
    power_kW: float | None = None
    power_input_kW: float | None = None
    capacity_kW: float | None = None
    efficiency: float | None = None
    loss_fraction: float | None = None
    loss_kW: float | None = None
    source_workbook: str | None = None
    source_sheet: str | None = None
    lookup_success: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def lookup_equipment_curve(preview, operating_point):
    """Lookup a generic equipment curve and return a structured result."""
    if preview.errors:
        return _error_result(preview, preview.errors)
    try:
        if preview.curve_type == ONE_DIMENSIONAL_POWER:
            load, value = _lookup_1d(preview, operating_point.load_ratio, "power_kW")
            return _success_result(preview, operating_point, load_ratio=load, power_kW=value)
        if preview.curve_type == TWO_DIMENSIONAL_POWER:
            return _lookup_2d_power(preview, operating_point)
        if preview.curve_type == ELECTRICAL_EFFICIENCY:
            load, efficiency = _lookup_1d(preview, operating_point.load_ratio, "efficiency")
            if efficiency <= 0:
                raise ValueError(f"Invalid {preview.equipment_id} efficiency: {efficiency}")
            if operating_point.base_power_kW is None:
                raise ValueError(f"{preview.equipment_id} electrical efficiency lookup requires base_power_kW.")
            base_power = float(operating_point.base_power_kW)
            loss = max(0.0, base_power / efficiency - base_power)
            return _success_result(preview, operating_point, load_ratio=load, efficiency=efficiency, loss_kW=loss)
        if preview.curve_type == ELECTRICAL_LOSS_FRACTION:
            load, fraction = _lookup_1d(preview, operating_point.load_ratio, "loss_fraction")
            if operating_point.base_power_kW is None:
                raise ValueError(f"{preview.equipment_id} electrical loss_fraction lookup requires base_power_kW.")
            loss = max(0.0, float(operating_point.base_power_kW) * fraction)
            return _success_result(preview, operating_point, load_ratio=load, loss_fraction=fraction, loss_kW=loss)
        if preview.curve_type == ELECTRICAL_LOSS_POWER:
            load, loss = _lookup_1d(preview, operating_point.load_ratio, "loss_kW")
            return _success_result(preview, operating_point, load_ratio=load, loss_kW=loss)
        return _error_result(preview, [f"Unsupported curve type: {preview.curve_type}"])
    except Exception as exc:
        return _error_result(preview, [str(exc)])


def _lookup_1d(preview, load_ratio, value_field):
    rows = _rows_1d(preview, value_field)
    loads = [row["load_ratio"] for row in rows]
    load = _clamp(_to_float(load_ratio, "load_ratio"), loads[0], loads[-1])
    lo, hi = _bounds(loads, load)
    row_lo = _row_by_key(rows, "load_ratio", lo)
    row_hi = _row_by_key(rows, "load_ratio", hi)
    if row_lo is None or row_hi is None:
        raise ValueError(f"Missing interpolation neighbors for {preview.equipment_id}.")
    return load, _linear(lo, hi, row_lo[value_field], row_hi[value_field], load)


def _lookup_2d_power(preview, operating_point):
    rows = _rows_2d(preview)
    ambients = sorted({row["ambient_C"] for row in rows})
    loads = sorted({row["load_ratio"] for row in rows})
    ambient = _clamp(_to_float(operating_point.ambient_C, "ambient_C"), ambients[0], ambients[-1])
    load = _clamp(_to_float(operating_point.load_ratio, "load_ratio"), loads[0], loads[-1])
    alo, ahi = _bounds(ambients, ambient)
    llo, lhi = _bounds(loads, load)
    grid = {(row["ambient_C"], row["load_ratio"]): row for row in rows}
    corners = {(a, l): grid.get((a, l)) for a in (alo, ahi) for l in (llo, lhi)}
    missing = [point for point, row in corners.items() if row is None]
    if missing:
        raise ValueError(f"Missing interpolation neighbors for {preview.equipment_id}: {missing}")
    values = {}
    for field_name in ("power_input_kW", "capacity_kW", "unit_efficiency_kW_per_kW", "cop"):
        if any(corner.get(field_name) is not None for corner in corners.values()):
            lower_line = _linear(llo, lhi, corners[(alo, llo)].get(field_name), corners[(alo, lhi)].get(field_name), load)
            upper_line = _linear(llo, lhi, corners[(ahi, llo)].get(field_name), corners[(ahi, lhi)].get(field_name), load)
            values[field_name] = _linear(alo, ahi, lower_line, upper_line, ambient)
    return _success_result(
        preview,
        operating_point,
        load_ratio=load,
        ambient_C=ambient,
        power_input_kW=values.get("power_input_kW"),
        power_kW=values.get("power_input_kW"),
        capacity_kW=values.get("capacity_kW"),
        efficiency=values.get("unit_efficiency_kW_per_kW") or values.get("cop"),
    )


def _rows_1d(preview, value_field):
    rows = []
    seen = set()
    for index, row in enumerate(preview.solver_curve_rows, start=1):
        parsed = {
            "load_ratio": _to_float(row.get("load_ratio"), f"{preview.equipment_id} row {index} load_ratio"),
            value_field: _to_float(row.get(value_field), f"{preview.equipment_id} row {index} {value_field}"),
        }
        if parsed["load_ratio"] in seen:
            raise ValueError(f"Duplicate {preview.equipment_id} load_ratio point: {parsed['load_ratio']}")
        seen.add(parsed["load_ratio"])
        rows.append(parsed)
    if not rows:
        raise ValueError(f"{preview.equipment_id} curve contains no rows.")
    return sorted(rows, key=lambda item: item["load_ratio"])


def _rows_2d(preview):
    rows = []
    seen = set()
    for index, row in enumerate(preview.solver_curve_rows, start=1):
        parsed = {
            "ambient_C": _to_float(row.get("ambient_C"), f"{preview.equipment_id} row {index} ambient_C"),
            "load_ratio": _to_float(row.get("load_ratio"), f"{preview.equipment_id} row {index} load_ratio"),
            "power_input_kW": _to_float(row.get("power_input_kW"), f"{preview.equipment_id} row {index} power_input_kW"),
            "capacity_kW": _to_optional_float(row.get("capacity_kW"), f"{preview.equipment_id} row {index} capacity_kW"),
            "unit_efficiency_kW_per_kW": _to_optional_float(row.get("unit_efficiency_kW_per_kW"), f"{preview.equipment_id} row {index} unit_efficiency_kW_per_kW"),
            "cop": _to_optional_float(row.get("cop"), f"{preview.equipment_id} row {index} cop"),
        }
        point = (parsed["ambient_C"], parsed["load_ratio"])
        if point in seen:
            raise ValueError(f"Duplicate {preview.equipment_id} ambient/load point: {point}")
        seen.add(point)
        rows.append(parsed)
    if not rows:
        raise ValueError(f"{preview.equipment_id} curve contains no rows.")
    ambients = sorted({row["ambient_C"] for row in rows})
    loads = sorted({row["load_ratio"] for row in rows})
    if len(rows) != len(ambients) * len(loads):
        raise ValueError(f"{preview.equipment_id} ambient/load grid is incomplete.")
    return rows


def _success_result(preview, operating_point, **values):
    return EquipmentLookupResult(
        equipment_id=preview.equipment_id,
        curve_type=preview.curve_type,
        source_workbook=preview.source_workbook,
        source_sheet=preview.source_sheet,
        lookup_success=True,
        metadata=dict(getattr(preview, "metadata", {}) or {}),
        **values,
    )


def _error_result(preview, errors):
    return EquipmentLookupResult(
        equipment_id=preview.equipment_id,
        curve_type=preview.curve_type,
        source_workbook=preview.source_workbook,
        source_sheet=preview.source_sheet,
        lookup_success=False,
        errors=list(errors),
        metadata=dict(getattr(preview, "metadata", {}) or {}),
    )


def _row_by_key(rows, key, value):
    return next((row for row in rows if row[key] == value), None)


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
    raise ValueError(f"Could not find interpolation bounds for {target}.")


def _linear(x0, x1, y0, y1, x):
    if y0 is None or y1 is None:
        return None
    if x0 == x1:
        return y0
    return y0 + (y1 - y0) * ((x - x0) / (x1 - x0))


def _clamp(value, lower, upper):
    return max(lower, min(upper, value))


def _to_float(value, label):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid numeric value for {label}: {value!r}") from None


def _to_optional_float(value, label):
    if value is None:
        return None
    return _to_float(value, label)
