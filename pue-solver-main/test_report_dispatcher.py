import unittest

from report_dispatcher import dispatch_report
from report_profile_registry import get_report_profile_for_topology


class ReportDispatcherTest(unittest.TestCase):
    def _solver_result(self):
        return {
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


if __name__ == "__main__":
    unittest.main()
