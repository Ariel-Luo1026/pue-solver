"""Topology-neutral unit redundancy and scenario resolution.

This module resolves project-level unit counts only. It deliberately does not
import solver.py or any equipment performance engine.
"""

from math import ceil


DEFAULT_ROLE_KEYS = (
    "cooling_units",
    "chiller_units",
    "dry_cooler_units",
    "pump_units",
    "indoor_units",
    "engine_units",
)


def calculate_required_units(design_load, unit_capacity):
    """Return duty units required to satisfy design load."""
    design = _positive_float(design_load)
    capacity = _positive_float(unit_capacity)
    if design is None or capacity is None:
        raise ValueError("design_load and unit_capacity must be greater than 0.")
    return int(ceil(design / capacity))


def calculate_unit_requirements(design_load, unit_capacity, redundancy_units=1):
    """Return N+redundancy unit requirements for a project."""
    required_units = calculate_required_units(design_load, unit_capacity)
    redundancy = _non_negative_int(redundancy_units, 1)
    installed_units = required_units + redundancy
    return {
        "required_units": required_units,
        "installed_units": installed_units,
        "normal_active_units": installed_units,
        "failure_active_units": required_units,
        "indoor_active_units": installed_units,
        "redundancy": f"N+{redundancy}" if redundancy else "N",
    }


def resolve_unit_scenario(
    design_load,
    unit_capacity,
    scenario_name="Normal",
    scenario_formula=None,
    redundancy_units=1,
    role_quantities=None,
):
    """Resolve project and per-role units for a Normal/Failure-style scenario."""
    sizing = calculate_unit_requirements(design_load, unit_capacity, redundancy_units=redundancy_units)
    formula = _scenario_formula(scenario_name, scenario_formula)
    active_units = calculate_active_units(
        sizing["required_units"],
        sizing["installed_units"],
        formula,
    )
    standby_units = max(sizing["installed_units"] - active_units, 0)
    failed_units = standby_units if _is_failure_scenario(scenario_name, formula) else 0
    resolved = {
        "required_units": sizing["required_units"],
        "installed_units": sizing["installed_units"],
        "active_units": active_units,
        "standby_units": standby_units,
        "failed_units": failed_units,
        "redundancy_mode": sizing["redundancy"],
        "scenario_name": scenario_name or "Normal",
        "scenario_formula": formula,
        "quantity_basis": "ceil(design_load / unit_capacity) with N+redundancy scenario dispatch",
    }
    resolved["role_quantities"] = _role_quantities(
        resolved,
        overrides=role_quantities,
    )
    return resolved


def calculate_active_units(required_units, installed_units, scenario_formula):
    """Evaluate a supported running-unit formula."""
    required = _non_negative_int(required_units, 0)
    installed = _non_negative_int(installed_units, required)
    formula = " ".join(str(scenario_formula or "").strip().lower().split())
    if formula in {"", "normal", "installed_units"}:
        return installed
    if formula in {"failure", "required_units"}:
        return required
    if formula == "installed_units - 1":
        return max(0, installed - 1)
    raise ValueError(f"Unsupported unit scenario formula: {scenario_formula}")


def _role_quantities(base, overrides=None):
    roles = {
        "cooling_units": _role_count(base["required_units"], base["installed_units"], base["active_units"]),
        "chiller_units": _role_count(base["required_units"], base["installed_units"], base["active_units"]),
        "dry_cooler_units": _role_count(base["required_units"], base["installed_units"], base["active_units"]),
        "pump_units": _role_count(base["required_units"], base["installed_units"], base["active_units"]),
        "indoor_units": _role_count(base["required_units"], base["installed_units"], base["installed_units"]),
        "engine_units": _role_count(base["required_units"], base["installed_units"], base["active_units"]),
    }
    if isinstance(overrides, dict):
        for role, override in overrides.items():
            if not isinstance(override, dict):
                continue
            current = roles.get(role, _role_count(base["required_units"], base["installed_units"], base["active_units"]))
            installed = _non_negative_int(override.get("installed_units"), current["installed_units"])
            active = _non_negative_int(override.get("active_units"), current["active_units"])
            required = _non_negative_int(override.get("required_units"), current["required_units"])
            roles[role] = _role_count(required, installed, active)
    return roles


def _role_count(required_units, installed_units, active_units):
    active = _non_negative_int(active_units, 0)
    installed = _non_negative_int(installed_units, active)
    return {
        "required_units": _non_negative_int(required_units, 0),
        "installed_units": installed,
        "active_units": active,
        "standby_units": max(installed - active, 0),
    }


def _scenario_formula(scenario_name, scenario_formula):
    if scenario_formula:
        return str(scenario_formula)
    return "required_units" if _is_failure_scenario(scenario_name, "") else "installed_units"


def _is_failure_scenario(scenario_name, scenario_formula):
    text = f"{scenario_name or ''} {scenario_formula or ''}".lower()
    return "failure" in text or "failed" in text or "installed_units - 1" in text


def _positive_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _non_negative_int(value, default):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return int(default)
    return number if number >= 0 else int(default)
