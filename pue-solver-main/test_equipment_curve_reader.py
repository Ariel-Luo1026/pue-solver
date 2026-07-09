import contextlib
import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from equipment_curve_reader import (
    ELECTRICAL_EFFICIENCY,
    ELECTRICAL_LOSS_FRACTION,
    ELECTRICAL_LOSS_POWER,
    ONE_DIMENSIONAL_POWER,
    TWO_DIMENSIONAL_POWER,
    UNKNOWN_SCHEMA,
    find_equipment_workbook,
    read_equipment_solver_curve,
)
from test_acc_v2_curve_reader import _write_xlsx


class EquipmentCurveReaderTest(unittest.TestCase):
    def test_find_equipment_workbook_supports_aliases(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_config(temp_dir, {
                "CHW_PUMP_2": [["load_ratio", "power_kW"], [0.5, 20]],
                "CDU_2": [["load_ratio", "power_kW"], [0.5, 13]],
                "RTC_1&2": [["load_ratio", "power_kW"], [0.5, 12]],
                "MAU_1&2": [["load_ratio", "power_kW"], [0.5, 9]],
                "ELECTRICAL_DISTRIBUTION_2": [["load_ratio", "efficiency"], [0.5, 0.98]],
                "ENGINE_3": [["load_ratio", "engine_output_kW"], [0.5, 1500]],
                "ENGINE_RADIATOR_1": [["load_ratio", "power_kW"], [0.5, 30]],
            })

            self.assertEqual(find_equipment_workbook(config, "pump").parent.name, "CHW_PUMP_2")
            self.assertEqual(find_equipment_workbook(config, "chw_pump").parent.name, "CHW_PUMP_2")
            self.assertEqual(find_equipment_workbook(config, "rtc").parent.name, "RTC_1&2")
            self.assertEqual(find_equipment_workbook(config, "rtc_1_2").parent.name, "RTC_1&2")
            self.assertEqual(find_equipment_workbook(config, "rtc_1&2").parent.name, "RTC_1&2")
            self.assertEqual(find_equipment_workbook(config, "auxiliary_load").parent.name, "RTC_1&2")
            self.assertEqual(find_equipment_workbook(config, "mau").parent.name, "MAU_1&2")
            self.assertEqual(find_equipment_workbook(config, "cdu").parent.name, "CDU_2")
            self.assertEqual(find_equipment_workbook(config, "cdu_2").parent.name, "CDU_2")
            self.assertEqual(find_equipment_workbook(config, "electrical").parent.name, "ELECTRICAL_DISTRIBUTION_2")
            self.assertEqual(find_equipment_workbook(config, "electrical_loss").parent.name, "ELECTRICAL_DISTRIBUTION_2")
            self.assertEqual(find_equipment_workbook(config, "power_distribution").parent.name, "ELECTRICAL_DISTRIBUTION_2")
            self.assertEqual(find_equipment_workbook(config, "distribution_loss").parent.name, "ELECTRICAL_DISTRIBUTION_2")
            self.assertEqual(find_equipment_workbook(config, "engine").parent.name, "ENGINE_3")
            self.assertEqual(find_equipment_workbook(config, "gas_engine").parent.name, "ENGINE_3")
            self.assertEqual(find_equipment_workbook(config, "generator").parent.name, "ENGINE_3")
            self.assertEqual(find_equipment_workbook(config, "engine_3").parent.name, "ENGINE_3")
            self.assertEqual(find_equipment_workbook(config, "engine_radiator").parent.name, "ENGINE_RADIATOR_1")
            self.assertEqual(find_equipment_workbook(config, "radiator").parent.name, "ENGINE_RADIATOR_1")
            self.assertEqual(find_equipment_workbook(config, "engine_radiator_1").parent.name, "ENGINE_RADIATOR_1")

    def test_missing_workbook_and_solver_curve_report_errors(self):
        with TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "ACC_1.5MW_GASENGINE_CDU"
            (config / "equipment").mkdir(parents=True)

            missing = read_equipment_solver_curve(config, "pump")
            self.assertTrue(missing.errors)
            self.assertIn("workbook missing", missing.errors[0])

            folder = config / "equipment" / "CHW_PUMP_2"
            folder.mkdir()
            _write_xlsx(folder / "CHW_PUMP_2.xlsx", {"Information": [["A", "B"]]})
            no_sheet = read_equipment_solver_curve(config, "pump")
            self.assertIn("Solver_Curve sheet missing", no_sheet.errors[0])

    def test_schema_detection(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_config(temp_dir, {
                "CHW_PUMP_2": [["load_ratio", "power_kW"], [0.5, 20]],
                "ACC_2": [["ambient_C", "load_ratio", "power_input_kW"], [30, 0.5, 100]],
                "ELECTRICAL_DISTRIBUTION_2": [["load_ratio", "efficiency"], [0.5, 0.98]],
                "ENGINE_3": [["load_ratio", "engine_output_kW"], [0.5, 1500]],
                "ENGINE_RADIATOR_1": [["load_ratio", "radiator_fan_power_kW"], [0.5, 30]],
            })

            self.assertEqual(read_equipment_solver_curve(config, "pump").curve_type, ONE_DIMENSIONAL_POWER)
            self.assertEqual(read_equipment_solver_curve(config, "acc_unit").curve_type, TWO_DIMENSIONAL_POWER)
            self.assertEqual(
                read_equipment_solver_curve(config, "electrical_distribution").curve_type,
                ELECTRICAL_EFFICIENCY,
            )
            self.assertEqual(read_equipment_solver_curve(config, "engine").curve_type, ONE_DIMENSIONAL_POWER)
            self.assertEqual(read_equipment_solver_curve(config, "engine_radiator").curve_type, ONE_DIMENSIONAL_POWER)

    def test_electrical_loss_schema_detection(self):
        with TemporaryDirectory() as temp_dir:
            loss_fraction_config = _make_config(temp_dir, {
                "ELECTRICAL_DISTRIBUTION_2": [["load_ratio", "loss_fraction"], [0.5, 0.03]],
            })
            self.assertEqual(
                read_equipment_solver_curve(loss_fraction_config, "electrical_distribution").curve_type,
                ELECTRICAL_LOSS_FRACTION,
            )

        with TemporaryDirectory() as temp_dir:
            loss_power_config = _make_config(temp_dir, {
                "ELECTRICAL_DISTRIBUTION_2": [["load_ratio", "loss_kW"], [0.5, 30]],
            })
            self.assertEqual(
                read_equipment_solver_curve(loss_power_config, "electrical_distribution").curve_type,
                ELECTRICAL_LOSS_POWER,
            )

    def test_unknown_schema_reports_error(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_config(temp_dir, {
                "CHW_PUMP_2": [["flow", "head"], [1, 2]],
            })

            preview = read_equipment_solver_curve(config, "pump")

        self.assertEqual(preview.curve_type, UNKNOWN_SCHEMA)
        self.assertTrue(preview.errors)
        self.assertIn("Unknown Solver_Curve schema", preview.errors[0])

    def test_acc_solver_curve_success_prints_workbook_diagnostics(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_config(temp_dir, {
                "ACC_2": [
                    ["ambient_C", "load_ratio", "power_input_kW"],
                    [30, 0.5, 100],
                    [35, 1.0, 220],
                ],
            })
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                preview = read_equipment_solver_curve(config, "acc_unit")

        output = stdout.getvalue()
        self.assertFalse(preview.errors)
        self.assertIn("ACC workbook path=", output)
        self.assertIn("ACC_2.xlsx", output)
        self.assertIn("ACC workbook exists=True", output)
        self.assertRegex(output, r"ACC workbook file size=\d+")
        self.assertIn("ACC workbook loaded successfully", output)
        self.assertIn("ACC workbook sheet names=", output)
        self.assertIn("ACC Solver_Curve requested sheet name=Solver_Curve", output)
        self.assertIn("ACC Solver_Curve available sheet names=", output)
        self.assertIn("ACC Solver_Curve row count=2", output)
        self.assertIn("ACC Solver_Curve column count=3", output)
        self.assertIn("ACC Solver_Curve first five rows=", output)
        self.assertIn("'ambient_C': 30", output)

    def test_acc_solver_curve_missing_sheet_prints_available_sheets(self):
        with TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "ACC_1.5MW_GASENGINE_CDU"
            folder = config / "equipment" / "ACC_2"
            folder.mkdir(parents=True)
            _write_xlsx(folder / "ACC_2.xlsx", {"Information": [["A", "B"], [1, 2]]})
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                preview = read_equipment_solver_curve(config, "ACC_2")

        output = stdout.getvalue()
        self.assertTrue(preview.errors)
        self.assertIn("ACC workbook path=", output)
        self.assertIn("ACC workbook exists=True", output)
        self.assertIn("ACC workbook loaded successfully", output)
        self.assertIn("ACC Solver_Curve requested sheet name=Solver_Curve", output)
        self.assertIn("ACC Solver_Curve available sheet names=['Information']", output)
        self.assertIn("ACC Solver_Curve sheet missing; available sheet names=['Information']", output)


def _make_config(root, equipment_sheets):
    config = Path(root) / "ACC_1.5MW_GASENGINE_CDU"
    for folder_name, solver_curve_rows in equipment_sheets.items():
        folder = config / "equipment" / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        _write_xlsx(
            folder / f"{folder_name}.xlsx",
            {
                "Information": [["Parameter", "Value"], ["Equipment", folder_name]],
                "Metadata": [["Parameter", "Value"], ["source", "unit-test"]],
                "Performance_Map": [["placeholder"], ["not used"]],
                "Solver_Curve": solver_curve_rows,
                "Validation": [["Parameter", "Value"], ["Status", "Available"]],
            },
        )
    return config


if __name__ == "__main__":
    unittest.main()
