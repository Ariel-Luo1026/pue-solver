import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parent
UI = (ROOT / "ui.js").read_text(encoding="utf-8")
SOLVER = (ROOT / "solver.py").read_text(encoding="utf-8")


def function_source(source, name):
    match = re.search(rf"function\s+{re.escape(name)}\s*\([^)]*\)\s*{{", source)
    if not match:
        raise AssertionError(f"Missing function: {name}")
    depth = 0
    quote = None
    escaped = False
    for index in range(match.end() - 1, len(source)):
        char = source[index]
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
                return source[match.start():index + 1]
    raise AssertionError(f"Unclosed function: {name}")


class FinalReportConsistencyCleanupTest(unittest.TestCase):
    def test_peak_total_electrical_loss_is_canonical_peak_hour_field(self):
        self.assertIn(
            '"peak_design_electrical_loss_kW": peak_design_hour.get("electrical_loss_kW")',
            SOLVER,
        )
        self.assertIn(
            '"peak_design_it_electrical_loss_kW": peak_design_hour.get("it_electrical_loss_kW")',
            SOLVER,
        )
        self.assertIn(
            '"peak_design_mep_electrical_loss_kW": peak_design_hour.get("mep_electrical_loss_kW")',
            SOLVER,
        )

    def test_appendix_and_browser_pdf_use_canonical_total(self):
        report = function_source(UI, "buildHtmlReportFromSections")
        self.assertIn('["Electrical Loss, kW", peak.peak_design_electrical_loss_kW]', report)
        breakdown = function_source(UI, "buildPeakDemandBreakdown")
        self.assertIn("peak.peak_design_it_electrical_loss_kW", breakdown)
        self.assertIn("peak.peak_design_mep_electrical_loss_kW", breakdown)
        self.assertIn("peak.peak_design_electrical_loss_kW", breakdown)

    def test_acc_peak_loss_reconciliation_contract_is_preserved(self):
        breakdown = function_source(UI, "buildPeakDemandBreakdown")
        self.assertIn("Math.abs(designSum - designTotal) < 1e-6", breakdown)
        self.assertIn("peak.peak_design_facility_electrical_demand_kW", breakdown)

    def test_chw_basis_normalizes_legacy_wording_in_both_report_paths(self):
        display = function_source(UI, "chwPumpLoadRatioBasisDisplay")
        self.assertIn("Current Cooling Load per Active CHW Pump / Failure Peak Design Cooling Load per Active CHW Pump", display)
        self.assertIn("fixed single-pump reference capacity", display)
        report = function_source(UI, "buildHtmlReportFromSections")
        browser = function_source(UI, "renderEngineeringResultsSummary")
        self.assertIn("chwPumpLoadRatioBasisDisplay(pumpLoadRatioBasis)", report)
        self.assertIn("chwPumpLoadRatioBasisDisplay(", browser)

    def test_cw_pump_semantics_remain_distinct(self):
        report = function_source(UI, "buildHtmlReportFromSections")
        self.assertIn("Fixed Single-CW-Pump Reference Capacity", report)
        self.assertIn("Heat Rejection Load per Active CW Pump", report)

    def test_active_chw_pump_label_is_consistent(self):
        self.assertIn('"Active CHW Pump Count"', UI)
        self.assertNotIn('["Active Pump Count"', UI)

    def test_key_findings_engine_radiator_wording_tracks_applicability(self):
        report = function_source(UI, "buildHtmlReportFromSections")
        basis = function_source(UI, "reportKeyFindingsPueBasis")
        self.assertIn('["acc_gas_engine_cdu", "chiller_dry_cooler"].includes(topology)', basis)
        self.assertIn("engineApplicable", basis)
        self.assertIn(
            "modeled cooling, pumping, indoor equipment, engine radiator, and electrical distribution loads",
            basis,
        )
        self.assertIn(
            "modeled cooling, pumping, indoor equipment, and electrical distribution loads",
            basis,
        )
        self.assertIn("reportKeyFindingsPueBasis(solverTopology, engineApplicable)", report)
        self.assertIn("esc(keyFindingsPueBasis)", report)

    def test_redundant_chw_sentence_is_removed_but_canonical_formula_remains(self):
        report = function_source(UI, "buildHtmlReportFromSections")
        self.assertNotIn(
            "The CHW Pump load ratio is normalized using the configured cooling-unit rated design capacity as the reference capacity.",
            report,
        )
        self.assertIn(
            "CHW Pump Load Ratio = Current Cooling Load per Active CHW Pump / Failure Peak Design Cooling Load per Active CHW Pump.",
            report,
        )

    def test_acc_engineering_assumption_note_remains_available(self):
        self.assertIn("engineering assumption pending vendor confirmation", SOLVER)
        report = function_source(UI, "buildHtmlReportFromSections")
        self.assertIn("pumpDesignBasisLimitation", report)

    def test_reported_components_remain_topology_filtered(self):
        topology = function_source(UI, "topologyAwareAnnualEnergyBreakdown")
        acc_allowed = topology[topology.index('topology === "acc_gas_engine_cdu"'):topology.index('topology === "chiller_dry_cooler"')]
        chiller_allowed = topology[topology.index('topology === "chiller_dry_cooler"'):]
        self.assertIn("ENGINE_RADIATOR", acc_allowed)
        self.assertIn('engineApplicable ? ["ENGINE_RADIATOR"] : []', chiller_allowed)


if __name__ == "__main__":
    unittest.main()
