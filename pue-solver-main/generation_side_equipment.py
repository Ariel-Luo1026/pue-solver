"""Topology-neutral gas-engine generation and engine-radiator helpers.

Equipment pairing is configuration-owned: callers pass independently resolved
``engine`` and ``engine_radiator`` bindings.  This module never selects a model
from a topology name or assumes a particular ENGINE_x / ENGINE_RADIATOR_x ID.
"""

from dataclasses import dataclass

from equipment_role_resolver import resolve_equipment_role_id


class GenerationSideEquipmentError(ValueError):
    """Raised when configured generation-side equipment cannot be evaluated."""


@dataclass(frozen=True)
class GenerationRoleIds:
    engine: str
    engine_radiator: str


def generation_is_applicable(power_source):
    """Return whether the declared power source requires generation equipment."""
    normalized = "".join(character for character in str(power_source or "").lower() if character.isalnum())
    return normalized == "gasengine"


def gas_engine_roles_for_power_source(manifest, loaded_equipment, power_source):
    """Activate generation roles only for an explicitly configured Gas Engine source."""
    if not generation_is_applicable(power_source):
        return None
    return resolve_generation_role_ids(manifest, loaded_equipment)


def resolve_generation_role_ids(manifest, loaded_equipment):
    """Resolve independent Engine and Engine Radiator models from manifest roles."""
    engine_id = resolve_equipment_role_id(manifest, "engine", loaded_equipment)
    radiator_id = resolve_equipment_role_id(manifest, "engine_radiator", loaded_equipment)
    if not isinstance(engine_id, str) or not engine_id:
        raise GenerationSideEquipmentError("Configured Gas Engine requires a scalar engine role.")
    if not isinstance(radiator_id, str) or not radiator_id:
        raise GenerationSideEquipmentError(
            "Configured Gas Engine requires a scalar engine_radiator role."
        )
    return GenerationRoleIds(engine=engine_id, engine_radiator=radiator_id)


def equipment_id_from_curve(curve, role_name):
    """Return the selected model ID carried by a Configuration Library curve."""
    equipment_id = curve.get("equipment_id") if isinstance(curve, dict) else None
    if not isinstance(equipment_id, str) or not equipment_id.strip():
        raise GenerationSideEquipmentError(
            f"Configured {role_name} curve is missing its selected equipment_id."
        )
    return equipment_id.strip()


def evaluate_engine_generation(
    curve,
    load_ratio,
    active_units,
    lookup_power_per_unit,
    evaluate_curve_1d,
):
    """Evaluate generation reference metrics without adding output to facility load.

    ``lookup_power_per_unit`` must read the selected workbook-backed curve.  Fuel
    behavior intentionally preserves the existing ACC direct-mode semantics:
    use the selected efficiency curve when present, otherwise the configured
    default efficiency carried by the binding.
    """
    equipment_id = equipment_id_from_curve(curve, "engine")
    rows = curve.get("data") if isinstance(curve, dict) else None
    if not isinstance(rows, list) or not rows:
        raise GenerationSideEquipmentError(
            f"{equipment_id} configured engine curve is missing or empty."
        )
    units = _positive_units(active_units, "engine_active_units")
    per_unit_output = max(0.0, float(lookup_power_per_unit(equipment_id, rows, load_ratio)))
    total_output = per_unit_output * units
    efficiency_points = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ratio = _number_or_none(row.get("load_ratio"))
        efficiency = _number_or_none(row.get("engine_efficiency"))
        if efficiency is None:
            efficiency = _number_or_none(row.get("efficiency"))
        if ratio is not None and efficiency is not None:
            efficiency_points.append([ratio, efficiency])
    if efficiency_points:
        efficiency = float(evaluate_curve_1d(efficiency_points, load_ratio, "linear"))
    else:
        efficiency = _number_or_none(curve.get("default_efficiency"))
        if efficiency is None:
            raise GenerationSideEquipmentError(
                f"{equipment_id} has no engine efficiency curve or configured default efficiency."
            )
    efficiency = min(1.0, max(1e-6, float(efficiency)))
    fuel_input = total_output / efficiency
    return {
        "equipment_id": equipment_id,
        "active_units": units,
        "output_kW": total_output,
        "efficiency": efficiency,
        "fuel_input_kW": fuel_input,
        "waste_heat_kW": max(0.0, fuel_input - total_output),
    }


def engine_radiator_load_ratio(current_non_radiator_facility_kW, reference_non_radiator_facility_kW):
    """Canonical radiator normalization used by the existing ACC implementation.

    load ratio = current non-radiator facility demand / Failure Peak Design
    non-radiator facility demand.  The curve engine remains responsible for
    applying its configured lookup bounds.
    """
    current = max(0.0, float(current_non_radiator_facility_kW or 0.0))
    reference = float(reference_non_radiator_facility_kW or 0.0)
    return current / reference if reference > 0 else 0.0


def linear_curve_value(points, x, method="linear"):
    """Evaluate numeric [x, y] points with the solver's linear clamp semantics."""
    ordered = sorted((float(point[0]), float(point[1])) for point in points)
    if not ordered:
        raise GenerationSideEquipmentError("Cannot evaluate an empty curve.")
    target = float(x)
    if target <= ordered[0][0]:
        return ordered[0][1]
    if target >= ordered[-1][0]:
        return ordered[-1][1]
    for (x0, y0), (x1, y1) in zip(ordered, ordered[1:]):
        if x0 <= target <= x1:
            if x1 == x0:
                raise GenerationSideEquipmentError(f"Duplicate curve point: {x0}")
            return y0 + (target - x0) * (y1 - y0) / (x1 - x0)
    return ordered[-1][1]


def evaluate_engine_radiator(
    curve,
    current_non_radiator_facility_kW,
    reference_non_radiator_facility_kW,
    active_units,
    lookup_power_per_unit,
):
    """Evaluate the independently selected radiator as facility-side MEP power."""
    equipment_id = equipment_id_from_curve(curve, "engine_radiator")
    rows = curve.get("data") if isinstance(curve, dict) else None
    if not isinstance(rows, list) or not rows:
        raise GenerationSideEquipmentError(
            f"{equipment_id} configured engine_radiator curve is missing or empty."
        )
    units = _positive_units(active_units, "engine_radiator_active_units")
    ratio = engine_radiator_load_ratio(
        current_non_radiator_facility_kW,
        reference_non_radiator_facility_kW,
    )
    lookup = lookup_power_per_unit(equipment_id, rows, ratio)
    if isinstance(lookup, dict):
        per_unit_power = lookup.get("power_kW")
        lookup_ratio = lookup.get("load_ratio", ratio)
    else:
        per_unit_power = lookup
        lookup_ratio = ratio
    if per_unit_power is None:
        raise GenerationSideEquipmentError(
            f"{equipment_id} engine_radiator lookup returned no electrical power."
        )
    return {
        "equipment_id": equipment_id,
        "active_units": units,
        "load_ratio": ratio,
        "lookup_load_ratio": float(lookup_ratio),
        "power_per_unit_kW": max(0.0, float(per_unit_power)),
        "total_power_kW": max(0.0, float(per_unit_power)) * units,
    }


def _positive_units(value, field_name):
    try:
        units = int(value)
    except (TypeError, ValueError) as exc:
        raise GenerationSideEquipmentError(f"{field_name} must be a positive integer.") from exc
    if units <= 0:
        raise GenerationSideEquipmentError(f"{field_name} must be a positive integer.")
    return units


def _number_or_none(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
