import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from configuration_library_loader import build_solver_input_from_library
from configuration_validator import validate_configuration_library
from equipment_metadata import (
    load_equipment_metadata,
    validate_equipment_folder,
    validate_equipment_metadata,
)
from equipment_curve_registry import validate_curve_type_supported


class EquipmentMetadataTest(unittest.TestCase):
    def _valid_metadata(self):
        return {
            "schema_version": "1.0",
            "equipment_id": "TEST_ACC",
            "equipment_type": "ACC",
            "display_name": "Test ACC",
            "curve_type": "ambient_capacity_power",
            "unit_system": "SI",
            "status": "implemented",
        }

    def test_valid_metadata_loads(self):
        with TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "TEST_ACC"
            folder.mkdir()
            (folder / "TEST_ACC.xlsx").touch()
            metadata_path = folder / "equipment_metadata.json"
            metadata_path.write_text(
                """{
  "schema_version": "1.0",
  "equipment_id": "TEST_ACC",
  "equipment_type": "ACC",
  "display_name": "Test ACC",
  "curve_type": "ambient_capacity_power",
  "unit_system": "SI",
  "status": "implemented"
}""",
                encoding="utf-8",
            )

            metadata = load_equipment_metadata(folder)
            validation = validate_equipment_folder(folder)

        self.assertEqual(metadata["equipment_type"], "ACC")
        self.assertEqual(validation["status"], "valid")

    def test_missing_required_field_rejected(self):
        metadata = self._valid_metadata()
        del metadata["display_name"]

        validation = validate_equipment_metadata(metadata)

        self.assertEqual(validation["status"], "error")
        self.assertIn("Missing required equipment metadata field: display_name", validation["issues"])

    def test_unknown_equipment_type_rejected(self):
        metadata = self._valid_metadata()
        metadata["equipment_type"] = "UNKNOWN_TYPE"

        validation = validate_equipment_metadata(metadata)

        self.assertEqual(validation["status"], "error")
        self.assertIn("Unknown equipment_type: UNKNOWN_TYPE", validation["issues"])

    def test_acc_equipment_metadata_passes_validation(self):
        root = Path(__file__).resolve().parent.parent / "Configuration Library" / "ACC_1.5MW_GASENGINE_CDU" / "equipment"
        equipment_ids = [
            "ACC_2",
            "CHW_PUMP_2",
            "CDU_2",
            "RTC_1&2",
            "MAU_1&2",
            "ENGINE_3",
            "ENGINE_RADIATOR_1",
            "ELECTRICAL_DISTRIBUTION_2",
        ]

        validations = [validate_equipment_folder(root / equipment_id) for equipment_id in equipment_ids]

        self.assertTrue(all(item["status"] == "valid" for item in validations), validations)
        self.assertEqual(validations[0]["curve_schema"], "ambient_capacity_power_2D")

    def test_chiller_cop_map_validates(self):
        metadata = load_equipment_metadata(
            Path(__file__).resolve().parent.parent
            / "Configuration Library"
            / "CHILLER_DRYCOOLER_2MW_GRID"
            / "equipment"
            / "CENTRIFUGALCHILLER_1"
        )

        validation = validate_equipment_metadata(metadata)

        self.assertEqual(validation["status"], "valid", validation)
        self.assertEqual(validation["curve_schema"], "cop_map_2D")

    def test_dry_cooler_curve_validates(self):
        metadata = load_equipment_metadata(
            Path(__file__).resolve().parent.parent
            / "Configuration Library"
            / "CHILLER_DRYCOOLER_2MW_GRID"
            / "equipment"
            / "DRYCOOLER_6"
        )

        validation = validate_equipment_metadata(metadata)

        self.assertEqual(validation["status"], "valid", validation)
        self.assertEqual(validation["curve_schema"], "ambient_capacity_power_1D")

    def test_unknown_curve_type_fails_registry_validation(self):
        validation = validate_curve_type_supported("ACC", "unknown_curve_type")

        self.assertEqual(validation["status"], "error")
        self.assertIn("Unsupported curve_type for ACC", validation["issues"][0])

    def test_unknown_curve_type_fails_metadata_validation(self):
        metadata = self._valid_metadata()
        metadata["curve_type"] = "unknown_curve_type"

        validation = validate_equipment_metadata(metadata)

        self.assertEqual(validation["status"], "error")
        self.assertIn("Unsupported curve_type for ACC", validation["issues"][0])

    def test_incorrect_curve_type_detected(self):
        library_input = build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        mutated = deepcopy(library_input)
        acc_metadata = mutated["equipment"]["cooling"]["ACC"]["equipment_metadata"]
        acc_metadata["curve_type"] = "load_ratio_power"

        validation = validate_configuration_library(mutated)

        self.assertEqual(validation["status"], "error")
        self.assertTrue(
            any(
                "Curve type mismatch: expected load_ratio_power; found ambient_capacity_power" in issue
                for item in validation["equipment_validation"]
                for issue in item["issues"]
            ),
            validation,
        )


if __name__ == "__main__":
    unittest.main()
