import unittest
from copy import deepcopy

from equipment_role_resolver import EquipmentRoleResolutionError
from generation_side_equipment import (
    GenerationSideEquipmentError,
    engine_radiator_load_ratio,
    evaluate_engine_generation,
    evaluate_engine_radiator,
    gas_engine_roles_for_power_source,
    resolve_generation_role_ids,
)
from configuration_library_loader import build_solver_input_from_library
from library_solver_adapter import convert_library_input_to_solver_input
from solver import compute_pue_project


class GenerationSideEquipmentTest(unittest.TestCase):
    def test_grid_power_source_does_not_activate_generation_roles(self):
        self.assertIsNone(gas_engine_roles_for_power_source({}, {}, "Grid"))

    def test_gas_engine_power_source_requires_both_roles(self):
        manifest = {
            "configuration_id": "STRICT_GAS",
            "equipment_roles": {},
            "required_roles": ["engine", "engine_radiator"],
            "optional_roles": [],
        }
        with self.assertRaisesRegex(EquipmentRoleResolutionError, "missing required equipment role 'engine'"):
            gas_engine_roles_for_power_source(manifest, {}, "Gas Engine")

    def test_roles_select_synthetic_models_without_production_ids(self):
        manifest = {
            "configuration_id": "SYNTHETIC_GAS_CONFIGURATION",
            "equipment_roles": {
                "engine": "ENGINE_TEST",
                "engine_radiator": "ENGINE_RADIATOR_TEST",
            },
            "required_roles": ["engine", "engine_radiator"],
            "optional_roles": [],
        }
        resolved = resolve_generation_role_ids(
            manifest,
            {"ENGINE_TEST": {}, "ENGINE_RADIATOR_TEST": {}},
        )
        self.assertEqual(resolved.engine, "ENGINE_TEST")
        self.assertEqual(resolved.engine_radiator, "ENGINE_RADIATOR_TEST")

    def test_engine_and_radiator_pairing_is_configuration_owned(self):
        manifest = {
            "configuration_id": "INDEPENDENT_PAIR",
            "equipment_roles": {
                "engine": "ENGINE_ALPHA",
                "engine_radiator": "ENGINE_RADIATOR_OMEGA",
            },
            "required_roles": ["engine", "engine_radiator"],
            "optional_roles": [],
        }
        resolved = resolve_generation_role_ids(
            manifest,
            {"ENGINE_ALPHA": {}, "ENGINE_RADIATOR_OMEGA": {}},
        )
        self.assertEqual((resolved.engine, resolved.engine_radiator), (
            "ENGINE_ALPHA", "ENGINE_RADIATOR_OMEGA"
        ))

    def test_missing_engine_role_fails_explicitly(self):
        manifest = {
            "configuration_id": "MISSING_ENGINE",
            "equipment_roles": {"engine_radiator": "RADIATOR_TEST"},
            "required_roles": ["engine", "engine_radiator"],
            "optional_roles": [],
        }
        with self.assertRaisesRegex(EquipmentRoleResolutionError, "missing required equipment role 'engine'"):
            resolve_generation_role_ids(manifest, {"RADIATOR_TEST": {}})

    def test_missing_radiator_role_fails_explicitly(self):
        manifest = {
            "configuration_id": "MISSING_RADIATOR",
            "equipment_roles": {"engine": "ENGINE_TEST"},
            "required_roles": ["engine", "engine_radiator"],
            "optional_roles": [],
        }
        with self.assertRaisesRegex(EquipmentRoleResolutionError, "missing required equipment role 'engine_radiator'"):
            resolve_generation_role_ids(manifest, {"ENGINE_TEST": {}})

    def test_missing_role_workbook_binding_fails_explicitly(self):
        manifest = {
            "configuration_id": "MISSING_BINDING",
            "equipment_roles": {
                "engine": "ENGINE_TEST",
                "engine_radiator": "RADIATOR_TEST",
            },
            "required_roles": ["engine", "engine_radiator"],
            "optional_roles": [],
        }
        with self.assertRaisesRegex(EquipmentRoleResolutionError, "references missing equipment 'ENGINE_TEST'"):
            resolve_generation_role_ids(manifest, {"RADIATOR_TEST": {}})

    def test_synthetic_engine_evaluation_is_generation_side_only(self):
        curve = {
            "equipment_id": "ENGINE_TEST",
            "data": [
                {"load_ratio": 0.5, "power_kW": 500, "engine_efficiency": 0.4},
                {"load_ratio": 1.0, "power_kW": 1000, "engine_efficiency": 0.4},
            ],
        }
        result = evaluate_engine_generation(
            curve,
            0.75,
            2,
            lambda equipment_id, rows, ratio: 750,
            lambda points, ratio, interpolation: 0.4,
        )
        self.assertEqual(result["equipment_id"], "ENGINE_TEST")
        self.assertEqual(result["active_units"], 2)
        self.assertEqual(result["output_kW"], 1500)
        self.assertEqual(result["fuel_input_kW"], 3750)
        self.assertEqual(result["waste_heat_kW"], 2250)

    def test_radiator_preserves_non_radiator_facility_normalization(self):
        curve = {
            "equipment_id": "ENGINE_RADIATOR_TEST",
            "data": [{"load_ratio": 0.0, "power_kW": 0}, {"load_ratio": 1.0, "power_kW": 50}],
        }
        result = evaluate_engine_radiator(
            curve,
            current_non_radiator_facility_kW=750,
            reference_non_radiator_facility_kW=1000,
            active_units=3,
            lookup_power_per_unit=lambda equipment_id, rows, ratio: {
                "power_kW": 37.5,
                "load_ratio": ratio,
            },
        )
        self.assertEqual(engine_radiator_load_ratio(750, 1000), 0.75)
        self.assertEqual(result["equipment_id"], "ENGINE_RADIATOR_TEST")
        self.assertEqual(result["load_ratio"], 0.75)
        self.assertEqual(result["total_power_kW"], 112.5)

    def test_invalid_radiator_curve_does_not_fall_back(self):
        with self.assertRaisesRegex(GenerationSideEquipmentError, "missing or empty"):
            evaluate_engine_radiator(
                {"equipment_id": "ENGINE_RADIATOR_TEST", "data": []},
                500,
                1000,
                1,
                lambda equipment_id, rows, ratio: 99,
            )

    def test_acc_solver_accepts_independently_named_fixture_models_and_unit_counts(self):
        sample = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        sample["project"]["it_load"]["hourly_it_load_kW"] = [3960]
        sample["weather"]["hourly_data"] = {
            "hour_index": [1],
            "dry_bulb_C": [25],
            "wet_bulb_C": [],
        }
        sample["engine_curve"] = deepcopy(sample["engine_curve"])
        sample["engine_radiator_curve"] = deepcopy(sample["engine_radiator_curve"])
        sample["engine_curve"]["equipment_id"] = "ENGINE_TEST"
        sample["engine_radiator_curve"]["equipment_id"] = "ENGINE_RADIATOR_ALTERNATE"
        sample["project"]["engine_active_units"] = 2
        sample["project"]["engine_radiator_active_units"] = 1

        result = compute_pue_project(sample)

        self.assertNotIn("error", result)
        hour = result["hourly_results"][0]
        self.assertEqual(hour["engine_active_units"], 2)
        self.assertEqual(hour["engine_radiator_active_units"], 1)
        self.assertGreater(hour["engine_output_kW"], 0)
        self.assertGreater(hour["engine_radiator_power_kW"], 0)


if __name__ == "__main__":
    unittest.main()
