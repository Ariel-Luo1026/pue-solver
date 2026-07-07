import ast
import unittest
from pathlib import Path

from calculators.hourly_engine import HourlyContext, HourlySimulationEngine
from calculators.models import HourlyResult, make_hourly_result


class CustomResultEngine(HourlySimulationEngine):
    def run_single_hour(self, hourly_context):
        return make_hourly_result(
            hour_index=hourly_context.hour_index,
            it_load_kw=hourly_context.it_load,
            metadata={"engine": "custom"},
        )


class HourlyResultModelTest(unittest.TestCase):
    def test_hourly_result_instantiates(self):
        result = HourlyResult(
            hour_index=1,
            it_load_kw=4400.0,
            outdoor_dry_bulb_c=32.0,
            hourly_pue=1.2,
        )
        self.assertEqual(result.hour_index, 1)
        self.assertEqual(result.it_load_kw, 4400.0)
        self.assertEqual(result.equipment_results, {})
        self.assertEqual(result.warnings, [])

    def test_make_hourly_result_returns_hourly_result(self):
        result = make_hourly_result(hour_index=2, total_facility_power_kw=5200.0)
        self.assertIsInstance(result, HourlyResult)
        self.assertEqual(result.hour_index, 2)
        self.assertEqual(result.total_facility_power_kw, 5200.0)

    def test_safe_defaults_work(self):
        result = make_hourly_result()
        self.assertIsNone(result.hour_index)
        self.assertIsNone(result.hourly_pue)
        self.assertEqual(result.equipment_results, {})
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.metadata, {})

    def test_equipment_results_can_hold_per_equipment_data(self):
        result = make_hourly_result(
            hour_index=3,
            equipment_results={
                "acc_unit": {"power_kw": 900.0},
                "pump": {"power_kw": 50.0},
            },
        )
        self.assertEqual(result.equipment_results["acc_unit"]["power_kw"], 900.0)
        self.assertEqual(result.equipment_results["pump"]["power_kw"], 50.0)

    def test_models_do_not_import_solver(self):
        source = (Path(__file__).resolve().parent / "calculators" / "models.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.append(node.module)
        self.assertNotIn("solver", imported_modules)

    def test_hourly_engine_can_run_with_generic_result_objects(self):
        engine = CustomResultEngine([
            HourlyContext(hour_index=1, it_load=100.0),
            HourlyContext(hour_index=2, it_load=200.0),
        ])
        results = engine.run_hours()
        self.assertTrue(all(isinstance(result, HourlyResult) for result in results))
        self.assertEqual([result.it_load_kw for result in results], [100.0, 200.0])


if __name__ == "__main__":
    unittest.main()
