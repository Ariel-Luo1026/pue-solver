"""Generic equipment curve schema registry for Configuration Library metadata."""

from copy import deepcopy


EQUIPMENT_CURVE_REGISTRY = {
    "ACC": {
        "ambient_capacity_power": {
            "curve_type": "ambient_capacity_power",
            "curve_schema": "ambient_capacity_power_2D",
            "display_name": "Ambient Capacity / Power Map",
        },
        "ambient_capacity_power_2D": {
            "curve_type": "ambient_capacity_power_2D",
            "curve_schema": "ambient_capacity_power_2D",
            "display_name": "Ambient Capacity / Power Map",
        },
    },
    "CHILLER": {
        "cop_curve": {
            "curve_type": "cop_curve",
            "curve_schema": "cop_map_2D",
            "display_name": "Chiller COP Map",
        },
        "cop_map_2D": {
            "curve_type": "cop_map_2D",
            "curve_schema": "cop_map_2D",
            "display_name": "Chiller COP Map",
        },
    },
    "DRY_COOLER": {
        "ambient_capacity_power": {
            "curve_type": "ambient_capacity_power",
            "curve_schema": "ambient_capacity_power_1D",
            "display_name": "Ambient Capacity / Power Curve",
        },
        "ambient_capacity_power_1D": {
            "curve_type": "ambient_capacity_power_1D",
            "curve_schema": "ambient_capacity_power_1D",
            "display_name": "Ambient Capacity / Power Curve",
        },
    },
    "CHW_PUMP": {
        "load_ratio_power": {
            "curve_type": "load_ratio_power",
            "curve_schema": "load_ratio_power_1D",
            "display_name": "Load Ratio / Power Curve",
        },
        "load_ratio_power_1D": {
            "curve_type": "load_ratio_power_1D",
            "curve_schema": "load_ratio_power_1D",
            "display_name": "Load Ratio / Power Curve",
        },
    },
    "CDU": {
        "load_ratio_power": {
            "curve_type": "load_ratio_power",
            "curve_schema": "load_ratio_power_1D",
            "display_name": "Load Ratio / Power Curve",
        },
        "load_ratio_power_1D": {
            "curve_type": "load_ratio_power_1D",
            "curve_schema": "load_ratio_power_1D",
            "display_name": "Load Ratio / Power Curve",
        },
    },
    "RTC": {
        "load_ratio_power": {
            "curve_type": "load_ratio_power",
            "curve_schema": "load_ratio_power_1D",
            "display_name": "Load Ratio / Power Curve",
        },
        "load_ratio_power_1D": {
            "curve_type": "load_ratio_power_1D",
            "curve_schema": "load_ratio_power_1D",
            "display_name": "Load Ratio / Power Curve",
        },
    },
    "MAU": {
        "load_ratio_power": {
            "curve_type": "load_ratio_power",
            "curve_schema": "load_ratio_power_1D",
            "display_name": "Load Ratio / Power Curve",
        },
        "load_ratio_power_1D": {
            "curve_type": "load_ratio_power_1D",
            "curve_schema": "load_ratio_power_1D",
            "display_name": "Load Ratio / Power Curve",
        },
    },
    "ENGINE": {
        "load_ratio_engine_output": {
            "curve_type": "load_ratio_engine_output",
            "curve_schema": "load_ratio_engine_output_1D",
            "display_name": "Load Ratio / Engine Output Curve",
        },
    },
    "ENGINE_RADIATOR": {
        "load_ratio_power": {
            "curve_type": "load_ratio_power",
            "curve_schema": "load_ratio_power_1D",
            "display_name": "Load Ratio / Power Curve",
        },
        "load_ratio_power_1D": {
            "curve_type": "load_ratio_power_1D",
            "curve_schema": "load_ratio_power_1D",
            "display_name": "Load Ratio / Power Curve",
        },
    },
    "ELECTRICAL_DISTRIBUTION": {
        "electrical_path_efficiency": {
            "curve_type": "electrical_path_efficiency",
            "curve_schema": "efficiency_curve",
            "display_name": "Electrical Path Efficiency",
        },
        "efficiency_curve": {
            "curve_type": "efficiency_curve",
            "curve_schema": "efficiency_curve",
            "display_name": "Electrical Path Efficiency",
        },
    },
}


def normalize_curve_type(curve_type):
    """Return a normalized curve type key."""
    text = str(curve_type or "").strip()
    if not text:
        return ""
    return "_".join(text.replace("-", " ").split())


def get_supported_curve(equipment_type, curve_type):
    """Return registered curve metadata for an equipment_type + curve_type pair."""
    equipment_key = str(equipment_type or "").strip().upper()
    curve_key = normalize_curve_type(curve_type)
    curve = EQUIPMENT_CURVE_REGISTRY.get(equipment_key, {}).get(curve_key)
    return deepcopy(curve) if curve else None


def validate_curve_type_supported(equipment_type, curve_type):
    """Validate that a metadata curve_type is supported for an equipment type."""
    curve = get_supported_curve(equipment_type, curve_type)
    if curve:
        return {
            "status": "valid",
            "equipment_type": str(equipment_type or "").strip().upper(),
            "curve_type": curve_type,
            "curve_schema": curve.get("curve_schema", ""),
            "issues": [],
            "curve": curve,
        }
    expected = ", ".join(list_supported_curve_types(equipment_type)) or "none registered"
    equipment_key = str(equipment_type or "").strip().upper()
    return {
        "status": "error",
        "equipment_type": equipment_key,
        "curve_type": curve_type,
        "curve_schema": "",
        "issues": [
            f"Unsupported curve_type for {equipment_key}: expected {expected}; found {curve_type}"
        ],
        "curve": None,
    }


def list_supported_curve_types(equipment_type):
    """Return supported declared curve type keys for an equipment type."""
    equipment_key = str(equipment_type or "").strip().upper()
    return list(EQUIPMENT_CURVE_REGISTRY.get(equipment_key, {}).keys())


def list_curve_schemas():
    """Return every registered curve schema record."""
    records = []
    for equipment_type, curves in EQUIPMENT_CURVE_REGISTRY.items():
        for curve in curves.values():
            record = deepcopy(curve)
            record["equipment_type"] = equipment_type
            records.append(record)
    return records
