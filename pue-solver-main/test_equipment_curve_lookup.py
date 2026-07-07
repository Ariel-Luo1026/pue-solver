import unittest

from equipment_curve_lookup import EquipmentOperatingPoint, lookup_equipment_curve
from equipment_curve_reader import EquipmentCurvePreview


class EquipmentCurveLookupTest(unittest.TestCase):
    def test_one_dimensional_exact_interpolation_and_clamp(self):
        preview = _preview("CHW_PUMP_2", "one_dimensional_power", [
            {"load_ratio": 0.2, "power_kW": 10},
            {"load_ratio": 0.8, "power_kW": 40},
        ])

        self.assertEqual(lookup_equipment_curve(preview, EquipmentOperatingPoint(0.2)).power_kW, 10)
        self.assertAlmostEqual(lookup_equipment_curve(preview, EquipmentOperatingPoint(0.5)).power_kW, 25)
        self.assertEqual(lookup_equipment_curve(preview, EquipmentOperatingPoint(-1)).load_ratio, 0.2)
        self.assertEqual(lookup_equipment_curve(preview, EquipmentOperatingPoint(2)).load_ratio, 0.8)

    def test_one_dimensional_duplicate_rejection(self):
        preview = _preview("CHW_PUMP_2", "one_dimensional_power", [
            {"load_ratio": 0.5, "power_kW": 10},
            {"load_ratio": 0.5, "power_kW": 11},
        ])

        result = lookup_equipment_curve(preview, EquipmentOperatingPoint(0.5))

        self.assertFalse(result.lookup_success)
        self.assertIn("Duplicate CHW_PUMP_2 load_ratio point", result.errors[0])

    def test_two_dimensional_exact_and_interpolation(self):
        preview = _preview("ACC_2", "two_dimensional_power", [
            {"ambient_C": 20, "load_ratio": 0.5, "power_input_kW": 100, "capacity_kW": 1000},
            {"ambient_C": 20, "load_ratio": 1.0, "power_input_kW": 200, "capacity_kW": 1200},
            {"ambient_C": 30, "load_ratio": 0.5, "power_input_kW": 150, "capacity_kW": 900},
            {"ambient_C": 30, "load_ratio": 1.0, "power_input_kW": 300, "capacity_kW": 1100},
        ])

        exact = lookup_equipment_curve(preview, EquipmentOperatingPoint(0.5, ambient_C=20))
        ambient = lookup_equipment_curve(preview, EquipmentOperatingPoint(0.5, ambient_C=25))
        load = lookup_equipment_curve(preview, EquipmentOperatingPoint(0.75, ambient_C=20))
        bilinear = lookup_equipment_curve(preview, EquipmentOperatingPoint(0.75, ambient_C=25))

        self.assertEqual(exact.power_input_kW, 100)
        self.assertEqual(ambient.power_input_kW, 125)
        self.assertEqual(load.power_input_kW, 150)
        self.assertEqual(bilinear.power_input_kW, 187.5)
        self.assertEqual(lookup_equipment_curve(preview, EquipmentOperatingPoint(9, ambient_C=99)).load_ratio, 1.0)

    def test_electrical_efficiency_loss_fraction_and_loss_power(self):
        efficiency = _preview("ELECTRICAL_DISTRIBUTION_2", "electrical_efficiency", [
            {"load_ratio": 0.0, "efficiency": 0.95},
            {"load_ratio": 1.0, "efficiency": 0.99},
        ])
        loss_fraction = _preview("ELECTRICAL_DISTRIBUTION_2", "electrical_loss_fraction", [
            {"load_ratio": 0.0, "loss_fraction": 0.05},
            {"load_ratio": 1.0, "loss_fraction": 0.01},
        ])
        loss_power = _preview("ELECTRICAL_DISTRIBUTION_2", "electrical_loss_power", [
            {"load_ratio": 0.0, "loss_kW": 5},
            {"load_ratio": 1.0, "loss_kW": 15},
        ])

        self.assertAlmostEqual(
            lookup_equipment_curve(efficiency, EquipmentOperatingPoint(0.5, base_power_kW=100)).loss_kW,
            100 / 0.97 - 100,
        )
        self.assertAlmostEqual(
            lookup_equipment_curve(loss_fraction, EquipmentOperatingPoint(0.5, base_power_kW=100)).loss_kW,
            3.0,
        )
        self.assertEqual(
            lookup_equipment_curve(loss_power, EquipmentOperatingPoint(0.5, base_power_kW=100)).loss_kW,
            10,
        )

    def test_electrical_requires_base_power_for_efficiency_and_loss_fraction(self):
        efficiency = _preview("ELECTRICAL_DISTRIBUTION_2", "electrical_efficiency", [
            {"load_ratio": 0.5, "efficiency": 0.98},
        ])
        loss_fraction = _preview("ELECTRICAL_DISTRIBUTION_2", "electrical_loss_fraction", [
            {"load_ratio": 0.5, "loss_fraction": 0.02},
        ])

        self.assertFalse(lookup_equipment_curve(efficiency, EquipmentOperatingPoint(0.5)).lookup_success)
        self.assertFalse(lookup_equipment_curve(loss_fraction, EquipmentOperatingPoint(0.5)).lookup_success)

    def test_invalid_electrical_efficiency_rejected(self):
        efficiency = _preview("ELECTRICAL_DISTRIBUTION_2", "electrical_efficiency", [
            {"load_ratio": 0.5, "efficiency": 0.0},
        ])

        result = lookup_equipment_curve(efficiency, EquipmentOperatingPoint(0.5, base_power_kW=100))

        self.assertFalse(result.lookup_success)
        self.assertIn("Invalid ELECTRICAL_DISTRIBUTION_2 efficiency", result.errors[0])


def _preview(equipment_id, curve_type, rows):
    return EquipmentCurvePreview(
        equipment_id=equipment_id,
        curve_type=curve_type,
        solver_curve_rows=rows,
        required_columns_present=True,
    )


if __name__ == "__main__":
    unittest.main()
