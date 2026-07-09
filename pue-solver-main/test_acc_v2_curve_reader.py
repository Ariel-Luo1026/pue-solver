import contextlib
import io
import ast
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from xml.sax.saxutils import escape

from acc_v2_curve_reader import (
    ACCV2CurvePreview,
    ACC_SOLVER_CURVE_COLUMNS,
    CDU_SOLVER_CURVE_COLUMNS,
    CHW_PUMP_SOLVER_CURVE_COLUMNS,
    EquipmentCurvePreview,
    RTC_SOLVER_CURVE_COLUMNS,
    derive_acc_cop_if_missing,
    find_equipment_workbook,
    read_acc_v2_equipment_curves,
    read_equipment_solver_curve,
    validate_solver_curve_columns,
)


class ACCV2CurveReaderTest(unittest.TestCase):
    def test_acc_solver_curve_reads_required_columns(self):
        with TemporaryDirectory() as temp_dir:
            workbook = Path(temp_dir) / "ACC_2.xlsx"
            _write_xlsx(
                workbook,
                {
                    "Solver_Curve": [
                        list(ACC_SOLVER_CURVE_COLUMNS),
                        [35, 1300, 420],
                    ]
                },
            )

            rows = read_equipment_solver_curve(workbook, ACC_SOLVER_CURVE_COLUMNS)

        self.assertEqual(rows[0]["ambient_C"], 35)
        self.assertEqual(rows[0]["capacity_kW"], 1300)
        self.assertEqual(rows[0]["power_input_kW"], 420)

    def test_acc_solver_curve_reader_prints_workbook_diagnostics(self):
        with TemporaryDirectory() as temp_dir:
            workbook = Path(temp_dir) / "ACC_2.xlsx"
            _write_xlsx(
                workbook,
                {
                    "Solver_Curve": [
                        list(ACC_SOLVER_CURVE_COLUMNS),
                        [35, 1300, 420],
                    ],
                    "Information": [["Parameter", "Value"], ["Equipment", "ACC_2"]],
                },
            )
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                rows = read_equipment_solver_curve(workbook, ACC_SOLVER_CURVE_COLUMNS)

        output = stdout.getvalue()
        self.assertEqual(len(rows), 1)
        self.assertIn("ACC workbook path=", output)
        self.assertIn("ACC workbook exists=True", output)
        self.assertRegex(output, r"ACC workbook file size=\d+")
        self.assertIn("ACC workbook loaded successfully", output)
        self.assertIn("ACC workbook sheet names=", output)
        self.assertIn("ACC Solver_Curve requested sheet name=Solver_Curve", output)
        self.assertIn("ACC Solver_Curve available sheet names=", output)
        self.assertIn("ACC Solver_Curve row count=1", output)
        self.assertIn("ACC Solver_Curve column count=3", output)
        self.assertIn("ACC Solver_Curve first five rows=", output)

    def test_acc_cop_is_derived_if_missing(self):
        row, warnings = derive_acc_cop_if_missing(
            {"ambient_C": 35, "load_ratio": 0.8, "capacity_kW": 1300, "power_input_kW": 425}
        )

        self.assertAlmostEqual(row["unit_efficiency_kW_per_kW"], 1300 / 425)
        self.assertTrue(any("derived COP" in warning for warning in warnings))

    def test_rtc_solver_curve_reads_power_curve(self):
        with TemporaryDirectory() as temp_dir:
            workbook = Path(temp_dir) / "RTC_1&2.xlsx"
            _write_xlsx(workbook, {"Solver_Curve": [["load_ratio", "power_kW"], [0.5, 12.0]]})

            rows = read_equipment_solver_curve(workbook, RTC_SOLVER_CURVE_COLUMNS)

        self.assertEqual(rows, [{"load_ratio": 0.5, "power_kW": 12}])

    def test_cdu_fixed_power_solver_curve_reads_power_curve(self):
        with TemporaryDirectory() as temp_dir:
            workbook = Path(temp_dir) / "CDU_2.xlsx"
            _write_xlsx(
                workbook,
                {
                    "Solver_Curve": [
                        ["load_ratio", "power_kW"],
                        [0.1, 13],
                        [0.5, 13],
                        [1.0, 13],
                    ]
                },
            )

            rows = read_equipment_solver_curve(workbook, CDU_SOLVER_CURVE_COLUMNS)

        self.assertEqual([row["power_kW"] for row in rows], [13, 13, 13])

    def test_chw_pump_solver_curve_reads_power_curve(self):
        with TemporaryDirectory() as temp_dir:
            workbook = Path(temp_dir) / "CHW_PUMP_2.xlsx"
            _write_xlsx(
                workbook,
                {
                    "Solver_Curve": [
                        ["load_ratio", "power_kW"],
                        [0.1, 5],
                        [0.5, 20],
                        [1.0, 60],
                    ]
                },
            )

            rows = read_equipment_solver_curve(workbook, CHW_PUMP_SOLVER_CURVE_COLUMNS)

        self.assertEqual([row["power_kW"] for row in rows], [5, 20, 60])

    def test_chw_pump_preview_accepts_scenario_solver_curve_sheets(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_configuration(
                temp_dir,
                {
                    "ACC_2": [["ambient_C", "load_ratio", "capacity_kW", "power_input_kW"], [35, 0.8, 1300, 425]],
                    "RTC_1&2": [["load_ratio", "power_kW"], [0.8, 12]],
                    "CDU_2": [["load_ratio", "power_kW"], [0.8, 13]],
                    "CHW_PUMP_2": [["load_ratio", "power_kW"], [0.8, 20]],
                },
            )
            _replace_pump_with_scenario_curves(config)

            preview = read_acc_v2_equipment_curves(config)

        pump = preview.equipment_curves["pump"]
        self.assertEqual(preview.validation_status, "valid")
        self.assertTrue(pump.required_columns_present)
        self.assertEqual(pump.missing_columns, [])
        self.assertEqual(pump.metadata["selected_solver_curve_sheet"], "Solver_Curve_Normal")
        self.assertEqual([row["power_kW"] for row in pump.solver_curve_rows], [15, 45])

    def test_missing_solver_curve_produces_clear_error(self):
        with TemporaryDirectory() as temp_dir:
            workbook = Path(temp_dir) / "ACC_2.xlsx"
            _write_xlsx(workbook, {"Information": [["Parameter", "Value"], ["Equipment", "ACC"]]})

            with self.assertRaisesRegex(ValueError, "Solver_Curve sheet missing"):
                read_equipment_solver_curve(workbook, ACC_SOLVER_CURVE_COLUMNS)

    def test_missing_required_columns_produces_validation_error(self):
        rows = [{"load_ratio": 0.5, "power_kW": 12}]

        validation = validate_solver_curve_columns(rows, ("load_ratio", "power_kW", "ambient_C"))

        self.assertFalse(validation["required_columns_present"])
        self.assertEqual(validation["missing_columns"], ["ambient_C"])

    def test_duplicate_acc_ambient_and_capacity_produces_warning(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_configuration(
                temp_dir,
                {
                    "ACC_2": [
                        ["ambient_C", "load_ratio", "capacity_kW", "power_input_kW"],
                        [35, 0.8, 1300, 425],
                        [35, 0.8, 1300, 425],
                    ],
                    "RTC_1&2": [["load_ratio", "power_kW"], [0.8, 12]],
                    "CDU_2": [["load_ratio", "power_kW"], [0.8, 13]],
                    "CHW_PUMP_2": [["load_ratio", "power_kW"], [0.8, 20]],
                },
            )

            preview = read_acc_v2_equipment_curves(config)

        self.assertTrue(any("duplicate ambient_C/capacity_kW" in warning for warning in preview.warnings))

    def test_find_equipment_workbook_resolves_required_equipment(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_configuration(
                temp_dir,
                {
                    "ACC_2": [["ambient_C", "load_ratio", "capacity_kW", "power_input_kW"], [35, 0.8, 1300, 425]],
                    "RTC_1&2": [["load_ratio", "power_kW"], [0.8, 12]],
                    "CDU_2": [["load_ratio", "power_kW"], [0.8, 13]],
                    "CHW_PUMP_2": [["load_ratio", "power_kW"], [0.8, 20]],
                },
            )

            self.assertEqual(find_equipment_workbook(config, "acc_unit").parent.name, "ACC_2")
            self.assertEqual(find_equipment_workbook(config, "rtc").parent.name, "RTC_1&2")
            self.assertEqual(find_equipment_workbook(config, "cdu").parent.name, "CDU_2")
            self.assertEqual(find_equipment_workbook(config, "pump").parent.name, "CHW_PUMP_2")

    def test_alias_lookup_resolves_rtc_workbook(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_configuration(
                temp_dir,
                {
                    "RTC_1&2": [["load_ratio", "power_kW"], [0.8, 12]],
                },
            )

            workbook = find_equipment_workbook(config, "auxiliary_load")

        self.assertIsNotNone(workbook)
        self.assertEqual(workbook.parent.name, "RTC_1&2")

    def test_reader_does_not_import_solver(self):
        reader_path = Path(__file__).with_name("acc_v2_curve_reader.py")
        tree = ast.parse(reader_path.read_text(encoding="utf-8"))
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

        self.assertNotIn("solver", imported_modules)

    def test_read_acc_v2_equipment_curves_returns_preview(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_configuration(
                temp_dir,
                {
                    "ACC_2": [["ambient_C", "load_ratio", "capacity_kW", "power_input_kW"], [35, 0.8, 1300, 425]],
                    "RTC_1&2": [["load_ratio", "power_kW"], [0.8, 12]],
                    "CDU_2": [["load_ratio", "power_kW"], [0.8, 13]],
                    "CHW_PUMP_2": [["load_ratio", "power_kW"], [0.8, 20]],
                },
            )

            preview = read_acc_v2_equipment_curves(config)

        self.assertIsInstance(preview, ACCV2CurvePreview)
        self.assertEqual(preview.validation_status, "valid")
        self.assertIsInstance(preview.equipment_curves["acc_unit"], EquipmentCurvePreview)
        self.assertIn("rtc", preview.equipment_curves)
        self.assertIn("cdu", preview.equipment_curves)
        self.assertIn("pump", preview.equipment_curves)

    def test_current_legacy_acc_result_remains_unchanged_by_design(self):
        reader_path = Path(__file__).with_name("acc_v2_curve_reader.py").read_text(encoding="utf-8")

        self.assertNotIn("compute_pue_project", reader_path)
        self.assertNotIn("compute_acc_excel", reader_path)


def _make_configuration(root, equipment_sheets):
    config = Path(root) / "ACC_1.5MW_GASENGINE_CDU"
    equipment_root = config / "equipment"
    equipment_root.mkdir(parents=True)
    for folder_name, solver_curve_rows in equipment_sheets.items():
        folder = equipment_root / folder_name
        folder.mkdir()
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


def _replace_pump_with_scenario_curves(config):
    folder = Path(config) / "equipment" / "CHW_PUMP_2"
    _write_xlsx(
        folder / "CHW_PUMP_2.xlsx",
        {
            "Information": [["Parameter", "Value"], ["Equipment", "CHW_PUMP_2"]],
            "Metadata": [["Parameter", "Value"], ["source", "unit-test"]],
            "Performance_Map": [["placeholder"], ["not used"]],
            "Solver_Curve_Normal": [["load_ratio", "power_kW"], [0.5, 15], [1.0, 45]],
            "Solver_Curve_Failure": [["load_ratio", "power_kW"], [0.5, 20], [1.0, 60]],
            "Validation": [["Parameter", "Value"], ["Status", "Available"]],
        },
    )


def _write_xlsx(path, sheets):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            _workbook_xml(list(sheets)),
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            _relationships_xml(len(sheets)),
        )
        for index, rows in enumerate(sheets.values(), start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(rows))


def _workbook_xml(sheet_names):
    sheet_nodes = "\n".join(
        f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(sheet_names, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheet_nodes}</sheets>"
        "</workbook>"
    )


def _relationships_xml(sheet_count):
    relationships = "\n".join(
        '<Relationship '
        f'Id="rId{index}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{relationships}"
        "</Relationships>"
    )


def _sheet_xml(rows):
    row_nodes = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            reference = f"{_column_letter(column_index)}{row_index}"
            if isinstance(value, (int, float)):
                cells.append(f'<c r="{reference}"><v>{value}</v></c>')
            elif value is None:
                continue
            else:
                cells.append(
                    f'<c r="{reference}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
                )
        row_nodes.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(row_nodes)}</sheetData>'
        "</worksheet>"
    )


def _column_letter(index):
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


if __name__ == "__main__":
    unittest.main()
