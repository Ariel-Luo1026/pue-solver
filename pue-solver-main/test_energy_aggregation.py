import unittest
from copy import deepcopy

from configuration_library_loader import build_solver_input_from_library
from energy_aggregation import AnnualEnergyAggregationError, aggregate_annual_energy
from library_solver_adapter import _build_acc_gas_engine_cdu_solver_input
from solver import compute_pue_project
from topology_dispatcher import dispatch_topology


class EnergyAggregationTest(unittest.TestCase):
    def test_acc_annual_aggregation_matches_existing_pue(self):
        library_input = build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        solver_input = _build_acc_gas_engine_cdu_solver_input(deepcopy(library_input))
        existing = compute_pue_project(solver_input)

        aggregated = aggregate_annual_energy(existing)

        self.assertLess(abs(aggregated["PUE"] - existing["annual_results"]["annual_average_PUE"]), 1e-9)
        self.assertIn("ACC", aggregated["components"])
        self.assertIn("CHW_PUMP", aggregated["components"])

    def test_chiller_dry_cooler_aggregation(self):
        library_input = build_solver_input_from_library("CHILLER_DRYCOOLER_2MW_GRID", 2.0, "Normal")
        result = dispatch_topology(library_input["configuration_manifest"], library_input)

        aggregated = result["standard_annual_energy"]
        annual = result["annual_results"]

        self.assertAlmostEqual(
            aggregated["components"]["CHILLER"]["energy_kWh"],
            annual["annual_chiller_energy_kWh"],
        )
        self.assertAlmostEqual(
            aggregated["components"]["DRY_COOLER"]["energy_kWh"],
            annual["annual_dry_cooler_energy_kWh"],
        )
        self.assertAlmostEqual(
            aggregated["components"]["CHW_PUMP"]["energy_kWh"],
            annual["annual_pump_energy_kWh"],
        )
        self.assertAlmostEqual(aggregated["PUE"], annual["annual_average_PUE"])

    def test_unknown_equipment_type_warns_without_crashing(self):
        aggregated = aggregate_annual_energy({
            "hourly_results": [
                {
                    "it_load_kW": 100,
                    "facility_power_kW": 110,
                    "mystery_performance_result": {
                        "equipment_id": "MYSTERY_1",
                        "equipment_type": "MYSTERY",
                        "performance": {"power_kW": 10},
                    },
                }
            ]
        })

        self.assertEqual(aggregated["components"]["MYSTERY"]["energy_kWh"], 10)
        self.assertTrue(aggregated["warnings"])
        self.assertAlmostEqual(aggregated["PUE"], 1.1)

    def test_empty_performance_result_fails_clearly(self):
        with self.assertRaisesRegex(AnnualEnergyAggregationError, "hourly_results is empty"):
            aggregate_annual_energy({"hourly_results": []})

        with self.assertRaisesRegex(AnnualEnergyAggregationError, "no PerformanceResult or supported legacy power fields"):
            aggregate_annual_energy({"hourly_results": [{"it_load_kW": 100, "facility_power_kW": 100}]})


if __name__ == "__main__":
    unittest.main()
