import ast
import unittest
from pathlib import Path

import calculation_adapter
import calculators
from calculation_adapter import get_calculation_context, get_calculator_for_project
from calculators import get_calculator_for_context, list_calculators
from calculators.acc_calculator import ACCCalculator


class CalculatorSkeletonTest(unittest.TestCase):
    def test_acc_context_resolves_to_acc_calculator(self):
        context = get_calculation_context({
            "cooling_system_type": "ACC",
            "power_source": "Gas Engine",
            "cooling_unit_capacity_mw": 1.5,
        })
        context["solver_mode"] = "acc_hourly"

        calculator = get_calculator_for_context(context)

        self.assertIsInstance(calculator, ACCCalculator)
        self.assertEqual(calculator.calculator_id, "acc_calculator")

    def test_acc_calculator_can_handle_acc_hourly_context(self):
        calculator = ACCCalculator()
        self.assertTrue(calculator.can_handle({
            "topology": {"topology_id": "acc"},
            "solver_mode": "acc_hourly",
        }))

    def test_abs_context_returns_no_calculator(self):
        context = get_calculation_context({
            "cooling_system_type": "ABS + Cooling Tower",
            "power_source": "Gas Engine",
            "cooling_unit_capacity_mw": 1,
        })
        context["solver_mode"] = "placeholder"

        self.assertIsNone(get_calculator_for_context(context))

    def test_acc_calculator_run_is_not_implemented_in_phase_9(self):
        with self.assertRaisesRegex(
            NotImplementedError,
            "ACC calculation is still handled by legacy solver.py in this phase.",
        ):
            ACCCalculator().run({"cooling_system_type": "ACC"})

    def test_calculation_adapter_returns_calculator_metadata_only(self):
        metadata = get_calculator_for_project({
            "cooling_system_type": "ACC",
            "power_source": "Grid",
            "cooling_unit_capacity_mw": 1,
        })

        self.assertEqual(metadata["calculator_id"], "acc_calculator")
        self.assertEqual(metadata["display_name"], "ACC Calculator")
        self.assertEqual(metadata["supported_topology_ids"], ["acc"])
        self.assertEqual(metadata["supported_solver_modes"], ["acc_hourly"])

    def test_placeholder_project_returns_no_calculator_metadata(self):
        metadata = get_calculator_for_project({
            "cooling_system_type": "Chiller + Dry Cooler",
            "power_source": "Grid",
            "cooling_unit_capacity_mw": 2,
        })

        self.assertIsNone(metadata)

    def test_list_calculators_contains_acc_calculator(self):
        calculator_ids = [calculator.calculator_id for calculator in list_calculators()]
        self.assertIn("acc_calculator", calculator_ids)

    def test_adapter_and_calculators_do_not_import_solver(self):
        modules = [calculation_adapter, calculators]
        calculator_dir = Path(calculators.__file__).resolve().parent
        sources = [
            Path(module.__file__).read_text(encoding="utf-8")
            for module in modules
        ] + [
            (calculator_dir / "base_calculator.py").read_text(encoding="utf-8"),
            (calculator_dir / "acc_calculator.py").read_text(encoding="utf-8"),
        ]
        imported_modules = []
        for source in sources:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_modules.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_modules.append(node.module)
        self.assertNotIn("solver", imported_modules)


if __name__ == "__main__":
    unittest.main()
