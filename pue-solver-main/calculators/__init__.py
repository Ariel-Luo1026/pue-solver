"""Calculator registry for future modular calculation engines.

Phase 9 exposes calculator metadata and matching only; it performs no
calculations and does not import solver.py.
"""

from calculators.acc_calculator import ACCCalculator


def list_calculators():
    """Return available calculator instances."""
    return [ACCCalculator()]


def get_calculator_for_context(context):
    """Return the first calculator that can handle context, or None."""
    for calculator in list_calculators():
        if calculator.can_handle(context):
            return calculator
    return None
