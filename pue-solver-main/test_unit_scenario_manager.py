import ast
import unittest
from pathlib import Path

from unit_scenario_manager import (
    calculate_active_units,
    calculate_required_units,
    calculate_unit_requirements,
    resolve_unit_scenario,
)


class UnitScenarioManagerTest(unittest.TestCase):
    def test_n_plus_one_sizing_unchanged_for_acc_example(self):
        sizing = calculate_unit_requirements(4.4, 1.5)

        self.assertEqual(sizing["required_units"], 3)
        self.assertEqual(sizing["installed_units"], 4)
        self.assertEqual(sizing["normal_active_units"], 4)
        self.assertEqual(sizing["failure_active_units"], 3)
        self.assertEqual(sizing["indoor_active_units"], 4)
        self.assertEqual(sizing["redundancy"], "N+1")

    def test_acc_normal_active_units_unchanged(self):
        resolved = resolve_unit_scenario(
            4.4,
            1.5,
            scenario_name="Normal",
            scenario_formula="installed_units",
        )

        self.assertEqual(resolved["required_units"], 3)
        self.assertEqual(resolved["installed_units"], 4)
        self.assertEqual(resolved["active_units"], 4)
        self.assertEqual(resolved["standby_units"], 0)
        self.assertEqual(resolved["failed_units"], 0)

    def test_acc_failure_active_units_unchanged(self):
        resolved = resolve_unit_scenario(
            4.4,
            1.5,
            scenario_name="Failure",
            scenario_formula="installed_units - 1",
        )

        self.assertEqual(resolved["required_units"], 3)
        self.assertEqual(resolved["installed_units"], 4)
        self.assertEqual(resolved["active_units"], 3)
        self.assertEqual(resolved["standby_units"], 1)
        self.assertEqual(resolved["failed_units"], 1)

    def test_supported_scenario_formulas(self):
        self.assertEqual(calculate_active_units(3, 4, "installed_units"), 4)
        self.assertEqual(calculate_active_units(3, 4, "installed_units - 1"), 3)
        self.assertEqual(calculate_active_units(3, 4, "required_units"), 3)
        with self.assertRaisesRegex(ValueError, "Unsupported unit scenario formula"):
            calculate_active_units(3, 4, "installed_units / 2")

    def test_role_specific_unit_counts_are_supported(self):
        resolved = resolve_unit_scenario(
            4.4,
            1.5,
            scenario_name="Failure",
            scenario_formula="installed_units - 1",
            role_quantities={
                "pump_units": {"installed_units": 4, "active_units": 4},
                "indoor_units": {"installed_units": 6, "active_units": 6},
                "engine_units": {"installed_units": 4, "active_units": 3},
            },
        )
        roles = resolved["role_quantities"]

        self.assertEqual(roles["cooling_units"]["active_units"], 3)
        self.assertEqual(roles["chiller_units"]["active_units"], 3)
        self.assertEqual(roles["dry_cooler_units"]["active_units"], 3)
        self.assertEqual(roles["pump_units"]["active_units"], 4)
        self.assertEqual(roles["indoor_units"]["active_units"], 6)
        self.assertEqual(roles["engine_units"]["active_units"], 3)

    def test_required_units_rejects_invalid_inputs(self):
        with self.assertRaisesRegex(ValueError, "must be greater than 0"):
            calculate_required_units(0, 1.5)
        with self.assertRaisesRegex(ValueError, "must be greater than 0"):
            calculate_required_units(4.4, 0)

    def test_module_does_not_import_solver_or_runtime_dependencies(self):
        source = Path(__file__).with_name("unit_scenario_manager.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

        self.assertNotIn("solver", imported_modules)
        self.assertNotIn("acc_v2_engine", imported_modules)
        self.assertNotIn("topology_dispatcher", imported_modules)


if __name__ == "__main__":
    unittest.main()
