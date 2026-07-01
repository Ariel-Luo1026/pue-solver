import unittest
from pathlib import Path


class AccBenchmarkReportContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = Path(__file__).with_name("ui.js").read_text(encoding="utf-8")

    def test_benchmark_report_identity_and_method_are_explicit(self):
        for text in (
            "Annual Data Center PUE Performance Assessment — ACC Benchmark Mode",
            "This result uses Excel Benchmark Compatible Mode based on scenario peak power and annual temperature factor.",
            "Scenario peak power × annual factor",
            "ACC / Gas Engine",
        ):
            self.assertIn(text, self.ui)

    def test_acc_component_and_contribution_labels_exist(self):
        for text in (
            "ACC Benchmark Components", "CHW Pump Power", "Indoor CDU / RTC / MAU Equivalent",
            "ACC pPUE", "Pump pPUE", "Indoor Equipment pPUE", "Engine Radiator pPUE",
        ):
            self.assertIn(text, self.ui)

    def test_benchmark_chart_and_weather_disclosures_exist(self):
        self.assertIn("Benchmark annual-average series — PUE", self.ui)
        self.assertIn("Monthly PUE — benchmark annual-average repeated series", self.ui)
        self.assertIn(
            "In Benchmark Mode, the EPW weather profile is represented through the annual temperature factor rather than direct hourly ACC interpolation.",
            self.ui,
        )

    def test_final_benchmark_only_wording_is_present(self):
        self.assertIn(
            "Detailed dynamic equipment-curve plots are not used in Excel Benchmark Compatible Mode. ACC power is represented through scenario peak ACC power and the annual temperature factor.",
            self.ui,
        )
        self.assertIn(
            '["Hourly Dispatch Classification", "Not applicable in Excel Benchmark Compatible Mode"]',
            self.ui,
        )


if __name__ == "__main__":
    unittest.main()
