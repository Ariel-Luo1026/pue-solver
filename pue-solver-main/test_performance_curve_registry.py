import unittest
from unittest.mock import patch

from performance_curve_registry import (
    PERFORMANCE_CURVE_REGISTRY,
    build_default_curve_path,
    get_default_curve_for_equipment,
    equipment_family_key,
    normalize_equipment_key,
    resolve_curve_source,
)


class PerformanceCurveRegistrySmokeTest(unittest.TestCase):
    def test_registry_and_default_metadata_exist(self):
        self.assertTrue(PERFORMANCE_CURVE_REGISTRY)
        default = get_default_curve_for_equipment("ACC_1")
        self.assertEqual(default["equipment_id"], "ACC_1")
        self.assertIn("acc", PERFORMANCE_CURVE_REGISTRY)
        self.assertEqual(default["equipment_type"], "acc")
        self.assertEqual(default["default_curve_directory"], "data/performance_curves/acc/")
        self.assertEqual(default["default_curve_filename"], "ACC_1.xlsx")
        self.assertEqual(default["default_curve_path"], "data/performance_curves/acc/ACC_1.xlsx")

    def test_directory_builder_and_all_registered_paths(self):
        self.assertEqual(
            build_default_curve_path("CHW Pump", "CHW_PUMP_2"),
            "data/performance_curves/pump/CHW_PUMP_2.xlsx",
        )
        for equipment_type, models in PERFORMANCE_CURVE_REGISTRY.items():
            self.assertTrue(equipment_type)
            for equipment_id, metadata in models.items():
                self.assertEqual(metadata["equipment_type"], equipment_type)
                self.assertEqual(
                    metadata["default_curve_path"],
                    f"{metadata['default_curve_directory']}{metadata['default_curve_filename']}",
                )

    def test_acc_three_uses_hierarchical_default_path(self):
        metadata = get_default_curve_for_equipment("ACC_3")
        self.assertEqual(metadata["equipment_type"], "acc")
        self.assertEqual(metadata["default_curve_path"], "data/performance_curves/acc/ACC_3.xlsx")

    def test_uploaded_curve_has_priority_over_default(self):
        with patch("performance_curve_registry.Path.is_file", return_value=True):
            resolved = resolve_curve_source("ACC_1", {"ACC_1": "user/ACC_override.xlsx"})
        self.assertEqual(resolved["source_type"], "uploaded")
        self.assertEqual(resolved["file"], "user/ACC_override.xlsx")

    def test_existing_default_file_is_selected(self):
        with patch("performance_curve_registry.Path.is_file", return_value=True):
            resolved = resolve_curve_source("CHW_PUMP_1", {})
        self.assertEqual(resolved["source_type"], "default")
        self.assertEqual(resolved["file"], "data/performance_curves/pump/CHW_PUMP_1.xlsx")

    def test_missing_curve_is_non_fatal(self):
        with patch("performance_curve_registry.Path.is_file", return_value=False):
            resolved = resolve_curve_source("ACC_2", {})
        self.assertEqual(resolved["source_type"], "missing")
        self.assertIsNone(resolved["file"])
        self.assertIn("ACC_2", resolved["warning"])

    def test_unknown_equipment_is_non_fatal(self):
        resolved = resolve_curve_source("UNKNOWN_MODEL", {})
        self.assertEqual(resolved["source_type"], "missing")
        self.assertIsNone(get_default_curve_for_equipment("UNKNOWN_MODEL"))

    def test_labels_and_delimiters_resolve_to_catalog_models(self):
        self.assertEqual(normalize_equipment_key("chw-pump 2"), "CHW_PUMP_2")
        self.assertEqual(equipment_family_key("Engine Radiator 2"), "ENGINE_RADIATOR")
        cases = {
            "ACC 2": "acc_performance_curve",
            "chw-pump 2": "pump_power_curve",
            "Engine_3": "engine_efficiency_curve",
            "engine radiator 2": "engine_radiator_performance_curve",
            "CDU 2": "cdu_performance_curve",
            "rtc-1": "rtc_performance_curve",
            "mau 1": "mau_performance_curve",
        }
        for label, curve_type in cases.items():
            with self.subTest(label=label):
                self.assertEqual(get_default_curve_for_equipment(label)["curve_type"], curve_type)

    def test_family_fallback_ignores_instance_number(self):
        self.assertEqual(get_default_curve_for_equipment("ACC 99")["equipment_type"], "acc")
        self.assertEqual(get_default_curve_for_equipment("Engine Radiator 2")["equipment_type"], "engine_radiator")

    def test_uploaded_family_curve_matches_different_instance(self):
        resolved = resolve_curve_source("Engine 3", {"ENGINE_2": "library/engine.xlsx"})
        self.assertEqual(resolved["source_type"], "uploaded")
        self.assertEqual(resolved["file"], "library/engine.xlsx")


if __name__ == "__main__":
    unittest.main()
