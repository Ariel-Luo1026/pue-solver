import ast
import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from calculators.acc_calculator import (
    ACCCalculator,
    ACCInputContext,
    build_acc_input_context,
)
from configuration_library_loader import build_solver_input_from_library
from library_solver_adapter import convert_library_input_to_solver_input
from solver import compute_pue_project


class ACCCalculatorInputContextTest(unittest.TestCase):
    def test_build_acc_input_context_returns_dataclass(self):
        context = build_acc_input_context({
            "cooling_system_type": "ACC",
            "power_source": "Gas Engine",
            "cooling_unit_capacity_mw": 1.5,
        })
        self.assertIsInstance(context, ACCInputContext)
        self.assertEqual(context.cooling_system_type, "ACC")
        self.assertEqual(context.power_source, "Gas Engine")

    def test_original_project_input_is_not_modified(self):
        project_input = {
            "project": {
                "name": "Immutable Test",
                "it_load": {"hourly_it_load_kW": [1, 2, 3]},
            },
            "weather": {"hourly_data": {"dry_bulb_C": [20, 21, 22]}},
        }
        before = copy.deepcopy(project_input)
        context = build_acc_input_context(project_input)
        context.raw_project_input["project"]["name"] = "Changed Copy"

        self.assertEqual(project_input, before)

    def test_unit_capacity_normalizes_mw_and_kw_inputs_to_kw(self):
        cases = [
            ({"cooling_unit_capacity_mw": 1.5}, 1500.0),
            ({"Cooling Unit Capacity": "1.5 MW"}, 1500.0),
            ({"Cooling Unit Capacity": "1.5MW"}, 1500.0),
            ({"equipment": {"cooling": {"cooling_unit_capacity_kW": 1500}}}, 1500.0),
            ({"Cooling Unit Capacity": "1500 kW"}, 1500.0),
        ]
        for project_input, expected in cases:
            with self.subTest(project_input=project_input):
                self.assertEqual(build_acc_input_context(project_input).unit_capacity_kw, expected)

    def test_hourly_it_load_profile_and_weather_hours_are_preserved(self):
        context = build_acc_input_context({
            "project": {
                "scenario_name": "Normal",
                "active_units": 4,
                "it_load": {
                    "design_it_load_kW": 4400,
                    "hourly_it_load_kW": [3960, 3970, 3980],
                    "cooling_unit_count": 4,
                },
            },
            "weather": {
                "hourly_data": {
                    "dry_bulb_C": [30, 31, 32],
                    "wet_bulb_C": [21, 22, 23],
                    "hour_index": [1, 2, 3],
                }
            },
        })

        self.assertEqual(context.hourly_it_load_kw, [3960.0, 3970.0, 3980.0])
        self.assertEqual(context.weather_hours, 3)
        self.assertEqual(context.design_it_load_kw, 4400.0)
        self.assertEqual(context.unit_count, 4)
        self.assertEqual(context.scenario, "Normal")
        self.assertEqual(context.active_engines, 4)

    def test_build_acc_input_context_does_not_import_or_call_solver(self):
        acc_source = Path(__file__).resolve().parent / "calculators" / "acc_calculator.py"
        tree = ast.parse(acc_source.read_text(encoding="utf-8"))
        module_imports = []
        non_run_solver_imports = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                module_imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                module_imports.append(node.module)
            elif isinstance(node, ast.FunctionDef) and node.name == "build_acc_input_context":
                for child in ast.walk(node):
                    if isinstance(child, ast.Import):
                        non_run_solver_imports.extend(alias.name for alias in child.names)
                    elif isinstance(child, ast.ImportFrom) and child.module:
                        non_run_solver_imports.append(child.module)
        self.assertNotIn("solver", module_imports)
        self.assertNotIn("solver", non_run_solver_imports)

    def test_acc_calculator_run_still_delegates_to_legacy_solver(self):
        sentinel = {"annual_results": {"annual_average_PUE": 1.23}}
        project_input = {"cooling_system_type": "ACC"}
        with patch("solver.compute_pue_project", return_value=sentinel) as mocked:
            result = ACCCalculator().run(project_input)
        self.assertIs(result, sentinel)
        mocked.assert_called_once_with(project_input)

    def test_acc_calculator_run_matches_direct_legacy_solver_result(self):
        sample = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        legacy_result = compute_pue_project(sample)
        calculator_result = ACCCalculator().run(sample)

        for key in (
            "annual_average_PUE",
            "annual_IT_energy_kWh",
            "annual_facility_energy_kWh",
            "annual_cooling_energy_kWh",
        ):
            self.assertEqual(
                calculator_result["annual_results"][key],
                legacy_result["annual_results"][key],
            )


if __name__ == "__main__":
    unittest.main()
