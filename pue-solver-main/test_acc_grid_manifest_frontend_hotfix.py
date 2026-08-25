import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "Configuration Library"
UI_PATH = Path(__file__).resolve().parent / "ui.js"


def function_source(source, name):
    match = re.search(rf"(?:async\s+)?function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", source)
    if not match:
        raise AssertionError(f"Function not found: {name}")
    depth = 0
    for index in range(match.end() - 1, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():index + 1]
    raise AssertionError(f"Function is not balanced: {name}")


class AccGridManifestFrontendHotfixTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = UI_PATH.read_text(encoding="utf-8")
        cls.grid_manifest = json.loads(
            (LIBRARY / "ACC_1.5MW_GRID_CDU" / "configuration_manifest.json").read_text(encoding="utf-8")
        )
        cls.gas_manifest = json.loads(
            (LIBRARY / "ACC_1.5MW_GASENGINE_CDU" / "configuration_manifest.json").read_text(encoding="utf-8")
        )

    def test_acc_grid_is_a_complete_manifest_only_configuration(self):
        grid_root = LIBRARY / "ACC_1.5MW_GRID_CDU"
        self.assertTrue((grid_root / "configuration_manifest.json").is_file())
        self.assertFalse((grid_root / "configuration.xlsx").exists())
        self.assertEqual(self.grid_manifest["power_source"], "Grid")
        self.assertEqual(self.grid_manifest["cooling_unit_capacity_mw"], 1.5)
        self.assertEqual([item["scenario"] for item in self.grid_manifest["scenarios"]], ["Normal", "Failure"])

    def test_load_mode_uses_manifest_completeness_before_legacy_dispatch_compatibility(self):
        block = function_source(self.ui, "configurationLibraryLoadMode")
        self.assertIn("manifest?.power_source", block)
        self.assertIn("manifest?.cooling_unit_capacity_mw", block)
        self.assertIn("manifest?.scenarios", block)
        self.assertIn('if (manifestOwnsConfiguration) return "manifest"', block)
        self.assertLess(
            block.index('if (manifestOwnsConfiguration) return "manifest"'),
            block.index('manifest?.solver_topology === "acc_gas_engine_cdu"'),
        )

    def test_manifest_branch_never_fetches_configuration_xlsx(self):
        load = function_source(self.ui, "loadSelectedConfigurationLibrary")
        legacy_start = load.index('if (loadMode === "legacy")')
        manifest_start = load.index("} else {", legacy_start)
        manifest_end = load.index("const sourceType", manifest_start)
        self.assertIn('fetchConfigurationWorkbook(`${base}/configuration.xlsx`)', load[legacy_start:manifest_start])
        self.assertNotIn("configuration.xlsx", load[manifest_start:manifest_end])
        self.assertIn("selectedManifest.scenarios", load[manifest_start:manifest_end])

    def test_pyodide_sync_skips_optional_legacy_files_but_keeps_equipment_strict(self):
        sync = function_source(self.ui, "syncConfigurationLibraryToPyodide")
        plan = function_source(self.ui, "buildConfigurationLibraryWorkbookSyncPlan")
        self.assertIn('const supportFiles = loadMode === "legacy"', sync)
        self.assertIn('?["configuration.xlsx", "scenario.xlsx", "input/IT_LOAD_90_PERCENT.xlsx"]'.replace("?", "? "), sync.replace("\n", " "))
        self.assertIn("required: true", plan)
        self.assertIn("throw new Error(`Could not sync Configuration Library workbook", sync)

    def test_grid_manifest_does_not_request_generation_workbooks(self):
        roles = self.grid_manifest["equipment_roles"]
        self.assertNotIn("engine", roles)
        self.assertNotIn("engine_radiator", roles)
        self.assertNotIn("ENGINE_3", json.dumps(self.grid_manifest))
        self.assertNotIn("ENGINE_RADIATOR_1", json.dumps(self.grid_manifest))

    def test_presentation_is_semantic_not_internal_dispatch_label(self):
        display = function_source(self.ui, "configurationTopologyDisplay")
        catalog = function_source(self.ui, "renderConfigurationLibraryCatalog")
        self.assertIn('if (topologyId === "acc_gas_engine_cdu") return "ACC"', display)
        self.assertIn("configurationTopologyDisplay(manifest)", catalog)
        self.assertNotIn("topology.display", catalog)
        self.assertEqual(self.grid_manifest["display_name"], "ACC 1.5 MW + Grid + CDU")
        self.assertIn("Gas Engine", self.gas_manifest["display_name"])
        self.assertEqual(self.grid_manifest["solver_topology"], self.gas_manifest["solver_topology"])

    def test_manifest_values_drive_frontend_power_source_and_capacity(self):
        power = function_source(self.ui, "manifestPowerSource")
        capacity = function_source(self.ui, "manifestCoolingUnitCapacityMw")
        self.assertIn("if (manifest?.power_source) return String(manifest.power_source)", power)
        self.assertIn("manifest?.cooling_unit_capacity_mw", capacity)
        self.assertIn("return declaredCapacityMw", capacity)


if __name__ == "__main__":
    unittest.main()
