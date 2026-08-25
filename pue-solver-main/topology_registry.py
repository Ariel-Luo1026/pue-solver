"""Cooling topology metadata and implementation status registry.

This module is architecture metadata only. It does not perform numerical
calculation and is not imported by solver.py.
"""

from copy import deepcopy

from equipment_registry import get_equipment


TOPOLOGY_REGISTRY = {
    "acc_gas_engine_cdu": {
        "topology_id": "acc_gas_engine_cdu",
        "display_name": "ACC",
        "cooling_system_type": "acc_gas_engine_cdu",
        "legacy_cooling_system_types": ["ACC"],
        "implementation_status": "implemented",
        "status": "implemented",
        "adapter": "acc_gas_engine_cdu",
        "calculation_status": "implemented",
        "required_roles": [
            "primary_cooling",
            "chw_pump",
            "rtc",
            "cdu",
            "mau",
            "electrical_distribution",
        ],
        "optional_roles": ["engine", "engine_radiator"],
        "required_inputs": ["weather", "it_load", "scenario"],
        "solver_dispatch_key": "acc_gas_engine_cdu",
        "report_profile": "acc_gas_engine_cdu",
        "notes": "Existing ACC V2 Configuration Library direct Solver_Curve annual path.",
        "primary_cooling_equipment": ["ACC"],
        "heat_rejection_equipment": ["Outdoor Air Heat Rejection"],
        "indoor_side_equipment": ["CDU", "RTC", "MAU"],
        "power_source_options": ["Grid", "Gas Engine"],
        "equipment_ids": [
            "acc_unit",
            "cdu",
            "pump",
            "terminal_fan",
            "mau",
            "auxiliary_load",
            "rtc",
            "electrical_distribution",
            "gas_engine",
            "engine_radiator",
        ],
        "required_performance_curves": [
            "ACC performance curve",
            "Pump power curve",
            "CDU performance curve",
            "Auxiliary load profile",
            "Fan power curve",
            "Electrical loss model",
            "Engine efficiency curve",
            "Heat exchanger performance curve",
            "IT load profile",
            "weather profile",
        ],
        "heat_flow_path": ["IT Load", "CDU", "ACC", "Outdoor Air"],
        "environmental_driver": ["Outdoor Dry Bulb Temperature"],
    },
    "chiller_dry_cooler": {
        "topology_id": "chiller_dry_cooler",
        "display_name": "Chiller + Dry Cooler",
        "cooling_system_type": "chiller_dry_cooler",
        "legacy_cooling_system_types": ["Chiller + Dry Cooler"],
        "implementation_status": "implemented",
        "status": "implemented",
        "adapter": "chiller_dry_cooler",
        "calculation_status": "implemented",
        "required_roles": ["chiller", "dry_cooler", "chw_pump", "electrical_distribution"],
        "optional_roles": ["indoor_cooling"],
        "required_inputs": ["weather", "it_load", "scenario"],
        "solver_dispatch_key": "chiller_dry_cooler",
        "report_profile": "chiller_dry_cooler",
        "notes": "Configuration Library annual runtime dispatches through the chiller and dry cooler equipment engines.",
        "primary_cooling_equipment": ["Chiller"],
        "heat_rejection_equipment": ["Dry Cooler"],
        "indoor_side_equipment": ["CDU", "CHW Pump", "CW Pump"],
        "power_source_options": ["Grid", "Gas Engine"],
        "equipment_ids": ["chiller", "dry_cooler", "cdu", "pump", "terminal_fan", "electrical_distribution", "auxiliary_load"],
        "required_performance_curves": ["Chiller COP surface", "Dry-cooler performance curve", "Pump power curve", "IT load profile", "weather profile"],
        "heat_flow_path": ["IT Load", "CDU", "Chilled Water Loop", "Chiller", "Condenser Water Loop", "Dry Cooler", "Outdoor Air"],
        "environmental_driver": ["Outdoor Dry Bulb Temperature"],
    },
    "water_cooled_chiller": {
        "topology_id": "water_cooled_chiller",
        "display_name": "Water-Cooled Chiller",
        "cooling_system_type": "water_cooled_chiller",
        "legacy_cooling_system_types": [],
        "implementation_status": "placeholder",
        "status": "placeholder",
        "adapter": None,
        "calculation_status": "placeholder",
        "required_roles": ["primary_cooling", "chw_pump", "condenser_water_pump"],
        "optional_roles": ["cdu", "mau", "rtc", "electrical_distribution"],
        "solver_dispatch_key": "placeholder",
        "report_profile": "planned",
        "notes": "Planned topology only; no annual solver dispatch is implemented.",
        "primary_cooling_equipment": ["Water-Cooled Chiller"],
        "heat_rejection_equipment": ["Condenser Water Loop"],
        "indoor_side_equipment": ["CDU", "CHW Pump"],
        "power_source_options": ["Grid", "Gas Engine"],
        "equipment_ids": ["chiller", "cdu", "pump", "electrical_distribution"],
        "required_performance_curves": ["Chiller COP surface", "Pump power curve"],
        "heat_flow_path": ["IT Load", "CDU", "Chiller", "Condenser Water Loop"],
        "environmental_driver": ["Cooling Water Temperature"],
    },
    "chiller_cooling_tower": {
        "topology_id": "chiller_cooling_tower",
        "display_name": "Chiller + Cooling Tower",
        "cooling_system_type": "chiller_cooling_tower",
        "legacy_cooling_system_types": ["Chiller + Cooling Tower"],
        "implementation_status": "placeholder",
        "status": "placeholder",
        "adapter": None,
        "calculation_status": "placeholder",
        "required_roles": ["primary_cooling", "cooling_tower", "chw_pump", "cdu"],
        "optional_roles": ["cw_pump", "mau", "rtc", "electrical_distribution", "engine", "engine_radiator"],
        "solver_dispatch_key": "placeholder",
        "report_profile": "planned",
        "notes": "Metadata exists; no complete annual cooling-tower calculation path is implemented.",
        "primary_cooling_equipment": ["Chiller"],
        "heat_rejection_equipment": ["Cooling Tower"],
        "indoor_side_equipment": ["CDU", "CHW Pump", "CW Pump"],
        "power_source_options": ["Grid", "Gas Engine"],
        "equipment_ids": ["chiller", "cooling_tower", "cdu", "pump", "terminal_fan", "electrical_distribution", "auxiliary_load"],
        "required_performance_curves": ["Chiller COP surface", "Cooling-tower performance curve", "Pump power curve", "IT load profile", "weather profile"],
        "heat_flow_path": ["IT Load", "CDU", "Chilled Water Loop", "Chiller", "Condenser Water Loop", "Cooling Tower", "Outdoor Air"],
        "environmental_driver": ["Outdoor Wet Bulb Temperature", "Cooling Water Temperature"],
    },
    "liquid_cooling": {
        "topology_id": "liquid_cooling",
        "display_name": "Liquid Cooling",
        "cooling_system_type": "liquid_cooling",
        "legacy_cooling_system_types": [],
        "implementation_status": "placeholder",
        "status": "placeholder",
        "adapter": None,
        "calculation_status": "placeholder",
        "required_roles": ["cdu", "primary_cooling"],
        "optional_roles": ["chw_pump", "mau", "rtc", "electrical_distribution"],
        "solver_dispatch_key": "placeholder",
        "report_profile": "planned",
        "notes": "Liquid/air IT heat-split fields exist, but there is no distinct liquid-cooling topology dispatch.",
        "primary_cooling_equipment": ["Liquid Cooling System"],
        "heat_rejection_equipment": ["TBD"],
        "indoor_side_equipment": ["CDU"],
        "power_source_options": ["Grid", "Gas Engine"],
        "equipment_ids": ["cdu", "pump", "electrical_distribution"],
        "required_performance_curves": ["CDU performance curve"],
        "heat_flow_path": ["IT Load", "CDU", "Primary Cooling"],
        "environmental_driver": ["TBD"],
    },
    "abs_dry_cooler": {
        "topology_id": "abs_dry_cooler",
        "display_name": "ABS + Dry Cooler",
        "cooling_system_type": "abs_dry_cooler",
        "legacy_cooling_system_types": ["ABS + Dry Cooler"],
        "implementation_status": "placeholder",
        "status": "placeholder",
        "adapter": None,
        "calculation_status": "placeholder",
        "required_roles": ["primary_cooling", "dry_cooler", "chw_pump", "cdu"],
        "optional_roles": ["cw_pump", "mau", "rtc", "engine", "engine_radiator", "electrical_distribution"],
        "solver_dispatch_key": "placeholder",
        "report_profile": "planned",
        "notes": "Absorption chiller topology metadata only; no annual solver dispatch is implemented.",
        "primary_cooling_equipment": ["Absorption Chiller"],
        "heat_rejection_equipment": ["Dry Cooler"],
        "indoor_side_equipment": ["CDU", "CHW Pump", "CW Pump"],
        "power_source_options": ["Grid", "Gas Engine"],
        "equipment_ids": ["absorption_chiller", "dry_cooler", "heat_exchanger", "cdu", "pump", "terminal_fan", "gas_engine", "electrical_distribution", "auxiliary_load"],
        "required_performance_curves": ["ABS performance / COP curve", "Dry-cooler performance curve", "Pump power curve", "IT load profile", "weather profile"],
        "heat_flow_path": ["IT Load", "CDU", "Chilled Water Loop", "Absorption Chiller", "Condenser Water Loop", "Dry Cooler", "Outdoor Air"],
        "environmental_driver": ["Outdoor Dry Bulb Temperature"],
    },
    "abs_cooling_tower": {
        "topology_id": "abs_cooling_tower",
        "display_name": "ABS + Cooling Tower",
        "cooling_system_type": "abs_cooling_tower",
        "legacy_cooling_system_types": ["ABS + Cooling Tower"],
        "implementation_status": "placeholder",
        "status": "placeholder",
        "adapter": None,
        "calculation_status": "placeholder",
        "required_roles": ["primary_cooling", "cooling_tower", "chw_pump", "cdu"],
        "optional_roles": ["cw_pump", "mau", "rtc", "engine", "engine_radiator", "electrical_distribution"],
        "solver_dispatch_key": "placeholder",
        "report_profile": "planned",
        "notes": "Absorption plus cooling tower metadata only; no annual solver dispatch is implemented.",
        "primary_cooling_equipment": ["Absorption Chiller"],
        "heat_rejection_equipment": ["Cooling Tower"],
        "indoor_side_equipment": ["CDU", "CHW Pump", "CW Pump"],
        "power_source_options": ["Grid", "Gas Engine"],
        "equipment_ids": ["absorption_chiller", "cooling_tower", "heat_exchanger", "cdu", "pump", "terminal_fan", "gas_engine", "electrical_distribution", "auxiliary_load"],
        "required_performance_curves": ["ABS performance / COP curve", "Cooling-tower performance curve", "Pump power curve", "IT load profile", "weather profile"],
        "heat_flow_path": ["IT Load", "CDU", "Chilled Water Loop", "Absorption Chiller", "Condenser Water Loop", "Cooling Tower", "Outdoor Air"],
        "environmental_driver": ["Outdoor Wet Bulb Temperature", "Cooling Water Temperature"],
    },
}


def get_topology(topology_id):
    """Return topology metadata by topology ID or compatibility alias."""
    if topology_id in {"acc", "ACC"}:
        return _legacy_acc_topology()
    topology = TOPOLOGY_REGISTRY.get(topology_id)
    return deepcopy(topology) if topology else None


def list_topologies():
    """Return all registered topology metadata records."""
    return [deepcopy(topology) for topology in TOPOLOGY_REGISTRY.values()]


def get_topology_by_cooling_type(cooling_system_type):
    """Return topology metadata matching a canonical or legacy cooling type."""
    for topology in TOPOLOGY_REGISTRY.values():
        if topology["cooling_system_type"] == cooling_system_type:
            return deepcopy(topology)
        if cooling_system_type in topology.get("legacy_cooling_system_types", []):
            if cooling_system_type == "ACC":
                return _legacy_acc_topology()
            return deepcopy(topology)
    return get_topology(cooling_system_type)


def get_topology_equipment(topology_id):
    """Return equipment records referenced by a topology."""
    topology = get_topology(topology_id)
    if topology is None:
        raise KeyError(f"Unknown topology_id: {topology_id}")

    equipment_records = []
    for equipment_id in topology.get("equipment_ids", []):
        equipment = get_equipment(equipment_id)
        if equipment is None:
            raise KeyError(
                f"Topology {topology['topology_id']!r} references unknown equipment_id: {equipment_id!r}"
            )
        equipment_records.append(equipment)
    return equipment_records


def _legacy_acc_topology():
    topology = deepcopy(TOPOLOGY_REGISTRY["acc_gas_engine_cdu"])
    topology["topology_id"] = "acc"
    topology["cooling_system_type"] = "ACC"
    topology["solver_dispatch_key"] = "acc_gas_engine_cdu"
    topology["equipment_ids"] = [
        equipment_id
        for equipment_id in topology["equipment_ids"]
        if equipment_id != "engine_radiator"
    ]
    return topology
