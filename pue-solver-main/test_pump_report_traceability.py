import unittest
from pathlib import Path


class PumpReportTraceabilityTest(unittest.TestCase):
    def test_report_discloses_unified_pump_method_and_annual_diagnostics(self):
        ui = (Path(__file__).with_name("ui.js")).read_text(encoding="utf-8")
        self.assertIn("Failure Peak Design cooling load per active CHW Pump", ui)
        self.assertIn("Current Cooling Load per Active CHW Pump / Failure Peak Design Cooling Load per Active CHW Pump", ui)
        self.assertIn("chw_pump_design_basis_limitation", ui)
        self.assertIn("Normal and Failure use the same Solver_Curve", ui)
        self.assertIn("Pump Annual Diagnostics", ui)
        self.assertIn("Maximum Raw Pump Load Ratio", ui)
        self.assertIn("Overload Hours", ui)
        self.assertIn("Clamped Hours", ui)
        self.assertIn("Annual Pump Energy", ui)


if __name__ == "__main__":
    unittest.main()
