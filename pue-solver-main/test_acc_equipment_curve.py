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
            without_explicit_acc.pop("library_context", None)
            cls.phase10b_pue[scenario] = compute_pue_project(without_explicit_acc)["annual_results"]["annual_average_PUE"]

    def test_acc_curve_is_used_in_hourly_results(self):
        for scenario in ("Normal", "Failure"):
            hour = self.results[scenario]["hourly_results"][0]
            self.assertGreater(hour["acc_power_kW"], 0)
            self.assertGreater(hour["acc_cop"], 0)
            self.assertEqual("configuration_library_solver_curve", hour["acc_curve_source"])
            self.assertGreater(hour["acc_load_ratio"], 0)
            self.assertIsNotNone(hour["acc_ambient_C"])
            self.assertIsNone(hour["acc_temperature_power_factor"])
            self.assertEqual(hour["acc_lookup_basis"], "ambient_C+required_capacity_per_unit_kW")

    def test_annual_acc_metrics(self):
        for scenario in ("Normal", "Failure"):
            annual = self.results[scenario]["annual_results"]
            self.assertGreater(annual["annual_acc_energy_kWh"], 0)
            self.assertGreater(annual["average_acc_cop"], 0)
            self.assertGreater(annual["max_acc_power_kW"], 0)
            self.assertEqual(annual["acc_curve_source"], "configuration_library_solver_curve")
            self.assertGreater(annual["min_acc_cop"], 0)
            self.assertGreaterEqual(annual["max_acc_cop"], annual["min_acc_cop"])
            self.assertIsNone(annual["average_acc_temperature_power_factor"])

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

    def test_capacity_surface_without_ambient_fails_instead_of_using_legacy_fallback(self):
        adapted = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        for row in adapted["acc_curve"]["data"]:
            row.pop("ambient_C", None)
        with self.assertRaisesRegex(ValueError, "ambient_C"):
            compute_pue_project(adapted)

    def test_chw_pump_uses_configuration_library_solver_curve(self):
        output = self.results["Normal"]
        hour = output["hourly_results"][0]

        self.assertEqual(
            output["annual_results"]["chw_pump_curve_source"],
            "configuration_library_solver_curve",
        )
        self.assertEqual(hour["chw_pump_curve_source"], "configuration_library_solver_curve")
        self.assertEqual(hour["pump_power_details"][0]["source"], "configuration_library_solver_curve")
        self.assertEqual(hour["pump_power_details"][0]["curve_ref"], "CHW_PUMP_2_power_vs_load")
        self.assertGreater(hour["pump_power_kW"], 0)

    def test_chw_pump_invalid_configuration_curve_fails_without_legacy_fallback(self):
        adapted = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        adapted["curve_library"]["curves"]["CHW_PUMP_2_power_vs_load"]["data"] = []

        output = compute_pue_project(adapted)

        self.assertIn("error", output)
        self.assertIn("CHW_PUMP_2 Solver_Curve missing or invalid", output["error"])
        self.assertIn("load_ratio", output["error"])
        self.assertIn("power_kW", output["error"])
        self.assertEqual(output["hourly_results"], [])
        self.assertEqual(output["annual_results"], {})
        self.assertTrue(output["validation"]["errors"])

    def test_chw_pump_missing_configuration_curve_fails_without_legacy_fallback(self):
        adapted = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        adapted["curve_library"]["curves"].pop("CHW_PUMP_2_power_vs_load")

        output = compute_pue_project(adapted)

        self.assertIn("error", output)
        self.assertIn("CHW_PUMP_2 Solver_Curve missing or invalid", output["error"])
        self.assertIn("load_ratio", output["error"])
        self.assertIn("power_kW", output["error"])
        self.assertEqual(output["hourly_results"], [])
        self.assertEqual(output["annual_results"], {})

    def test_chw_pump_duplicate_configuration_curve_fails_without_legacy_fallback(self):
        adapted = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        adapted["curve_library"]["curves"]["CHW_PUMP_2_power_vs_load"]["data"] = [
            {"load_ratio": 0.5, "power_kW": 15},
            {"load_ratio": 0.5, "power_kW": 16},
        ]

        output = compute_pue_project(adapted)

        self.assertIn("error", output)
        self.assertIn("CHW_PUMP_2 Solver_Curve missing or invalid", output["error"])
        self.assertIn("Duplicate CHW_PUMP_2 load_ratio point", output["error"])
        self.assertEqual(output["hourly_results"], [])
        self.assertEqual(output["annual_results"], {})

    def test_without_configuration_library_pump_reference_keeps_legacy_pump_behavior(self):
        adapted = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        adapted.pop("library_context", None)
        adapted["curve_library"] = {"curves": {}}
        adapted["equipment"]["cooling"]["pumps"].pop("source_equipment_id", None)
        adapted["equipment"]["cooling"]["pumps"]["power_curve_refs"] = []

        output = compute_pue_project(adapted)
        hour = output["hourly_results"][0]

        self.assertEqual(output["annual_results"]["chw_pump_curve_source"], "legacy_non_configuration_mode")
        self.assertEqual(hour["chw_pump_curve_source"], "legacy_non_configuration_mode")
        self.assertEqual(hour["pump_power_details"], [])
        self.assertEqual(hour["pump_power_kW"], 0.01 * hour["IT_load_kW"])


if __name__ == "__main__":
    unittest.main()
