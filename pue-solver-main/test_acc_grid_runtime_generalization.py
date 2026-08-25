import unittest
from copy import deepcopy
from pathlib import Path

from configuration_library_loader import build_solver_input_from_library
from configuration_manifest import ConfigurationManifestError, validate_configuration_manifest
from library_solver_adapter import convert_library_input_to_solver_input
from solver import compute_pue_project


def synthetic_grid_library_input(scenario="Normal"):
    payload = deepcopy(build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.0, scenario))
    payload["configuration_id"] = "SYNTHETIC_ACC_GRID"
    payload["configuration_display_name"] = "Synthetic ACC + Grid + CDU"
    payload["power_source"] = "Grid"
    manifest = payload["configuration_manifest"]
    manifest["configuration_id"] = "SYNTHETIC_ACC_GRID"
    manifest["display_name"] = "Synthetic ACC + Grid + CDU"
    manifest["power_source"] = "Grid"
    for role in ("engine", "engine_radiator"):
        equipment_id = manifest["equipment_roles"].pop(role)
        manifest["required_roles"].remove(role)
        payload["selected_curves"].pop(equipment_id, None)
        payload["equipment"]["cooling"].pop(role, None)
    payload["project"]["it_load"]["hourly_it_load_kW"] = [3600.0]
    payload["project"]["it_load"]["hourly_it_load_percent"] = [90.0]
    payload["weather"] = {"hourly_data": {"hour_index": [1], "dry_bulb_C": [35.0]}}
    return payload


class AccGridRuntimeGeneralizationTest(unittest.TestCase):
    def test_grid_manifest_validly_omits_generation_roles(self):
        manifest = synthetic_grid_library_input()["configuration_manifest"]
        validated = validate_configuration_manifest(manifest, "synthetic/configuration_manifest.json")
        self.assertEqual(validated["power_source"], "Grid")
        self.assertNotIn("engine", validated["equipment_roles"])
        self.assertNotIn("engine_radiator", validated["equipment_roles"])

    def test_explicit_gas_engine_manifest_requires_both_generation_roles(self):
        manifest = synthetic_grid_library_input()["configuration_manifest"]
        manifest["power_source"] = "Gas Engine"
        with self.assertRaisesRegex(ConfigurationManifestError, "requires generation role: engine"):
            validate_configuration_manifest(manifest, "synthetic/configuration_manifest.json")

    def test_grid_adapter_omits_generation_curves_and_unit_counts(self):
        adapted = convert_library_input_to_solver_input(synthetic_grid_library_input())
        self.assertNotIn("engine_curve", adapted)
        self.assertNotIn("engine_radiator_curve", adapted)
        self.assertNotIn("engine_active_units", adapted["project"])
        self.assertNotIn("engine_radiator_active_units", adapted["project"])

    def test_grid_hourly_annual_peak_and_electrical_reconciliation(self):
        adapted = convert_library_input_to_solver_input(synthetic_grid_library_input())
        adapted["peak_design_weather_source"] = "manual"
        adapted["peak_design_outdoor_dry_bulb_C"] = 44.0
        adapted["project"]["peak_design_weather_source"] = "manual"
        adapted["project"]["peak_design_outdoor_dry_bulb_C"] = 44.0
        adapted["feature_flags"] = {"acc_v2_enabled": True}
        adapted["acc_v2"] = {
            "enabled": True,
            "configuration_path": str(
                Path(__file__).resolve().parent.parent
                / "Configuration Library"
                / "ACC_1.5MW_GASENGINE_CDU"
            ),
        }
        result = compute_pue_project(adapted)
        self.assertNotIn("error", result)
        row = result["hourly_results"][0]
        self.assertIsNone(row["engine_output_kW"])
        self.assertEqual(row["engine_radiator_power_kW"], 0.0)
        self.assertAlmostEqual(
            row["it_electrical_loss_kW"] + row["mep_electrical_loss_kW"],
            row["electrical_loss_kW"],
            places=12,
        )
        annual = result["annual_results"]
        self.assertEqual(annual["annual_engine_output_kWh"], 0.0)
        self.assertEqual(annual["annual_engine_radiator_energy_kWh"], 0.0)
        self.assertAlmostEqual(
            annual["annual_facility_energy_kWh"],
            sum(item["total_facility_power_kW"] for item in result["hourly_results"]),
            places=9,
        )
        self.assertEqual(result["peak_results"].get("peak_design_engine_radiator_power_kW"), 0.0)

    def test_normal_failure_cooling_and_indoor_unit_policy_is_unchanged(self):
        normal = synthetic_grid_library_input("Normal")["project"]
        failure = synthetic_grid_library_input("Failure")["project"]
        self.assertEqual((normal["required_units"], normal["installed_units"], normal["active_units"], normal["indoor_active_units"]), (3, 4, 4, 4))
        self.assertEqual((failure["required_units"], failure["installed_units"], failure["active_units"], failure["indoor_active_units"]), (3, 4, 3, 4))


if __name__ == "__main__":
    unittest.main()
