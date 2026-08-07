"""Topology report profile metadata.

This module only describes which solver result fields belong to each report
profile. It does not calculate or transform solver outputs.
"""

from copy import deepcopy

from report_sections import COMMON_REPORT_SECTIONS, COMMON_REPORT_SECTION_IDS, topology_specific_sections


COMMON_REPORT_SECTION_TITLES = [section["title"] for section in COMMON_REPORT_SECTIONS]


ACC_GAS_ENGINE_CDU_FIELDS = [
    {
        "key": "annual_average_PUE",
        "label": "Annual PUE",
        "category": "summary",
    },
    {
        "key": "annual_IT_energy_kWh",
        "label": "IT Energy",
        "category": "summary",
    },
    {
        "key": "annual_facility_energy_kWh",
        "label": "Facility Energy",
        "category": "summary",
    },
    {
        "key": "annual_total_cooling_system_energy_kWh",
        "label": "Cooling Energy",
        "category": "cooling",
    },
    {
        "key": "annual_acc_energy_kWh",
        "label": "ACC Energy",
        "category": "cooling",
    },
    {
        "key": "annual_pump_energy_kWh",
        "label": "Pump Energy",
        "category": "cooling",
    },
    {
        "key": "annual_white_space_equipment_energy_kWh",
        "label": "Indoor Equipment Energy",
        "category": "indoor",
        "fallback_keys": ["annual_indoor_equipment_energy_kWh"],
    },
    {
        "key": "annual_engine_energy_kWh",
        "label": "Engine Energy",
        "category": "engine",
    },
    {
        "key": "annual_engine_radiator_energy_kWh",
        "label": "Engine/Radiator Energy",
        "category": "engine",
    },
    {
        "key": "annual_electrical_loss_kWh",
        "label": "Electrical Losses",
        "category": "electrical",
        "fallback_keys": [
            "annual_it_electrical_loss_kWh",
            "annual_mep_electrical_loss_kWh",
        ],
    },
]


GENERIC_PUE_FIELDS = [
    {
        "key": "annual_average_PUE",
        "label": "Annual PUE",
        "category": "summary",
    },
    {
        "key": "annual_IT_energy_kWh",
        "label": "IT Energy",
        "category": "summary",
    },
    {
        "key": "annual_facility_energy_kWh",
        "label": "Facility Energy",
        "category": "summary",
    },
]

CHILLER_DRY_COOLER_FIELDS = GENERIC_PUE_FIELDS + [
    {
        "key": "annual_chiller_energy_kWh",
        "label": "Chiller Energy",
        "category": "cooling",
    },
    {
        "key": "annual_dry_cooler_energy_kWh",
        "label": "Dry Cooler Energy",
        "category": "cooling",
    },
    {
        "key": "annual_pump_energy_kWh",
        "label": "Pump Energy (Legacy CHW)",
        "category": "cooling",
    },
    {
        "key": "annual_chw_pump_energy_kWh",
        "label": "CHW Pump Energy",
        "category": "cooling",
    },
    {
        "key": "annual_cw_pump_energy_kWh",
        "label": "CW Pump Energy",
        "category": "cooling",
    },
    {
        "key": "annual_electrical_loss_kWh",
        "label": "Electrical Losses",
        "category": "electrical",
    },
    {
        "key": "average_chiller_COP",
        "label": "Average Chiller COP",
        "category": "performance",
    },
    {
        "key": "min_chiller_COP",
        "label": "Minimum Chiller COP",
        "category": "performance",
    },
    {
        "key": "max_chiller_COP",
        "label": "Maximum Chiller COP",
        "category": "performance",
    },
    {
        "key": "dry_cooler_capacity_kW",
        "label": "Dry Cooler Capacity",
        "category": "cooling_system_summary",
    },
    {
        "key": "configuration_status",
        "label": "Configuration Status",
        "category": "cooling_system_summary",
    },
]


REPORT_PROFILE_REGISTRY = {
    "acc_gas_engine_cdu": {
        "profile_id": "acc_gas_engine_cdu",
        "display_name": "ACC Gas Engine CDU Report",
        "cooling_system_type": "ACC + Gas Engine + CDU",
        "topology": "acc_gas_engine_cdu",
        "status": "implemented",
        "simulation_engine": "ACC V2 Configuration Library Engine",
        "performance_model": "ACC V2 Direct Mode: Configuration Library Solver_Curve hourly simulation",
        "simulation_basis": "8760-hour Annual Dynamic Simulation",
        "common_sections": list(COMMON_REPORT_SECTION_IDS),
        "topology_specific_sections": topology_specific_sections("acc_gas_engine_cdu"),
        "fields": ACC_GAS_ENGINE_CDU_FIELDS,
    },
    "chiller_dry_cooler": {
        "profile_id": "chiller_dry_cooler",
        "display_name": "Chiller + Dry Cooler Report",
        "cooling_system_type": "Chiller + Dry Cooler",
        "topology": "chiller_dry_cooler",
        "configuration_status": "Implemented",
        "status": "implemented",
        "simulation_engine": "Topology Dispatcher Runtime",
        "performance_model": "Configuration Library Solver_Curve hourly simulation",
        "simulation_basis": "8760-hour Annual Dynamic Simulation",
        "common_sections": list(COMMON_REPORT_SECTION_IDS),
        "topology_specific_sections": topology_specific_sections("chiller_dry_cooler"),
        "sections": COMMON_REPORT_SECTION_TITLES + [
            "Cooling System Summary",
            "Standard Annual Energy Breakdown",
            "Performance",
        ],
        "fields": CHILLER_DRY_COOLER_FIELDS,
    },
    "water_cooled_chiller": {
        "profile_id": "water_cooled_chiller",
        "display_name": "Water-Cooled Chiller Report",
        "cooling_system_type": "Water-Cooled Chiller",
        "topology": "water_cooled_chiller",
        "status": "metadata_only",
        "common_sections": list(COMMON_REPORT_SECTION_IDS),
        "topology_specific_sections": topology_specific_sections("water_cooled_chiller"),
        "fields": GENERIC_PUE_FIELDS,
    },
    "liquid_cooling": {
        "profile_id": "liquid_cooling",
        "display_name": "Liquid Cooling Report",
        "cooling_system_type": "Liquid Cooling",
        "topology": "liquid_cooling",
        "status": "metadata_only",
        "common_sections": list(COMMON_REPORT_SECTION_IDS),
        "topology_specific_sections": topology_specific_sections("liquid_cooling"),
        "fields": GENERIC_PUE_FIELDS,
    },
}


GENERIC_REPORT_PROFILE = {
    "profile_id": "generic_pue",
    "display_name": "Generic PUE Summary",
    "cooling_system_type": "Unknown Cooling System",
    "topology": "unknown",
    "status": "generic",
    "simulation_engine": "Topology Dispatcher Runtime",
    "performance_model": "Standardized hourly simulation",
    "simulation_basis": "Annual Dynamic Simulation",
    "common_sections": list(COMMON_REPORT_SECTION_IDS),
    "topology_specific_sections": [],
    "fields": GENERIC_PUE_FIELDS,
}


def get_report_profile(profile_id):
    """Return a report profile by profile ID."""
    profile = REPORT_PROFILE_REGISTRY.get(profile_id)
    return deepcopy(profile) if profile else None


def get_report_profile_for_topology(topology):
    """Return the report profile registered for a solver topology."""
    for profile in REPORT_PROFILE_REGISTRY.values():
        if profile.get("topology") == topology:
            return deepcopy(profile)
    return None


def get_generic_report_profile(topology=None):
    """Return the generic summary profile for unknown or unsupported topologies."""
    profile = deepcopy(GENERIC_REPORT_PROFILE)
    if topology:
        profile["topology"] = topology
    return profile


def list_report_profiles():
    """Return all registered report profiles."""
    return [deepcopy(profile) for profile in REPORT_PROFILE_REGISTRY.values()]
