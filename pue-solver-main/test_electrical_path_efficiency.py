import unittest
from copy import deepcopy

from configuration_library_loader import build_solver_input_from_library
from library_solver_adapter import convert_library_input_to_solver_input
from solver import compute_pue_project


class ElectricalPathEfficiencyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        library_input = build_solver_input_from_library(
            "ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal"
        )
        cls.adapted = convert_library_input_to_solver_input(library_input)
        cls.with_path = compute_pue_project(cls.adapted)
        without_path_input = deepcopy(cls.adapted)
        without_path_input.pop("electrical_path", None)
        without_path_input.get("equipment", {}).pop("electrical_path", None)
        without_path_input.pop("library_context", None)
        cls.without_path = compute_pue_project(without_path_input)

    def test_hourly_it_and_mep_path_formulas(self):
        hour = self.with_path["hourly_results"][0]
        expected_it_loss = hour["it_terminal_load_kW"] / 0.9723 - hour["it_terminal_load_kW"]
        expected_mep_loss = hour["mep_terminal_load_kW"] / 0.9959 - hour["mep_terminal_load_kW"]
        self.assertAlmostEqual(hour["it_electrical_loss_kW"], expected_it_loss)
        self.assertAlmostEqual(hour["mep_electrical_loss_kW"], expected_mep_loss)
        self.assertAlmostEqual(
            hour["electrical_loss_kW"],
            hour["it_electrical_loss_kW"] + hour["mep_electrical_loss_kW"],
        )
        self.assertEqual(hour["electrical_distribution_curve_source"], "configuration_library_solver_curve")
        self.assertEqual(hour["electrical_distribution_curve_type"], "efficiency")
        self.assertAlmostEqual(
            hour["electrical_distribution_base_power_kW"],
            hour["it_terminal_load_kW"] + hour["mep_terminal_load_kW"],
        )
        self.assertAlmostEqual(hour["it_upstream_power_kW"], hour["it_terminal_load_kW"] / 0.9723)
        self.assertAlmostEqual(hour["mep_upstream_power_kW"], hour["mep_terminal_load_kW"] / 0.9959)

    def test_annual_losses_and_energy_balances(self):
        annual = self.with_path["annual_results"]
        self.assertGreater(annual["annual_electrical_loss_kWh"], 0)
        self.assertGreater(annual["annual_it_electrical_loss_kWh"], 0)
        self.assertGreater(annual["annual_mep_electrical_loss_kWh"], 0)
        self.assertEqual(annual["electrical_distribution_curve_source"], "configuration_library_solver_curve")
        self.assertEqual(annual["electrical_distribution_curve_type"], "efficiency")
        self.assertAlmostEqual(
            annual["annual_electrical_loss_kWh"],
            annual["annual_it_electrical_loss_kWh"] + annual["annual_mep_electrical_loss_kWh"],
        )
        self.assertAlmostEqual(
            annual["annual_IT_upstream_energy_kWh"],
            annual["annual_IT_terminal_energy_kWh"] + annual["annual_it_electrical_loss_kWh"],
        )
        self.assertAlmostEqual(
            annual["annual_MEP_upstream_energy_kWh"],
            annual["annual_MEP_terminal_energy_kWh"] + annual["annual_mep_electrical_loss_kWh"],
        )

    def test_pue_uses_terminal_it_denominator_and_differs_from_legacy(self):
        annual = self.with_path["annual_results"]
        self.assertAlmostEqual(
            annual["annual_average_PUE"],
            annual["annual_facility_energy_kWh"] / annual["annual_IT_terminal_energy_kWh"],
        )
        self.assertNotAlmostEqual(
            annual["annual_average_PUE"],
            self.without_path["annual_results"]["annual_average_PUE"],
        )

    def test_missing_electrical_distribution_fails_in_configuration_library_mode(self):
        adapted = deepcopy(self.adapted)
        adapted.pop("electrical_path", None)
        adapted.get("equipment", {}).pop("electrical_path", None)

        output = compute_pue_project(adapted)

        self.assertIn("error", output)
        self.assertIn("ELECTRICAL_DISTRIBUTION_2 Solver_Curve missing or invalid", output["error"])
        self.assertEqual(output["hourly_results"], [])

    def test_invalid_electrical_distribution_fails_in_configuration_library_mode(self):
        adapted = deepcopy(self.adapted)
        adapted["electrical_path"]["it_efficiency"] = 0.0

        output = compute_pue_project(adapted)

        self.assertIn("error", output)
        self.assertIn("ELECTRICAL_DISTRIBUTION_2 Solver_Curve missing or invalid", output["error"])
        self.assertEqual(output["hourly_results"], [])


if __name__ == "__main__":
    unittest.main()
