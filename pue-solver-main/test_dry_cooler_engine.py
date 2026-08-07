import unittest
from pathlib import Path

from configuration_library_loader import _records, read_xlsx_sheets
from equipment_curve_reader import DRY_COOLER_OUTDOOR_TEMPERATURE_POWER, read_equipment_solver_curve
from equipment_engines.dry_cooler import (
    DryCoolerEngineValidationError,
    calculate_dry_cooler_power,
    lookup_dry_cooler_point,
    lookup_dry_cooler_power_point,
)


CONFIGURATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "Configuration Library"
    / "CHILLER_DRYCOOLER_2MW_GRID"
)


class DryCoolerEngineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preview = read_equipment_solver_curve(CONFIGURATION_PATH, "DRYCOOLER_6")
        workbook = CONFIGURATION_PATH / "equipment" / "DRYCOOLER_6" / "DRYCOOLER_6.xlsx"
        cls.performance_map = _records(read_xlsx_sheets(workbook)["Performance_Map"])

    def test_reader_detects_dry_cooler_curve(self):
        self.assertEqual(self.preview.curve_type, DRY_COOLER_OUTDOOR_TEMPERATURE_POWER)
        self.assertEqual(self.preview.errors, [])

    def test_ambient_lookup(self):
        point = lookup_dry_cooler_point(
            self.performance_map,
            ambient_dry_bulb_C=35,
            equipment_id="DRYCOOLER_6",
        )

        self.assertEqual(point["ambient_dry_bulb_C"], 35)
        self.assertEqual(point["dry_cooler_capacity_kW"], 4890)

    def test_capacity_calculation(self):
        result = calculate_dry_cooler_power(
            self.preview,
            required_heat_rejection_kW=2445,
            ambient_dry_bulb_C=35,
            equipment_id="DRYCOOLER_6",
            capacity_curve_data=self.performance_map,
        )

        self.assertEqual(result["dry_cooler_capacity_kW"], 4890)
        self.assertEqual(result["dry_cooler_capacity_ratio"], 0.5)

    def test_fan_power_output(self):
        result = calculate_dry_cooler_power(
            self.preview,
            required_heat_rejection_kW=2445,
            ambient_dry_bulb_C=35,
            equipment_id="DRYCOOLER_6",
            capacity_curve_data=self.performance_map,
        )

        expected = lookup_dry_cooler_power_point(self.preview, 35, "DRYCOOLER_6")["dry_cooler_power_kW"]
        self.assertEqual(result["dry_cooler_power_kW"], expected)
        self.assertEqual(result["dry_cooler_curve_source"], "configuration_library_solver_curve")

    def test_missing_curve_error(self):
        with self.assertRaisesRegex(DryCoolerEngineValidationError, "Heat_Rejection_Capacity_kW"):
            lookup_dry_cooler_point(
                [{"Outdoor_Dry_Bulb_C": 35, "Estimated_Fan_Power_kW": 261.3}],
                ambient_dry_bulb_C=35,
                equipment_id="TEST_DRY_COOLER",
            )


if __name__ == "__main__":
    unittest.main()
