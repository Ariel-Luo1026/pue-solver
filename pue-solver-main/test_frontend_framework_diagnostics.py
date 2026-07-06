import unittest
from pathlib import Path


class FrontendFrameworkDiagnosticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent
        cls.index = (root / "index.html").read_text(encoding="utf-8")
        cls.ui = (root / "ui.js").read_text(encoding="utf-8")

    def test_diagnostics_panel_exists_in_index(self):
        self.assertIn('id="frameworkDiagnosticsPanel"', self.index)
        self.assertIn("Framework Diagnostics", self.index)
        self.assertIn('id="frameworkDiagnosticsGrid"', self.index)
        self.assertIn("Frontend diagnostics preview — not connected to calculation.", self.index)

    def test_diagnostics_fields_are_present(self):
        for label in (
            "Detected Topology",
            "Cooling System Type",
            "Power Source",
            "Unit Capacity",
            "Solver Mode",
            "Equipment Detected",
            "Missing Equipment",
            "Performance Requirements",
            "Validation Status",
            "Recommended Next Actions",
        ):
            self.assertIn(label, self.ui)

    def test_acc_and_placeholder_solver_modes_are_available(self):
        self.assertIn('"acc_hourly"', self.ui)
        self.assertIn('"placeholder"', self.ui)
        self.assertIn('"acc"', self.ui)
        self.assertIn('"abs_cooling_tower"', self.ui)

    def test_existing_calculation_buttons_remain_available(self):
        self.assertIn('id="btnRun"', self.index)
        self.assertIn('id="btnRunConfigurationLibrary"', self.index)
        self.assertIn('runUsingConfigurationLibrary', self.ui)

    def test_diagnostics_are_not_added_to_exported_report(self):
        report_start = self.ui.index("function buildHtmlReport")
        report_end = self.ui.index("function exportHtmlReport")
        report_source = self.ui[report_start:report_end]
        self.assertNotIn("Framework Diagnostics", report_source)
        self.assertNotIn("frameworkDiagnosticsPanel", report_source)


if __name__ == "__main__":
    unittest.main()
