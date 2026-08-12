import re
import unittest
from pathlib import Path


class FrontendPeakFacilityBindingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = Path(__file__).with_name("ui.js").read_text(encoding="utf-8")
        cls.index = Path(__file__).with_name("index.html").read_text(encoding="utf-8")
        start = cls.ui.index("function showProjectVisualization(outObj)")
        end = cls.ui.index("function showSinglePointVisualization(outObj)", start)
        cls.block = cls.ui[start:end]

    def test_chiller_top_card_uses_standardized_peak_summary(self):
        self.assertIn(
            "const peakFacilityPowerKw = peakSummary?.peak_facility_power_kW",
            self.block,
        )
        self.assertIn(
            'setText("peakFacilityPower", `${fmtInteger(peakFacilityPowerKw)} kW`)',
            self.block,
        )

    def test_standardized_value_precedes_legacy_acc_fallback(self):
        binding = re.search(
            r"const peakFacilityPowerKw = ([^;]+);",
            self.block,
        )
        self.assertIsNotNone(binding)
        expression = binding.group(1)
        self.assertLess(
            expression.index("peakSummary?.peak_facility_power_kW"),
            expression.index("peak.peak_total_facility_power_kW"),
        )
        self.assertIn("??", expression)

    def test_valid_peak_does_not_use_undefined_legacy_value(self):
        self.assertNotIn(
            'fmtInteger(isDirectAccV2Summary ? peakDesignDemandKw : peak.peak_total_facility_power_kW)',
            self.block,
        )
        self.assertNotIn(
            'setText("peakFacilityPower", `${fmtInteger(peak.peak_total_facility_power_kW)} kW`)',
            self.block,
        )

    def test_dual_peak_cards_use_distinct_existing_solver_fields(self):
        self.assertIn("Annual Observed Peak Facility Demand", self.index)
        self.assertIn("Peak Design Facility Demand", self.index)
        self.assertIn(
            "const peakDesignFacilityPowerKw = peak.peak_design_facility_electrical_demand_kW",
            self.block,
        )
        self.assertIn("?? peak.peak_design_total_facility_power_kW", self.block)
        self.assertIn('setText("peakDesignFacilityPower"', self.block)

    def test_peak_supporting_conditions_and_scenario_are_bound_from_result(self):
        for expected in (
            '["Peak Hour", peakSummary.peak_facility_hour]',
            '["IT Load at Peak", `${fmtInteger(peakSummary.peak_it_load_kW)} kW`]',
            '["Outdoor DB at Peak", `${fmtNumber(peakSummary.peak_outdoor_dry_bulb_C, 1)} deg C`]',
            '["Design IT Load", Number.isFinite(Number(peak.peak_design_it_load_kW))',
            '["Design Outdoor DB", Number.isFinite(Number(peak.peak_design_outdoor_dry_bulb_C))',
            '["Scenario", scenarioName]',
        ):
            self.assertIn(expected, self.block)
        self.assertIn("outObj.project?.scenario_name || outObj.scenario_name", self.block)

    def test_internal_failure_reference_is_not_bound_as_facility_demand(self):
        self.assertNotIn("failure_peak_non_radiator_facility_power_kW", self.block)
        for example in ("5024.994", "5653.961", "5152.55", "5856.754"):
            self.assertNotIn(example, self.ui)

    def test_peak_demand_breakdown_uses_existing_annual_and_design_fields(self):
        self.assertIn('id="peakDemandBreakdown"', self.index)
        self.assertIn('id="peakDemandBreakdownBody"', self.index)
        start = self.ui.index("function buildPeakDemandBreakdown")
        end = self.ui.index("function showProjectVisualization", start)
        breakdown = self.ui[start:end]
        self.assertIn("row?.total_facility_power_kW", breakdown)
        self.assertIn("peak.peak_design_facility_electrical_demand_kW", breakdown)
        self.assertIn("annualRow.engine_radiator_power_kW", breakdown)
        self.assertIn("peak.peak_design_engine_radiator_power_kW", breakdown)
        self.assertEqual(breakdown.count('["ENGINE_RADIATOR Power"'), 1)
        self.assertNotIn("engine_output_kW", breakdown)
        self.assertNotIn("failure_peak_non_radiator_facility_power_kW", breakdown)
        self.assertIn("annualRow.it_electrical_loss_kW", breakdown)
        self.assertIn("annualRow.mep_electrical_loss_kW", breakdown)
        self.assertIn("peak.peak_design_it_electrical_loss_kW", breakdown)
        self.assertIn("peak.peak_design_mep_electrical_loss_kW", breakdown)
        self.assertIn("Math.abs(annualSum - annualTotal) < 1e-6", breakdown)
        self.assertIn("Math.abs(designSum - designTotal) < 1e-6", breakdown)

    def test_html_report_reuses_peak_breakdown_mapper(self):
        report_start = self.ui.index("function buildHtmlReportFromSections")
        report_end = self.ui.index("function ", report_start + 20)
        report = self.ui[report_start:report_end]
        self.assertIn("buildPeakDemandBreakdown(output, peakSummary)", report)
        self.assertIn("Peak Demand Breakdown", report)
        self.assertIn("Annual Observed Peak", report)
        self.assertIn("Peak Design", report)


if __name__ == "__main__":
    unittest.main()
