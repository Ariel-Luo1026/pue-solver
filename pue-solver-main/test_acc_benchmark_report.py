import re
import unittest
from pathlib import Path


class AccBenchmarkReportContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = Path(__file__).with_name("ui.js").read_text(encoding="utf-8")

    def _function_source(self, function_name):
        match = re.search(rf"(?:async\s+)?function\s+{re.escape(function_name)}\s*\(", self.ui)
        if not match:
            raise AssertionError(f"function {function_name} not found")
        start = match.start()
        match = re.search(r"\n(?:async\s+)?function\s+\w+\s*\(", self.ui[start + 1:])
        end = start + 1 + match.start() if match else len(self.ui)
        return self.ui[start:end]

    def test_report_identity_is_generic_and_data_driven(self):
        report_block = self._function_source("buildHtmlReportFromSections")
        for text in (
            "Annual Data Center PUE Performance Assessment",
            "JUNO | Cooling System | Annual PUE Assessment",
            "System Architecture: ${esc(systemArchitecture)}",
            "dispatchReportProfile(solverTopology, output)",
            "report.equipment_performance",
        ):
            self.assertIn(text, report_block)
        self.assertNotIn("JUNO | ACC Cooling System | Annual PUE Assessment", report_block)
        self.assertNotIn("Cooling Architecture: ACC + Gas Engine + CDU", report_block)

    def test_report_header_uses_skyvault_png_logo_asset(self):
        report_block = self._function_source("buildHtmlReportFromSections")
        export_block = self._function_source("exportHtmlReport")
        self.assertIn("const SKYVAULT_REPORT_LOGO = `data:image/png;base64,", self.ui)
        self.assertIn("let html = buildHtmlReport(lastReportContext);", export_block)
        self.assertIn('class="reportHeaderTop"', report_block)
        self.assertIn('class="reportLogo"', report_block)
        self.assertIn('src="${SKYVAULT_REPORT_LOGO}"', report_block)
        self.assertIn('class="reportLogoBlock"', export_block)
        self.assertIn('src="${SKYVAULT_REPORT_LOGO}"', export_block)
        self.assertNotIn('src="./assets/skyvault-logo.png"', self.ui)
        self.assertNotIn('svg class="reportLogo"', self.ui)

    def test_acc_component_fields_are_report_data_not_template_blocks(self):
        report_block = self._function_source("buildHtmlReportFromSections")
        sections_block = self._function_source("buildAnnualEnergyBreakdown")
        for text in (
            "ACC",
            "CHW_PUMP",
            "INDOOR_EQUIPMENT",
            "ENGINE_RADIATOR",
            "ELECTRICAL_LOSS",
        ):
            self.assertIn(text, sections_block)
        self.assertIn("Object.entries(annualEnergyBreakdown.components || {})", report_block)
        self.assertNotIn("ACC Cooling System Components", report_block)

    def test_generic_report_charts_are_conditional(self):
        report_block = self._function_source("buildHtmlReportFromSections")
        for text in (
            "annualResultCharts.length",
            "operatingCharts.length",
            "pueSeries.length > 1",
            "hasVariableItLoad",
            "Annual Facility Energy Composition",
            "Monthly Average PUE",
        ):
            self.assertIn(text, report_block)

    def test_exported_report_excludes_debug_strings(self):
        report_block = self._function_source("buildHtmlReportFromSections")
        for forbidden in (
            "Framework Diagnostics",
            "frameworkDiagnosticsPanel",
            "TEST_LOGO_POSITION",
            "REAL_FINAL_HTML",
            "window.__DEBUG_HTML",
            "inspectReportLogoDom",
        ):
            self.assertNotIn(forbidden, report_block)

    def test_direct_acc_diagnostics_still_exist_outside_report_renderer(self):
        benchmark_source = Path(__file__).with_name("acc_excel_benchmark.py").read_text(encoding="utf-8")
        self.assertIn("Configuration Library-driven ACC simulation using direct hourly Solver_Curve lookup.", self.ui)
        for field in ("max_acc_power_kW", "scenario_peak_acc_power_kW", "acc_peak_to_scenario_peak_ratio"):
            self.assertIn(field, benchmark_source)
        report_block = self._function_source("buildHtmlReportFromSections")
        self.assertNotIn("acc_peak_to_scenario_peak_ratio", report_block)

    def test_experimental_modes_remain_unexposed_in_direct_ui(self):
        index = Path(__file__).with_name("index.html").read_text(encoding="utf-8")
        self.assertNotIn('value="experimental_acc_hourly_shape"', index)
        self.assertNotIn("ACC V2 Direct Solver_Curve Hourly Mode", index)
        self.assertIn("compute_acc_experimental_hourly_shape", self.ui)
        self.assertNotIn("Excel Benchmark Hourly Equivalent Mode", index)
        self.assertNotIn("ACC Benchmark Hourly Equivalent Mode", self.ui)


if __name__ == "__main__":
    unittest.main()
