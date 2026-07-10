import json
import unittest
from copy import deepcopy
from pathlib import Path

from configuration_direct_mode_audit import (
    CALIBRATION_TERMS,
    LEGACY_TERMS,
    audit_direct_mode_result,
)
from configuration_library_loader import build_solver_input_from_library
from library_solver_adapter import convert_library_input_to_solver_input
from solver import compute_pue_project


class ConfigurationDirectModeAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.input = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        cls.result = compute_pue_project(deepcopy(cls.input))

    def test_audit_passes_real_direct_mode_result(self):
        audit = audit_direct_mode_result(self.result)

        self.assertTrue(audit.passed, audit.errors)
        self.assertEqual(audit.errors, [])
        self.assertEqual(audit.legacy_terms_found, [])
        self.assertEqual(
            audit.equipment_sources,
            {
                "acc_curve_source": "configuration_library_solver_curve",
                "chw_pump_curve_source": "configuration_library_solver_curve",
                "mau_curve_source": "configuration_library_solver_curve",
                "rtc_curve_source": "configuration_library_solver_curve",
                "cdu_curve_source": "configuration_library_solver_curve",
                "electrical_distribution_curve_source": "configuration_library_solver_curve",
                "engine_curve_source": "configuration_library_solver_curve",
                "engine_radiator_curve_source": "configuration_library_solver_curve",
            },
        )

    def test_audit_accepts_acc_v2_direct_source_label(self):
        result = deepcopy(self.result)
        result["hourly_results"][0]["acc_curve_source"] = "acc_v2_solver_curve_direct"
        result["annual_results"]["acc_curve_source"] = "acc_v2_solver_curve_direct"

        audit = audit_direct_mode_result(result)

        self.assertTrue(audit.passed, audit.errors)

    def test_audit_rejects_legacy_source_labels_and_terms(self):
        result = deepcopy(self.result)
        result["annual_results"]["chw_pump_curve_source"] = "legacy_non_configuration_mode"
        result["hourly_results"][0]["terminal_fan_curve_source"] = "legacy_pump_curve_fallback"

        audit = audit_direct_mode_result(result)

        self.assertFalse(audit.passed)
        self.assertIn("legacy_non_configuration_mode", audit.legacy_terms_found)
        self.assertIn("legacy_pump_curve_fallback", audit.legacy_terms_found)

    def test_audit_rejects_calibration_language_in_result(self):
        result = deepcopy(self.result)
        result["annual_results"]["calculation_note"] = "weather-driven sensitivity calibrated to benchmark target"

        audit = audit_direct_mode_result(result)

        self.assertFalse(audit.passed)
        self.assertIn("calibrated", audit.legacy_terms_found)
        self.assertIn("benchmark target", audit.legacy_terms_found)
        self.assertIn("weather-driven sensitivity", audit.legacy_terms_found)

    def test_audit_energy_consistency_uses_hourly_sums(self):
        audit = audit_direct_mode_result(self.result)

        self.assertTrue(audit.passed, audit.errors)
        for check in audit.energy_consistency.values():
            self.assertTrue(check["passed"], check)
            self.assertLessEqual(check["delta"], 1e-4, check)

    def test_audit_rejects_energy_mismatch(self):
        result = deepcopy(self.result)
        result["annual_results"]["annual_mau_energy_kWh"] += 1.0

        audit = audit_direct_mode_result(result)

        self.assertFalse(audit.passed)
        self.assertFalse(audit.energy_consistency["annual_mau_energy_kWh"]["passed"])

    def test_audit_rejects_terminal_fan_mau_double_count(self):
        result = deepcopy(self.result)
        result["hourly_results"][0]["terminal_fan_power_kW"] = result["hourly_results"][0]["mau_power_kW"] + 1.0

        audit = audit_direct_mode_result(result)

        self.assertFalse(audit.passed)
        self.assertTrue(any("terminal_fan_power_kW duplicates mau_power_kW" in error for error in audit.errors))

    def test_missing_or_invalid_equipment_controlled_failures(self):
        cases = {
            "ACC": _remove_acc_curve,
            "CHW_PUMP_2": lambda sample: sample["curve_library"]["curves"].pop("CHW_PUMP_2_power_vs_load", None),
            "MAU_1&2": lambda sample: _pop_library_fixed_power(sample, "MAU"),
            "RTC_1&2": lambda sample: _pop_library_fixed_power(sample, "RTC"),
            "CDU_2": lambda sample: _pop_library_fixed_power(sample, "CDU"),
            "ELECTRICAL_DISTRIBUTION_2": _remove_electrical_path,
            "ENGINE_3": lambda sample: sample.pop("engine_curve", None),
            "ENGINE_RADIATOR_1": lambda sample: sample.pop("engine_radiator_curve", None),
        }
        for equipment_id, mutate in cases.items():
            with self.subTest(equipment_id=equipment_id):
                sample = deepcopy(self.input)
                mutate(sample)

                output = compute_pue_project(sample)

                self.assertIn("error", output)
                self.assertIn(f"{equipment_id} Solver_Curve missing or invalid", output["error"])
                self.assertEqual(output["hourly_results"], [])
                self.assertEqual(output["annual_results"], {})

    def test_direct_mode_visible_ui_and_report_text_allows_required_no_calibration_disclosure_only(self):
        root = Path(__file__).resolve().parent
        visible_sources = [
            (root / "index.html").read_text(encoding="utf-8"),
            (root / "ui.js").read_text(encoding="utf-8"),
        ]
        visible_source = "\n".join(visible_sources)
        visible_text = visible_source.lower()

        forbidden_visible_phrases = (
            "annual energy performance calibration",
            "benchmark target",
            "weather-driven sensitivity",
            "fallback to legacy",
        )
        for phrase in forbidden_visible_phrases:
            self.assertNotIn(phrase, visible_text)
        self.assertIn("Annual Calibration", visible_source)
        self.assertIn("Not applied", visible_source)
        self.assertNotIn("Annual Calibrated", visible_source)

    def test_audit_serialized_output_has_no_forbidden_terms(self):
        serialized = json.dumps(self.result, sort_keys=True).lower()

        for term in LEGACY_TERMS + CALIBRATION_TERMS:
            self.assertNotIn(term, serialized)


def _pop_library_fixed_power(sample, prefix):
    fixed_power = sample.get("equipment", {}).get("library_fixed_power", {})
    for key in list(fixed_power):
        if str(key).upper().startswith(prefix):
            fixed_power.pop(key)


def _remove_acc_curve(sample):
    sample.pop("acc_curve", None)
    if isinstance(sample.get("library_context"), dict):
        sample["library_context"].pop("acc_curve", None)


def _remove_electrical_path(sample):
    sample.pop("electrical_path", None)
    if isinstance(sample.get("equipment"), dict):
        sample["equipment"].pop("electrical_path", None)


if __name__ == "__main__":
    unittest.main()
