"""Cooling-system equipment metadata registry.

Phase 2 equipment framework skeleton. This module is intentionally
metadata-only and is not imported by solver.py.
"""

from copy import deepcopy


EQUIPMENT_REGISTRY = {
    "acc_unit": {
        "equipment_id": "acc_unit",
        "display_name": "ACC Unit",
        "equipment_category": "heat_rejection",
        "energy_type": ["electricity"],
        "typical_inputs": [
            "IT load ratio",
            "outdoor dry-bulb temperature",
            "unit capacity",
        ],
        "typical_outputs": [
            "ACC power",
            "heat rejection capacity",
        ],
        "required_performance_curves": ["ACC performance curve"],
        "calculation_role": "primary cooling / heat rejection equipment for ACC topology",
        "implementation_status": "implemented",
    },
    "cdu": {
        "equipment_id": "cdu",
        "display_name": "CDU",
        "equipment_category": "indoor_heat_transfer",
        "energy_type": ["electricity", "chilled water"],
        "typical_inputs": [
            "IT load",
            "supply water temperature",
            "return water temperature",
        ],
        "typical_outputs": [
            "indoor equipment power",
            "heat transfer to chilled water loop",
        ],
        "required_performance_curves": ["CDU performance curve"],
        "calculation_role": "indoor-side heat transfer equipment",
        "implementation_status": "implemented",
    },
    "pump": {
        "equipment_id": "pump",
        "display_name": "Pump",
        "equipment_category": "fluid_movement",
        "energy_type": ["electricity"],
        "typical_inputs": [
            "flow rate",
            "pump head",
            "pump efficiency",
        ],
        "typical_outputs": [
            "pump power",
            "fluid circulation",
        ],
        "required_performance_curves": ["Pump power curve"],
        "calculation_role": "fluid circulation power for cooling loops",
        "implementation_status": "implemented",
    },
    "terminal_fan": {
        "equipment_id": "terminal_fan",
        "display_name": "Terminal Fan",
        "equipment_category": "air_movement",
        "energy_type": ["electricity"],
        "typical_inputs": [
            "airflow",
            "fan speed",
            "static pressure",
        ],
        "typical_outputs": [
            "fan power",
            "air circulation",
        ],
        "required_performance_curves": ["Fan power curve"],
        "calculation_role": "white-space air movement support load",
        "implementation_status": "implemented",
    },
    "electrical_distribution": {
        "equipment_id": "electrical_distribution",
        "display_name": "Electrical Distribution",
        "equipment_category": "electrical",
        "energy_type": ["electricity"],
        "typical_inputs": [
            "IT power",
            "cooling equipment power",
            "electrical loss factor",
        ],
        "typical_outputs": [
            "electrical distribution losses",
            "facility power",
        ],
        "required_performance_curves": ["Electrical loss model"],
        "calculation_role": "electrical-loss accounting for facility power",
        "implementation_status": "implemented",
    },
    "auxiliary_load": {
        "equipment_id": "auxiliary_load",
        "display_name": "Auxiliary Load",
        "equipment_category": "auxiliary",
        "energy_type": ["electricity"],
        "typical_inputs": [
            "auxiliary load allowance",
            "operating hours",
            "scenario factor",
        ],
        "typical_outputs": [
            "auxiliary power",
            "auxiliary energy",
        ],
        "required_performance_curves": ["Auxiliary load profile"],
        "calculation_role": "non-primary support load included in facility energy",
        "implementation_status": "implemented",
    },
    "chiller": {
        "equipment_id": "chiller",
        "display_name": "Chiller",
        "equipment_category": "primary_cooling",
        "energy_type": ["electricity"],
        "typical_inputs": [
            "cooling load",
            "leaving chilled water temperature",
            "entering condenser water temperature",
        ],
        "typical_outputs": [
            "chiller power",
            "cooling capacity",
            "condenser heat rejection",
        ],
        "required_performance_curves": ["Chiller COP surface"],
        "calculation_role": "primary cooling equipment for chiller topologies",
        "implementation_status": "placeholder",
    },
    "dry_cooler": {
        "equipment_id": "dry_cooler",
        "display_name": "Dry Cooler",
        "equipment_category": "heat_rejection",
        "energy_type": ["electricity"],
        "typical_inputs": [
            "condenser loop heat rejection",
            "outdoor dry-bulb temperature",
            "fan speed",
        ],
        "typical_outputs": [
            "dry-cooler power",
            "heat rejection capacity",
        ],
        "required_performance_curves": ["Dry-cooler performance curve"],
        "calculation_role": "heat rejection equipment for dry-cooler topologies",
        "implementation_status": "placeholder",
    },
    "cooling_tower": {
        "equipment_id": "cooling_tower",
        "display_name": "Cooling Tower",
        "equipment_category": "heat_rejection",
        "energy_type": ["electricity", "water"],
        "typical_inputs": [
            "condenser loop heat rejection",
            "outdoor wet-bulb temperature",
            "cooling water temperature",
        ],
        "typical_outputs": [
            "cooling tower fan power",
            "heat rejection capacity",
            "makeup water demand",
        ],
        "required_performance_curves": ["Cooling-tower performance curve"],
        "calculation_role": "heat rejection equipment for cooling-tower topologies",
        "implementation_status": "placeholder",
    },
    "absorption_chiller": {
        "equipment_id": "absorption_chiller",
        "display_name": "Absorption Chiller",
        "equipment_category": "primary_cooling",
        "energy_type": ["thermal", "electricity"],
        "typical_inputs": [
            "cooling load",
            "hot water input",
            "condenser water temperature",
        ],
        "typical_outputs": [
            "cooling capacity",
            "thermal energy use",
            "auxiliary electric power",
        ],
        "required_performance_curves": ["ABS performance / COP curve"],
        "calculation_role": "primary cooling equipment for ABS topologies",
        "implementation_status": "placeholder",
    },
    "gas_engine": {
        "equipment_id": "gas_engine",
        "display_name": "Gas Engine",
        "equipment_category": "power_generation",
        "energy_type": ["natural gas", "electricity", "thermal"],
        "typical_inputs": [
            "electrical load",
            "engine load ratio",
            "fuel heating value",
        ],
        "typical_outputs": [
            "engine electrical output",
            "fuel consumption",
            "engine radiator heat",
        ],
        "required_performance_curves": ["Engine efficiency curve"],
        "calculation_role": "on-site power source option for cooling-system configurations",
        "implementation_status": "implemented",
    },
    "heat_exchanger": {
        "equipment_id": "heat_exchanger",
        "display_name": "Heat Exchanger",
        "equipment_category": "heat_transfer",
        "energy_type": ["thermal"],
        "typical_inputs": [
            "hot-side inlet temperature",
            "cold-side inlet temperature",
            "flow rates",
        ],
        "typical_outputs": [
            "heat transfer rate",
            "leaving fluid temperatures",
        ],
        "required_performance_curves": ["Heat exchanger performance curve"],
        "calculation_role": "thermal transfer equipment for future hybrid topologies",
        "implementation_status": "placeholder",
    },
}


def get_equipment(equipment_id):
    """Return equipment metadata by equipment ID, or None if it is unknown."""
    equipment = EQUIPMENT_REGISTRY.get(equipment_id)
    return deepcopy(equipment) if equipment else None


def list_equipment():
    """Return all registered equipment metadata records."""
    return [deepcopy(equipment) for equipment in EQUIPMENT_REGISTRY.values()]


def list_equipment_by_category(category):
    """Return equipment records matching an equipment category."""
    return [
        deepcopy(equipment)
        for equipment in EQUIPMENT_REGISTRY.values()
        if equipment["equipment_category"] == category
    ]


def list_equipment_by_status(status):
    """Return equipment records matching an implementation status."""
    return [
        deepcopy(equipment)
        for equipment in EQUIPMENT_REGISTRY.values()
        if equipment["implementation_status"] == status
    ]
