"""Base interface for future modular calculation engines.

Calculators should keep topology-specific orchestration small and reuse common
engineering helpers from calculators.common.weather,
calculators.common.performance_curve, calculators.common.energy_balance, and
calculators.common.pue_metrics where practical. Legacy solver.py paths remain
unchanged unless a later migration phase explicitly wires a calculator into a
calculation path.
"""


class BaseCalculator:
    calculator_id = None
    display_name = None
    supported_topology_ids = []
    supported_solver_modes = []

    def can_handle(self, context):
        """Return True when this calculator advertises support for context."""
        context = context or {}
        topology = context.get("topology") or {}
        topology_id = topology.get("topology_id") or context.get("topology_id")
        solver_mode = context.get("solver_mode") or context.get("calculation_mode")
        return (
            topology_id in self.supported_topology_ids
            and solver_mode in self.supported_solver_modes
        )

    def metadata(self):
        """Return read-only calculator metadata for routing diagnostics."""
        return {
            "calculator_id": self.calculator_id,
            "display_name": self.display_name,
            "supported_topology_ids": list(self.supported_topology_ids),
            "supported_solver_modes": list(self.supported_solver_modes),
        }

    def run(self, project_input):
        """Run the calculator.

        Subclasses may use calculators.common helpers, but Phase 11 does not
        require or wire those helpers into existing legacy calculations.
        """
        raise NotImplementedError("Calculator execution is not implemented in this phase.")
