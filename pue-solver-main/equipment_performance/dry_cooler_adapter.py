"""Dry cooler performance adapter wrapping the existing dry cooler engine."""

from equipment_engines.dry_cooler import DryCoolerEngine
from equipment_performance.performance_result import standard_performance


class DryCoolerPerformanceAdapter:
    """Normalize dry cooler ambient curve output without changing formulas."""

    equipment_type = "DRY_COOLER"
    curve_schema = "outdoor_temperature_power_1D"

    def __init__(self, equipment_metadata=None, curve_data=None, capacity_curve_data=None):
        self.metadata = equipment_metadata if isinstance(equipment_metadata, dict) else {}
        self.curve_data = curve_data
        self.equipment_id = self.metadata.get("equipment_id") or "DRY_COOLER"
        self.engine = DryCoolerEngine(
            equipment_id=self.equipment_id,
            curve_data=curve_data,
            capacity_curve_data=capacity_curve_data,
        )

    def calculate(self, input_conditions):
        conditions = input_conditions if isinstance(input_conditions, dict) else {}
        result = self.engine.calculate(
            required_heat_rejection_kW=conditions.get("required_heat_rejection_kW"),
            ambient_dry_bulb_C=conditions.get("ambient_dry_bulb_C"),
        )
        return standard_performance(
            self.equipment_id,
            self.equipment_type,
            input_conditions={
                "required_heat_rejection_kW": conditions.get("required_heat_rejection_kW"),
                "ambient_dry_bulb_C": conditions.get("ambient_dry_bulb_C"),
            },
            performance={
                "power_kW": result["dry_cooler_power_kW"],
                "COP": None,
                "load_ratio": None,
                "capacity_ratio": result["dry_cooler_capacity_ratio"],
                "capacity_kW": result["dry_cooler_capacity_kW"],
                "clamped_status": False,
            },
            diagnostics={
                "curve_schema": self.curve_schema,
                "curve_source": result["dry_cooler_curve_source"],
                "power_lookup": {
                    key: value for key, value in result.items() if key.startswith("dry_cooler_")
                },
            },
        )
