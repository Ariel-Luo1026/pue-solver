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


class ChillerReportSemanticCleanupTest(unittest.TestCase):
    def test_browser_design_it_capacity_uses_canonical_peak_result_fallback(self):
        context = function_source("engineeringContextRows")
        self.assertIn("peak.peak_design_it_load_kW", context)
        self.assertIn('fmtNumber(designItKw / 1000, 3)', context)

    def test_curve_type_model_basis_mapping_is_engineering_accurate(self):
        basis = function_source("equipmentModelBasis")
        expected = {
            "cop_curve": "Hourly temperature and load lookup",
            "outdoor_temperature_power": "Hourly outdoor-temperature power lookup",
            "load_ratio_engine_output": "Hourly load-ratio engine-output lookup",
            "load_ratio_power": "Hourly load-ratio power lookup",
            "electrical_path_efficiency": "Hourly electrical-path efficiency lookup",
        }
        for curve_type, wording in expected.items():
            self.assertIn(curve_type, basis)
            self.assertIn(wording, basis)
        register = function_source("buildEquipmentCurveRegister")
        self.assertIn("equipmentModelBasis(curveType, variables", register)

    def test_engine_model_basis_is_curve_type_driven(self):
        basis = function_source("equipmentModelBasis")
        self.assertIn(
            'load_ratio_engine_output: "Hourly load-ratio engine-output lookup"',
            basis,
        )
        self.assertNotIn("ENGINE_3", basis)
        self.assertIn('load_ratio_power: "Hourly load-ratio power lookup"', basis)

    def test_key_findings_wording_is_topology_and_engine_applicability_aware(self):
        basis = function_source("reportKeyFindingsPueBasis")
        self.assertIn('topology === "acc_gas_engine_cdu"', basis)
        self.assertIn('topology === "chiller_dry_cooler" && engineApplicable', basis)
        self.assertIn(
            "modeled cooling, pumping, indoor equipment, engine radiator, and electrical distribution loads",
            basis,
        )
        self.assertIn(
            "modeled cooling, pumping, indoor equipment, and electrical distribution loads",
            basis,
        )
        report = function_source("buildHtmlReportFromSections")
        self.assertIn("reportKeyFindingsPueBasis(solverTopology, engineApplicable)", report)

    def test_chw_cw_and_indoor_equipment_share_load_ratio_basis(self):
        basis = function_source("equipmentModelBasis")
        self.assertIn('load_ratio_power: "Hourly load-ratio power lookup"', basis)
        for equipment in ("CHW_PUMP", "CW_PUMP", "CDU", "RTC", "MAU"):
            self.assertRegex(UI, rf'{equipment}[^\n]*')

    def test_chiller_runtime_methodology_has_no_active_affinity_equation(self):
        formulas = function_source("formulasHtml")
        self.assertNotIn('"Affinity Law"', formulas)
        self.assertNotIn("P</i><sub>variable</sub>", formulas)
        report = function_source("buildHtmlReportFromSections")
        self.assertIn("not applied as a second runtime power calculation", report)

    def test_legacy_future_equipment_wording_is_absent(self):
        self.assertNotIn("future equipment", UI.lower())
        basis = function_source("reportKeyFindingsPueBasis")
        self.assertIn("modeled cooling, pumping, indoor equipment, and electrical distribution loads", basis)

    def test_facility_power_boundary_is_preserved(self):
        formulas = function_source("formulasHtml")
        for token in ("chiller,h", "drycooler,h", "CHW pump,h", "CW pump,h", "indoor,h", "aux,h", "elec,loss,h"):
            self.assertIn(token, formulas)
        for token in ("CDU,h", "RTC,h", "MAU,h"):
            self.assertEqual(formulas.count(token), 1)
        self.assertIn("included in the MEP terminal load before electrical-distribution loss", formulas)

    def test_facility_power_formula_shows_only_applicable_engine_radiator(self):
        formulas = function_source("formulasHtml")
        self.assertIn("isChiller && engineApplicable", formulas)
        self.assertIn("engine radiator,h", formulas)
        self.assertNotIn("engine output", formulas.lower())
        self.assertNotIn("configuration_id", formulas)
        self.assertIn("radiator,h", formulas)  # Existing ACC Gas Engine equation.
        report = function_source("buildHtmlReportFromSections")
        self.assertIn("formulasHtml(solverTopology, engineApplicable)", report)


if __name__ == "__main__":
    unittest.main()
