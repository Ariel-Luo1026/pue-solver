"""Cooling topology metadata registry.

Phase 1 topology framework skeleton. This module is intentionally
metadata-only and is not imported by solver.py.
"""

from copy import deepcopy

from equipment_registry import get_equipment


TOPOLOGY_REGISTRY = {
    "acc": {
        "topology_id": "acc",
        "display_name": "ACC",
        "cooling_system_type": "ACC",
        "primary_cooling_equipment": ["ACC"],
        "heat_rejection_equipment": ["Outdoor Air Heat Rejection"],
        "indoor_side_equipment": ["CDU"],
        "power_source_options": ["Grid", "Gas Engine"],
        "equipment_ids": [
            "acc_unit",
            "cdu",
            "pump",
            "terminal_fan",
            "electrical_distribution",
            "auxiliary_load",
            "gas_engine",
        ],
        "required_performance_curves": [
            "ACC performance curve",
            "IT load profile",
            "weather profile",
        ],
        "heat_flow_path": [
            "IT Load",
            "CDU",
            "ACC",
            "Outdoor Air",
        ],
        "environmental_driver": ["Outdoor Dry Bulb Temperature"],
        "calculation_status": "implemented",
    },
    "chiller_dry_cooler": {
        "topology_id": "chiller_dry_cooler",
        "display_name": "Chiller + Dry Cooler",
        "cooling_system_type": "Chiller + Dry Cooler",
        "primary_cooling_equipment": ["Chiller"],
        "heat_rejection_equipment": ["Dry Cooler"],
        "indoor_side_equipment": ["CDU", "CHW Pump", "CW Pump"],
        "power_source_options": ["Grid", "Gas Engine"],
        "equipment_ids": [
            "chiller",
            "dry_cooler",
            "cdu",
            "pump",
            "terminal_fan",
            "electrical_distribution",
            "auxiliary_load",
        ],
        "required_performance_curves": [
            "Chiller COP surface",
            "Dry-cooler performance curve",
            "Pump power curve",
            "IT load profile",
            "weather profile",
        ],
        "heat_flow_path": [
            "IT Load",
            "CDU",
            "Chilled Water Loop",
            "Chiller",
            "Condenser Water Loop",
            "Dry Cooler",
            "Outdoor Air",
        ],
        "environmental_driver": ["Outdoor Dry Bulb Temperature"],
        "calculation_status": "placeholder",
    },
    "chiller_cooling_tower": {
        "topology_id": "chiller_cooling_tower",
        "display_name": "Chiller + Cooling Tower",
        "cooling_system_type": "Chiller + Cooling Tower",
        "primary_cooling_equipment": ["Chiller"],
        "heat_rejection_equipment": ["Cooling Tower"],
        "indoor_side_equipment": ["CDU", "CHW Pump", "CW Pump"],
        "power_source_options": ["Grid", "Gas Engine"],
        "equipment_ids": [
            "chiller",
            "cooling_tower",
            "cdu",
            "pump",
            "terminal_fan",
            "electrical_distribution",
            "auxiliary_load",
        ],
        "required_performance_curves": [
            "Chiller COP surface",
            "Cooling-tower performance curve",
            "Pump power curve",
            "IT load profile",
            "weather profile",
        ],
        "heat_flow_path": [
            "IT Load",
            "CDU",
            "Chilled Water Loop",
            "Chiller",
            "Condenser Water Loop",
            "Cooling Tower",
            "Outdoor Air",
        ],
        "environmental_driver": [
            "Outdoor Wet Bulb Temperature",
            "Cooling Water Temperature",
        ],
        "calculation_status": "placeholder",
    },
    "abs_dry_cooler": {
        "topology_id": "abs_dry_cooler",
        "display_name": "ABS + Dry Cooler",
        "cooling_system_type": "ABS + Dry Cooler",
        "primary_cooling_equipment": ["Absorption Chiller"],
        "heat_rejection_equipment": ["Dry Cooler"],
        "indoor_side_equipment": ["CDU", "CHW Pump", "CW Pump"],
        "power_source_options": ["Grid", "Gas Engine"],
        "equipment_ids": [
            "absorption_chiller",
            "dry_cooler",
            "heat_exchanger",
            "cdu",
            "pump",
            "terminal_fan",
            "gas_engine",
            "electrical_distribution",
            "auxiliary_load",
        ],
        "required_performance_curves": [
            "ABS performance / COP curve",
            "Dry-cooler performance curve",
            "Pump power curve",
            "IT load profile",
            "weather profile",
        ],
        "heat_flow_path": [
            "IT Load",
            "CDU",
            "Chilled Water Loop",
            "Absorption Chiller",
            "Condenser Water Loop",
            "Dry Cooler",
            "Outdoor Air",
        ],
        "environmental_driver": ["Outdoor Dry Bulb Temperature"],
        "calculation_status": "placeholder",
    },
    "abs_cooling_tower": {
        "topology_id": "abs_cooling_tower",
        "display_name": "ABS + Cooling Tower",
        "cooling_system_type": "ABS + Cooling Tower",
        "primary_cooling_equipment": ["Absorption Chiller"],
        "heat_rejection_equipment": ["Cooling Tower"],
        "indoor_side_equipment": ["CDU", "CHW Pump", "CW Pump"],
        "power_source_options": ["Grid", "Gas Engine"],
        "equipment_ids": [
            "absorption_chiller",
            "cooling_tower",
            "heat_exchanger",
            "cdu",
            "pump",
            "terminal_fan",
            "gas_engine",
            "electrical_distribution",
            "auxiliary_load",
        ],
        "required_performance_curves": [
            "ABS performance / COP curve",
            "Cooling-tower performance curve",
            "Pump power curve",
            "IT load profile",
            "weather profile",
        ],
        "heat_flow_path": [
            "IT Load",
            "CDU",
            "Chilled Water Loop",
            "Absorption Chiller",
            "Condenser Water Loop",
            "Cooling Tower",
            "Outdoor Air",
        ],
        "environmental_driver": [
            "Outdoor Wet Bulb Temperature",
            "Cooling Water Temperature",
        ],
        "calculation_status": "placeholder",
    },
}


def get_topology(topology_id):
    """Return topology metadata by topology ID, or None if it is unknown."""
    topology = TOPOLOGY_REGISTRY.get(topology_id)
    return deepcopy(topology) if topology else None


def list_topologies():
    """Return all registered topology metadata records."""
    return [deepcopy(topology) for topology in TOPOLOGY_REGISTRY.values()]


def get_topology_by_cooling_type(cooling_system_type):
    """Return topology metadata matching a cooling-system type label."""
    for topology in TOPOLOGY_REGISTRY.values():
        if topology["cooling_system_type"] == cooling_system_type:
            return deepcopy(topology)
    return None


def get_topology_equipment(topology_id):
    """Return equipment records referenced by a topology.

    Raises:
        KeyError: when the topology or a referenced equipment ID is unknown.
    """
    topology = TOPOLOGY_REGISTRY.get(topology_id)
    if topology is None:
        raise KeyError(f"Unknown topology_id: {topology_id}")

    equipment_records = []
    for equipment_id in topology.get("equipment_ids", []):
        equipment = get_equipment(equipment_id)
        if equipment is None:
            raise KeyError(
                f"Topology {topology_id!r} references unknown equipment_id: {equipment_id!r}"
            )
        equipment_records.append(equipment)
    return equipment_records
