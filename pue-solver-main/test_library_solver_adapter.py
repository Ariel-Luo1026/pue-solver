import unittest

from configuration_library_loader import build_solver_input_from_library
from library_solver_adapter import convert_library_input_to_solver_input
from solver import compute_pue_project


class LibrarySolverAdapterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.normal_library = build_solver_input_from_library(
            "ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal"
        )
        cls.failure_library = build_solver_input_from_library(
            "ACC_1.5MW_GASENGINE_CDU", 4.4, "Failure"
        )
        cls.normal = convert_library_input_to_solver_input(cls.normal_library)
        cls.failure = convert_library_input_to_solver_input(cls.failure_library)

    def test_normal_project_and_unit_mapping(self):
        project = self.normal["project"]
        self.assertEqual(project["it_load"]["hourly_it_load_kW"][0], 3960)
        self.assertEqual(project["required_units"], 3)
        self.assertEqual(project["installed_units"], 4)
        self.assertEqual(project["active_units"], 4)
        self.assertEqual(project["cooling_unit_count"], 4)
        self.assertEqual(project["it_load"]["cooling_unit_count"], 4)

    def test_failure_active_units(self):
        self.assertEqual(self.failure["project"]["required_units"], 3)
        self.assertEqual(self.failure["project"]["installed_units"], 4)
        self.assertEqual(self.failure["project"]["active_units"], 3)
        self.assertEqual(self.failure["equipment"]["cooling"]["cooling_unit_count"], 3)

    def test_curves_and_electrical_metadata_are_preserved(self):
        curves = self.normal["curve_library"]["curves"]
        self.assertIn("ACC_2_COP", curves)
        self.assertEqual(self.normal["acc_curve"]["equipment_id"], "ACC_2")
        self.assertEqual(self.normal["acc_curve"]["source_sheet"], "Solver_Curve")
        self.assertTrue(self.normal["acc_curve"]["data"])
        self.assertEqual(self.normal["engine_curve"]["equipment_id"], "ENGINE_2")
        self.assertEqual(self.normal["engine_curve"]["source_sheet"], "Solver_Curve_Normal")
        self.assertEqual(self.failure["engine_curve"]["source_sheet"], "Solver_Curve_Failure")
        self.assertTrue(self.normal["engine_curve"]["data"])
        self.assertEqual(self.normal["engine_radiator_curve"]["equipment_id"], "ENGINE_RADIATOR_2")
        self.assertEqual(self.normal["engine_radiator_curve"]["source_sheet"], "Solver_Curve_Normal")
        self.assertEqual(self.failure["engine_radiator_curve"]["source_sheet"], "Solver_Curve_Failure")
        self.assertIn("CHW_PUMP_2_power_vs_load", curves)
        self.assertEqual(
            self.failure["library_context"]["selected_curves"]["ENGINE_2"]["sheet_name"],
            "Solver_Curve_Failure",
        )
        self.assertAlmostEqual(self.normal["electrical_path"]["it_efficiency"], 0.9723)
        self.assertAlmostEqual(self.normal["electrical_path"]["mep_efficiency"], 0.9959)
        self.assertIn("engine_output_reference", self.normal["library_context"])
        self.assertIn("engine_radiator", self.normal["library_context"])
        self.assertEqual(set(self.normal["library_context"]["auxiliary_equipment"]), {"CDU_2", "RTC_2", "MAU_2"})
        self.assertEqual(set(self.normal["equipment"]["library_fixed_power"]), {"CDU_2", "RTC_2", "MAU_2"})

    def test_adapter_output_is_accepted_by_compute_pue_project(self):
        for adapted in (self.normal, self.failure):
            output = compute_pue_project(adapted)
            self.assertNotIn("error", output)
            self.assertEqual(len(output["hourly_results"]), 8760)
            self.assertIsInstance(output["annual_results"]["annual_average_PUE"], float)
            self.assertGreater(output["annual_results"]["annual_average_PUE"], 1.0)


if __name__ == "__main__":
    unittest.main()
