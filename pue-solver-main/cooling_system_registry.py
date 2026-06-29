"""Phase 3 cooling-system registry using model-level equipment catalog IDs.

This registry is architecture-only. It is not imported by solver.py.
"""

from equipment_catalog import resolve_equipment_list

WHITE_SPACE_BY_MODEL = {
    1: ["CDU_1", "RTC_1", "RTC_2", "MAU_1", "MAU_2"],
    2: ["CDU_2", "RTC_1", "RTC_2", "MAU_1", "MAU_2"],
    3: ["CDU_3", "RTC_1", "RTC_2", "MAU_1", "MAU_2"],
}


def _power_sources(white_ids, gray_ids, gas_engine_ids, required_curves, smoke_water_hx=False):
    gas_ids = list(gray_ids) + ["ENGINE_RADIATOR_1", *gas_engine_ids]
    gas_curves = list(required_curves) + ["Engine efficiency curve", "Engine radiator performance curve"]
    if smoke_water_hx:
        gas_ids.append("SMOKE_WATER_HX_1")
        gas_curves.append("Smoke-water HX performance curve")
    return {
        "Grid": {
            "white_space_equipment": list(white_ids),
            "gray_space_equipment": list(gray_ids),
            "required_curves": list(required_curves),
        },
        "Gas Engine": {
            "white_space_equipment": list(white_ids),
            "gray_space_equipment": gas_ids,
            "required_curves": gas_curves,
        },
    }


def _unit(white_model, gray_ids, engine_id, curves, smoke_water_hx=False):
    return {
        "power_sources": _power_sources(
            WHITE_SPACE_BY_MODEL[white_model], gray_ids, [engine_id], curves, smoke_water_hx
        )
    }


COOLING_SYSTEM_REGISTRY = {
    "ABS + Dry Cooler": {
        "cooling_unit_capacities": {
            "1": _unit(1, ["ABS_1", "DRY_COOLER_1", "CHW_PUMP_1", "CW_PUMP_1"], "ENGINE_2", ["ABS performance / COP curve", "Dry-cooler performance curve", "Pump power curve"], True),
            "1.5": _unit(2, ["ABS_2", "DRY_COOLER_2", "CHW_PUMP_2", "CW_PUMP_2"], "ENGINE_2", ["ABS performance / COP curve", "Dry-cooler performance curve", "Pump power curve"], True),
        },
        "calculation_implemented": False,
    },
    "Chiller + Dry Cooler": {
        "cooling_unit_capacities": {
            "1.5": _unit(1, ["CHILLER_1", "DRY_COOLER_1", "CHW_PUMP_1", "CW_PUMP_1"], "ENGINE_2", ["Chiller COP surface", "Dry-cooler performance curve", "Pump power curve"]),
            "2": _unit(2, ["CHILLER_2", "DRY_COOLER_2", "CHW_PUMP_2", "CW_PUMP_2"], "ENGINE_2", ["Chiller COP surface", "Dry-cooler performance curve", "Pump power curve"]),
            "4": _unit(3, ["CHILLER_3", "DRY_COOLER_3", "CHW_PUMP_3", "CW_PUMP_3"], "ENGINE_3", ["Chiller COP surface", "Dry-cooler performance curve", "Pump power curve"]),
        },
        "calculation_implemented": True,
    },
    "ACC": {
        "cooling_unit_capacities": {
            "1": _unit(1, ["ACC_1", "CHW_PUMP_1"], "ENGINE_2", ["ACC capacity and COP curves", "Pump power curve"]),
            "1.5": _unit(2, ["ACC_2", "CHW_PUMP_2"], "ENGINE_2", ["ACC capacity and COP curves", "Pump power curve"]),
            "2": _unit(3, ["ACC_2", "CHW_PUMP_3"], "ENGINE_3", ["ACC capacity and COP curves", "Pump power curve"]),
        },
        "calculation_implemented": False,
    },
    "Chiller + Cooling Tower": {
        "cooling_unit_capacities": {
            "2": _unit(2, ["CHILLER_2", "COOLING_TOWER_2", "CHW_PUMP_2", "CW_PUMP_2"], "ENGINE_2", ["Chiller COP surface", "Cooling-tower performance curve", "Pump power curve"]),
            "4": _unit(3, ["CHILLER_3", "COOLING_TOWER_3", "CHW_PUMP_3", "CW_PUMP_3"], "ENGINE_3", ["Chiller COP surface", "Cooling-tower performance curve", "Pump power curve"]),
        },
        "calculation_implemented": False,
    },
    "ABS + Cooling Tower": {
        "cooling_unit_capacities": {
            "1": _unit(1, ["ABS_1", "COOLING_TOWER_1", "CHW_PUMP_1", "CW_PUMP_1"], "ENGINE_2", ["ABS performance / COP curve", "Cooling-tower performance curve", "Pump power curve"], True),
            "1.5": _unit(2, ["ABS_2", "COOLING_TOWER_2", "CHW_PUMP_2", "CW_PUMP_2"], "ENGINE_2", ["ABS performance / COP curve", "Cooling-tower performance curve", "Pump power curve"], True),
            "2": _unit(3, ["ABS_3", "COOLING_TOWER_3", "CHW_PUMP_3", "CW_PUMP_3"], "ENGINE_3", ["ABS performance / COP curve", "Cooling-tower performance curve", "Pump power curve"], True),
        },
        "calculation_implemented": False,
    },
}


def resolve_configuration_equipment(system_type, capacity_mw, power_source):
    """Return resolved white/gray catalog objects for a registry path."""
    config = COOLING_SYSTEM_REGISTRY[system_type]["cooling_unit_capacities"][str(capacity_mw)]["power_sources"][power_source]
    return {
        "white_space_equipment": resolve_equipment_list(config["white_space_equipment"]),
        "gray_space_equipment": resolve_equipment_list(config["gray_space_equipment"]),
    }
