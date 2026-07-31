import json
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent
LIBRARY_ROOT = REPO_ROOT / "Configuration Library"


class ManifestFirstLoadingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = (PROJECT_DIR / "ui.js").read_text(encoding="utf-8")

    def _function_source(self, name):
        marker = f"function {name}"
        start = self.ui.index(marker)
        brace = self.ui.index("{", start)
        depth = 0
        for index in range(brace, len(self.ui)):
            char = self.ui[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return self.ui[start:index + 1]
        raise AssertionError(f"Could not extract {name}")

    def test_acc_legacy_configuration_loads(self):
        manifest = json.loads(
            (LIBRARY_ROOT / "ACC_1.5MW_GASENGINE_CDU" / "configuration_manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["solver_topology"], "acc_gas_engine_cdu")
        self.assertTrue((LIBRARY_ROOT / "ACC_1.5MW_GASENGINE_CDU" / "configuration.xlsx").is_file())
        self.assertIn('return manifest?.solver_topology === "acc_gas_engine_cdu" ? "legacy" : "manifest"', self.ui)

    def test_chiller_manifest_configuration_loads_without_legacy_workbook(self):
        config_root = LIBRARY_ROOT / "CHILLER_DRYCOOLER_2MW_GRID"
        manifest = json.loads((config_root / "configuration_manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["solver_topology"], "chiller_dry_cooler")
        self.assertTrue((config_root / "equipment" / "CENTRIFUGALCHILLER_1" / "CENTRIFUGALCHILLER_1.xlsx").is_file())
        self.assertFalse((config_root / "configuration.xlsx").exists())
        self.assertFalse((config_root / "scenario.xlsx").exists())

    def test_missing_configuration_xlsx_does_not_fail_when_manifest_exists(self):
        load_source = self._function_source("loadSelectedConfigurationLibrary")
        legacy_branch = load_source[
            load_source.index('if (loadMode === "legacy")'):
            load_source.index("const itLoad = {")
        ]
        manifest_branch = legacy_branch[legacy_branch.index("} else {"):]

        self.assertIn('fetchConfigurationWorkbook(`${base}/configuration.xlsx`)', legacy_branch)
        self.assertNotIn('fetchConfigurationWorkbook(`${base}/configuration.xlsx`)', manifest_branch)
        self.assertIn("equipmentEntries = await loadConfigurationEquipmentEntries(configurationName, selectedManifest)", manifest_branch)
        self.assertIn("defaultConfigurationLibraryItLoad(configurationName)", manifest_branch)

    def test_generic_payload_shape_is_preserved_after_loading(self):
        load_source = self._function_source("loadSelectedConfigurationLibrary")
        payload_source = self._function_source("buildGenericConfigurationLibraryPayload")

        for field in (
            "configuration_manifest",
            "configuration_name",
            "cooling_system_type",
            "cooling_unit_capacity_mw",
            "power_source",
            "it_load",
            "equipment",
            "selected_curves",
        ):
            self.assertIn(field, load_source)
        self.assertIn("configurationLibraryData.standardized_solver_input = buildFrontendSolverInputFromLibrary(configurationLibraryData)", load_source)
        self.assertIn("role_bindings", payload_source)
        self.assertIn("equipment_bindings", payload_source)

    def test_pyodide_sync_skips_legacy_support_files_for_manifest_mode(self):
        sync_source = self._function_source("syncConfigurationLibraryToPyodide")

        self.assertIn('const supportFiles = loadMode === "legacy"', sync_source)
        self.assertIn('"configuration.xlsx"', sync_source)
        self.assertIn('"scenario.xlsx"', sync_source)
        self.assertIn('"input/IT_LOAD_90_PERCENT.xlsx"', sync_source)


if __name__ == "__main__":
    unittest.main()
