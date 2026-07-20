import json
import shutil
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from configuration_library_loader import build_solver_input_from_library, read_xlsx_sheets, _records
from configuration_manifest import (
    ConfigurationManifestError,
    UnsupportedConfigurationStatusError,
    assert_manifest_executable,
    discover_configuration_manifests,
    load_configuration_manifest,
)
from configuration_validator import validate_configuration_library
from equipment_metadata import load_equipment_metadata, validate_equipment_folder
from library_solver_adapter import (
    _build_acc_gas_engine_cdu_solver_input,
    build_solver_input_from_configuration,
)
from report_dispatcher import dispatch_report
from solver import compute_pue_project
from topology_dispatcher import dispatch_topology


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LIBRARY_ROOT = PROJECT_ROOT / "Configuration Library"
TEST_CONFIGURATION = LIBRARY_ROOT / "TEST_ACC_CONFIGURATION"


class ConfigurationWorkflowTest(unittest.TestCase):
    def test_valid_configuration_discovery_finds_test_acc_configuration(self):
        manifests = discover_configuration_manifests(LIBRARY_ROOT)
        by_id = {item["configuration_id"]: item for item in manifests}
        index = json.loads((LIBRARY_ROOT / "configuration_library_index.json").read_text(encoding="utf-8"))
        indexed_ids = {item["configuration_id"] for item in index["configurations"]}

        self.assertIn("TEST_ACC_CONFIGURATION", by_id)
        self.assertIn("TEST_ACC_CONFIGURATION", indexed_ids)
        self.assertEqual(by_id["TEST_ACC_CONFIGURATION"]["implementation_status"], "test_only")

    def test_manifest_validation_passes_but_test_configuration_is_not_executable(self):
        manifest = load_configuration_manifest(TEST_CONFIGURATION)

        self.assertEqual(manifest["configuration_id"], "TEST_ACC_CONFIGURATION")
        self.assertEqual(manifest["equipment_roles"]["acc"], "TEST_ACC")
        with self.assertRaisesRegex(UnsupportedConfigurationStatusError, "test-only"):
            assert_manifest_executable(manifest)

    def test_equipment_metadata_validation_passes(self):
        equipment_folder = TEST_CONFIGURATION / "equipment" / "TEST_ACC"
        metadata = load_equipment_metadata(equipment_folder)
        validation = validate_equipment_folder(equipment_folder)

        self.assertEqual(metadata["equipment_id"], "TEST_ACC")
        self.assertEqual(metadata["curve_type"], "ambient_capacity_power")
        self.assertEqual(validation["status"], "valid")

    def test_missing_metadata_fails_validation(self):
        with self._temporary_test_configuration() as configuration_dir:
            (configuration_dir / "equipment" / "TEST_ACC" / "equipment_metadata.json").unlink()
            runtime_input = self._runtime_input(configuration_dir)

            validation = validate_configuration_library(runtime_input)

        self.assertEqual(validation["status"], "error")
        self.assertTrue(
            any(
                "Missing equipment metadata" in issue
                for item in validation["equipment_validation"]
                for issue in item["issues"]
            ),
            validation,
        )

    def test_curve_type_mismatch_fails_validation(self):
        with self._temporary_test_configuration() as configuration_dir:
            metadata_path = configuration_dir / "equipment" / "TEST_ACC" / "equipment_metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["curve_type"] = "cop_map"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            runtime_input = self._runtime_input(configuration_dir)

            validation = validate_configuration_library(runtime_input)

        self.assertEqual(validation["status"], "error")
        self.assertTrue(
            any(
                "Curve type mismatch" in issue
                for item in validation["equipment_validation"]
                for issue in item["issues"]
            ),
            validation,
        )

    def test_missing_required_equipment_role_fails_manifest_validation(self):
        with self._temporary_test_configuration() as configuration_dir:
            manifest_path = configuration_dir / "configuration_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["equipment_roles"].pop("acc")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ConfigurationManifestError, "missing required equipment role: acc"):
                load_configuration_manifest(configuration_dir)

    def test_frontend_can_display_test_configuration_without_hard_coding_it(self):
        ui = (PROJECT_ROOT / "pue-solver-main" / "ui.js").read_text(encoding="utf-8")
        index = json.loads((LIBRARY_ROOT / "configuration_library_index.json").read_text(encoding="utf-8"))
        indexed_ids = {item["configuration_id"] for item in index["configurations"]}

        self.assertIn("TEST_ACC_CONFIGURATION", indexed_ids)
        self.assertIn('test_only: "Test Only"', ui)
        self.assertIn("Configuration Validation", ui)
        self.assertIn("Equipment Summary / Package Auto Binding", ui)
        self.assertNotIn("TEST_ACC_CONFIGURATION", ui)

    def test_topology_dispatcher_and_report_layer_preserve_existing_acc_result(self):
        library_input = build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")

        dispatched = build_solver_input_from_configuration(
            library_input["configuration_manifest"],
            deepcopy(library_input),
        )
        direct_dispatch = dispatch_topology(library_input["configuration_manifest"], deepcopy(library_input))
        previous = _build_acc_gas_engine_cdu_solver_input(deepcopy(library_input))

        dispatched_pue = compute_pue_project(dispatched)["annual_results"]["annual_average_PUE"]
        direct_dispatch_pue = compute_pue_project(direct_dispatch)["annual_results"]["annual_average_PUE"]
        previous_pue = compute_pue_project(previous)["annual_results"]["annual_average_PUE"]
        report = dispatch_report(dispatched["topology_id"], {"annual_results": {"annual_average_PUE": dispatched_pue}})

        self.assertLess(abs(dispatched_pue - previous_pue), 1e-9)
        self.assertLess(abs(direct_dispatch_pue - previous_pue), 1e-9)
        self.assertEqual(report["profile_id"], "acc_gas_engine_cdu")

    def _temporary_test_configuration(self):
        temp_dir = TemporaryDirectory()
        target = Path(temp_dir.name) / "TEST_ACC_CONFIGURATION"
        shutil.copytree(TEST_CONFIGURATION, target)

        class _Context:
            def __enter__(self_inner):
                return target

            def __exit__(self_inner, exc_type, exc, tb):
                temp_dir.cleanup()

        return _Context()

    def _runtime_input(self, configuration_dir):
        manifest = load_configuration_manifest(configuration_dir)
        equipment_folder = configuration_dir / "equipment" / "TEST_ACC"
        workbook = equipment_folder / "TEST_ACC.xlsx"
        rows = _records(read_xlsx_sheets(workbook)["Solver_Curve"])
        metadata = None
        metadata_path = equipment_folder / "equipment_metadata.json"
        if metadata_path.is_file():
            metadata = load_equipment_metadata(metadata_path)
        selected = {
            "TEST_ACC": {
                "status": "Selected",
                "sheet_name": "Solver_Curve",
                "curve": rows,
            }
        }
        return {
            "configuration_manifest": manifest,
            "configuration_id": manifest["configuration_id"],
            "topology_id": manifest["solver_topology"],
            "selected_curves": selected,
            "equipment": {
                "cooling": {
                    "TEST_ACC": {
                        "enabled": True,
                        "equipment_id": "TEST_ACC",
                        "role": "acc",
                        "package_path": "equipment/TEST_ACC/TEST_ACC.xlsx",
                        "selected_curve_sheet": "Solver_Curve",
                        "selected_curve_status": "Selected",
                        "curve_data": rows,
                        "equipment_metadata": metadata,
                    }
                }
            },
        }


if __name__ == "__main__":
    unittest.main()
