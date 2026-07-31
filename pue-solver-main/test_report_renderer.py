import inspect
import unittest

from report_dispatcher import dispatch_report
from report_renderer import render_report_sections


class ReportRendererTest(unittest.TestCase):
    def test_acc_report_sections_render(self):
        report = dispatch_report("acc_gas_engine_cdu", {
            "annual_results": {
                "annual_average_PUE": 1.2,
                "annual_IT_energy_kWh": 1000.0,
                "annual_facility_energy_kWh": 1200.0,
                "annual_acc_energy_kWh": 80.0,
                "average_acc_cop": 12.0,
                "max_acc_power_kW": 25.0,
            }
        })

        rendered = render_report_sections(report["report_sections"])
        titles = [section["title"] for section in rendered["sections"]]
        equipment = next(section for section in rendered["sections"] if section["id"] == "equipment_performance")

        self.assertIn("Equipment Performance", titles)
        self.assertIn("Annual Energy Breakdown", titles)
        self.assertIn("PUE Summary", titles)
        self.assertEqual(equipment["rows"][0]["equipment_type"], "ACC")
        self.assertEqual(equipment["rows"][0]["COP"], 12.0)

    def test_chiller_report_sections_render(self):
        report = dispatch_report("chiller_dry_cooler", {
            "implementation_status": "implemented",
            "annual_results": {
                "annual_average_PUE": 1.25,
                "annual_IT_energy_kWh": 1000.0,
                "annual_facility_energy_kWh": 1250.0,
                "annual_chiller_energy_kWh": 120.0,
                "annual_dry_cooler_energy_kWh": 80.0,
            },
            "hourly_results": [{
                "chiller_performance_result": {
                    "equipment_id": "CENTRIFUGALCHILLER_1",
                    "equipment_type": "CHILLER",
                    "performance": {"power_kW": 120.0, "COP": 5.0, "load_ratio": 0.5},
                    "diagnostics": {},
                },
                "dry_cooler_performance_result": {
                    "equipment_id": "DRYCOOLER_6",
                    "equipment_type": "DRY_COOLER",
                    "performance": {"power_kW": 80.0, "capacity_ratio": 0.7},
                    "diagnostics": {},
                },
            }],
        })

        rendered = render_report_sections(report["report_sections"])
        performance = next(section for section in rendered["sections"] if section["id"] == "equipment_performance")
        types = [row["equipment_type"] for row in performance["rows"]]

        self.assertIn("CHILLER", types)
        self.assertIn("DRY_COOLER", types)

    def test_unknown_equipment_renders_generically(self):
        rendered = render_report_sections({
            "common": [{
                "id": "equipment_performance",
                "title": "Equipment Performance",
                "rows": [{
                    "equipment_id": "FUTURE_1",
                    "equipment_type": "FUTURE_COOLING",
                    "power_kW": 42.0,
                }],
            }]
        })

        self.assertEqual(rendered["sections"][0]["rows"][0]["equipment_type"], "FUTURE_COOLING")
        self.assertEqual(rendered["sections"][0]["rows"][0]["power_kW"], 42.0)

    def test_renderer_has_no_topology_dependency(self):
        import report_renderer

        source = inspect.getsource(report_renderer)
        self.assertNotIn("acc_gas_engine_cdu", source)
        self.assertNotIn("chiller_dry_cooler", source)


if __name__ == "__main__":
    unittest.main()
