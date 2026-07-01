import unittest
from copy import deepcopy

from configuration_library_loader import build_solver_input_from_library
from library_solver_adapter import convert_library_input_to_solver_input
from solver import compute_pue_project


class EngineRadiatorCurveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = {}
        cls.outputs = {}
        cls.without_radiator = {}
        for scenario in ("Normal", "Failure"):
            adapted = convert_library_input_to_solver_input(
                build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, scenario)
            )
            cls.inputs[scenario] = adapted
            cls.outputs[scenario] = compute_pue_project(adapted)
            no_radiator = deepcopy(adapted)
            no_radiator.pop("engine_radiator_curve", None)
            cls.without_radiator[scenario] = compute_pue_project(no_radiator)

    def test_scenario_specific_radiator_curves(self):
        self.assertEqual(self.inputs["Normal"]["engine_radiator_curve"]["source_sheet"], "Solver_Curve_Normal")
        self.assertEqual(self.inputs["Failure"]["engine_radiator_curve"]["source_sheet"], "Solver_Curve_Failure")

    def test_hourly_radiator_power_enters_mep_terminal_load(self):
        expected = {"Normal": 120.0, "Failure": 108.0}
        for scenario, expected_power in expected.items():
            hour = self.outputs[scenario]["hourly_results"][0]
            baseline = self.without_radiator[scenario]["hourly_results"][0]
            self.assertEqual(hour["engine_radiator_power_kW"], expected_power)
            self.assertAlmostEqual(
                hour["mep_terminal_load_kW"],
                baseline["mep_terminal_load_kW"] + expected_power,
            )
            self.assertIn("ENGINE_RADIATOR_2", hour["engine_radiator_curve_source"])

    def test_annual_radiator_metrics_and_pue_change(self):
        expected_power = {"Normal": 120.0, "Failure": 108.0}
        for scenario, power in expected_power.items():
            annual = self.outputs[scenario]["annual_results"]
            baseline = self.without_radiator[scenario]["annual_results"]
            self.assertEqual(annual["annual_engine_radiator_energy_kWh"], power * 8760)
            self.assertEqual(annual["max_engine_radiator_power_kW"], power)
            self.assertGreater(annual["annual_average_PUE"], baseline["annual_average_PUE"])


if __name__ == "__main__":
    unittest.main()
