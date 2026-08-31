import unittest

from capacity_validation import (
    derive_capacity_validation_from_result,
    operating_scenario_from_result,
    validate_peak_capacity,
)
from report_sections.report_section_registry import engineering_conclusion


class CapacityValidationTest(unittest.TestCase):
    def test_acc_normal_scenario_validation(self):
        result = validate_peak_capacity(
            "acc_gas_engine_cdu",
            peak_results={"peak_design_cooling_load_kW": 4400.0},
            unit_scenario={
                "scenario_name": "Normal",
                "redundancy_mode": "N+1",
                "required_units": 3,
                "installed_units": 4,
                "active_units": 4,
                "standby_units": 0,
                "failed_units": 0,
            },
            role_capacities={
                "cooling": {
                    "required_units": 3,
                    "installed_units": 4,
                    "active_units": 4,
                    "unit_capacity_kW": 1500.0,
                    "peak_load_kW": 4400.0,
                }
            },
        )

        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["scenario_name"], "Normal")
        self.assertEqual(result["installed_capacity_kW"], 6000.0)
        self.assertEqual(result["active_capacity_kW"], 6000.0)
        self.assertEqual(result["capacity_margin_kW"], 1600.0)

    def test_acc_failure_scenario_validation(self):
        result = validate_peak_capacity(
            "acc_gas_engine_cdu",
            peak_results={"peak_design_cooling_load_kW": 4400.0},
            unit_scenario={
                "scenario_name": "Failure",
                "redundancy_mode": "N+1",
                "required_units": 3,
                "installed_units": 4,
                "active_units": 3,
                "failed_units": 1,
            },
            role_capacities={
                "cooling": {
                    "required_units": 3,
                    "installed_units": 4,
                    "active_units": 3,
                    "unit_capacity_kW": 1500.0,
                    "peak_load_kW": 4400.0,
                }
            },
        )

        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["failed_units"], 1)
        self.assertEqual(result["active_capacity_kW"], 4500.0)
        self.assertEqual(result["capacity_margin_kW"], 100.0)

    def test_chiller_role_validation(self):
        result = validate_peak_capacity(
            "chiller_dry_cooler",
            peak_results={"peak_design_cooling_load_kW": 4000.0},
            unit_scenario={
                "scenario_name": "Normal",
                "redundancy_mode": "N+1",
                "required_units": 2,
                "installed_units": 3,
                "active_units": 3,
                "role_quantities": {
                    "chiller_units": {"required_units": 2, "installed_units": 3, "active_units": 3}
                },
            },
            role_capacities={
                "chiller": {
                    "required_units": 2,
                    "installed_units": 3,
                    "active_units": 3,
                    "unit_capacity_kW": 2000.0,
                    "peak_load_kW": 4000.0,
                }
            },
        )

        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["active_capacity_kW"], 6000.0)
        self.assertEqual(result["role_validations"]["chiller"]["capacity_margin_kW"], 2000.0)

    def test_missing_peak_dry_cooler_capacity_warning(self):
        result = validate_peak_capacity(
            "chiller_dry_cooler",
            peak_results={"peak_design_cooling_load_kW": 4000.0},
            unit_scenario={"scenario_name": "Normal", "redundancy_mode": "N+1"},
            role_capacities={
                "chiller": {"active_units": 2, "unit_capacity_kW": 2000.0, "peak_load_kW": 4000.0},
                "dry_cooler": {
                    "active_units": 2,
                    "unit_capacity_kW": None,
                    "peak_load_kW": 4800.0,
                    "warnings": ["Dry cooler peak ambient capacity cannot be calculated because peak design dry bulb is unavailable."],
                },
            },
        )

        self.assertEqual(result["status"], "warning")
        self.assertIn("Dry cooler peak ambient capacity", result["warnings"][0])
        self.assertEqual(result["role_validations"]["dry_cooler"]["status"], "warning")

    def test_operating_scenario_prefers_role_specific_counts(self):
        result = operating_scenario_from_result({
            "library_context": {
                "runtime_assumptions": {
                    "unit_scenario": {
                        "scenario_name": "Failure",
                        "redundancy_mode": "N+1",
                        "installed_units": 3,
                        "required_units": 2,
                        "active_units": 2,
                        "failed_units": 1,
                        "role_quantities": {
                            "chiller_units": {"active_units": 2},
                            "dry_cooler_units": {"active_units": 2},
                            "pump_units": {"active_units": 2},
                        },
                    }
                }
            }
        })

        self.assertEqual(result["scenario_name"], "Failure")
        self.assertEqual(result["active_chiller_units"], 2)
        self.assertEqual(result["active_dry_cooler_units"], 2)
        self.assertEqual(result["active_pump_units"], 2)

    def test_derives_acc_capacity_validation_from_solver_result(self):
        result = derive_capacity_validation_from_result(
            "acc_gas_engine_cdu",
            {
                "project": {
                    "scenario_name": "Normal",
                    "redundancy_strategy": "N+1",
                    "required_units": 3,
                    "installed_units": 4,
                    "active_units": 4,
                    "cooling_unit_capacity_kW": 1500.0,
                },
                "peak_results": {"peak_design_cooling_load_kW": 4400.0},
            },
        )

        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["active_capacity_kW"], 6000.0)

    def test_acc_curve_supported_failure_is_adequate_despite_negative_nameplate_margin(self):
        result = derive_capacity_validation_from_result(
            "acc_gas_engine_cdu",
            {
                "project": {"cooling_unit_capacity_kW": 1000.0},
                "peak_results": {
                    "peak_design_cooling_load_kW": 4078.0,
                    "peak_design_ACC_required_capacity_per_unit_kW": 1019.5,
                    "peak_design_ACC_used_capacity_per_unit_kW": 1019.5,
                    "peak_design_ACC_curve_lookup_success": True,
                    "peak_design_ACC_capacity_clamped": False,
                },
                "library_context": {"runtime_assumptions": {"unit_scenario": {
                    "scenario_name": "Failure", "active_units": 4, "failed_units": 1,
                }}},
            },
        )

        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["capacity_adequacy_basis"], "peak_design_acc_capacity_surface")
        self.assertEqual(result["active_capacity_kW"], 4078.0)
        self.assertEqual(result["nominal_active_capacity_kW"], 4000.0)
        self.assertEqual(result["nominal_capacity_margin_kW"], -78.0)
        self.assertIsNone(result["capacity_margin_percent"])
        self.assertEqual(
            engineering_conclusion(result),
            "Cooling system satisfies peak design cooling demand under selected operating scenario.",
        )

    def test_acc_clamped_peak_capacity_is_not_physically_adequate(self):
        result = derive_capacity_validation_from_result(
            "acc_gas_engine_cdu",
            {
                "project": {"cooling_unit_capacity_kW": 1000.0},
                "peak_results": {
                    "peak_design_cooling_load_kW": 4400.0,
                    "peak_design_ACC_required_capacity_per_unit_kW": 1100.0,
                    "peak_design_ACC_used_capacity_per_unit_kW": 1050.0,
                    "peak_design_ACC_curve_lookup_success": True,
                    "peak_design_ACC_capacity_clamped": True,
                },
                "library_context": {"runtime_assumptions": {"unit_scenario": {
                    "scenario_name": "Failure", "active_units": 4,
                }}},
            },
        )

        self.assertEqual(result["status"], "error")
        self.assertTrue(result["capacity_clamped"])
        self.assertIn("valid unclamped curve domain", result["warnings"][0])


if __name__ == "__main__":
    unittest.main()
