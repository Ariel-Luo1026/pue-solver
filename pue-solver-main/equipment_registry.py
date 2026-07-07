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
    "mau": {
        "equipment_id": "mau",
        "display_name": "MAU",
        "equipment_category": "air_movement",
        "category": "air_movement",
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
        "calculation_role": "make-up air unit fan or fixed-power support load in the current simplified model",
        "implementation_status": "implemented",
        "status": "implemented",
        "canonical_name": "mau",
        "aliases": ["terminal_fan"],
        "engineering_description": (
            "Make-Up Air Unit; may include fan, filter, damper and air-side "
            "conditioning equipment; currently modeled as fan or fixed power where applicable."
        ),
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
    "rtc": {
        "equipment_id": "rtc",
        "display_name": "RTC",
        "equipment_category": "auxiliary",
        "category": "auxiliary",
        "energy_type": ["electricity"],
        "typical_inputs": [
            "RTC terminal load allowance",
            "operating hours",
            "scenario factor",
        ],
        "typical_outputs": [
            "auxiliary power",
            "auxiliary energy",
        ],
        "required_performance_curves": ["Auxiliary load profile"],
        "calculation_role": "room terminal cooling / temperature control load represented by fixed or fan power",
        "implementation_status": "implemented",
        "status": "implemented",
        "canonical_name": "rtc",
        "aliases": ["auxiliary_load"],
        "engineering_description": (
            "Room terminal cooling / room temperature control equipment; currently "
            "modeled mainly through RTC fan power or terminal cooling behavior."
        ),
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
    "engine_radiator": {
        "equipment_id": "engine_radiator",
        "display_name": "Engine Radiator",
        "equipment_category": "heat_transfer",
        "category": "heat_transfer",
        "energy_type": ["thermal"],
        "typical_inputs": [
            "engine waste heat",
            "radiator fan speed",
            "ambient temperature",
        ],
        "typical_outputs": [
            "engine radiator power",
            "engine heat rejection capacity",
        ],
        "required_performance_curves": ["Heat exchanger performance curve"],
        "calculation_role": "gas engine radiator / radiator fan / engine heat rejection equipment",
        "implementation_status": "placeholder",
        "status": "placeholder",
        "canonical_name": "engine_radiator",
        "aliases": ["heat_exchanger"],
        "engineering_description": (
            "Gas engine radiator / radiator fan / engine heat rejection equipment; "
            "not a generic heat exchanger."
        ),
    },
}


# Compatibility aliases only:
# - auxiliary_load resolves to rtc, but RTC is not a generic auxiliary load.
# - terminal_fan resolves to mau, but MAU is not the same engineering device as RTC.
# - heat_exchanger resolves to engine_radiator, but an engine radiator is not a generic plate heat exchanger.
EQUIPMENT_ALIASES = {
    alias: equipment_id
    for equipment_id, equipment in EQUIPMENT_REGISTRY.items()
    for alias in equipment.get("aliases", [])
}


for _equipment_id, _equipment in EQUIPMENT_REGISTRY.items():
    _equipment.setdefault("canonical_name", _equipment_id)
    _equipment.setdefault("aliases", [])
    _equipment.setdefault("category", _equipment.get("equipment_category"))
    _equipment.setdefault("status", _equipment.get("implementation_status"))
    _equipment.setdefault("engineering_description", _equipment.get("calculation_role", ""))


def canonicalize_equipment_id(equipment_id):
    """Return the engineering canonical equipment ID for an ID or legacy alias."""
    if equipment_id is None:
        return None
    value = str(equipment_id)
    return EQUIPMENT_ALIASES.get(value, value)


def get_equipment_aliases(equipment_id):
    """Return compatibility aliases for an equipment ID."""
    canonical_id = canonicalize_equipment_id(equipment_id)
    equipment = EQUIPMENT_REGISTRY.get(canonical_id)
    return list(equipment.get("aliases", [])) if equipment else []


def is_equipment_alias(equipment_id):
    """Return True when equipment_id is a legacy compatibility alias."""
    return str(equipment_id) in EQUIPMENT_ALIASES


def equipment_ids_equivalent(a, b):
    """Return True when two equipment IDs resolve to the same canonical ID."""
    return canonicalize_equipment_id(a) == canonicalize_equipment_id(b)


def get_equipment(equipment_id):
    """Return equipment metadata by equipment ID, or None if it is unknown."""
    equipment = EQUIPMENT_REGISTRY.get(canonicalize_equipment_id(equipment_id))
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
