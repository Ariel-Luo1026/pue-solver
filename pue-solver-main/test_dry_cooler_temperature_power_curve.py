import unittest
from copy import deepcopy
from pathlib import Path

from configuration_library_loader import build_solver_input_from_library, read_xlsx_sheets, _records
from equipment_engines.dry_cooler import lookup_dry_cooler_power_point
from topology_dispatcher import dispatch_topology


ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "Configuration Library" / "CHILLER_DRYCOOLER_2MW_GRID" / "equipment" / "DRYCOOLER_6" / "DRYCOOLER_6.xlsx"


class DryCoolerTemperaturePowerCurveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sheets = read_xlsx_sheets(WORKBOOK)
        cls.rows = _records(sheets["Solver_Curve"])
        cls.numeric_rows = [row for row in cls.rows if isinstance(row.get("outdoor_dry_bulb_C"), (int, float))]

    def test_workbook_curve_loads_with_required_numeric_columns(self):
        self.assertEqual(len(self.numeric_rows), 57)
        self.assertEqual(self.numeric_rows[0]["outdoor_dry_bulb_C"], -10)
        self.assertEqual(self.numeric_rows[-1]["outdoor_dry_bulb_C"], 46)
        self.assertTrue(all(isinstance(row["power_kW"], (int, float)) for row in self.numeric_rows))

    def test_representative_curve_values(self):
        for temperature, expected in ((33, 52.26), (34, 56.65), (40, 134.23), (44, 261.30)):
            point = lookup_dry_cooler_power_point(self.rows, temperature, "DRYCOOLER_6")
            self.assertAlmostEqual(point["dry_cooler_power_kW"], expected)

    def test_interpolation_and_boundary_clamps(self):
        midpoint = lookup_dry_cooler_power_point(self.rows, 33.5, "DRYCOOLER_6")
        low = lookup_dry_cooler_power_point(self.rows, -20, "DRYCOOLER_6")
        high = lookup_dry_cooler_power_point(self.rows, 50, "DRYCOOLER_6")
        self.assertAlmostEqual(midpoint["dry_cooler_power_kW"], (52.26 + 56.65) / 2)
        self.assertEqual(low["dry_cooler_lookup_temperature_C"], -10)
        self.assertTrue(low["dry_cooler_temperature_clamped_low"])
        self.assertEqual(high["dry_cooler_lookup_temperature_C"], 46)
        self.assertTrue(high["dry_cooler_temperature_clamped_high"])

    def _input(self, scenario="Normal", temperature=33.0, hours=1):
        payload = build_solver_input_from_library("CHILLER_DRYCOOLER_2MW_GRID", 4.0, "Normal")
        payload["scenario_name"] = scenario
        payload["project"]["scenario_name"] = scenario
        payload["project"]["it_load"]["hourly_it_load_kW"] = [3600.0] * hours
        payload["weather"] = {"hourly_data": {"dry_bulb_C": [temperature] * hours}}
        return payload

    def test_runtime_uses_temperature_only_and_scales_by_active_units(self):
        normal_input = self._input("Normal", 33)
        failure_input = self._input("Failure", 33)
        normal = dispatch_topology(normal_input["configuration_manifest"], normal_input)["hourly_results"][0]
        failure = dispatch_topology(failure_input["configuration_manifest"], failure_input)["hourly_results"][0]
        for row in (normal, failure):
            self.assertEqual(row["dry_cooler_power_per_unit_kW"], 52.26)
            self.assertAlmostEqual(row["dry_cooler_power_total_kW"], 52.26 * row["dry_cooler_active_unit_count"])
            self.assertEqual(row["dry_cooler_power_lookup_basis"], "outdoor_dry_bulb_temperature_only")
            self.assertEqual(row["dry_cooler_power_curve_source"], "DRYCOOLER_6/Solver_Curve")

    def test_annual_energy_sums_hourly_temperature_curve_power(self):
        payload = self._input("Normal", 34, hours=2)
        output = dispatch_topology(payload["configuration_manifest"], payload)
        expected = sum(row["dry_cooler_power_total_kW"] for row in output["hourly_results"])
        self.assertAlmostEqual(output["annual_results"]["annual_dry_cooler_energy_kWh"], expected)

    def test_peak_design_uses_design_temperature_and_capacity_validation_remains(self):
        payload = self._input("Normal", 20)
        payload["peak_design_condition_override"] = {"extreme_db_max_C": 44.0}
        output = dispatch_topology(payload["configuration_manifest"], payload)
        peak = output["peak_results"]
        self.assertAlmostEqual(peak["peak_design_dry_cooler_power_per_unit_kW"], 261.3)
        self.assertIn("dry_cooler", output["capacity_validation"]["role_validations"])
        self.assertGreater(output["capacity_validation"]["role_validations"]["dry_cooler"]["active_capacity_kW"], 0)

    def test_non_dry_cooler_annual_results_remain_at_protected_baseline(self):
        payload = build_solver_input_from_library("CHILLER_DRYCOOLER_2MW_GRID", 4.0, "Normal")
        output = dispatch_topology(payload["configuration_manifest"], payload)["annual_results"]
        expected = {
            "annual_chiller_energy_kWh": 2665424.606890732,
            "annual_cw_pump_energy_kWh": 365736.88120780105,
            "annual_cooling_load_kWh": 31536000.0,
            "annual_IT_energy_kWh": 31536000.0,
        }
        for key, value in expected.items():
            self.assertAlmostEqual(output[key], value)
        expected_annual_chw_pump_energy_kWh = 11.12 * 3 * 8760
        self.assertAlmostEqual(
            output["annual_chw_pump_energy_kWh"],
            expected_annual_chw_pump_energy_kWh,
            places=6,
        )

    def test_frontend_schema_and_report_disclosure_use_temperature_only_model(self):
        ui = (Path(__file__).resolve().parent / "ui.js").read_text(encoding="utf-8")
        self.assertIn('outdoor_temperature_power: "outdoor_temperature_power_1D"', ui)
        self.assertIn("Dry Cooler Power Model", ui)
        self.assertIn("Dry Cooler Power Diagnostics", ui)
        self.assertIn("determined from outdoor dry-bulb temperature", ui)
        self.assertIn("not applied as a second runtime power calculation", ui)
        self.assertIn("Performance_Map separately represents thermal heat-rejection capacity", ui)


if __name__ == "__main__":
    unittest.main()
