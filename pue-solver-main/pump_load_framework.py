"""Shared single-curve pump load and power calculation."""

PUMP_LOAD_RATIO_BASIS = "hourly cooling load / (active pump count * fixed single-pump reference capacity)"
COOLING_UNIT_RATED_CAPACITY_LOAD_RATIO_BASIS = (
    "cooling_load_per_active_unit_over_cooling_unit_rated_capacity"
)


class PumpLoadFrameworkError(ValueError):
    pass


def resolve_pump_reference_capacity(role_metadata=None, equipment_metadata=None, associated_equipment_capacity_kW=None, cooling_unit_capacity_kW=None):
    role_metadata = role_metadata if isinstance(role_metadata, dict) else {}
    equipment_metadata = equipment_metadata if isinstance(equipment_metadata, dict) else {}
    candidates = (
        (role_metadata.get("pump_reference_capacity_kW"), "role_metadata.pump_reference_capacity_kW"),
        (equipment_metadata.get("reference_capacity_kW"), "equipment_metadata.reference_capacity_kW"),
        (associated_equipment_capacity_kW, "associated_dry_cooler_rated_heat_rejection_capacity_kW"),
        (cooling_unit_capacity_kW, "cooling_unit_rated_capacity_kW"),
    )
    for value, source in candidates:
        try:
            capacity = float(value)
        except (TypeError, ValueError):
            continue
        if capacity > 0:
            return capacity, source
    raise PumpLoadFrameworkError(
        "Pump reference capacity is unavailable. Provide pump_reference_capacity_kW, "
        "reference_capacity_kW, an associated equipment capacity, or a positive cooling-unit rated capacity."
    )


def evaluate_pump_power(cooling_load_kW, active_pump_count, reference_capacity_kW, curve_rows, curve_source="Solver_Curve"):
    try:
        cooling_load = max(0.0, float(cooling_load_kW))
        active_count = int(active_pump_count)
        reference_capacity = float(reference_capacity_kW)
    except (TypeError, ValueError) as exc:
        raise PumpLoadFrameworkError(f"Invalid pump operating-point input: {exc}") from exc
    if reference_capacity <= 0:
        raise PumpLoadFrameworkError("Pump reference capacity must be greater than zero.")
    points = []
    for row in curve_rows or []:
        if isinstance(row, dict):
            try:
                points.append((float(row["load_ratio"]), float(row["power_kW"])))
            except (KeyError, TypeError, ValueError):
                pass
    points.sort()
    if not points:
        raise PumpLoadFrameworkError("Pump Solver_Curve requires numeric load_ratio and power_kW columns.")
    curve_min, curve_max = points[0][0], points[-1][0]
    if active_count <= 0 or cooling_load <= 0:
        return _diagnostics(reference_capacity, active_count, 0.0, 0.0, None, curve_min, curve_max,
                            0.0, 0.0, False, False, False, curve_source)
    required_per_unit = cooling_load / active_count
    raw_ratio = required_per_unit / reference_capacity
    lookup_ratio = min(curve_max, max(curve_min, raw_ratio))
    clamped_low = 0.0 < raw_ratio < curve_min
    clamped_high = raw_ratio > curve_max
    per_unit = _interpolate(points, lookup_ratio)
    return _diagnostics(reference_capacity, active_count, required_per_unit, raw_ratio, lookup_ratio,
                        curve_min, curve_max, per_unit, per_unit * active_count,
                        clamped_low, clamped_high, clamped_high, curve_source)


def _interpolate(points, x_value):
    if x_value <= points[0][0]:
        return points[0][1]
    for left, right in zip(points, points[1:]):
        if x_value <= right[0]:
            span = right[0] - left[0]
            return right[1] if span == 0 else left[1] + (x_value - left[0]) * (right[1] - left[1]) / span
    return points[-1][1]


def _diagnostics(reference, active, required, raw, lookup, curve_min, curve_max, per_unit, total,
                 clamped_low, clamped_high, overload, source):
    return {
        "pump_reference_capacity_per_unit_kW": reference,
        "pump_active_unit_count": active,
        "pump_required_load_per_unit_kW": required,
        "pump_load_ratio_raw": raw,
        "pump_load_ratio_lookup": lookup,
        "pump_curve_min_load_ratio": curve_min,
        "pump_curve_max_load_ratio": curve_max,
        "pump_power_per_unit_kW": per_unit,
        "pump_power_total_kW": total,
        "pump_clamped_low": clamped_low,
        "pump_clamped_high": clamped_high,
        "pump_overload": overload,
        "pump_curve_source": source,
        "pump_load_ratio_basis": PUMP_LOAD_RATIO_BASIS,
    }
