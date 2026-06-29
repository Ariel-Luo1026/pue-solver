"""Scenario definitions for the architecture-only multi-scenario PUE framework."""

DEFAULT_SCENARIO_KEY = "normal_75"

SCENARIO_REGISTRY = {
    "normal_75": {
        "scenario_key": "normal_75",
        "display_name": "Normal / 75% cooling operation",
        "description": "Normal case with 4 energy modules operating.",
        "active_energy_modules": 4,
        "failure_count": 0,
        "cooling_operation_ratio": 0.75,
        "notes": "Normal case: 4 energy modules operating.",
    },
    "one_failure_three_active": {
        "scenario_key": "one_failure_three_active",
        "display_name": "1 Failure / 3 active energy modules",
        "description": "Failure case with 4 IT modules supported by 3 active energy modules.",
        "active_energy_modules": 3,
        "failure_count": 1,
        "cooling_operation_ratio": None,
        "notes": "Failure case: 4 IT modules supported by 3 active energy modules.",
    },
}


def get_scenario(scenario_key=DEFAULT_SCENARIO_KEY):
    """Return scenario metadata, defaulting to the normal case."""
    return SCENARIO_REGISTRY.get(scenario_key, SCENARIO_REGISTRY[DEFAULT_SCENARIO_KEY])


def create_scenario_result(scenario_key, annual_results=None):
    """Create the result envelope used by future multi-scenario execution."""
    scenario = get_scenario(scenario_key)
    return {
        "scenario_key": scenario["scenario_key"],
        "scenario_name": scenario["display_name"],
        "annual_results": annual_results,
    }


def apply_scenario_to_solver_input(input_obj, scenario_key=DEFAULT_SCENARIO_KEY):
    """Attach validated scenario metadata without changing calculation fields."""
    target = input_obj if input_obj is not None else {}
    target["scenario_key"] = get_scenario(scenario_key)["scenario_key"]
    return target
