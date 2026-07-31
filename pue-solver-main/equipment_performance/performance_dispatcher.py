"""Dispatch equipment metadata and curve schemas to performance adapters."""

from equipment_curve_registry import validate_curve_type_supported
from equipment_performance.acc_adapter import ACCPerformanceAdapter
from equipment_performance.chiller_adapter import ChillerPerformanceAdapter
from equipment_performance.dry_cooler_adapter import DryCoolerPerformanceAdapter


class EquipmentPerformanceDispatchError(ValueError):
    """Raised when an equipment performance adapter cannot be selected."""


PERFORMANCE_ADAPTER_REGISTRY = {
    ("ACC", "ambient_capacity_power_2D"): ACCPerformanceAdapter,
    ("CHILLER", "cop_map_2D"): ChillerPerformanceAdapter,
    ("DRY_COOLER", "ambient_capacity_power_1D"): DryCoolerPerformanceAdapter,
}


def dispatch_performance_adapter(equipment_metadata, curve_data=None, curve_type=None):
    """Return a performance adapter selected by equipment metadata."""
    metadata = equipment_metadata if isinstance(equipment_metadata, dict) else {}
    equipment_type = str(metadata.get("equipment_type") or "").strip().upper()
    declared_curve_type = curve_type or metadata.get("curve_schema") or metadata.get("curve_type")
    if not equipment_type:
        raise EquipmentPerformanceDispatchError("Equipment performance dispatch failed: missing equipment_type.")
    if not declared_curve_type:
        raise EquipmentPerformanceDispatchError("Equipment performance dispatch failed: missing curve_type.")

    validation = validate_curve_type_supported(equipment_type, declared_curve_type)
    if validation["status"] == "error":
        raise EquipmentPerformanceDispatchError(
            "Equipment performance dispatch failed: " + "; ".join(validation["issues"])
        )
    curve_schema = validation.get("curve_schema")
    adapter_class = PERFORMANCE_ADAPTER_REGISTRY.get((equipment_type, curve_schema))
    if adapter_class is None:
        raise EquipmentPerformanceDispatchError(
            f"Equipment performance dispatch failed: no adapter registered for {equipment_type} curve schema {curve_schema}."
        )
    return adapter_class(
        equipment_metadata={**metadata, "equipment_type": equipment_type, "curve_schema": curve_schema},
        curve_data=curve_data,
    )


def calculate_equipment_performance(equipment_metadata, curve_data, input_conditions, curve_type=None):
    """Dispatch and evaluate one equipment performance point."""
    adapter = dispatch_performance_adapter(equipment_metadata, curve_data=curve_data, curve_type=curve_type)
    return adapter.calculate(input_conditions)
