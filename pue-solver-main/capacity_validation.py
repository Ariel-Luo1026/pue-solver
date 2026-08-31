"""Unified unit scenario and peak capacity validation helpers.

This module derives engineering validation metrics from solver/runtime output.
It does not calculate equipment performance or change solver formulas.
"""


def validate_peak_capacity(
    topology,
    peak_results=None,
    unit_scenario=None,
    role_capacities=None,
    runtime_diagnostics=None,
):
    """Return a unified capacity validation object.

    role_capacities may contain a primary role such as ``cooling`` or
    ``chiller`` plus optional role entries such as ``dry_cooler``.
    Each role supports installed_units, active_units, unit_capacity_kW,
    installed_capacity_kW, active_capacity_kW, and peak_load_kW.
    """
    peak = peak_results if isinstance(peak_results, dict) else {}
    scenario = unit_scenario if isinstance(unit_scenario, dict) else {}
    roles = role_capacities if isinstance(role_capacities, dict) else {}
    diagnostics = runtime_diagnostics if isinstance(runtime_diagnostics, dict) else {}
    warnings = []

    peak_load = _first_number(
        peak.get("peak_design_cooling_load_kW"),
        peak.get("peak_cooling_load_kW"),
        diagnostics.get("peak_cooling_load_kW"),
    )
    if peak_load is None:
        warnings.append("Peak design cooling load is unavailable.")

    primary_role = _primary_role(topology, roles)
    primary = roles.get(primary_role, {}) if isinstance(roles.get(primary_role), dict) else {}
    installed_capacity = _capacity(primary, "installed", peak_load)
    active_capacity = _capacity(primary, "active", peak_load)
    role_validations = {}
    for role_name, role in roles.items():
        if not isinstance(role, dict):
            continue
        role_peak_load = _first_number(role.get("peak_load_kW"), peak_load)
        role_installed = _capacity(role, "installed", role_peak_load)
        role_active = _capacity(role, "active", role_peak_load)
        role_warnings = list(role.get("warnings") or [])
        if role_peak_load is None:
            role_warnings.append("Peak load is unavailable.")
        if role_active is None:
            role_warnings.append("Active capacity is unavailable.")
        role_margin = _margin(role_active, role_peak_load)
        role_validations[role_name] = {
            "status": _status(role_margin, role_warnings),
            "peak_load_kW": role_peak_load,
            "installed_capacity_kW": role_installed,
            "active_capacity_kW": role_active,
            "capacity_margin_kW": role_margin,
            "capacity_margin_percent": _margin_percent(role_margin, role_peak_load),
            "installed_units": _first_int(role.get("installed_units")),
            "required_units": _first_int(role.get("required_units")),
            "active_units": _first_int(role.get("active_units")),
            "warnings": role_warnings,
        }

    margin = _margin(active_capacity, peak_load)
    all_warnings = warnings[:]
    for role in role_validations.values():
        all_warnings.extend(role.get("warnings") or [])
    result = {
        "status": _status(margin, all_warnings),
        "topology": topology,
        "scenario_name": scenario.get("scenario_name") or diagnostics.get("scenario_name"),
        "redundancy_mode": scenario.get("redundancy_mode") or diagnostics.get("redundancy_mode"),
        "peak_cooling_load_kW": peak_load,
        "installed_capacity_kW": installed_capacity,
        "active_capacity_kW": active_capacity,
        "capacity_margin_kW": margin,
        "capacity_margin_percent": _margin_percent(margin, peak_load),
        "failed_units": _first_int(scenario.get("failed_units"), diagnostics.get("failed_units")),
        "warnings": _dedupe(all_warnings),
        "role_validations": role_validations,
    }
    return result


def operating_scenario_from_result(solver_result):
    """Return display-ready unit scenario values from a solver result."""
    result = solver_result if isinstance(solver_result, dict) else {}
    scenario = _unit_scenario(result)
    project = result.get("project") if isinstance(result.get("project"), dict) else {}
    rows = result.get("hourly_results") if isinstance(result.get("hourly_results"), list) else []
    first_row = rows[0] if rows and isinstance(rows[0], dict) else {}

    role_quantities = scenario.get("role_quantities") if isinstance(scenario.get("role_quantities"), dict) else {}
    operating = {
        "scenario_name": scenario.get("scenario_name") or result.get("scenario_name") or project.get("scenario_name"),
        "redundancy_mode": scenario.get("redundancy_mode") or project.get("redundancy_strategy"),
        "installed_units": _first_int(scenario.get("installed_units"), project.get("installed_units")),
        "required_units": _first_int(scenario.get("required_units"), project.get("required_units")),
        "active_units": _first_int(scenario.get("active_units"), project.get("active_units")),
        "standby_units": _first_int(scenario.get("standby_units"), project.get("standby_units")),
        "failed_units": _first_int(scenario.get("failed_units")),
    }
    for role_name, output_key in (
        ("chiller_units", "active_chiller_units"),
        ("dry_cooler_units", "active_dry_cooler_units"),
        ("pump_units", "active_pump_units"),
    ):
        role = role_quantities.get(role_name) if isinstance(role_quantities.get(role_name), dict) else {}
        value = _first_int(role.get("active_units"), first_row.get(output_key))
        if value is not None:
            operating[output_key] = value
    return {key: value for key, value in operating.items() if value is not None}


def derive_capacity_validation_from_result(topology, solver_result):
    """Build capacity validation from an existing solver/runtime result."""
    result = solver_result if isinstance(solver_result, dict) else {}
    existing = result.get("capacity_validation")
    if isinstance(existing, dict):
        return existing

    project = result.get("project") if isinstance(result.get("project"), dict) else {}
    peak = result.get("peak_results") if isinstance(result.get("peak_results"), dict) else {}
    scenario = _unit_scenario(result)
    hourly = result.get("hourly_results") if isinstance(result.get("hourly_results"), list) else []
    first_row = hourly[0] if hourly and isinstance(hourly[0], dict) else {}
    peak_load = _first_number(
        peak.get("peak_design_cooling_load_kW"),
        max(
            [
                float(row.get("cooling_load_kW"))
                for row in hourly
                if isinstance(row, dict) and _is_number(row.get("cooling_load_kW"))
            ],
            default=None,
        ),
    )

    if topology == "acc_gas_engine_cdu":
        active_units = _first_int(scenario.get("active_units"), project.get("active_units"))
        required_per_unit = _first_number(
            peak.get("peak_design_ACC_required_capacity_per_unit_kW"),
            peak.get("peak_design_required_capacity_per_acc_unit_kW"),
            peak_load / active_units if peak_load is not None and active_units else None,
        )
        used_per_unit = _first_number(peak.get("peak_design_ACC_used_capacity_per_unit_kW"))
        lookup_success = peak.get("peak_design_ACC_curve_lookup_success") is True
        capacity_clamped = peak.get("peak_design_ACC_capacity_clamped") is True
        diagnostics_present = "peak_design_ACC_curve_lookup_success" in peak
        if diagnostics_present:
            tolerance = max(1e-6, abs(required_per_unit) * 1e-9) if required_per_unit is not None else 1e-6
            curve_adequate = (
                lookup_success
                and required_per_unit is not None
                and used_per_unit is not None
                and not capacity_clamped
                and used_per_unit + tolerance >= required_per_unit
            )
            nominal_unit_capacity = _first_number(
                project.get("cooling_unit_capacity_kW"),
                first_row.get("cooling_unit_capacity_kW"),
            )
            nominal_active_capacity = (
                active_units * nominal_unit_capacity
                if active_units is not None and nominal_unit_capacity is not None
                else None
            )
            nominal_margin = _margin(nominal_active_capacity, peak_load)
            warnings = [] if curve_adequate else [
                "Peak ACC curve lookup did not establish adequate capacity within the valid unclamped curve domain."
            ]
            return {
                "status": "valid" if curve_adequate else "error",
                "topology": topology,
                "scenario_name": scenario.get("scenario_name"),
                "redundancy_mode": scenario.get("redundancy_mode"),
                "peak_cooling_load_kW": peak_load,
                "active_units": active_units,
                "required_capacity_per_unit_kW": required_per_unit,
                "used_capacity_per_unit_kW": used_per_unit,
                "curve_lookup_success": lookup_success,
                "capacity_clamped": capacity_clamped,
                "capacity_adequacy_basis": "peak_design_acc_capacity_surface",
                "installed_capacity_kW": None,
                "active_capacity_kW": used_per_unit * active_units if used_per_unit is not None and active_units is not None else None,
                "capacity_margin_kW": None,
                "capacity_margin_percent": None,
                "nominal_active_capacity_kW": nominal_active_capacity,
                "nominal_capacity_margin_kW": nominal_margin,
                "nominal_capacity_margin_percent": _margin_percent(nominal_margin, peak_load),
                "failed_units": _first_int(scenario.get("failed_units")),
                "warnings": warnings,
                "role_validations": {},
            }

    unit_capacity = _first_number(
        project.get("cooling_unit_capacity_kW"),
        first_row.get("cooling_unit_capacity_kW"),
        first_row.get("chiller_unit_capacity_kW"),
    )
    installed_units = _first_int(scenario.get("installed_units"), project.get("installed_units"))
    required_units = _first_int(scenario.get("required_units"), project.get("required_units"))
    active_units = _first_int(scenario.get("active_units"), project.get("active_units"))
    roles = {}
    if unit_capacity is not None:
        roles["cooling"] = {
            "installed_units": installed_units,
            "required_units": required_units,
            "active_units": active_units,
            "unit_capacity_kW": unit_capacity,
            "peak_load_kW": peak_load,
        }
    return validate_peak_capacity(topology, peak, scenario, roles)


def _unit_scenario(result):
    context = result.get("library_context") if isinstance(result.get("library_context"), dict) else {}
    assumptions = context.get("runtime_assumptions") if isinstance(context.get("runtime_assumptions"), dict) else {}
    scenario = assumptions.get("unit_scenario") if isinstance(assumptions.get("unit_scenario"), dict) else {}
    return scenario


def _primary_role(topology, roles):
    if topology == "chiller_dry_cooler" and "chiller" in roles:
        return "chiller"
    if "cooling" in roles:
        return "cooling"
    if roles:
        return next(iter(roles))
    return "cooling"


def _capacity(role, mode, peak_load):
    direct = _first_number(role.get(f"{mode}_capacity_kW"))
    if direct is not None:
        return direct
    units = _first_int(role.get(f"{mode}_units"))
    unit_capacity = _first_number(role.get("unit_capacity_kW"))
    if units is None or unit_capacity is None:
        return None
    return units * unit_capacity


def _margin(capacity, load):
    if capacity is None or load is None:
        return None
    return capacity - load


def _margin_percent(margin, load):
    if margin is None or load in (None, 0):
        return None
    return margin / load * 100.0


def _status(margin, warnings):
    if margin is not None and margin < 0:
        return "error"
    if warnings:
        return "warning"
    return "valid"


def _first_number(*values):
    for value in values:
        if _is_number(value):
            return float(value)
    return None


def _first_int(*values):
    for value in values:
        if _is_number(value):
            return int(float(value))
    return None


def _is_number(value):
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _dedupe(values):
    seen = set()
    result = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
