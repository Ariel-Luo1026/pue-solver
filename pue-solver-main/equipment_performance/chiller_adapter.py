"""Chiller performance adapter wrapping the existing chiller engine."""

from equipment_engines.chiller import ChillerEngine
from equipment_performance.performance_result import standard_performance


class ChillerPerformanceAdapter:
    """Normalize chiller COP-map output without changing chiller formulas."""

    equipment_type = "CHILLER"
    curve_schema = "cop_map_2D"

    def __init__(self, equipment_metadata=None, curve_data=None):
        self.metadata = equipment_metadata if isinstance(equipment_metadata, dict) else {}
        self.curve_data = curve_data
        self.equipment_id = self.metadata.get("equipment_id") or "CHILLER"
        self.engine = ChillerEngine(
            equipment_id=self.equipment_id,
            curve_data=curve_data,
        )

    def calculate(self, input_conditions):
        conditions = input_conditions if isinstance(input_conditions, dict) else {}
        rated_capacity = (
            conditions.get("rated_chiller_capacity_kW")
            or conditions.get("rated_capacity_kW")
            or self.metadata.get("rated_capacity_kW")
        )
        result = self.engine.calculate(
            required_cooling_capacity_kW=conditions.get("required_cooling_capacity_kW"),
            rated_chiller_capacity_kW=rated_capacity,
            CEFT_C=conditions.get("CEFT_C"),
        )
        return standard_performance(
            self.equipment_id,
            self.equipment_type,
            input_conditions={
                "required_cooling_capacity_kW": conditions.get("required_cooling_capacity_kW"),
                "rated_chiller_capacity_kW": rated_capacity,
                "CEFT_C": conditions.get("CEFT_C"),
            },
            performance={
                "power_kW": result["chiller_power_kW"],
                "COP": result["chiller_COP"],
                "load_ratio": result["chiller_load_ratio"],
                "capacity_ratio": result["chiller_load_ratio"],
                "capacity_kW": result["chiller_capacity_kW"],
                "clamped_status": False,
            },
            diagnostics={
                "curve_schema": self.curve_schema,
                "curve_source": result["chiller_curve_source"],
            },
        )
