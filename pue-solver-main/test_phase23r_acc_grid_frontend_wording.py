import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class Phase23RAccGridFrontendWordingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = (ROOT / "ui.js").read_text(encoding="utf-8")
        cls.index = (ROOT / "index.html").read_text(encoding="utf-8")

    def test_acc_calculation_principle_separates_cooling_and_power_source(self):
        self.assertIn('? "ACC + CDU"', self.ui)
        self.assertIn("Cooling System: ${esc(calculationCoolingSystem)}", self.ui)
        self.assertIn("Power Source: ${esc(calculationPowerSource)}", self.ui)
        self.assertIn('? "Gas Engine" : "Grid"', self.ui)

    def test_acc_architecture_uses_topology_neutral_equal_sharing_wording(self):
        self.assertIn(
            "All active cooling units are assumed to operate with equal load sharing throughout the year.",
            self.index,
        )
        self.assertNotIn(
            "All chiller and dry cooler units are assumed to run throughout the year",
            self.index,
        )

    def test_acc_capacity_adequacy_uses_peak_curve_diagnostics(self):
        self.assertIn("peak_design_ACC_curve_lookup_success", self.ui)
        self.assertIn("peak_design_ACC_used_capacity_per_unit_kW", self.ui)
        self.assertIn("!capacityClamped && usedPerUnit + tolerance >= requiredPerUnit", self.ui)
        self.assertIn('hasOwnProperty.call(peak, "peak_design_ACC_curve_lookup_success")', self.ui)
        self.assertIn('capacity_adequacy_basis: "peak_design_acc_capacity_surface"', self.ui)
        self.assertIn("nominal_capacity_margin_kW: nominalMargin", self.ui)
        self.assertIn("capacityValidation.capacity_margin_percent == null", self.ui)


if __name__ == "__main__":
    unittest.main()
