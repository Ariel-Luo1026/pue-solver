import ast
import unittest
from pathlib import Path

import calculation_adapter
from calculation_adapter import build_standard_context, run_calculation_adapter
from calculators.models import (
    CalculationContext,
    CalculationResult,
    CalculatorCapability,
)


class CalculatorModelsTest(unittest.TestCase):
    def test_calculation_context_instantiates(self):
        context = CalculationContext(
            configuration_name="ACC_1.5MW_GASENGINE_CDU",
            topology_id="acc",
            topology_display_name="ACC",
            cooling_system_type="ACC",
            power_source="Gas Engine",
            unit_capacity=1.5,
            solver_mode="acc_hourly",
        )
        self.assertEqual(context.topology_id, "acc")
        self.assertEqual(context.equipment, [])
        self.assertEqual(context.performance_requirements, [])

    def test_calculation_result_instantiates(self):
        result = CalculationResult(
            annual_results={"annual_average_PUE": 1.2},
            solver_version="legacy",
            calculator_id="acc_calculator",
        )
        self.assertEqual(result.annual_results["annual_average_PUE"], 1.2)
        self.assertEqual(result.hourly_results, [])
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.errors, [])

    def test_calculator_capability_instantiates(self):
        capability = CalculatorCapability(
            calculator_id="acc_calculator",
            display_name="ACC Calculator",
            supported_topologies=["acc"],
            supported_solver_modes=["acc_hourly"],
            implementation_status="legacy_wrapper",
        )
        self.assertEqual(capability.supported_topologies, ["acc"])
        self.assertEqual(capability.implementation_status, "legacy_wrapper")

    def test_build_standard_context_returns_calculation_context(self):
        context = build_standard_context({
            "cooling_system_type": "ACC",
            "power_source": "Gas Engine",
            "cooling_unit_capacity_mw": 1.5,
            "configuration_name": "ACC_1.5MW_GASENGINE_CDU",
        })
        self.assertIsInstance(context, CalculationContext)
        self.assertEqual(context.topology_id, "acc")
        self.assertEqual(context.topology_display_name, "ACC")
        self.assertEqual(context.solver_mode, "acc_hourly")
        self.assertTrue(context.equipment)
        self.assertTrue(context.performance_requirements)

    def test_existing_adapter_behavior_is_unchanged(self):
        result = run_calculation_adapter({
            "cooling_system_type": "ACC",
            "power_source": "Grid",
            "cooling_unit_capacity_mw": 1,
        })
        self.assertIsInstance(result["context"], dict)
        self.assertEqual(result["solver_mode"], "acc_hourly")

    def test_models_and_standard_context_have_no_solver_ui_or_report_dependency(self):
        root = Path(__file__).resolve().parent
        sources = [
            root / "calculators" / "models.py",
            Path(calculation_adapter.__file__),
        ]
        imported_modules = []
        for path in sources:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_modules.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_modules.append(node.module)
        self.assertNotIn("solver", imported_modules)
        self.assertNotIn("ui", imported_modules)
        self.assertNotIn("report", imported_modules)


if __name__ == "__main__":
    unittest.main()
