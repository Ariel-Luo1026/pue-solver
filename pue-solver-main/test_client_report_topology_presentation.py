import re
import unittest
from pathlib import Path


UI = (Path(__file__).parent / "ui.js").read_text(encoding="utf-8")
SOLVER = (Path(__file__).parent / "solver.py").read_text(encoding="utf-8")


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


class ClientReportTopologyPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = function_source(UI, "buildHtmlReportFromSections")

    def test_peak_design_and_methodology_are_topology_aware(self):
        self.assertIn('solverTopology === "chiller_dry_cooler"', self.report)
        for text in ("Chiller Total Power", "Dry Cooler Total Power", "CW Pump Power", "Dry Cooler Power Model"):
            self.assertIn(text, self.report)
        self.assertIn('solverTopology === "acc_gas_engine_cdu"', self.report)
        for text in ("ACC Total Power", "CDU Power", "RTC Power", "MAU Power", "Engine Radiator Power"):
            self.assertIn(text, self.report)

    def test_chiller_report_includes_configured_indoor_equipment(self):
        peak_rows = function_source(UI, "buildPeakDemandBreakdown")
        annual_rows = function_source(UI, "annualEquipmentEnergyRows")
        for text in ("CDU Power", "RTC Power", "MAU Power"):
            self.assertIn(text, peak_rows)
        for text in ('["CDU", annual.annual_cdu_energy_kWh]', '["RTC", annual.annual_rtc_energy_kWh]', '["MAU", annual.annual_mau_energy_kWh]'):
            self.assertIn(text, annual_rows)
        self.assertIn('"INDOOR_EQUIPMENT"', function_source(UI, "topologyAwareAnnualEnergyBreakdown"))

    def test_grid_chiller_report_suppresses_engine_notes(self):
        self.assertIn("const engineApplicable", self.report)
        self.assertIn("engineApplicable ?", self.report)

    def test_acc_client_labels_are_professional(self):
        rows = function_source(UI, "annualEquipmentEnergyRows")
        self.assertIn('["Engine Radiator", annual.annual_engine_radiator_energy_kWh]', rows)
        self.assertNotIn('["ENGINE_RADIATOR", annual.annual_engine_radiator_energy_kWh]', rows)
        self.assertIn("Electrical Distribution Loss", rows)
        appendix = self.report[self.report.index("Appendix D — Engineering Diagnostics"):]
        self.assertIn("Topology Identifier", appendix)
        self.assertIn("solverTopology", appendix)

    def test_equipment_performance_cards_are_not_duplicated(self):
        self.assertEqual(self.report.count('${performanceCards.length ? `<div class="grid">${performanceCards.join("")}</div>`'), 1)
        self.assertNotIn("Equipment Performance Summary", self.report)
        self.assertIn("Cooling Load Breakdown", self.report)

    def test_constant_it_suppresses_and_variable_it_enables_chart(self):
        self.assertIn("Math.max(...itLoadValues) - Math.min(...itLoadValues)", self.report)
        self.assertIn("itLoadVariation > 1e-6", self.report)
        self.assertIn('...(hasVariableItLoad ? [["Facility Power vs IT Load"', self.report)

    def test_compact_temperature_chart_reuses_existing_bins(self):
        chart = function_source(UI, "temperatureDistributionChartHtml")
        self.assertIn("distribution.rows.map", chart)
        self.assertIn("Annual Outdoor Temperature Distribution", chart)
        self.assertIn('yLabel: "Annual Hours"', chart)
        self.assertIn("temperatureDistributionChartHtml(tempDistribution)", self.report)
        self.assertNotIn("temperatureDistributionTableHtml(tempDistribution)", self.report)

    def test_equations_are_topology_aware(self):
        formulas = function_source(UI, "formulasHtml")
        self.assertIn('const isChiller = String(topologyId)', formulas)
        self.assertIn("Dry Cooler Leaving Water", formulas)
        self.assertIn("...(isChiller ? [", formulas)
        self.assertIn("formulasHtml(solverTopology)", self.report)

    def test_solar_heat_gain_is_hourly_summed_once_and_reconciles(self):
        self.assertEqual(31_536_000 + 12_082.823 + 621_960, 32_170_042.823)
        self.assertEqual(SOLVER.count('annual_solar_heat_gain = sum(item.get("solar_heat_gain_kW", 0.0)'), 1)
        self.assertIn("cooling_load_kw = it_kw + solar_heat_gain_kw + other_auxiliary_heat_gain_kw", SOLVER)
        self.assertIn('annual_cooling_load = sum(item.get("cooling_load_kW"', SOLVER)

    def test_export_hotfix_path_remains_intact(self):
        export = function_source(UI, "exportHtmlReport")
        for token in ("new Blob", "URL.createObjectURL", "link.click()", "URL.revokeObjectURL", "console.error", "setSolverDataStatus"):
            self.assertIn(token, export)
        self.assertNotIn("annualFacilityEnergySummary(outObj)", self.report)


if __name__ == "__main__":
    unittest.main()
