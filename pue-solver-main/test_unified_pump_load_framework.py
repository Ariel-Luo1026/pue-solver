import unittest

from pump_load_framework import (
    PumpLoadFrameworkError,
    calculate_failure_peak_pump_reference,
    evaluate_pump_power,
    resolve_pump_reference_capacity,
)


class UnifiedPumpLoadFrameworkTest(unittest.TestCase):
    CURVE = [
        {"load_ratio": 0.1, "power_kW": 10.0},
        {"load_ratio": 0.5, "power_kW": 20.0},
        {"load_ratio": 1.0, "power_kW": 40.0},
    ]

    def test_fixed_reference_formula_and_total_power(self):
        result = evaluate_pump_power(1200, 2, 1000, self.CURVE)
        self.assertAlmostEqual(result["pump_required_load_per_unit_kW"], 600)
        self.assertAlmostEqual(result["pump_load_ratio_raw"], 0.6)
        self.assertAlmostEqual(result["pump_load_ratio_lookup"], 0.6)
        self.assertAlmostEqual(result["pump_power_per_unit_kW"], 24)
        self.assertAlmostEqual(result["pump_power_total_kW"], 48)

    def test_clamping_and_stopped_pump(self):
        low = evaluate_pump_power(10, 2, 1000, self.CURVE)
        high = evaluate_pump_power(3000, 2, 1000, self.CURVE)
        stopped = evaluate_pump_power(100, 0, 1000, self.CURVE)
        self.assertTrue(low["pump_clamped_low"])
        self.assertTrue(high["pump_clamped_high"])
        self.assertTrue(high["pump_overload"])
        self.assertIsNone(stopped["pump_load_ratio_lookup"])
        self.assertEqual(stopped["pump_power_total_kW"], 0)

    def test_reference_precedence_and_missing_reference_failure(self):
        value, source = resolve_pump_reference_capacity(
            {"pump_reference_capacity_kW": 900}, {"reference_capacity_kW": 800}, 700
        )
        self.assertEqual((value, source), (900, "role_metadata.pump_reference_capacity_kW"))
        with self.assertRaisesRegex(PumpLoadFrameworkError, "reference capacity is unavailable"):
            resolve_pump_reference_capacity()

    def test_failure_peak_design_reference_uses_canonical_thermal_inputs(self):
        result = calculate_failure_peak_pump_reference(
            4000,
            7,
            71,
            4,
        )
        self.assertEqual(result["pump_reference_peak_cooling_load_kW"], 4078)
        self.assertEqual(result["pump_reference_capacity_kW"], 1019.5)
        failure = evaluate_pump_power(4078, 4, result["pump_reference_capacity_kW"], self.CURVE)
        normal = evaluate_pump_power(4078, 5, result["pump_reference_capacity_kW"], self.CURVE)
        self.assertAlmostEqual(failure["pump_load_ratio_raw"], 1.0)
        self.assertAlmostEqual(normal["pump_load_ratio_raw"], 0.8)
        self.assertFalse(failure["pump_clamped_high"])

    def test_failure_peak_reference_rejects_invalid_design_inputs(self):
        with self.assertRaisesRegex(PumpLoadFrameworkError, "Design IT load"):
            calculate_failure_peak_pump_reference(0, 0, 0, 4)
        with self.assertRaisesRegex(PumpLoadFrameworkError, "greater than zero"):
            calculate_failure_peak_pump_reference(4000, 0, 0, 0)


if __name__ == "__main__":
    unittest.main()
