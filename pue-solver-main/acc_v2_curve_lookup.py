"""ACC V2 curve lookup engine.

Phase 13C adds reusable lookup/interpolation APIs only. It does not import
solver.py and is not connected to any production calculation path.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ACCOperatingPoint:
    ambient_C: float
    load_ratio: float
    capacity_kW: float
    power_input_kW: float
    unit_efficiency_kW_per_kW: float
    cop: float


@dataclass(frozen=True)
class RTCOperatingPoint:
    load_ratio: float
    power_kW: float


@dataclass(frozen=True)
class CDUOperatingPoint:
    load_ratio: float
    power_kW: float


@dataclass(frozen=True)
class CHWPumpOperatingPoint:
    load_ratio: float
    power_kW: float
    source: str = "configuration_library_solver_curve"


def lookup_acc_curve(preview, ambient_C, load_ratio):
    """Return an interpolated ACC operating point from a 2D curve preview."""
    rows = _acc_rows(preview)
    ambient_values = sorted({row["ambient_C"] for row in rows})
    load_values = sorted({row["load_ratio"] for row in rows})
    grid = _acc_grid(rows)

    ambient = _clamp(_to_float(ambient_C, "ambient_C"), ambient_values[0], ambient_values[-1])
    load = _clamp(_to_float(load_ratio, "load_ratio"), load_values[0], load_values[-1])
    lower_ambient, upper_ambient = _bounds(ambient_values, ambient)
    lower_load, upper_load = _bounds(load_values, load)

    corners = {
        (a, l): grid.get((a, l))
        for a in (lower_ambient, upper_ambient)
        for l in (lower_load, upper_load)
    }
    missing = [point for point, row in corners.items() if row is None]
    if missing:
        raise ValueError(f"Missing interpolation neighbors for ACC curve: {missing}")

    interpolated = {}
    for field in ("capacity_kW", "power_input_kW", "unit_efficiency_kW_per_kW"):
        lower_line = _linear(
            lower_load,
            upper_load,
            corners[(lower_ambient, lower_load)][field],
            corners[(lower_ambient, upper_load)][field],
            load,
        )
        upper_line = _linear(
            lower_load,
            upper_load,
            corners[(upper_ambient, lower_load)][field],
            corners[(upper_ambient, upper_load)][field],
            load,
        )
        interpolated[field] = _linear(
            lower_ambient,
            upper_ambient,
            lower_line,
            upper_line,
            ambient,
        )

    return ACCOperatingPoint(
        ambient_C=ambient,
        load_ratio=load,
        capacity_kW=interpolated["capacity_kW"],
        power_input_kW=interpolated["power_input_kW"],
        unit_efficiency_kW_per_kW=interpolated["unit_efficiency_kW_per_kW"],
        cop=interpolated["unit_efficiency_kW_per_kW"],
    )


def lookup_rtc_curve(preview, load_ratio):
    """Return an interpolated RTC operating point from a 1D power curve."""
    load, power = _lookup_power_curve(preview, load_ratio, equipment_label="RTC")
    return RTCOperatingPoint(load_ratio=load, power_kW=power)


def lookup_cdu_curve(preview, load_ratio):
    """Return an interpolated CDU operating point from a 1D power curve."""
    load, power = _lookup_power_curve(preview, load_ratio, equipment_label="CDU")
    return CDUOperatingPoint(load_ratio=load, power_kW=power)


def lookup_chw_pump_curve(preview, load_ratio):
    """Return an interpolated CHW pump operating point from a 1D power curve."""
    load, power = _lookup_power_curve(preview, load_ratio, equipment_label="CHW pump")
    return CHWPumpOperatingPoint(load_ratio=load, power_kW=power)


def _acc_rows(preview):
    raw_rows = getattr(preview, "solver_curve_rows", None) or []
    if not raw_rows:
        raise ValueError("ACC curve contains no rows.")
    rows = []
    seen = set()
    for index, row in enumerate(raw_rows, start=1):
        parsed = {
            "ambient_C": _to_float(row.get("ambient_C"), f"ACC row {index} ambient_C"),
            "load_ratio": _to_float(row.get("load_ratio"), f"ACC row {index} load_ratio"),
            "capacity_kW": _to_float(row.get("capacity_kW"), f"ACC row {index} capacity_kW"),
            "power_input_kW": _to_float(row.get("power_input_kW"), f"ACC row {index} power_input_kW"),
            "unit_efficiency_kW_per_kW": _to_float(
                row.get("unit_efficiency_kW_per_kW"),
                f"ACC row {index} unit_efficiency_kW_per_kW",
            ),
        }
        point = (parsed["ambient_C"], parsed["load_ratio"])
        if point in seen:
            raise ValueError(f"Duplicate ACC lookup grid point: {point}")
        seen.add(point)
        rows.append(parsed)
    _validate_rectangular_grid(rows)
    return rows


def _acc_grid(rows):
    return {(row["ambient_C"], row["load_ratio"]): row for row in rows}


def _validate_rectangular_grid(rows):
    ambient_values = sorted({row["ambient_C"] for row in rows})
    load_values = sorted({row["load_ratio"] for row in rows})
    expected_count = len(ambient_values) * len(load_values)
    if len(rows) != expected_count:
        raise ValueError("ACC ambient/load grid is inconsistent; not all grid points are present.")


def _lookup_power_curve(preview, load_ratio, equipment_label):
    rows = _power_rows(preview, equipment_label)
    load_values = [row["load_ratio"] for row in rows]
    load = _clamp(_to_float(load_ratio, "load_ratio"), load_values[0], load_values[-1])
    lower_load, upper_load = _bounds(load_values, load)
    lower_row = _row_by_load(rows, lower_load)
    upper_row = _row_by_load(rows, upper_load)
    if lower_row is None or upper_row is None:
        raise ValueError(f"Missing interpolation neighbors for {equipment_label} curve.")
    return load, _linear(lower_load, upper_load, lower_row["power_kW"], upper_row["power_kW"], load)


def _power_rows(preview, equipment_label):
    raw_rows = getattr(preview, "solver_curve_rows", None) or []
    if not raw_rows:
        raise ValueError(f"{equipment_label} curve contains no rows.")
    rows = []
    seen = set()
    for index, row in enumerate(raw_rows, start=1):
        parsed = {
            "load_ratio": _to_float(row.get("load_ratio"), f"{equipment_label} row {index} load_ratio"),
            "power_kW": _to_float(row.get("power_kW"), f"{equipment_label} row {index} power_kW"),
        }
        if parsed["load_ratio"] in seen:
            raise ValueError(f"Duplicate {equipment_label} load_ratio point: {parsed['load_ratio']}")
        seen.add(parsed["load_ratio"])
        rows.append(parsed)
    return sorted(rows, key=lambda row: row["load_ratio"])


def _row_by_load(rows, load):
    for row in rows:
        if row["load_ratio"] == load:
            return row
    return None


def _bounds(values, target):
    values = sorted(values)
    if len(values) == 1:
        return values[0], values[0]
    if target <= values[0]:
        return values[0], values[0]
    if target >= values[-1]:
        return values[-1], values[-1]
    for index in range(len(values) - 1):
        lower = values[index]
        upper = values[index + 1]
        if lower <= target <= upper:
            return lower, upper
    raise ValueError(f"Could not find interpolation bounds for {target}.")


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
        raise ValueError(f"Invalid numeric value for {label}: {value!r}") from None
