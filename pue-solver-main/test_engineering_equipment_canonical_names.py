import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from configuration_library_loader import _resolve_actual_equipment_folder
from configuration_library_scanner import parse_equipment_folder_name, scan_single_configuration
from library_solver_adapter import _resolve_equipment_key


class EngineeringEquipmentCanonicalNamesTest(unittest.TestCase):
    def test_parser_prefers_engineering_canonical_names(self):
        cases = {
            "RTC_1&2": "rtc",
            "RTC_01_02": "rtc",
            "RTC_North": "rtc",
            "MAU_1&2": "mau",
            "MAU_01_02": "mau",
            "MAU_North": "mau",
            "ENGINE_RADIATOR_1": "engine_radiator",
            "ENGINE_RADIATOR_North": "engine_radiator",
        }
        for folder_name, equipment_id in cases.items():
            with self.subTest(folder_name=folder_name):
                self.assertEqual(
                    parse_equipment_folder_name(folder_name)["canonical_equipment_id"],
                    equipment_id,
                )

    def test_scanner_manifest_uses_engineering_canonical_ids(self):
        with TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "ACC_1.5MW_GASENGINE_CDU"
            (config / "input").mkdir(parents=True)
            equipment = config / "equipment"
            equipment.mkdir()
            (config / "configuration.xlsx").touch()
            (config / "scenario.xlsx").touch()
            for folder_name in (
                "ACC_2",
                "CDU_2",
                "CHW_PUMP_2",
                "ELECTRICAL_DISTRIBUTION_2",
                "ENGINE_3",
                "ENGINE_RADIATOR_1",
                "MAU_1&2",
                "RTC_1&2",
            ):
                (equipment / folder_name).mkdir()

            manifest = scan_single_configuration(config)

        self.assertEqual(
            set(manifest["detected_equipment_ids"]),
            {
                "acc_unit",
                "cdu",
                "pump",
                "electrical_distribution",
                "gas_engine",
                "engine_radiator",
                "mau",
                "rtc",
            },
        )

    def test_loader_resolves_legacy_and_canonical_ids_to_actual_folders(self):
        with TemporaryDirectory() as temp_dir:
            equipment_root = Path(temp_dir) / "equipment"
            for folder_name in ("RTC_1&2", "MAU_1&2", "ENGINE_RADIATOR_1"):
                folder = equipment_root / folder_name
                folder.mkdir(parents=True)
                (folder / f"{folder_name}.xlsx").touch()

            cases = {
                "auxiliary_load": "RTC_1&2",
                "rtc": "RTC_1&2",
                "terminal_fan": "MAU_1&2",
                "mau": "MAU_1&2",
                "heat_exchanger": "ENGINE_RADIATOR_1",
                "engine_radiator": "ENGINE_RADIATOR_1",
            }
            for requested_id, expected_folder in cases.items():
                with self.subTest(requested_id=requested_id):
                    self.assertEqual(
                        _resolve_actual_equipment_folder(equipment_root, requested_id),
                        expected_folder,
                    )

    def test_adapter_resolves_legacy_and_canonical_ids_to_selected_curve_keys(self):
        selected_curves = {
            "RTC_1&2": {},
            "MAU_1&2": {},
            "ENGINE_RADIATOR_1": {},
        }
        cases = {
            ("auxiliary_load", "auxiliary_load"): "RTC_1&2",
            ("rtc", "rtc"): "RTC_1&2",
            ("terminal_fan", "terminal_fan"): "MAU_1&2",
            ("mau", "mau"): "MAU_1&2",
            ("heat_exchanger", "heat_exchanger"): "ENGINE_RADIATOR_1",
            ("engine_radiator", "engine_radiator"): "ENGINE_RADIATOR_1",
        }
        for (preferred_id, canonical_id), expected_key in cases.items():
            with self.subTest(preferred_id=preferred_id, canonical_id=canonical_id):
                self.assertEqual(
                    _resolve_equipment_key(selected_curves, preferred_id, canonical_id),
                    expected_key,
                )


if __name__ == "__main__":
    unittest.main()
