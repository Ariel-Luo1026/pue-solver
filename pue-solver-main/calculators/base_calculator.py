"""Base interface for future modular calculation engines.

Phase 9 skeleton only. Calculators introduced here do not replace or call
legacy solver.py calculations.
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

        Not implemented in Phase 9; formulas remain in the legacy path.
        """
        raise NotImplementedError("Calculator execution is not implemented in this phase.")
