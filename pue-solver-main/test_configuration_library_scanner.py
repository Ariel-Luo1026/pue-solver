import unittest
import ast
from pathlib import Path
from tempfile import TemporaryDirectory

import configuration_library_scanner
from configuration_library_scanner import (
    scan_configuration_library,
    scan_single_configuration,
)


class ConfigurationLibraryScannerTest(unittest.TestCase):
    def _make_configuration(self, root, name, equipment_folders):
        configuration_path = Path(root) / name
        (configuration_path / "input").mkdir(parents=True)
        equipment_path = configuration_path / "equipment"
        equipment_path.mkdir()
        (configuration_path / "configuration.xlsx").touch()
        (configuration_path / "scenario.xlsx").touch()
        for folder in equipment_folders:
            (equipment_path / folder).mkdir()
        return configuration_path

    def test_acc_gasengine_folder_name_detection(self):
        with TemporaryDirectory() as temp_dir:
            configuration_path = self._make_configuration(
                temp_dir,
                "ACC_1.5MW_GASENGINE_CDU",
                ["ACC_2", "CDU_2", "ENGINE_2"],
            )
            manifest = scan_single_configuration(configuration_path)

        self.assertEqual(manifest["topology_id"], "acc")
        self.assertEqual(manifest["topology_display_name"], "ACC")
        self.assertEqual(manifest["detected_cooling_system_type"], "ACC")
        self.assertEqual(manifest["detected_power_source"], "Gas Engine")
        self.assertEqual(manifest["detected_unit_capacity"], "1.5 MW")

    def test_acc_equipment_folder_mapping(self):
        with TemporaryDirectory() as temp_dir:
            configuration_path = self._make_configuration(
                temp_dir,
                "ACC_1.5MW_GASENGINE_CDU",
                ["ACC_2", "CDU_2", "CHW_PUMP_2", "ENGINE_2"],
            )
            manifest = scan_single_configuration(configuration_path)

        self.assertIn("acc_unit", manifest["detected_equipment_ids"])
        self.assertIn("cdu", manifest["detected_equipment_ids"])
        self.assertIn("pump", manifest["detected_equipment_ids"])
        self.assertIn("gas_engine", manifest["detected_equipment_ids"])

    def test_unknown_equipment_folders_are_reported_without_failure(self):
        with TemporaryDirectory() as temp_dir:
            configuration_path = self._make_configuration(
                temp_dir,
                "ACC_1MW_GRID_CDU",
                ["ACC_1", "UNKNOWN_BOX_1"],
            )
            manifest = scan_single_configuration(configuration_path)

        self.assertEqual(manifest["topology_id"], "acc")
        self.assertEqual(manifest["detected_power_source"], "Grid")
        self.assertEqual(manifest["validation_status"], "warning")
        self.assertIn("UNKNOWN_BOX_1", manifest["unexpected_equipment_folders"])
        self.assertTrue(
            any("UNKNOWN_BOX_1" in message for message in manifest["validation_messages"])
        )

    def test_missing_expected_equipment_ids_are_reported(self):
        with TemporaryDirectory() as temp_dir:
            configuration_path = self._make_configuration(
                temp_dir,
                "ACC_1MW_GRID_CDU",
                ["ACC_1"],
            )
            manifest = scan_single_configuration(configuration_path)

        self.assertIn("cdu", manifest["missing_expected_equipment_ids"])
        self.assertIn("pump", manifest["missing_expected_equipment_ids"])
        self.assertTrue(
            any("cdu" in message for message in manifest["validation_messages"])
        )

    def test_scans_all_configuration_folders_under_root(self):
        with TemporaryDirectory() as temp_dir:
            self._make_configuration(temp_dir, "ACC_1MW_GRID_CDU", ["ACC_1"])
            self._make_configuration(
                temp_dir,
                "ABS_COOLINGTOWER_1MW_GRID_CDU",
                ["ABS_1", "COOLING_TOWER_1", "ENGINE_RADIATOR_1"],
            )
            manifests = scan_configuration_library(temp_dir)

        self.assertEqual(len(manifests), 2)
        self.assertEqual(
            {manifest["topology_id"] for manifest in manifests},
            {"acc", "abs_cooling_tower"},
        )

    def test_tentative_equipment_mappings_are_reported(self):
        with TemporaryDirectory() as temp_dir:
            configuration_path = self._make_configuration(
                temp_dir,
                "ABS_DRYCOOLER_1.5MW_GASENGINE_CDU",
                ["ABS_2", "DRY_COOLER_2", "ENGINE_RADIATOR_2", "MAU_2", "RTC_2"],
            )
            manifest = scan_single_configuration(configuration_path)

        self.assertIn("heat_exchanger", manifest["detected_equipment_ids"])
        self.assertIn("terminal_fan", manifest["detected_equipment_ids"])
        self.assertIn("auxiliary_load", manifest["detected_equipment_ids"])
        self.assertTrue(
            any("tentative" in message.lower() for message in manifest["validation_messages"])
        )

    def test_scanner_does_not_import_or_call_solver(self):
        scanner_source = Path(configuration_library_scanner.__file__).read_text(encoding="utf-8")
        tree = ast.parse(scanner_source)
        imported_modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.append(node.module)
        self.assertNotIn("solver", imported_modules)


if __name__ == "__main__":
    unittest.main()
