"""ACC calculator skeleton.

Phase 9 does not move ACC formulas. Existing ACC calculations remain handled
by the legacy solver.py / ACC benchmark paths.
"""

from calculators.base_calculator import BaseCalculator


class ACCCalculator(BaseCalculator):
    calculator_id = "acc_calculator"
    display_name = "ACC Calculator"
    supported_topology_ids = ["acc"]
    supported_solver_modes = ["acc_hourly"]

    def run(self, project_input):
        raise NotImplementedError(
            "ACC calculation is still handled by legacy solver.py in this phase."
        )
