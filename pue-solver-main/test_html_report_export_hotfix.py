import unittest
from pathlib import Path


ROOT = Path(__file__).parent


def javascript_function(source, name):
    start = source.index(f"function {name}")
    brace = source.index("{", source.index(")", start))
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError(name)


class HtmlReportExportHotfixTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = (ROOT / "ui.js").read_text(encoding="utf-8")
        cls.index = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.builder = javascript_function(cls.ui, "buildHtmlReportFromSections")
        cls.exporter = javascript_function(cls.ui, "exportHtmlReport")

    def test_report_builder_uses_its_declared_output_object(self):
        self.assertIn("const output = context.output || {};", self.builder)
        self.assertEqual(self.builder.count("annualFacilityEnergySummary(output)"), 2)
        self.assertNotIn("annualFacilityEnergySummary(outObj)", self.builder)

    def test_builder_retains_acc_and_chiller_schema_adaptation(self):
        self.assertIn("dispatchReportProfile(solverTopology, output)", self.builder)
        self.assertIn('["pue", "hourly_PUE", "PUE"]', self.builder)
        self.assertIn('["facility_power_kW", "total_facility_power_kW"]', self.builder)
        self.assertIn("annual.annual_acc_energy_kWh", self.ui)
        self.assertIn("annual.annual_chiller_energy_kWh", self.ui)

    def test_missing_optional_fields_remain_guarded(self):
        for token in (
            "const annual = output.annual_results || {};",
            "const peak = output.peak_results || {};",
            "Array.isArray(output.hourly_results)",
            "report.annual_energy_breakdown || {}",
            "annualEnergyBreakdown.components || {}",
            "annualEnergyBreakdown.warnings?.length",
        ):
            self.assertIn(token, self.builder)

    def test_export_success_path_reaches_browser_download_and_cleanup(self):
        for token in (
            "let html = buildHtmlReport(lastReportContext);",
            'new Blob([html], { type: "text/html;charset=utf-8" })',
            "URL.createObjectURL(blob)",
            'document.createElement("a")',
            "document.body.appendChild(link)",
            "link.click()",
            "link.remove()",
            "URL.revokeObjectURL(url)",
            'setSolverDataStatus("HTML 报告已生成。", "ok")',
        ):
            self.assertIn(token, self.exporter)

    def test_export_failure_is_visible_and_not_reported_as_success(self):
        self.assertIn("try {", self.exporter)
        self.assertIn("catch (error)", self.exporter)
        self.assertIn('console.error("HTML report export failed:", error)', self.exporter)
        self.assertIn("HTML 报告导出失败", self.exporter)
        self.assertIn('", "error")', self.exporter)
        self.assertLess(
            self.exporter.index("link.click()"),
            self.exporter.index('setSolverDataStatus("HTML 报告已生成。", "ok")'),
        )

    def test_button_binding_and_report_hierarchy_are_preserved(self):
        self.assertIn('id="btnExportHtmlReport"', self.index)
        self.assertIn(
            'btnExportHtmlReport.addEventListener("click", exportHtmlReport)',
            self.ui,
        )
        for heading in (
            "Engineering Summary",
            "Energy &amp; PUE Summary",
            "Peak Facility Demand",
            "Annual Facility Energy Composition",
            "Peak Demand Breakdown",
            "Equipment Performance",
            "Annual Performance Charts",
        ):
            self.assertIn(heading, self.builder)


if __name__ == "__main__":
    unittest.main()
