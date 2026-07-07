import ast
import copy
import unittest
from pathlib import Path

from unit_quantity import (
    UnitQuantityConfig,
    build_unit_quantity_for_equipment,
    calculate_auto_units,
    resolve_unit_quantity,
)


class UnitQuantityTest(unittest.TestCase):
    def test_auto_mode_ceil_calculation(self):
        self.assertEqual(calculate_auto_units(12000, 1500), 8)

        resolved = resolve_unit_quantity(
            UnitQuantityConfig(
                equipment_id="acc_unit",
                quantity_mode="auto",
                design_load_kw=12000,
                auto_unit_capacity_kw=1500,
            )
        )

        self.assertEqual(resolved.auto_calculated_units, 8)
        self.assertEqual(resolved.effective_installed_units, 8)
        self.assertEqual(resolved.effective_running_units, 8)
        self.assertEqual(resolved.effective_standby_units, 0)
        self.assertEqual(resolved.redundancy_mode, "N")

    def test_manual_mode_n_plus_two(self):
        resolved = resolve_unit_quantity(
            UnitQuantityConfig(
                equipment_id="gas_engine",
                quantity_mode="manual",
                manual_installed_units=10,
                manual_running_units=8,
                manual_standby_units=2,
            )
        )

        self.assertEqual(resolved.effective_installed_units, 10)
        self.assertEqual(resolved.effective_running_units, 8)
        self.assertEqual(resolved.effective_standby_units, 2)
        self.assertEqual(resolved.redundancy_mode, "N+2")

    def test_manual_running_defaults_to_installed(self):
        resolved = resolve_unit_quantity(
            UnitQuantityConfig(
                equipment_id="cdu",
                quantity_mode="manual",
                manual_installed_units=5,
            )
        )

        self.assertEqual(resolved.effective_running_units, 5)
        self.assertEqual(resolved.effective_standby_units, 0)
        self.assertEqual(resolved.redundancy_mode, "N")
        self.assertTrue(any("running units not provided" in note for note in resolved.notes))

    def test_standby_is_inferred_from_installed_minus_running(self):
        resolved = resolve_unit_quantity(
            UnitQuantityConfig(
                equipment_id="rtc",
                quantity_mode="manual",
                manual_installed_units=9,
                manual_running_units=8,
            )
        )

        self.assertEqual(resolved.effective_standby_units, 1)
        self.assertEqual(resolved.redundancy_mode, "N+1")

    def test_invalid_or_missing_inputs_produce_safe_notes(self):
        self.assertEqual(calculate_auto_units(None, 1500), 0)
        self.assertEqual(calculate_auto_units(12000, 0), 0)

        auto = resolve_unit_quantity(
            UnitQuantityConfig(
                equipment_id="acc_unit",
                quantity_mode="auto",
                design_load_kw=None,
                auto_unit_capacity_kw=1500,
            )
        )
        self.assertEqual(auto.effective_installed_units, 0)
        self.assertTrue(auto.notes)

        manual = resolve_unit_quantity(
            UnitQuantityConfig(
                equipment_id="acc_unit",
                quantity_mode="manual",
                manual_installed_units=-1,
                manual_running_units=3,
            )
        )
        self.assertEqual(manual.effective_installed_units, 0)
        self.assertEqual(manual.redundancy_mode, "custom")
        self.assertTrue(manual.notes)

    def test_canonical_alias_is_resolved(self):
        resolved = resolve_unit_quantity(
            UnitQuantityConfig(
                equipment_id="auxiliary_load",
                quantity_mode="auto",
                design_load_kw=100,
                auto_unit_capacity_kw=50,
            )
        )

        self.assertEqual(resolved.equipment_id, "rtc")
        self.assertEqual(resolved.effective_installed_units, 2)

    def test_build_unit_quantity_reads_project_input_override(self):
        project_input = {
            "equipment_quantity_overrides": {
                "auxiliary_load": {
                    "quantity_mode": "manual",
                    "manual_installed_units": 10,
                    "manual_running_units": 8,
                    "manual_standby_units": 2,
                }
            }
        }
        original = copy.deepcopy(project_input)

        resolved = build_unit_quantity_for_equipment(
            "rtc",
            project_input,
            unit_capacity_kw=50,
            design_load_kw=100,
        )

        self.assertEqual(resolved.equipment_id, "rtc")
        self.assertEqual(resolved.quantity_mode, "manual")
        self.assertEqual(resolved.effective_installed_units, 10)
        self.assertEqual(resolved.effective_running_units, 8)
        self.assertEqual(resolved.effective_standby_units, 2)
        self.assertEqual(resolved.redundancy_mode, "N+2")
        self.assertEqual(project_input, original)

    def test_no_override_defaults_to_auto_mode(self):
        resolved = build_unit_quantity_for_equipment(
            "mau",
            {},
            unit_capacity_kw=25,
            design_load_kw=70,
        )

        self.assertEqual(resolved.quantity_mode, "auto")
        self.assertEqual(resolved.equipment_id, "mau")
        self.assertEqual(resolved.effective_installed_units, 3)

    def test_module_does_not_import_solver_ui_or_report_dependencies(self):
        source = Path(__file__).with_name("unit_quantity.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

        self.assertNotIn("solver", imported_modules)
        self.assertNotIn("ui", imported_modules)
        self.assertNotIn("acc_excel_benchmark", imported_modules)


if __name__ == "__main__":
    unittest.main()
