import ast
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import calculation_adapter
from calculation_adapter import (
    get_calculation_context,
    resolve_solver_mode,
    run_calculation_adapter,
)


class CalculationAdapterTest(unittest.TestCase):
    def _make_configuration(self, root, name, equipment_folders):
        configuration_path = Path(root) / name
        (configuration_path / "input").mkdir(parents=True)
        equipment_path = configuration_path / "equipment"
        equipment_path.mkdir()
        (configuration_path / "configuration.xlsx").touch()
        (configuration_path / "scenario.xlsx").touch()
        for folder in equipment_folders:
            (equipment_path / folder).mkdir()
        return configuration_path

    def test_acc_returns_acc_hourly_solver_mode(self):
        result = run_calculation_adapter({
            "cooling_system_type": "ACC",
            "power_source": "Gas Engine",
            "cooling_unit_capacity_mw": 1.5,
            "configuration_name": "ACC_1.5MW_GASENGINE_CDU",
        })

        self.assertEqual(result["solver_mode"], "acc_hourly")
        self.assertEqual(result["context"]["calculation_mode"], "acc_hourly")

    def test_abs_returns_placeholder_solver_mode(self):
        result = run_calculation_adapter({
            "cooling_system_type": "ABS + Cooling Tower",
            "power_source": "Gas Engine",
            "cooling_unit_capacity_mw": 1,
        })

        self.assertEqual(result["solver_mode"], "placeholder")

    def test_cooling_tower_returns_placeholder_solver_mode(self):
        context = get_calculation_context({
            "cooling_system_type": "Chiller + Cooling Tower",
            "power_source": "Grid",
            "cooling_unit_capacity_mw": 2,
        })

        self.assertEqual(resolve_solver_mode(context), "placeholder")

    def test_chiller_dry_cooler_returns_placeholder_solver_mode(self):
        result = run_calculation_adapter({
            "cooling_system_type": "Chiller + Dry Cooler",
            "power_source": "Grid",
            "cooling_unit_capacity_mw": 2,
        })

        self.assertEqual(result["solver_mode"], "placeholder")

    def test_context_returns_topology_equipment_and_performance_requirements(self):
        context = get_calculation_context({
            "cooling_system_type": "ACC",
            "power_source": "Gas Engine",
            "cooling_unit_capacity_mw": 1.5,
            "configuration_name": "ACC_1.5MW_GASENGINE_CDU",
        })

        self.assertEqual(context["topology"]["topology_id"], "acc")
        self.assertIn("acc_unit", {item["equipment_id"] for item in context["equipment"]})
        self.assertIn(
            "acc_performance_curve",
            {item["requirement_id"] for item in context["performance_requirements"]},
        )
        self.assertEqual(context["power_source"], "Gas Engine")
        self.assertEqual(context["cooling_system_type"], "ACC")
        self.assertEqual(context["unit_capacity"], 1.5)
        self.assertEqual(context["configuration_name"], "ACC_1.5MW_GASENGINE_CDU")

    def test_context_reads_configuration_summary_when_configuration_path_is_available(self):
        with TemporaryDirectory() as temp_dir:
            configuration_path = self._make_configuration(
                temp_dir,
                "ACC_1.5MW_GASENGINE_CDU",
                [
                    "ACC_2",
                    "CDU_2",
                    "CHW_PUMP_2",
                    "MAU_2",
                    "ELECTRICAL_DISTRIBUTION_2",
                    "RTC_2",
                    "ENGINE_2",
                ],
            )
            context = get_calculation_context({
                "cooling_system_type": "ACC",
                "power_source": "Gas Engine",
                "cooling_unit_capacity_mw": 1.5,
                "configuration_path": configuration_path,
            })

        self.assertIsNotNone(context["configuration_summary"])
        self.assertEqual(context["configuration_summary"]["topology_id"], "acc")
        self.assertEqual(context["configuration_summary"]["completeness_score"], 1.0)

    def test_adapter_accepts_nested_project_input_shape(self):
        context = get_calculation_context({
            "project": {
                "cooling_system_type": "ACC",
                "power_source": "Grid",
                "cooling_unit_capacity_kW": 1500,
                "name": "Nested Project",
            }
        })

        self.assertEqual(context["topology"]["topology_id"], "acc")
        self.assertEqual(context["power_source"], "Grid")
        self.assertEqual(context["unit_capacity"], 1500)
        self.assertEqual(context["configuration_name"], "Nested Project")

    def test_adapter_has_no_solver_dependency(self):
        adapter_source = Path(calculation_adapter.__file__).read_text(encoding="utf-8")
        tree = ast.parse(adapter_source)
        imported_modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.append(node.module)
        self.assertNotIn("solver", imported_modules)


if __name__ == "__main__":
    unittest.main()
