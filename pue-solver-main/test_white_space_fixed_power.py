import unittest
from copy import deepcopy

from configuration_library_loader import build_solver_input_from_library
from library_solver_adapter import convert_library_input_to_solver_input
from solver import compute_pue_project


class WhiteSpaceFixedPowerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outputs = {}
        cls.phase10a_pue = {}
        for scenario in ("Normal", "Failure"):
            adapted = convert_library_input_to_solver_input(
                build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, scenario)
            )
            cls.outputs[scenario] = compute_pue_project(adapted)
            without_white_space = deepcopy(adapted)
            without_white_space["equipment"].pop("library_fixed_power", None)
            without_white_space["library_context"].pop("auxiliary_equipment", None)
            cls.phase10a_pue[scenario] = compute_pue_project(without_white_space)["annual_results"]["annual_average_PUE"]

    def test_normal_hourly_fixed_power(self):
        hour = self.outputs["Normal"]["hourly_results"][0]
        self.assertGreater(hour["cdu_power_kW"], 0)
        self.assertGreater(hour["rtc_power_kW"], 0)
        self.assertGreater(hour["mau_power_kW"], 0)
        self.assertEqual(
            hour["white_space_equipment_power_kW"],
            hour["cdu_power_kW"] + hour["rtc_power_kW"] + hour["mau_power_kW"],
        )

    def test_failure_hourly_fixed_power(self):
        hour = self.outputs["Failure"]["hourly_results"][0]
        self.assertGreater(hour["cdu_power_kW"], 0)
        self.assertGreater(hour["rtc_power_kW"], 0)
        self.assertGreater(hour["mau_power_kW"], 0)
        self.assertEqual(
            hour["white_space_equipment_power_kW"],
            hour["cdu_power_kW"] + hour["rtc_power_kW"] + hour["mau_power_kW"],
        )

    def test_annual_fixed_power_energy(self):
        normal = self.outputs["Normal"]["annual_results"]
        normal_hour = self.outputs["Normal"]["hourly_results"][0]
        self.assertEqual(normal["annual_cdu_energy_kWh"], normal_hour["cdu_power_kW"] * 8760)
        self.assertEqual(normal["annual_rtc_energy_kWh"], normal_hour["rtc_power_kW"] * 8760)
        self.assertEqual(normal["annual_mau_energy_kWh"], normal_hour["mau_power_kW"] * 8760)
        self.assertEqual(
            normal["annual_white_space_equipment_energy_kWh"],
            normal_hour["white_space_equipment_power_kW"] * 8760,
        )
        failure = self.outputs["Failure"]["annual_results"]
        failure_hour = self.outputs["Failure"]["hourly_results"][0]
        self.assertEqual(
            failure["annual_white_space_equipment_energy_kWh"],
            failure_hour["white_space_equipment_power_kW"] * 8760,
        )

    def test_fixed_power_changes_pue_and_enters_mep_path(self):
        for scenario in ("Normal", "Failure"):
            output = self.outputs[scenario]
            annual = output["annual_results"]
            self.assertGreater(annual["annual_average_PUE"], self.phase10a_pue[scenario])
            hour = output["hourly_results"][0]
            self.assertGreater(hour["mep_upstream_power_kW"], hour["mep_terminal_load_kW"])


if __name__ == "__main__":
    unittest.main()
