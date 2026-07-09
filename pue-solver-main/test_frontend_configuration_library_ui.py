import re
import unittest
from pathlib import Path


class FrontendConfigurationLibraryUITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent
        cls.index = (root / "index.html").read_text(encoding="utf-8")
        cls.ui = (root / "ui.js").read_text(encoding="utf-8")

    def test_manual_redundancy_controls_exist(self):
        for text in (
            "Unit Quantity / Redundancy",
            "Quantity Mode",
            "Redundancy",
            "Installed Units",
            "Running Units",
            "Standby Units",
            'id="unitQuantityMode"',
            'id="unitRedundancyMode"',
            'id="manualInstalledUnits"',
            'id="manualRunningUnits"',
            'id="manualStandbyUnits"',
        ):
            self.assertIn(text, self.index)

    def test_unit_quantity_maps_to_project_input(self):
        self.assertIn("function getUnitQuantitySelection", self.ui)
        self.assertIn('mode: "manual"', self.ui)
        self.assertIn('redundancy === "N+1"', self.ui)
        self.assertIn('redundancy === "N+2"', self.ui)
        self.assertIn("unit_quantity: unitQuantity", self.ui)
        self.assertIn("running_units: activeUnits", self.ui)
        self.assertIn("standby_units: standbyUnits", self.ui)

    def test_auto_mode_remains_default(self):
        self.assertIn('<option value="auto" selected>Auto</option>', self.index)
        self.assertIn('mode: "auto"', self.ui)
        self.assertIn("calculateFrontendUnitRequirements", self.ui)

    def test_configuration_library_binding_uses_current_equipment_ids(self):
        expected_ids = (
            "ACC_2",
            "CHW_PUMP_2",
            "CDU_2",
            "RTC_1&2",
            "MAU_1&2",
            "ELECTRICAL_DISTRIBUTION_2",
            "ENGINE_3",
            "ENGINE_RADIATOR_1",
        )
        direct_block = self.ui[
            self.ui.index("const DIRECT_MODE_EQUIPMENT_ORDER"):
            self.ui.index("const DIRECT_MODE_EQUIPMENT_CANDIDATES")
        ]
        for equipment_id in expected_ids:
            self.assertIn(equipment_id, direct_block)
        binding_block = self._function_source("renderConfigurationLibrarySummary")
        self.assertIn("DIRECT_MODE_EQUIPMENT_ORDER.map", binding_block)
        self.assertIn("Using Configuration Library Solver_Curve", binding_block)
        self.assertIn("Missing Solver_Curve", binding_block)

    def test_configuration_library_binding_resolves_legacy_aliases(self):
        alias_block = self.ui[
            self.ui.index("const DEFAULT_DIRECT_MODE_EQUIPMENT_ALIASES"):
            self.ui.index("function libraryCurveForEquipment")
        ]
        for text in (
            'RTC_1: "RTC_1&2"',
            'RTC_2: "RTC_1&2"',
            'MAU_1: "MAU_1&2"',
            'MAU_2: "MAU_1&2"',
            'ENGINE_2: "ENGINE_3"',
            'ENGINE_RADIATOR_2: "ENGINE_RADIATOR_1"',
            '"RTC_1&2": ["RTC_1&2", "RTC_2", "rtc", "auxiliary_load"]',
            '"MAU_1&2": ["MAU_1&2", "MAU_2", "mau", "terminal_fan"]',
            'ENGINE_3: ["ENGINE_3", "ENGINE_2", "engine", "generator", "gas_engine"]',
            'ENGINE_RADIATOR_1: ["ENGINE_RADIATOR_1", "ENGINE_RADIATOR_2", "engine_radiator", "radiator", "heat_exchanger"]',
        ):
            self.assertIn(text, alias_block)
        binding_block = self._function_source("renderConfigurationLibrarySummary")
        self.assertIn("findLibraryEquipmentPackage(data, equipmentId)", binding_block)
        self.assertIn("${esc(resolved.resolvedId)}", binding_block)
        self.assertIn("Missing Workbook", binding_block)
        self.assertIn("librarySelectedCurveType(selected)", binding_block)
        self.assertIn("displayCurveType(solverCurveType)", binding_block)
        self.assertIn("<th>Curve Type</th>", binding_block)
        self.assertIn("Not evaluated", binding_block)
        self.assertIn("Unknown", binding_block)
        self.assertIn("function resolveFrontendEquipmentId", alias_block)
        self.assertIn("let directModeEquipmentAliases = { ...DEFAULT_DIRECT_MODE_EQUIPMENT_ALIASES }", alias_block)

    def test_configuration_library_aliases_load_shared_json_with_fallback(self):
        alias_block = self._function_source("loadConfigurationEquipmentAliases")
        self.assertIn('new URL("Configuration Library/equipment_aliases.json", document.baseURI)', alias_block)
        self.assertIn("directModeEquipmentAliases = { ...DEFAULT_DIRECT_MODE_EQUIPMENT_ALIASES, ...loaded }", alias_block)
        self.assertIn("directModeEquipmentAliases = { ...DEFAULT_DIRECT_MODE_EQUIPMENT_ALIASES }", alias_block)
        self.assertIn('fetch(aliasUrl, { cache: "no-store" })', alias_block)

    def test_pyodide_is_lazy_loaded_after_startup(self):
        init_block = self._function_source("init")
        self.assertNotIn("loadPyodide()", init_block)
        self.assertNotIn("runPythonAsync", init_block)
        self.assertIn("Calculation engine will load when you click Run", init_block)
        self.assertIn("btnRun.disabled = false", init_block)

        ensure_block = self._function_source("ensurePyodideReady")
        self.assertIn("if (pyodide && window.pyodideReady) return pyodide", ensure_block)
        self.assertIn("if (pyodideReadyPromise) return pyodideReadyPromise", ensure_block)
        self.assertIn("pyodideReadyPromise = (async () =>", ensure_block)
        self.assertIn("pyodide = await loadPyodide()", ensure_block)
        self.assertIn("for (const moduleName of DIRECT_MODE_PYTHON_MODULES)", ensure_block)
        self.assertIn('console.time("loadPyodide")', ensure_block)
        self.assertIn('console.time("fetch/write module loop")', ensure_block)
        self.assertIn('console.time("solver.py runPythonAsync")', ensure_block)
        self.assertIn('console.time("benchmark runPythonAsync")', ensure_block)
        self.assertIn("window.pyodideReady = true", ensure_block)

    def test_run_paths_await_lazy_pyodide_engine(self):
        run_block = self._function_source("run")
        self.assertIn("if (runInProgress) return", run_block)
        self.assertIn("setRunButtonsDisabled(true)", run_block)
        self.assertIn("await ensurePyodideReady()", run_block)
        self.assertLess(run_block.index("await ensurePyodideReady()"), run_block.index("pyodide.globals.set"))
        self.assertIn("setRunButtonsDisabled(false)", run_block)

        library_run_block = self._function_source("runUsingConfigurationLibrary")
        self.assertIn("await ensurePyodideReady()", library_run_block)
        self.assertLess(
            library_run_block.index("await ensurePyodideReady()"),
            library_run_block.index("syncConfigurationLibraryToPyodide(configurationLibraryData)"),
        )

    def test_configuration_library_loader_fetches_canonical_workbook_before_raw_alias(self):
        fetch_block = self._function_source("fetchResolvedConfigurationEquipmentWorkbook")
        self.assertIn("const resolvedId = resolveFrontendEquipmentId(rawEquipmentId)", fetch_block)
        self.assertIn("const candidateIds = [resolvedId, rawEquipmentId]", fetch_block)
        candidate_block = fetch_block[fetch_block.index("const candidateIds"):fetch_block.index("const errors")]
        self.assertLess(candidate_block.index("resolvedId"), candidate_block.index("rawEquipmentId"))
        self.assertIn("const packagePath = `equipment/${candidateId}/${candidateId}.xlsx`", fetch_block)
        self.assertIn("sheets: await fetchConfigurationWorkbook(`${configurationBase}/${packagePath}`)", fetch_block)

        loader_block = self._function_source("loadSelectedConfigurationLibrary")
        self.assertIn("await loadConfigurationEquipmentAliases()", loader_block)
        self.assertIn("const resolvedId = resolveFrontendEquipmentId(equipmentId)", loader_block)
        self.assertIn("fetchResolvedConfigurationEquipmentWorkbook(base, equipmentId)", loader_block)
        self.assertIn("return [fetched.resolvedId", loader_block)
        self.assertIn("equipment_id: fetched.resolvedId", loader_block)
        self.assertIn("source_equipment_id: fetched.rawEquipmentId", loader_block)
        self.assertIn("source_workbook_equipment_id: fetched.sourceEquipmentId", loader_block)
        self.assertIn("solver_curves: Object.fromEntries(curveNames.map(name => [name, sheets[name]]))", loader_block)
        self.assertNotIn("fetchConfigurationWorkbook(`${base}/${packagePath}`)", loader_block)

    def test_configuration_library_run_input_uses_canonical_auxiliary_ids(self):
        builder_block = self._function_source("buildFrontendSolverInputFromLibrary")
        self.assertIn('["CDU_2", "RTC_1&2", "MAU_1&2"].map', builder_block)
        self.assertIn("equipment_id: resolved.resolvedId", builder_block)
        adapter_block = self._function_source("convertFrontendLibraryInputToSolverInput")
        self.assertIn("library_fixed_power: clone(libraryInput.equipment.auxiliary)", adapter_block)
        self.assertIn("auxiliary_equipment: clone(libraryInput.equipment.auxiliary)", adapter_block)

    def test_configuration_library_aliases_do_not_warn_as_tentative(self):
        diagnostics_block = self.ui[
            self.ui.index("function tentativeFrameworkMapping"):
            self.ui.index("function buildFrameworkDiagnosticsPreview")
        ]
        self.assertIn("isDirectModeResolvedAlias(equipmentFolder, equipmentId)", diagnostics_block)

    def test_result_cards_use_not_available_placeholder(self):
        summary_block = self._function_source("renderConfigurationLibrarySummary")
        self.assertIn("Not available", summary_block)
        self.assertNotIn("Waiting for Solver", summary_block)
        for text in (
            "firstAvailableResultField",
            "sumAvailableResultFields",
            "maxHourlyResultField",
            "annual_chw_pump_energy_kWh",
            "annual_ACC_energy_kWh",
            "annual_engine_energy_kWh",
            "engine_radiator_power_kW",
        ):
            self.assertIn(text, summary_block)

    def test_configuration_library_direct_input_carries_configuration_path(self):
        builder_block = self._function_source("buildFrontendSolverInputFromLibrary")
        self.assertIn("configuration_path: data.configuration_path || data.configuration_name", builder_block)
        adapter_block = self._function_source("convertFrontendLibraryInputToSolverInput")
        self.assertIn("configuration_path: libraryInput.configuration_path || libraryInput.configuration_name", adapter_block)
        self.assertIn("configuration_name: libraryInput.configuration_name", adapter_block)

    def test_cooling_load_heat_gain_inputs_feed_configuration_library_solver_input(self):
        for text in (
            'id="solarHeatGainMaxKw"',
            'id="solarDaytimeStartHour"',
            'id="solarDaytimeEndHour"',
            'id="otherAuxiliaryHeatGainKw"',
            "Solar heat gain is included in Total Cooling Load.",
        ):
            self.assertIn(text, self.index)
        for legacy in ("solarGainAnnualKwh", "solarGainPeakKw", "Report-only Solar Heat Gain"):
            self.assertNotIn(legacy, self.index)

        builder_block = self._function_source("buildFrontendSolverInputFromLibrary")
        self.assertIn("const heatGains = getCoolingLoadHeatGainInput()", builder_block)
        self.assertIn("solar_heat_gain_max_kW: heatGains.solarHeatGainMaxKw", builder_block)
        self.assertIn("other_auxiliary_heat_gain_kW: heatGains.otherAuxiliaryHeatGainKw", builder_block)

        adapter_block = self._function_source("convertFrontendLibraryInputToSolverInput")
        self.assertIn("solar_heat_gain_max_kW: libraryInput.heat_gains?.solar_heat_gain_max_kW ?? 0", adapter_block)
        self.assertIn("other_auxiliary_heat_gain_kW: libraryInput.heat_gains?.other_auxiliary_heat_gain_kW ?? 0", adapter_block)

    def test_configuration_library_workbooks_sync_to_pyodide_as_binary_files(self):
        self.assertIn('const CONFIGURATION_LIBRARY_PYODIDE_ROOT = "Configuration Library"', self.ui)
        for function_name in (
            "ensurePyodideDir",
            "writeBinaryFileToPyodide",
            "fetchConfigurationLibraryArrayBuffer",
            "syncConfigurationLibraryToPyodide",
        ):
            self.assertIn(f"function {function_name}", self.ui)
        write_block = self._function_source("writeBinaryFileToPyodide")
        self.assertIn("ensurePyodideDir(directory)", write_block)
        self.assertIn("new Uint8Array(arrayBuffer)", write_block)
        self.assertIn("pyodide.FS.writeFile(path", write_block)
        sync_block = self._function_source("syncConfigurationLibraryToPyodide")
        self.assertIn('["configuration.xlsx", "scenario.xlsx", "input/IT_LOAD_90_PERCENT.xlsx"]', sync_block)
        self.assertIn("buildConfigurationLibraryWorkbookSyncPlan(selectedConfiguration)", sync_block)
        self.assertIn("verifyConfigurationLibrarySynced(configurationPath)", sync_block)
        self.assertIn("workbook_paths: workbookPaths", sync_block)

    def test_configuration_library_sync_plan_uses_direct_mode_equipment_paths(self):
        plan_block = self._function_source("buildConfigurationLibraryWorkbookSyncPlan")
        self.assertIn("DIRECT_MODE_EQUIPMENT_ORDER.map", plan_block)
        self.assertIn("findLibraryEquipmentPackage(data, equipmentId)", plan_block)
        self.assertIn("sourceRelativePaths", plan_block)
        self.assertIn("pyodideRelativePath", plan_block)
        self.assertIn("resolved.resolvedId", plan_block)
        self.assertIn("DIRECT_MODE_EQUIPMENT_ORDER.includes(resolvedId)", plan_block)
        for equipment_id in (
            "ACC_2",
            "CHW_PUMP_2",
            "CDU_2",
            "RTC_1&2",
            "MAU_1&2",
            "ELECTRICAL_DISTRIBUTION_2",
            "ENGINE_3",
            "ENGINE_RADIATOR_1",
        ):
            self.assertIn(equipment_id, self.ui[self.ui.index("const DIRECT_MODE_EQUIPMENT_ORDER"):self.ui.index("const DIRECT_MODE_WHITE_SPACE_EQUIPMENT")])

    def test_configuration_library_sync_fetches_canonical_ids_before_aliases(self):
        plan_block = self._function_source("buildConfigurationLibraryWorkbookSyncPlan")
        self.assertIn("const sourceIds = [resolved.resolvedId, ...aliases, resolved.equipmentPackage?.equipment_id, resolved.packageKey]", plan_block)
        self.assertIn("item.sourceRelativePaths = item.sourceIds.map(sourceId => `${configurationName}/equipment/${sourceId}/${sourceId}.xlsx`)", plan_block)
        alias_block = self.ui[
            self.ui.index("const DIRECT_MODE_EQUIPMENT_CANDIDATES"):
            self.ui.index("function resolveDirectModeEquipmentId")
        ]
        for canonical, legacy in (
            ('"RTC_1&2"', '"RTC_2"'),
            ('"MAU_1&2"', '"MAU_2"'),
            ("ENGINE_3", '"ENGINE_2"'),
            ("ENGINE_RADIATOR_1", '"ENGINE_RADIATOR_2"'),
        ):
            self.assertLess(alias_block.index(canonical), alias_block.index(legacy))
        sync_block = self._function_source("syncConfigurationLibraryToPyodide")
        self.assertIn("fetchFirstConfigurationLibraryWorkbook(item.sourceRelativePaths)", sync_block)
        self.assertIn("const pyodidePath = `${configurationPath}/${item.pyodideRelativePath}`", sync_block)
        self.assertIn("writeBinaryFileToPyodide(pyodidePath, fetched.arrayBuffer)", sync_block)

    def test_configuration_library_direct_sync_has_no_legacy_only_fetch_path(self):
        plan_block = self._function_source("buildConfigurationLibraryWorkbookSyncPlan")
        for legacy_path in (
            "equipment/RTC_2/RTC_2.xlsx",
            "equipment/MAU_2/MAU_2.xlsx",
            "equipment/ENGINE_2/ENGINE_2.xlsx",
            "equipment/ENGINE_RADIATOR_2/ENGINE_RADIATOR_2.xlsx",
        ):
            self.assertNotIn(legacy_path, plan_block)

    def test_configuration_library_run_syncs_before_solver_and_uses_pyodide_path(self):
        run_block = self._function_source("runUsingConfigurationLibrary")
        self.assertLess(run_block.index("await syncConfigurationLibraryToPyodide(configurationLibraryData)"), run_block.index("convertFrontendLibraryInputToSolverInput(libraryInput)"))
        self.assertIn("configurationLibraryData.configuration_path = syncResult.configuration_path", run_block)
        self.assertIn("libraryInput.configuration_path = syncResult.configuration_path", run_block)
        self.assertIn("applyAccCalculationEngineSelection(adaptedInput, calculationMode, libraryInput.configuration_path)", run_block)
        self.assertIn("Configuration Library synced:", run_block)
        self.assertIn("workbooks=${syncResult.workbook_paths.length}", run_block)
        self.assertIn("Configuration Library workbook sync failed", run_block)
        guard_block = self._function_source("verifyConfigurationLibrarySynced")
        self.assertIn("Configuration Library workbooks were not synced into Pyodide runtime. Please reload the Configuration Library.", guard_block)

    def test_required_performance_curves_use_direct_mode_ids(self):
        render_block = self._function_source("renderCoolingSystemSelection")
        self.assertIn("FRAMEWORK_DIAGNOSTIC_TOPOLOGIES.ACC.performance_requirements", render_block)
        self.assertIn("DIRECT_MODE_WHITE_SPACE_EQUIPMENT", render_block)
        self.assertIn("DIRECT_MODE_GRAY_SPACE_EQUIPMENT", render_block)
        diagnostics_block = self.ui[
            self.ui.index("const FRAMEWORK_DIAGNOSTIC_TOPOLOGIES"):
            self.ui.index("const DEFAULT_COOLING_SYSTEM_TYPE")
        ]
        for required in (
            "ACC_2 Solver_Curve",
            "CHW_PUMP_2 Solver_Curve",
            "CDU_2 Solver_Curve",
            "RTC_1&2 Solver_Curve",
            "MAU_1&2 Solver_Curve",
            "ELECTRICAL_DISTRIBUTION_2 Solver_Curve",
            "ENGINE_3 Solver_Curve",
            "ENGINE_RADIATOR_1 Solver_Curve",
        ):
            self.assertIn(required, diagnostics_block)
        for forbidden in ("RTC 1", "RTC 2", "MAU 1", "MAU 2"):
            self.assertNotIn(forbidden, render_block)

    def test_scenario_summary_hidden_in_direct_mode(self):
        self.assertIn('id="scenarioSummaryPanel"', self.index)
        summary_block = self._function_source("renderScenarioSummary")
        self.assertIn("isConfigurationLibraryDirectModeActive()", summary_block)
        self.assertIn('panel.style.display = "none"', summary_block)

    def test_framework_diagnostics_use_direct_mode_labels(self):
        diagnostics_block = self.ui[
            self.ui.index("const FRAMEWORK_DIAGNOSTIC_TOPOLOGIES"):
            self.ui.index("const DEFAULT_COOLING_SYSTEM_TYPE")
        ]
        for required in (
            "ACC_2 Solver_Curve",
            "CHW_PUMP_2 Solver_Curve",
            "MAU_1&2 Solver_Curve",
            "RTC_1&2 Solver_Curve",
            "CDU_2 Solver_Curve",
            "ELECTRICAL_DISTRIBUTION_2 Solver_Curve",
            "ENGINE_3 Solver_Curve",
            "ENGINE_RADIATOR_1 Solver_Curve",
        ):
            self.assertIn(required, diagnostics_block)
        for legacy in ("terminal_fan", "auxiliary_load", "heat_exchanger", "pump_power_curve", "electrical_efficiency_curve"):
            self.assertNotIn(legacy, diagnostics_block)

    def test_report_wording_uses_current_equipment_names(self):
        report_block = self._function_source("buildHtmlReport")
        self.assertIn("MAU Energy", report_block)
        self.assertIn("Electrical Distribution Loss", report_block)
        self.assertIn("CDU / RTC / MAU", report_block)
        for forbidden in (
            "Terminal Fan",
            "Airflow Power",
            "Auxiliary Load",
            "fallback to Legacy",
            "weather-driven sensitivity",
            "annual calibration",
            "benchmark target",
        ):
            self.assertNotIn(forbidden, report_block)

    def test_configuration_library_acc_v2_direct_disclosure_labels(self):
        detector_block = self._function_source("isConfigurationLibraryAccV2DirectResult")
        for text in (
            "CONFIGURATION_LIBRARY_ACC_ENGINE",
            "CONFIGURATION_LIBRARY_DIRECT_CALCULATION_MODE",
            "project_8760",
            "acc_v2_solver_curve_direct",
            "configuration_library_solver_curve",
            "excel_benchmark_compatible",
        ):
            self.assertIn(text, detector_block)

        report_block = self._function_source("buildHtmlReport")
        for text in (
            "isConfigurationLibraryAccV2DirectMode",
            "ACC Calculation Mode",
            "True EPW × Solver_Curve",
            "Annual Calibration",
            "Not applied",
            "Annual Calibration Factor",
            "1.0",
        ):
            self.assertIn(text, report_block)
        self.assertNotIn("Annual Calibrated", report_block)

    def test_configuration_library_summary_discloses_no_acc_calibration(self):
        summary_block = self._function_source("renderConfigurationLibrarySummary")
        principle_block = self._function_source("showProjectVisualization")
        for block in (summary_block, principle_block):
            self.assertIn("isConfigurationLibraryAccV2DirectResult", block)
            self.assertIn("ACC Calculation Mode", block)
            self.assertIn("True EPW × Solver_Curve", block)
            self.assertIn("Annual Calibration", block)
            self.assertIn("Not applied", block)
            self.assertNotIn("Annual Calibrated", block)

    def test_benchmark_report_labels_remain_separate(self):
        report_block = self._function_source("buildHtmlReport")
        self.assertIn("ACC Annual Weather Factor", report_block)
        self.assertIn("acc_annual_temperature_factor", report_block)
        self.assertIn("isAnnualBenchmarkMode", report_block)
        self.assertIn("excel_benchmark_compatible", report_block)

    def _function_source(self, function_name):
        match = re.search(rf"(?:async\s+)?function\s+{re.escape(function_name)}\s*\(", self.ui)
        if not match:
            raise AssertionError(f"function {function_name} not found")
        start = match.start()
        match = re.search(r"\n(?:async\s+)?function\s+\w+\s*\(", self.ui[start + 1:])
        end = start + 1 + match.start() if match else len(self.ui)
        return self.ui[start:end]


if __name__ == "__main__":
    unittest.main()
