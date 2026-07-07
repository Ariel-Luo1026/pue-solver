import json
import unittest
from copy import deepcopy
from unittest.mock import patch

import solver
from configuration_library_loader import build_solver_input_from_library
from library_solver_adapter import convert_library_input_to_solver_input
from solver import compute_pue_project


class Phase15FDirectModeGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.input = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        cls.output = compute_pue_project(deepcopy(cls.input))

    def test_direct_mode_uses_equipment_specific_source_labels(self):
        self.assertNotIn("error", self.output)
        hour = self.output["hourly_results"][0]
        annual = self.output["annual_results"]

        expected_sources = {
            "acc_curve_source": "configuration_library_solver_curve",
            "chw_pump_curve_source": "configuration_library_solver_curve",
            "mau_curve_source": "configuration_library_solver_curve",
            "rtc_curve_source": "configuration_library_solver_curve",
            "cdu_curve_source": "configuration_library_solver_curve",
            "electrical_distribution_curve_source": "configuration_library_solver_curve",
            "engine_curve_source": "configuration_library_solver_curve",
            "engine_radiator_curve_source": "configuration_library_solver_curve",
        }
        for key, source in expected_sources.items():
            self.assertEqual(hour[key], source)
            self.assertEqual(annual[key], source)

    def test_direct_mode_compatibility_fields_alias_mau(self):
        hour = self.output["hourly_results"][0]
        annual = self.output["annual_results"]

        self.assertEqual(hour["terminal_fan_power_kW"], hour["mau_power_kW"])
        self.assertEqual(hour["airflow_power_kW"], hour["mau_power_kW"])
        self.assertEqual(annual["annual_terminal_fan_energy_kWh"], annual["annual_mau_energy_kWh"])
        direct_equipment_power = (
            hour["cdu_power_kW"]
            + hour["rtc_power_kW"]
            + hour["mau_power_kW"]
            + hour["engine_radiator_power_kW"]
        )
        self.assertGreater(direct_equipment_power, 0.0)
        self.assertNotEqual(
            hour["auxiliary_power_kW"],
            direct_equipment_power,
            "Legacy auxiliary_power_kW must not hide RTC/CDU/MAU/engine/radiator direct-mode power.",
        )

    def test_direct_mode_output_has_no_legacy_fallback_metadata(self):
        serialized = json.dumps(self.output, sort_keys=True).lower()

        forbidden = (
            "legacy_pump_curve_fallback",
            "terminal_fan_curve_source",
            "legacy electrical fallback",
            "legacy_non_configuration_mode",
            "experimental_acc_ambient_shape_annual_calibration",
            "annual calibration",
            "benchmark target",
        )
        for token in forbidden:
            self.assertNotIn(token, serialized)
        self.assertNotIn("calibrated", serialized)

    def test_direct_mode_does_not_reference_legacy_curve_refs(self):
        calls = []
        original_curve_value = solver._curve_value

        def spy(curve_lib, curve_ref, x=None, y=None):
            calls.append(str(curve_ref))
            return original_curve_value(curve_lib, curve_ref, x, y)

        with patch.object(solver, "_curve_value", side_effect=spy):
            output = compute_pue_project(deepcopy(self.input))

        self.assertNotIn("error", output)
        joined = "\n".join(calls).lower()
        self.assertNotIn("pump_power_vs_it_load", joined)
        self.assertNotIn("terminal_fan", joined)
        self.assertNotIn("electrical efficiency curve", joined)
        self.assertNotIn("benchmark target", joined)
        self.assertNotIn("annual calibration", joined)


if __name__ == "__main__":
    unittest.main()
