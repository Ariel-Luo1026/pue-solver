"""Dispatch solver results to topology-specific report profile metadata."""

from copy import deepcopy

from report_profile_registry import (
    get_generic_report_profile,
    get_report_profile_for_topology,
)
from capacity_validation import (
    derive_capacity_validation_from_result,
    operating_scenario_from_result,
)
from energy_aggregation import AnnualEnergyAggregationError, aggregate_annual_energy
from report_sections import build_report_sections


MONTH_HOURS = tuple(days * 24 for days in (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31))


def _annual_results(solver_result):
    if not isinstance(solver_result, dict):
        return {}
    annual = solver_result.get("annual_results")
    return annual if isinstance(annual, dict) else {}


def _hourly_results(solver_result):
    if not isinstance(solver_result, dict):
        return []
    hourly = solver_result.get("hourly_results")
    return hourly if isinstance(hourly, list) else []


def _field_value(annual, derived, field):
    key = field.get("key")
    if key in annual:
        return annual.get(key)
    if key in derived:
        return derived.get(key)
    for fallback_key in field.get("fallback_keys", []):
        if fallback_key in annual:
            return annual.get(fallback_key)
        if fallback_key in derived:
            return derived.get(fallback_key)
    return None


def _derived_summary_values(solver_result):
    hourly = _hourly_results(solver_result)
    chiller_cops = [
        float(_standard_performance_value(row, "chiller_performance_result", "COP", row.get("chiller_COP")))
        for row in hourly
        if isinstance(row, dict)
        and _is_number(_standard_performance_value(row, "chiller_performance_result", "COP", row.get("chiller_COP")))
    ]
    dry_cooler_capacities = [
        float(_standard_performance_value(row, "dry_cooler_performance_result", "capacity_kW", row.get("dry_cooler_capacity_kW")))
        for row in hourly
        if isinstance(row, dict)
        and _is_number(_standard_performance_value(row, "dry_cooler_performance_result", "capacity_kW", row.get("dry_cooler_capacity_kW")))
    ]
    values = {}
    if chiller_cops:
        values["average_chiller_COP"] = sum(chiller_cops) / len(chiller_cops)
        values["min_chiller_COP"] = min(chiller_cops)
        values["max_chiller_COP"] = max(chiller_cops)
    if dry_cooler_capacities:
        values["dry_cooler_capacity_kW"] = max(dry_cooler_capacities)
    if isinstance(solver_result, dict):
        values["configuration_status"] = solver_result.get("implementation_status")
    return values


def _is_number(value):
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _standard_performance_value(row, result_key, performance_key, fallback=None):
    result = row.get(result_key) if isinstance(row, dict) else None
    performance = result.get("performance") if isinstance(result, dict) else None
    if isinstance(performance, dict) and performance.get(performance_key) is not None:
        return performance.get(performance_key)
    return fallback


def dispatch_report(topology, solver_result):
    """Return report profile metadata plus summary values for a topology.

    Unknown topologies intentionally return a generic PUE-only profile instead
    of raising; report export should remain possible for solver results that do
    not yet have topology-specific presentation metadata.
    """
    profile = get_report_profile_for_topology(topology)
    if profile is None:
        profile = get_generic_report_profile(topology or "unknown")
        profile["dispatch_status"] = "generic"
    else:
        profile["dispatch_status"] = "matched"

    annual = _annual_results(solver_result)
    derived = _derived_summary_values(solver_result)
    summary = {}
    for field in profile.get("fields", []):
        summary[field["key"]] = _field_value(annual, derived, field)

    dispatched = deepcopy(profile)
    operating_scenario = operating_scenario_from_result(solver_result)
    capacity_validation = derive_capacity_validation_from_result(topology, solver_result)
    annual_energy_breakdown = _annual_energy_breakdown(solver_result)
    dispatched["summary"] = summary
    dispatched["operating_scenario"] = operating_scenario
    dispatched["capacity_validation"] = capacity_validation
    dispatched["annual_energy_breakdown"] = annual_energy_breakdown
    dispatched["visualization_data"] = build_visualization_data(solver_result)
    dispatched["equipment_curve_register"] = build_equipment_curve_register(solver_result)
    dispatched["equipment_performance"] = build_equipment_performance(
        solver_result, annual_energy_breakdown, derived
    )
    dispatched["cooling_load_breakdown"] = build_cooling_load_breakdown(solver_result)
    dispatched["report_sections"] = build_report_sections(
        topology,
        solver_result,
        profile=dispatched,
        operating_scenario=operating_scenario,
        capacity_validation=capacity_validation,
        annual_energy_breakdown=annual_energy_breakdown,
    )
    return dispatched


def build_visualization_data(solver_result):
    """Map standardized hourly runtime rows to topology-neutral report data."""
    hourly = [row for row in _hourly_results(solver_result) if isinstance(row, dict)]
    temperature_vs_pue = []
    facility_rows = []
    pue_rows = []
    for index, row in enumerate(hourly):
        temperature = _hourly_dry_bulb(row)
        pue = _first_number(row, ("pue", "hourly_PUE", "PUE"))
        facility_power = _first_number(row, ("facility_power_kW", "total_facility_power_kW"))
        hour = _first_number(row, ("hour_index", "hour"))
        record = (row, int(hour) if hour is not None else index + 1, pue, facility_power)
        if temperature is not None and pue is not None:
            temperature_vs_pue.append({"temperature_C": temperature, "pue": pue})
        if facility_power is not None:
            facility_rows.append(record)
        if pue is not None:
            pue_rows.append(record)

    peak_record = max(facility_rows, key=lambda item: item[3]) if facility_rows else None
    max_pue_record = max(pue_rows, key=lambda item: item[2]) if pue_rows else None
    peak_row = peak_record[0] if peak_record else {}
    peak_summary = {
        "peak_facility_hour": peak_record[1] if peak_record else None,
        "peak_pue": peak_record[2] if peak_record else None,
        "peak_facility_power_kW": peak_record[3] if peak_record else None,
        "peak_it_load_kW": _first_number(peak_row, ("it_load_kW", "IT_load_kW")),
        "peak_outdoor_dry_bulb_C": _hourly_dry_bulb(peak_row),
        "max_hourly_pue": max_pue_record[2] if max_pue_record else None,
        "max_hourly_pue_hour": max_pue_record[1] if max_pue_record else None,
    }
    return {
        "temperature_vs_pue": temperature_vs_pue,
        "peak_summary": peak_summary,
        "monthly_pue": _monthly_pue(hourly),
    }


def build_equipment_curve_register(solver_result):
    context = solver_result.get("library_context") if isinstance(solver_result, dict) else {}
    context = context if isinstance(context, dict) else {}
    selected = context.get("selected_curves") or solver_result.get("selected_curves") or {}
    if not isinstance(selected, dict):
        return []
    rows = []
    for equipment_id, curve in selected.items():
        if not isinstance(curve, dict):
            continue
        sheet = curve.get("sheet_name") or curve.get("selected_curve_sheet")
        metadata = curve.get("equipment_metadata") if isinstance(curve.get("equipment_metadata"), dict) else {}
        curve_type = metadata.get("curve_type") or curve.get("curve_type") or sheet
        if not sheet and not curve.get("electrical_path") and not curve_type:
            continue
        rows.append({
            "equipment_id": str(equipment_id),
            "curve_source": "Configuration Library Solver_Curve",
            "curve_type": curve_type or "Equipment Performance Curve",
            "model_basis": _curve_model_basis(metadata, curve),
        })
    return rows


def build_equipment_performance(solver_result, annual_energy, derived=None):
    annual = _annual_results(solver_result)
    summary = {**annual, **(derived or {})}
    components = annual_energy.get("components") if isinstance(annual_energy, dict) else {}
    if not isinstance(components, dict):
        return []
    rows = []
    for equipment, component in components.items():
        if not isinstance(component, dict) or not _is_number(component.get("energy_kWh")):
            continue
        metric_value = _average_metric(summary, equipment, "cop")
        rows.append({
            "equipment": equipment,
            "annual_energy_kWh": float(component["energy_kWh"]),
            "performance_metric": "Average COP" if metric_value is not None else None,
            "metric_value": metric_value,
        })
    return rows


def build_cooling_load_breakdown(solver_result):
    annual = _annual_results(solver_result)
    return {
        "annual_it_load_kWh": _number_or_none(annual.get("annual_IT_energy_kWh")),
        "annual_solar_heat_gain_kWh": _number_or_none(annual.get("annual_solar_heat_gain_kWh")),
        "annual_other_auxiliary_heat_gain_kWh": _number_or_none(
            annual.get("annual_other_auxiliary_heat_gain_kWh")
        ),
        "annual_cooling_load_kWh": _number_or_none(annual.get("annual_cooling_load_kWh")),
    }


def _monthly_pue(hourly):
    rows = []
    offset = 0
    for month, hours in enumerate(MONTH_HOURS, start=1):
        month_rows = hourly[offset:offset + hours]
        offset += hours
        facility = sum(filter(lambda value: value is not None, (
            _first_number(row, ("facility_power_kW", "total_facility_power_kW")) for row in month_rows
        )))
        it_energy = sum(filter(lambda value: value is not None, (
            _first_number(row, ("it_load_kW", "IT_load_kW")) for row in month_rows
        )))
        if it_energy > 0:
            rows.append({"month": month, "average_pue": facility / it_energy})
    return rows


def _curve_model_basis(metadata, curve):
    independent = metadata.get("independent_variables")
    if isinstance(independent, list) and independent:
        return "Hourly " + " and ".join(str(value) for value in independent) + " lookup"
    if curve.get("electrical_path"):
        return "Hourly electrical path efficiency lookup"
    return "Hourly temperature and load lookup"


def _average_metric(summary, equipment, metric):
    normalized_equipment = str(equipment).lower()
    candidates = (
        f"average_{normalized_equipment}_{metric}",
        f"average_{normalized_equipment}{metric}",
    )
    lower_summary = {str(key).lower(): value for key, value in summary.items()}
    for candidate in candidates:
        value = lower_summary.get(candidate)
        if _is_number(value):
            return float(value)
    return None


def _number_or_none(value):
    return float(value) if _is_number(value) else None


def _first_number(row, keys):
    for key in keys:
        value = row.get(key)
        if _is_number(value):
            return float(value)
    return None


def _hourly_dry_bulb(row):
    return _first_number(
        row,
        (
            "dry_bulb_C",
            "outdoor_dry_bulb_C",
            "outdoor_temp_C",
            "weather_dry_bulb_C",
            "dry_bulb",
            "ambient_dry_bulb_C",
        ),
    )


def _annual_energy_breakdown(solver_result):
    if isinstance(solver_result, dict) and isinstance(solver_result.get("standard_annual_energy"), dict):
        return solver_result["standard_annual_energy"]
    try:
        return aggregate_annual_energy(solver_result)
    except AnnualEnergyAggregationError as exc:
        fallback = _annual_energy_from_annual_results(solver_result)
        if fallback is not None:
            return fallback
        return {"status": "unavailable", "warnings": [str(exc)], "components": {}}


def _annual_energy_from_annual_results(solver_result):
    annual = _annual_results(solver_result)
    if not annual:
        return None
    components = {}

    def add(key, value):
        if _is_number(value):
            components[key] = {"energy_kWh": float(value), "sources": ["annual_results"]}

    add("ACC", annual.get("annual_acc_energy_kWh"))
    add("CHILLER", annual.get("annual_chiller_energy_kWh"))
    add("DRY_COOLER", annual.get("annual_dry_cooler_energy_kWh"))
    add("CHW_PUMP", annual.get("annual_pump_energy_kWh"))
    add(
        "INDOOR_EQUIPMENT",
        annual.get("annual_white_space_equipment_energy_kWh")
        or annual.get("annual_indoor_equipment_energy_kWh"),
    )
    add("ELECTRICAL_LOSS", annual.get("annual_electrical_loss_kWh"))
    cooling = sum(
        component["energy_kWh"]
        for key, component in components.items()
        if key in {"ACC", "CHILLER", "DRY_COOLER", "CHW_PUMP"}
    )
    return {
        "annual_it_energy_kWh": annual.get("annual_IT_energy_kWh"),
        "annual_facility_energy_kWh": annual.get("annual_facility_energy_kWh"),
        "annual_cooling_energy_kWh": cooling,
        "components": components,
        "PUE": annual.get("annual_average_PUE"),
        "warnings": [],
    }
