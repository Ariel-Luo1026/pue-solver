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
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in "'\"`":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return UI[match.start():index + 1]
    raise AssertionError(f"Unclosed function: {name}")


class ClientReportSemanticCleanupTests(unittest.TestCase):
    def test_topology_aware_energy_and_performance_components(self):
        adapter = function_source("topologyAwareAnnualEnergyBreakdown")
        self.assertIn('"ACC", "CHW_PUMP", "CDU", "RTC", "MAU"', adapter)
        self.assertNotIn('"ACC", "CHILLER"', adapter)
        self.assertIn('"CHILLER", "DRY_COOLER", "CHW_PUMP", "CW_PUMP"', adapter)
        dispatch = function_source("dispatchReportProfile")
        self.assertLess(dispatch.index("topologyAwareAnnualEnergyBreakdown"), dispatch.index("buildEquipmentPerformance"))

    def test_acc_and_chiller_rows_are_mutually_exclusive(self):
        energy = function_source("annualEquipmentEnergyRows")
        peak = function_source("buildPeakDemandBreakdown")
        self.assertIn('["ACC", annual.annual_acc_energy_kWh]', energy)
        self.assertIn('["Chiller", annual.annual_chiller_energy_kWh]', energy)
        self.assertNotIn("annual_acc_energy_kWh || annual.annual_chiller_energy_kWh", energy)
        self.assertNotIn("ACC / Chiller Power", peak)
        self.assertIn("ACC Power", peak)
        self.assertIn("Chiller Power", peak)

    def test_customer_summary_terminology_and_weather_fallback(self):
        report = function_source("buildHtmlReportFromSections")
        for text in ("Cooling Technology", "Power Source", "System Architecture", "Weather Station", "Weather Data Source"):
            self.assertIn(text, report)
        self.assertIn("Project EPW Weather File", report)
        self.assertIn("toLocaleString", report)
        customer = report[report.index("<h2>1. Engineering Summary"):report.index("<h2>2. Energy")]
        self.assertNotIn("solverTopology)", customer)
        self.assertNotIn("report.profile_id", customer)

    def test_alignment_summary_and_diagnostics_are_both_preserved(self):
        report = function_source("buildHtmlReportFromSections")
        for text in ("Annual Data Alignment", "IT Load Sequence", "Weather Sequence", "IT / Weather Hourly Alignment"):
            self.assertIn(text, report)
        appendix = report[report.index("Appendix C — IT / Weather Alignment"):]
        for text in ("IT Load Time Basis", "Calendar Sequence Validation", "EPW Hour Convention", "First Row Alignment", "Full CSV Audit"):
            self.assertIn(text, appendix)

    def test_facility_total_and_peak_semantics(self):
        report = function_source("buildHtmlReportFromSections")
        self.assertIn("Annual Facility Energy Composition", report)
        self.assertIn("Total Facility Energy is the reconciled total", report)
        self.assertNotIn('["Facility Energy", annualEnergyBreakdown', report)
        self.assertIn("Annual Observed Peak Facility Demand", report)
        self.assertIn("Peak Design Facility Demand", report)

    def test_mep_boundary_and_export_hotfix_remain_protected(self):
        summary = function_source("annualFacilityEnergySummary")
        report = function_source("buildHtmlReportFromSections")
        export = function_source("exportHtmlReport")
        self.assertIn("Annual Cooling & MEP Terminal Energy", summary)
        self.assertIn("excludes IT energy and upstream electrical distribution losses", report)
        self.assertNotIn("annualFacilityEnergySummary(outObj)", report)
        for token in ("new Blob", "URL.createObjectURL", "link.click()", "URL.revokeObjectURL", "console.error"):
            self.assertIn(token, export)


if __name__ == "__main__":
    unittest.main()
