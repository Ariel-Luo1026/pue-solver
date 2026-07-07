import re
import unittest
from pathlib import Path


class FrontendConfigurationLibraryUITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent
        cls.index = (root / "index.html").read_text(encoding="utf-8")
        cls.ui = (root / "ui.js").read_text(encoding="utf-8")

    def test_manual_redundancy_controls_exist(self):
        for text in (
            "Unit Quantity / Redundancy",
            "Quantity Mode",
            "Redundancy",
            "Installed Units",
            "Running Units",
            "Standby Units",
            'id="unitQuantityMode"',
            'id="unitRedundancyMode"',
            'id="manualInstalledUnits"',
            'id="manualRunningUnits"',
            'id="manualStandbyUnits"',
        ):
            self.assertIn(text, self.index)

    def test_unit_quantity_maps_to_project_input(self):
        self.assertIn("function getUnitQuantitySelection", self.ui)
        self.assertIn('mode: "manual"', self.ui)
        self.assertIn('redundancy === "N+1"', self.ui)
        self.assertIn('redundancy === "N+2"', self.ui)
        self.assertIn("unit_quantity: unitQuantity", self.ui)
        self.assertIn("running_units: activeUnits", self.ui)
        self.assertIn("standby_units: standbyUnits", self.ui)

    def test_auto_mode_remains_default(self):
        self.assertIn('<option value="auto" selected>Auto</option>', self.index)
        self.assertIn('mode: "auto"', self.ui)
        self.assertIn("calculateFrontendUnitRequirements", self.ui)

    def test_configuration_library_binding_uses_current_equipment_ids(self):
        expected_ids = (
            "ACC_2",
            "CHW_PUMP_2",
            "CDU_2",
            "RTC_1&2",
            "MAU_1&2",
            "ELECTRICAL_DISTRIBUTION_2",
            "ENGINE_3",
            "ENGINE_RADIATOR_1",
        )
        binding_block = self._function_source("renderConfigurationLibrarySummary")
        for equipment_id in expected_ids:
            self.assertIn(equipment_id, binding_block)
        self.assertIn("Using Configuration Library Solver_Curve", binding_block)
        self.assertIn("Missing Solver_Curve", binding_block)

    def test_result_cards_use_not_available_placeholder(self):
        summary_block = self._function_source("renderConfigurationLibrarySummary")
        self.assertIn("Not available", summary_block)
        self.assertNotIn("Waiting for Solver", summary_block)

    def test_framework_diagnostics_use_direct_mode_labels(self):
        diagnostics_block = self.ui[
            self.ui.index("const FRAMEWORK_DIAGNOSTIC_TOPOLOGIES"):
            self.ui.index("const DEFAULT_COOLING_SYSTEM_TYPE")
        ]
        for required in (
            "ACC_2 Solver_Curve",
            "CHW_PUMP_2 Solver_Curve",
            "MAU_1&2 Solver_Curve",
            "RTC_1&2 Solver_Curve",
            "CDU_2 Solver_Curve",
            "ELECTRICAL_DISTRIBUTION_2 Solver_Curve",
            "ENGINE_3 Solver_Curve",
            "ENGINE_RADIATOR_1 Solver_Curve",
        ):
            self.assertIn(required, diagnostics_block)
        for legacy in ("terminal_fan", "auxiliary_load", "heat_exchanger", "pump_power_curve", "electrical_efficiency_curve"):
            self.assertNotIn(legacy, diagnostics_block)

    def test_report_wording_uses_current_equipment_names(self):
        report_block = self._function_source("buildHtmlReport")
        self.assertIn("MAU Energy", report_block)
        self.assertIn("Electrical Distribution Loss", report_block)
        self.assertIn("CDU / RTC / MAU", report_block)
        for forbidden in (
            "Terminal Fan",
            "Airflow Power",
            "Auxiliary Load",
            "fallback to Legacy",
            "weather-driven sensitivity",
            "annual calibration",
            "benchmark target",
        ):
            self.assertNotIn(forbidden, report_block)

    def _function_source(self, function_name):
        start = self.ui.index(f"function {function_name}")
        match = re.search(r"\nfunction\s+\w+", self.ui[start + 1:])
        end = start + 1 + match.start() if match else len(self.ui)
        return self.ui[start:end]


if __name__ == "__main__":
    unittest.main()
