import unittest

from report_dispatcher import dispatch_report
from report_sections import COMMON_REPORT_SECTIONS, build_report_sections
from report_sections.report_section_registry import engineering_conclusion


class ReportSectionsTest(unittest.TestCase):
    def _acc_result(self):
        return {
            "project": {
                "scenario_name": "Normal",
                "redundancy_strategy": "N+1",
                "required_units": 3,
                "installed_units": 4,
                "active_units": 4,
                "cooling_unit_capacity_kW": 1500.0,
            },
            "peak_results": {
                "peak_design_it_load_kW": 4200.0,
                "peak_design_cooling_load_kW": 4400.0,
                "peak_design_outdoor_dry_bulb_C": 35.0,
            },
            "annual_results": {
                "annual_average_PUE": 1.2,
                "annual_IT_energy_kWh": 1000.0,
                "annual_facility_energy_kWh": 1200.0,
                "annual_total_cooling_system_energy_kWh": 100.0,
                "annual_acc_energy_kWh": 80.0,
                "annual_pump_energy_kWh": 20.0,
            },
        }

    def _chiller_result(self):
        return {
            "implementation_status": "implemented",
            "capacity_validation": {
                "status": "valid",
                "scenario_name": "Failure",
                "redundancy_mode": "N+1",
                "peak_cooling_load_kW": 2000.0,
                "installed_capacity_kW": 3000.0,
                "active_capacity_kW": 2000.0,
                "capacity_margin_kW": 0.0,
                "capacity_margin_percent": 0.0,
                "failed_units": 1,
                "warnings": [],
            },
            "library_context": {
                "runtime_assumptions": {
                    "unit_scenario": {
                        "scenario_name": "Failure",
                        "redundancy_mode": "N+1",
                        "required_units": 2,
                        "installed_units": 3,
                        "active_units": 2,
                        "standby_units": 0,
                        "failed_units": 1,
                        "role_quantities": {
                            "chiller_units": {"active_units": 2},
                            "dry_cooler_units": {"active_units": 2},
                            "pump_units": {"active_units": 2},
                        },
                    }
                }
            },
            "annual_results": {
                "annual_average_PUE": 1.25,
                "annual_IT_energy_kWh": 1000.0,
                "annual_facility_energy_kWh": 1250.0,
                "annual_chiller_energy_kWh": 120.0,
                "annual_dry_cooler_energy_kWh": 80.0,
                "annual_pump_energy_kWh": 20.0,
                "annual_electrical_loss_kWh": 30.0,
            },
            "hourly_results": [
                {
                    "it_load_kW": 1000.0,
                    "total_facility_power_kW": 1250.0,
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
                    "active_chiller_units": 1,
                    "active_dry_cooler_units": 1,
                }
            ],
        }

    def test_acc_report_contains_all_common_sections(self):
        dispatched = dispatch_report("acc_gas_engine_cdu", self._acc_result())
        titles = [section["title"] for section in dispatched["report_sections"]["common"]]

        self.assertEqual(titles, [section["title"] for section in COMMON_REPORT_SECTIONS])
        self.assertIn("ACC COP", [section["title"] for section in dispatched["report_sections"]["topology_specific"]])
        self.assertEqual(dispatched["annual_energy_breakdown"]["PUE"], 1.2)

    def test_chiller_report_contains_all_common_sections(self):
        dispatched = dispatch_report("chiller_dry_cooler", self._chiller_result())
        titles = [section["title"] for section in dispatched["report_sections"]["common"]]

        self.assertEqual(titles, [section["title"] for section in COMMON_REPORT_SECTIONS])
        self.assertIn(
            "Dry Cooler Performance",
            [section["title"] for section in dispatched["report_sections"]["topology_specific"]],
        )

    def test_unit_scenario_capacity_and_energy_sections_are_display_ready(self):
        sections = build_report_sections("chiller_dry_cooler", self._chiller_result())["common"]
        by_id = {section["id"]: section for section in sections}

        scenario = {row["label"]: row["value"] for row in by_id["operating_scenario"]["rows"]}
        capacity = {row["label"]: row["value"] for row in by_id["peak_capacity_validation"]["rows"]}
        energy = {row["label"]: row["value"] for row in by_id["annual_energy_breakdown"]["rows"]}

        self.assertEqual(scenario["Active Chiller Units"], 2)
        self.assertEqual(scenario["Active Dry Cooler Units"], 2)
        self.assertEqual(scenario["Active Pumps"], 2)
        self.assertEqual(capacity["Active Capacity"], 2000.0)
        self.assertEqual(energy["Chiller"], 120.0)
        self.assertEqual(energy["Dry Cooler"], 80.0)

    def test_equipment_performance_section_uses_standard_performance_result(self):
        sections = build_report_sections("chiller_dry_cooler", self._chiller_result())["common"]
        performance = next(section for section in sections if section["id"] == "equipment_performance")

        self.assertEqual(performance["rows"][0]["equipment"], "CENTRIFUGALCHILLER_1")
        self.assertEqual(performance["rows"][0]["type"], "CHILLER")
        self.assertEqual(performance["rows"][0]["COP"], 5.0)

    def test_conclusion_rules_are_deterministic(self):
        self.assertEqual(
            engineering_conclusion({"status": "valid", "capacity_margin_percent": 15.0}),
            "Cooling system satisfies peak design cooling demand under selected operating scenario.",
        )
        self.assertEqual(
            engineering_conclusion({"status": "warning", "capacity_margin_percent": 3.0}),
            "Cooling capacity margin is limited under failure scenario.",
        )
        self.assertEqual(
            engineering_conclusion({"status": "error", "capacity_margin_percent": -1.0}),
            "Available cooling capacity is insufficient for peak design demand.",
        )


if __name__ == "__main__":
    unittest.main()
