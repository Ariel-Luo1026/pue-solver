import unittest
from pathlib import Path

from equipment_curve_reader import CHILLER_COP_MAP, read_equipment_solver_curve
from equipment_engines.chiller import (
    ChillerEngineValidationError,
    calculate_chiller_power,
    lookup_chiller_cop,
)


CONFIGURATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "Configuration Library"
    / "CHILLER_DRYCOOLER_2MW_GRID"
)


class ChillerEngineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preview = read_equipment_solver_curve(CONFIGURATION_PATH, "CENTRIFUGALCHILLER_1")

    def test_reader_detects_chiller_cop_map(self):
        self.assertEqual(self.preview.curve_type, CHILLER_COP_MAP)
        self.assertEqual(self.preview.errors, [])

    def test_valid_cop_lookup(self):
        cop = lookup_chiller_cop(self.preview, CEFT_C=35, load_ratio=1.0, equipment_id="CENTRIFUGALCHILLER_1")

        self.assertAlmostEqual(cop, 8.099, places=6)

    def test_part_load_cop_lookup(self):
        full_load_cop = lookup_chiller_cop(self.preview, CEFT_C=35, load_ratio=1.0, equipment_id="CENTRIFUGALCHILLER_1")
        part_load_cop = lookup_chiller_cop(self.preview, CEFT_C=35, load_ratio=0.5, equipment_id="CENTRIFUGALCHILLER_1")

        self.assertAlmostEqual(part_load_cop, 8.814, places=6)
        self.assertNotEqual(part_load_cop, full_load_cop)

    def test_power_calculation(self):
        result = calculate_chiller_power(
            [{"CEFT_C": 35, "load_ratio": 1.0, "COP_kW_per_kW": 5.0}],
            required_cooling_capacity_kW=1000,
            rated_chiller_capacity_kW=1000,
            CEFT_C=35,
            equipment_id="TEST_CHILLER",
        )

        self.assertEqual(result["chiller_power_kW"], 200)
        self.assertEqual(result["chiller_COP"], 5)
        self.assertEqual(result["chiller_load_ratio"], 1)
        self.assertEqual(result["chiller_capacity_kW"], 1000)
        self.assertEqual(result["chiller_curve_source"], "configuration_library_solver_curve")

    def test_invalid_curve_missing_cop_map(self):
        with self.assertRaisesRegex(ChillerEngineValidationError, "COP_kW_per_kW"):
            lookup_chiller_cop(
                [{"CEFT_C": 35, "load_ratio": 1.0, "power_kW": 200}],
                CEFT_C=35,
                load_ratio=1.0,
                equipment_id="TEST_CHILLER",
            )


if __name__ == "__main__":
    unittest.main()
