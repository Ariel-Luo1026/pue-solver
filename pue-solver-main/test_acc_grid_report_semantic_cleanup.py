import re
import unittest
from pathlib import Path


UI = (Path(__file__).resolve().parent / "ui.js").read_text(encoding="utf-8")


def function_source(name):
    match = re.search(rf"(?:async\s+)?function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", UI)
    if not match:
        raise AssertionError(f"Function not found: {name}")
    depth = 0
    for index in range(match.end() - 1, len(UI)):
        if UI[index] == "{":
            depth += 1
        elif UI[index] == "}":
            depth -= 1
            if depth == 0:
                return UI[match.start():index + 1]
    raise AssertionError(f"Unbalanced function: {name}")


class AccGridReportSemanticCleanupTest(unittest.TestCase):
    def test_peak_breakdown_uses_generation_applicability_for_both_topologies(self):
        block = function_source("buildPeakDemandBreakdown")
        self.assertEqual(block.count("...(engineGenerationApplicable(outObj) ? [engineRadiatorRow] : [])"), 2)
        self.assertNotRegex(block, r"\n\s*engineRadiatorRow\s*\n")
        self.assertIn("annualReconciles", block)
        self.assertIn("designReconciles", block)

    def test_annual_rows_require_engine_applicability(self):
        block = function_source("annualEquipmentEnergyRows")
        self.assertIn("engineApplicable = false", block)
        self.assertEqual(block.count('...(engineApplicable ? [["Engine Radiator"'), 2)

    def test_ppue_uses_topology_aware_applicability(self):
        dispatch = function_source("dispatchReportProfile")
        breakdown = function_source("topologyAwareAnnualEnergyBreakdown")
        self.assertIn("topologyAwareAnnualEnergyBreakdown", dispatch)
        self.assertIn("engineGenerationApplicable(solverResult)", breakdown)
        self.assertIn('...(engineApplicable ? ["ENGINE_RADIATOR"] : [])', breakdown)
        self.assertIn("reconciles", function_source("pueContributionBreakdown"))

    def test_appendix_b_tables_and_charts_share_applicability_filter(self):
        report = function_source("buildHtmlReportFromSections")
        self.assertIn("report.equipment_curve_register.filter(curveApplicable)", report)
        self.assertIn("groupReportCurves(reportCurves.filter(curveApplicable))", report)
        self.assertIn('(engineApplicable || !["engine", "engine_radiator"].includes(family))', report)

    def test_grid_equipment_performance_omits_radiator_metrics(self):
        renderer = function_source("renderEngineeringResultsSummary")
        self.assertIn("const engineApplicable = engineGenerationApplicable", renderer)
        self.assertIn('...(engineApplicable ? [', renderer)
        self.assertIn("Maximum ENGINE_RADIATOR Load Ratio", renderer)

    def test_generation_reference_remains_applicability_driven(self):
        report = function_source("buildHtmlReportFromSections")
        self.assertIn("Number(annual.annual_engine_output_kWh) > 0", report)
        self.assertIn("Generation-Side Reference", report)

    def test_appendix_d_separates_physical_and_internal_identifiers(self):
        report = function_source("buildHtmlReportFromSections")
        appendix = report[report.index("Appendix D — Engineering Diagnostics"):]
        self.assertIn('["Cooling Topology", esc(coolingTechnology)]', appendix)
        self.assertIn('["Power Source", esc(powerSource)]', appendix)
        self.assertIn('["Internal Dispatch Identifier", esc(solverTopology)]', appendix)
        self.assertIn('["Internal Report Profile", esc(report.profile_id', appendix)
        self.assertNotIn('["Topology Identifier"', appendix)
        self.assertNotIn('["Report Profile"', appendix)

    def test_grid_veto_precedes_legacy_acc_dispatch_identifier(self):
        applicability = function_source("engineGenerationApplicable")
        self.assertLess(
            applicability.index("if (/^grid$/i.test"),
            applicability.index("engineConfigured"),
        )
        self.assertNotIn("acc_gas_engine_cdu", applicability)

    def test_gas_engine_reporting_remains_applicable(self):
        applicability = function_source("engineGenerationApplicable")
        self.assertIn("/gas\\s*engine/i.test", applicability)
        report = function_source("buildHtmlReportFromSections")
        self.assertIn('engineApplicable ? [["Engine Radiator Power, kW"', report)
        self.assertIn('engineApplicable ? "Gas Engine" : "Grid"', report)


if __name__ == "__main__":
    unittest.main()
