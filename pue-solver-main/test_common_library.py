import ast
import unittest
from pathlib import Path

from calculators.common.annual_statistics import (
    calculate_average,
    calculate_peak,
    calculate_total_energy,
)
from calculators.common.interpolation import interpolate_1d, interpolate_2d
from calculators.common.performance_curve import (
    CurveInterpolator,
    PerformanceCurve,
)
from calculators.common.pue_metrics import calculate_pue


class CommonCalculationLibraryTest(unittest.TestCase):
    def test_common_modules_import_and_basic_helpers_work(self):
        self.assertTrue(callable(interpolate_1d))
        self.assertTrue(callable(interpolate_2d))
        self.assertEqual(calculate_pue(120, 100), 1.2)
        self.assertEqual(calculate_average([1, 2, 3]), 2.0)
        self.assertEqual(calculate_total_energy([10, 20, 30]), 60.0)
        self.assertEqual(calculate_peak([10, 20, 30]), 30.0)

    def test_interpolation_helpers_are_callable_and_return_values(self):
        self.assertEqual(interpolate_1d([(0, 0), (10, 100)], 5), 50.0)
        self.assertEqual(interpolate_2d([(0, 0, 1), (10, 10, 2)], 9, 9), 2.0)

    def test_performance_curve_class_instantiates(self):
        curve = PerformanceCurve("test_curve", [(0, 0), (1, 10)])
        result = CurveInterpolator(curve).evaluate(0.5)
        self.assertEqual(curve.curve_id, "test_curve")
        self.assertEqual(result.value, 5.0)
        self.assertEqual(result.source, "test_curve")

    def test_common_modules_do_not_import_solver(self):
        common_dir = Path(__file__).resolve().parent / "calculators" / "common"
        imported_modules = []
        for path in common_dir.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_modules.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_modules.append(node.module)
        self.assertNotIn("solver", imported_modules)


if __name__ == "__main__":
    unittest.main()
