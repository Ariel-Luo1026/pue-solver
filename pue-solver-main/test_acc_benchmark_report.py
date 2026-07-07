import unittest
from pathlib import Path


class AccBenchmarkReportContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = Path(__file__).with_name("ui.js").read_text(encoding="utf-8")

    def test_benchmark_report_identity_and_method_are_explicit(self):
        for text in (
            "Annual Data Center PUE Performance Assessment",
            "JUNO | ACC Cooling System | Annual PUE Assessment",
            "Project: JUNO",
            "Cooling Architecture: ACC + Gas Engine + CDU",
            "Annual-equivalent energy performance model",
        ):
            self.assertIn(text, self.ui)

    def test_report_header_uses_skyvault_png_logo_asset(self):
        self.assertIn("const SKYVAULT_REPORT_LOGO = `data:image/png;base64,", self.ui)
        self.assertIn("function exportHtmlReport()", self.ui)
        self.assertIn("let html = buildHtmlReport(lastReportContext);", self.ui)
        self.assertIn('class="reportLogoBlock"', self.ui)
        self.assertIn('class="reportLogo"', self.ui)
        self.assertIn('src="${SKYVAULT_REPORT_LOGO}"', self.ui)
        self.assertNotIn('src="./assets/skyvault-logo.png"', self.ui)
        self.assertNotIn('src="../../../ArielLuoProjectspue-solver/assets/skyvault-logo.png"', self.ui)
        self.assertIn("display:block !important;width:210px !important;height:auto !important;max-width:210px !important;visibility:visible !important;opacity:1 !important;", self.ui)
        self.assertIn('const headerTopOpen = \'<div class="reportHeaderTop">\';', self.ui)
        self.assertIn('html = html.replace(headerTopOpen, `${headerTopOpen}', self.ui)
        self.assertIn('new Blob([html], { type: "text/html;charset=utf-8" })', self.ui)
        self.assertIn(".reportLogo { display:block; width:210px; height:auto; object-fit:contain; margin-bottom:0; }", self.ui)
        self.assertNotIn('svg class="reportLogo"', self.ui)
        self.assertNotIn("<!-- REPORT_LOGO_INSERTED -->", self.ui)
        self.assertNotIn("TEST_LOGO_POSITION", self.ui)
        self.assertNotIn("REAL_FINAL_HTML", self.ui)
        self.assertNotIn("window.__DEBUG_HTML", self.ui)
        self.assertNotIn("inspectReportLogoDom", self.ui)
        self.assertNotIn("DOM reportLogo", self.ui)
        self.assertGreater(
            self.ui.index('class="reportLogoBlock"'),
            self.ui.index("function exportHtmlReport()"),
        )
        self.assertLess(
            self.ui.index('class="reportLogoBlock"'),
            self.ui.index('new Blob([html], { type: "text/html;charset=utf-8" })'),
        )

    def test_acc_component_and_contribution_labels_exist(self):
        for text in (
            "ACC Cooling System Components", "CHW Pump Power", "Indoor CDU / RTC / MAU Equivalent",
            "ACC pPUE", "Pump pPUE", "Indoor Equipment pPUE", "Engine Radiator pPUE",
        ):
            self.assertIn(text, self.ui)

    def test_benchmark_chart_and_weather_disclosures_exist(self):
        self.assertIn("Cooling System Component Average Power", self.ui)
        self.assertNotIn("Benchmark annual-average series — PUE", self.ui)
        self.assertNotIn("Benchmark annual-average series — Facility Power", self.ui)
        self.assertNotIn("Monthly PUE — benchmark annual-average repeated series", self.ui)
        self.assertIn(
            "For this annual-equivalent assessment, the weather profile is represented through an annual weather factor rather than direct hourly dispatch.",
            self.ui,
        )

    def test_benchmark_power_chart_contains_auditable_components(self):
        for text in (
            '{ label: "IT Load", value: benchmarkAverage.IT }',
            '{ label: "ACC Power", value: benchmarkAverage.ACC }',
            '{ label: "Pump Power", value: benchmarkAverage.pump }',
            '{ label: "Indoor Equipment", value: benchmarkAverage.indoor_CDU_RTC_MAU_equivalent }',
            '{ label: "Engine Radiator", value: benchmarkAverage.engine_radiator }',
            '{ label: "Electrical Loss", value:',
            '{ label: "Facility Power", value: benchmarkAverage.facility }',
        ):
            self.assertIn(text, self.ui)

    def test_final_benchmark_only_wording_is_present(self):
        self.assertIn(
            "Detailed dynamic equipment-curve plots are not used in the annual-equivalent assessment. ACC power is represented through scenario peak ACC power and the annual weather factor.",
            self.ui,
        )
        self.assertIn(
            '["Hourly Dispatch Classification", isExcelReplicatedHourlyMode ? "Hourly weather-driven simulation with derived component powers" : (isExperimentalHourlyMode ? "Configuration Library Solver_Curve direct hourly simulation" : "Not applicable in annual-equivalent assessment")]',
            self.ui,
        )

    def test_benchmark_print_layout_uses_natural_height(self):
        for text in (
            '.benchmark-report { height:auto; min-height:0; }',
            '.benchmark-report .grid { display:block; }',
            '.benchmark-report table { break-inside:auto; }',
        ):
            self.assertIn(text, self.ui)

    def test_empty_chart_cards_and_temperature_bins_are_conditional(self):
        self.assertIn('const resultChartCards = isAnnualBenchmarkMode ? [', self.ui)
        self.assertIn('${resultChartCards.length ? `<div class="grid">', self.ui)
        self.assertIn('const hasTemperatureBins = Boolean(tempDistribution?.rows?.length);', self.ui)
        self.assertIn('${hasTemperatureBins ? `<div class="card"><h3>Temperature Bin Hours</h3>', self.ui)

    def test_weather_chart_cards_are_indivisible_when_printed(self):
        self.assertIn('<div class="card chartCard"><h3>${esc(title)}</h3>', self.ui)
        self.assertIn(
            '.chartCard, .benchmark-report .chartCard { break-inside:avoid; page-break-inside:avoid; break-before:auto; }',
            self.ui,
        )

    def test_peak_hourly_pue_kpi_is_na_in_benchmark_mode(self):
        self.assertIn('const peakHourlyPue = !isAnnualBenchmarkMode && Number.isFinite(Number(annual.max_hourly_PUE))', self.ui)
        self.assertIn('<div class="metric"><div class="label">Peak Hourly PUE</div>', self.ui)
        self.assertIn('${isAnnualBenchmarkMode ? "N/A" : reportValue(peakHourlyPue, "", 3)}', self.ui)
        self.assertIn('Annual-equivalent assessment uses average equipment values.', self.ui)
        self.assertNotIn('(isBenchmarkMode ? Number(annual.annual_average_PUE) : null)', self.ui)

    def test_benchmark_peak_hourly_pue_disclosure_is_explicit(self):
        self.assertIn(
            "Peak hourly PUE is not reported for this annual-equivalent assessment because equipment powers are represented as annual-average values rather than hourly dispatch.",
            self.ui,
        )

    def test_dynamic_peak_hourly_pue_still_uses_max_hourly_pue(self):
        self.assertIn('Number(annual.max_hourly_PUE)', self.ui)
        self.assertIn('isAnnualBenchmarkMode ? "N/A" : reportValue(peakHourlyPue, "", 3)', self.ui)

    def test_experimental_hourly_shape_mode_is_wired_to_ui_and_report(self):
        index = Path(__file__).with_name("index.html").read_text(encoding="utf-8")
        self.assertIn('value="experimental_acc_hourly_shape"', index)
        self.assertIn("ACC V2 Direct Solver_Curve Hourly Mode", index)
        self.assertIn("compute_acc_experimental_hourly_shape", self.ui)
        self.assertIn('const isExperimentalHourlyMode =', self.ui)
        self.assertNotIn("Excel Benchmark Hourly Equivalent Mode", index)
        self.assertNotIn("ACC Benchmark Hourly Equivalent Mode", self.ui)

    def test_experimental_report_discloses_direct_solver_curve_method_and_peak_warning(self):
        self.assertIn(
            "Configuration Library-driven ACC simulation using direct hourly Solver_Curve lookup.",
            self.ui,
        )
        self.assertIn("ACC annual energy is calculated as the sum of hourly ACC power with no external annual adjustment.", self.ui)
        self.assertIn("Direct hourly ACC power exceeds scenario peak ACC power by more than 10%.", self.ui)
        for field in ("max_acc_power_kW", "scenario_peak_acc_power_kW", "acc_peak_to_scenario_peak_ratio"):
            self.assertIn(field, self.ui)

    def test_excel_replicated_hourly_mode_is_wired_and_distinct(self):
        index = Path(__file__).with_name("index.html").read_text(encoding="utf-8")
        self.assertIn('value="excel_replicated_hourly"', index)
        self.assertIn("Excel Replicated Hourly Mode", index)
        self.assertIn("compute_acc_excel_replicated_hourly", self.ui)
        self.assertIn('const isExcelReplicatedHourlyMode =', self.ui)
        self.assertIn("Project-specific hourly ACC performance model", self.ui)


if __name__ == "__main__":
    unittest.main()
