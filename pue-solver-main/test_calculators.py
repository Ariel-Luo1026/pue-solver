import ast
import unittest
from pathlib import Path
from unittest.mock import patch

import calculation_adapter
import calculators
from calculation_adapter import (
    get_calculation_context,
    get_calculator_for_project,
    run_project_via_adapter,
)
from calculators import get_calculator_for_context, list_calculators
from calculators.acc_calculator import ACCCalculator
from configuration_library_loader import build_solver_input_from_library
from library_solver_adapter import convert_library_input_to_solver_input
from solver import compute_pue_project


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

    def test_acc_calculator_run_delegates_to_legacy_solver_entry_point(self):
        sentinel = {"annual_results": {"annual_average_PUE": 1.23}}
        with patch("solver.compute_pue_project", return_value=sentinel) as mocked:
            result = ACCCalculator().run({"cooling_system_type": "ACC"})

        self.assertIs(result, sentinel)
        mocked.assert_called_once_with({"cooling_system_type": "ACC"})

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

    def test_run_project_via_adapter_routes_acc_to_acc_calculator(self):
        sentinel = {"annual_results": {"annual_average_PUE": 1.23}}
        with patch.object(ACCCalculator, "run", return_value=sentinel) as mocked:
            result = run_project_via_adapter({
                "cooling_system_type": "ACC",
                "power_source": "Grid",
                "cooling_unit_capacity_mw": 1,
            })

        self.assertIs(result, sentinel)
        mocked.assert_called_once()

    def test_run_project_via_adapter_raises_for_unsupported_placeholder(self):
        with self.assertRaisesRegex(
            NotImplementedError,
            "No calculator implemented for topology chiller_dry_cooler / solver mode placeholder",
        ):
            run_project_via_adapter({
                "cooling_system_type": "Chiller + Dry Cooler",
                "power_source": "Grid",
                "cooling_unit_capacity_mw": 2,
            })

    def test_adapter_acc_path_matches_direct_legacy_solver_results(self):
        sample = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        legacy_result = compute_pue_project(sample)
        adapter_result = run_project_via_adapter(sample)

        annual_keys = (
            "annual_average_PUE",
            "annual_IT_energy_kWh",
            "annual_facility_energy_kWh",
            "annual_cooling_energy_kWh",
        )
        for key in annual_keys:
            self.assertEqual(
                adapter_result["annual_results"][key],
                legacy_result["annual_results"][key],
            )
        peak_key = "peak_total_facility_power_kW"
        if peak_key in legacy_result.get("peak_results", {}):
            self.assertEqual(
                adapter_result["peak_results"][peak_key],
                legacy_result["peak_results"][peak_key],
            )

    def test_list_calculators_contains_acc_calculator(self):
        calculator_ids = [calculator.calculator_id for calculator in list_calculators()]
        self.assertIn("acc_calculator", calculator_ids)

    def test_adapter_and_calculator_registry_do_not_import_solver_at_module_import_time(self):
        modules = [calculation_adapter, calculators]
        calculator_dir = Path(calculators.__file__).resolve().parent
        sources = [
            Path(module.__file__).read_text(encoding="utf-8")
            for module in modules
        ] + [
            (calculator_dir / "base_calculator.py").read_text(encoding="utf-8"),
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

    def test_acc_calculator_imports_solver_only_inside_run(self):
        acc_source = Path(calculators.__file__).resolve().parent / "acc_calculator.py"
        tree = ast.parse(acc_source.read_text(encoding="utf-8"))
        module_level_imports = []
        run_imports = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                module_level_imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                module_level_imports.append(node.module)
            elif isinstance(node, ast.ClassDef) and node.name == "ACCCalculator":
                for class_node in node.body:
                    if isinstance(class_node, ast.FunctionDef) and class_node.name == "run":
                        for run_node in ast.walk(class_node):
                            if isinstance(run_node, ast.Import):
                                run_imports.extend(alias.name for alias in run_node.names)
                            elif isinstance(run_node, ast.ImportFrom) and run_node.module:
                                run_imports.append(run_node.module)
        self.assertNotIn("solver", module_level_imports)
        self.assertIn("solver", run_imports)


if __name__ == "__main__":
    unittest.main()
