import unittest
from copy import deepcopy

from configuration_library_loader import build_solver_input_from_library
from energy_aggregation import aggregate_annual_energy
from equipment_performance.acc_adapter import performance_result_from_legacy_acc_row
from solver import compute_pue_project
from topology_adapters.acc_gas_engine_cdu import build_acc_solver_input_from_configuration
from topology_dispatcher import dispatch_topology


class AccPerformanceResultMigrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library_input = build_solver_input_from_library(
            "ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal"
        )
        cls.manifest = cls.library_input["configuration_manifest"]
        cls.dispatched = dispatch_topology(cls.manifest, deepcopy(cls.library_input))
        legacy_input = build_acc_solver_input_from_configuration(
            cls.manifest,
            deepcopy(cls.library_input),
        )
        cls.legacy = compute_pue_project(legacy_input)

    def test_acc_performance_result_schema_from_legacy_row(self):
        legacy_row = self.legacy["hourly_results"][0]
        result = performance_result_from_legacy_acc_row(
            legacy_row,
            equipment_id="ACC_2",
        ).to_dict()

        self.assertEqual(result["equipment_id"], "ACC_2")
        self.assertEqual(result["equipment_type"], "ACC")
        self.assertEqual(
            result["input_conditions"]["ambient_C"],
            legacy_row["acc_ambient_C"],
        )
        self.assertEqual(
            result["input_conditions"]["required_capacity_kW"],
            legacy_row["acc_required_capacity_per_unit_kW"],
        )
        self.assertEqual(result["performance"]["power_kW"], legacy_row["acc_power_kW"])
        self.assertEqual(result["performance"]["COP"], legacy_row["acc_cop"])
        self.assertEqual(result["performance"]["load_ratio"], legacy_row["acc_load_ratio"])
        self.assertEqual(
            result["performance"]["capacity_ratio"],
            legacy_row["acc_diagnostic_load_ratio"],
        )
        self.assertEqual(
            result["diagnostics"]["clamped_status"],
            legacy_row["acc_capacity_clamped"],
        )

    def test_acc_hourly_output_contains_standardized_result(self):
        row = self.dispatched["hourly_results"][0]
        performance_result = row["acc_performance_result"]

        self.assertEqual(performance_result["equipment_id"], "ACC_2")
        self.assertEqual(performance_result["equipment_type"], "ACC")
        self.assertEqual(performance_result["performance"]["power_kW"], row["acc_power_kW"])
        self.assertEqual(performance_result["performance"]["COP"], row["acc_cop"])
        self.assertEqual(performance_result["performance"]["load_ratio"], row["acc_load_ratio"])
        self.assertEqual(
            performance_result["diagnostics"]["source"],
            "existing_acc_solver_output",
        )
        self.assertIn("standard_annual_energy", self.dispatched)

    def test_energy_aggregation_using_performance_result_equals_legacy(self):
        migrated = aggregate_annual_energy(self.dispatched)
        legacy = aggregate_annual_energy(self.legacy)

        self.assertAlmostEqual(
            migrated["components"]["ACC"]["energy_kWh"],
            legacy["components"]["ACC"]["energy_kWh"],
            places=9,
        )
        self.assertAlmostEqual(migrated["PUE"], legacy["PUE"], places=12)
        self.assertEqual(
            migrated["components"]["ACC"]["sources"],
            ["PerformanceResult"],
        )

    def test_annual_pue_unchanged_after_acc_performance_result_migration(self):
        self.assertLess(
            abs(
                self.dispatched["annual_results"]["annual_average_PUE"]
                - self.legacy["annual_results"]["annual_average_PUE"]
            ),
            1e-9,
        )
        self.assertLess(
            abs(
                self.dispatched["standard_annual_energy"]["PUE"]
                - self.dispatched["annual_results"]["annual_average_PUE"]
            ),
            1e-9,
        )


if __name__ == "__main__":
    unittest.main()
