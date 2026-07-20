"""Topology report profile metadata.

This module only describes which solver result fields belong to each report
profile. It does not calculate or transform solver outputs.
"""

from copy import deepcopy


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


REPORT_PROFILE_REGISTRY = {
    "acc_gas_engine_cdu": {
        "profile_id": "acc_gas_engine_cdu",
        "display_name": "ACC Gas Engine CDU Report",
        "cooling_system_type": "ACC + Gas Engine + CDU",
        "topology": "acc_gas_engine_cdu",
        "status": "implemented",
        "fields": ACC_GAS_ENGINE_CDU_FIELDS,
    },
    "chiller_dry_cooler": {
        "profile_id": "chiller_dry_cooler",
        "display_name": "Chiller + Dry Cooler Report",
        "cooling_system_type": "Chiller + Dry Cooler",
        "topology": "chiller_dry_cooler",
        "configuration_status": "Framework Ready / Data Missing",
        "status": "framework_ready_data_missing",
        "fields": GENERIC_PUE_FIELDS,
    },
    "water_cooled_chiller": {
        "profile_id": "water_cooled_chiller",
        "display_name": "Water-Cooled Chiller Report",
        "cooling_system_type": "Water-Cooled Chiller",
        "topology": "water_cooled_chiller",
        "status": "metadata_only",
        "fields": GENERIC_PUE_FIELDS,
    },
    "liquid_cooling": {
        "profile_id": "liquid_cooling",
        "display_name": "Liquid Cooling Report",
        "cooling_system_type": "Liquid Cooling",
        "topology": "liquid_cooling",
        "status": "metadata_only",
        "fields": GENERIC_PUE_FIELDS,
    },
}


GENERIC_REPORT_PROFILE = {
    "profile_id": "generic_pue",
    "display_name": "Generic PUE Summary",
    "cooling_system_type": "Unknown Cooling System",
    "topology": "unknown",
    "status": "generic",
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
