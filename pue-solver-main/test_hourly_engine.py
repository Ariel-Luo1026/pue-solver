import ast
import unittest
from pathlib import Path

from calculators.acc_calculator import ACCCalculator
from calculators.hourly_engine import (
    HourlyContext,
    HourlySimulationEngine,
    SimulationHooks,
)
from configuration_library_loader import build_solver_input_from_library
from library_solver_adapter import convert_library_input_to_solver_input
from solver import compute_pue_project


class RecordingHooks(SimulationHooks):
    def __init__(self):
        self.before = []
        self.after = []

    def before_hour(self, hourly_context):
        self.before.append(hourly_context.hour_index)

    def after_hour(self, hourly_context, result):
        self.after.append(result["hour_index"])


class HourlyEngineTest(unittest.TestCase):
    def test_hourly_context_instantiates(self):
        context = HourlyContext(
            hour_index=1,
            outdoor_temperature=30.0,
            wet_bulb_temperature=22.0,
            it_load=4400.0,
            metadata={"source": "test"},
        )
        self.assertEqual(context.hour_index, 1)
        self.assertEqual(context.metadata["source"], "test")

    def test_8760_loop_executes(self):
        hours = [HourlyContext(hour_index=index) for index in range(1, 8761)]
        engine = HourlySimulationEngine(hours=hours)
        results = engine.run_hours()

        self.assertEqual(len(results), 8760)
        self.assertEqual(results[0]["hour_index"], 1)
        self.assertEqual(results[-1]["hour_index"], 8760)

    def test_simulation_hooks_are_callable(self):
        hooks = RecordingHooks()
        hours = [HourlyContext(hour_index=1), HourlyContext(hour_index=2)]
        engine = HourlySimulationEngine(hours=hours, hooks=hooks)
        engine.run_hours()

        self.assertEqual(hooks.before, [1, 2])
        self.assertEqual(hooks.after, [1, 2])

    def test_acc_calculator_can_instantiate_hourly_engine_without_using_it_in_run(self):
        engine = ACCCalculator().create_hourly_engine([HourlyContext(hour_index=1)])
        self.assertIsInstance(engine, HourlySimulationEngine)
        self.assertEqual(engine.run_hours()[0]["hour_index"], 1)

    def test_hourly_engine_has_no_solver_ui_or_report_dependency(self):
        source = (Path(__file__).resolve().parent / "calculators" / "hourly_engine.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.append(node.module)
        self.assertNotIn("solver", imported_modules)
        self.assertNotIn("ui", imported_modules)
        self.assertNotIn("report", imported_modules)

    def test_acc_calculator_run_still_matches_legacy_solver_result(self):
        sample = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        legacy_result = compute_pue_project(sample)
        calculator_result = ACCCalculator().run(sample)
        self.assertEqual(
            calculator_result["annual_results"]["annual_average_PUE"],
            legacy_result["annual_results"]["annual_average_PUE"],
        )
        self.assertEqual(
            calculator_result["annual_results"]["annual_facility_energy_kWh"],
            legacy_result["annual_results"]["annual_facility_energy_kWh"],
        )


if __name__ == "__main__":
    unittest.main()
