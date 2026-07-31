import unittest
from copy import deepcopy
from unittest.mock import patch

from configuration_library_loader import build_solver_input_from_library
from topology_dispatcher import dispatch_topology


class ChillerDryCoolerRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library_input = build_solver_input_from_library(
            "CHILLER_DRYCOOLER_2MW_GRID", 2.0, "Normal"
        )
        cls.result = dispatch_topology(
            cls.library_input["configuration_manifest"],
            cls.library_input,
        )

    def test_topology_returns_annual_result(self):
        self.assertEqual(self.result["status"], "success")
        self.assertEqual(self.result["topology_id"], "chiller_dry_cooler")
        self.assertIn("annual_results", self.result)
        self.assertIn("annual_average_PUE", self.result["annual_results"])

    def test_returns_8760_hourly_records(self):
        self.assertEqual(len(self.result["hourly_results"]), 8760)

    def test_hourly_component_powers_exist(self):
        row = self.result["hourly_results"][0]

        self.assertIn("chiller_power_kW", row)
        self.assertIn("dry_cooler_power_kW", row)
        self.assertIn("chiller_performance_result", row)
        self.assertIn("dry_cooler_performance_result", row)
        self.assertIn("pump_power_kW", row)
        self.assertIn("electrical_loss_kW", row)
        self.assertIn("PUE", row)
        self.assertGreater(row["chiller_power_kW"], 0)
        self.assertGreater(row["dry_cooler_power_kW"], 0)
        self.assertGreater(row["pump_power_kW"], 0)
        self.assertGreater(row["facility_power_kW"], row["it_load_kW"])
        self.assertEqual(row["chiller_performance_result"]["equipment_type"], "CHILLER")
        self.assertEqual(row["dry_cooler_performance_result"]["equipment_type"], "DRY_COOLER")
        self.assertAlmostEqual(
            row["chiller_power_per_unit_kW"],
            row["chiller_performance_result"]["performance"]["power_kW"],
        )
        self.assertAlmostEqual(
            row["dry_cooler_power_per_unit_kW"],
            row["dry_cooler_performance_result"]["performance"]["power_kW"],
        )

    def test_annual_component_energy_exists(self):
        annual = self.result["annual_results"]

        self.assertIn("annual_chiller_energy_kWh", annual)
        self.assertIn("annual_dry_cooler_energy_kWh", annual)
        self.assertIn("annual_pump_energy_kWh", annual)
        self.assertIn("annual_electrical_loss_kWh", annual)
        self.assertGreater(annual["annual_chiller_energy_kWh"], 0)
        self.assertGreater(annual["annual_dry_cooler_energy_kWh"], 0)
        self.assertGreater(annual["annual_pump_energy_kWh"], 0)
        self.assertGreater(annual["annual_facility_energy_kWh"], annual["annual_IT_energy_kWh"])

    def test_failure_scenario_uses_fewer_active_units_and_higher_chiller_load_ratio(self):
        normal_input = build_solver_input_from_library(
            "CHILLER_DRYCOOLER_2MW_GRID", 4.0, "Normal"
        )
        failure_input = deepcopy(normal_input)
        failure_input["scenario_name"] = "Failure"
        failure_input["project"]["scenario_name"] = "Failure"

        normal_row = dispatch_topology(
            normal_input["configuration_manifest"], normal_input
        )["hourly_results"][23]
        failure_row = dispatch_topology(
            failure_input["configuration_manifest"], failure_input
        )["hourly_results"][23]

        self.assertEqual(normal_row["active_chiller_units"], 3)
        self.assertEqual(failure_row["active_chiller_units"], 2)
        self.assertEqual(normal_row["active_dry_cooler_units"], 3)
        self.assertEqual(failure_row["active_dry_cooler_units"], 2)
        self.assertEqual(normal_row["active_pump_units"], 3)
        self.assertEqual(failure_row["active_pump_units"], 2)
        self.assertGreater(failure_row["chiller_load_ratio"], normal_row["chiller_load_ratio"])
        self.assertLess(failure_row["chiller_COP"], normal_row["chiller_COP"])
        self.assertGreater(failure_row["chiller_power_kW"], normal_row["chiller_power_kW"])
        self.assertNotEqual(failure_row["dry_cooler_power_kW"], normal_row["dry_cooler_power_kW"])

    def test_pump_power_scales_by_active_pump_units(self):
        normal_input = build_solver_input_from_library(
            "CHILLER_DRYCOOLER_2MW_GRID", 4.0, "Normal"
        )
        failure_input = deepcopy(normal_input)
        failure_input["scenario_name"] = "Failure"
        failure_input["project"]["scenario_name"] = "Failure"

        normal_row = dispatch_topology(
            normal_input["configuration_manifest"], normal_input
        )["hourly_results"][23]
        failure_row = dispatch_topology(
            failure_input["configuration_manifest"], failure_input
        )["hourly_results"][23]

        self.assertAlmostEqual(
            normal_row["pump_power_kW"],
            normal_row["pump_power_per_unit_kW"] * normal_row["active_pump_units"],
        )
        self.assertAlmostEqual(
            failure_row["pump_power_kW"],
            failure_row["pump_power_per_unit_kW"] * failure_row["active_pump_units"],
        )
        self.assertAlmostEqual(normal_row["pump_power_per_unit_kW"], failure_row["pump_power_per_unit_kW"])

    def test_capacity_validation_reports_normal_and_failure_unit_scenarios(self):
        normal_input = build_solver_input_from_library(
            "CHILLER_DRYCOOLER_2MW_GRID", 4.0, "Normal"
        )
        failure_input = deepcopy(normal_input)
        failure_input["scenario_name"] = "Failure"
        failure_input["project"]["scenario_name"] = "Failure"

        for payload in (normal_input, failure_input):
            payload["peak_design_condition_override"] = {"extreme_db_max_C": 35.0}

        normal = dispatch_topology(
            normal_input["configuration_manifest"], normal_input
        )
        failure = dispatch_topology(
            failure_input["configuration_manifest"], failure_input
        )

        self.assertEqual(normal["capacity_validation"]["scenario_name"], "Normal")
        self.assertEqual(failure["capacity_validation"]["scenario_name"], "Failure")
        self.assertEqual(normal["capacity_validation"]["role_validations"]["chiller"]["active_units"], 3)
        self.assertEqual(failure["capacity_validation"]["role_validations"]["chiller"]["active_units"], 2)
        self.assertGreater(
            normal["capacity_validation"]["capacity_margin_kW"],
            failure["capacity_validation"]["capacity_margin_kW"],
        )
        self.assertIn("dry_cooler", normal["capacity_validation"]["role_validations"])
        self.assertIsNotNone(
            normal["capacity_validation"]["role_validations"]["dry_cooler"]["active_capacity_kW"]
        )

    def test_local_cache_peak_design_result_is_calculated(self):
        peak = self.result["peak_results"]
        self.assertEqual(peak["peak_design_weather_source"], "ASHRAE_local_cache")
        self.assertEqual(peak["peak_PUE_definition"], "peak_design")
        self.assertIsNotNone(peak["peak_design_outdoor_dry_bulb_C"])
        self.assertAlmostEqual(
            peak["peak_PUE"],
            peak["peak_design_facility_electrical_demand_kW"]
            / peak["peak_design_it_load_kW"],
        )

    def test_manual_peak_design_uses_same_equipment_runtime_at_design_temperature(self):
        payload = deepcopy(self.library_input)
        payload["peak_design_weather_source"] = "manual"
        payload["peak_design_outdoor_dry_bulb_C"] = 47.0
        payload["project"]["peak_design_weather_source"] = "manual"
        payload["project"]["peak_design_outdoor_dry_bulb_C"] = 47.0

        result = dispatch_topology(payload["configuration_manifest"], payload)
        peak = result["peak_results"]
        point = peak["peak_design_equipment_result"]

        self.assertEqual(peak["peak_design_weather_source"], "manual")
        self.assertEqual(peak["peak_design_outdoor_dry_bulb_C"], 47.0)
        self.assertNotEqual(47.0, max(row["ambient_dry_bulb_C"] for row in result["hourly_results"]))
        self.assertEqual(point["ambient_dry_bulb_C"], 47.0)
        self.assertEqual(peak["peak_design_cooling_load_kW"], point["cooling_load_kW"])
        self.assertEqual(peak["peak_design_chiller_power_kW"], point["chiller_power_kW"])
        self.assertEqual(peak["peak_design_dry_cooler_power_kW"], point["dry_cooler_power_kW"])
        self.assertEqual(peak["peak_design_CHW_pump_power_kW"], point["pump_power_kW"])
        self.assertEqual(peak["peak_design_electrical_loss_kW"], point["electrical_loss_kW"])
        self.assertEqual(peak["peak_design_facility_electrical_demand_kW"], point["facility_power_kW"])
        self.assertAlmostEqual(peak["peak_PUE"], point["facility_power_kW"] / point["it_load_kW"])

    def test_unavailable_design_condition_does_not_retain_hourly_pue(self):
        unavailable = {
            "source": "ASHRAE_online",
            "lookup_status": "failed",
            "failure_reason": "no valid design condition",
            "extreme_db_max_C": None,
        }
        with patch("solver._peak_design_weather_condition", return_value=unavailable):
            result = dispatch_topology(
                self.library_input["configuration_manifest"],
                deepcopy(self.library_input),
            )

        peak = result["peak_results"]
        self.assertEqual(peak["peak_PUE_definition"], "unavailable")
        self.assertIsNone(peak["peak_PUE"])
        self.assertIsNone(peak["peak_design_facility_electrical_demand_kW"])
        self.assertEqual(peak["peak_design_lookup_status"], "failed")


if __name__ == "__main__":
    unittest.main()
