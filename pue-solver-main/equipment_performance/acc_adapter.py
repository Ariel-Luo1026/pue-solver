"""ACC performance adapter wrapping the existing ACC V2 lookup layer."""

from acc_v2_curve_lookup import lookup_acc_curve
from equipment_curve_reader import EquipmentCurvePreview
from equipment_performance.performance_result import standard_performance


class ACCPerformanceAdapter:
    """Normalize ACC operating point output without changing ACC formulas."""

    equipment_type = "ACC"
    curve_schema = "ambient_capacity_power_2D"

    def __init__(self, equipment_metadata=None, curve_data=None):
        self.metadata = equipment_metadata if isinstance(equipment_metadata, dict) else {}
        self.curve_data = curve_data
        self.equipment_id = self.metadata.get("equipment_id") or "ACC"

    def calculate(self, input_conditions):
        conditions = input_conditions if isinstance(input_conditions, dict) else {}
        preview = _preview(self.equipment_id, self.curve_data)
        point = lookup_acc_curve(
            preview,
            ambient_C=conditions.get("ambient_C"),
            load_ratio=conditions.get("load_ratio"),
            required_capacity_kW=conditions.get("required_capacity_kW"),
            nominal_unit_capacity_kW=conditions.get("nominal_unit_capacity_kW"),
        )
        return standard_performance(
            self.equipment_id,
            self.equipment_type,
            input_conditions={
                "ambient_C": point.ambient_C,
                "load_ratio": conditions.get("load_ratio"),
                "required_capacity_kW": conditions.get("required_capacity_kW"),
                "nominal_unit_capacity_kW": conditions.get("nominal_unit_capacity_kW"),
            },
            performance={
                "power_kW": point.power_input_kW,
                "COP": point.cop,
                "load_ratio": point.load_ratio,
                "capacity_ratio": point.diagnostic_load_ratio,
                "capacity_kW": point.capacity_kW,
                "clamped_status": point.capacity_clamped,
            },
            diagnostics={
                "curve_schema": self.curve_schema,
                "curve_source": "existing_acc_v2_lookup",
                "required_capacity_kW": point.required_capacity_kW,
                "power_input_per_unit_kW": point.power_input_per_unit_kW,
                "diagnostic_load_ratio": point.diagnostic_load_ratio,
            },
        )


def performance_result_from_legacy_acc_row(row, equipment_id="ACC"):
    """Wrap an existing solver ACC hourly row without recalculating performance."""
    hourly = row if isinstance(row, dict) else {}
    ambient_c = _first_present(
        hourly.get("acc_ambient_C"),
        hourly.get("dry_bulb_C"),
        hourly.get("outdoor_dry_bulb_C"),
    )
    required_capacity_kw = _first_present(
        hourly.get("acc_required_capacity_per_unit_kW"),
        hourly.get("cooling_load_kW"),
    )
    load_ratio = _first_present(
        hourly.get("acc_load_ratio"),
        hourly.get("unit_load_ratio"),
    )
    capacity_ratio = _first_present(
        hourly.get("acc_diagnostic_load_ratio"),
        load_ratio,
    )
    clamped_status = bool(hourly.get("acc_capacity_clamped", False))
    return standard_performance(
        equipment_id,
        "ACC",
        input_conditions={
            "ambient_C": ambient_c,
            "required_capacity_kW": required_capacity_kw,
        },
        performance={
            "power_kW": _first_present(hourly.get("acc_power_kW"), hourly.get("acc_power_input_kW")),
            "COP": hourly.get("acc_cop"),
            "load_ratio": load_ratio,
            "capacity_ratio": capacity_ratio,
            "capacity_kW": hourly.get("cooling_unit_capacity_kW"),
            "clamped_status": clamped_status,
        },
        diagnostics={
            "curve_schema": ACCPerformanceAdapter.curve_schema,
            "curve_source": hourly.get("acc_curve_source") or "legacy_solver_hourly_output",
            "clamped_status": clamped_status,
            "power_input_per_unit_kW": hourly.get("acc_power_input_per_unit_kW"),
            "diagnostic_load_ratio": hourly.get("acc_diagnostic_load_ratio"),
            "source": "existing_acc_solver_output",
        },
    )


def _first_present(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _preview(equipment_id, curve_data):
    if isinstance(curve_data, EquipmentCurvePreview):
        return curve_data
    if isinstance(curve_data, dict):
        rows = curve_data.get("points")
        if not isinstance(rows, list):
            rows = curve_data.get("data")
        return EquipmentCurvePreview(
            equipment_id=equipment_id,
            curve_type="ambient_capacity_power_2D",
            solver_curve_rows=list(rows or []),
            required_columns_present=True,
        )
    return EquipmentCurvePreview(
        equipment_id=equipment_id,
        curve_type="ambient_capacity_power_2D",
        solver_curve_rows=list(curve_data or []),
        required_columns_present=True,
    )
