import unittest
from pathlib import Path

from report_dispatcher import dispatch_report


PROJECT_DIR = Path(__file__).resolve().parent


class ReportCompletenessPolishTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = (PROJECT_DIR / "ui.js").read_text(encoding="utf-8")

    def _result(self, topology="chiller_dry_cooler"):
        hourly = []
        for hour in range(8760):
            hourly.append({
                "hour_index": hour + 1,
                "ambient_dry_bulb_C": 20.0 + hour % 10,
                "pue": 1.2,
                "facility_power_kW": 1200.0,
                "it_load_kW": 1000.0,
                "chiller_COP": 12.0,
            })
        return {
            "topology_id": topology,
            "annual_results": {
                "annual_average_PUE": 1.2,
                "annual_IT_energy_kWh": 8_760_000.0,
                "annual_facility_energy_kWh": 10_512_000.0,
                "annual_chiller_energy_kWh": 1_000_000.0,
                "annual_dry_cooler_energy_kWh": 500_000.0,
                "annual_pump_energy_kWh": 100_000.0,
                "annual_electrical_loss_kWh": 152_000.0,
                "annual_solar_heat_gain_kWh": 12_000.0,
                "annual_other_auxiliary_heat_gain_kWh": 600_000.0,
                "annual_cooling_load_kWh": 9_372_000.0,
            },
            "hourly_results": hourly,
            "library_context": {
                "selected_curves": {
                    "CENTRIFUGALCHILLER_1": {
                        "status": "Selected",
                        "sheet_name": "Solver_Curve",
                        "equipment_metadata": {"curve_type": "cop_map_2D"},
                    },
                    "DRYCOOLER_6": {
                        "status": "Selected",
                        "sheet_name": "Solver_Curve",
                        "equipment_metadata": {"curve_type": "ambient_capacity_power_1D"},
                    },
                }
            },
        }

    def test_peak_design_summary_uses_only_dedicated_design_result(self):
        report_source = self._function_source("buildHtmlReportFromSections")
        self.assertIn('peak.peak_PUE_definition === "peak_design"', report_source)
        self.assertIn("peakDesignPueAvailable ? reportValue(peak.peak_PUE", report_source)
        self.assertIn("Maximum Hourly PUE is reported separately and has not been substituted", report_source)

    def test_report_keeps_maximum_hourly_pue_separate(self):
        report_source = self._function_source("buildHtmlReportFromSections")
        self.assertIn("report.visualization_data.peak_summary", report_source)
        self.assertIn("Maximum Hourly PUE", report_source)
        self.assertIn("peakSummary.max_hourly_pue", report_source)
        self.assertNotIn("Peak Hourly PUE", report_source)

    def test_peak_design_condition_is_traceable_and_separate_from_epw_peak(self):
        report_source = self._function_source("buildHtmlReportFromSections")
        self.assertIn("Peak Design Condition", report_source)
        self.assertIn("Design Outdoor Dry-Bulb Temperature, deg C", report_source)
        self.assertIn("peak.peak_design_outdoor_dry_bulb_C", report_source)
        self.assertIn("Annual EPW Peak Dry-Bulb Temperature", report_source)
        self.assertIn("Annual Simulation Weather Source", report_source)
        self.assertIn("EPW / 8760-hour TMY data", report_source)
        self.assertIn("Peak Design Weather Source", report_source)
        self.assertIn("ASHRAE 20-year extreme outdoor dry-bulb design condition", report_source)

    def test_peak_design_pue_and_loads_use_solver_peak_results(self):
        report_source = self._function_source("buildHtmlReportFromSections")
        self.assertIn('["Peak Design IT Load, kW", reportValue(peak.peak_design_it_load_kW', report_source)
        self.assertIn('["Peak Design Cooling Load, kW", reportValue(peak.peak_design_cooling_load_kW', report_source)
        self.assertIn('["Peak Design PUE", peakDesignPueAvailable ? reportValue(peak.peak_PUE', report_source)
        self.assertIn("peak.peak_design_facility_electrical_demand_kW", report_source)
        self.assertIn("peak.peak_design_total_facility_power_kW", report_source)

    def test_failed_ashrae_lookup_is_not_reported_as_successful(self):
        report_source = self._function_source("buildHtmlReportFromSections")
        self.assertIn('const peakDesignDryBulbAvailable = peak.peak_design_outdoor_dry_bulb_C != null', report_source)
        self.assertIn('Peak Design PUE cannot be substantiated as ASHRAE-based.', report_source)
        self.assertIn('["Lookup Status", esc(peakDesignLookupDisplay)]', report_source)
        self.assertIn('? "Online"', report_source)
        self.assertIn(': "Unavailable"', report_source)

    def test_dry_cooler_equipment_register_is_populated(self):
        report = dispatch_report("chiller_dry_cooler", self._result())
        by_id = {row["equipment_id"]: row for row in report["equipment_curve_register"]}
        self.assertIn("DRYCOOLER_6", by_id)
        self.assertEqual(by_id["DRYCOOLER_6"]["curve_source"], "Configuration Library Solver_Curve")

    def test_monthly_pue_uses_energy_ratio(self):
        report = dispatch_report("chiller_dry_cooler", self._result())
        monthly = report["visualization_data"]["monthly_pue"]
        self.assertEqual(len(monthly), 12)
        self.assertAlmostEqual(monthly[0]["average_pue"], 1.2)
        report_source = self._function_source("buildHtmlReportFromSections")
        self.assertIn("report.visualization_data.monthly_pue", report_source)

    def test_cooling_load_breakdown_matches_annual_totals(self):
        breakdown = dispatch_report("chiller_dry_cooler", self._result())["cooling_load_breakdown"]
        expected = (
            breakdown["annual_it_load_kWh"]
            + breakdown["annual_solar_heat_gain_kWh"]
            + breakdown["annual_other_auxiliary_heat_gain_kWh"]
        )
        self.assertEqual(breakdown["annual_cooling_load_kWh"], expected)

    def test_unknown_topology_generates_generic_complete_report(self):
        report = dispatch_report("future_topology", self._result("future_topology"))
        self.assertEqual(report["dispatch_status"], "generic")
        self.assertEqual(len(report["visualization_data"]["monthly_pue"]), 12)
        self.assertTrue(report["equipment_curve_register"])
        self.assertTrue(report["equipment_performance"])

    def test_diagnostic_aliases_use_canonical_families(self):
        source = self._function_source("equipmentRoleFamily")
        self.assertIn('family.includes("CHILLER")', source)
        self.assertIn('return "DRY_COOLER"', source)

    def _function_source(self, name):
        marker = f"function {name}"
        start = self.ui.index(marker)
        brace = self.ui.index("{", start)
        depth = 0
        for index in range(brace, len(self.ui)):
            if self.ui[index] == "{":
                depth += 1
            elif self.ui[index] == "}":
                depth -= 1
                if depth == 0:
                    return self.ui[start:index + 1]
        raise AssertionError(name)


if __name__ == "__main__":
    unittest.main()
