import re
import unittest
from pathlib import Path


class FrontendPeakFacilityBindingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = Path(__file__).with_name("ui.js").read_text(encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
