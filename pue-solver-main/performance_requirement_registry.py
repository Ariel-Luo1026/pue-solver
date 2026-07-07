"""Performance requirement metadata registry.

Phase 4 performance requirement mapping. This module is intentionally
metadata-only and is not imported by solver.py.
"""

from copy import deepcopy

from equipment_registry import equipment_ids_equivalent
from topology_registry import get_topology, get_topology_equipment


PERFORMANCE_REQUIREMENT_REGISTRY = {
    "it_load_profile": {
        "requirement_id": "it_load_profile",
        "display_name": "IT Load Profile",
        "requirement_category": "load_profile",
        "expected_file_type": ["csv", "xlsx", "json"],
        "typical_independent_variables": ["hour"],
        "typical_dependent_variables": ["IT load", "IT load ratio"],
        "used_by_equipment_ids": ["acc_unit", "chiller", "absorption_chiller"],
        "implementation_status": "implemented",
    },
    "weather_profile": {
        "requirement_id": "weather_profile",
        "display_name": "Weather Profile",
        "requirement_category": "weather_data",
        "expected_file_type": ["csv", "xlsx", "epw", "json"],
        "typical_independent_variables": ["hour"],
        "typical_dependent_variables": [
            "outdoor dry-bulb temperature",
            "outdoor wet-bulb temperature",
            "relative humidity",
        ],
        "used_by_equipment_ids": [
            "acc_unit",
            "dry_cooler",
            "cooling_tower",
            "chiller",
            "absorption_chiller",
        ],
        "implementation_status": "implemented",
    },
    "acc_performance_curve": {
        "requirement_id": "acc_performance_curve",
        "display_name": "ACC Performance Curve",
        "requirement_category": "equipment_performance_curve",
        "expected_file_type": ["xlsx", "csv", "json"],
        "typical_independent_variables": [
            "IT load ratio",
            "outdoor dry-bulb temperature",
        ],
        "typical_dependent_variables": ["ACC power", "ACC hourly factor"],
        "used_by_equipment_ids": ["acc_unit"],
        "implementation_status": "implemented",
    },
    "cdu_performance_curve": {
        "requirement_id": "cdu_performance_curve",
        "display_name": "CDU Performance Curve",
        "requirement_category": "equipment_performance_curve",
        "expected_file_type": ["xlsx", "csv", "json"],
        "typical_independent_variables": ["IT load", "water temperature"],
        "typical_dependent_variables": ["CDU power", "heat transfer rate"],
        "used_by_equipment_ids": ["cdu"],
        "implementation_status": "implemented",
    },
    "pump_power_curve": {
        "requirement_id": "pump_power_curve",
        "display_name": "Pump Power Curve",
        "requirement_category": "equipment_performance_curve",
        "expected_file_type": ["xlsx", "csv", "json"],
        "typical_independent_variables": ["flow rate", "pump head"],
        "typical_dependent_variables": ["pump power"],
        "used_by_equipment_ids": ["pump"],
        "implementation_status": "implemented",
    },
    "terminal_fan_curve": {
        "requirement_id": "terminal_fan_curve",
        "display_name": "MAU / Terminal Fan Curve",
        "requirement_category": "equipment_performance_curve",
        "expected_file_type": ["xlsx", "csv", "json"],
        "typical_independent_variables": ["airflow", "fan speed", "static pressure"],
        "typical_dependent_variables": ["fan power"],
        # MAU is the canonical engineering equipment. terminal_fan is a legacy
        # compatibility alias for the current simplified fan/fixed-power model.
        "used_by_equipment_ids": ["mau", "terminal_fan"],
        "implementation_status": "implemented",
    },
    "electrical_efficiency_curve": {
        "requirement_id": "electrical_efficiency_curve",
        "display_name": "Electrical Efficiency Curve",
        "requirement_category": "electrical_model",
        "expected_file_type": ["xlsx", "csv", "json"],
        "typical_independent_variables": ["electrical load", "load ratio"],
        "typical_dependent_variables": ["electrical loss", "distribution efficiency"],
        "used_by_equipment_ids": ["electrical_distribution"],
        "implementation_status": "implemented",
    },
    "auxiliary_fixed_load": {
        "requirement_id": "auxiliary_fixed_load",
        "display_name": "RTC Fixed / Terminal Load",
        "requirement_category": "fixed_load_model",
        "expected_file_type": ["xlsx", "csv", "json"],
        "typical_independent_variables": ["operating hour", "scenario"],
        "typical_dependent_variables": ["auxiliary power", "auxiliary energy"],
        # RTC is the canonical engineering equipment. auxiliary_load is only a
        # backward-compatible alias, not an exact engineering definition.
        "used_by_equipment_ids": ["rtc", "auxiliary_load"],
        "implementation_status": "implemented",
    },
    "gas_engine_curve": {
        "requirement_id": "gas_engine_curve",
        "display_name": "Gas Engine Curve",
        "requirement_category": "equipment_performance_curve",
        "expected_file_type": ["xlsx", "csv", "json"],
        "typical_independent_variables": ["engine load ratio"],
        "typical_dependent_variables": ["engine efficiency", "fuel consumption"],
        "used_by_equipment_ids": ["gas_engine"],
        "implementation_status": "implemented",
    },
    "chiller_cop_surface": {
        "requirement_id": "chiller_cop_surface",
        "display_name": "Chiller COP Surface",
        "requirement_category": "equipment_performance_curve",
        "expected_file_type": ["xlsx", "csv", "json"],
        "typical_independent_variables": [
            "cooling load",
            "leaving chilled water temperature",
            "entering condenser water temperature",
        ],
        "typical_dependent_variables": ["chiller COP", "chiller power"],
        "used_by_equipment_ids": ["chiller"],
        "implementation_status": "placeholder",
    },
    "dry_cooler_fan_curve": {
        "requirement_id": "dry_cooler_fan_curve",
        "display_name": "Dry Cooler Fan Curve",
        "requirement_category": "equipment_performance_curve",
        "expected_file_type": ["xlsx", "csv", "json"],
        "typical_independent_variables": [
            "heat rejection load",
            "outdoor dry-bulb temperature",
            "fan speed",
        ],
        "typical_dependent_variables": ["dry-cooler fan power", "heat rejection capacity"],
        "used_by_equipment_ids": ["dry_cooler"],
        "implementation_status": "placeholder",
    },
    "cooling_tower_performance_curve": {
        "requirement_id": "cooling_tower_performance_curve",
        "display_name": "Cooling Tower Performance Curve",
        "requirement_category": "equipment_performance_curve",
        "expected_file_type": ["xlsx", "csv", "json"],
        "typical_independent_variables": [
            "heat rejection load",
            "outdoor wet-bulb temperature",
            "cooling water temperature",
        ],
        "typical_dependent_variables": ["cooling tower fan power", "heat rejection capacity"],
        "used_by_equipment_ids": ["cooling_tower"],
        "implementation_status": "placeholder",
    },
    "absorption_chiller_performance_curve": {
        "requirement_id": "absorption_chiller_performance_curve",
        "display_name": "Absorption Chiller Performance Curve",
        "requirement_category": "equipment_performance_curve",
        "expected_file_type": ["xlsx", "csv", "json"],
        "typical_independent_variables": [
            "cooling load",
            "hot water input",
            "condenser water temperature",
        ],
        "typical_dependent_variables": ["ABS COP", "thermal energy use"],
        "used_by_equipment_ids": ["absorption_chiller"],
        "implementation_status": "placeholder",
    },
    "heat_exchanger_curve": {
        "requirement_id": "heat_exchanger_curve",
        "display_name": "Engine Radiator Curve",
        "requirement_category": "equipment_performance_curve",
        "expected_file_type": ["xlsx", "csv", "json"],
        "typical_independent_variables": [
            "hot-side inlet temperature",
            "cold-side inlet temperature",
            "flow rates",
        ],
        "typical_dependent_variables": ["heat transfer rate", "leaving fluid temperatures"],
        # Engine Radiator is canonical. heat_exchanger is only a compatibility
        # alias for older topology definitions.
        "used_by_equipment_ids": ["engine_radiator", "heat_exchanger"],
        "implementation_status": "placeholder",
    },
}


PERFORMANCE_CURVE_LABEL_TO_REQUIREMENT_ID = {
    "IT load profile": "it_load_profile",
    "weather profile": "weather_profile",
    "ACC performance curve": "acc_performance_curve",
    "CDU performance curve": "cdu_performance_curve",
    "Pump power curve": "pump_power_curve",
    "Fan power curve": "terminal_fan_curve",
    "Electrical loss model": "electrical_efficiency_curve",
    "Auxiliary load profile": "auxiliary_fixed_load",
    "Engine efficiency curve": "gas_engine_curve",
    "Chiller COP surface": "chiller_cop_surface",
    "Dry-cooler performance curve": "dry_cooler_fan_curve",
    "Cooling-tower performance curve": "cooling_tower_performance_curve",
    "ABS performance / COP curve": "absorption_chiller_performance_curve",
    "Heat exchanger performance curve": "heat_exchanger_curve",
}


def get_performance_requirement(requirement_id):
    """Return requirement metadata by requirement ID, or None if unknown."""
    requirement = PERFORMANCE_REQUIREMENT_REGISTRY.get(requirement_id)
    return deepcopy(requirement) if requirement else None


def list_performance_requirements():
    """Return all registered performance requirement records."""
    return [deepcopy(requirement) for requirement in PERFORMANCE_REQUIREMENT_REGISTRY.values()]


def list_requirements_by_equipment(equipment_id):
    """Return requirement records that declare usage by an equipment ID."""
    return [
        deepcopy(requirement)
        for requirement in PERFORMANCE_REQUIREMENT_REGISTRY.values()
        if any(equipment_ids_equivalent(equipment_id, used_id) for used_id in requirement["used_by_equipment_ids"])
    ]


def list_requirements_by_status(status):
    """Return requirement records matching an implementation status."""
    return [
        deepcopy(requirement)
        for requirement in PERFORMANCE_REQUIREMENT_REGISTRY.values()
        if requirement["implementation_status"] == status
    ]


def _requirement_for_curve_label(curve_label):
    requirement_id = PERFORMANCE_CURVE_LABEL_TO_REQUIREMENT_ID.get(curve_label)
    if requirement_id is None:
        raise KeyError(f"No performance requirement mapping for curve/data type: {curve_label!r}")
    return get_performance_requirement(requirement_id)


def get_topology_performance_requirements(topology_id):
    """Return unique performance requirement records for a topology."""
    topology = get_topology(topology_id)
    if topology is None:
        raise KeyError(f"Unknown topology_id: {topology_id}")

    curve_labels = list(topology.get("required_performance_curves", []))
    for equipment in get_topology_equipment(topology_id):
        curve_labels.extend(equipment.get("required_performance_curves", []))

    requirements = []
    seen_requirement_ids = set()
    for curve_label in curve_labels:
        requirement = _requirement_for_curve_label(curve_label)
        requirement_id = requirement["requirement_id"]
        if requirement_id not in seen_requirement_ids:
            requirements.append(requirement)
            seen_requirement_ids.add(requirement_id)
    return requirements
