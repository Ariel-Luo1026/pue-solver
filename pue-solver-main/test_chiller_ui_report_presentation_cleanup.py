import re
import unittest
from pathlib import Path


UI = (Path(__file__).parent / "ui.js").read_text(encoding="utf-8")


def function_source(name):
    match = re.search(rf"function\s+{re.escape(name)}\s*\([^)]*\)\s*{{", UI)
    if not match:
        raise AssertionError(f"Missing function: {name}")
    depth = 0
    quote = None
    escaped = False
    for index in range(match.end() - 1, len(UI)):
        char = UI[index]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif quote:
            if char == quote:
                quote = None
        elif char in "'\"`":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return UI[match.start():index + 1]
    raise AssertionError(f"Unclosed function: {name}")


class ChillerUiReportPresentationCleanupTest(unittest.TestCase):
    def test_browser_annual_breakdown_passes_topology_to_shared_rows(self):
        renderer = function_source("renderEngineeringResultsSummary")
        self.assertIn("annualEquipmentEnergyRows(annual, topologyId, engineApplicable)", renderer)

    def test_chiller_annual_rows_contain_every_active_component_once(self):
        rows = function_source("annualEquipmentEnergyRows")
        expected = {
            "Chiller": "annual_chiller_energy_kWh",
            "Dry Cooler": "annual_dry_cooler_energy_kWh",
            "CHW Pump": "annual_chw_pump_energy_kWh",
            "CW Pump": "annual_cw_pump_energy_kWh",
            "CDU": "annual_cdu_energy_kWh",
            "RTC": "annual_rtc_energy_kWh",
            "MAU": "annual_mau_energy_kWh",
            "Electrical Distribution Loss": "annual_electrical_loss_kWh",
        }
        for label, field in expected.items():
            self.assertIn(label, rows)
            self.assertIn(field, rows)
        self.assertNotIn('["Indoor Equipment"', rows)

    def test_one_shared_engine_applicability_rule_controls_all_renderers(self):
        applicability = function_source("engineGenerationApplicable")
        self.assertIn('/^grid$/i.test(String(powerSource).trim())', applicability)
        self.assertNotIn('topology === "acc_gas_engine_cdu"', applicability)
        self.assertIn("gas\\s*engine", applicability)
        self.assertIn("engineConfigured", applicability)
        self.assertIn("annual_engine_output_kWh", applicability)
        self.assertIn("engineGenerationApplicable(output, context.input || {})", function_source("buildHtmlReportFromSections"))
        self.assertIn("engineApplicable: engineGenerationApplicable(outObj)", function_source("buildPeakDemandBreakdown"))
        self.assertIn("breakdown.engineApplicable ?", function_source("renderPeakDemandBreakdown"))
        self.assertIn("engineGenerationApplicable(outObj, configurationLibraryData || {})", function_source("renderEngineeringResultsSummary"))

    def test_chiller_formula_includes_indoor_load_before_distribution_loss(self):
        formulas = function_source("formulasHtml")
        for token in ("indoor,h", "CDU,h", "RTC,h", "MAU,h", "elec,loss,h"):
            self.assertIn(token, formulas)
        self.assertIn("included in the MEP terminal load before electrical-distribution loss", formulas)

    def test_dry_cooler_wording_disclaims_second_power_calculation(self):
        report = function_source("buildHtmlReportFromSections")
        self.assertIn("not applied as a second runtime power calculation", report)
        self.assertIn("Performance_Map separately represents thermal heat-rejection capacity", report)
        self.assertNotIn("Engineering temperature-only power estimate based on the supplied", report)


if __name__ == "__main__":
    unittest.main()
