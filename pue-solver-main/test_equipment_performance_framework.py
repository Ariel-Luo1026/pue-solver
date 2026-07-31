import unittest
from pathlib import Path

from acc_v2_curve_lookup import lookup_acc_curve
from equipment_curve_reader import read_equipment_solver_curve
from equipment_metadata import load_equipment_metadata
from equipment_performance import (
    EquipmentPerformanceDispatchError,
    PerformanceResult,
    calculate_equipment_performance,
    dispatch_performance_adapter,
)
from configuration_library_loader import build_solver_input_from_library
from solver import compute_pue_project
from topology_adapters.acc_gas_engine_cdu import build_acc_solver_input_from_configuration
from topology_dispatcher import dispatch_topology


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ACC_CONFIG = PROJECT_ROOT / "Configuration Library" / "ACC_1.5MW_GASENGINE_CDU"
CHILLER_CONFIG = PROJECT_ROOT / "Configuration Library" / "CHILLER_DRYCOOLER_2MW_GRID"


class EquipmentPerformanceFrameworkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.acc_metadata = load_equipment_metadata(ACC_CONFIG / "equipment" / "ACC_2")
        cls.acc_curve = read_equipment_solver_curve(ACC_CONFIG, "ACC_2")
        cls.chiller_metadata = load_equipment_metadata(
            CHILLER_CONFIG / "equipment" / "CENTRIFUGALCHILLER_1"
        )
        cls.chiller_curve = read_equipment_solver_curve(CHILLER_CONFIG, "CENTRIFUGALCHILLER_1")
        cls.dry_cooler_metadata = load_equipment_metadata(CHILLER_CONFIG / "equipment" / "DRYCOOLER_6")
        cls.dry_cooler_curve = read_equipment_solver_curve(CHILLER_CONFIG, "DRYCOOLER_6")

    def test_acc_dispatch(self):
        adapter = dispatch_performance_adapter(self.acc_metadata, self.acc_curve)

        self.assertEqual(adapter.equipment_type, "ACC")
        self.assertEqual(adapter.curve_schema, "ambient_capacity_power_2D")

    def test_acc_dispatch_result_matches_existing_lookup(self):
        conditions = {
            "ambient_C": 35,
            "required_capacity_kW": 1200,
            "nominal_unit_capacity_kW": 1500,
        }

        result = calculate_equipment_performance(self.acc_metadata, self.acc_curve, conditions)
        expected = lookup_acc_curve(
            self.acc_curve,
            ambient_C=conditions["ambient_C"],
            required_capacity_kW=conditions["required_capacity_kW"],
            nominal_unit_capacity_kW=conditions["nominal_unit_capacity_kW"],
        )

        self.assertIsInstance(result, PerformanceResult)
        self.assertLess(abs(result.performance["power_kW"] - expected.power_input_kW), 1e-9)
        self.assertLess(abs(result.performance["COP"] - expected.cop), 1e-9)
        self.assertLess(abs(result.performance["capacity_kW"] - expected.capacity_kW), 1e-9)

    def test_chiller_dispatch(self):
        result = calculate_equipment_performance(
            self.chiller_metadata,
            self.chiller_curve,
            {
                "required_cooling_capacity_kW": 1000,
                "rated_chiller_capacity_kW": 2000,
                "CEFT_C": 35,
            },
        )

        self.assertEqual(result.equipment_type, "CHILLER")
        self.assertAlmostEqual(result.performance["COP"], 8.814, places=6)
        self.assertAlmostEqual(result.performance["power_kW"], 1000 / 8.814, places=6)
        self.assertEqual(result.performance["load_ratio"], 0.5)

    def test_dry_cooler_dispatch(self):
        result = calculate_equipment_performance(
            self.dry_cooler_metadata,
            self.dry_cooler_curve,
            {
                "required_heat_rejection_kW": 2445,
                "ambient_dry_bulb_C": 35,
            },
        )

        self.assertEqual(result.equipment_type, "DRY_COOLER")
        self.assertEqual(result.performance["power_kW"], 261.3)
        self.assertEqual(result.performance["capacity_kW"], 4890)
        self.assertEqual(result.performance["capacity_ratio"], 0.5)

    def test_invalid_equipment_rejection(self):
        with self.assertRaisesRegex(EquipmentPerformanceDispatchError, "Unsupported curve_type"):
            dispatch_performance_adapter(
                {
                    "equipment_id": "UNKNOWN_1",
                    "equipment_type": "ACC",
                    "curve_type": "not_a_curve",
                },
                [],
            )

    def test_standard_result_schema(self):
        result = calculate_equipment_performance(
            self.dry_cooler_metadata,
            self.dry_cooler_curve,
            {
                "required_heat_rejection_kW": 2445,
                "ambient_dry_bulb_C": 35,
            },
        ).to_dict()

        self.assertEqual(
            set(result),
            {"equipment_id", "equipment_type", "input_conditions", "performance", "diagnostics"},
        )
        for field in ("power_kW", "COP", "load_ratio", "capacity_ratio", "clamped_status"):
            self.assertIn(field, result["performance"])

    def test_acc_annual_pue_regression_unchanged(self):
        library_input = build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        dispatched = dispatch_topology(library_input["configuration_manifest"], library_input)
        baseline = build_acc_solver_input_from_configuration(
            library_input["configuration_manifest"],
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )

        dispatched_pue = dispatched["annual_results"]["annual_average_PUE"]
        baseline_pue = compute_pue_project(baseline)["annual_results"]["annual_average_PUE"]

        self.assertLess(abs(dispatched_pue - baseline_pue), 1e-9)


if __name__ == "__main__":
    unittest.main()
