import unittest

from report_dispatcher import dispatch_report


class ReportVisualizationDataTest(unittest.TestCase):
    def _result(self, equipment_key):
        return {
            "annual_results": {
                "annual_average_PUE": 1.2,
                "annual_IT_energy_kWh": 100.0,
                "annual_facility_energy_kWh": 120.0,
            },
            "hourly_results": [
                {
                    "hour_index": 1,
                    "dry_bulb_C": 20.0,
                    "pue": 1.10,
                    "facility_power_kW": 1100.0,
                    "it_load_kW": 1000.0,
                    equipment_key: 10.0,
                },
                {
                    "hour_index": 2,
                    "dry_bulb_C": 35.0,
                    "pue": 1.25,
                    "facility_power_kW": 1250.0,
                    "it_load_kW": 1000.0,
                    equipment_key: 20.0,
                },
            ],
        }

    def _assert_visualization(self, topology, equipment_key):
        data = dispatch_report(topology, self._result(equipment_key))["visualization_data"]
        self.assertEqual(data["temperature_vs_pue"][1], {"temperature_C": 35.0, "pue": 1.25})
        self.assertEqual(data["peak_summary"]["peak_facility_hour"], 2)
        self.assertEqual(data["peak_summary"]["peak_facility_power_kW"], 1250.0)
        self.assertEqual(data["peak_summary"]["peak_it_load_kW"], 1000.0)
        self.assertEqual(data["peak_summary"]["max_hourly_pue_hour"], 2)

    def test_acc_generates_temperature_vs_pue_data(self):
        self._assert_visualization("acc_gas_engine_cdu", "acc_power_kW")

    def test_chiller_generates_temperature_vs_pue_data(self):
        self._assert_visualization("chiller_dry_cooler", "chiller_power_kW")

    def test_dry_cooler_generates_temperature_vs_pue_data(self):
        self._assert_visualization("chiller_dry_cooler", "dry_cooler_power_kW")

    def test_peak_summary_uses_max_facility_and_max_pue_independently(self):
        result = self._result("cooling_power_kW")
        result["hourly_results"][0]["pue"] = 1.4
        result["hourly_results"][0]["facility_power_kW"] = 1150.0
        result["hourly_results"][0]["it_load_kW"] = 900.0
        result["hourly_results"][0]["dry_bulb_C"] = 18.0
        result["hourly_results"][1]["it_load_kW"] = 1050.0
        result["hourly_results"][1]["dry_bulb_C"] = 36.0
        peak = dispatch_report("unknown", result)["visualization_data"]["peak_summary"]
        self.assertEqual(peak["peak_facility_hour"], 2)
        self.assertEqual(peak["peak_pue"], 1.25)
        self.assertEqual(peak["peak_facility_power_kW"], 1250.0)
        self.assertEqual(peak["peak_it_load_kW"], 1050.0)
        self.assertEqual(peak["peak_outdoor_dry_bulb_C"], 36.0)
        self.assertEqual(peak["max_hourly_pue"], 1.4)
        self.assertEqual(peak["max_hourly_pue_hour"], 1)

    def test_unknown_equipment_renders_generic_visualization(self):
        report = dispatch_report("future_topology", self._result("unknown_equipment_power_kW"))
        self.assertEqual(report["dispatch_status"], "generic")
        self.assertEqual(len(report["visualization_data"]["temperature_vs_pue"]), 2)


if __name__ == "__main__":
    unittest.main()
