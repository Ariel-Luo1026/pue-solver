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

    def test_simulation_readiness_panel_and_checks_exist(self):
        for text in (
            'id="simulationReadinessPanel"',
            "Simulation Readiness",
            'id="simulationReadinessChecks"',
            'id="simulationReadinessStatus"',
            "READY FOR ANNUAL SIMULATION",
            "SIMULATION INPUTS NOT READY",
        ):
            self.assertIn(text, self.index + self.ui)
        readiness = self._function_source("getSimulationReadiness")
        for check in (
            "configurationReady", "equipmentBindingsReady", "weatherReady",
            "itLoadReady", "coolingInputsReady", "simulationReady",
        ):
            self.assertIn(check, readiness)

    def test_readiness_reuses_current_binding_weather_and_it_load_state(self):
        readiness = self._function_source("getSimulationReadiness")
        self.assertIn('validation?.status === "valid"', readiness)
        self.assertIn("missing_roles", readiness)
        self.assertIn("missing_curves", readiness)
        self.assertIn("getWeatherHours(standardDataFiles.weather)", readiness)
        self.assertIn("[8760, 8784].includes(weatherHours)", readiness)
        self.assertIn("itLoadHours === weatherHours", readiness)

    def test_cooling_input_readiness_validates_numbers_and_existing_ranges(self):
        block = self._function_source("coolingLoadAdjustmentInputsReady")
        for element_id in (
            "solarHeatGainMaxKw", "solarDaytimeStartHour", "solarDaytimeEndHour",
            "otherAuxiliaryHeatGainKw", "otherElectricalAuxiliaryPowerKw",
        ):
            self.assertIn(element_id, block)
        self.assertIn("Number.isFinite(value)", block)
        self.assertIn("value >= minimum", block)
        self.assertIn("value <= maximum", block)

    def test_run_button_uses_consolidated_readiness_and_existing_handler(self):
        set_disabled = self._function_source("setRunButtonsDisabled")
        self.assertIn("!simulationReady", set_disabled)
        self.assertIn('btnRun.addEventListener("click", runUsingConfigurationLibrary)', self.ui)

    def test_configuration_change_resets_and_cooling_changes_refresh_readiness(self):
        init_block = self._function_source("initStandardDataInputs")
        self.assertIn("configurationLibraryData = null", init_block)
        self.assertIn("window.configurationLibraryData = null", init_block)
        self.assertGreaterEqual(init_block.count("refreshSimulationReadiness()"), 2)

    def test_cooling_advanced_information_is_collapsed_by_default(self):
        start = self.index.index('<details id="coolingAdvancedConfigurationDetails"')
        end = self.index.index("</details>", start)
        details = self.index[start:end]

        self.assertNotIn(" open", details.split(">", 1)[0])
        self.assertIn("Advanced Configuration Details", details)
        for label, element_id in (
            ("White Space Equipment", "whiteSpaceEquipmentList"),
            ("Gray Space Equipment", "graySpaceEquipmentList"),
            ("Required Performance Curves", "coolingPerformanceCurveList"),
        ):
            self.assertIn(label, details)
            self.assertIn(f'id="{element_id}"', details)

    def test_cooling_advanced_disclosure_does_not_wrap_primary_controls(self):
        details_start = self.index.index('<details id="coolingAdvancedConfigurationDetails"')
        primary_controls = (
            'id="coolingSystemType"',
            'id="coolingUnitCapacity"',
            'id="powerSource"',
            'id="scenarioSelect"',
        )
        for control in primary_controls:
            self.assertLess(self.index.index(control), details_start)

    def test_cooling_system_definition_is_read_only_and_library_driven(self):
        for element_id in ("coolingSystemType", "coolingUnitCapacity", "powerSource"):
            self.assertIn(f'id="{element_id}" class="coolingDefinitionValue"', self.index)
            self.assertNotIn(f'<select id="{element_id}"', self.index)
            self.assertIn(f'id="{element_id}Source"', self.index)
        self.assertIn("Source: Configuration Library", self.index)
        self.assertIn('<select id="scenarioSelect"></select>', self.index)

        selection_block = self._function_source("getCoolingSystemSelection")
        for source in (
            "configurationLibraryData?.cooling_system_type",
            "configurationLibraryData?.cooling_unit_capacity_mw",
            "configurationLibraryData?.power_source",
        ):
            self.assertIn(source, selection_block)
        for element_id in ("coolingSystemType", "coolingUnitCapacity", "powerSource"):
            self.assertNotIn(f'document.getElementById("{element_id}")', selection_block)
        self.assertIn('document.getElementById("scenarioSelect")', selection_block)

    def test_loaded_library_populates_read_only_definition_cards(self):
        render_block = self._function_source("renderCoolingSystemSelection")
        for text in (
            'coolingSystemType: libraryLoaded ? type : "Not loaded"',
            'coolingUnitCapacity: libraryLoaded ? `${capacityMw} MW` : "Not loaded"',
            'powerSource: libraryLoaded ? powerSource : "Not loaded"',
            '"Loaded from Configuration Library"',
        ):
            self.assertIn(text, render_block)

    def test_configuration_change_clears_definition_and_requires_reload(self):
        init_block = self._function_source("initStandardDataInputs")
        self.assertIn("configurationLibraryData = null", init_block)
        self.assertIn("refreshSimulationReadiness()", init_block)
        self.assertIn('summary.style.display = "none"', init_block)
        self.assertIn("Equipment binding status will appear after the Configuration Library is loaded.", init_block)
        self.assertIn("renderCoolingSystemSelection()", init_block)

    def test_unit_quantity_maps_to_project_input(self):
        self.assertIn("function getUnitQuantitySelection", self.ui)
        self.assertIn('mode: "manual"', self.ui)
        self.assertIn('redundancy === "N+1"', self.ui)
        self.assertIn('redundancy === "N+2"', self.ui)
        self.assertIn("unit_quantity: unitQuantity", self.ui)
        self.assertIn("running_units: activeUnits", self.ui)
        self.assertIn("standby_units: standbyUnits", self.ui)
        self.assertIn("indoor_active_units: indoorActiveUnits", self.ui)

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
        self.assertIn("manifestEquipmentRoleIds(data.configuration_manifest).map", binding_block)
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
        self.assertIn('new URL("equipment_aliases.json", CONFIGURATION_LIBRARY_ROOT_URL)', alias_block)
        self.assertIn("directModeEquipmentAliases = { ...DEFAULT_DIRECT_MODE_EQUIPMENT_ALIASES, ...loaded }", alias_block)
        self.assertIn("directModeEquipmentAliases = { ...DEFAULT_DIRECT_MODE_EQUIPMENT_ALIASES }", alias_block)
        self.assertIn('fetch(aliasUrl, { cache: "no-store" })', alias_block)

    def test_pyodide_is_lazy_loaded_after_startup(self):
        init_block = self._function_source("init")
        self.assertNotIn("loadPyodide()", init_block)
        self.assertNotIn("runPythonAsync", init_block)
        self.assertIn("Calculation engine will load when you click Run", init_block)
        self.assertIn("btnRun.disabled = !configurationLibraryData", init_block)

        ensure_block = self._function_source("ensurePyodideReady")
        self.assertIn("if (pyodide && window.pyodideReady) return pyodide", ensure_block)
        self.assertIn("if (pyodideReadyPromise) return pyodideReadyPromise", ensure_block)
        self.assertIn("pyodideReadyPromise = (async () =>", ensure_block)
        self.assertIn("pyodide = await loadPyodide()", ensure_block)
        self.assertIn("for (const moduleName of DIRECT_MODE_PYTHON_MODULES)", ensure_block)
        self.assertIn('console.time("loadPyodide")', ensure_block)
        self.assertIn('console.time("fetch/write module loop")', ensure_block)
        self.assertIn('console.time("solver.py runPythonAsync")', ensure_block)
        self.assertIn('fetch("./solver.py", { cache: "no-store" })', ensure_block)
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
        equipment_loader_block = self._function_source("loadConfigurationEquipmentEntries")
        self.assertIn("await loadConfigurationEquipmentAliases()", loader_block)
        self.assertIn("loadConfigurationEquipmentEntries(configurationName, selectedManifest)", loader_block)
        self.assertIn("const resolvedId = resolveFrontendEquipmentId(equipmentId)", equipment_loader_block)
        self.assertIn("fetchResolvedConfigurationEquipmentWorkbook(base, equipmentId)", equipment_loader_block)
        self.assertIn("return [fetched.resolvedId", equipment_loader_block)
        self.assertIn("equipment_id: fetched.resolvedId", equipment_loader_block)
        self.assertIn("source_equipment_id: fetched.rawEquipmentId", equipment_loader_block)
        self.assertIn("source_workbook_equipment_id: fetched.sourceEquipmentId", equipment_loader_block)
        self.assertIn("solver_curves: Object.fromEntries(curveNames.map(name => [name, sheets[name]]))", equipment_loader_block)
        self.assertNotIn("fetchConfigurationWorkbook(`${base}/${packagePath}`)", equipment_loader_block)

    def test_configuration_library_run_input_uses_canonical_auxiliary_ids(self):
        builder_block = self._function_source("buildGenericConfigurationLibraryPayload")
        self.assertIn("const roleBindings = Object.fromEntries", builder_block)
        self.assertIn("Object.keys(manifest?.equipment_roles || {}).map", builder_block)
        self.assertIn("resolveEquipmentRoleIdFromMapping(manifest, roleName, data.equipment, roleRequired)", builder_block)
        self.assertIn("equipment_id: resolved.resolvedId", builder_block)
        self.assertIn("role_bindings: roleBindings", builder_block)
        self.assertIn("equipment_bindings: equipmentBindings", builder_block)
        self.assertNotIn('topologyId === "acc_gas_engine_cdu"', builder_block)
        self.assertNotIn('topologyId === "chiller_dry_cooler"', builder_block)
        adapter_block = self._function_source("convertFrontendLibraryInputToSolverInput")
        self.assertIn("SUPPORTED_CONFIGURATION_TOPOLOGIES.includes(topologyId)", adapter_block)
        self.assertIn("return JSON.parse(JSON.stringify(libraryInput))", adapter_block)
        self.assertNotIn("library_fixed_power: clone(libraryInput.equipment.auxiliary)", adapter_block)

    def test_frontend_carries_normal_indoor_unit_count_for_library_direct_input(self):
        sizing_block = self._function_source("calculateFrontendUnitRequirements")
        self.assertIn("indoorActiveUnits: requiredUnits + 1", sizing_block)

        builder_block = self._function_source("buildGenericConfigurationLibraryPayload")
        self.assertIn("const indoorActiveUnits = unitQuantity.mode === \"manual\"", builder_block)
        self.assertIn("indoor_active_units: indoorActiveUnits", builder_block)
        self.assertLess(builder_block.index("const indoorActiveUnits"), builder_block.index("project: {"))

        self.assertIn("indoor_active_units: indoorActiveUnits", builder_block)

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

    def test_configuration_library_summary_displays_equipment_metadata(self):
        self.assertIn("function fetchConfigurationLibraryJson", self.ui)
        equipment_loader_block = self._function_source("loadConfigurationEquipmentEntries")
        self.assertIn("equipment_metadata.json", equipment_loader_block)
        self.assertIn("equipment_metadata: equipmentMetadata", equipment_loader_block)
        validation_block = self._function_source("validateFrontendConfigurationLibrary")
        self.assertIn("equipment_metadata missing", validation_block)
        summary_block = self._function_source("renderConfigurationLibrarySummary")
        for text in (
            "Equipment Binding Details",
            "Equipment Type",
            "Curve Type",
            "Curve Schema",
            "Metadata Status",
            "equipmentMetadata.equipment_type",
            "equipmentMetadata.curve_type",
            "equipmentCurveSchema",
        ):
            self.assertIn(text, summary_block)

    def test_configuration_library_secondary_sections_are_collapsed_disclosures(self):
        summary_block = self._function_source("renderConfigurationLibrarySummary")
        for details_id, title in (
            ("configurationMetadataDetails", "Configuration Metadata"),
            ("configurationCalculationSummaryDetails", "Calculation Summary"),
            ("configurationEquipmentBindingDetails", "Equipment Binding Details"),
        ):
            self.assertIn(f'<details id="{details_id}"', summary_block)
            self.assertIn(f"<summary>{title}</summary>", summary_block)
        self.assertNotIn('<details id="configurationMetadataDetails" open', summary_block)
        self.assertNotIn('<details id="configurationCalculationSummaryDetails" open', summary_block)
        self.assertNotIn('<details id="configurationEquipmentBindingDetails" open', summary_block)

    def test_framework_diagnostics_is_developer_disclosure_closed_by_default(self):
        start = self.index.index('<details id="frameworkDiagnosticsDetails"')
        opening_tag = self.index[start:self.index.index(">", start)]
        end = self.index.index("</details>", start)
        details = self.index[start:end]
        self.assertNotIn(" open", opening_tag)
        self.assertIn("Framework Diagnostics (Developer)", details)
        self.assertIn('id="frameworkDiagnosticsNotice"', details)
        self.assertIn('id="frameworkDiagnosticsGrid"', details)

    def test_configuration_library_direct_input_carries_configuration_path(self):
        builder_block = self._function_source("buildGenericConfigurationLibraryPayload")
        self.assertIn("configuration_path: data.configuration_path || data.configuration_name", builder_block)
        self.assertIn("configuration_name: data.configuration_name", builder_block)

    def test_cooling_load_heat_gain_inputs_feed_configuration_library_solver_input(self):
        for text in (
            'id="solarHeatGainMaxKw"',
            'id="solarDaytimeStartHour"',
            'id="solarDaytimeEndHour"',
            'id="otherAuxiliaryHeatGainKw"',
            'id="otherElectricalAuxiliaryPowerKw"',
            "Other Electrical Auxiliary Power (kW)",
            "Direct electrical loads not represented by dedicated equipment models.",
            "Solar heat gain and other auxiliary heat gains are included in Total Cooling Load.",
        ):
            self.assertIn(text, self.index)
        for legacy in ("solarGainAnnualKwh", "solarGainPeakKw", "Report-only Solar Heat Gain"):
            self.assertNotIn(legacy, self.index)

        builder_block = self._function_source("buildGenericConfigurationLibraryPayload")
        self.assertIn("const heatGains = getCoolingLoadHeatGainInput()", builder_block)
        self.assertIn("solar_heat_gain_max_kW: heatGains.solarHeatGainMaxKw", builder_block)
        self.assertIn("other_auxiliary_heat_gain_kW: heatGains.otherAuxiliaryHeatGainKw", builder_block)
        self.assertIn("other_electrical_auxiliary_power_kW: heatGains.otherElectricalAuxiliaryPowerKw", builder_block)

    def test_simulation_inputs_are_configuration_library_driven(self):
        self.assertIn("Simulation Inputs", self.index)
        self.assertIn("Weather Source", self.index)
        self.assertIn("Automatic EPW Matching", self.index)
        self.assertNotIn('id="btnAutoMatchEpw"', self.index)
        for legacy_id in (
            "fileWeather",
            "fileDryCooler",
            "fileChiller",
            "fileElectrical",
            "filePumps",
            "fileFans",
        ):
            self.assertNotIn(f'id="{legacy_id}"', self.index)
        self.assertIn('id="fileItLoad"', self.index)
        self.assertIn('accept=".xlsx,.xls,.csv"', self.index)
        for legacy_title in (
            "IT负载全年曲线",
            "干冷器性能曲线",
            "离心冷水机COP曲面",
            "电气设备性能曲线",
            "水泵性能曲线",
            "末端风机性能曲线",
        ):
            self.assertNotIn(legacy_title, self.index)

    def test_configuration_load_and_annual_run_are_separate_actions(self):
        self.assertIn('id="btnLoadConfigurationLibrary">Load Configuration Library</button>', self.index)
        self.assertIn('id="btnRun" disabled>Run Annual PUE Simulation</button>', self.index)
        self.assertNotIn("Run Using Configuration Library", self.index)
        self.assertNotIn('id="btnRunConfigurationLibrary"', self.index)

        init_block = self._function_source("initStandardDataInputs")
        self.assertIn('libraryButton.addEventListener("click", loadSelectedConfigurationLibrary)', init_block)
        self.assertNotIn("runUsingConfigurationLibrary", init_block)
        self.assertIn('btnRun.addEventListener("click", runUsingConfigurationLibrary)', self.ui)

    def test_configuration_mode_wording_is_not_duplicated(self):
        self.assertEqual(self.index.count("Configuration Library Direct Solver_Curve Hourly Simulation"), 1)

    def test_project_level_heat_gain_defaults_are_preserved(self):
        for element_id, value in (
            ("solarHeatGainMaxKw", "7"),
            ("solarDaytimeStartHour", "6"),
            ("solarDaytimeEndHour", "18"),
            ("otherAuxiliaryHeatGainKw", "71"),
            ("otherElectricalAuxiliaryPowerKw", "0"),
        ):
            self.assertRegex(self.index, rf'id="{element_id}"[^>]*value="{value}"')

    def test_advanced_input_override_is_closed_with_connected_it_profile(self):
        start = self.index.index('<details id="advancedInputOverrideDetails"')
        opening_tag = self.index[start:self.index.index(">", start)]
        end = self.index.index("</details>", start)
        details = self.index[start:end]
        self.assertNotIn(" open", opening_tag)
        for title in (
            "Advanced Input Override",
            "Annual IT Load Profile",
            "Manual Weather File Override",
            "Custom Equipment Curve Override",
        ):
            self.assertIn(title, details)
        self.assertIn('id="fileItLoad"', details)
        self.assertIn("Project-level override", details)
        self.assertNotIn("Manual IT Load Profile Override", details)

    def test_canonical_it_profile_precedence_and_validation_are_wired(self):
        load_block = self._function_source("loadSelectedConfigurationLibrary")
        builder = self._function_source("buildGenericConfigurationLibraryPayload")
        readiness = self._function_source("getSimulationReadiness")
        upload = self._function_source("handleStandardFile")
        self.assertIn("projectItLoadProfileOverride", load_block)
        self.assertNotIn('slot === "itLoad"', load_block)
        self.assertIn("configuration_library_profile", load_block)
        self.assertIn("compatibility_default", load_block)
        self.assertIn("Compatibility Default — 90% Constant", load_block)
        self.assertIn("resolvedItProfile?.hourly_it_load_kW", builder)
        self.assertIn("it_load_profile_source_type", builder)
        self.assertIn("valid_with_overload_warning", readiness)
        self.assertIn("itLoadHours === weatherHours", readiness)
        self.assertIn("IT Load Profile Upload Failed", upload)

    def test_configuration_library_binding_status_uses_existing_bindings(self):
        self.assertIn('id="configurationLibraryBindingStatus"', self.index)
        summary_block = self._function_source("renderConfigurationLibrarySummary")
        for text in (
            "bindingSummaryRows",
            "selected.sheet_name || selected.electrical_path",
            "Configuration Library Loaded:",
            'CHILLER: "Chiller"',
            "Dry Cooler",
            "CHW Pump",
            "CW Pump",
            "Electrical Distribution",
        ):
            self.assertIn(text, summary_block)

    def test_input_ready_message_describes_library_driven_workflow(self):
        status_block = self._function_source("refreshStandardInputStatus")
        self.assertIn("设备模型由 Configuration Library 自动加载", status_block)
        self.assertIn("Equipment models are automatically loaded from Configuration Library", status_block)
        self.assertNotIn("点击“运行计算”会自动生成 solver 输入", status_block)

    def test_library_load_triggers_existing_epw_matcher_automatically(self):
        load_block = self._function_source("loadSelectedConfigurationLibrary")
        self.assertIn("resetAutomaticEpwBindingState()", load_block)
        self.assertIn("const epwMatched = await autoMatchLocalEpw()", load_block)
        self.assertIn("refreshSimulationReadiness()", load_block)
        self.assertIn("Equipment models and EPW weather are ready", load_block)
        self.assertIn("async function autoMatchLocalEpw()", self.ui)

    def test_epw_status_updates_without_manual_button(self):
        apply_block = self._function_source("applyMatchedEpw")
        self.assertIn("✓ Automatic EPW Matching", apply_block)
        self.assertIn("Climate Station:", apply_block)
        self.assertIn("hourly weather loaded", apply_block)
        self.assertNotIn("btnAutoMatchEpw", self.index)

    def test_configuration_change_clears_epw_and_disables_run(self):
        init_block = self._function_source("initStandardDataInputs")
        self.assertIn("resetAutomaticEpwBindingState()", init_block)
        self.assertIn("configurationLibraryData = null", init_block)
        self.assertIn("refreshSimulationReadiness()", init_block)
        reset_block = self._function_source("resetAutomaticEpwBindingState")
        self.assertIn("automaticEpwReady = false", reset_block)
        self.assertIn("standardDataFiles.weather = null", reset_block)
        self.assertIn("Waiting for Configuration Library loading", reset_block)

    def test_annual_run_requires_library_and_epw_ready(self):
        disable_block = self._function_source("setRunButtonsDisabled")
        self.assertIn("!simulationReady", disable_block)
        run_block = self._function_source("runUsingConfigurationLibrary")
        self.assertIn("if (!automaticEpwReady)", run_block)
        self.assertIn("Automatic EPW weather matching must complete successfully", run_block)

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
        self.assertIn("verifyConfigurationLibrarySynced(configurationPath, selectedConfiguration)", sync_block)
        self.assertIn("workbook_paths: workbookPaths", sync_block)

    def test_configuration_library_options_are_manifest_discovered(self):
        self.assertNotIn('<option value="ACC_1.5MW_GASENGINE_CDU">ACC_1.5MW_GASENGINE_CDU</option>', self.index)
        self.assertIn("configuration_library_index.json", self.ui)
        self.assertIn("function loadConfigurationLibraryCatalog", self.ui)
        self.assertIn("function renderConfigurationLibraryCatalog", self.ui)
        self.assertIn("configuration_manifest.json", self.ui)
        self.assertIn("configurationStatusLabel", self.ui)
        self.assertIn("Available", self.ui)
        self.assertIn("Framework Ready / Data Missing", self.ui)
        self.assertIn("Topology:", self.ui)
        init_block = self._function_source("initStandardDataInputs")
        self.assertIn("loadConfigurationLibraryCatalog()", init_block)

    def test_frontend_can_select_chiller_dry_cooler_configuration(self):
        self.assertIn('chiller_dry_cooler: { display: "Chiller + Dry Cooler", status: "implemented"', self.ui)
        self.assertIn('"chiller_dry_cooler"', self.ui)
        catalog_block = self._function_source("renderConfigurationLibraryCatalog")
        self.assertIn("manifest.runnable ? \"\" : \"disabled\"", catalog_block)
        self.assertIn("Topology: ${topology.display}", catalog_block)
        builder_block = self._function_source("buildGenericConfigurationLibraryPayload")
        self.assertIn('SUPPORTED_CONFIGURATION_TOPOLOGIES.includes(topologyId)', builder_block)
        self.assertIn("role_bindings: roleBindings", builder_block)
        self.assertIn("equipment_bindings: equipmentBindings", builder_block)
        self.assertNotIn('topologyId === "chiller_dry_cooler"', builder_block)
        self.assertNotIn('chiller: bindingByRole("chiller", "chiller")', builder_block)
        self.assertNotIn('dry_cooler: {', builder_block)
        self.assertIn("dry_cooler_approach_C: dryCoolerApproachC", builder_block)
        self.assertIn("weather,", builder_block)
        run_block = self._function_source("runUsingConfigurationLibrary")
        self.assertIn('const solverFn = "dispatch_topology"', run_block)
        self.assertNotIn('topologyId === "chiller_dry_cooler" ? "dispatch_topology" : "compute_pue_project"', run_block)

    def test_unavailable_configuration_cannot_run_frontend_direct_mode(self):
        run_block = self._function_source("runUsingConfigurationLibrary")
        self.assertIn("isConfigurationManifestRunnable(configurationLibraryData.configuration_manifest)", run_block)
        self.assertIn("requires validated Solver_Curve data and solver module implementation", run_block)
        builder_block = self._function_source("buildGenericConfigurationLibraryPayload")
        self.assertIn("Unsupported solver topology for Configuration Library direct mode", builder_block)
        adapter_block = self._function_source("convertFrontendLibraryInputToSolverInput")
        self.assertIn("Unsupported solver topology for Configuration Library dispatch", adapter_block)

    def test_selected_configuration_manifest_is_passed_to_adapter(self):
        load_block = self._function_source("loadSelectedConfigurationLibrary")
        self.assertIn("const selectedManifest = selectedConfigurationManifest()", load_block)
        self.assertIn("configuration_manifest: selectedManifest", load_block)
        builder_block = self._function_source("buildGenericConfigurationLibraryPayload")
        self.assertIn("configuration_manifest: JSON.parse(JSON.stringify(manifest))", builder_block)
        self.assertIn("configuration_id: manifest.configuration_id", builder_block)

    def test_configuration_library_sync_plan_uses_direct_mode_equipment_paths(self):
        plan_block = self._function_source("buildConfigurationLibraryWorkbookSyncPlan")
        self.assertIn("manifestEquipmentRoleIds(data?.configuration_manifest)", plan_block)
        self.assertIn("roleEquipmentIds.map", plan_block)
        self.assertIn("findLibraryEquipmentPackage(data, equipmentId)", plan_block)
        self.assertIn("sourceRelativePaths", plan_block)
        self.assertIn("pyodideRelativePath", plan_block)
        self.assertIn("resolved.resolvedId", plan_block)
        self.assertIn("roleTargets.has(resolvedId)", plan_block)
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
        self.assertNotIn("applyAccCalculationEngineSelection(adaptedInput, calculationMode, libraryInput.configuration_path)", run_block)
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
        report_block = self._function_source("buildHtmlReportFromSections")
        self.assertIn("reportKeyLabel(key)", report_block)
        self.assertIn("Cooling System Performance", report_block)
        self.assertIn("Electrical Distribution Loss", self.ui)
        self.assertIn("MAU Energy", self.ui)
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

    def test_report_uses_topology_profile_metadata(self):
        self.assertIn("const REPORT_PROFILE_REGISTRY", self.ui)
        self.assertIn("function reportProfileForTopology", self.ui)
        self.assertIn("function dispatchReportProfile", self.ui)
        report_block = self._function_source("buildHtmlReportFromSections")
        for text in (
            "dispatchReportProfile(solverTopology, output)",
            "Cooling System Type",
            "Cooling Architecture",
            "Report Configuration",
        ):
            self.assertIn(text, report_block)

    def test_chiller_dry_cooler_report_fields_are_exposed(self):
        self.assertIn("average_chiller_COP", self.ui)
        self.assertIn("min_chiller_COP", self.ui)
        self.assertIn("max_chiller_COP", self.ui)
        report_block = self._function_source("buildHtmlReportFromSections")
        for text in (
            "report.equipment_performance",
            "report.cooling_load_breakdown",
            "buildReportSections",
        ):
            self.assertIn(text, report_block)
        for text in (
            "Operating Scenario",
            "Peak Capacity Validation",
            "Active Chiller Units",
            "Active Dry Cooler Units",
            "Active Pumps",
            "Capacity Margin",
            "Annual Energy Breakdown",
            "Project Summary",
            "Weather & Design Conditions",
            "Cooling Load Summary",
            "Cooling System Configuration",
            "Equipment Performance",
            "PUE Summary",
            "Engineering Conclusion",
        ):
            self.assertIn(text, self.ui)
        self.assertIn("Configuration Status", self.ui)
        renderer_block = self._function_source("renderReportSections")
        self.assertIn("normalizeReportSections", renderer_block)
        self.assertNotIn("isAccMode", renderer_block)
        self.assertNotIn("isChillerDryCoolerMode", renderer_block)
        self.assertIn("buildAnnualEnergyBreakdown", self.ui)
        self.assertIn("COMMON_REPORT_SECTIONS", self.ui)
        self.assertIn("buildReportSections", self.ui)
        self.assertIn("buildEngineeringConclusion", self.ui)
        self.assertIn('"report_renderer.py"', self.ui)
        self.assertIn('"report_sections/__init__.py"', self.ui)
        self.assertIn('"report_sections/report_section_registry.py"', self.ui)

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

        report_block = self._function_source("showProjectVisualization")
        for text in ("Cooling System:", "Simulation Engine:", "Performance Model:", "Simulation Basis:"):
            self.assertIn(text, report_block)
        self.assertIn("ACC V2 Direct Mode", self.ui)
        self.assertNotIn("Annual Calibration", report_block)
        self.assertNotIn("Annual Calibration Factor", report_block)
        self.assertNotIn("Annual Calibrated", report_block)

    def test_acc_cooling_load_report_polish_labels(self):
        report_block = self._function_source("buildHtmlReportFromSections")
        for text in (
            "Weather Source",
            "EPW File",
        ):
            self.assertIn(text, report_block)
        self.assertIn("Required Cooling Capacity / Installed Cooling Unit Capacity", self.ui)
        self.assertIn("Annual Cooling Load", self.ui)
        for text in (
            "Minimum ACC COP",
            "Maximum ACC COP",
            "Maximum ACC Power",
            "ACC Capacity Clamped Hours",
        ):
            self.assertIn(text, self.ui)
        for forbidden in (
            "IT Load / Total Cooling Unit Capacity",
            "Ambient plus required capacity Solver_Curve lookup",
            "report-only decomposition",
            "solar heat gain impact on cooling load",
        ):
            self.assertNotIn(forbidden, report_block)

    def test_configuration_library_summary_discloses_no_acc_calibration(self):
        summary_block = self._function_source("renderConfigurationLibrarySummary")
        principle_block = self._function_source("showProjectVisualization")
        for block in (summary_block, principle_block):
            self.assertNotIn("Annual Calibration", block)
            self.assertNotIn("Annual Calibration Factor", block)
            self.assertNotIn("Annual Calibrated", block)
        self.assertIn("isConfigurationLibraryAccV2DirectResult", summary_block)
        self.assertIn("ACC V2 Direct Mode", summary_block)
        self.assertIn("Simulation Basis", principle_block)
        self.assertIn("8760-hour Annual Dynamic Simulation", self.ui)

    def test_configuration_library_acc_v2_report_labels_peak_design_separately(self):
        report_block = self._function_source("buildHtmlReportFromSections")
        visualization_block = self._function_source("showProjectVisualization")
        self.assertIn("Peak Design PUE", report_block)
        for block in (report_block, visualization_block):
            self.assertNotIn("Peak Design Engine Output", block)
            self.assertNotIn("Max Hourly Engine Output", block)
        self.assertIn("peak_design_cooling_load_kW", self.ui)
        self.assertIn("peak_design_outdoor_dry_bulb_C", self.ui)
        self.assertIn("ASHRAE Station ID", report_block)
        self.assertIn("Peak Design Weather Source", report_block)
        self.assertIn("Peak Design PUE", report_block)
        self.assertIn("report.visualization_data.peak_summary", visualization_block)
        self.assertIn("peakSummary.peak_facility_power_kW", visualization_block)
        self.assertIn("peakSummary.max_hourly_pue", visualization_block)

    def test_peak_design_weather_controls_feed_library_input(self):
        self.assertIn('"ashrae_online_lookup.py"', self.ui)
        self.assertIn('"ashrae_design_conditions.py"', self.ui)
        self.assertIn('"ashrae_design_conditions_data.json"', self.ui)
        self.assertIn("function peakDesignSourceLabel", self.ui)
        self.assertIn("ASHRAE Online", self.ui)
        self.assertIn("Automatic ASHRAE Online Lookup", self.ui)
        self.assertIn("ASHRAE Online Lookup Successful", self.ui)
        self.assertIn("Lookup Status", self.ui)
        self.assertIn("Lookup Method", self.ui)
        self.assertIn('const hasSuccessfulAshraeLookup = lookupStatus === "SUCCESS"', self.ui)
        self.assertIn("Design DB Maximum", self.ui)
        self.assertIn("http://127.0.0.1:8011/api/ashrae_design_condition", self.ui)
        self.assertIn('const ASHRAE_PROXY_URL = "http://127.0.0.1:8011/api/ashrae_design_condition"', self.ui)
        self.assertIn("ashraeDesignConditionsUrl", self.ui)
        self.assertIn("ashrae_design_conditions_url: libraryAshraeUrl", self.ui)
        self.assertIn("Manual Override", self.ui)
        self.assertIn("Local ASHRAE Cache", self.ui)
        self.assertIn("ASHRAE Online unavailable", self.ui)
        self.assertIn("Manual override required", self.ui)
        self.assertIn("Using Local ASHRAE Cache fallback", self.ui)
        self.assertIn("peak_design_online_status", self.ui)
        self.assertIn("peak_design_fallback_status", self.ui)
        self.assertIn("peak_design_lookup_provider", self.ui)
        self.assertIn("peak_design_lookup_status", self.ui)
        self.assertIn("peak_design_lookup_failure_reason", self.ui)
        self.assertIn("peak_design_lookup_method", self.ui)
        self.assertIn("peak_design_lookup_endpoint", self.ui)

        for text in (
            "Peak Design Weather",
            "Automatic ASHRAE 20-year Extreme Design Condition",
            "Manual Override",
            'id="manualPeakDesignDryBulbC"',
            "Design Outdoor Dry Bulb",
        ):
            self.assertIn(text, self.index)

        builder_block = self._function_source("buildGenericConfigurationLibraryPayload")
        for text in (
            "const peakDesignWeather = getPeakDesignWeatherInput()",
            "const libraryAshraeUrl = ASHRAE_PROXY_URL",
            "peak_design_weather_source: peakDesignWeather.peakDesignWeatherSource",
            "peak_design_outdoor_dry_bulb_C: peakDesignWeather.peakDesignOutdoorDryBulbC",
            "ashrae_design_conditions_url: libraryAshraeUrl",
            "site_location: {",
            "latitude: projectInfo.latitude",
            "longitude: projectInfo.longitude",
        ):
            self.assertIn(text, builder_block)

        adapter_block = self._function_source("convertFrontendLibraryInputToSolverInput")
        self.assertIn("return JSON.parse(JSON.stringify(libraryInput))", adapter_block)
        self.assertIn("fetchAshraeProxyDesignConditionForLibrary", self.ui)
        self.assertIn('fetch(url, { cache: "no-store" })', self.ui)
        self.assertIn("peak_design_condition_override", self.ui)

    def test_configuration_library_engineering_ashrae_diagnostics_stay_out_of_customer_report(self):
        summary_block = self._function_source("renderConfigurationLibrarySummary")
        self.assertIn("ASHRAE Endpoint Sent to Solver", summary_block)
        self.assertIn("ASHRAE Endpoint Received by Solver", summary_block)
        self.assertIn("Lookup Method", summary_block)
        self.assertIn("Lookup Provider", summary_block)

        report_block = self._function_source("buildHtmlReportFromSections")
        self.assertNotIn("ASHRAE Endpoint Sent to Solver", report_block)
        self.assertNotIn("ASHRAE Endpoint Received by Solver", report_block)

    def test_benchmark_report_labels_remain_separate(self):
        report_block = self._function_source("buildHtmlReportFromSections")
        self.assertNotIn("ACC Annual Weather Factor", report_block)
        self.assertNotIn("isAnnualBenchmarkMode", report_block)
        self.assertIn("excel_benchmark_compatible", self.ui)

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
