"""Framework adapter for Chiller + Dry Cooler Configuration Library packages.

This adapter intentionally does not perform annual simulation. It validates
manifest role bindings and returns a structured framework status until
validated manufacturer curves and solver logic are available.
"""

from equipment_role_resolver import validate_required_equipment_roles


FRAMEWORK_REASON = (
    "Topology framework created. Validated manufacturer Solver_Curve data required before annual simulation."
)


def build_solver_input_from_configuration(manifest, solver_input):
    loaded_equipment = {}
    if isinstance(solver_input, dict):
        loaded_equipment = solver_input.get("selected_curves") or solver_input.get("equipment") or {}
    validate_required_equipment_roles(manifest, loaded_equipment)
    return {
        "status": "framework_ready_data_missing",
        "topology": "chiller_dry_cooler",
        "reason": FRAMEWORK_REASON,
    }
