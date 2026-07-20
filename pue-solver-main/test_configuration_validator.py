import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from configuration_library_loader import build_solver_input_from_library
from configuration_library_scanner import scan_single_configuration
from configuration_validator import (
    validate_configuration_library,
    validate_configuration_manifest,
)
from library_solver_adapter import (
    _build_acc_gas_engine_cdu_solver_input,
    build_solver_input_from_configuration,
)
from solver import compute_pue_project


class ConfigurationValidatorTest(unittest.TestCase):
    def _make_configuration(
        self,
        root,
        name,
        equipment_folders,
        configuration_file=True,
        scenario_file=True,
        input_folder=True,
        equipment_folder=True,
    ):
        configuration_path = Path(root) / name
        configuration_path.mkdir(parents=True)
        if input_folder:
            (configuration_path / "input").mkdir()
        if equipment_folder:
            equipment_path = configuration_path / "equipment"
            equipment_path.mkdir()
            for folder in equipment_folders:
                (equipment_path / folder).mkdir()
        if configuration_file:
            (configuration_path / "configuration.xlsx").touch()
        if scenario_file:
            (configuration_path / "scenario.xlsx").touch()
        return configuration_path

    def _validate_path(self, configuration_path):
        return validate_configuration_manifest(scan_single_configuration(configuration_path))

    def test_complete_acc_configuration_is_warning_only_for_tentative_mappings(self):
        with TemporaryDirectory() as temp_dir:
            configuration_path = self._make_configuration(
                temp_dir,
                "ACC_1.5MW_GASENGINE_CDU",
                [
                    "ACC_2",
                    "CDU_2",
                    "CHW_PUMP_2",
                    "MAU_2",
                    "ELECTRICAL_DISTRIBUTION_2",
                    "RTC_2",
                    "ENGINE_2",
                ],
            )
            summary = self._validate_path(configuration_path)

        self.assertEqual(summary["topology_id"], "acc")
        self.assertEqual(summary["validation_status"], "warning")
        self.assertEqual(summary["completeness_score"], 1.0)
        self.assertTrue(summary["tentative_equipment_mappings"])
        self.assertEqual(summary["missing_equipment_ids"], [])

    def test_missing_configuration_workbook_returns_invalid(self):
        with TemporaryDirectory() as temp_dir:
            configuration_path = self._make_configuration(
                temp_dir,
                "ACC_1MW_GRID_CDU",
                ["ACC_1"],
                configuration_file=False,
            )
            summary = self._validate_path(configuration_path)

        self.assertEqual(summary["validation_status"], "invalid")
        self.assertIn("Add configuration.xlsx", summary["recommended_next_actions"])

    def test_unknown_topology_folder_returns_invalid(self):
        with TemporaryDirectory() as temp_dir:
            configuration_path = self._make_configuration(
                temp_dir,
                "UNKNOWN_1MW_GRID_CDU",
                ["ACC_1"],
            )
            summary = self._validate_path(configuration_path)

        self.assertEqual(summary["validation_status"], "invalid")
        self.assertIsNone(summary["topology_id"])

    def test_missing_pump_lowers_completeness_score(self):
        with TemporaryDirectory() as temp_dir:
            configuration_path = self._make_configuration(
                temp_dir,
                "ACC_1MW_GRID_CDU",
                ["ACC_1", "CDU_1", "ENGINE_2"],
            )
            summary = self._validate_path(configuration_path)

        self.assertEqual(summary["validation_status"], "warning")
        self.assertIn("pump", summary["missing_equipment_ids"])
        self.assertLess(summary["completeness_score"], 1.0)

    def test_unexpected_equipment_folder_appears_in_recommended_next_actions(self):
        with TemporaryDirectory() as temp_dir:
            configuration_path = self._make_configuration(
                temp_dir,
                "ACC_1MW_GRID_CDU",
                ["ACC_1", "UNKNOWN_1"],
            )
            summary = self._validate_path(configuration_path)

        self.assertIn("UNKNOWN_1", summary["unexpected_equipment_folders"])
        self.assertIn(
            "Confirm equipment folder meaning: UNKNOWN_1",
            summary["recommended_next_actions"],
        )

    def test_tentative_rtc_mapping_appears_in_summary(self):
        with TemporaryDirectory() as temp_dir:
            configuration_path = self._make_configuration(
                temp_dir,
                "ACC_1MW_GRID_CDU",
                ["ACC_1", "RTC_2"],
            )
            summary = self._validate_path(configuration_path)

        self.assertIn(
            {"equipment_folder": "RTC_2", "equipment_id": "rtc", "message": "RTC_2 → rtc is tentative."},
            summary["tentative_equipment_mappings"],
        )
        self.assertIn(
            "Review tentative mapping: RTC_2 → rtc",
            summary["recommended_next_actions"],
        )

    def test_grouped_tentative_folder_mapping_appears_in_summary(self):
        with TemporaryDirectory() as temp_dir:
            configuration_path = self._make_configuration(
                temp_dir,
                "ACC_1MW_GRID_CDU",
                ["ACC_1", "RTC_1&2", "MAU_1&2"],
            )
            summary = self._validate_path(configuration_path)

        self.assertIn(
            {"equipment_folder": "RTC_1&2", "equipment_id": "rtc", "message": "RTC_1&2 → rtc is tentative."},
            summary["tentative_equipment_mappings"],
        )
        self.assertIn(
            {"equipment_folder": "MAU_1&2", "equipment_id": "mau", "message": "MAU_1&2 → mau is tentative."},
            summary["tentative_equipment_mappings"],
        )

    def test_canonical_detected_ids_satisfy_legacy_topology_expectations(self):
        with TemporaryDirectory() as temp_dir:
            configuration_path = self._make_configuration(
                temp_dir,
                "ACC_1.5MW_GASENGINE_CDU",
                [
                    "ACC_2",
                    "CDU_2",
                    "CHW_PUMP_2",
                    "ELECTRICAL_DISTRIBUTION_2",
                    "ENGINE_3",
                    "MAU_1&2",
                    "RTC_1&2",
                ],
            )
            summary = self._validate_path(configuration_path)

        self.assertNotIn("terminal_fan", summary["missing_equipment_ids"])
        self.assertNotIn("auxiliary_load", summary["missing_equipment_ids"])
        self.assertIn("terminal_fan", summary["present_equipment_ids"])
        self.assertIn("auxiliary_load", summary["present_equipment_ids"])

    def test_validate_configuration_library_returns_multiple_summaries(self):
        with TemporaryDirectory() as temp_dir:
            self._make_configuration(temp_dir, "ACC_1MW_GRID_CDU", ["ACC_1"])
            self._make_configuration(
                temp_dir,
                "ABS_COOLINGTOWER_1MW_GRID_CDU",
                ["ABS_1", "COOLING_TOWER_1", "ENGINE_RADIATOR_1"],
            )
            summaries = validate_configuration_library(temp_dir)

        self.assertEqual(len(summaries), 2)
        self.assertEqual(
            {summary["topology_id"] for summary in summaries},
            {"acc", "abs_cooling_tower"},
        )

    def test_valid_acc_runtime_configuration_passes(self):
        library_input = build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")

        summary = validate_configuration_library(library_input)

        self.assertEqual(summary["status"], "valid")
        self.assertEqual(summary["configuration_id"], "ACC_1.5MW_GASENGINE_CDU")
        self.assertEqual(summary["topology"], "acc_gas_engine_cdu")
        self.assertEqual(summary["missing_roles"], [])
        self.assertEqual(summary["missing_curves"], [])

    def test_missing_required_runtime_equipment_fails(self):
        library_input = build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        del library_input["selected_curves"]["CHW_PUMP_2"]

        summary = validate_configuration_library(library_input)

        self.assertEqual(summary["status"], "error")
        self.assertIn("chw_pump", summary["missing_roles"])

    def test_missing_runtime_solver_curve_fails(self):
        library_input = build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        library_input["selected_curves"]["CHW_PUMP_2"] = {
            "sheet_name": None,
            "status": "Missing Solver_Curve",
            "curve": [],
        }

        summary = validate_configuration_library(library_input)

        self.assertEqual(summary["status"], "error")
        self.assertIn("chw_pump=CHW_PUMP_2", summary["missing_curves"])

    def test_validation_failure_stops_before_dispatch(self):
        library_input = build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        del library_input["selected_curves"]["CHW_PUMP_2"]

        with self.assertRaisesRegex(ValueError, "Configuration Library validation failed"):
            build_solver_input_from_configuration(
                library_input["configuration_manifest"],
                library_input,
            )

    def test_unknown_runtime_topology_fails(self):
        library_input = build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        library_input["configuration_manifest"]["solver_topology"] = "unknown_topology"

        summary = validate_configuration_library(library_input)

        self.assertEqual(summary["status"], "error")
        self.assertIn("Unknown solver_topology: unknown_topology", summary["warnings"])

    def test_existing_acc_annual_pue_unchanged_by_validation_layer(self):
        library_input = build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")

        validated = build_solver_input_from_configuration(
            library_input["configuration_manifest"],
            deepcopy(library_input),
        )
        previous = _build_acc_gas_engine_cdu_solver_input(deepcopy(library_input))

        validated_pue = compute_pue_project(validated)["annual_results"]["annual_average_PUE"]
        previous_pue = compute_pue_project(previous)["annual_results"]["annual_average_PUE"]
        self.assertLess(abs(validated_pue - previous_pue), 1e-9)


if __name__ == "__main__":
    unittest.main()
