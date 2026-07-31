"""Dispatch equipment metadata and curve schemas to runtime engine registrations.

This module is a routing framework only. It does not move or reimplement ACC V2,
solver.py formulas, or equipment curve lookup behavior.
"""

from copy import deepcopy

from equipment_curve_registry import validate_curve_type_supported
from equipment_engines.chiller import ChillerEngine
from equipment_engines.dry_cooler import DryCoolerEngine


class EquipmentEngineDispatchError(ValueError):
    """Raised when equipment metadata cannot be dispatched to a runtime engine."""


ENGINE_REGISTRY = {
    ("ACC", "ambient_capacity_power_2D"): {
        "engine_key": "acc_ambient_capacity_power_2d",
        "engine_type": "existing_acc_v2_wrapper",
        "status": "implemented",
        "reason": "Uses existing ACC V2 calculation path; no calculation logic is implemented here.",
    },
    ("CHW_PUMP", "load_ratio_power_1D"): {
        "engine_key": "generic_load_ratio_power_1d",
        "engine_type": "configuration_library_equipment_engine",
        "status": "implemented",
        "reason": "Uses existing generic ConfigurationLibraryEquipmentEngine lookup wrapper.",
    },
    ("CDU", "load_ratio_power_1D"): {
        "engine_key": "generic_load_ratio_power_1d",
        "engine_type": "configuration_library_equipment_engine",
        "status": "implemented",
        "reason": "Uses existing generic ConfigurationLibraryEquipmentEngine lookup wrapper.",
    },
    ("RTC", "load_ratio_power_1D"): {
        "engine_key": "generic_load_ratio_power_1d",
        "engine_type": "configuration_library_equipment_engine",
        "status": "implemented",
        "reason": "Uses existing generic ConfigurationLibraryEquipmentEngine lookup wrapper.",
    },
    ("MAU", "load_ratio_power_1D"): {
        "engine_key": "generic_load_ratio_power_1d",
        "engine_type": "configuration_library_equipment_engine",
        "status": "implemented",
        "reason": "Uses existing generic ConfigurationLibraryEquipmentEngine lookup wrapper.",
    },
    ("ELECTRICAL_DISTRIBUTION", "efficiency_curve"): {
        "engine_key": "electrical_distribution_efficiency_curve",
        "engine_type": "configuration_library_equipment_engine",
        "status": "implemented",
        "reason": "Uses existing electrical-path efficiency lookup wrapper.",
    },
    ("CHILLER", "cop_map_2D"): {
        "engine_key": "chiller_cop_map_2d",
        "engine_type": "equipment_engines.chiller.ChillerEngine",
        "engine_class": ChillerEngine,
        "status": "implemented",
        "reason": "Uses Configuration Library chiller COP map runtime engine.",
    },
    ("DRY_COOLER", "ambient_capacity_power_1D"): {
        "engine_key": "dry_cooler_ambient_capacity_power_1d",
        "engine_type": "equipment_engines.dry_cooler.DryCoolerEngine",
        "engine_class": DryCoolerEngine,
        "status": "implemented",
        "reason": "Uses Configuration Library dry cooler ambient capacity/power runtime engine.",
    },
}


def dispatch_equipment_engine(equipment_metadata, curve_type=None, curve_data=None):
    """Return the registered runtime engine for equipment metadata and curve data."""
    metadata = equipment_metadata if isinstance(equipment_metadata, dict) else {}
    equipment_type = str(metadata.get("equipment_type") or "").strip().upper()
    declared_curve_type = curve_type or metadata.get("curve_type")
    if not equipment_type:
        raise EquipmentEngineDispatchError("Equipment engine dispatch failed: missing equipment_type.")
    if not declared_curve_type:
        raise EquipmentEngineDispatchError("Equipment engine dispatch failed: missing curve_type.")

    curve_validation = validate_curve_type_supported(equipment_type, declared_curve_type)
    if curve_validation["status"] == "error":
        raise EquipmentEngineDispatchError(
            "Equipment engine dispatch failed: " + "; ".join(curve_validation["issues"])
        )

    curve_schema = curve_validation.get("curve_schema", "")
    registration = ENGINE_REGISTRY.get((equipment_type, curve_schema))
    if registration is None:
        raise EquipmentEngineDispatchError(
            f"Equipment engine dispatch failed: no runtime engine registered for {equipment_type} curve schema {curve_schema}."
        )

    result = deepcopy(registration)
    engine_class = registration.get("engine_class")
    result.update({
        "equipment_id": metadata.get("equipment_id", ""),
        "equipment_type": equipment_type,
        "curve_type": declared_curve_type,
        "curve_schema": curve_schema,
        "curve_data": curve_data,
    })
    if engine_class is not None:
        result["engine_class"] = engine_class
        result["engine"] = engine_class(
            equipment_id=metadata.get("equipment_id", equipment_type),
            curve_data=curve_data,
        )
    return result


def get_equipment_engine_registration(equipment_type, curve_schema):
    """Return a registered engine entry by equipment type and normalized schema."""
    registration = ENGINE_REGISTRY.get((str(equipment_type or "").strip().upper(), curve_schema))
    return deepcopy(registration) if registration else None


def list_equipment_engines():
    """Return all equipment engine registrations."""
    records = []
    for (equipment_type, curve_schema), registration in ENGINE_REGISTRY.items():
        record = deepcopy(registration)
        record["equipment_type"] = equipment_type
        record["curve_schema"] = curve_schema
        records.append(record)
    return records
