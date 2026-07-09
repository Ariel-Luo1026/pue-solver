import ast
import unittest
from pathlib import Path

from acc_v2_curve_lookup import (
    ACCOperatingPoint,
    CDUOperatingPoint,
    CHWPumpOperatingPoint,
    RTCOperatingPoint,
    lookup_acc_curve,
    lookup_cdu_curve,
    lookup_chw_pump_curve,
    lookup_rtc_curve,
)
from acc_v2_curve_reader import EquipmentCurvePreview


class ACCV2CurveLookupTest(unittest.TestCase):
    def _acc_preview(self, rows=None):
        if rows is None:
            rows = [
                _acc_row(20, 0.5, 1000, 250, 4.0),
                _acc_row(20, 1.0, 1200, 400, 3.0),
                _acc_row(30, 0.5, 900, 300, 3.0),
                _acc_row(30, 1.0, 1100, 500, 2.2),
            ]
        return EquipmentCurvePreview(
            equipment_id="acc_unit",
            folder_name="ACC_2",
            workbook_path=None,
            solver_curve_rows=rows,
            required_columns_present=True,
        )

    def _power_preview(self, equipment_id, rows):
        return EquipmentCurvePreview(
            equipment_id=equipment_id,
            folder_name=equipment_id,
            workbook_path=None,
            solver_curve_rows=rows,
            required_columns_present=True,
        )

    def test_acc_exact_lookup(self):
        point = lookup_acc_curve(self._acc_preview(), ambient_C=20, load_ratio=0.5)

        self.assertIsInstance(point, ACCOperatingPoint)
        self.assertEqual(point.ambient_C, 20)
        self.assertEqual(point.load_ratio, 0.5)
        self.assertEqual(point.capacity_kW, 1000)
        self.assertEqual(point.power_input_kW, 250)
        self.assertEqual(point.unit_efficiency_kW_per_kW, 4.0)
        self.assertEqual(point.cop, 4.0)

    def test_acc_load_interpolation(self):
        point = lookup_acc_curve(self._acc_preview(), ambient_C=20, load_ratio=0.75)

        self.assertEqual(point.ambient_C, 20)
        self.assertEqual(point.load_ratio, 0.75)
        self.assertEqual(point.capacity_kW, 1100)
        self.assertEqual(point.power_input_kW, 325)
        self.assertEqual(point.cop, 3.5)

    def test_acc_ambient_interpolation(self):
        point = lookup_acc_curve(self._acc_preview(), ambient_C=25, load_ratio=0.5)

        self.assertEqual(point.ambient_C, 25)
        self.assertEqual(point.load_ratio, 0.5)
        self.assertEqual(point.capacity_kW, 950)
        self.assertEqual(point.power_input_kW, 275)
        self.assertEqual(point.cop, 3.5)

    def test_acc_bilinear_interpolation(self):
        point = lookup_acc_curve(self._acc_preview(), ambient_C=25, load_ratio=0.75)

        self.assertEqual(point.ambient_C, 25)
        self.assertEqual(point.load_ratio, 0.75)
        self.assertEqual(point.capacity_kW, 1050)
        self.assertEqual(point.power_input_kW, 362.5)
        self.assertAlmostEqual(point.cop, 3.05)

    def test_acc_capacity_surface_uses_required_capacity_not_load_ratio(self):
        preview = self._acc_preview(rows=[
            {"ambient_C": 20, "capacity_kW": 500, "power_input_kW": 100},
            {"ambient_C": 20, "capacity_kW": 1000, "power_input_kW": 300},
            {"ambient_C": 30, "capacity_kW": 500, "power_input_kW": 150},
            {"ambient_C": 30, "capacity_kW": 1000, "power_input_kW": 450},
        ])

        point = lookup_acc_curve(
            preview,
            ambient_C=25,
            load_ratio=0.1,
            required_capacity_kW=750,
            nominal_unit_capacity_kW=1000,
        )

        self.assertEqual(point.required_capacity_kW, 750)
        self.assertAlmostEqual(point.power_input_kW, 250)
        self.assertAlmostEqual(point.diagnostic_load_ratio, 0.75)

    def test_acc_capacity_surface_clamps_capacity(self):
        preview = self._acc_preview(rows=[
            {"ambient_C": 20, "capacity_kW": 500, "power_input_kW": 100},
            {"ambient_C": 20, "capacity_kW": 1000, "power_input_kW": 300},
        ])

        point = lookup_acc_curve(preview, ambient_C=20, required_capacity_kW=1200)

        self.assertEqual(point.capacity_kW, 1000)
        self.assertTrue(point.capacity_clamped)

    def test_acc_lower_clamp(self):
        point = lookup_acc_curve(self._acc_preview(), ambient_C=5, load_ratio=0.1)

        self.assertEqual(point.ambient_C, 20)
        self.assertEqual(point.load_ratio, 0.5)
        self.assertEqual(point.capacity_kW, 1000)

    def test_acc_upper_clamp(self):
        point = lookup_acc_curve(self._acc_preview(), ambient_C=45, load_ratio=1.5)

        self.assertEqual(point.ambient_C, 30)
        self.assertEqual(point.load_ratio, 1.0)
        self.assertEqual(point.capacity_kW, 1100)

    def test_rtc_interpolation(self):
        preview = self._power_preview(
            "rtc",
            [{"load_ratio": 0.0, "power_kW": 10}, {"load_ratio": 1.0, "power_kW": 20}],
        )

        point = lookup_rtc_curve(preview, load_ratio=0.25)

        self.assertIsInstance(point, RTCOperatingPoint)
        self.assertEqual(point.load_ratio, 0.25)
        self.assertEqual(point.power_kW, 12.5)

    def test_cdu_interpolation(self):
        preview = self._power_preview(
            "cdu",
            [{"load_ratio": 0.0, "power_kW": 12}, {"load_ratio": 1.0, "power_kW": 16}],
        )

        point = lookup_cdu_curve(preview, load_ratio=0.75)

        self.assertIsInstance(point, CDUOperatingPoint)
        self.assertEqual(point.load_ratio, 0.75)
        self.assertEqual(point.power_kW, 15)

    def test_chw_pump_exact_lookup_and_source(self):
        preview = self._power_preview(
            "pump",
            [{"load_ratio": 0.0, "power_kW": 5}, {"load_ratio": 1.0, "power_kW": 60}],
        )

        point = lookup_chw_pump_curve(preview, load_ratio=1.0)

        self.assertIsInstance(point, CHWPumpOperatingPoint)
        self.assertEqual(point.load_ratio, 1.0)
        self.assertEqual(point.power_kW, 60)
        self.assertEqual(point.source, "configuration_library_solver_curve")

    def test_chw_pump_interpolation_and_clamps(self):
        preview = self._power_preview(
            "pump",
            [{"load_ratio": 0.2, "power_kW": 10}, {"load_ratio": 0.8, "power_kW": 40}],
        )

        self.assertAlmostEqual(lookup_chw_pump_curve(preview, load_ratio=0.5).power_kW, 25)
        self.assertEqual(lookup_chw_pump_curve(preview, load_ratio=-1).load_ratio, 0.2)
        self.assertEqual(lookup_chw_pump_curve(preview, load_ratio=2).load_ratio, 0.8)

    def test_rtc_lower_and_upper_clamp(self):
        preview = self._power_preview(
            "rtc",
            [{"load_ratio": 0.2, "power_kW": 10}, {"load_ratio": 0.8, "power_kW": 16}],
        )

        self.assertEqual(lookup_rtc_curve(preview, load_ratio=-1).load_ratio, 0.2)
        self.assertEqual(lookup_rtc_curve(preview, load_ratio=2).load_ratio, 0.8)

    def test_single_row_curves(self):
        acc = lookup_acc_curve(
            self._acc_preview(rows=[_acc_row(25, 0.8, 1000, 300, 3.333333)]),
            ambient_C=99,
            load_ratio=0,
        )
        rtc = lookup_rtc_curve(
            self._power_preview("rtc", [{"load_ratio": 0.6, "power_kW": 11}]),
            load_ratio=0.1,
        )

        self.assertEqual(acc.ambient_C, 25)
        self.assertEqual(acc.load_ratio, 0.8)
        self.assertEqual(acc.capacity_kW, 1000)
        self.assertEqual(rtc.load_ratio, 0.6)
        self.assertEqual(rtc.power_kW, 11)

    def test_acc_duplicate_rejection(self):
        preview = self._acc_preview(rows=[
            _acc_row(20, 0.5, 1000, 250, 4),
            _acc_row(20, 0.5, 1001, 251, 4),
        ])

        with self.assertRaisesRegex(ValueError, "Duplicate ACC lookup grid point"):
            lookup_acc_curve(preview, 20, 0.5)

    def test_power_curve_duplicate_rejection(self):
        preview = self._power_preview(
            "rtc",
            [{"load_ratio": 0.5, "power_kW": 10}, {"load_ratio": 0.5, "power_kW": 11}],
        )

        with self.assertRaisesRegex(ValueError, "Duplicate RTC load_ratio point"):
            lookup_rtc_curve(preview, 0.5)

        with self.assertRaisesRegex(ValueError, "Duplicate CHW pump load_ratio point"):
            lookup_chw_pump_curve(preview, 0.5)

    def test_acc_inconsistent_grid_rejection(self):
        preview = self._acc_preview(rows=[
            _acc_row(20, 0.5, 1000, 250, 4),
            _acc_row(20, 1.0, 1200, 400, 3),
            _acc_row(30, 0.5, 900, 300, 3),
        ])

        with self.assertRaisesRegex(ValueError, "grid is inconsistent"):
            lookup_acc_curve(preview, 25, 0.75)

    def test_invalid_data_rejection(self):
        preview = self._acc_preview(rows=[
            _acc_row(20, 0.5, 1000, 250, "bad"),
        ])

        with self.assertRaisesRegex(ValueError, "Invalid numeric value"):
            lookup_acc_curve(preview, 20, 0.5)

    def test_empty_curve_rejection(self):
        with self.assertRaisesRegex(ValueError, "ACC curve contains no rows"):
            lookup_acc_curve(self._acc_preview(rows=[]), 20, 0.5)

        with self.assertRaisesRegex(ValueError, "RTC curve contains no rows"):
            lookup_rtc_curve(self._power_preview("rtc", []), 0.5)

    def test_missing_interpolation_neighbor_rejection(self):
        preview = self._acc_preview(rows=[
            _acc_row(20, 0.5, 1000, 250, 4),
            _acc_row(20, 1.0, 1200, 400, 3),
            _acc_row(30, 0.5, 900, 300, 3),
            _acc_row(30, 1.0, 1100, 500, 2.2),
            _acc_row(40, 0.5, 800, 350, 2.28),
        ])

        with self.assertRaisesRegex(ValueError, "grid is inconsistent"):
            lookup_acc_curve(preview, 35, 0.75)

    def test_lookup_module_does_not_import_solver(self):
        lookup_path = Path(__file__).with_name("acc_v2_curve_lookup.py")
        tree = ast.parse(lookup_path.read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)

        self.assertNotIn("solver", imports)


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
