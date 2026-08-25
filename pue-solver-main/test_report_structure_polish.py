import unittest
from pathlib import Path

from report_dispatcher import dispatch_report


PROJECT_DIR = Path(__file__).resolve().parent


class ReportStructurePolishTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = (PROJECT_DIR / "ui.js").read_text(encoding="utf-8")
        cls.report = cls._function_source("buildHtmlReportFromSections")

    def test_chiller_report_contains_cooling_system_performance(self):
        self.assertIn("6. Equipment Performance", self.report)
        self.assertIn("Detailed Cooling System Performance", self.report)
        self.assertIn("6. Equipment Performance", self.report)
        self.assertEqual(self.report.count('${performanceCards.length ? `<div class="grid">${performanceCards.join("")}</div>`'), 1)
        self.assertIn('${esc(reportKeyLabel(row.equipment))} Performance', self.report)

    def test_equipment_curve_register_is_appendix(self):
        self.assertIn("Appendix B — Equipment Model Basis", self.report)
        self.assertNotIn("3. Equipment Curve Register", self.report)
        self.assertGreater(
            self.report.index("Appendix B — Equipment Model Basis"),
            self.report.index("Engineering Conclusion"),
        )

    def test_export_does_not_render_empty_performance_sections(self):
        self.assertNotIn("No rows reported.", self.report)
        self.assertIn('performanceCards.length ? ', self.report)

    def test_cooling_load_breakdown_exists(self):
        self.assertIn("Cooling Load Breakdown", self.report)
        self.assertIn("Annual Solar Heat Gain", self.report)
        self.assertIn("Annual Other Auxiliary Heat Gain", self.report)

    def test_acc_report_content_is_preserved(self):
        for text in (
            "Peak Design PUE",
            "PUE Contribution Breakdown",
            "Outdoor Temperature vs PUE",
            "Annual Facility Energy Composition",
        ):
            self.assertIn(text, self.report)
        self.assertIn('profile_id: "acc_gas_engine_cdu"', self.ui)
        self.assertIn('${esc(reportKeyLabel(row.equipment))} Performance', self.report)

    def test_annual_pue_data_is_not_modified(self):
        result = {
            "annual_results": {
                "annual_average_PUE": 1.2345,
                "annual_IT_energy_kWh": 100.0,
                "annual_facility_energy_kWh": 123.45,
            },
            "hourly_results": [],
        }
        report = dispatch_report("acc_gas_engine_cdu", result)
        self.assertEqual(report["summary"]["annual_average_PUE"], 1.2345)

    def test_current_cooling_load_formula_is_present(self):
        formula = self._function_source("formulasHtml")
        self.assertIn("Q</i><sub>solar,h</sub>", formula)
        self.assertIn("Q</i><sub>other_aux,h</sub>", formula)
        self.assertNotIn("Q</i><sub>pump,h</sub>", formula)

    def test_engineering_terminology_is_used(self):
        self.assertIn('"Cooling Technology"', self.report)
        self.assertIn('"System Architecture"', self.report)
        self.assertNotIn('["Solver Topology"', self.report)
        appendix = self.report[self.report.index("Appendix D — Engineering Diagnostics"):]
        self.assertIn('["Internal Report Profile"', appendix)
        self.assertIn('["Internal Dispatch Identifier"', appendix)

    @classmethod
    def _function_source(cls, name):
        marker = f"function {name}"
        start = cls.ui.index(marker)
        brace = cls.ui.index("{", start)
        depth = 0
        for index in range(brace, len(cls.ui)):
            if cls.ui[index] == "{":
                depth += 1
            elif cls.ui[index] == "}":
                depth -= 1
                if depth == 0:
                    return cls.ui[start:index + 1]
        raise AssertionError(name)


if __name__ == "__main__":
    unittest.main()
