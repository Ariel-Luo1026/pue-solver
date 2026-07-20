"""ACC + gas engine + CDU Configuration Library adapter routing."""


def build_solver_input_from_configuration(manifest, equipment_roles):
    """Build the existing ACC solver input without changing calculation logic."""
    from library_solver_adapter import _build_acc_gas_engine_cdu_solver_input

    return _build_acc_gas_engine_cdu_solver_input(equipment_roles)
