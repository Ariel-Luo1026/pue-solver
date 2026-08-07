import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from configuration_library_loader import (
    _resolve_actual_equipment_folder,
    calculate_installed_units,
    calculate_required_units,
    calculate_running_units,
    calculate_unit_requirements,
    build_solver_input_from_library,
    discover_configuration_library,
    load_configuration_library,
    load_equipment_packages,
    load_equipment_aliases,
    resolve_equipment_alias,
    select_solver_curve,
)
from test_acc_v2_curve_reader import _write_xlsx
from tools.validate_configuration_library import validate_configuration_library


class ConfigurationLibraryLoaderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loaded = load_configuration_library("ACC_1.5MW_GASENGINE_CDU")

    def test_configuration_workbook(self):
        self.assertEqual(self.loaded["configuration_name"], "ACC_1.5MW_GASENGINE_CDU")
        self.assertEqual(self.loaded["configuration_id"], "ACC_1.5MW_GASENGINE_CDU")
        self.assertEqual(self.loaded["topology_id"], "acc_gas_engine_cdu")
        self.assertEqual(self.loaded["implementation_status"], "implemented")
        self.assertEqual(self.loaded["cooling_system_type"], "ACC")
        self.assertEqual(self.loaded["cooling_unit_capacity_mw"], 1.5)
        self.assertEqual(self.loaded["power_source"], "Gas Engine")
        self.assertTrue(self.loaded["equipment_per_cooling_unit"])

    def test_discovery_uses_configuration_manifests(self):
        discovered = discover_configuration_library()
        by_id = {item["configuration_id"]: item for item in discovered}
        self.assertIn("ACC_1.5MW_GASENGINE_CDU", by_id)
        self.assertEqual(by_id["ACC_1.5MW_GASENGINE_CDU"]["implementation_status"], "implemented")
        self.assertEqual(by_id["ACC_1.5MW_GASENGINE_CDU"]["solver_topology"], "acc_gas_engine_cdu")

    def test_scenario_workbook_and_dynamic_unit_rules(self):
        scenarios = {item["scenario"]: item for item in self.loaded["scenarios"]}
        self.assertEqual(scenarios["Normal"]["running_unit_formula"], "installed_units")
        self.assertEqual(scenarios["Failure"]["running_unit_formula"], "installed_units - 1")
        required = calculate_required_units(6.0, self.loaded["cooling_unit_capacity_mw"])
        installed = calculate_installed_units(6.0, self.loaded["cooling_unit_capacity_mw"])
        self.assertEqual(required, 4)
        self.assertEqual(installed, 5)
        self.assertEqual(calculate_running_units(installed, scenarios["Normal"]["running_unit_formula"]), 5)
        self.assertEqual(calculate_running_units(installed, scenarios["Failure"]["running_unit_formula"]), 4)

    def test_corrected_n_plus_one_example(self):
        sizing = calculate_unit_requirements(4.4, 1.5)
        self.assertEqual(sizing["required_units"], 3)
        self.assertEqual(sizing["installed_units"], 4)
        self.assertEqual(sizing["normal_active_units"], 4)
        self.assertEqual(sizing["failure_active_units"], 3)
        self.assertEqual(sizing["indoor_active_units"], 4)
        self.assertEqual(sizing["redundancy"], "N+1")

    def test_it_load_profile_has_8760_hours(self):
        profile = self.loaded["it_load"]
        self.assertEqual(profile["hours"], 8760)
        self.assertEqual(len(profile["hourly_it_load_percent"]), 8760)
        self.assertEqual(len(profile["hourly_it_load_%"]), 8760)
        self.assertTrue(all(value == 90 for value in profile["hourly_it_load_percent"]))

    def test_expected_equipment_packages_and_solver_curves(self):
        expected = {
            "ACC_2", "CHW_PUMP_2", "ENGINE_2", "ENGINE_RADIATOR_2",
            "CDU_2", "RTC_2", "MAU_2", "ELECTRICAL_DISTRIBUTION_2",
        }
        self.assertEqual(set(self.loaded["equipment"]), expected)
        self.assertEqual(len(self.loaded["equipment_per_cooling_unit"]), 8)
        self.assertTrue(all(item["status"] in {"Found", "Electrical Path Found"} for item in self.loaded["equipment"].values()))
        self.assertIn("Solver_Curve", self.loaded["equipment"]["ACC_2"]["solver_curves"])
        self.assertIn("Solver_Curve", self.loaded["equipment"]["CHW_PUMP_2"]["solver_curves"])
        self.assertIn("Solver_Curve_Failure", self.loaded["equipment"]["ENGINE_2"]["solver_curves"])

    def test_shared_equipment_alias_json_loads_required_mappings(self):
        aliases = load_equipment_aliases()
        expected = {
            "RTC_1": "RTC_1&2",
            "RTC_2": "RTC_1&2",
            "MAU_1": "MAU_1&2",
            "MAU_2": "MAU_1&2",
            "ENGINE_2": "ENGINE_3",
            "ENGINE_RADIATOR_2": "ENGINE_RADIATOR_1",
        }
        for raw, resolved in expected.items():
            self.assertEqual(aliases[raw], resolved)
            self.assertEqual(resolve_equipment_alias(raw, aliases), resolved)

    def test_alias_resolution_prefers_shared_alias_workbook(self):
        with TemporaryDirectory() as temp_dir:
            equipment_root = Path(temp_dir) / "equipment"
            canonical = equipment_root / "RTC_1&2"
            canonical.mkdir(parents=True)
            _write_xlsx(canonical / "RTC_1&2.xlsx", {"Solver_Curve": [["load_ratio", "power_kW"], [0.5, 12]]})

            self.assertEqual(_resolve_actual_equipment_folder(equipment_root, "RTC_1"), "RTC_1&2")
            self.assertEqual(_resolve_actual_equipment_folder(equipment_root, "RTC_2"), "RTC_1&2")

    def test_configuration_library_diagnostic_resolves_aliased_workbooks(self):
        results = validate_configuration_library()
        errors = [item for item in results if item["status"] != "ok"]
        self.assertEqual(errors, [])
        by_equipment = {(item["configuration"], item["equipment_id"]): item for item in results}
        self.assertEqual(by_equipment[("ACC_1.5MW_GASENGINE_CDU", "RTC_2")]["resolved_id"], "RTC_1&2")
        self.assertEqual(by_equipment[("ACC_1.5MW_GASENGINE_CDU", "MAU_2")]["resolved_id"], "MAU_1&2")
        self.assertEqual(by_equipment[("ACC_1.5MW_GASENGINE_CDU", "ENGINE_2")]["resolved_id"], "ENGINE_3")
        self.assertEqual(
            by_equipment[("ACC_1.5MW_GASENGINE_CDU", "ENGINE_RADIATOR_2")]["resolved_id"],
            "ENGINE_RADIATOR_1",
        )

    def test_normal_and_failure_curve_selection_with_fallback(self):
        equipment = self.loaded["equipment"]
        self.assertEqual(select_solver_curve(equipment["CHW_PUMP_2"], "Normal")["sheet_name"], "Solver_Curve")
        self.assertEqual(select_solver_curve(equipment["CHW_PUMP_2"], "Failure")["sheet_name"], "Solver_Curve")
        self.assertEqual(select_solver_curve(equipment["ACC_2"], "Normal")["sheet_name"], "Solver_Curve")
        self.assertEqual(select_solver_curve(equipment["CDU_2"], "Failure")["sheet_name"], "Solver_Curve")
        self.assertEqual(select_solver_curve(equipment["ELECTRICAL_DISTRIBUTION_2"], "Normal")["status"], "Electrical Path Found")

    def test_acc_performance_map_is_final_fallback(self):
        package = {
            "equipment_id": "ACC_TEST",
            "solver_curves": {},
            "performance_map": [{"percent_load": 100, "power_input_kW": 400}],
        }
        selected = select_solver_curve(package, "Normal")
        self.assertEqual(selected["sheet_name"], "Performance_Map")
        self.assertEqual(selected["status"], "Selected")

    def test_electrical_distribution_solver_efficiencies(self):
        electrical = self.loaded["equipment"]["ELECTRICAL_DISTRIBUTION_2"]
        self.assertEqual(electrical["status"], "Electrical Path Found")
        self.assertAlmostEqual(electrical["electrical_path"]["it_efficiency"], 0.9723)
        self.assertAlmostEqual(electrical["electrical_path"]["mep_efficiency"], 0.9959)
        selected = select_solver_curve(electrical, "Failure")
        self.assertEqual(selected["sheet_name"], "Solver")
        self.assertEqual(selected["status"], "Electrical Path Found")

    def test_other_seven_equipment_curve_logic_is_unchanged(self):
        equipment = self.loaded["equipment"]
        expected = {
            "ACC_2": ("Solver_Curve", "Solver_Curve"),
            "CHW_PUMP_2": ("Solver_Curve", "Solver_Curve"),
            "ENGINE_2": ("Solver_Curve_Normal", "Solver_Curve_Failure"),
            "ENGINE_RADIATOR_2": ("Solver_Curve_Normal", "Solver_Curve_Failure"),
            "CDU_2": ("Solver_Curve", "Solver_Curve"),
            "RTC_2": ("Solver_Curve", "Solver_Curve"),
            "MAU_2": ("Solver_Curve", "Solver_Curve"),
        }
        for equipment_id, (normal_sheet, failure_sheet) in expected.items():
            self.assertEqual(select_solver_curve(equipment[equipment_id], "Normal")["sheet_name"], normal_sheet)
            self.assertEqual(select_solver_curve(equipment[equipment_id], "Failure")["sheet_name"], failure_sheet)

    def test_library_bound_input_contains_scenario_bindings(self):
        bound = self.loaded["library_bound_input"]
        self.assertEqual(set(bound), {
            "configuration", "unit_counts", "scenarios", "equipment_packages",
            "selected_curves", "it_load_profile",
        })
        self.assertEqual(bound["selected_curves"]["Normal"]["ENGINE_2"]["sheet_name"], "Solver_Curve_Normal")
        self.assertEqual(bound["selected_curves"]["Failure"]["ENGINE_2"]["sheet_name"], "Solver_Curve_Failure")

    def test_missing_equipment_package_is_marked_without_crashing(self):
        with TemporaryDirectory() as temp_dir:
            packages = load_equipment_packages(
                Path(temp_dir), [{"equipment_id": "MISSING_TEST_1", "per_cooling_unit": 1}]
            )
        missing = packages["MISSING_TEST_1"]
        self.assertEqual(missing["status"], "Missing")
        self.assertEqual(select_solver_curve(missing, "Normal")["status"], "Missing Curve")

    def test_standardized_input_is_metadata_only(self):
        standardized = self.loaded["standardized_input"]
        self.assertEqual(standardized["cooling_system_type"], "ACC")
        self.assertEqual(standardized["project"]["it_load"]["hours"], 8760)
        self.assertIn("equipment_packages", standardized["configuration_library"])

    def test_phase8_normal_standardized_solver_input(self):
        solver_input = build_solver_input_from_library(
            "ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal"
        )
        project = solver_input["project"]
        self.assertEqual(project["design_it_load_kW"], 4400)
        self.assertEqual(project["cooling_unit_capacity_kW"], 1500)
        self.assertEqual(project["required_units"], 3)
        self.assertEqual(project["installed_units"], 4)
        self.assertEqual(project["active_units"], 4)
        self.assertEqual(project["indoor_active_units"], 4)
        self.assertEqual(project["redundancy_strategy"], "N+1")
        self.assertEqual(project["scenario_name"], "Normal")
        self.assertEqual(len(project["it_load"]["hourly_it_load_kW"]), 8760)
        self.assertAlmostEqual(project["it_load"]["hourly_it_load_kW"][0], 3960)
        self.assertAlmostEqual(solver_input["electrical_path"]["it_efficiency"], 0.9723)
        self.assertAlmostEqual(solver_input["electrical_path"]["mep_efficiency"], 0.9959)
        self.assertEqual(solver_input["selected_curves"]["CHW_PUMP_2"]["sheet_name"], "Solver_Curve")
        self.assertEqual(solver_input["selected_curves"]["CDU_2"]["sheet_name"], "Solver_Curve")
        self.assertEqual(solver_input["configuration_id"], "ACC_1.5MW_GASENGINE_CDU")
        self.assertEqual(solver_input["topology_id"], "acc_gas_engine_cdu")
        self.assertEqual(solver_input["implementation_status"], "implemented")
        self.assertEqual(solver_input["report_profile"], "acc_gas_engine_cdu")
        self.assertEqual(solver_input["cooling_system_type"], "ACC")

    def test_phase8_failure_standardized_solver_input(self):
        solver_input = build_solver_input_from_library(
            "ACC_1.5MW_GASENGINE_CDU", 4.4, "Failure"
        )
        project = solver_input["project"]
        self.assertEqual(project["required_units"], 3)
        self.assertEqual(project["installed_units"], 4)
        self.assertEqual(project["active_units"], 3)
        self.assertEqual(project["indoor_active_units"], 4)
        self.assertEqual(project["scenario_name"], "Failure")
        self.assertEqual(solver_input["selected_curves"]["ENGINE_2"]["sheet_name"], "Solver_Curve_Failure")


if __name__ == "__main__":
    unittest.main()
