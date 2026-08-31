import math
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent
UI_SOURCE = (ROOT / "ui.js").read_text(encoding="utf-8")


def function_source(name, next_name):
    start = UI_SOURCE.index(f"function {name}")
    end = UI_SOURCE.index(f"function {next_name}", start)
    return UI_SOURCE[start:end]


class Phase23RGenerationSidePresentationCleanupTests(unittest.TestCase):
    def test_total_engine_radiator_labels_are_human_readable(self):
        self.assertIn("Maximum Total Engine Radiator Fan Power", UI_SOURCE)
        self.assertIn("Annual Total Engine Radiator Fan Energy", UI_SOURCE)
        self.assertNotIn("Maximum ENGINE_RADIATOR Fan Power", UI_SOURCE)
        self.assertNotIn("Annual ENGINE_RADIATOR Fan Energy", UI_SOURCE)

    def test_ppue_panel_contains_every_facility_energy_category(self):
        panel = function_source("renderPueContributionSummaryPanel", "mwTextFromKw")
        for label in (
            "Total Non-IT pPUE",
            "Largest PUE Driver",
            "Primary Cooling Equipment Share of Non-IT Overhead",
        ):
            self.assertIn(label, panel)
        builder = function_source("buildPueContributionSummary", "enginePresentationIdentity")
        for label in (
            "Cooling Equipment",
            "Indoor Equipment",
            "Engine Radiator",
            "Electrical Distribution Loss",
            "Other Electrical Auxiliary",
        ):
            self.assertIn(label, builder)

    def test_gas_normal_baseline_ppue_reconciles_to_annual_pue(self):
        it_energy = 31_536_000.0
        categories = {
            "Cooling Equipment": 3_073_722.68148376 + 326_890.1072334989,
            "Indoor Equipment": 563_268.0 + 270_246.0 + 87_600.0,
            "Engine Radiator": 656_633.1531809819,
            "Electrical Distribution Loss": 918_929.1232417392,
            "Other Electrical Auxiliary": 0.0,
        }
        ppue = {label: value / it_energy for label, value in categories.items()}
        annual_pue = 1.1870018095237183
        self.assertTrue(math.isclose(1.0 + sum(ppue.values()), annual_pue, rel_tol=0, abs_tol=1e-12))
        self.assertEqual(max(ppue, key=ppue.get), "Cooling Equipment")
        self.assertTrue(math.isclose(sum(value / sum(ppue.values()) for value in ppue.values()), 1.0, abs_tol=1e-12))

    def test_grid_breakdown_hides_zero_engine_radiator(self):
        builder = function_source("buildPueContributionSummary", "enginePresentationIdentity")
        self.assertIn("...(radiatorEnergy > 0 ?", builder)
        self.assertIn("annual_engine_radiator_energy_kWh", builder)

    def test_generation_reference_is_excluded_from_facility_contributions(self):
        builder = function_source("buildPueContributionSummary", "enginePresentationIdentity")
        for excluded in ("annual_engine_output_kWh", "annual_engine_fuel_input_kWh", "annual_engine_waste_heat_kWh"):
            self.assertNotIn(excluded, builder)

    def test_source_and_runtime_engine_identities_are_presented(self):
        self.assertIn('["Engine Model", engineIdentity.sourceId]', UI_SOURCE)
        self.assertIn('["Runtime Canonical ID", engineIdentity.runtimeId]', UI_SOURCE)
        identity = function_source("enginePresentationIdentity", "signedPpueText")
        self.assertIn("source_workbook_equipment_id", identity)
        self.assertIn('"ENGINE_2"', identity)
        self.assertIn('"ENGINE_3"', identity)

    def test_generation_boundary_wording_is_generic_and_explicit(self):
        wording = "Engine generation-side reference quantities are excluded from Facility Demand and PUE electrical consumption."
        self.assertIn(wording, UI_SOURCE)
        self.assertNotIn("ENGINE_3 is generation-side equipment", UI_SOURCE)

    def test_phase23r_a1_calculation_principle_wording_remains_intact(self):
        self.assertIn('const calculationCoolingSystem = String(topologyId).toLowerCase() === "acc_gas_engine_cdu"', UI_SOURCE)
        self.assertIn('? "ACC + CDU"', UI_SOURCE)
        self.assertIn("Power Source: ${esc(calculationPowerSource)}", UI_SOURCE)


if __name__ == "__main__":
    unittest.main()
