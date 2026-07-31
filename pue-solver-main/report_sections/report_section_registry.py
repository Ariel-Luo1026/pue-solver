"""Common report section definitions and deterministic section builders.

This module formats existing solver/runtime outputs for reporting. It does
not calculate equipment performance, capacity, or annual energy.
"""

from copy import deepcopy

from capacity_validation import (
    derive_capacity_validation_from_result,
    operating_scenario_from_result,
)
from energy_aggregation import AnnualEnergyAggregationError, aggregate_annual_energy


COMMON_REPORT_SECTIONS = (
    {"id": "project_summary", "title": "Project Summary"},
    {"id": "weather_design_conditions", "title": "Weather & Design Conditions"},
    {"id": "cooling_load_summary", "title": "Cooling Load Summary"},
    {"id": "cooling_system_configuration", "title": "Cooling System Configuration"},
    {"id": "operating_scenario", "title": "Operating Scenario"},
    {"id": "peak_capacity_validation", "title": "Peak Capacity Validation"},
    {"id": "equipment_performance", "title": "Equipment Performance"},
    {"id": "annual_energy_breakdown", "title": "Annual Energy Breakdown"},
    {"id": "pue_summary", "title": "PUE Summary"},
    {"id": "engineering_conclusion", "title": "Engineering Conclusion"},
)

COMMON_REPORT_SECTION_IDS = tuple(section["id"] for section in COMMON_REPORT_SECTIONS)

TOPOLOGY_SPECIFIC_SECTIONS = {
    "acc_gas_engine_cdu": (
        {"id": "acc_cop", "title": "ACC COP"},
        {"id": "acc_power", "title": "ACC Power"},
    ),
    "chiller_dry_cooler": (
        {"id": "chiller_cop", "title": "Chiller COP"},
        {"id": "dry_cooler_performance", "title": "Dry Cooler Performance"},
    ),
}


def list_common_report_sections():
    """Return shared report section metadata."""
    return deepcopy(list(COMMON_REPORT_SECTIONS))


def topology_specific_sections(topology):
    """Return topology-specific report section metadata."""
    return deepcopy(list(TOPOLOGY_SPECIFIC_SECTIONS.get(topology, ())))


def build_report_sections(
    topology,
    solver_result,
    profile=None,
    operating_scenario=None,
    capacity_validation=None,
    annual_energy_breakdown=None,
):
    """Build display-ready common section payloads from existing outputs."""
    result = solver_result if isinstance(solver_result, dict) else {}
    annual = _dict(result.get("annual_results"))
    peak = _dict(result.get("peak_results"))
    project = _dict(result.get("project"))
    context = _dict(result.get("library_context"))
    runtime_assumptions = _dict(context.get("runtime_assumptions"))
    profile_data = profile if isinstance(profile, dict) else {}
    scenario = operating_scenario or operating_scenario_from_result(result)
    validation = capacity_validation or derive_capacity_validation_from_result(topology, result)
    energy = annual_energy_breakdown or _annual_energy(result, annual)
    hourly = result.get("hourly_results") if isinstance(result.get("hourly_results"), list) else []

    common = {
        "project_summary": _section("project_summary", rows=[
            ("Configuration", result.get("configuration_id") or project.get("configuration_id")),
            ("Cooling System Type", profile_data.get("cooling_system_type") or result.get("cooling_system_type")),
            ("Solver Topology", topology),
            ("Report Profile", profile_data.get("profile_id")),
            ("Implementation Status", result.get("implementation_status") or profile_data.get("status")),
        ]),
        "weather_design_conditions": _section("weather_design_conditions", rows=[
            ("Weather Source", peak.get("peak_design_weather_source") or project.get("weather_source")),
            ("EPW Location", project.get("location") or project.get("site_location")),
            ("Simulation Hours", len(hourly) if hourly else None),
            ("Annual Weather Source", project.get("annual_weather_source") or runtime_assumptions.get("weather_source")),
            ("ASHRAE Design DB", peak.get("peak_design_outdoor_dry_bulb_C")),
            ("Peak Dry Bulb", peak.get("peak_design_outdoor_dry_bulb_C")),
            ("Peak Cooling Design Point", peak.get("peak_design_cooling_load_kW")),
        ]),
        "cooling_load_summary": _section("cooling_load_summary", rows=[
            ("Design IT Load", peak.get("peak_design_it_load_kW") or project.get("design_it_load_kW")),
            ("Peak IT Load", peak.get("peak_design_it_load_kW") or _max_hourly(hourly, ("it_load_kW", "IT_load_kW"))),
            ("Annual IT Energy", annual.get("annual_IT_energy_kWh") or energy.get("annual_it_energy_kWh")),
            ("Solar Heat Gain", annual.get("annual_solar_heat_gain_kWh")),
            ("Other Auxiliary Heat Gain", annual.get("annual_other_auxiliary_heat_gain_kWh")),
            ("Peak Cooling Load", peak.get("peak_design_cooling_load_kW")),
            ("Annual Cooling Load", annual.get("annual_cooling_load_kWh")),
        ]),
        "cooling_system_configuration": _section("cooling_system_configuration", rows=[
            ("Cooling System Type", profile_data.get("cooling_system_type") or result.get("cooling_system_type")),
            ("Solver Topology", topology),
            ("Configuration Status", result.get("implementation_status") or profile_data.get("configuration_status")),
        ] + _profile_summary_rows(profile_data.get("summary"))),
        "operating_scenario": _section("operating_scenario", rows=_scenario_rows(scenario)),
        "peak_capacity_validation": _section("peak_capacity_validation", rows=_capacity_rows(validation), status=validation.get("status")),
        "equipment_performance": _section(
            "equipment_performance",
            rows=_equipment_performance_rows(hourly, annual),
        ),
        "annual_energy_breakdown": _section("annual_energy_breakdown", rows=_annual_energy_rows(energy)),
        "pue_summary": _section("pue_summary", rows=[
            ("Annual PUE", annual.get("annual_average_PUE") or energy.get("PUE")),
            ("Annual IT Energy", annual.get("annual_IT_energy_kWh") or energy.get("annual_it_energy_kWh")),
            ("Annual Facility Energy", annual.get("annual_facility_energy_kWh") or energy.get("annual_facility_energy_kWh")),
        ]),
        "engineering_conclusion": _section(
            "engineering_conclusion",
            rows=[("Conclusion", engineering_conclusion(validation))],
            status=_conclusion_status(validation),
        ),
    }
    return {
        "common": [common[section_id] for section_id in COMMON_REPORT_SECTION_IDS],
        "topology_specific": topology_specific_sections(topology),
    }


def engineering_conclusion(capacity_validation):
    """Return deterministic engineering conclusion text."""
    validation = capacity_validation if isinstance(capacity_validation, dict) else {}
    status = str(validation.get("status") or "warning").lower()
    margin_percent = _number(validation.get("capacity_margin_percent"))
    if status == "error":
        return "Available cooling capacity is insufficient for peak design demand."
    if status == "valid" and (margin_percent is None or margin_percent >= 10.0):
        return "Cooling system satisfies peak design cooling demand under selected operating scenario."
    return "Cooling capacity margin is limited under failure scenario."


def _section(section_id, rows=None, status=None):
    title = next(section["title"] for section in COMMON_REPORT_SECTIONS if section["id"] == section_id)
    payload = {"id": section_id, "title": title, "rows": _rows(rows or [])}
    if status:
        payload["status"] = status
    return payload


def _rows(rows):
    formatted = []
    for row in rows:
        if isinstance(row, dict):
            formatted.append(row)
            continue
        label, value = row
        formatted.append({"label": label, "value": value})
    return formatted


def _scenario_rows(scenario):
    return [
        ("Scenario", scenario.get("scenario_name")),
        ("Redundancy Mode", scenario.get("redundancy_mode")),
        ("Required Units", scenario.get("required_units")),
        ("Installed Units", scenario.get("installed_units")),
        ("Active Units", scenario.get("active_units")),
        ("Standby Units", scenario.get("standby_units")),
        ("Failed Units", scenario.get("failed_units")),
        ("Active Chiller Units", scenario.get("active_chiller_units")),
        ("Active Dry Cooler Units", scenario.get("active_dry_cooler_units")),
        ("Active Pumps", scenario.get("active_pump_units")),
    ]


def _capacity_rows(validation):
    return [
        ("Peak Cooling Load", validation.get("peak_cooling_load_kW")),
        ("Installed Capacity", validation.get("installed_capacity_kW")),
        ("Active Capacity", validation.get("active_capacity_kW")),
        ("Capacity Margin", validation.get("capacity_margin_kW")),
        ("Margin Percentage", validation.get("capacity_margin_percent")),
        ("Validation Status", validation.get("status")),
    ]


def _annual_energy_rows(energy):
    components = _dict(energy.get("components"))
    component_value = lambda key: _dict(components.get(key)).get("energy_kWh")
    return [
        ("IT Energy", energy.get("annual_it_energy_kWh")),
        ("ACC", component_value("ACC")),
        ("Chiller", component_value("CHILLER")),
        ("Dry Cooler", component_value("DRY_COOLER")),
        ("CHW Pump", component_value("CHW_PUMP")),
        ("Indoor Equipment", component_value("INDOOR_EQUIPMENT")),
        ("Electrical Loss", component_value("ELECTRICAL_LOSS")),
        ("Facility Energy", energy.get("annual_facility_energy_kWh")),
        ("PUE", energy.get("PUE")),
    ]


def _equipment_performance_rows(hourly, annual=None):
    seen = set()
    rows = []
    for row in hourly:
        if not isinstance(row, dict):
            continue
        for key, value in row.items():
            if not str(key).endswith("_performance_result") or not isinstance(value, dict):
                continue
            equipment_type = value.get("equipment_type")
            equipment_id = value.get("equipment_id")
            unique = (equipment_id, equipment_type)
            if unique in seen:
                continue
            seen.add(unique)
            performance = _dict(value.get("performance"))
            diagnostics = _dict(value.get("diagnostics"))
            rows.append({
                "equipment": equipment_id,
                "equipment_type": equipment_type,
                "type": equipment_type,
                "power_kW": performance.get("power_kW"),
                "COP": performance.get("COP"),
                "load_ratio": performance.get("load_ratio"),
                "capacity_ratio": performance.get("capacity_ratio"),
                "diagnostics": diagnostics,
            })
    if not rows:
        rows.extend(_annual_equipment_performance_rows(annual))
    return rows


def _annual_equipment_performance_rows(annual):
    annual = _dict(annual)
    rows = []
    if any(annual.get(key) is not None for key in (
        "max_acc_power_kW",
        "average_acc_cop",
        "acc_capacity_clamped_hours",
    )):
        rows.append({
            "equipment": "ACC",
            "equipment_type": "ACC",
            "type": "ACC",
            "power_kW": annual.get("max_acc_power_kW"),
            "COP": annual.get("average_acc_cop"),
            "load_ratio": None,
            "capacity_ratio": None,
            "diagnostics": {
                "source": "annual_results",
                "clamped_hours": annual.get("acc_capacity_clamped_hours"),
            },
        })
    return rows


def _profile_summary_rows(summary):
    summary = _dict(summary)
    rows = []
    for key, value in summary.items():
        if value is None:
            continue
        rows.append((_title_from_key(key), value))
    return rows


def _title_from_key(key):
    return str(key).replace("_", " ").title()


def _annual_energy(result, annual):
    if isinstance(result.get("standard_annual_energy"), dict):
        return result["standard_annual_energy"]
    try:
        return aggregate_annual_energy(result)
    except AnnualEnergyAggregationError:
        return {
            "annual_it_energy_kWh": annual.get("annual_IT_energy_kWh"),
            "annual_facility_energy_kWh": annual.get("annual_facility_energy_kWh"),
            "annual_cooling_energy_kWh": annual.get("annual_total_cooling_system_energy_kWh"),
            "components": {},
            "PUE": annual.get("annual_average_PUE"),
            "warnings": [],
        }


def _max_hourly(hourly, keys):
    values = []
    for row in hourly:
        if not isinstance(row, dict):
            continue
        for key in keys:
            value = _number(row.get(key))
            if value is not None:
                values.append(value)
                break
    return max(values) if values else None


def _conclusion_status(validation):
    status = str(_dict(validation).get("status") or "warning").lower()
    if status == "error":
        return "fail"
    if status == "valid":
        return "pass"
    return "warning"


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dict(value):
    return value if isinstance(value, dict) else {}
