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
        cls.without_white_space_outputs = {}
        for scenario in ("Normal", "Failure"):
            adapted = convert_library_input_to_solver_input(
                build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, scenario)
            )
            cls.outputs[scenario] = compute_pue_project(adapted)
            without_white_space = deepcopy(adapted)
            without_white_space["equipment"].pop("library_fixed_power", None)
            without_white_space.pop("library_context", None)
            cls.without_white_space_outputs[scenario] = compute_pue_project(without_white_space)
            cls.phase10a_pue[scenario] = cls.without_white_space_outputs[scenario]["annual_results"]["annual_average_PUE"]

    def test_normal_hourly_fixed_power(self):
        hour = self.outputs["Normal"]["hourly_results"][0]
        self.assertGreater(hour["cdu_power_kW"], 0)
        self.assertGreater(hour["rtc_power_kW"], 0)
        self.assertGreater(hour["mau_power_kW"], 0)
        self.assertEqual(hour["cdu_curve_source"], "configuration_library_solver_curve")
        self.assertEqual(hour["rtc_curve_source"], "configuration_library_solver_curve")
        self.assertEqual(hour["mau_curve_source"], "configuration_library_solver_curve")
        self.assertEqual(
            hour["white_space_equipment_power_kW"],
            hour["cdu_power_kW"] + hour["rtc_power_kW"] + hour["mau_power_kW"],
        )

    def test_failure_hourly_fixed_power(self):
        hour = self.outputs["Failure"]["hourly_results"][0]
        self.assertGreater(hour["cdu_power_kW"], 0)
        self.assertGreater(hour["rtc_power_kW"], 0)
        self.assertGreater(hour["mau_power_kW"], 0)
        self.assertEqual(hour["cdu_curve_source"], "configuration_library_solver_curve")
        self.assertEqual(hour["rtc_curve_source"], "configuration_library_solver_curve")
        self.assertEqual(hour["mau_curve_source"], "configuration_library_solver_curve")
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
        self.assertEqual(normal["cdu_curve_source"], "configuration_library_solver_curve")
        self.assertEqual(normal["rtc_curve_source"], "configuration_library_solver_curve")
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
            hour = output["hourly_results"][0]
            baseline_hour = self.without_white_space_outputs[scenario]["hourly_results"][0]
            self.assertGreater(
                hour["non_radiator_facility_power_kW"],
                baseline_hour["non_radiator_facility_power_kW"],
            )
            self.assertGreater(hour["mep_upstream_power_kW"], hour["mep_terminal_load_kW"])

    def test_missing_mau_curve_fails_in_configuration_library_mode(self):
        adapted = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        for key in list(adapted["equipment"]["library_fixed_power"]):
            if str(key).upper().startswith("MAU"):
                adapted["equipment"]["library_fixed_power"].pop(key)

        output = compute_pue_project(adapted)

        self.assertIn("error", output)
        self.assertIn("MAU_1&2 Solver_Curve missing or invalid", output["error"])
        self.assertEqual(output["hourly_results"], [])

    def test_invalid_mau_curve_fails_in_configuration_library_mode(self):
        adapted = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        for binding in adapted["equipment"]["library_fixed_power"].values():
            if str(binding.get("equipment_id", "")).upper().startswith("MAU"):
                binding["curve_data"] = [
                    {"load_ratio": 0.5, "power_kW": 8},
                    {"load_ratio": 0.5, "power_kW": 9},
                ]

        output = compute_pue_project(adapted)

        self.assertIn("error", output)
        self.assertIn("MAU_1&2 Solver_Curve missing or invalid", output["error"])
        self.assertIn("Duplicate", output["error"])
        self.assertEqual(output["hourly_results"], [])

    def test_missing_rtc_curve_fails_in_configuration_library_mode(self):
        adapted = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        for key in list(adapted["equipment"]["library_fixed_power"]):
            if str(key).upper().startswith("RTC"):
                adapted["equipment"]["library_fixed_power"].pop(key)

        output = compute_pue_project(adapted)

        self.assertIn("error", output)
        self.assertIn("RTC_1&2 Solver_Curve missing or invalid", output["error"])
        self.assertEqual(output["hourly_results"], [])

    def test_invalid_rtc_curve_fails_in_configuration_library_mode(self):
        adapted = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        for binding in adapted["equipment"]["library_fixed_power"].values():
            if str(binding.get("equipment_id", "")).upper().startswith("RTC"):
                binding["curve_data"] = [
                    {"load_ratio": 0.5, "power_kW": 8},
                    {"load_ratio": 0.5, "power_kW": 9},
                ]

        output = compute_pue_project(adapted)

        self.assertIn("error", output)
        self.assertIn("RTC_1&2 Solver_Curve missing or invalid", output["error"])
        self.assertIn("Duplicate", output["error"])
        self.assertEqual(output["hourly_results"], [])

    def test_missing_cdu_curve_fails_in_configuration_library_mode(self):
        adapted = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        for key in list(adapted["equipment"]["library_fixed_power"]):
            if str(key).upper().startswith("CDU"):
                adapted["equipment"]["library_fixed_power"].pop(key)

        output = compute_pue_project(adapted)

        self.assertIn("error", output)
        self.assertIn("CDU_2 Solver_Curve missing or invalid", output["error"])
        self.assertEqual(output["hourly_results"], [])

    def test_invalid_cdu_curve_fails_in_configuration_library_mode(self):
        adapted = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        for binding in adapted["equipment"]["library_fixed_power"].values():
            if str(binding.get("equipment_id", "")).upper().startswith("CDU"):
                binding["curve_data"] = [
                    {"load_ratio": 0.5, "power_kW": 11},
                    {"load_ratio": 0.5, "power_kW": 12},
                ]

        output = compute_pue_project(adapted)

        self.assertIn("error", output)
        self.assertIn("CDU_2 Solver_Curve missing or invalid", output["error"])
        self.assertIn("Duplicate", output["error"])
        self.assertEqual(output["hourly_results"], [])


if __name__ == "__main__":
    unittest.main()
