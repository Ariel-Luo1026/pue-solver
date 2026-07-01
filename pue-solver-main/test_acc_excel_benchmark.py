import unittest

from acc_excel_benchmark import compute_acc_excel_benchmark
from configuration_library_loader import build_solver_input_from_library
from library_solver_adapter import convert_library_input_to_solver_input
from solver import compute_pue_project


class AccExcelBenchmarkTest(unittest.TestCase):
    def _input(self, scenario):
        return convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, scenario)
        )

    def test_normal_matches_excel(self):
        output = compute_acc_excel_benchmark(self._input("Normal"))
        self.assertAlmostEqual(output["annual_results"]["annual_average_PUE"], 1.23299755, places=8)
        self.assertEqual(output["annual_results"]["calculation_mode"], "excel_benchmark_compatible")

    def test_failure_matches_excel(self):
        output = compute_acc_excel_benchmark(self._input("Failure"))
        self.assertAlmostEqual(output["annual_results"]["annual_average_PUE"], 1.22622588, places=8)

    def test_auditable_components_and_annual_schema(self):
        output = compute_acc_excel_benchmark(self._input("Normal"))
        annual = output["annual_results"]
        for key in (
            "annual_IT_energy_kWh", "annual_facility_energy_kWh", "annual_acc_energy_kWh",
            "annual_pump_energy_kWh", "annual_indoor_equipment_energy_kWh",
            "annual_engine_radiator_energy_kWh", "annual_it_electrical_loss_kWh",
            "annual_mep_electrical_loss_kWh", "annual_total_cooling_system_energy_kWh",
        ):
            self.assertGreater(annual[key], 0)
        self.assertEqual(len(output["hourly_results"]), 8760)

    def test_dynamic_acc_mode_remains_available(self):
        dynamic = compute_pue_project(self._input("Normal"))
        self.assertNotIn("error", dynamic)
        self.assertNotEqual(dynamic["annual_results"].get("calculation_mode"), "excel_benchmark_compatible")
        self.assertGreater(dynamic["annual_results"]["annual_acc_energy_kWh"], 0)


if __name__ == "__main__":
    unittest.main()
