import unittest

from report_dispatcher import dispatch_report
from report_profile_registry import get_report_profile_for_topology


class ReportDispatcherTest(unittest.TestCase):
    def _solver_result(self):
        return {
            "project": {
                "scenario_name": "Normal",
                "redundancy_strategy": "N+1",
                "required_units": 3,
                "installed_units": 4,
                "active_units": 4,
                "cooling_unit_capacity_kW": 1500.0,
            },
            "peak_results": {"peak_design_cooling_load_kW": 4400.0},
            "annual_results": {
                "annual_average_PUE": 1.23456789,
                "annual_IT_energy_kWh": 1000.0,
                "annual_facility_energy_kWh": 1234.56789,
                "annual_total_cooling_system_energy_kWh": 120.0,
                "annual_acc_energy_kWh": 80.0,
                "annual_pump_energy_kWh": 10.0,
                "annual_white_space_equipment_energy_kWh": 15.0,
                "annual_engine_energy_kWh": 300.0,
                "annual_engine_radiator_energy_kWh": 12.0,
                "annual_electrical_loss_kWh": 17.56789,
            }
        }

    def _chiller_solver_result(self):
        return {
            "implementation_status": "implemented",
            "capacity_validation": {
                "status": "valid",
                "scenario_name": "Normal",
                "redundancy_mode": "N+1",
                "peak_cooling_load_kW": 2000.0,
                "installed_capacity_kW": 4000.0,
                "active_capacity_kW": 4000.0,
                "capacity_margin_kW": 2000.0,
                "capacity_margin_percent": 100.0,
                "failed_units": 0,
                "warnings": [],
            },
            "library_context": {
                "runtime_assumptions": {
                    "unit_scenario": {
                        "scenario_name": "Normal",
                        "redundancy_mode": "N+1",
                        "required_units": 1,
                        "installed_units": 2,
                        "active_units": 2,
                        "standby_units": 0,
                        "failed_units": 0,
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
                "annual_chiller_energy_kWh": 100.0,
                "annual_dry_cooler_energy_kWh": 80.0,
                "annual_pump_energy_kWh": 20.0,
                "annual_electrical_loss_kWh": 50.0,
            },
            "hourly_results": [
                {"chiller_COP": 5.0, "dry_cooler_capacity_kW": 2000.0},
                {"chiller_COP": 6.0, "dry_cooler_capacity_kW": 2100.0},
                {"chiller_COP": 4.0, "dry_cooler_capacity_kW": 1900.0},
            ],
        }

    def test_acc_topology_selects_acc_report_profile(self):
        profile = dispatch_report("acc_gas_engine_cdu", self._solver_result())

        self.assertEqual(profile["profile_id"], "acc_gas_engine_cdu")
        self.assertEqual(profile["dispatch_status"], "matched")
        self.assertEqual(profile["cooling_system_type"], "ACC + Gas Engine + CDU")

    def test_unknown_topology_returns_generic_report(self):
        profile = dispatch_report("unknown_topology", self._solver_result())

        self.assertEqual(profile["profile_id"], "generic_pue")
        self.assertEqual(profile["dispatch_status"], "generic")
        self.assertEqual(profile["topology"], "unknown_topology")
        self.assertEqual(
            set(profile["summary"]),
            {
                "annual_average_PUE",
                "annual_IT_energy_kWh",
                "annual_facility_energy_kWh",
            },
        )

    def test_acc_generated_report_fields_unchanged(self):
        profile = get_report_profile_for_topology("acc_gas_engine_cdu")
        fields = [field["key"] for field in profile["fields"]]

        for field in (
            "annual_average_PUE",
            "annual_IT_energy_kWh",
            "annual_facility_energy_kWh",
            "annual_total_cooling_system_energy_kWh",
            "annual_acc_energy_kWh",
            "annual_pump_energy_kWh",
            "annual_white_space_equipment_energy_kWh",
            "annual_engine_energy_kWh",
            "annual_engine_radiator_energy_kWh",
            "annual_electrical_loss_kWh",
        ):
            self.assertIn(field, fields)

        dispatched = dispatch_report("acc_gas_engine_cdu", self._solver_result())
        self.assertEqual(dispatched["summary"]["annual_acc_energy_kWh"], 80.0)
        self.assertEqual(dispatched["summary"]["annual_engine_radiator_energy_kWh"], 12.0)
        self.assertEqual(dispatched["operating_scenario"]["scenario_name"], "Normal")
        self.assertEqual(dispatched["capacity_validation"]["active_capacity_kW"], 6000.0)
        self.assertEqual(dispatched["annual_energy_breakdown"]["PUE"], 1.23456789)
        self.assertEqual(dispatched["annual_energy_breakdown"]["components"]["ACC"]["energy_kWh"], 80.0)

    def test_chiller_dry_cooler_report_profile_dispatches_with_performance_summary(self):
        dispatched = dispatch_report("chiller_dry_cooler", self._chiller_solver_result())

        self.assertEqual(dispatched["profile_id"], "chiller_dry_cooler")
        self.assertEqual(dispatched["dispatch_status"], "matched")
        self.assertEqual(dispatched["configuration_status"], "Implemented")
        self.assertIn("Cooling System Summary", dispatched["sections"])
        self.assertIn("Annual Energy Breakdown", dispatched["sections"])
        self.assertIn("Performance", dispatched["sections"])
        self.assertEqual(dispatched["summary"]["annual_chiller_energy_kWh"], 100.0)
        self.assertEqual(dispatched["summary"]["annual_dry_cooler_energy_kWh"], 80.0)
        self.assertEqual(dispatched["summary"]["annual_pump_energy_kWh"], 20.0)
        self.assertEqual(dispatched["summary"]["annual_electrical_loss_kWh"], 50.0)
        self.assertEqual(dispatched["summary"]["average_chiller_COP"], 5.0)
        self.assertEqual(dispatched["summary"]["min_chiller_COP"], 4.0)
        self.assertEqual(dispatched["summary"]["max_chiller_COP"], 6.0)
        self.assertEqual(dispatched["summary"]["dry_cooler_capacity_kW"], 2100.0)
        self.assertEqual(dispatched["summary"]["configuration_status"], "implemented")
        self.assertEqual(dispatched["operating_scenario"]["active_chiller_units"], 2)
        self.assertEqual(dispatched["operating_scenario"]["active_dry_cooler_units"], 2)
        self.assertEqual(dispatched["operating_scenario"]["active_pump_units"], 2)
        self.assertEqual(dispatched["capacity_validation"]["capacity_margin_kW"], 2000.0)
        self.assertEqual(
            dispatched["annual_energy_breakdown"]["components"]["CHILLER"]["energy_kWh"],
            100.0,
        )


if __name__ == "__main__":
    unittest.main()
