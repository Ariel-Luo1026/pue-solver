import copy
import unittest
from pathlib import Path

from configuration_library_loader import build_solver_input_from_library
from library_solver_adapter import convert_library_input_to_solver_input
from solver import compute_pue_project


class FrontendACCV2IntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent
        cls.index = (root / "index.html").read_text(encoding="utf-8")
        cls.ui = (root / "ui.js").read_text(encoding="utf-8")

    def test_acc_engine_selector_exists_and_legacy_is_default(self):
        self.assertIn('id="accCalculationEngine"', self.index)
        self.assertIn('<option value="legacy" selected>Legacy ACC Engine</option>', self.index)
        self.assertIn('<option value="acc_v2">ACC V2 Configuration Library Engine</option>', self.index)

    def test_engineering_note_explains_strict_acc_v2_solver_curve_requirement(self):
        self.assertIn("Engineering Mode — ACC Calculation Engine", self.index)
        self.assertIn("ACC V2 requires valid Configuration Library Solver_Curve data.", self.index)

    def test_frontend_maps_acc_v2_selection_to_solver_feature_flag(self):
        self.assertIn("function applyAccCalculationEngineSelection", self.ui)
        self.assertIn("feature_flags.acc_v2_enabled = true", self.ui)
        self.assertIn("inputObj.acc_v2.enabled = true", self.ui)
        self.assertIn("feature_flags.acc_v2_enabled = false", self.ui)

    def test_legacy_only_benchmark_modes_do_not_receive_acc_v2_feature_flag(self):
        self.assertIn('"excel_benchmark_compatible"', self.ui)
        self.assertIn('"excel_replicated_hourly"', self.ui)
        self.assertIn('legacyOnlyBenchmarkModes = ["excel_benchmark_compatible", "excel_replicated_hourly"]', self.ui)
        self.assertIn('legacyOnlyBenchmarkModes.includes(calculationMode) ? "legacy" : selectedEngine', self.ui)
        self.assertIn("legacyOnlyBenchmarkModes.includes(calculationMode)", self.ui)

    def test_experimental_mode_can_receive_acc_v2_feature_flag(self):
        self.assertIn('"experimental_acc_hourly_shape"', self.ui)
        helper_start = self.ui.index("function applyAccCalculationEngineSelection")
        helper_end = self.ui.index("function getAccEngineUsedLabel")
        helper_source = self.ui[helper_start:helper_end]
        self.assertNotIn('"experimental_acc_hourly_shape"', helper_source)

    def test_frontend_result_area_reports_acc_engine_used(self):
        self.assertIn("function getAccEngineUsedLabel", self.ui)
        self.assertIn("ACC Engine Used:", self.ui)
        self.assertIn("ACC V2 unavailable", self.ui)
        self.assertIn('"acc_v2"', self.ui)

    def test_solver_rejects_acc_v2_enabled_and_missing_configuration_in_direct_mode(self):
        sample = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        sample["feature_flags"] = {"acc_v2_enabled": True}
        sample["acc_v2"] = {"enabled": True, "configuration_path": "missing-configuration"}

        result = compute_pue_project(sample)

        self.assertIn("error", result)
        self.assertIn("ACC Solver_Curve missing or invalid", result["error"])
        self.assertIn("does not allow ACC legacy fallback", result["error"])


if __name__ == "__main__":
    unittest.main()
