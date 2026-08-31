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


if __name__ == "__main__":
    unittest.main()
