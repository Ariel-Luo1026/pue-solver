"""Model-level equipment catalog for cooling-system architecture selection."""


def _item(equipment_id, equipment_type, model_number, display_name, space_type):
    curve_type = _catalog_curve_type(equipment_type)
    return {
        "id": equipment_id,
        "equipment_type": equipment_type,
        "model_number": str(model_number),
        "display_name": display_name,
        "space_type": space_type,
        "default_curve_id": equipment_id,
        "default_curve_file": f"data/performance_curves/{equipment_id}.xlsx",
        "curve_type": curve_type,
        "rated_capacity_kw": None,
        "rated_power_kw": None,
        "notes": "Placeholder catalog item. Model-level performance data to be added later.",
    }


def _catalog_curve_type(equipment_type):
    normalized = equipment_type.upper().replace(" ", "_").replace("-", "_")
    if normalized in {"CHW_PUMP", "CW_PUMP"}:
        return "pump_power_curve"
    return {
        "ACC": "acc_performance_curve", "ABS": "abs_performance_curve",
        "CHILLER": "chiller_cop_curve", "DRY_COOLER": "dry_cooler_performance_curve",
        "COOLING_TOWER": "cooling_tower_performance_curve", "ENGINE": "engine_efficiency_curve",
        "ENGINE_RADIATOR": "engine_radiator_performance_curve",
        "SMOKE_WATER_HX": "heat_exchanger_performance_curve",
        "CDU": "cdu_performance_curve", "RTC": "rtc_performance_curve", "MAU": "mau_performance_curve",
    }.get(normalized, "equipment_performance_curve")


_CATALOG_SPECS = [
    ("CDU_1", "CDU", 1, "CDU 1", "white_space"),
    ("CDU_2", "CDU", 2, "CDU 2", "white_space"),
    ("CDU_3", "CDU", 3, "CDU 3", "white_space"),
    ("RTC_1", "RTC", 1, "RTC 1", "white_space"),
    ("RTC_2", "RTC", 2, "RTC 2", "white_space"),
    ("MAU_1", "MAU", 1, "MAU 1", "white_space"),
    ("MAU_2", "MAU", 2, "MAU 2", "white_space"),
    ("ACC_1", "ACC", 1, "ACC 1", "gray_space"),
    ("ACC_2", "ACC", 2, "ACC 2", "gray_space"),
    ("ABS_1", "ABS", 1, "ABS 1", "gray_space"),
    ("ABS_2", "ABS", 2, "ABS 2", "gray_space"),
    ("ABS_3", "ABS", 3, "ABS 3", "gray_space"),
    ("CHILLER_1", "Chiller", 1, "Chiller 1", "gray_space"),
    ("CHILLER_2", "Chiller", 2, "Chiller 2", "gray_space"),
    ("CHILLER_3", "Chiller", 3, "Chiller 3", "gray_space"),
    ("DRY_COOLER_1", "Dry Cooler", 1, "Dry Cooler 1", "gray_space"),
    ("DRY_COOLER_2", "Dry Cooler", 2, "Dry Cooler 2", "gray_space"),
    ("DRY_COOLER_3", "Dry Cooler", 3, "Dry Cooler 3", "gray_space"),
    ("COOLING_TOWER_1", "Cooling Tower", 1, "Cooling Tower 1", "gray_space"),
    ("COOLING_TOWER_2", "Cooling Tower", 2, "Cooling Tower 2", "gray_space"),
    ("COOLING_TOWER_3", "Cooling Tower", 3, "Cooling Tower 3", "gray_space"),
    ("CHW_PUMP_1", "CHW Pump", 1, "CHW Pump 1", "gray_space"),
    ("CHW_PUMP_2", "CHW Pump", 2, "CHW Pump 2", "gray_space"),
    ("CHW_PUMP_3", "CHW Pump", 3, "CHW Pump 3", "gray_space"),
    ("CW_PUMP_1", "CW Pump", 1, "CW Pump 1", "gray_space"),
    ("CW_PUMP_2", "CW Pump", 2, "CW Pump 2", "gray_space"),
    ("CW_PUMP_3", "CW Pump", 3, "CW Pump 3", "gray_space"),
    ("ENGINE_2", "Engine", 2, "Engine 2", "gray_space"),
    ("ENGINE_3", "Engine", 3, "Engine 3", "gray_space"),
    ("ENGINE_RADIATOR_1", "Engine Radiator", 1, "Engine Radiator 1", "gray_space"),
    ("SMOKE_WATER_HX_1", "Smoke-Water HX", 1, "Smoke-Water HX 1", "gray_space"),
]

EQUIPMENT_CATALOG = {
    equipment_id: _item(equipment_id, equipment_type, model_number, display_name, space_type)
    for equipment_id, equipment_type, model_number, display_name, space_type in _CATALOG_SPECS
}


def get_equipment_item(equipment_id):
    """Return catalog metadata for an ID, or None when the ID is unknown."""
    return EQUIPMENT_CATALOG.get(equipment_id)


def resolve_equipment_list(equipment_ids):
    """Resolve equipment IDs in order; unknown IDs are represented by None."""
    return [get_equipment_item(equipment_id) for equipment_id in equipment_ids]
