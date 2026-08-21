import unittest
from copy import deepcopy

from configuration_library_loader import build_solver_input_from_library
from topology_dispatcher import dispatch_topology
from topology_adapters.chiller_dry_cooler_runtime import ChillerDryCoolerRuntimeError


class CWPumpFrameworkTest(unittest.TestCase):
    def _input(self, scenario="Normal"):
        payload = build_solver_input_from_library("CHILLER_DRYCOOLER_2MW_GRID", 4.0, "Normal")
        payload["scenario_name"] = scenario
        payload["project"]["scenario_name"] = scenario
        return payload

    def _run(self, scenario="Normal"):
        payload = self._input(scenario)
        return payload, dispatch_topology(payload["configuration_manifest"], payload)

    def test_binding_and_single_curve_resolve(self):
        payload = self._input()
        self.assertEqual(payload["configuration_manifest"]["equipment_roles"]["cw_pump"], "CW_PUMP_6")
        selected = payload["selected_curves"]["CW_PUMP_6"]
        self.assertEqual(selected["sheet_name"], "Solver_Curve")
        self.assertEqual(set(selected["curve"][0]), {"load_ratio", "power_kW"})

    def test_cw_uses_heat_rejection_while_chw_uses_cooling_load(self):
        _, output = self._run()
        row = output["hourly_results"][0]
        self.assertAlmostEqual(row["cw_pump_heat_rejection_load_kW"], row["cooling_load_kW"] + row["chiller_power_kW"])
        self.assertAlmostEqual(
            row["cw_pump_load_ratio_raw"],
            row["cw_pump_heat_rejection_load_kW"] / (row["cw_pump_active_unit_count"] * row["cw_pump_reference_capacity_per_unit_kW"]),
        )
        self.assertAlmostEqual(
            row["pump_load_ratio_raw"],
            row["cooling_load_kW"] / (row["pump_active_unit_count"] * row["pump_reference_capacity_per_unit_kW"]),
        )

    def test_normal_and_failure_share_curve_but_failure_ratio_is_higher(self):
        normal_input, normal = self._run("Normal")
        failure_input, failure = self._run("Failure")
        normal_row, failure_row = normal["hourly_results"][0], failure["hourly_results"][0]
        self.assertEqual(normal_input["selected_curves"]["CW_PUMP_6"]["sheet_name"], "Solver_Curve")
        self.assertEqual(failure_input["selected_curves"]["CW_PUMP_6"]["sheet_name"], "Solver_Curve")
        self.assertLess(failure_row["cw_pump_active_unit_count"], normal_row["cw_pump_active_unit_count"])
        self.assertGreater(failure_row["cw_pump_load_ratio_raw"], normal_row["cw_pump_load_ratio_raw"])
        self.assertEqual(failure_row["cw_pump_reference_capacity_per_unit_kW"], normal_row["cw_pump_reference_capacity_per_unit_kW"])

    def test_energy_is_separate_and_facility_includes_each_pump_once(self):
        _, output = self._run()
        annual = output["annual_results"]
        self.assertGreater(annual["annual_chw_pump_energy_kWh"], 0)
        self.assertGreater(annual["annual_cw_pump_energy_kWh"], 0)
        self.assertAlmostEqual(annual["annual_pump_energy_kWh"], annual["annual_chw_pump_energy_kWh"])
        row = output["hourly_results"][0]
        expected = (row["it_load_kW"] + row["chiller_power_kW"] + row["dry_cooler_power_kW"]
                    + row["pump_power_kW"] + row["cw_pump_power_total_kW"]
                    + row["white_space_equipment_power_kW"] + row["electrical_loss_kW"])
        self.assertAlmostEqual(row["facility_power_kW"], expected)

    def test_peak_design_includes_both_pumps(self):
        payload = self._input()
        payload["peak_design_condition_override"] = {
            "status": "success", "source": "manual", "design_dry_bulb_C": 44,
            "lookup_status": "manual_override",
        }
        output = dispatch_topology(payload["configuration_manifest"], payload)
        peak = output["peak_results"]
        self.assertGreater(peak["peak_design_CHW_pump_power_kW"], 0)
        self.assertGreater(peak["peak_design_CW_pump_power_kW"], 0)
        self.assertAlmostEqual(
            peak["peak_design_heat_rejection_kW"],
            peak["peak_design_cooling_load_kW"] + peak["peak_design_chiller_power_kW"],
        )

    def test_reference_is_dry_cooler_design_capacity_and_diagnostics_exist(self):
        _, output = self._run()
        rows = output["hourly_results"]
        self.assertTrue(all(row["cw_pump_reference_capacity_per_unit_kW"] == 3065 for row in rows))
        self.assertTrue(all(row["cw_pump_reference_capacity_source"] == "associated_dry_cooler_rated_heat_rejection_capacity_kW" for row in rows))
        required = {
            "cw_pump_load_ratio_lookup", "cw_pump_curve_min_load_ratio", "cw_pump_curve_max_load_ratio",
            "cw_pump_power_per_unit_kW", "cw_pump_power_total_kW", "cw_pump_load_ratio_clamped_low",
            "cw_pump_load_ratio_clamped_high", "cw_pump_overload", "cw_pump_curve_source",
            "cw_pump_load_ratio_basis",
        }
        self.assertTrue(required.issubset(rows[0]))

    def test_missing_required_cw_pump_fails_clearly(self):
        payload = self._input()
        payload["selected_curves"].pop("CW_PUMP_6")
        with self.assertRaisesRegex((ChillerDryCoolerRuntimeError, ValueError), "cw_pump|CW_PUMP_6"):
            dispatch_topology(payload["configuration_manifest"], payload)

    def test_non_pump_annual_outputs_are_stable_between_repeated_runs(self):
        _, first = self._run()
        _, second = self._run()
        for key in ("annual_chiller_energy_kWh", "annual_dry_cooler_energy_kWh", "annual_cooling_load_kWh", "annual_IT_energy_kWh", "annual_chw_pump_energy_kWh"):
            self.assertAlmostEqual(first["annual_results"][key], second["annual_results"][key])


if __name__ == "__main__":
    unittest.main()
