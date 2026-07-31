import unittest
from pathlib import Path

from report_dispatcher import dispatch_report


PROJECT_DIR = Path(__file__).resolve().parent


class TemperatureVsPueFrontendBindingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = (PROJECT_DIR / "ui.js").read_text(encoding="utf-8")

    def _result(self, temperature_key):
        return {
            "annual_results": {
                "annual_average_PUE": 1.2,
                "annual_IT_energy_kWh": 1000.0,
                "annual_facility_energy_kWh": 1200.0,
            },
            "hourly_results": [
                {
                    "hour_index": 1,
                    temperature_key: 31.5,
                    "pue": 1.2,
                    "facility_power_kW": 1200.0,
                    "it_load_kW": 1000.0,
                }
            ],
        }

    def _assert_temperature_data(self, topology, alias):
        report = dispatch_report(topology, self._result(alias))
        self.assertEqual(
            report["visualization_data"]["temperature_vs_pue"],
            [{"temperature_C": 31.5, "pue": 1.2}],
        )
        self.assertEqual(
            report["visualization_data"]["peak_summary"]["peak_outdoor_dry_bulb_C"],
            31.5,
        )

    def test_acc_temperature_vs_pue_non_empty(self):
        self._assert_temperature_data("acc_gas_engine_cdu", "dry_bulb_C")

    def test_chiller_temperature_vs_pue_non_empty(self):
        self._assert_temperature_data("chiller_dry_cooler", "ambient_dry_bulb_C")

    def test_dry_cooler_temperature_vs_pue_non_empty(self):
        self._assert_temperature_data("chiller_dry_cooler", "weather_dry_bulb_C")

    def test_all_required_dry_bulb_aliases_are_frontend_mapped(self):
        for alias in (
            "dry_bulb_C",
            "outdoor_dry_bulb_C",
            "outdoor_temp_C",
            "weather_dry_bulb_C",
            "dry_bulb",
        ):
            self.assertIn(f'"{alias}"', self.ui)

    def test_chart_consumes_only_report_visualization_data(self):
        start = self.ui.index('createChart("tempVsPueChart"')
        end = self.ui.index('const peakDetails', start)
        chart_source = self.ui[start:end]
        self.assertIn("report.visualization_data.temperature_vs_pue.map", chart_source)
        self.assertNotIn("hourly.map", chart_source)
        self.assertNotIn("isDirectAccV2", chart_source)

    def test_annual_hourly_peak_summary_labels_are_unambiguous(self):
        index = (PROJECT_DIR / "index.html").read_text(encoding="utf-8")
        start = self.ui.index('const peakDetails = document.getElementById("peakHourDetails")')
        end = self.ui.index("\n}", start) + 2
        section_source = self.ui[start:end]

        self.assertIn("Annual Hourly Peak Summary", index)
        self.assertNotIn("Peak Hour Details", index)
        self.assertNotIn('["Peak PUE"', section_source)
        self.assertIn('["Maximum Hourly PUE", fmtNumber(peakSummary.max_hourly_pue, 3)]', section_source)
        self.assertNotIn("Peak Design PUE", section_source)
        self.assertIn('["Peak Facility Demand Hour", peakSummary.peak_facility_hour]', section_source)
        self.assertIn('["Hour of Maximum Hourly PUE", peakSummary.max_hourly_pue_hour]', section_source)
        self.assertIn('["Peak Facility Demand", `${fmtInteger(peakSummary.peak_facility_power_kW)} kW`]', section_source)
        self.assertIn('["IT Load at Peak Facility Demand", `${fmtInteger(peakSummary.peak_it_load_kW)} kW`]', section_source)
        self.assertIn('["Outdoor Dry-Bulb at Peak Facility Demand", `${fmtNumber(peakSummary.peak_outdoor_dry_bulb_C, 1)} deg C`]', section_source)
        self.assertIn(
            "This section reports peak values observed within the 8,760-hour annual EPW simulation "
            "and is separate from the ASHRAE-based Peak Design Condition analysis.",
            index,
        )


if __name__ == "__main__":
    unittest.main()
