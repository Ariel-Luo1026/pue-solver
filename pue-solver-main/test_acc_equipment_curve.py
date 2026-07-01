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
            self.assertIn("ACC_2:Solver_Curve:ambient_power_input_kW", hour["acc_curve_source"])
            self.assertGreater(hour["acc_load_ratio"], 0)
            self.assertIsNotNone(hour["acc_ambient_C"])
            self.assertGreater(hour["acc_temperature_power_factor"], 0)

    def test_annual_acc_metrics(self):
        for scenario in ("Normal", "Failure"):
            annual = self.results[scenario]["annual_results"]
            self.assertGreater(annual["annual_acc_energy_kWh"], 0)
            self.assertGreater(annual["average_acc_cop"], 0)
            self.assertGreater(annual["max_acc_power_kW"], 0)
            self.assertEqual(annual["acc_curve_source"], "ACC_2:Solver_Curve:ambient_power_input_kW")
            self.assertGreater(annual["min_acc_cop"], 0)
            self.assertGreaterEqual(annual["max_acc_cop"], annual["min_acc_cop"])
            self.assertGreater(annual["average_acc_temperature_power_factor"], 0)

    def test_explicit_acc_curve_changes_phase10b_pue(self):
        for scenario in ("Normal", "Failure"):
            self.assertNotAlmostEqual(
                self.results[scenario]["annual_results"]["annual_average_PUE"],
                self.phase10b_pue[scenario],
            )

    def test_outdoor_temperature_changes_annual_acc_energy(self):
        energies = {}
        for temperature in (-10.0, 45.0):
            adapted = convert_library_input_to_solver_input(
                build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
            )
            adapted["weather"]["hourly_data"]["dry_bulb_C"] = [temperature] * 8760
            output = compute_pue_project(adapted)
            energies[temperature] = output["annual_results"]["annual_acc_energy_kWh"]
        self.assertLess(energies[-10.0], energies[45.0])

    def test_load_ratio_fallback_when_ambient_is_missing(self):
        adapted = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        for row in adapted["acc_curve"]["data"]:
            row.pop("ambient_C", None)
        output = compute_pue_project(adapted)
        hour = output["hourly_results"][0]
        self.assertGreater(hour["acc_power_kW"], 0)
        self.assertIn("ACC_2:Solver_Curve:power_input_kW", hour["acc_curve_source"])
        self.assertIsNone(hour["acc_ambient_C"])
        self.assertIsNone(hour["acc_temperature_power_factor"])


if __name__ == "__main__":
    unittest.main()
