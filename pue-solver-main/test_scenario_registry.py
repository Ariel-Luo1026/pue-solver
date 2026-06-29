import unittest

from cooling_system_registry import COOLING_SYSTEM_REGISTRY
from scenario_registry import (
    DEFAULT_SCENARIO_KEY,
    SCENARIO_REGISTRY,
    apply_scenario_to_solver_input,
    create_scenario_result,
)


class ScenarioRegistrySmokeTest(unittest.TestCase):
    def test_required_scenarios_and_default_exist(self):
        self.assertEqual(DEFAULT_SCENARIO_KEY, "normal_75")
        self.assertEqual(
            set(SCENARIO_REGISTRY), {"normal_75", "one_failure_three_active"}
        )
        self.assertEqual(SCENARIO_REGISTRY["normal_75"]["active_energy_modules"], 4)
        self.assertEqual(SCENARIO_REGISTRY["one_failure_three_active"]["failure_count"], 1)

    def test_scenario_key_can_be_added_to_standard_input_envelope(self):
        solver_input = {"cooling_system_type": "Chiller + Dry Cooler"}
        returned = apply_scenario_to_solver_input(solver_input, "normal_75")
        self.assertIs(returned, solver_input)
        self.assertEqual(returned["scenario_key"], "normal_75")

    def test_multi_scenario_result_envelope(self):
        result = create_scenario_result("normal_75", {"annual_average_PUE": 1.2})
        self.assertEqual(result["scenario_key"], "normal_75")
        self.assertEqual(result["annual_results"]["annual_average_PUE"], 1.2)

    def test_existing_default_registry_path_remains_valid(self):
        path = COOLING_SYSTEM_REGISTRY["Chiller + Dry Cooler"]["cooling_unit_capacities"]["2"]["power_sources"]["Grid"]
        self.assertTrue(path["white_space_equipment"])
        self.assertTrue(path["gray_space_equipment"])
        self.assertEqual(DEFAULT_SCENARIO_KEY, "normal_75")


if __name__ == "__main__":
    unittest.main()
