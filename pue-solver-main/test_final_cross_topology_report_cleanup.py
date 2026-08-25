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


class FinalCrossTopologyReportCleanupTest(unittest.TestCase):
    def test_acc_peak_design_exposes_canonical_heat_gain_fields(self):
        self.assertIn('"peak_design_solar_heat_gain_kW": peak_design_hour.get("solar_heat_gain_kW")', SOLVER)
        self.assertIn('"peak_design_other_auxiliary_heat_gain_kW": peak_design_hour.get("other_auxiliary_heat_gain_kW")', SOLVER)
        self.assertIn('peak.peak_design_solar_heat_gain_kW', UI)
        self.assertIn('peak.peak_design_other_auxiliary_heat_gain_kW', UI)

    def test_peak_cooling_load_uses_existing_solver_result_without_report_recalculation(self):
        report = function_source(UI, "buildHtmlReportFromSections")
        self.assertIn('peak.peak_design_cooling_load_kW', report)
        self.assertNotIn('peak_design_it_load_kW +', report)

    def test_standard_acc_breakdown_merges_existing_engine_radiator_energy(self):
        breakdown = function_source(UI, "buildAnnualEnergyBreakdown")
        self.assertIn("annual.annual_engine_radiator_energy_kWh", breakdown)
        self.assertIn("components.ENGINE_RADIATOR", breakdown)
        self.assertIn('sources: ["annual_results"]', breakdown)

    def test_acc_ppue_reconciliation_uses_component_energy_over_it_energy(self):
        contribution = function_source(UI, "pueContributionBreakdown")
        self.assertIn("Number(data?.energy_kWh)", contribution)
        self.assertIn("/ annualItEnergy", contribution)
        self.assertIn("listedTotal", contribution)
        self.assertIn("Math.abs(listedTotal - annualPue) <= 0.0015", contribution)
        report = function_source(UI, "buildHtmlReportFromSections")
        self.assertIn("Listed pPUE reconciliation", report)

    def test_topology_filter_keeps_radiator_for_gas_engine_applicability(self):
        topology = function_source(UI, "topologyAwareAnnualEnergyBreakdown")
        acc_allowed = topology[topology.index('topology === "acc_gas_engine_cdu"'):topology.index('topology === "chiller_dry_cooler"')]
        chiller_allowed = topology[topology.index('topology === "chiller_dry_cooler"'):]
        self.assertIn("ENGINE_RADIATOR", acc_allowed)
        self.assertIn('engineApplicable ? ["ENGINE_RADIATOR"] : []', chiller_allowed)

    def test_chw_wording_and_diagnostic_label_are_topology_neutral(self):
        report = function_source(UI, "buildHtmlReportFromSections")
        self.assertIn("CHW Pump Load Ratio = Cooling Load per Active Unit / Cooling Unit Rated Design Capacity", report)
        self.assertNotIn("The CHW Pump load ratio is normalized using the configured cooling-unit rated design capacity", report)
        self.assertNotIn("ACC performance-envelope maximum", report)
        self.assertIn('"Active CHW Pump Count"', report)
        self.assertNotIn('["Active Pump Count"', report)

    def test_existing_good_cross_topology_features_remain(self):
        self.assertIn("yMin: 1.00", UI)
        self.assertIn("equipmentModelBasis(curveType", UI)
        self.assertIn("engineGenerationApplicable", UI)
        rows = function_source(UI, "annualEquipmentEnergyRows")
        for label in ("Chiller", "Dry Cooler", "CW Pump", "CDU", "RTC", "MAU", "Engine Radiator"):
            self.assertIn(label, rows)


if __name__ == "__main__":
    unittest.main()
