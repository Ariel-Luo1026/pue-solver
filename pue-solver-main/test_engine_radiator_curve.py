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
            no_radiator["engine_radiator_curve"]["data"] = [
                {**row, "power_kW": 0.0}
                for row in no_radiator["engine_radiator_curve"]["data"]
            ]
            cls.without_radiator[scenario] = compute_pue_project(no_radiator)

    def test_scenario_specific_radiator_curves(self):
        for scenario in ("Normal", "Failure"):
            self.assertIn(
                self.inputs[scenario]["engine_radiator_curve"]["source_sheet"],
                {"Solver_Curve", f"Solver_Curve_{scenario}"},
            )
            self.assertTrue(self.inputs[scenario]["engine_radiator_curve"]["data"])

    def test_hourly_radiator_power_enters_mep_terminal_load(self):
        for scenario in ("Normal", "Failure"):
            hour = self.outputs[scenario]["hourly_results"][0]
            expected_power = hour["engine_radiator_power_kW"]
            self.assertGreater(expected_power, 0.0)
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

    def test_radiator_load_ratio_uses_non_radiator_facility_demand(self):
        for scenario in ("Normal", "Failure"):
            output = self.outputs[scenario]
            annual_peak = max(row["non_radiator_facility_power_kW"] for row in output["hourly_results"])
            for hour in output["hourly_results"]:
                failure_peak = hour["failure_peak_non_radiator_facility_power_kW"]
                expected_ratio = hour["non_radiator_facility_power_kW"] / failure_peak
                previous_ratio = hour["cooling_load_kW"] / (
                    hour["engine_radiator_active_units"]
                    * hour["engine_radiator_reference_capacity_kW"]
                )
                self.assertAlmostEqual(hour["engine_radiator_load_ratio"], expected_ratio)
                self.assertAlmostEqual(
                    hour["engine_radiator_previous_cooling_load_ratio"], previous_ratio
                )
                self.assertEqual(
                    hour["engine_radiator_load_ratio_basis"],
                    "non_radiator_facility_demand_ratio",
                )
                self.assertEqual(
                    hour["engine_radiator_reference_power_kW"],
                    failure_peak,
                )
                self.assertEqual(hour["engine_radiator_peak_reference_power_kW"], failure_peak)
                self.assertEqual(
                    hour["engine_radiator_reference_basis"],
                    "failure_scenario_peak_non_radiator_facility_demand",
                )
                self.assertEqual(
                    hour["engine_radiator_previous_annual_max_reference_kW"], annual_peak
                )
                self.assertAlmostEqual(
                    hour["engine_radiator_previous_annual_max_load_ratio"],
                    hour["non_radiator_facility_power_kW"] / annual_peak,
                )

    def test_radiator_curve_receives_non_radiator_facility_demand_ratio(self):
        sample = deepcopy(self.inputs["Normal"])
        sample["project"]["it_load"]["hourly_it_load_kW"] = [2200, 4400]
        sample["weather"]["hourly_data"]["dry_bulb_C"] = [25, 25]
        sample["weather"]["hourly_data"]["hour_index"] = [1, 2]
        sample["engine_radiator_curve"]["data"] = [
            {"load_ratio": 0.1, "power_kW": 10},
            {"load_ratio": 1.0, "power_kW": 100},
        ]

        output = compute_pue_project(sample)
        low_hour, peak_hour = output["hourly_results"]

        self.assertAlmostEqual(
            low_hour["engine_radiator_load_ratio_lookup"],
            max(0.1, low_hour["engine_radiator_load_ratio"]),
        )
        self.assertAlmostEqual(
            low_hour["engine_radiator_power_kW"],
            low_hour["engine_radiator_load_ratio_lookup"]
            * 100
            * low_hour["engine_radiator_active_units"],
        )
        self.assertGreater(peak_hour["engine_radiator_load_ratio"], 0.0)

    def test_annual_radiator_metrics_and_pue_change(self):
        for scenario in ("Normal", "Failure"):
            annual = self.outputs[scenario]["annual_results"]
            baseline = self.without_radiator[scenario]["annual_results"]
            hourly_power = [row["engine_radiator_power_kW"] for row in self.outputs[scenario]["hourly_results"]]
            self.assertAlmostEqual(annual["annual_engine_radiator_energy_kWh"], sum(hourly_power))
            self.assertEqual(annual["max_engine_radiator_power_kW"], max(hourly_power))
            self.assertEqual(annual["engine_radiator_curve_source"], "configuration_library_solver_curve")
            self.assertEqual(annual["engine_radiator_curve_type"], "one_dimensional_power")
            self.assertGreater(annual["annual_average_PUE"], baseline["annual_average_PUE"])
            self.assertGreater(annual["annual_PUE_engine_radiator_impact"], 0.0)
            self.assertAlmostEqual(
                annual["annual_average_PUE"] - annual["annual_PUE_without_engine_radiator"],
                annual["annual_PUE_engine_radiator_impact"],
            )

    def test_non_radiator_facility_demand_is_pre_radiator_and_non_circular(self):
        for scenario in ("Normal", "Failure"):
            output = self.outputs[scenario]
            for hour in output["hourly_results"]:
                expected_terminal = (
                    hour["IT_load_kW"]
                    + hour["cooling_power_kW"]
                    + hour["pump_power_kW"]
                    + hour["airflow_power_kW"]
                    + hour["auxiliary_power_kW"]
                    + hour["white_space_equipment_power_kW"]
                )
                self.assertAlmostEqual(hour["non_radiator_terminal_power_kW"], expected_terminal)
                self.assertAlmostEqual(
                    hour["non_radiator_facility_power_kW"],
                    expected_terminal + hour["non_radiator_electrical_loss_kW"],
                )
                self.assertAlmostEqual(
                    hour["it_terminal_load_kW"] + hour["mep_terminal_load_kW"],
                    expected_terminal + hour["engine_radiator_power_kW"],
                )
                self.assertEqual(
                    hour["engine_radiator_future_load_ratio_basis"],
                    "Non-radiator facility demand ratio",
                )
                self.assertEqual(
                    hour["engine_3_power_boundary"],
                    "generation_side_excluded_from_facility_power",
                )
                self.assertEqual(
                    hour["engine_radiator_power_boundary"],
                    "facility_auxiliary_electrical_load",
                )

            expected_peak = max(
                output["hourly_results"],
                key=lambda row: row["non_radiator_facility_power_kW"],
            )
            self.assertEqual(
                output["peak_results"]["peak_non_radiator_facility_power_kW"],
                expected_peak["non_radiator_facility_power_kW"],
            )
            self.assertEqual(
                output["peak_results"]["peak_non_radiator_facility_hour_index"],
                expected_peak["hour_index"],
            )
            self.assertEqual(
                output["peak_results"]["peak_non_radiator_facility_definition"],
                "annual_maximum",
            )

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
