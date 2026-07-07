import ast
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from acc_v2_diagnostics import (
    ACCV2Diagnostic,
    CurveSummary,
    ValidationSummary,
    build_acc_v2_preview,
    sample_lookup_report,
    summarize_acc_curve,
    summarize_cdu_curve,
    summarize_rtc_curve,
    validate_acc_dataset,
)
from acc_v2_curve_reader import ACCV2CurvePreview, EquipmentCurvePreview
from test_acc_v2_curve_reader import _make_configuration


class ACCV2DiagnosticsTest(unittest.TestCase):
    def test_successful_preview_build(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_configuration(
                temp_dir,
                {
                    "ACC_2": [
                        ["ambient_C", "load_ratio", "capacity_kW", "power_input_kW", "unit_efficiency_kW_per_kW"],
                        [20, 0.5, 1000, 250, 4],
                        [20, 1.0, 1200, 400, 3],
                        [30, 0.5, 900, 300, 3],
                        [30, 1.0, 1100, 500, 2.2],
                    ],
                    "RTC_1&2": [["load_ratio", "power_kW"], [0.5, 10], [1.0, 20]],
                    "CDU_2": [["load_ratio", "power_kW"], [0.5, 13], [1.0, 13]],
                    "CHW_PUMP_2": [["load_ratio", "power_kW"], [0.5, 20], [1.0, 60]],
                },
            )

            diagnostic = build_acc_v2_preview(config)

        self.assertIsInstance(diagnostic, ACCV2Diagnostic)
        self.assertEqual(diagnostic.validation_summary.validation_status, "valid")
        self.assertIn("acc_unit", diagnostic.curve_summaries)
        self.assertIn("rtc", diagnostic.lookup_samples)
        self.assertFalse(diagnostic.errors)

    def test_acc_summary_generation(self):
        summary = summarize_acc_curve(_acc_preview())

        self.assertIsInstance(summary, CurveSummary)
        self.assertEqual(summary.minimum_ambient_C, 20)
        self.assertEqual(summary.maximum_ambient_C, 30)
        self.assertEqual(summary.ambient_count, 2)
        self.assertEqual(summary.minimum_load_ratio, 0.5)
        self.assertEqual(summary.maximum_load_ratio, 1.0)
        self.assertEqual(summary.load_ratio_count, 2)
        self.assertEqual(summary.number_of_points, 4)
        self.assertEqual(summary.capacity_range, (900.0, 1200.0))
        self.assertEqual(summary.power_range, (250.0, 500.0))
        self.assertEqual(summary.cop_range, (2.2, 4.0))

    def test_rtc_and_cdu_summary_generation(self):
        rtc = summarize_rtc_curve(_power_preview("rtc", [{"load_ratio": 0.25, "power_kW": 8}, {"load_ratio": 1, "power_kW": 20}]))
        cdu = summarize_cdu_curve(_power_preview("cdu", [{"load_ratio": 0, "power_kW": 13}, {"load_ratio": 1, "power_kW": 13}]))

        self.assertEqual(rtc.minimum_load_ratio, 0.25)
        self.assertEqual(rtc.maximum_load_ratio, 1.0)
        self.assertEqual(rtc.power_range, (8.0, 20.0))
        self.assertEqual(rtc.number_of_points, 2)
        self.assertEqual(cdu.power_range, (13.0, 13.0))

    def test_dataset_validation_valid_dataset(self):
        validation = validate_acc_dataset(_acc_preview())

        self.assertIsInstance(validation, ValidationSummary)
        self.assertEqual(validation.validation_status, "valid")
        self.assertEqual(validation.errors, ())

    def test_warning_collection_for_single_point_dataset(self):
        validation = validate_acc_dataset(
            _acc_preview(rows=[_acc_row(25, 0.8, 1000, 300, 3.333)])
        )

        self.assertEqual(validation.validation_status, "valid")
        self.assertTrue(any("single operating point" in warning for warning in validation.warnings))

    def test_lookup_sampling(self):
        preview = ACCV2CurvePreview(
            configuration_name="test",
            equipment_curves={
                "acc_unit": _acc_preview(),
                "rtc": _power_preview("rtc", [{"load_ratio": 0.5, "power_kW": 10}, {"load_ratio": 1.0, "power_kW": 20}]),
                "cdu": _power_preview("cdu", [{"load_ratio": 0.5, "power_kW": 13}, {"load_ratio": 1.0, "power_kW": 13}]),
            },
        )

        report = sample_lookup_report(preview)

        self.assertEqual(len(report["acc_unit"]["samples"]), 3)
        self.assertEqual(len(report["rtc"]["samples"]), 3)
        self.assertEqual(len(report["cdu"]["samples"]), 3)
        self.assertFalse(report["acc_unit"]["errors"])

    def test_empty_datasets(self):
        empty_acc = _acc_preview(rows=[])
        validation = validate_acc_dataset(empty_acc)
        summary = summarize_acc_curve(empty_acc)
        preview = ACCV2CurvePreview(configuration_name="empty", equipment_curves={"acc_unit": empty_acc})
        samples = sample_lookup_report(preview)

        self.assertEqual(validation.validation_status, "invalid")
        self.assertTrue(validation.errors)
        self.assertEqual(summary.number_of_points, 0)
        self.assertTrue(samples["acc_unit"]["errors"])

    def test_invalid_dataset_reports_errors_without_raising(self):
        preview = _acc_preview(rows=[
            _acc_row(20, 0.5, -1, 250, 4),
            _acc_row(20, 0.5, 1000, 250, 4),
            {"ambient_C": "bad", "load_ratio": 1, "capacity_kW": 1000, "power_input_kW": 0, "unit_efficiency_kW_per_kW": 3},
        ])

        validation = validate_acc_dataset(preview)

        self.assertEqual(validation.validation_status, "invalid")
        self.assertTrue(any("capacity_kW must be positive" in error for error in validation.errors))
        self.assertTrue(any("Duplicate ACC operating point" in error for error in validation.errors))
        self.assertTrue(any("ambient_C is missing or non-numeric" in error for error in validation.errors))

    def test_incomplete_grid_is_invalid(self):
        preview = _acc_preview(rows=[
            _acc_row(20, 0.5, 1000, 250, 4),
            _acc_row(20, 1.0, 1200, 400, 3),
            _acc_row(30, 0.5, 900, 300, 3),
        ])

        validation = validate_acc_dataset(preview)

        self.assertEqual(validation.validation_status, "invalid")
        self.assertTrue(any("grid is incomplete" in error for error in validation.errors))

    def test_diagnostics_module_does_not_import_solver(self):
        diagnostics_path = Path(__file__).with_name("acc_v2_diagnostics.py")
        tree = ast.parse(diagnostics_path.read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)

        self.assertNotIn("solver", imports)


def _acc_preview(rows=None):
    if rows is None:
        rows = [
            _acc_row(20, 0.5, 1000, 250, 4),
            _acc_row(20, 1.0, 1200, 400, 3),
            _acc_row(30, 0.5, 900, 300, 3),
            _acc_row(30, 1.0, 1100, 500, 2.2),
        ]
    return EquipmentCurvePreview(
        equipment_id="acc_unit",
        folder_name="ACC_2",
        workbook_path=None,
        solver_curve_rows=rows,
        required_columns_present=True,
    )


def _power_preview(equipment_id, rows):
    return EquipmentCurvePreview(
        equipment_id=equipment_id,
        folder_name=equipment_id,
        workbook_path=None,
        solver_curve_rows=rows,
        required_columns_present=True,
    )


def _acc_row(ambient, load, capacity, power, cop):
    return {
        "ambient_C": ambient,
        "load_ratio": load,
        "capacity_kW": capacity,
        "power_input_kW": power,
        "unit_efficiency_kW_per_kW": cop,
    }


if __name__ == "__main__":
    unittest.main()
