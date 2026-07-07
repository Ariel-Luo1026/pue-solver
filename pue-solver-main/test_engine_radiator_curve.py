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
            no_radiator.pop("library_context", None)
            cls.without_radiator[scenario] = compute_pue_project(no_radiator)

    def test_scenario_specific_radiator_curves(self):
        self.assertEqual(self.inputs["Normal"]["engine_radiator_curve"]["source_sheet"], "Solver_Curve_Normal")
        self.assertEqual(self.inputs["Failure"]["engine_radiator_curve"]["source_sheet"], "Solver_Curve_Failure")

    def test_hourly_radiator_power_enters_mep_terminal_load(self):
        expected = {"Normal": 120.0, "Failure": 108.0}
        for scenario, expected_power in expected.items():
            hour = self.outputs[scenario]["hourly_results"][0]
            self.assertEqual(hour["engine_radiator_power_kW"], expected_power)
            self.assertAlmostEqual(
                hour["mep_terminal_load_kW"],
                hour["cooling_power_kW"]
                + hour["pump_power_kW"]
                + hour["airflow_power_kW"]
                + hour["auxiliary_power_kW"]
                + hour["white_space_equipment_power_kW"]
                + expected_power,
            )
            self.assertEqual(hour["engine_radiator_curve_source"], "configuration_library_solver_curve")
            self.assertEqual(hour["engine_radiator_curve_type"], "one_dimensional_power")

    def test_annual_radiator_metrics_and_pue_change(self):
        expected_power = {"Normal": 120.0, "Failure": 108.0}
        for scenario, power in expected_power.items():
            annual = self.outputs[scenario]["annual_results"]
            baseline = self.without_radiator[scenario]["annual_results"]
            self.assertEqual(annual["annual_engine_radiator_energy_kWh"], power * 8760)
            self.assertEqual(annual["max_engine_radiator_power_kW"], power)
            self.assertEqual(annual["engine_radiator_curve_source"], "configuration_library_solver_curve")
            self.assertEqual(annual["engine_radiator_curve_type"], "one_dimensional_power")
            self.assertGreater(annual["annual_average_PUE"], baseline["annual_average_PUE"])

    def test_missing_radiator_curve_fails_in_configuration_library_mode(self):
        sample = deepcopy(self.inputs["Normal"])
        sample.pop("engine_radiator_curve", None)

        output = compute_pue_project(sample)

        self.assertIn("error", output)
        self.assertIn("ENGINE_RADIATOR_1 Solver_Curve missing or invalid", output["error"])
        self.assertEqual(output["hourly_results"], [])

    def test_invalid_radiator_curve_fails_in_configuration_library_mode(self):
        sample = deepcopy(self.inputs["Normal"])
        sample["engine_radiator_curve"]["data"] = [
            {"load_ratio": 0.5, "power_kW": 30},
            {"load_ratio": 0.5, "power_kW": 31},
        ]

        output = compute_pue_project(sample)

        self.assertIn("error", output)
        self.assertIn("ENGINE_RADIATOR_1 Solver_Curve missing or invalid", output["error"])
        self.assertIn("Duplicate", output["error"])
        self.assertEqual(output["hourly_results"], [])


if __name__ == "__main__":
    unittest.main()
