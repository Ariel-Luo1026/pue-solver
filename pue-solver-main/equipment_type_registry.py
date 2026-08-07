"""Standard Configuration Library equipment type registry.

The registry is metadata only. It describes supported equipment categories and
their expected curve metadata without implementing any new calculations.
"""

from copy import deepcopy


EQUIPMENT_TYPE_REGISTRY = {
    "ACC": {
        "equipment_type": "ACC",
        "display_name": "Air-Cooled Chiller / ACC",
        "expected_curve_types": ["ambient_capacity_power"],
        "status": "implemented",
    },
    "CHW_PUMP": {
        "equipment_type": "CHW_PUMP",
        "display_name": "Chilled Water Pump",
        "expected_curve_types": ["load_ratio_power"],
        "status": "implemented",
    },
    "CW_PUMP": {
        "equipment_type": "CW_PUMP",
        "display_name": "Cooling Water Pump",
        "expected_curve_types": ["load_ratio_power"],
        "status": "implemented",
    },
    "CDU": {
        "equipment_type": "CDU",
        "display_name": "Cooling Distribution Unit",
        "expected_curve_types": ["load_ratio_power"],
        "status": "implemented",
    },
    "RTC": {
        "equipment_type": "RTC",
        "display_name": "Rear Door / Row Thermal Cooling",
        "expected_curve_types": ["load_ratio_power"],
        "status": "implemented",
    },
    "MAU": {
        "equipment_type": "MAU",
        "display_name": "Makeup Air Unit",
        "expected_curve_types": ["load_ratio_power"],
        "status": "implemented",
    },
    "ENGINE": {
        "equipment_type": "ENGINE",
        "display_name": "Gas Engine",
        "expected_curve_types": ["load_ratio_engine_output"],
        "status": "implemented",
    },
    "ENGINE_RADIATOR": {
        "equipment_type": "ENGINE_RADIATOR",
        "display_name": "Engine Radiator",
        "expected_curve_types": ["load_ratio_power"],
        "status": "implemented",
    },
    "ELECTRICAL_DISTRIBUTION": {
        "equipment_type": "ELECTRICAL_DISTRIBUTION",
        "display_name": "Electrical Distribution",
        "expected_curve_types": ["electrical_path_efficiency"],
        "status": "implemented",
    },
    "CHILLER": {
        "equipment_type": "CHILLER",
        "display_name": "Chiller",
        "expected_curve_types": ["load_ratio_power", "cop_curve"],
        "status": "framework_only",
    },
    "COOLING_TOWER": {
        "equipment_type": "COOLING_TOWER",
        "display_name": "Cooling Tower",
        "expected_curve_types": ["load_ratio_power"],
        "status": "framework_only",
    },
    "DRY_COOLER": {
        "equipment_type": "DRY_COOLER",
        "display_name": "Dry Cooler",
        "expected_curve_types": ["ambient_capacity_power", "outdoor_temperature_power", "load_ratio_power"],
        "status": "framework_only",
    },
    "CONDENSER_PUMP": {
        "equipment_type": "CONDENSER_PUMP",
        "display_name": "Condenser Water Pump",
        "expected_curve_types": ["load_ratio_power"],
        "status": "framework_only",
    },
    "LIQUID_COOLING_CDU": {
        "equipment_type": "LIQUID_COOLING_CDU",
        "display_name": "Liquid Cooling CDU",
        "expected_curve_types": ["load_ratio_power"],
        "status": "framework_only",
    },
    "ABSORPTION_CHILLER": {
        "equipment_type": "ABSORPTION_CHILLER",
        "display_name": "Absorption Chiller",
        "expected_curve_types": ["load_ratio_power", "cop_curve"],
        "status": "framework_only",
    },
}


EQUIPMENT_TYPE_ALIASES = {
    "AIR COOLED CHILLER": "ACC",
    "AIR-COOLED CHILLER": "ACC",
    "ACC": "ACC",
    "CHW PUMP": "CHW_PUMP",
    "CHILLED WATER PUMP": "CHW_PUMP",
    "CHW_PUMP": "CHW_PUMP",
    "CW PUMP": "CW_PUMP",
    "COOLING WATER PUMP": "CW_PUMP",
    "CW_PUMP": "CW_PUMP",
    "GAS ENGINE": "ENGINE",
    "ENGINE": "ENGINE",
    "ENGINE RADIATOR": "ENGINE_RADIATOR",
    "ENGINE_RADIATOR": "ENGINE_RADIATOR",
    "ELECTRICAL DISTRIBUTION": "ELECTRICAL_DISTRIBUTION",
    "ELECTRICAL_DISTRIBUTION": "ELECTRICAL_DISTRIBUTION",
}


def normalize_equipment_type(equipment_type):
    """Return the canonical equipment type key for registry lookup."""
    text = str(equipment_type or "").strip()
    if not text:
        return ""
    normalized = "_".join(text.replace("-", " ").split()).upper()
    return EQUIPMENT_TYPE_ALIASES.get(text.upper(), EQUIPMENT_TYPE_ALIASES.get(normalized, normalized))


def get_equipment_type(equipment_type):
    """Return registered equipment type metadata."""
    key = normalize_equipment_type(equipment_type)
    item = EQUIPMENT_TYPE_REGISTRY.get(key)
    return deepcopy(item) if item else None


def list_equipment_types():
    """Return all registered equipment type records."""
    return [deepcopy(item) for item in EQUIPMENT_TYPE_REGISTRY.values()]


def is_curve_type_supported(equipment_type, curve_type):
    """Return whether curve_type is expected for equipment_type."""
    item = get_equipment_type(equipment_type)
    if not item:
        return False
    return curve_type in item.get("expected_curve_types", [])
