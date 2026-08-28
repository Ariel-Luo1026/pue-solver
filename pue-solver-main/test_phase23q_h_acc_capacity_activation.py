import contextlib
import io
import unittest
from pathlib import Path

from configuration_library_loader import build_solver_input_from_library
from library_solver_adapter import convert_library_input_to_solver_input
from solver import _evaluate_acc_equipment_curve, compute_pue_project


LIBRARY = Path(__file__).resolve().parents[1] / "Configuration Library"


def _payload(configuration_id, scenario, frontend=False, ambient=25.0):
    payload = convert_library_input_to_solver_input(
        build_solver_input_from_library(configuration_id, 4.0, scenario)
    )
    payload["project"]["it_load"]["hourly_it_load_kW"] = [3600.0]
    payload["project"]["it_load"]["hourly_it_load_percent"] = [90.0]
    payload["weather"]["hourly_data"] = {
        "hour_index": [1], "dry_bulb_C": [ambient], "wet_bulb_C": []
    }
    payload["_skip_peak_design_pue"] = True
    if frontend:
        payload["acc_v2_enabled"] = True
        payload["acc_v2"] = {"configuration_path": str(LIBRARY / configuration_id)}
    return payload


def _run(payload):
    with contextlib.redirect_stdout(io.StringIO()):
        return compute_pue_project(payload)


class Phase23QHAccCapacityActivationTests(unittest.TestCase):
    def test_acc1_direct_normal_and_failure_use_required_capacity(self):
        expected = {
            "Normal": (5, 720.0, 89.8513374327, 649.9, 780.0),
            "Failure": (4, 900.0, 115.0185714286, 780.0, 910.2),
        }
        for scenario, values in expected.items():
            with self.subTest(scenario=scenario):
                result = _run(_payload("ACC_1MW_GRID_CDU", scenario))
                self.assertNotIn("error", result)
                hour = result["hourly_results"][0]
                units, required, power, low, high = values
                self.assertEqual(hour["cooling_unit_count"], units)
                self.assertAlmostEqual(hour["acc_required_capacity_per_unit_kW"], required)
                self.assertAlmostEqual(hour["acc_used_capacity_kW"], required)
                self.assertAlmostEqual(hour["acc_power_input_per_unit_kW"], power)
                self.assertAlmostEqual(hour["acc_power_input_kW"], power * units)
                self.assertAlmostEqual(hour["acc_capacity_bracket_low_kW"], low)
                self.assertAlmostEqual(hour["acc_capacity_bracket_high_kW"], high)
                self.assertEqual(hour["acc_evaluator"], "acc_v2_capacity_surface")
                self.assertEqual(hour["acc_lookup_basis"], "ambient_C+required_capacity_per_unit_kW")
                self.assertTrue(hour["acc_v2_active"])

    def test_direct_frontend_and_grid_gas_parity(self):
        results = {}
        for configuration_id in ("ACC_1MW_GRID_CDU", "ACC_1MW_GASENGINE_CDU"):
            direct = _run(_payload(configuration_id, "Normal"))
            frontend = _run(_payload(configuration_id, "Normal", frontend=True))
            for key in ("cooling_load_kW", "cooling_unit_count", "acc_required_capacity_per_unit_kW",
                        "acc_used_capacity_kW", "acc_power_input_per_unit_kW", "acc_power_input_kW"):
                self.assertAlmostEqual(direct["hourly_results"][0][key], frontend["hourly_results"][0][key])
            results[configuration_id] = direct["hourly_results"][0]
        for key in ("cooling_load_kW", "cooling_unit_count", "acc_required_capacity_per_unit_kW",
                    "acc_used_capacity_kW", "acc_power_input_per_unit_kW", "acc_power_input_kW"):
            self.assertAlmostEqual(results["ACC_1MW_GRID_CDU"][key], results["ACC_1MW_GASENGINE_CDU"][key])

    def test_acc15_direct_and_frontend_use_same_capacity_surface(self):
        direct = _run(_payload("ACC_1.5MW_GRID_CDU", "Normal"))
        frontend = _run(_payload("ACC_1.5MW_GRID_CDU", "Normal", frontend=True))
        for result in (direct, frontend):
            self.assertNotIn("error", result)
            hour = result["hourly_results"][0]
            self.assertEqual(hour["acc_evaluator"], "acc_v2_capacity_surface")
            self.assertAlmostEqual(hour["acc_used_capacity_kW"], hour["acc_required_capacity_per_unit_kW"])
            self.assertNotEqual(hour["acc_power_input_per_unit_kW"], 100.1)
        self.assertAlmostEqual(direct["hourly_results"][0]["acc_power_input_per_unit_kW"],
                               frontend["hourly_results"][0]["acc_power_input_per_unit_kW"])

    def test_rectangular_guard_and_genuine_legacy_support(self):
        rectangular = {"curve_type": "ambient_capacity_power", "data": [
            {"ambient_C": 25, "load_ratio": 0.5, "capacity_kW": 500, "power_input_kW": 50},
            {"ambient_C": 25, "load_ratio": 1.0, "capacity_kW": 1000, "power_input_kW": 100},
        ]}
        with self.assertRaisesRegex(RuntimeError, "requires capacity-aware ACC evaluation"):
            _evaluate_acc_equipment_curve(rectangular, 0.75, 750, 1, oat_c=25)
        legacy = {"equipment_id": "LEGACY_ACC", "source_sheet": "Curve", "data": [
            {"load_ratio": 0.5, "power_input_kW": 50},
            {"load_ratio": 1.0, "power_input_kW": 100},
        ]}
        power, _cop, source, ambient, _factor = _evaluate_acc_equipment_curve(legacy, 0.75, 750, 1)
        self.assertAlmostEqual(power, 75.0)
        self.assertIn("LEGACY_ACC", source)
        self.assertIsNone(ambient)

    def test_peak_clamp_and_chw_pump_reference_are_unchanged(self):
        payload = _payload("ACC_1MW_GRID_CDU", "Normal")
        payload.pop("_skip_peak_design_pue")
        payload.update({"solar_heat_gain_max_kW": 7, "other_auxiliary_heat_gain_kW": 71,
                        "peak_design_weather_source": "manual", "peak_design_outdoor_dry_bulb_C": 46.1})
        result = _run(payload)
        self.assertNotIn("error", result)
        peak = result["peak_results"]
        self.assertAlmostEqual(peak["peak_design_CHW_pump_reference_capacity_kW"], 1019.5)
        self.assertAlmostEqual(peak["peak_design_CHW_pump_load_ratio"], 0.8)
        self.assertAlmostEqual(peak["peak_design_ACC_required_capacity_per_unit_kW"], 815.6)


if __name__ == "__main__":
    unittest.main()
