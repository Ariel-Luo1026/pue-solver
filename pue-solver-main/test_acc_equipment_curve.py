import unittest
from copy import deepcopy

from configuration_library_loader import build_solver_input_from_library
from library_solver_adapter import convert_library_input_to_solver_input
from solver import compute_pue_project


class AccEquipmentCurveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = {}
        cls.phase10b_pue = {}
        for scenario in ("Normal", "Failure"):
            adapted = convert_library_input_to_solver_input(
                build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, scenario)
            )
            cls.results[scenario] = compute_pue_project(adapted)
            without_explicit_acc = deepcopy(adapted)
            without_explicit_acc.pop("acc_curve", None)
            without_explicit_acc["library_context"].pop("acc_curve", None)
            cls.phase10b_pue[scenario] = compute_pue_project(without_explicit_acc)["annual_results"]["annual_average_PUE"]

    def test_acc_curve_is_used_in_hourly_results(self):
        for scenario in ("Normal", "Failure"):
            hour = self.results[scenario]["hourly_results"][0]
            self.assertGreater(hour["acc_power_kW"], 0)
            self.assertGreater(hour["acc_cop"], 0)
            self.assertIn("ACC_2:Solver_Curve:power_input_kW", hour["acc_curve_source"])
            self.assertGreater(hour["acc_load_ratio"], 0)

    def test_annual_acc_metrics(self):
        for scenario in ("Normal", "Failure"):
            annual = self.results[scenario]["annual_results"]
            self.assertGreater(annual["annual_acc_energy_kWh"], 0)
            self.assertGreater(annual["average_acc_cop"], 0)
            self.assertGreater(annual["max_acc_power_kW"], 0)
            self.assertEqual(annual["acc_curve_source"], "ACC_2:Solver_Curve:power_input_kW")

    def test_explicit_acc_curve_changes_phase10b_pue(self):
        for scenario in ("Normal", "Failure"):
            self.assertNotAlmostEqual(
                self.results[scenario]["annual_results"]["annual_average_PUE"],
                self.phase10b_pue[scenario],
            )


if __name__ == "__main__":
    unittest.main()
