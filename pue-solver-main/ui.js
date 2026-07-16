let pyodide = null;
let pyodideReadyPromise = null;
let pyodideDirectModeModulesLoaded = false;
let pyodideSolverLoaded = false;
let pyodideBenchmarkLoaded = false;
let runInProgress = false;

const WHITE_SPACE_BY_MODEL = {
    1: ["CDU_1", "RTC_1", "RTC_2", "MAU_1", "MAU_2"],
    2: ["CDU_2", "RTC_1", "RTC_2", "MAU_1", "MAU_2"],
    3: ["CDU_3", "RTC_1", "RTC_2", "MAU_1", "MAU_2"]
};

function coolingUnitConfiguration(whiteModel, grayIds, engineId, requiredCurves, smokeWaterHx = false) {
    const gasEquipment = [...grayIds, "ENGINE_RADIATOR_1", engineId];
    const gasCurves = [...requiredCurves, "Engine efficiency curve", "Engine radiator performance curve"];
    if (smokeWaterHx) {
        gasEquipment.push("SMOKE_WATER_HX_1");
        gasCurves.push("Smoke-water HX performance curve");
    }
    return { power_sources: {
        Grid: { white_space_equipment: [...WHITE_SPACE_BY_MODEL[whiteModel]], gray_space_equipment: [...grayIds], required_curves: [...requiredCurves] },
        "Gas Engine": { white_space_equipment: [...WHITE_SPACE_BY_MODEL[whiteModel]], gray_space_equipment: gasEquipment, required_curves: gasCurves }
    } };
}

const COOLING_SYSTEM_CONFIG = Object.freeze({
    "ABS + Dry Cooler": {
        cooling_unit_capacities: {
            "1": coolingUnitConfiguration(1, ["ABS_1", "DRY_COOLER_1", "CHW_PUMP_1", "CW_PUMP_1"], "ENGINE_2", ["ABS performance / COP curve", "Dry-cooler performance curve", "Pump power curve"], true),
            "1.5": coolingUnitConfiguration(2, ["ABS_2", "DRY_COOLER_2", "CHW_PUMP_2", "CW_PUMP_2"], "ENGINE_2", ["ABS performance / COP curve", "Dry-cooler performance curve", "Pump power curve"], true)
        },
        implemented: false
    },
    "Chiller + Dry Cooler": {
        cooling_unit_capacities: {
            "1.5": coolingUnitConfiguration(1, ["CHILLER_1", "DRY_COOLER_1", "CHW_PUMP_1", "CW_PUMP_1"], "ENGINE_2", ["Chiller COP surface", "Dry-cooler performance curve", "Pump power curve"]),
            "2": coolingUnitConfiguration(2, ["CHILLER_2", "DRY_COOLER_2", "CHW_PUMP_2", "CW_PUMP_2"], "ENGINE_2", ["Chiller COP surface", "Dry-cooler performance curve", "Pump power curve"]),
            "4": coolingUnitConfiguration(3, ["CHILLER_3", "DRY_COOLER_3", "CHW_PUMP_3", "CW_PUMP_3"], "ENGINE_3", ["Chiller COP surface", "Dry-cooler performance curve", "Pump power curve"])
        },
        implemented: true
    },
    "ACC": {
        cooling_unit_capacities: {
            "1": coolingUnitConfiguration(1, ["ACC_1", "CHW_PUMP_1"], "ENGINE_2", ["ACC capacity and COP curves", "Pump power curve"]),
            "1.5": coolingUnitConfiguration(2, ["ACC_2", "CHW_PUMP_2"], "ENGINE_3", ["ACC capacity and COP curves", "Pump power curve"]),
            "2": coolingUnitConfiguration(3, ["ACC_3", "CHW_PUMP_3"], "ENGINE_3", ["ACC capacity and COP curves", "Pump power curve"])
        },
        implemented: false
    },
    "Chiller + Cooling Tower": {
        cooling_unit_capacities: {
            "2": coolingUnitConfiguration(2, ["CHILLER_2", "COOLING_TOWER_2", "CHW_PUMP_2", "CW_PUMP_2"], "ENGINE_2", ["Chiller COP surface", "Cooling-tower performance curve", "Pump power curve"]),
            "4": coolingUnitConfiguration(3, ["CHILLER_3", "COOLING_TOWER_3", "CHW_PUMP_3", "CW_PUMP_3"], "ENGINE_3", ["Chiller COP surface", "Cooling-tower performance curve", "Pump power curve"])
        },
        implemented: false
    },
    "ABS + Cooling Tower": {
        cooling_unit_capacities: {
            "1": coolingUnitConfiguration(1, ["ABS_1", "COOLING_TOWER_1", "CHW_PUMP_1", "CW_PUMP_1"], "ENGINE_2", ["ABS performance / COP curve", "Cooling-tower performance curve", "Pump power curve"], true),
            "1.5": coolingUnitConfiguration(2, ["ABS_2", "COOLING_TOWER_2", "CHW_PUMP_2", "CW_PUMP_2"], "ENGINE_2", ["ABS performance / COP curve", "Cooling-tower performance curve", "Pump power curve"], true),
            "2": coolingUnitConfiguration(3, ["ABS_3", "COOLING_TOWER_3", "CHW_PUMP_3", "CW_PUMP_3"], "ENGINE_3", ["ABS performance / COP curve", "Cooling-tower performance curve", "Pump power curve"], true)
        },
        implemented: false
    }
});
window.COOLING_SYSTEM_CONFIG = COOLING_SYSTEM_CONFIG;

const FRAMEWORK_DIAGNOSTIC_TOPOLOGIES = Object.freeze({
    "ACC": {
        topology_id: "acc",
        display_name: "ACC",
        equipment_ids: ["ACC_2", "CHW_PUMP_2", "CDU_2", "RTC_1&2", "MAU_1&2", "ELECTRICAL_DISTRIBUTION_2", "ENGINE_3", "ENGINE_RADIATOR_1"],
        performance_requirements: ["IT load profile", "EPW weather profile", "ACC_2 Solver_Curve", "CHW_PUMP_2 Solver_Curve", "MAU_1&2 Solver_Curve", "RTC_1&2 Solver_Curve", "CDU_2 Solver_Curve", "ELECTRICAL_DISTRIBUTION_2 Solver_Curve", "ENGINE_3 Solver_Curve", "ENGINE_RADIATOR_1 Solver_Curve"]
    },
    "Chiller + Dry Cooler": {
        topology_id: "chiller_dry_cooler",
        display_name: "Chiller + Dry Cooler",
        equipment_ids: ["CHILLER", "DRY_COOLER", "CDU", "CHW_PUMP", "MAU", "ELECTRICAL_DISTRIBUTION", "RTC"],
        performance_requirements: ["IT load profile", "EPW weather profile", "Chiller Solver_Curve", "Dry Cooler Solver_Curve", "CHW Pump Solver_Curve", "MAU Solver_Curve", "Electrical Distribution Solver_Curve", "RTC Solver_Curve"]
    },
    "Chiller + Cooling Tower": {
        topology_id: "chiller_cooling_tower",
        display_name: "Chiller + Cooling Tower",
        equipment_ids: ["CHILLER", "COOLING_TOWER", "CDU", "CHW_PUMP", "MAU", "ELECTRICAL_DISTRIBUTION", "RTC"],
        performance_requirements: ["IT load profile", "EPW weather profile", "Chiller Solver_Curve", "Cooling Tower Solver_Curve", "CHW Pump Solver_Curve", "MAU Solver_Curve", "Electrical Distribution Solver_Curve", "RTC Solver_Curve"]
    },
    "ABS + Dry Cooler": {
        topology_id: "abs_dry_cooler",
        display_name: "ABS + Dry Cooler",
        equipment_ids: ["ABS", "DRY_COOLER", "ENGINE_RADIATOR", "CDU", "CHW_PUMP", "MAU", "ENGINE", "ELECTRICAL_DISTRIBUTION", "RTC"],
        performance_requirements: ["IT load profile", "EPW weather profile", "ABS Solver_Curve", "Dry Cooler Solver_Curve", "Engine Radiator Solver_Curve", "CHW Pump Solver_Curve", "MAU Solver_Curve", "Engine Solver_Curve", "Electrical Distribution Solver_Curve", "RTC Solver_Curve"]
    },
    "ABS + Cooling Tower": {
        topology_id: "abs_cooling_tower",
        display_name: "ABS + Cooling Tower",
        equipment_ids: ["ABS", "COOLING_TOWER", "ENGINE_RADIATOR", "CDU", "CHW_PUMP", "MAU", "ENGINE", "ELECTRICAL_DISTRIBUTION", "RTC"],
        performance_requirements: ["IT load profile", "EPW weather profile", "ABS Solver_Curve", "Cooling Tower Solver_Curve", "Engine Radiator Solver_Curve", "CHW Pump Solver_Curve", "MAU Solver_Curve", "Engine Solver_Curve", "Electrical Distribution Solver_Curve", "RTC Solver_Curve"]
    }
});
window.FRAMEWORK_DIAGNOSTIC_TOPOLOGIES = FRAMEWORK_DIAGNOSTIC_TOPOLOGIES;

const DEFAULT_COOLING_SYSTEM_TYPE = "Chiller + Dry Cooler";
const DEFAULT_COOLING_UNIT_CAPACITY_MW = 2;
const DEFAULT_POWER_SOURCE = "Grid";
const DEFAULT_SCENARIO_KEY = "normal_75";
const SCENARIO_REGISTRY = Object.freeze({
    normal_75: {
        scenario_key: "normal_75",
        display_name: "Normal / 75% cooling operation",
        description: "Normal case with 4 energy modules operating.",
        active_energy_modules: 4,
        failure_count: 0,
        cooling_operation_ratio: 0.75,
        notes: "Normal case: 4 energy modules operating."
    },
    one_failure_three_active: {
        scenario_key: "one_failure_three_active",
        display_name: "1 Failure / 3 active energy modules",
        description: "Failure case with 4 IT modules supported by 3 active energy modules.",
        active_energy_modules: 3,
        failure_count: 1,
        cooling_operation_ratio: null,
        notes: "Failure case: 4 IT modules supported by 3 active energy modules."
    }
});
window.SCENARIO_REGISTRY = SCENARIO_REGISTRY;
const COOLING_MODEL_UNAVAILABLE_MESSAGE = "This cooling system configuration is available for selection, but the calculation model has not been implemented yet.";
const POWER_SOURCE_MODEL_UNAVAILABLE_MESSAGE = "This power source configuration is available for selection, but the calculation model has not been implemented yet.";
const CHECKED_DEFAULT_CURVE_FILES = new Set();
const AVAILABLE_DEFAULT_CURVE_FILES = new Set();

const elStatus = document.getElementById("status");
const elLog = document.getElementById("log");
const elIn = document.getElementById("jsonInput");
const elOut = document.getElementById("jsonOutput");
const elRuntimeErrorDetails = document.getElementById("runtimeErrorDetails");
const btnRun = document.getElementById("btnRun");
const btnExportHtmlReport = document.getElementById("btnExportHtmlReport");
const btnExportJson = document.getElementById("btnExportJson");
const elSolverDataStatus = document.getElementById("solverDataStatus");
const resultCharts = {};
const standardDataFiles = {
    itLoad: null,
    weather: null,
    dryCooler: null,
    chiller: null,
    electrical: null,
    pumps: null,
    fans: null
};
let standardSolverInput = null;
let preferStandardFiles = false;
let lastReportContext = null;
let scenarioResults = [];
window.scenario_results = scenarioResults;
let configurationLibraryData = null;
let lastAccCalculationEngineSelection = "acc_v2";
const equipmentPdfSpecs = {};
const CONFIGURATION_LIBRARY_DIRECT_CALCULATION_MODE = "acc_v2_direct_solver_curve_hourly";
const CONFIGURATION_LIBRARY_ACC_ENGINE = "acc_v2_configuration_library";
const CONFIGURATION_LIBRARY_PYODIDE_ROOT = "Configuration Library";
const DIRECT_MODE_PYTHON_MODULES = Object.freeze([
    "equipment_registry.py",
    "topology_registry.py",
    "ashrae_online_lookup.py",
    "ashrae_design_conditions.py",
    "ashrae_design_conditions_data.json",
    "configuration_library_scanner.py",
    "configuration_library_loader.py",
    "equipment_curve_reader.py",
    "equipment_curve_lookup.py",
    "equipment_engine.py",
    "unit_quantity.py",
    "configuration_direct_mode_audit.py",
    "acc_v2_curve_lookup.py",
    "acc_v2_curve_reader.py",
    "acc_v2_diagnostics.py",
    "acc_v2_engine.py"
]);

function log(msg) { elLog.textContent = msg; }
function pretty(obj) { return JSON.stringify(obj, null, 2); }

function setRunButtonsDisabled(disabled) {
    if (btnRun) btnRun.disabled = disabled;
    const runLibraryButton = document.getElementById("btnRunConfigurationLibrary");
    if (runLibraryButton) runLibraryButton.disabled = disabled || !configurationLibraryData;
}

function clearRuntimeErrorDetails() {
    if (!elRuntimeErrorDetails) return;
    elRuntimeErrorDetails.textContent = "";
    elRuntimeErrorDetails.style.display = "none";
}

function showRuntimeErrorDetails(message) {
    if (!elRuntimeErrorDetails) return;
    elRuntimeErrorDetails.textContent = String(message || "");
    elRuntimeErrorDetails.style.display = "block";
}

function formatRuntimeException(error) {
    if (!error) return "Unknown runtime error";
    const message = error.message ? String(error.message) : String(error);
    const stack = error.stack ? String(error.stack) : "";
    return stack && !stack.includes(message) ? `${message}\n${stack}` : (stack || message);
}

async function ensurePyodideReady() {
    if (pyodide && window.pyodideReady) return pyodide;
    if (pyodideReadyPromise) return pyodideReadyPromise;

    pyodideReadyPromise = (async () => {
        try {
            if (elStatus) elStatus.textContent = "Loading calculation engine...";
            setSolverDataStatus("Loading calculation engine...", "info");
            if (!pyodide) {
                console.time("loadPyodide");
                try {
                    pyodide = await loadPyodide();
                } finally {
                    console.timeEnd("loadPyodide");
                }
            }

            if (!pyodideDirectModeModulesLoaded) {
                console.time("fetch/write module loop");
                try {
                    for (const moduleName of DIRECT_MODE_PYTHON_MODULES) {
                        await loadPythonModuleIntoPyodide(moduleName);
                    }
                    pyodideDirectModeModulesLoaded = true;
                } finally {
                    console.timeEnd("fetch/write module loop");
                }
            }

            if (!pyodideSolverLoaded) {
                console.time("solver.py runPythonAsync");
                try {
                    const pyText = await fetch("./solver.py", { cache: "no-store" }).then(r => r.text());
                    await pyodide.runPythonAsync(pyText);
                    pyodideSolverLoaded = true;
                } finally {
                    console.timeEnd("solver.py runPythonAsync");
                }
            }

            if (!pyodideBenchmarkLoaded) {
                console.time("benchmark runPythonAsync");
                try {
                    const benchmarkText = await fetch("./acc_excel_benchmark.py").then(r => r.text());
                    await pyodide.runPythonAsync(benchmarkText);
                    ensureAccExcelReplicatedHourlyLoaded();
                    pyodideBenchmarkLoaded = true;
                } finally {
                    console.timeEnd("benchmark runPythonAsync");
                }
            }

            window.pyodide = pyodide;
            window.pyodideReady = true;
            if (elStatus) elStatus.textContent = "Calculation engine ready.";
            setSolverDataStatus("Calculation engine ready.", "ok");
            return pyodide;
        } catch (error) {
            window.pyodideReady = false;
            pyodideReadyPromise = null;
            if (elStatus) elStatus.textContent = "Calculation engine failed.";
            setSolverDataStatus(`Calculation engine failed: ${String(error.message || error)}`, "error");
            throw error;
        }
    })();
    return pyodideReadyPromise;
}

async function loadPythonModuleIntoPyodide(fileName) {
    const text = await fetch(`./${fileName}`).then(response => {
        if (!response.ok) throw new Error(`Failed to load ${fileName}`);
        return response.text();
    });
    pyodide.FS.writeFile(fileName, text);
}

function ensurePyodideDir(path) {
    if (!pyodide) throw new Error("Pyodide is not loaded.");
    const parts = String(path || "").split("/").filter(Boolean);
    let current = "";
    parts.forEach(part => {
        current = current ? `${current}/${part}` : part;
        try {
            pyodide.FS.stat(current);
        } catch (_) {
            pyodide.FS.mkdir(current);
        }
    });
}

function writeBinaryFileToPyodide(path, arrayBuffer) {
    const directory = String(path || "").split("/").slice(0, -1).join("/");
    if (directory) ensurePyodideDir(directory);
    pyodide.FS.writeFile(path, new Uint8Array(arrayBuffer));
}

function ensureAccExcelReplicatedHourlyLoaded() {
    pyodide.runPython(`
if "compute_acc_excel_replicated_hourly" not in globals():
    raise RuntimeError("compute_acc_excel_replicated_hourly is not loaded")
`);
}

function getSelectedAccCalculationEngine() {
    return "acc_v2";
}

function applyAccCalculationEngineSelection(inputObj, calculationMode = CONFIGURATION_LIBRARY_DIRECT_CALCULATION_MODE, configurationPath = null) {
    lastAccCalculationEngineSelection = getSelectedAccCalculationEngine();
    if (!inputObj || typeof inputObj !== "object") {
        return inputObj;
    }
    inputObj.run_mode = calculationMode || CONFIGURATION_LIBRARY_DIRECT_CALCULATION_MODE;
    inputObj.acc_engine = CONFIGURATION_LIBRARY_ACC_ENGINE;
    inputObj.feature_flags = inputObj.feature_flags && typeof inputObj.feature_flags === "object"
        ? inputObj.feature_flags
        : {};
    inputObj.feature_flags.acc_v2_enabled = true;
    inputObj.acc_v2 = inputObj.acc_v2 && typeof inputObj.acc_v2 === "object"
        ? inputObj.acc_v2
        : {};
    inputObj.acc_v2.enabled = true;
    const activeConfigurationPath = configurationPath || inputObj.configuration_path || inputObj.configuration_name || inputObj.project?.name;
    if (activeConfigurationPath) inputObj.acc_v2.configuration_path = activeConfigurationPath;
    return inputObj;
}

function getAccEngineUsedLabel(outputObj) {
    return "ACC V2 Configuration Library Engine";
}

function isConfigurationLibraryAccV2DirectResult(outputObj = {}, inputObj = null) {
    const output = outputObj && typeof outputObj === "object" ? outputObj : {};
    const input = inputObj && typeof inputObj === "object" ? inputObj : {};
    const annual = output.annual_results && typeof output.annual_results === "object" ? output.annual_results : {};
    const firstHour = Array.isArray(output.hourly_results) && output.hourly_results.length ? output.hourly_results[0] : {};
    const calculationMode = output.calculation_mode || annual.calculation_mode || output.project?.calculation_mode || input.project?.calculation_mode;
    const benchmarkMode = ["excel_benchmark_compatible", "excel_replicated_hourly", "experimental_acc_hourly_shape"].includes(String(calculationMode || ""));
    const accV2Enabled = input.acc_engine === CONFIGURATION_LIBRARY_ACC_ENGINE
        || input.feature_flags?.acc_v2_enabled === true
        || input.acc_v2?.enabled === true
        || Boolean(configurationLibraryData);
    const libraryDirect = input.run_mode === CONFIGURATION_LIBRARY_DIRECT_CALCULATION_MODE
        || input.acc_engine === CONFIGURATION_LIBRARY_ACC_ENGINE
        || Boolean(input.library_context)
        || Boolean(input.configuration_library)
        || Boolean(configurationLibraryData);
    const accCurveSource = annual.acc_curve_source || firstHour.acc_curve_source;
    const usesConfigurationCurve = ["acc_v2_solver_curve_direct", "configuration_library_solver_curve"].includes(String(accCurveSource || ""));
    const project8760 = calculationMode === "project_8760" || (Array.isArray(output.hourly_results) && output.hourly_results.length > 1);
    return !benchmarkMode && accV2Enabled && libraryDirect && project8760 && usesConfigurationCurve;
}

function getCoolingSystemSelection() {
    const type = document.getElementById("coolingSystemType")?.value || DEFAULT_COOLING_SYSTEM_TYPE;
    const capacityMw = Number(document.getElementById("coolingUnitCapacity")?.value || DEFAULT_COOLING_UNIT_CAPACITY_MW);
    const powerSource = document.getElementById("powerSource")?.value || DEFAULT_POWER_SOURCE;
    const scenarioKey = document.getElementById("scenarioSelect")?.value || DEFAULT_SCENARIO_KEY;
    const scenario = SCENARIO_REGISTRY[scenarioKey] || SCENARIO_REGISTRY[DEFAULT_SCENARIO_KEY];
    const config = COOLING_SYSTEM_CONFIG[type];
    const unitConfig = config?.cooling_unit_capacities?.[String(capacityMw)];
    const powerConfig = unitConfig?.power_sources?.[powerSource];
    return { type, capacityMw, powerSource, scenarioKey, scenario, config, unitConfig, powerConfig };
}

function isConfigurationLibraryDirectModeActive(selection = getCoolingSystemSelection()) {
    return Boolean(configurationLibraryData)
        && configurationLibraryData.cooling_system_type === selection.type
        && Number(configurationLibraryData.cooling_unit_capacity_mw) === Number(selection.capacityMw)
        && configurationLibraryData.power_source === selection.powerSource;
}

function equipmentIdDisplayName(equipmentId) {
    const parts = String(equipmentId).split("_");
    const modelNumber = parts.pop();
    const type = parts.join("_");
    const typeNames = {
        CHW_PUMP: "CHW Pump",
        CW_PUMP: "CW Pump",
        DRY_COOLER: "Dry Cooler",
        COOLING_TOWER: "Cooling Tower",
        ENGINE_RADIATOR: "Engine Radiator",
        SMOKE_WATER_HX: "Smoke-Water HX",
        CHILLER: "Chiller",
        ENGINE: "Engine"
    };
    return `${typeNames[type] || type} ${modelNumber}`;
}

function curveTypeForEquipmentId(equipmentId) {
    if (/^(CHW|CW)_PUMP_/.test(equipmentId)) return "pump_power_curve";
    const rules = [
        [/^ACC_/, "acc_performance_curve"], [/^ABS_/, "abs_performance_curve"],
        [/^CHILLER_/, "chiller_cop_curve"], [/^DRY_COOLER_/, "dry_cooler_performance_curve"],
        [/^COOLING_TOWER_/, "cooling_tower_performance_curve"], [/^ENGINE_RADIATOR_/, "engine_radiator_performance_curve"],
        [/^ENGINE_/, "engine_efficiency_curve"], [/^SMOKE_WATER_HX_/, "heat_exchanger_performance_curve"],
        [/^CDU_/, "cdu_performance_curve"], [/^RTC_/, "rtc_performance_curve"], [/^MAU_/, "mau_performance_curve"]
    ];
    return rules.find(([pattern]) => pattern.test(equipmentId))?.[1] || "equipment_performance_curve";
}

function curveDirectoryForEquipmentId(equipmentId) {
    if (/^(CHW|CW|HW)_PUMP_/.test(equipmentId)) return "pump";
    const rules = [
        [/^DRY_COOLER_/, "dry_cooler"], [/^COOLING_TOWER_/, "cooling_tower"],
        [/^ENGINE_RADIATOR_/, "engine_radiator"], [/^SMOKE_WATER_HX_/, "heat_exchanger"],
        [/^CHILLER_/, "chiller"], [/^ENGINE_/, "engine"], [/^ACC_/, "acc"],
        [/^ABS_/, "abs"], [/^CDU_/, "cdu"], [/^RTC_/, "rtc"], [/^MAU_/, "mau"]
    ];
    return rules.find(([pattern]) => pattern.test(equipmentId))?.[1] || "other";
}

function buildFrontendDefaultCurvePath(equipmentId) {
    return `data/performance_curves/${curveDirectoryForEquipmentId(equipmentId)}/${equipmentId}.xlsx`;
}

function normalizeEquipmentCurveKey(value) {
    return String(value || "").toUpperCase().replace(/[^A-Z0-9]+/g, "_").replace(/^_+|_+$/g, "").replace(/_+/g, "_");
}

function equipmentCurveFamily(value) {
    return normalizeEquipmentCurveKey(value).replace(/_?\d+$/, "").replace(/_+$/, "");
}

const DEFAULT_DIRECT_MODE_EQUIPMENT_ALIASES = Object.freeze({
    RTC_1: "RTC_1&2",
    RTC_2: "RTC_1&2",
    MAU_1: "MAU_1&2",
    MAU_2: "MAU_1&2",
    ENGINE_2: "ENGINE_3",
    ENGINE_RADIATOR_2: "ENGINE_RADIATOR_1"
});
let directModeEquipmentAliases = { ...DEFAULT_DIRECT_MODE_EQUIPMENT_ALIASES };

const DIRECT_MODE_EQUIPMENT_ORDER = Object.freeze(["ACC_2", "CHW_PUMP_2", "CDU_2", "RTC_1&2", "MAU_1&2", "ELECTRICAL_DISTRIBUTION_2", "ENGINE_3", "ENGINE_RADIATOR_1"]);
const DIRECT_MODE_WHITE_SPACE_EQUIPMENT = Object.freeze(["CDU_2", "RTC_1&2", "MAU_1&2"]);
const DIRECT_MODE_GRAY_SPACE_EQUIPMENT = Object.freeze(["ACC_2", "CHW_PUMP_2", "ELECTRICAL_DISTRIBUTION_2", "ENGINE_3", "ENGINE_RADIATOR_1"]);
const DIRECT_MODE_CURVE_METADATA_FIELDS = Object.freeze({
    ACC_2: { source: "acc_curve_source", type: null },
    CHW_PUMP_2: { source: "chw_pump_curve_source", type: null },
    CDU_2: { source: "cdu_curve_source", type: null },
    "RTC_1&2": { source: "rtc_curve_source", type: null },
    "MAU_1&2": { source: "mau_curve_source", type: null },
    ELECTRICAL_DISTRIBUTION_2: { source: "electrical_distribution_curve_source", type: "electrical_distribution_curve_type" },
    ENGINE_3: { source: "engine_curve_source", type: "engine_curve_type" },
    ENGINE_RADIATOR_1: { source: "engine_radiator_curve_source", type: "engine_radiator_curve_type" }
});

const DIRECT_MODE_EQUIPMENT_CANDIDATES = Object.freeze({
    "RTC_1&2": ["RTC_1&2", "RTC_2", "rtc", "auxiliary_load"],
    "MAU_1&2": ["MAU_1&2", "MAU_2", "mau", "terminal_fan"],
    ENGINE_3: ["ENGINE_3", "ENGINE_2", "engine", "generator", "gas_engine"],
    ENGINE_RADIATOR_1: ["ENGINE_RADIATOR_1", "ENGINE_RADIATOR_2", "engine_radiator", "radiator", "heat_exchanger"]
});

function resolveDirectModeEquipmentId(equipmentId) {
    const text = String(equipmentId || "");
    return directModeEquipmentAliases[text] || directModeEquipmentAliases[text.toUpperCase()] || equipmentId;
}

function resolveFrontendEquipmentId(equipmentId) {
    return resolveDirectModeEquipmentId(equipmentId);
}

async function loadConfigurationEquipmentAliases() {
    const aliasUrl = new URL("Configuration Library/equipment_aliases.json", document.baseURI);
    try {
        const response = await fetch(aliasUrl, { cache: "no-store" });
        if (!response.ok) throw new Error(`Could not load ${aliasUrl.href} (HTTP ${response.status}).`);
        const loaded = await response.json();
        if (loaded && typeof loaded === "object" && !Array.isArray(loaded)) {
            directModeEquipmentAliases = { ...DEFAULT_DIRECT_MODE_EQUIPMENT_ALIASES, ...loaded };
        }
    } catch (_) {
        directModeEquipmentAliases = { ...DEFAULT_DIRECT_MODE_EQUIPMENT_ALIASES };
    }
    return directModeEquipmentAliases;
}

function findLibraryEquipmentPackage(data, equipmentId) {
    const resolvedId = resolveDirectModeEquipmentId(equipmentId);
    const packages = Object.entries(data?.equipment || {});
    const candidateIds = DIRECT_MODE_EQUIPMENT_CANDIDATES[resolvedId] || [resolvedId];
    for (const candidate of candidateIds) {
        const normalized = normalizeEquipmentCurveKey(candidate);
        const exact = packages.find(([key, item]) =>
            normalizeEquipmentCurveKey(key) === normalized ||
            normalizeEquipmentCurveKey(item?.equipment_id) === normalized
        );
        if (exact) return { resolvedId, packageKey: exact[0], equipmentPackage: exact[1] };
    }
    const family = equipmentCurveFamily(resolvedId);
    const familyMatch = packages.find(([, item]) => equipmentCurveFamily(item?.equipment_id) === family);
    if (familyMatch) return { resolvedId, packageKey: familyMatch[0], equipmentPackage: familyMatch[1] };
    return { resolvedId, packageKey: null, equipmentPackage: null };
}

function isDirectModeResolvedAlias(equipmentFolder, equipmentId) {
    if (!equipmentFolder || !equipmentId) return false;
    const resolvedId = resolveDirectModeEquipmentId(equipmentId);
    const normalizedFolder = normalizeEquipmentCurveKey(equipmentFolder);
    const normalizedResolved = normalizeEquipmentCurveKey(resolvedId);
    if (normalizedFolder === normalizedResolved) return true;
    return (DIRECT_MODE_EQUIPMENT_CANDIDATES[resolvedId] || [resolvedId])
        .some(candidate => normalizeEquipmentCurveKey(candidate) === normalizedFolder);
}

function libraryCurveForEquipment(equipmentId) {
    const { resolvedId, equipmentPackage } = findLibraryEquipmentPackage(configurationLibraryData, equipmentId);
    if (!equipmentPackage) return null;
    const scenario = document.getElementById("scenarioSelect")?.value === "one_failure_three_active" ? "Failure" : "Normal";
    const selected = selectLibrarySolverCurve(equipmentPackage, scenario);
    if (!selected.sheet_name) return null;
    return { resolvedId, equipmentPackage, selected };
}

function uploadedCurveForEquipment(equipmentId) {
    let file = null;
    if (/^CHILLER_/.test(equipmentId)) file = standardDataFiles.chiller;
    else if (/^DRY_COOLER_/.test(equipmentId)) file = standardDataFiles.dryCooler;
    else if (/^(CHW|CW)_PUMP_/.test(equipmentId)) file = standardDataFiles.pumps;
    else if (/^(RTC|MAU)_/.test(equipmentId)) file = standardDataFiles.fans;
    return file ? (file.source_file || "user_uploaded_curve") : null;
}

function buildSelectedCurveSources(powerConfig) {
    const equipmentIds = [
        ...(powerConfig?.white_space_equipment || []),
        ...(powerConfig?.gray_space_equipment || [])
    ];
    return Object.fromEntries(equipmentIds.map(equipmentId => {
        const uploaded = uploadedCurveForEquipment(equipmentId);
        const libraryCurve = libraryCurveForEquipment(equipmentId);
        const defaultFile = buildFrontendDefaultCurvePath(equipmentId);
        const defaultFilename = `${equipmentId}.xlsx`;
        const hasDefault = AVAILABLE_DEFAULT_CURVE_FILES.has(defaultFile);
        return [equipmentId, {
            source_type: uploaded ? "uploaded" : libraryCurve ? "library" : hasDefault ? "default" : "missing",
            file: uploaded || libraryCurve?.equipmentPackage.package_path || (hasDefault ? defaultFile : null),
            source_equipment_id: libraryCurve?.equipmentPackage.equipment_id || null,
            source_sheet: libraryCurve?.selected.sheet_name || null,
            default_curve_directory: `data/performance_curves/${curveDirectoryForEquipmentId(equipmentId)}/`,
            default_curve_filename: defaultFilename,
            default_curve_path: defaultFile,
            curve_type: curveTypeForEquipmentId(equipmentId),
            warning: uploaded || libraryCurve ? null : `Default curve file not yet available: ${defaultFile}`
        }];
    }));
}

async function checkSelectedDefaultCurveFiles(powerConfig) {
    const equipmentIds = [...(powerConfig?.white_space_equipment || []), ...(powerConfig?.gray_space_equipment || [])];
    const pending = equipmentIds.filter(equipmentId => !libraryCurveForEquipment(equipmentId)).map(buildFrontendDefaultCurvePath)
        .filter(path => !CHECKED_DEFAULT_CURVE_FILES.has(path));
    if (!pending.length) return;
    await Promise.all(pending.map(async path => {
        CHECKED_DEFAULT_CURVE_FILES.add(path);
        try {
            const response = await fetch(path, { method: "HEAD", cache: "no-store" });
            if (response.ok) AVAILABLE_DEFAULT_CURVE_FILES.add(path);
        } catch (_) {
            // Missing/unreachable defaults remain warnings; uploads still work.
        }
    }));
    renderCoolingSystemSelection();
}

function renderCoolingSystemSelection() {
    const { type, capacityMw, powerSource, scenario, config, powerConfig } = getCoolingSystemSelection();
    const directModeActive = isConfigurationLibraryDirectModeActive({ type, capacityMw, powerSource });
    const renderList = (id, values) => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = values.map(value => `<li>${esc(value)}</li>`).join("");
    };
    renderList("whiteSpaceEquipmentList", directModeActive
        ? DIRECT_MODE_WHITE_SPACE_EQUIPMENT
        : (powerConfig?.white_space_equipment || []).map(equipmentIdDisplayName));
    renderList("graySpaceEquipmentList", directModeActive
        ? DIRECT_MODE_GRAY_SPACE_EQUIPMENT
        : (powerConfig?.gray_space_equipment || []).map(equipmentIdDisplayName));
    const curveSources = directModeActive ? {} : buildSelectedCurveSources(powerConfig);
    const curveRows = directModeActive ? FRAMEWORK_DIAGNOSTIC_TOPOLOGIES.ACC.performance_requirements.map(name => `Required: ${name}`) : [
        ...(powerConfig?.required_curves || []).map(name => `Required: ${name}`),
        ...Object.entries(curveSources).map(([equipmentId, source]) => {
            const status = source.source_type === "uploaded" ? "Using uploaded curve" :
                source.source_type === "library" ? `Using Configuration Library Solver_Curve (${source.source_equipment_id} / ${source.source_sheet})` :
                source.source_type === "default" ? `Using default curve (${source.default_curve_filename})` : "Missing Solver_Curve";
            return `${equipmentIdDisplayName(equipmentId)} — ${status}`;
        })
    ];
    renderList("coolingPerformanceCurveList", curveRows);
    checkSelectedDefaultCurveFiles(powerConfig);
    const status = document.getElementById("coolingSystemStatus");
    if (status) {
        const libraryRunnable = directModeActive;
        const runnable = (config?.implemented && powerSource === DEFAULT_POWER_SOURCE) || libraryRunnable;
        status.textContent = runnable ? `${type}, ${capacityMw} MW, ${powerSource}, ${scenario.display_name}: ${libraryRunnable ? "Configuration Library calculation model" : "calculation model"} available.`
            : powerSource !== DEFAULT_POWER_SOURCE ? POWER_SOURCE_MODEL_UNAVAILABLE_MESSAGE : COOLING_MODEL_UNAVAILABLE_MESSAGE;
        status.style.color = runnable ? "#059669" : "#b45309";
    }
    renderScenarioSummary();
    renderFrameworkDiagnosticsPanel();
}

function renderScenarioSummary() {
    const panel = document.getElementById("scenarioSummaryPanel");
    if (isConfigurationLibraryDirectModeActive()) {
        if (panel) panel.style.display = "none";
        return;
    }
    if (panel) panel.style.display = "block";
    const body = document.getElementById("scenarioSummaryBody");
    if (!body) return;
    const selection = getCoolingSystemSelection();
    const scheme = `${selection.type} / ${selection.capacityMw} MW / ${selection.powerSource}`;
    const sizing = calculateFrontendUnitRequirements(getProjectReportInfo().capacityMw, selection.capacityMw);
    body.innerHTML = Object.values(SCENARIO_REGISTRY).map(scenario => {
        const result = scenarioResults.find(item => item.scenario_key === scenario.scenario_key);
        const annualPue = result?.annual_results?.annual_average_PUE;
        const activeEngines = selection.powerSource === "Gas Engine" && sizing
            ? (scenario.scenario_key === "normal_75" ? sizing.installedUnits : sizing.requiredUnits)
            : "—";
        return `<tr>
            <td>${esc(scheme)}</td><td>${esc(scenario.display_name)}</td><td>—</td>
            <td>${activeEngines}</td><td>—</td><td>—</td>
            <td>${Number.isFinite(Number(annualPue)) ? fmtNumber(annualPue, 3) : "—"}</td>
        </tr>`;
    }).join("");
}

function calculateFrontendUnitRequirements(totalItCapacityMw, coolingUnitCapacityMw) {
    const total = Number(totalItCapacityMw);
    const unit = Number(coolingUnitCapacityMw);
    if (!(total > 0) || !(unit > 0)) return null;
    const requiredUnits = Math.ceil(total / unit);
    return {
        requiredUnits,
        installedUnits: requiredUnits + 1,
        normalActiveUnits: requiredUnits + 1,
        failureActiveUnits: requiredUnits,
        indoorActiveUnits: requiredUnits + 1,
        redundancy: "N+1"
    };
}

function getManualUnitNumber(inputId) {
    const value = Number(document.getElementById(inputId)?.value);
    return Number.isFinite(value) && value >= 0 ? Math.floor(value) : null;
}

function getUnitQuantitySelection(sizing) {
    const mode = (document.getElementById("unitQuantityMode")?.value || "auto").toLowerCase() === "manual" ? "manual" : "auto";
    const redundancy = document.getElementById("unitRedundancyMode")?.value || "auto";
    const requiredUnits = sizing?.requiredUnits ?? null;
    const autoInstalled = sizing?.installedUnits ?? null;
    const autoRunning = sizing?.normalActiveUnits ?? null;
    const autoStandby = autoInstalled !== null && autoRunning !== null ? Math.max(autoInstalled - autoRunning, 0) : null;
    if (mode === "auto") {
        return {
            mode: "auto",
            redundancy: "auto",
            required_units: requiredUnits,
            installed_units: autoInstalled,
            running_units: autoRunning,
            standby_units: autoStandby
        };
    }
    let installed = getManualUnitNumber("manualInstalledUnits");
    let running = getManualUnitNumber("manualRunningUnits");
    let standby = getManualUnitNumber("manualStandbyUnits");
    const required = requiredUnits ?? running ?? installed ?? 0;
    if (redundancy === "N") {
        installed = required;
        running = required;
        standby = 0;
    } else if (redundancy === "N+1") {
        installed = required + 1;
        running = required;
        standby = 1;
    } else if (redundancy === "N+2") {
        installed = required + 2;
        running = required;
        standby = 2;
    } else {
        installed = installed ?? autoInstalled ?? required;
        running = running ?? Math.max(installed - (standby ?? 0), 0);
        standby = standby ?? Math.max(installed - running, 0);
    }
    return {
        mode: "manual",
        redundancy: redundancy === "auto" ? "custom" : redundancy,
        required_units: requiredUnits,
        installed_units: installed,
        running_units: running,
        standby_units: standby
    };
}

function renderUnitQuantityStatus(unitQuantity) {
    const status = document.getElementById("unitQuantityStatus");
    if (!status) return;
    if (!unitQuantity || unitQuantity.required_units === null) {
        status.textContent = "Enter Total IT Capacity to derive unit quantity.";
        return;
    }
    status.textContent = `${unitQuantity.mode === "manual" ? "Manual" : "Auto"}: required ${unitQuantity.required_units}, installed ${unitQuantity.installed_units}, running ${unitQuantity.running_units}, standby ${unitQuantity.standby_units}, redundancy ${unitQuantity.redundancy}.`;
}

function frameworkEquipmentIdFromFolder(equipmentFolder) {
    const raw = String(equipmentFolder || "");
    const upper = raw.toUpperCase();
    if (upper === "RTC_1&2") return "RTC_1&2";
    if (upper === "MAU_1&2") return "MAU_1&2";
    const normalized = upper.replace(/[^A-Z0-9]+/g, "_").replace(/_+\d+$/, "").replace(/^_+|_+$/g, "");
    const rules = [
        [/^ELECTRICAL_DISTRIBUTION/, "ELECTRICAL_DISTRIBUTION_2"],
        [/^ENGINE_RADIATOR/, "ENGINE_RADIATOR_1"],
        [/^SMOKE_WATER_HX/, "ENGINE_RADIATOR_1"],
        [/^HEAT_EXCHANGER/, "ENGINE_RADIATOR_1"],
        [/^COOLING_TOWER/, "COOLING_TOWER"],
        [/^DRY_COOLER/, "DRY_COOLER"],
        [/^CHW_PUMP|^CW_PUMP|^PUMP/, "CHW_PUMP_2"],
        [/^ACC/, "ACC_2"],
        [/^CDU/, "CDU_2"],
        [/^ENGINE/, "ENGINE_3"],
        [/^CHILLER/, "CHILLER"],
        [/^ABS/, "ABS"],
        [/^MAU/, "MAU_1&2"],
        [/^RTC/, "RTC_1&2"]
    ];
    return rules.find(([pattern]) => pattern.test(normalized))?.[1] || null;
}

function tentativeFrameworkMapping(equipmentFolder, equipmentId) {
    if (String(equipmentFolder || "") === String(equipmentId || "")) return null;
    if (isDirectModeResolvedAlias(equipmentFolder, equipmentId)) return null;
    return `${equipmentFolder} -> ${equipmentId}`;
}

function buildFrameworkDiagnosticsPreview() {
    const { type, capacityMw, powerSource } = getCoolingSystemSelection();
    const topology = FRAMEWORK_DIAGNOSTIC_TOPOLOGIES[type] || null;
    const solverMode = topology?.topology_id === "acc" ? "acc_hourly" : "placeholder";
    const libraryEquipmentFolders = Object.keys(configurationLibraryData?.equipment || {});
    const detectedEquipmentIds = [];
    const tentativeMappings = [];
    const unexpectedFolders = [];
    libraryEquipmentFolders.forEach(folder => {
        const equipmentId = frameworkEquipmentIdFromFolder(folder);
        if (!equipmentId) {
            unexpectedFolders.push(folder);
            return;
        }
        if (!detectedEquipmentIds.includes(equipmentId)) detectedEquipmentIds.push(equipmentId);
        const tentative = tentativeFrameworkMapping(folder, equipmentId);
        if (tentative) tentativeMappings.push(tentative);
    });
    const expectedEquipmentIds = topology?.equipment_ids || [];
    const missingEquipmentIds = configurationLibraryData
        ? expectedEquipmentIds.filter(equipmentId => !detectedEquipmentIds.includes(equipmentId))
        : [];
    const recommendedActions = [
        ...missingEquipmentIds.map(equipmentId => `Add missing equipment folder: ${equipmentId}`),
        ...tentativeMappings.map(mapping => `Review tentative mapping: ${mapping}`),
        ...unexpectedFolders.map(folder => `Confirm equipment folder meaning: ${folder}`)
    ];
    const validationStatus = !topology ? "invalid"
        : !configurationLibraryData ? "placeholder"
        : (missingEquipmentIds.length || tentativeMappings.length || unexpectedFolders.length ? "warning" : "valid");
    return {
        notice: "Frontend diagnostics preview — not connected to calculation.",
        topology: topology?.display_name || "Unknown",
        topology_id: topology?.topology_id || "unknown",
        cooling_system_type: type,
        power_source: powerSource,
        unit_capacity: `${capacityMw} MW`,
        solver_mode: solverMode,
        equipment_detected: configurationLibraryData ? detectedEquipmentIds : expectedEquipmentIds,
        missing_equipment: configurationLibraryData ? missingEquipmentIds : ["Not evaluated until Configuration Library is loaded"],
        performance_requirements: topology?.performance_requirements || [],
        validation_status: validationStatus,
        recommended_next_actions: recommendedActions.length ? recommendedActions : ["No action required for diagnostics preview"],
        tentative_mappings: tentativeMappings,
        configuration_name: configurationLibraryData?.configuration_name || "Current frontend selection"
    };
}

function diagnosticsStatusClass(status) {
    return ["valid", "warning", "invalid", "placeholder"].includes(status) ? status : "placeholder";
}

function renderDiagnosticsValue(value) {
    if (Array.isArray(value)) {
        if (!value.length) return "—";
        return `<ul style="margin:0; padding-left:18px;">${value.map(item => `<li>${esc(item)}</li>`).join("")}</ul>`;
    }
    return esc(value ?? "—");
}

function renderFrameworkDiagnosticsPanel() {
    const grid = document.getElementById("frameworkDiagnosticsGrid");
    if (!grid) return;
    const diagnostics = buildFrameworkDiagnosticsPreview();
    const statusClass = diagnosticsStatusClass(diagnostics.validation_status);
    const rows = [
        ["Detected Topology", `${diagnostics.topology} (${diagnostics.topology_id})`],
        ["Cooling System Type", diagnostics.cooling_system_type],
        ["Power Source", diagnostics.power_source],
        ["Unit Capacity", diagnostics.unit_capacity],
        ["Solver Mode", diagnostics.solver_mode],
        ["Equipment Detected", diagnostics.equipment_detected],
        ["Missing Equipment", diagnostics.missing_equipment],
        ["Performance Requirements", diagnostics.performance_requirements],
        ["Validation Status", `<span class="diagnosticsBadge ${statusClass}">${diagnostics.validation_status}</span>`],
        ["Recommended Next Actions", diagnostics.recommended_next_actions]
    ];
    grid.innerHTML = rows.map(([label, value]) => `<div class="fileSlot">
        <div class="panelTitle">${esc(label)}</div>
        <div class="diagnosticsValue">${label === "Validation Status" ? value : renderDiagnosticsValue(value)}</div>
    </div>`).join("");
    const notice = document.getElementById("frameworkDiagnosticsNotice");
    if (notice) notice.textContent = `${diagnostics.notice} Source: ${diagnostics.configuration_name}.`;
}

function recordScenarioResult(scenarioKey, annualResults) {
    const scenario = SCENARIO_REGISTRY[scenarioKey] || SCENARIO_REGISTRY[DEFAULT_SCENARIO_KEY];
    scenarioResults = scenarioResults.filter(item => item.scenario_key !== scenario.scenario_key);
    scenarioResults.push({
        scenario_key: scenario.scenario_key,
        scenario_name: scenario.display_name,
        annual_results: annualResults || null
    });
    window.scenario_results = scenarioResults;
    renderScenarioSummary();
}

function resetScenarioResults() {
    scenarioResults = [];
    window.scenario_results = scenarioResults;
}

function updateCoolingUnitCapacityOptions(preferredCapacity) {
    const type = document.getElementById("coolingSystemType")?.value || DEFAULT_COOLING_SYSTEM_TYPE;
    const select = document.getElementById("coolingUnitCapacity");
    if (!select) return;
    const capacities = Object.keys(COOLING_SYSTEM_CONFIG[type]?.cooling_unit_capacities || {}).map(Number);
    select.innerHTML = capacities.map(value => `<option value="${value}">${value} MW</option>`).join("");
    const requested = Number(preferredCapacity);
    select.value = capacities.includes(requested) ? String(requested) : String(capacities[0]);
    renderCoolingSystemSelection();
}

function initCoolingSystemSelection() {
    const typeSelect = document.getElementById("coolingSystemType");
    const capacitySelect = document.getElementById("coolingUnitCapacity");
    const powerSourceSelect = document.getElementById("powerSource");
    const scenarioSelect = document.getElementById("scenarioSelect");
    if (!typeSelect || !capacitySelect || !powerSourceSelect || !scenarioSelect) return;
    typeSelect.innerHTML = Object.keys(COOLING_SYSTEM_CONFIG).map(type => `<option value="${type}">${type}</option>`).join("");
    typeSelect.value = DEFAULT_COOLING_SYSTEM_TYPE;
    powerSourceSelect.value = DEFAULT_POWER_SOURCE;
    scenarioSelect.innerHTML = Object.values(SCENARIO_REGISTRY)
        .map(scenario => `<option value="${scenario.scenario_key}">${scenario.display_name}</option>`).join("");
    scenarioSelect.value = DEFAULT_SCENARIO_KEY;
    updateCoolingUnitCapacityOptions(DEFAULT_COOLING_UNIT_CAPACITY_MW);
    typeSelect.addEventListener("change", () => {
        resetScenarioResults();
        updateCoolingUnitCapacityOptions();
        standardSolverInput = null;
        refreshStandardInputStatus();
    });
    capacitySelect.addEventListener("change", () => {
        resetScenarioResults();
        renderCoolingSystemSelection();
        standardSolverInput = null;
        refreshStandardInputStatus();
    });
    powerSourceSelect.addEventListener("change", () => {
        resetScenarioResults();
        renderCoolingSystemSelection();
        standardSolverInput = null;
        refreshStandardInputStatus();
    });
    scenarioSelect.addEventListener("change", () => {
        renderCoolingSystemSelection();
        if (configurationLibraryData) {
            configurationLibraryData.standardized_solver_input = buildFrontendSolverInputFromLibrary(configurationLibraryData);
            renderConfigurationLibrarySummary(configurationLibraryData);
        }
        standardSolverInput = null;
        refreshStandardInputStatus();
    });
}

function fmtNumber(value, digits = 2) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
    return Number(value).toLocaleString("zh-CN", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits
    });
}

function fmtInteger(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
    return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function destroyResultCharts() {
    Object.keys(resultCharts).forEach((key) => {
        if (resultCharts[key]) {
            resultCharts[key].destroy();
            resultCharts[key] = null;
        }
    });
}

function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function getProjectReportInfo() {
    const stageMap = {
        "概念设计": "Concept Design",
        "方案设计": "Schematic Design",
        "初步设计": "Design Development",
        "施工图设计": "Construction Documents",
        "运行评估": "Operational Assessment"
    };
    const textValue = (id) => {
        const el = document.getElementById(id);
        return el && el.value ? el.value.trim() : "";
    };
    const capacityRaw = optionalNonNegativeNumber("projectCapacityMwInput");
    const latitude = optionalCoordinateNumber("projectLatitudeInput", -90, 90);
    const longitude = optionalCoordinateNumber("projectLongitudeInput", -180, 180);
    const stage = textValue("projectStageInput");
    return {
        name: textValue("projectNameInput"),
        location: textValue("projectLocationInput"),
        latitude,
        longitude,
        capacityMw: capacityRaw,
        stage: stageMap[stage] || stage,
        version: textValue("projectVersionInput") || "v1.0"
    };
}

function updateProjectInfoStatus() {
    const status = document.getElementById("projectInfoStatus");
    if (!status) return;
    const info = getProjectReportInfo();
    const parts = [];
    if (info.name) parts.push(info.name);
    if (info.location) parts.push(info.location);
    if (info.latitude !== null && info.longitude !== null) parts.push(`${fmtNumber(info.latitude, 4)}, ${fmtNumber(info.longitude, 4)}`);
    if (info.capacityMw !== null) parts.push(`${fmtNumber(info.capacityMw, 1)} MW`);
    if (info.stage) parts.push(info.stage);
    if (info.version) parts.push(info.version);
    status.textContent = parts.length
        ? `${parts.join(" / ")}；仅用于报告展示`
        : "用于报告标题和项目摘要，不参与 PUE 计算。";
    status.style.color = parts.length ? "#059669" : "#6b7280";
}

function renderProjectInfoReportPanel() {
    const panel = document.getElementById("projectInfoReportPanel");
    if (!panel) return;
    const info = getProjectReportInfo();
    const rows = [
        ["项目名称", info.name],
        ["项目地点", info.location],
        ["项目坐标", info.latitude !== null && info.longitude !== null ? `${fmtNumber(info.latitude, 4)}, ${fmtNumber(info.longitude, 4)}` : ""],
        ["IT 设计容量", info.capacityMw !== null ? `${fmtNumber(info.capacityMw, 1)} MW` : ""],
        ["项目阶段", info.stage]
    ].filter(([, value]) => value !== "");
    if (!rows.length) {
        panel.style.display = "none";
        panel.innerHTML = "";
        return;
    }
    panel.style.display = "block";
    panel.innerHTML =
        "<b>项目基本信息</b><br>" +
        rows.map(([label, value]) => `${label}：<b>${value}</b>`).join("；") +
        "。该信息用于报告识别和规模说明，不参与 PUE 计算。";
}

function optionalNonNegativeNumber(id) {
    const el = document.getElementById(id);
    if (!el || el.value === "") return null;
    const value = Number(el.value);
    return Number.isFinite(value) && value >= 0 ? value : null;
}

function optionalFiniteNumber(id) {
    const el = document.getElementById(id);
    if (!el || el.value === "") return null;
    const value = Number(el.value);
    return Number.isFinite(value) ? value : null;
}

function getCoolingLoadHeatGainInput() {
    return {
        solarHeatGainMaxKw: optionalNonNegativeNumber("solarHeatGainMaxKw") ?? 0,
        solarDaytimeStartHour: optionalNonNegativeNumber("solarDaytimeStartHour") ?? 6,
        solarDaytimeEndHour: optionalNonNegativeNumber("solarDaytimeEndHour") ?? 18,
        otherAuxiliaryHeatGainKw: optionalNonNegativeNumber("otherAuxiliaryHeatGainKw") ?? 0,
        otherElectricalAuxiliaryPowerKw: optionalNonNegativeNumber("otherElectricalAuxiliaryPowerKw") ?? 0
    };
}

function getPeakDesignWeatherInput() {
    const manualSelected = document.getElementById("peakDesignWeatherManual")?.checked === true;
    const manualDryBulb = optionalFiniteNumber("manualPeakDesignDryBulbC");
    const proxyUrl = manualSelected ? null : "http://127.0.0.1:8011/api/ashrae_design_condition";
    return {
        peakDesignWeatherSource: manualSelected ? "manual" : "ashrae_auto",
        peakDesignOutdoorDryBulbC: manualSelected ? manualDryBulb : null,
        ashraeDesignConditionsUrl: proxyUrl
    };
}

function peakDesignSourceLabel(source) {
    const normalized = String(source || "").trim();
    if (normalized === "ASHRAE_online" || normalized === "ASHRAE Online") return "ASHRAE Online";
    if (normalized === "ASHRAE_online_proxy" || normalized === "ASHRAE Online Proxy") return "ASHRAE Online Proxy";
    if (normalized === "manual" || normalized === "User Defined Design Condition") return "Manual Override";
    if (normalized === "ASHRAE_local_cache" || normalized === "ASHRAE_local_fallback") return "Local ASHRAE Cache";
    return normalized || "ASHRAE Online";
}

function updatePeakDesignWeatherStatus(peakResults = null) {
    const status = document.getElementById("peakDesignWeatherStatus");
    const autoSummary = document.getElementById("peakDesignWeatherAutoSummary");
    const input = getPeakDesignWeatherInput();
    const source = peakResults?.peak_design_weather_source;
    const station = peakResults?.peak_design_weather_station;
    const stationId = peakResults?.peak_design_weather_station_id;
    const distance = peakResults?.peak_design_weather_station_distance_km;
    const dryBulb = peakResults?.peak_design_outdoor_dry_bulb_C;
    const lookupStatus = String(peakResults?.peak_design_lookup_status || "").toUpperCase();
    const lookupProvider = peakResults?.peak_design_lookup_provider || "ASHRAE_online";
    const lookupMethod = peakResults?.peak_design_lookup_method || "";
    const lookupFailureReason = peakResults?.peak_design_lookup_failure_reason;
    const onlineStatus = peakResults?.peak_design_online_status;
    const fallbackStatus = peakResults?.peak_design_fallback_status;
    const hasSuccessfulAshraeLookup = lookupStatus === "SUCCESS" && station && Number.isFinite(Number(dryBulb));
    const fallbackMessage = source !== "ASHRAE_online" && lookupFailureReason
        ? `; ASHRAE Online Lookup Failed: ${lookupFailureReason}; ${source === "ASHRAE_local_cache" ? "Using Local ASHRAE Cache fallback" : "Using Manual Override fallback"}`
        : "";
    const failedLookupMessage = lookupFailureReason
        ? `ASHRAE Online unavailable; Reason: ${lookupFailureReason}; Online Status: ${onlineStatus || "failed"}; Fallback Status: ${fallbackStatus || "manual_override_required"}; Manual override required`
        : "";
    if (autoSummary) {
        autoSummary.textContent = hasSuccessfulAshraeLookup
            ? `ASHRAE Online Lookup Successful; Lookup Status: ${lookupStatus || "UNKNOWN"}; Lookup Method: ${lookupMethod || "ASHRAE_web"}; Provider: ${peakDesignSourceLabel(lookupProvider)}; Lookup Source: ${peakDesignSourceLabel(source)}; Weather Station: ${station}; Station ID: ${stationId || "N/A"}; Distance: ${Number.isFinite(Number(distance)) ? fmtNumber(Number(distance), 1) + " km" : "N/A"}; Design DB Maximum: ${fmtNumber(Number(dryBulb), 1)} deg C${fallbackMessage}`
            : (failedLookupMessage || "Automatic ASHRAE Online Lookup; Lookup Status: pending; Weather Station: pending; Design DB Maximum: pending");
    }
    if (!status) return;
    if (input.peakDesignWeatherSource === "manual") {
        status.textContent = Number.isFinite(Number(input.peakDesignOutdoorDryBulbC))
            ? `Peak Design Condition: User Defined Design Condition, ${fmtNumber(Number(input.peakDesignOutdoorDryBulbC), 1)} deg C.`
            : "Peak Design Condition: Manual override selected. Enter Design Outdoor Dry Bulb.";
        status.style.color = Number.isFinite(Number(input.peakDesignOutdoorDryBulbC)) ? "#059669" : "#b45309";
        return;
    }
    status.textContent = hasSuccessfulAshraeLookup
        ? `Peak Design Weather: ASHRAE Online Lookup Successful; Lookup Status: ${lookupStatus || "UNKNOWN"}; Lookup Method: ${lookupMethod || "ASHRAE_web"}; Provider: ${peakDesignSourceLabel(lookupProvider)}; ${peakDesignSourceLabel(source)} / ${station} / ${fmtNumber(Number(dryBulb), 1)} deg C.${fallbackMessage}`
        : (failedLookupMessage || "Peak Design Condition: Automatic ASHRAE 20-year Extreme Design Condition.");
    status.style.color = "#059669";
}

function updateSolarGainStatus() {
    const status = document.getElementById("statusSolarGain");
    if (!status) return;
    const heat = getCoolingLoadHeatGainInput();
    status.textContent = `Solar Heat Gain ${fmtNumber(heat.solarHeatGainMaxKw, 1)} kW；Other Auxiliary Heat Gains ${fmtNumber(heat.otherAuxiliaryHeatGainKw, 1)} kW；Other Electrical Auxiliary Power ${fmtNumber(heat.otherElectricalAuxiliaryPowerKw, 1)} kW`;
    status.style.color = "#059669";
}

function refreshRestoredFileStatuses() {
    updateFileStatus("statusItLoad", standardDataFiles.itLoad ? "已从本地存档恢复" : "未加载", standardDataFiles.itLoad ? "ok" : "info");
    updateFileStatus("statusWeather", standardDataFiles.weather ? "已从本地存档恢复" : "未加载", standardDataFiles.weather ? "ok" : "info");
    updateFileStatus("statusDryCooler", standardDataFiles.dryCooler ? "已从本地存档恢复" : "未加载", standardDataFiles.dryCooler ? "ok" : "info");
    updateFileStatus("statusChiller", standardDataFiles.chiller ? "已从本地存档恢复" : "未加载", standardDataFiles.chiller ? "ok" : "info");
    updateFileStatus("statusElectrical", standardDataFiles.electrical ? "已从本地存档恢复" : "未加载", standardDataFiles.electrical ? "ok" : "info");
    updateFileStatus("statusPumps", standardDataFiles.pumps ? "已从本地存档恢复" : "未加载", standardDataFiles.pumps ? "ok" : "info");
    updateFileStatus("statusFans", standardDataFiles.fans ? "已从本地存档恢复" : "未加载", standardDataFiles.fans ? "ok" : "info");
}

function renderSolarGainReportPanel() {
    const panel = document.getElementById("solarGainReportPanel");
    if (!panel) return;
    const heat = getCoolingLoadHeatGainInput();
    if (!heat.solarHeatGainMaxKw && !heat.otherAuxiliaryHeatGainKw && !heat.otherElectricalAuxiliaryPowerKw) {
        panel.style.display = "none";
        panel.innerHTML = "";
        return;
    }
    const values = [];
    values.push(`Solar Heat Gain Max：<b>${fmtNumber(heat.solarHeatGainMaxKw, 1)} kW</b>`);
    values.push(`Daytime：<b>${fmtNumber(heat.solarDaytimeStartHour, 0)}:00-${fmtNumber(heat.solarDaytimeEndHour, 0)}:00</b>`);
    values.push(`Other Auxiliary Heat Gains：<b>${fmtNumber(heat.otherAuxiliaryHeatGainKw, 1)} kW</b>`);
    values.push(`Other Electrical Auxiliary Power：<b>${fmtNumber(heat.otherElectricalAuxiliaryPowerKw, 1)} kW</b>`);
    panel.style.display = "block";
    panel.innerHTML =
        "<b>Heat Gains / Auxiliary</b><br>" +
        values.join("；") +
        "。Solar and other auxiliary heat gains are included in Total Cooling Load; other electrical auxiliary power contributes directly to Facility Energy and PUE.";
}

function summarizeNumericArray(values) {
    const nums = Array.isArray(values) ? values.map(Number).filter(Number.isFinite) : [];
    if (!nums.length) return null;
    const sum = nums.reduce((total, value) => total + value, 0);
    return {
        count: nums.length,
        min: Math.min(...nums),
        max: Math.max(...nums),
        avg: sum / nums.length,
        sum
    };
}

function extractEpwPeriodFromFileName(fileName) {
    const text = String(fileName || "");
    const tmyMatch = text.match(/(?:^|[\s._-])(TMYx?|IWEC[0-9]?|CSWD)[\s._-]*(\d{4})-(\d{4})(?:\b|$)/i);
    if (tmyMatch) return `${tmyMatch[1]} ${tmyMatch[2]}-${tmyMatch[3]}`;
    const rangeMatch = text.match(/(?:^|[^\d])(19\d{2}|20\d{2})-(19\d{2}|20\d{2})(?!\d)/);
    if (rangeMatch) return `${rangeMatch[1]}-${rangeMatch[2]}`;
    const tmyOnly = text.match(/(?:^|[\s._-])(TMYx?|IWEC[0-9]?|CSWD)(?:[\s._-]|$)/i);
    if (tmyOnly) return tmyOnly[1];
    return "";
}

function getWeatherPeriod(weatherObj) {
    if (!weatherObj || typeof weatherObj !== "object") return "N/A";
    const metadata = weatherObj.metadata && typeof weatherObj.metadata === "object"
        ? weatherObj.metadata.weather_source
        : null;
    const candidates = [
        metadata && metadata.weather_period,
        weatherObj.weather_period,
        weatherObj.source_file,
        metadata && metadata.epw_file,
        weatherObj.local_epw_match && weatherObj.local_epw_match.epw_path
    ];
    for (const candidate of candidates) {
        const period = extractEpwPeriodFromFileName(candidate);
        if (period) return period;
    }
    return "N/A";
}

function monthNameShort(month) {
    return ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][month - 1] || "";
}

function hourIndexToDateTime(index) {
    const monthDays = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    let remaining = Math.max(0, Math.floor(index));
    let month = 1;
    for (let i = 0; i < monthDays.length; i++) {
        const hours = monthDays[i] * 24;
        if (remaining < hours) {
            month = i + 1;
            break;
        }
        remaining -= hours;
    }
    const day = Math.floor(remaining / 24) + 1;
    const hour = remaining % 24;
    return {
        month,
        day,
        hour,
        label: `${monthNameShort(month)} ${day} ${String(hour).padStart(2, "0")}:00`
    };
}

function epwDateTimeFromWeatherData(weatherData, index) {
    const month = Number(weatherData.month && weatherData.month[index]);
    const day = Number(weatherData.day && weatherData.day[index]);
    const rawHour = Number(weatherData.epw_hour && weatherData.epw_hour[index]);
    if (Number.isFinite(month) && Number.isFinite(day) && Number.isFinite(rawHour)) {
        const hour = Math.max(0, Math.min(23, Math.floor(rawHour - 1)));
        return {
            month,
            day,
            hour,
            label: `${monthNameShort(month)} ${day} ${String(hour).padStart(2, "0")}:00`
        };
    }
    return hourIndexToDateTime(index);
}

function buildTemperatureDistribution(weatherData) {
    const rawDry = Array.isArray(weatherData && weatherData.dry_bulb_C)
        ? weatherData.dry_bulb_C
        : [];
    if (!rawDry.length) return null;
    const bins = new Map();
    let minTemp = Infinity;
    let maxTemp = -Infinity;
    let sum = 0;
    let peakIndex = 0;
    let validCount = 0;
    rawDry.forEach((value, index) => {
        const temp = Number(value);
        if (!Number.isFinite(temp)) return;
        const bin = Math.floor(temp);
        bins.set(bin, (bins.get(bin) || 0) + 1);
        sum += temp;
        validCount += 1;
        if (temp < minTemp) minTemp = temp;
        if (temp > maxTemp) {
            maxTemp = temp;
            peakIndex = index;
        }
    });
    if (!validCount) return null;
    const rows = Array.from(bins.entries())
        .sort((a, b) => a[0] - b[0])
        .map(([bin, hours]) => ({ bin, label: `${bin}°C`, hours }));
    const peakTime = epwDateTimeFromWeatherData(weatherData || {}, peakIndex);
    return {
        rows,
        totalHours: validCount,
        minTemp,
        avgTemp: sum / validCount,
        maxTemp,
        peakIndex,
        hourOfYear: peakIndex + 1,
        peakTime
    };
}

function temperatureDistributionTableHtml(distribution, maxRows = Infinity) {
    if (!distribution || !Array.isArray(distribution.rows)) return "";
    const rows = distribution.rows.slice(0, maxRows);
    return `<table class="mini"><thead><tr><th>Temperature Bin (°C)</th><th>Hours</th></tr></thead><tbody>${
        rows.map(row => `<tr><td>${esc(row.label)}</td><td>${esc(row.hours)}</td></tr>`).join("")
    }</tbody></table>`;
}

function renderTemperatureDistributionPanel() {
    const panel = document.getElementById("temperatureDistributionPanel");
    const summary = document.getElementById("temperatureDistributionSummary");
    if (!panel || !summary) return;
    const weather = standardDataFiles.weather || {};
    const weatherData = weather.data || weather.hourly_data || {};
    const distribution = buildTemperatureDistribution(weatherData);
    if (!distribution) {
        panel.style.display = "none";
        summary.innerHTML = "";
        return;
    }
    panel.style.display = "block";
    const cards = [
        ["Average Dry Bulb", `${fmtNumber(distribution.avgTemp, 1)} °C`],
        ["Minimum Dry Bulb", `${fmtNumber(distribution.minTemp, 1)} °C`],
        ["Maximum Dry Bulb", `${fmtNumber(distribution.maxTemp, 1)} °C`],
        ["Peak Dry Bulb Time", distribution.peakTime.label],
        ["Peak Dry Bulb Hour of Year", distribution.hourOfYear],
        ["Distribution Hours", distribution.totalHours]
    ];
    summary.innerHTML = cards.map(([label, value]) => `
        <div style="border:1px solid #e5e7eb; border-radius:8px; padding:10px; background:#fafafa;">
            <div class="muted" style="font-size:12px;">${label}</div>
            <div style="font-weight:700; margin-top:4px;">${value}</div>
        </div>
    `).join("");
    createChart("temperatureDistributionChart", {
        type: "bar",
        data: {
            labels: distribution.rows.map(row => row.label),
            datasets: [{
                label: "Hours",
                data: distribution.rows.map(row => row.hours),
                backgroundColor: "#0f766e",
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.label}: ${ctx.raw} hours`
                    }
                }
            },
            scales: {
                x: { title: { display: true, text: "Temperature Bin (deg C)" }, ticks: { maxTicksLimit: 18 } },
                y: { title: { display: true, text: "Hours" }, beginAtZero: true }
            }
        }
    });
}

function renderWeatherReportPanel() {
    const panel = document.getElementById("weatherReportPanel");
    if (!panel) return;
    const weather = standardDataFiles.weather || {};
    const data = weather.data || weather.hourly_data || {};
    const source = String(weather.source_format || "").toLowerCase();
    const weatherPeriod = getWeatherPeriod(weather);
    const dry = summarizeNumericArray(data.dry_bulb_C);
    const rh = summarizeNumericArray(data.relative_humidity_percent);
    const ghi = summarizeNumericArray(data.global_horizontal_radiation_Wh_m2);
    const dni = summarizeNumericArray(data.direct_normal_radiation_Wh_m2);
    const wind = summarizeNumericArray(data.wind_speed_m_s);
    const pressure = summarizeNumericArray(data.atmospheric_pressure_Pa);
    if (!dry && !ghi && !wind) {
        panel.style.display = "none";
        panel.innerHTML = "";
        return;
    }

    const location = weather.location || {};
    const place = [location.city, location.state_or_region, location.country].filter(Boolean).join(", ");
    const items = [];
    if (place) items.push(`地点：<b>${place}</b>`);
    if (source) items.push(`来源：<b>${source.toUpperCase()}</b>`);
    items.push(`数据周期：<b>${weatherPeriod}</b>`);
    if (dry) items.push(`干球温度：<b>${fmtNumber(dry.min, 1)}-${fmtNumber(dry.max, 1)} °C</b>，平均 <b>${fmtNumber(dry.avg, 1)} °C</b>`);
    if (rh) items.push(`相对湿度：平均 <b>${fmtNumber(rh.avg, 0)}%</b>`);
    if (ghi) items.push(`全年全球水平太阳辐射：<b>${fmtInteger(ghi.sum / 1000)} kWh/m²</b>，峰值 <b>${fmtInteger(ghi.max)} W/m²</b>`);
    if (dni) items.push(`峰值法向直射辐射：<b>${fmtInteger(dni.max)} W/m²</b>`);
    if (wind) items.push(`风速：平均 <b>${fmtNumber(wind.avg, 1)} m/s</b>，最大 <b>${fmtNumber(wind.max, 1)} m/s</b>`);
    if (pressure) items.push(`平均气压：<b>${fmtInteger(pressure.avg)} Pa</b>`);

    panel.style.display = "block";
    panel.innerHTML =
        "<b>报告补充：EPW 气象信息</b><br>" +
        items.join("；") +
        "。这些信息用于解释气候背景和太阳得热。";
}

function classifyEquipmentCategory(text, filename = "") {
    const hay = `${filename} ${text}`.toLowerCase();
    if (/chiller|冷水机|cop|centrifugal/.test(hay)) return "Chiller COP Surface";
    if (/dry\s*cooler|干冷|adiabatic|fluid cooler/.test(hay)) return "Dry Cooler";
    if (/pump|水泵|chw|cw pump/.test(hay)) return "Pumps";
    if (/fan|terminal|末端|airflow|ahu|crac|cra h/.test(hay)) return "MAU";
    if (/ups|transformer|electrical|switchgear|配电|变压器/.test(hay)) return "Electrical";
    return "General Equipment";
}

function firstRegex(text, patterns) {
    for (const pattern of patterns) {
        const match = text.match(pattern);
        if (match) return match[1] || match[0];
    }
    return "";
}

function extractEquipmentParameters(text, filename = "") {
    const compact = text.replace(/\s+/g, " ");
    const rows = [
        ["Model / Series", firstRegex(compact, [
            /(?:model|series|type)\s*[:#-]?\s*([A-Z0-9][A-Z0-9._/\-\s]{2,40})/i,
            /(?:型号|系列)\s*[:：]?\s*([A-Z0-9][A-Z0-9._/\-\s]{2,40})/i
        ]) || filename.replace(/\.pdf$/i, "")],
        ["Capacity", firstRegex(compact, [
            /(?:cooling\s*)?capacity\s*[:=]?\s*([0-9,.]+\s*(?:kW|MW|RT|tons?))/i,
            /(?:制冷量|冷量|容量)\s*[:：]?\s*([0-9,.]+\s*(?:kW|MW|RT|冷吨))/i
        ])],
        ["Power / Efficiency", firstRegex(compact, [
            /(?:power|input power|fan power|pump power)\s*[:=]?\s*([0-9,.]+\s*kW)/i,
            /(?:COP|EER|efficiency|η)\s*[:=]?\s*([0-9,.]+%?)/i,
            /(?:功率|效率)\s*[:：]?\s*([0-9,.]+%?\s*(?:kW)?)/i
        ])],
        ["Electrical", firstRegex(compact, [
            /(?:voltage|power supply)\s*[:=]?\s*([0-9,.]+\s*V(?:\s*\/\s*[0-9]+\s*Hz)?)/i,
            /(?:电压|电源)\s*[:：]?\s*([0-9,.]+\s*V(?:\s*\/\s*[0-9]+\s*Hz)?)/i
        ])],
        ["Flow / Temperature", firstRegex(compact, [
            /(?:flow|airflow|water flow)\s*[:=]?\s*([0-9,.]+\s*(?:m3\/h|m³\/h|L\/s|gpm|cfm))/i,
            /(?:supply|return|leaving|entering)[^.;]{0,24}?([0-9,.]+\s*°?\s*C)/i,
            /(?:流量|风量|水量)\s*[:：]?\s*([0-9,.]+\s*(?:m3\/h|m³\/h|L\/s))/i
        ])]
    ].filter(([, value]) => value).slice(0, 4);
    return rows.length ? rows : [["Source", filename || "Uploaded PDF"], ["Extraction", "No structured parameters found"]];
}

function setEquipmentSpecRows(category, specIndex, rows) {
    equipmentPdfSpecs[category] = equipmentPdfSpecs[category] || [];
    equipmentPdfSpecs[category][specIndex] = equipmentPdfSpecs[category][specIndex] || { sourceFile: "Manual entry", rows: [] };
    equipmentPdfSpecs[category][specIndex].rows = rows;
}

function renderEquipmentPdfEditor() {
    const root = document.getElementById("equipmentPdfEditor");
    if (!root) return;
    const categories = ["Dry Cooler", "Chiller COP Surface", "Electrical", "Pumps"];
    const blocks = categories
        .filter(category => Array.isArray(equipmentPdfSpecs[category]) && equipmentPdfSpecs[category].length)
        .map(category => {
            const spec = equipmentPdfSpecs[category][0];
            const rows = [...(spec.rows || [])];
            while (rows.length < 4) rows.push(["", ""]);
            return `
                <div class="panel">
                    <div class="panelTitle">${category} reference equipment parameter</div>
                    <div class="hint">Source: ${esc(spec.sourceFile || "Manual entry")} · 自动预填，可手动修正；报告使用这里的内容。</div>
                    <div style="display:grid; grid-template-columns: 1fr 1.5fr; gap:8px; margin-top:8px;">
                        ${rows.slice(0, 4).map(([label, value], i) => `
                            <input data-equipment-param="${esc(category)}" data-spec-index="0" data-row-index="${i}" data-field="label" value="${esc(label)}" placeholder="Parameter name" />
                            <input data-equipment-param="${esc(category)}" data-spec-index="0" data-row-index="${i}" data-field="value" value="${esc(value)}" placeholder="Value" />
                        `).join("")}
                    </div>
                </div>
            `;
        }).join("");
    root.innerHTML = blocks;
    root.querySelectorAll("[data-equipment-param]").forEach(input => {
        input.addEventListener("input", () => {
            const category = input.getAttribute("data-equipment-param");
            const specIndex = Number(input.getAttribute("data-spec-index"));
            const rows = [];
            root.querySelectorAll("[data-equipment-param]").forEach(el => {
                if (el.getAttribute("data-equipment-param") !== category) return;
                if (Number(el.getAttribute("data-spec-index")) !== specIndex) return;
                const rowIndex = Number(el.getAttribute("data-row-index"));
                const field = el.getAttribute("data-field");
                rows[rowIndex] = rows[rowIndex] || ["", ""];
                rows[rowIndex][field === "label" ? 0 : 1] = el.value;
            });
            setEquipmentSpecRows(category, specIndex, rows.filter(([label, value]) => label || value));
        });
    });
}

async function readPdfText(file) {
    if (!window.pdfjsLib) throw new Error("PDF.js is not loaded.");
    window.pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js";
    const buffer = await file.arrayBuffer();
    const pdf = await window.pdfjsLib.getDocument({ data: buffer }).promise;
    const pages = [];
    const maxPages = Math.min(pdf.numPages, 8);
    for (let pageNo = 1; pageNo <= maxPages; pageNo++) {
        const page = await pdf.getPage(pageNo);
        const content = await page.getTextContent();
        pages.push(content.items.map(item => item.str).join(" "));
    }
    return pages.join("\n");
}

async function handleEquipmentPdfFiles(files, forcedCategory = "") {
    const status = document.getElementById("statusEquipmentPdf");
    const list = Array.from(files || []);
    if (!list.length) return;
    if (status) {
        status.textContent = "正在解析 PDF 参数...";
        status.style.color = "#6b7280";
    }
    let parsed = 0;
    for (const file of list) {
        try {
            const text = await readPdfText(file);
            const category = forcedCategory || classifyEquipmentCategory(text, file.name);
            equipmentPdfSpecs[category] = equipmentPdfSpecs[category] || [];
            equipmentPdfSpecs[category].push({
                sourceFile: file.name,
                rows: extractEquipmentParameters(text, file.name)
            });
            parsed += 1;
        } catch (e) {
            equipmentPdfSpecs["General Equipment"] = equipmentPdfSpecs["General Equipment"] || [];
            equipmentPdfSpecs["General Equipment"].push({
                sourceFile: file.name,
                rows: [["PDF Parse Error", String(e.message || e)]]
            });
        }
    }
    if (status) {
        status.textContent = `已解析 ${parsed}/${list.length} 个 ${forcedCategory || "设备"} PDF；参数仅用于报告展示`;
        status.style.color = parsed ? "#059669" : "#dc2626";
    }
    renderEquipmentPdfEditor();
}

function equipmentSpecHtml(category) {
    const specs = equipmentPdfSpecs[category] || equipmentPdfSpecs["General Equipment"] || [];
    if (!specs.length) {
        return `<div class="specBlock"><b>Reference equipment parameter:</b> Not provided.</div>`;
    }
    return specs.slice(0, 2).map(spec => `
        <div class="specBlock">
            <b>Reference equipment parameter:</b> ${esc(spec.sourceFile)}
            <table class="mini"><tbody>${tableRows(spec.rows.slice(0, 4).map(([label, value]) => [label, esc(value)]))}</tbody></table>
        </div>
    `).join("");
}

function projectMemoryKey(name, version) {
    const clean = value => String(value || "").trim().toLowerCase().replace(/[^a-z0-9\u4e00-\u9fa5._-]+/g, "-").replace(/^-|-$/g, "");
    return `pueSolverProject:${clean(name) || "untitled"}:${clean(version) || "v1.0"}`;
}

function projectMemoryLabelFromKey(key) {
    return key.replace(/^pueSolverProject:/, "").replace(/:/g, " / ");
}

function getProjectMemoryKeys() {
    return Object.keys(localStorage)
        .filter(key => key.startsWith("pueSolverProject:"))
        .sort();
}

function updateProjectMemorySelect() {
    const select = document.getElementById("projectMemorySelect");
    if (!select) return;
    const keys = getProjectMemoryKeys();
    select.innerHTML = "";
    if (!keys.length) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "暂无本地存档";
        select.appendChild(opt);
        return;
    }
    keys.forEach(key => {
        const opt = document.createElement("option");
        opt.value = key;
        opt.textContent = projectMemoryLabelFromKey(key);
        select.appendChild(opt);
    });
}

function setProjectMemoryStatus(text, tone = "info") {
    const el = document.getElementById("projectMemoryStatus");
    if (!el) return;
    el.textContent = text;
    el.style.color = tone === "error" ? "#dc2626" : tone === "ok" ? "#059669" : "#6b7280";
}

function collectProjectMemoryPayload() {
    const coolingSelection = getCoolingSystemSelection();
    const peakWeather = getPeakDesignWeatherInput();
    return {
        saved_at: new Date().toISOString(),
        project_info: {
            name: document.getElementById("projectNameInput")?.value || "",
            location: document.getElementById("projectLocationInput")?.value || "",
            latitude: document.getElementById("projectLatitudeInput")?.value || "",
            longitude: document.getElementById("projectLongitudeInput")?.value || "",
            capacity_mw: document.getElementById("projectCapacityMwInput")?.value || "",
            stage: document.getElementById("projectStageInput")?.value || "",
            version: document.getElementById("projectVersionInput")?.value || "v1.0"
        },
        report_only_inputs: {
            solar_heat_gain_max_kw: document.getElementById("solarHeatGainMaxKw")?.value || "0",
            solar_daytime_start_hour: document.getElementById("solarDaytimeStartHour")?.value || "6",
            solar_daytime_end_hour: document.getElementById("solarDaytimeEndHour")?.value || "18",
            other_auxiliary_heat_gain_kw: document.getElementById("otherAuxiliaryHeatGainKw")?.value || "0",
            other_electrical_auxiliary_power_kw: document.getElementById("otherElectricalAuxiliaryPowerKw")?.value || "0",
            peak_design_weather_source: peakWeather.peakDesignWeatherSource,
            manual_peak_design_dry_bulb_c: document.getElementById("manualPeakDesignDryBulbC")?.value || "",
            aux_fixed_coeff: document.getElementById("auxFixedCoeff")?.value || "0.005",
            dry_cooler_approach_c: document.getElementById("dryCoolerApproachC")?.value || "5"
        },
        cooling_system_selection: {
            type: coolingSelection.type,
            capacity_mw: coolingSelection.capacityMw,
            power_source: coolingSelection.powerSource,
            scenario_key: coolingSelection.scenarioKey
        },
        standard_data_files: standardDataFiles,
        standard_solver_input: standardSolverInput,
        curve_lib: window.curveLib || null,
        equipment_pdf_specs: equipmentPdfSpecs
    };
}

function saveProjectMemory() {
    const info = getProjectReportInfo();
    const key = projectMemoryKey(info.name, info.version);
    try {
        localStorage.setItem(key, JSON.stringify(collectProjectMemoryPayload()));
        updateProjectMemorySelect();
        const select = document.getElementById("projectMemorySelect");
        if (select) select.value = key;
        setProjectMemoryStatus(`已保存项目输入：${projectMemoryLabelFromKey(key)}`, "ok");
    } catch (e) {
        setProjectMemoryStatus(`保存失败：${String(e.message || e)}`, "error");
    }
}

function restoreProjectMemory(key = "") {
    const select = document.getElementById("projectMemorySelect");
    const memoryKey = key || (select && select.value);
    if (!memoryKey) {
        setProjectMemoryStatus("没有可恢复的项目存档。", "error");
        return;
    }
    try {
        const payload = JSON.parse(localStorage.getItem(memoryKey) || "{}");
        const info = payload.project_info || {};
        const report = payload.report_only_inputs || {};
        if (document.getElementById("projectNameInput")) document.getElementById("projectNameInput").value = info.name || "";
        if (document.getElementById("projectLocationInput")) document.getElementById("projectLocationInput").value = info.location || "";
        if (document.getElementById("projectLatitudeInput")) document.getElementById("projectLatitudeInput").value = info.latitude || "";
        if (document.getElementById("projectLongitudeInput")) document.getElementById("projectLongitudeInput").value = info.longitude || "";
        if (document.getElementById("projectCapacityMwInput")) document.getElementById("projectCapacityMwInput").value = info.capacity_mw || "";
        if (document.getElementById("projectStageInput")) document.getElementById("projectStageInput").value = info.stage || "";
        if (document.getElementById("projectVersionInput")) document.getElementById("projectVersionInput").value = info.version || "v1.0";
        if (document.getElementById("solarHeatGainMaxKw")) document.getElementById("solarHeatGainMaxKw").value = report.solar_heat_gain_max_kw || "0";
        if (document.getElementById("solarDaytimeStartHour")) document.getElementById("solarDaytimeStartHour").value = report.solar_daytime_start_hour || "6";
        if (document.getElementById("solarDaytimeEndHour")) document.getElementById("solarDaytimeEndHour").value = report.solar_daytime_end_hour || "18";
        if (document.getElementById("otherAuxiliaryHeatGainKw")) document.getElementById("otherAuxiliaryHeatGainKw").value = report.other_auxiliary_heat_gain_kw || "0";
        if (document.getElementById("otherElectricalAuxiliaryPowerKw")) document.getElementById("otherElectricalAuxiliaryPowerKw").value = report.other_electrical_auxiliary_power_kw || "0";
        const restoredPeakSource = report.peak_design_weather_source === "manual" ? "manual" : "ashrae_auto";
        if (document.getElementById("peakDesignWeatherAuto")) document.getElementById("peakDesignWeatherAuto").checked = restoredPeakSource !== "manual";
        if (document.getElementById("peakDesignWeatherManual")) document.getElementById("peakDesignWeatherManual").checked = restoredPeakSource === "manual";
        if (document.getElementById("manualPeakDesignDryBulbC")) document.getElementById("manualPeakDesignDryBulbC").value = report.manual_peak_design_dry_bulb_c || "";
        if (document.getElementById("auxFixedCoeff")) document.getElementById("auxFixedCoeff").value = report.aux_fixed_coeff || "0.005";
        if (document.getElementById("dryCoolerApproachC")) document.getElementById("dryCoolerApproachC").value = report.dry_cooler_approach_c || "5";

        const coolingSelection = payload.cooling_system_selection || {};
        const restoredType = COOLING_SYSTEM_CONFIG[coolingSelection.type] ? coolingSelection.type : DEFAULT_COOLING_SYSTEM_TYPE;
        if (document.getElementById("coolingSystemType")) document.getElementById("coolingSystemType").value = restoredType;
        updateCoolingUnitCapacityOptions(coolingSelection.capacity_mw ?? DEFAULT_COOLING_UNIT_CAPACITY_MW);
        const restoredPowerSource = ["Grid", "Gas Engine"].includes(coolingSelection.power_source) ? coolingSelection.power_source : DEFAULT_POWER_SOURCE;
        if (document.getElementById("powerSource")) document.getElementById("powerSource").value = restoredPowerSource;
        const restoredScenario = SCENARIO_REGISTRY[coolingSelection.scenario_key] ? coolingSelection.scenario_key : DEFAULT_SCENARIO_KEY;
        if (document.getElementById("scenarioSelect")) document.getElementById("scenarioSelect").value = restoredScenario;
        renderCoolingSystemSelection();

        Object.keys(standardDataFiles).forEach(key => { standardDataFiles[key] = payload.standard_data_files?.[key] || null; });
        renderCoolingSystemSelection();
        standardSolverInput = payload.standard_solver_input || null;
        preferStandardFiles = Boolean(standardSolverInput || standardDataFiles.itLoad || standardDataFiles.weather);
        window.curveLib = payload.curve_lib || window.curveLib || { curves_1d: {}, cop_surfaces: {} };
        Object.keys(equipmentPdfSpecs).forEach(key => delete equipmentPdfSpecs[key]);
        Object.assign(equipmentPdfSpecs, payload.equipment_pdf_specs || {});
        renderEquipmentPdfEditor();

        if (standardSolverInput) elIn.value = pretty(standardSolverInput);
        refreshRestoredFileStatuses();
        previewInputCurves(standardDataFiles);
        refreshStandardInputStatus();
        updateProjectInfoStatus();
        updateSolarGainStatus();
        updatePeakDesignWeatherStatus();
        renderProjectInfoReportPanel();
        renderSolarGainReportPanel();
        renderWeatherReportPanel();
        renderTemperatureDistributionPanel();
        setProjectMemoryStatus(`已恢复项目输入：${projectMemoryLabelFromKey(memoryKey)}`, "ok");
    } catch (e) {
        setProjectMemoryStatus(`恢复失败：${String(e.message || e)}`, "error");
    }
}

function deleteProjectMemory() {
    const select = document.getElementById("projectMemorySelect");
    const key = select && select.value;
    if (!key) {
        setProjectMemoryStatus("没有可删除的项目存档。", "error");
        return;
    }
    localStorage.removeItem(key);
    updateProjectMemorySelect();
    setProjectMemoryStatus(`已删除项目存档：${projectMemoryLabelFromKey(key)}`, "ok");
}

function esc(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function plainNumber(value, digits = 2) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return null;
    return Number(value).toLocaleString("en-US", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits
    });
}

function reportValue(value, suffix = "", digits = 2) {
    const formatted = plainNumber(value, digits);
    return formatted === null ? "N/A" : `${formatted}${suffix}`;
}

function monthName(index) {
    return ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][index] || `M${index + 1}`;
}

function groupHourlyByMonth(hourly, picker) {
    const monthHours = [744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744];
    let start = 0;
    return monthHours.map((count, index) => {
        const rows = hourly.slice(start, start + count);
        start += count;
        const values = rows.map(picker).filter(v => Number.isFinite(Number(v))).map(Number);
        const avg = values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
        return { month: monthName(index), value: avg };
    });
}

function tableRows(rows) {
    return rows.map(([label, value]) => `<tr><th>${esc(label)}</th><td>${value}</td></tr>`).join("");
}

function buildPueContributionSummary(annual = {}) {
    const itEnergy = Number(annual.annual_IT_energy_kWh) || 0;
    const annualPue = Number(annual.annual_average_PUE) || 0;
    const nonItPue = annualPue > 1 ? annualPue - 1 : 0;
    const ppue = (value) => itEnergy > 0 ? (Number(value) || 0) / itEnergy : null;
    const share = (value) => nonItPue > 0 && Number.isFinite(Number(value)) ? Number(value) / nonItPue : null;
    const drivers = [
        { key: "cooling", label: "Cooling System", ppue: ppue(annual.annual_total_cooling_system_energy_kWh) },
        { key: "electrical", label: "Electrical Distribution Loss", ppue: ppue(annual.annual_electrical_loss_kWh) },
        { key: "auxiliary", label: "Other Electrical Auxiliary Power", ppue: ppue(annual.annual_auxiliary_energy_kWh) }
    ];
    const rankedDrivers = drivers
        .filter(driver => Number.isFinite(Number(driver.ppue)))
        .sort((a, b) => Number(b.ppue) - Number(a.ppue));
    return {
        itEnergy,
        annualPue,
        nonItPue,
        coolingPPUE: drivers[0].ppue,
        electricalPPUE: drivers[1].ppue,
        auxiliaryPPUE: drivers[2].ppue,
        coolingShare: share(drivers[0].ppue),
        electricalShare: share(drivers[1].ppue),
        auxiliaryShare: share(drivers[2].ppue),
        largestDriver: rankedDrivers[0] || null
    };
}

function signedPpueText(value) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "N/A";
    return `${Number(value) >= 0 ? "+" : ""}${fmtNumber(value, 3)}`;
}

function percentText(value) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "N/A";
    return `${fmtNumber(Number(value) * 100, 0)}%`;
}

function renderPueContributionSummaryPanel(annual) {
    const panel = document.getElementById("pueContributionSummaryPanel");
    const body = document.getElementById("pueContributionSummaryBody");
    if (!panel || !body) return;
    const summary = buildPueContributionSummary(annual || {});
    if (!(summary.itEnergy > 0)) {
        panel.style.display = "none";
        body.innerHTML = "";
        return;
    }
    panel.style.display = "block";
    const rows = [
        ["Cooling System pPUE", signedPpueText(summary.coolingPPUE)],
        ["Electrical Distribution Loss pPUE", signedPpueText(summary.electricalPPUE)],
        ["Other Electrical Auxiliary pPUE", signedPpueText(summary.auxiliaryPPUE)],
        ["Largest PUE Driver", summary.largestDriver ? summary.largestDriver.label : "N/A"],
        ["Cooling Share of Non-IT Overhead", percentText(summary.coolingShare)]
    ];
    body.innerHTML = rows.map(([label, value]) => `
        <div style="border:1px solid #e5e7eb; border-radius:8px; padding:10px; background:#fafafa;">
            <div class="muted" style="font-size:12px;">${label}</div>
            <div style="font-weight:700; margin-top:4px;">${value}</div>
        </div>
    `).join("");
}

function mwTextFromKw(value, digits = 1) {
    const kw = Number(value);
    if (!Number.isFinite(kw)) return "N/A";
    return `${fmtNumber(kw / 1000, digits)} MW`;
}

function ratioPercentText(value, digits = 2) {
    const ratio = Number(value);
    if (!Number.isFinite(ratio)) return "N/A";
    return `${fmtNumber(ratio * 100, digits)}%`;
}

function buildCoolingUnitArchitectureInfo(outputObj) {
    const hourly = Array.isArray(outputObj && outputObj.hourly_results) ? outputObj.hourly_results : [];
    const first = hourly[0] || {};
    const capacityKw = Number(first.cooling_unit_capacity_kW);
    const count = Number(first.cooling_unit_count);
    const totalCapacityKw = Number(first.cooling_unit_total_capacity_kW);
    const unitLoadRatio = Number(first.unit_load_ratio);
    if (!Number.isFinite(capacityKw) && !Number.isFinite(count) && !Number.isFinite(totalCapacityKw)) return null;
    return {
        capacityKw: Number.isFinite(capacityKw) ? capacityKw : null,
        count: Number.isFinite(count) ? count : null,
        totalCapacityKw: Number.isFinite(totalCapacityKw) ? totalCapacityKw : null,
        unitLoadRatio: Number.isFinite(unitLoadRatio) ? unitLoadRatio : null
    };
}

function renderCoolingUnitArchitecturePanel(outputObj) {
    const panel = document.getElementById("coolingUnitArchitecturePanel");
    const body = document.getElementById("coolingUnitArchitectureBody");
    if (!panel || !body) return;
    const info = buildCoolingUnitArchitectureInfo(outputObj);
    if (!info) {
        panel.style.display = "none";
        body.innerHTML = "";
        return;
    }
    panel.style.display = "block";
    const architecture = info.count && info.capacityKw
        ? `${fmtInteger(info.count)} × ${mwTextFromKw(info.capacityKw)} cooling units`
        : "N/A";
    const rows = [
        ["Cooling Unit Capacity", mwTextFromKw(info.capacityKw)],
        ["Cooling Unit Count", info.count !== null ? fmtInteger(info.count) : "N/A"],
        ["Total Cooling Unit Capacity", mwTextFromKw(info.totalCapacityKw)],
        ["Architecture", architecture],
        ["Dispatch Strategy", "All units running"],
        ["Load Sharing", "Equal load sharing"],
        ["Unit Load Ratio", "Required Cooling Capacity / Installed Cooling Unit Capacity"],
        ["Current Unit Load Ratio", ratioPercentText(info.unitLoadRatio)]
    ];
    body.innerHTML = rows.map(([label, value]) => `
        <div style="border:1px solid #e5e7eb; border-radius:8px; padding:10px; background:#fafafa;">
            <div class="muted" style="font-size:12px;">${label}</div>
            <div style="font-weight:700; margin-top:4px;">${value}</div>
        </div>
    `).join("");
}

function linearTicks(min, max, count = 5) {
    if (!Number.isFinite(min) || !Number.isFinite(max)) return [];
    if (Math.abs(max - min) < 1e-12) return [min];
    return Array.from({ length: count }, (_, i) => min + (max - min) * (i / (count - 1)));
}

function svgGrid(width, height, pad, xTicks, yTicks, sx, sy) {
    const vertical = xTicks.map(t => {
        const x = sx(t);
        return `<line x1="${x.toFixed(1)}" y1="${pad}" x2="${x.toFixed(1)}" y2="${height - pad}" class="gridLine" />
                <text x="${x.toFixed(1)}" y="${height - pad + 18}" text-anchor="middle" class="tick">${reportValue(t, "", 1)}</text>`;
    }).join("");
    const horizontal = yTicks.map(t => {
        const y = sy(t);
        return `<line x1="${pad}" y1="${y.toFixed(1)}" x2="${width - pad}" y2="${y.toFixed(1)}" class="gridLine" />
                <text x="${pad - 8}" y="${(y + 4).toFixed(1)}" text-anchor="end" class="tick">${reportValue(t, "", 1)}</text>`;
    }).join("");
    return vertical + horizontal;
}

function svgTracer(x, y, width, height, pad, label = "") {
    return `
        <line x1="${x.toFixed(1)}" y1="${pad}" x2="${x.toFixed(1)}" y2="${height - pad}" class="traceLine" />
        <line x1="${pad}" y1="${y.toFixed(1)}" x2="${width - pad}" y2="${y.toFixed(1)}" class="traceLine" />
        <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.5" class="tracePoint" />
        ${label ? `<text x="${Math.min(width - pad - 6, x + 8).toFixed(1)}" y="${Math.max(pad + 14, y - 8).toFixed(1)}" class="traceLabel">${esc(label)}</text>` : ""}
    `;
}

const REPORT_COLORS = Object.freeze({
    pueLine: "#4E5D6C",
    dryBulb: "#5E8B7E",
    relativeHumidity: "#3F72AF",
    windSpeed: "#4E5D6C",
    atmosphericPressure: "#6C757D",
    globalHorizontalRadiation: "#C47A00",
    directNormalRadiation: "#D28B26",
    totalSkyCover: "#6C757D",
    itEnergy: "#5E8B7E",
    coolingEnergy: "#4E5D6C",
    pumpEnergy: "#8A8A8A",
    electricalLoss: "#C47A00",
    other: "#D0D0D0",
    peakMarker: "#A35A2A"
});
const REPORT_CHART_COLORS = [
    REPORT_COLORS.pueLine,
    REPORT_COLORS.dryBulb,
    REPORT_COLORS.electricalLoss,
    REPORT_COLORS.pumpEnergy,
    REPORT_COLORS.relativeHumidity,
    REPORT_COLORS.directNormalRadiation,
    REPORT_COLORS.atmosphericPressure,
    REPORT_COLORS.other
];

function reportEnergyColor(label) {
    const text = String(label || "").toLowerCase();
    if (text.includes("it")) return REPORT_COLORS.itEnergy;
    if (text.includes("cooling") || text.includes("acc") || text.includes("chiller") || text.includes("dry cooler")) return REPORT_COLORS.coolingEnergy;
    if (text.includes("pump")) return REPORT_COLORS.pumpEnergy;
    if (text.includes("electrical") || text.includes("elec") || text.includes("loss")) return REPORT_COLORS.electricalLoss;
    return REPORT_COLORS.other;
}

function svgLineChart(series, opts = {}) {
    const width = opts.width || 920;
    const height = opts.height || 280;
    const pad = 42;
    const values = (series || []).map(Number).filter(Number.isFinite);
    if (values.length < 2) return `<div class="empty">Not enough data</div>`;
    const sampleEvery = Math.max(1, Math.ceil(values.length / (opts.maxPoints || 700)));
    const sampled = values.filter((_, i) => i % sampleEvery === 0 || i === values.length - 1);
    const min = opts.min ?? Math.min(...sampled);
    const max = opts.max ?? Math.max(...sampled);
    const span = Math.max(max - min, 1e-9);
    const xMax = Math.max(values.length - 1, 1);
    const sx = x => pad + (x / xMax) * (width - pad * 2);
    const sy = value => height - pad - ((value - min) / span) * (height - pad * 2);
    const sampledWithIndex = values
        .map((value, index) => ({ value, index }))
        .filter((_, i) => i % sampleEvery === 0 || i === values.length - 1);
    const points = sampledWithIndex.map(({ value, index }) => `${sx(index).toFixed(1)},${sy(value).toFixed(1)}`).join(" ");
    const maxPoint = values.reduce((best, value, index) => value > best.value ? { value, index } : best, { value: -Infinity, index: 0 });
    const xTicks = linearTicks(0, xMax, 6);
    const yTicks = linearTicks(min, max, 5);
    const lineColor = opts.color || REPORT_COLORS.pueLine;
    return `
        <svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(opts.title || "line chart")}">
            ${svgGrid(width, height, pad, xTicks, yTicks, sx, sy)}
            <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" class="axis" />
            <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" class="axis" />
            <text x="${pad}" y="${pad - 12}" class="tick">${esc(opts.yLabel || "")}</text>
            <text x="${width - pad}" y="${height - 12}" text-anchor="end" class="tick">${esc(opts.xLabel || "")}</text>
            <polyline points="${points}" fill="none" stroke="${lineColor}" stroke-width="1.8" />
            ${svgTracer(sx(maxPoint.index), sy(maxPoint.value), width, height, pad, `max ${reportValue(maxPoint.value, "", 2)}`)}
        </svg>`;
}

function svgBarChart(items, opts = {}) {
    const width = opts.width || 920;
    const height = opts.height || 280;
    const margin = { left: 84, top: 44, right: 42, bottom: 42 };
    const rows = (items || []).filter(item => Number.isFinite(Number(item.value)));
    if (!rows.length) return `<div class="empty">Not enough data</div>`;
    const max = Math.max(...rows.map(item => Number(item.value)), 1);
    const scaleMax = max * 1.05;
    const formatAxisTick = (value) => {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return "N/A";
        const abs = Math.abs(numeric);
        const maximumFractionDigits = opts.yTickDigits ?? (abs >= 100 ? 0 : (abs >= 10 ? 1 : 3));
        return numeric.toLocaleString("en-US", {
            minimumFractionDigits: opts.yTickDigits ?? 0,
            maximumFractionDigits
        });
    };
    const formatBarValue = (value) => {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return "N/A";
        const abs = Math.abs(numeric);
        const maximumFractionDigits = opts.valueLabelDigits ?? (abs >= 100 ? 0 : (abs >= 10 ? 1 : 3));
        return numeric.toLocaleString("en-US", {
            minimumFractionDigits: 0,
            maximumFractionDigits
        });
    };
    const barGap = 8;
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const xAxisY = height - margin.bottom;
    const baseBarWidth = (plotWidth - barGap * (rows.length - 1)) / rows.length;
    const barWidthScale = opts.barWidthScale || 1;
    const barWidth = baseBarWidth * barWidthScale;
    const barInset = (baseBarWidth - barWidth) / 2;
    const maxTickY = xAxisY - (plotHeight * max) / scaleMax;
    const yTicks = opts.yTickCount ? linearTicks(0, max, opts.yTickCount) : [];
    const tickRows = yTicks.map((tick) => {
        const y = xAxisY - (plotHeight * tick) / scaleMax;
        return `
            <line x1="${margin.left}" y1="${y.toFixed(1)}" x2="${width - margin.right}" y2="${y.toFixed(1)}" class="gridLine" />
            <text x="${margin.left - 10}" y="${(y + 4).toFixed(1)}" text-anchor="end" class="tick">${formatAxisTick(tick)}</text>`;
    }).join("");
    const bars = rows.map((item, i) => {
        const value = Number(item.value);
        const h = (plotHeight * value) / scaleMax;
        const x = margin.left + i * (baseBarWidth + barGap) + barInset;
        const y = xAxisY - h;
        const fill = item.color || opts.color || REPORT_COLORS.coolingEnergy;
        const valueLabel = opts.showValueLabels
            ? `<text x="${(x + barWidth / 2).toFixed(1)}" y="${Math.max(14, y - 6).toFixed(1)}" text-anchor="middle" class="tick">${formatBarValue(value)}</text>`
            : "";
        return `
            <rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${Math.max(1, barWidth).toFixed(1)}" height="${h.toFixed(1)}" fill="${fill}" />
            ${valueLabel}
            <text x="${(x + barWidth / 2).toFixed(1)}" y="${height - 16}" text-anchor="middle" class="tick">${esc(item.label)}</text>`;
    }).join("");
    return `
        <svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(opts.title || "bar chart")}">
            <line x1="${margin.left}" y1="${xAxisY}" x2="${width - margin.right}" y2="${xAxisY}" class="axis" />
            <line x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${xAxisY}" class="axis" />
            <text x="${margin.left}" y="${margin.top - 20}" class="tick">${esc(opts.yLabel || "")}</text>
            ${tickRows || `<text x="${margin.left - 10}" y="${(maxTickY + 4).toFixed(1)}" text-anchor="end" class="tick">${formatAxisTick(max)}</text>`}
            ${bars}
        </svg>`;
}

function svgXYLineChart(points, opts = {}) {
    const width = opts.width || 920;
    const height = opts.height || 280;
    const pad = 42;
    const pts = curvePoints2d(points);
    if (pts.length < 2) return `<div class="empty">Not enough data</div>`;
    const xMin = Math.min(...pts.map(p => p[0]));
    const xMax = Math.max(...pts.map(p => p[0]));
    const yMin = Math.min(...pts.map(p => p[1]));
    const yMax = Math.max(...pts.map(p => p[1]));
    const sx = value => pad + ((value - xMin) / Math.max(xMax - xMin, 1e-9)) * (width - pad * 2);
    const sy = value => height - pad - ((value - yMin) / Math.max(yMax - yMin, 1e-9)) * (height - pad * 2);
    const poly = pts.map(([x, y]) => `${sx(x).toFixed(1)},${sy(y).toFixed(1)}`).join(" ");
    const maxPoint = pts.reduce((best, point) => point[1] > best[1] ? point : best, pts[0]);
    const xTicks = linearTicks(xMin, xMax, 6);
    const yTicks = linearTicks(yMin, yMax, 5);
    const lineColor = opts.color || REPORT_COLORS.pueLine;
    return `
        <svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(opts.title || "curve chart")}">
            ${svgGrid(width, height, pad, xTicks, yTicks, sx, sy)}
            <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" class="axis" />
            <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" class="axis" />
            <text x="${pad}" y="${pad - 12}" class="tick">${esc(opts.yLabel || "")}</text>
            <text x="${width - pad}" y="${height - 12}" text-anchor="end" class="tick">${esc(opts.xLabel || "")}</text>
            <polyline points="${poly}" fill="none" stroke="${lineColor}" stroke-width="1.8" />
            ${svgTracer(sx(maxPoint[0]), sy(maxPoint[1]), width, height, pad, `max ${reportValue(maxPoint[1], "", 2)}`)}
        </svg>`;
}

function svgMultiCurveChart(curves, opts = {}) {
    const width = opts.width || 920;
    const height = opts.height || 300;
    const pad = 46;
    const prepared = (curves || [])
        .map(curve => ({ ...curve, points: curvePoints2d(curve.points || []) }))
        .filter(curve => curve.points.length >= 2);
    if (!prepared.length) return `<div class="empty">Not enough data</div>`;
    const all = prepared.flatMap(curve => curve.points);
    const xMin = Math.min(...all.map(p => p[0]));
    const xMax = Math.max(...all.map(p => p[0]));
    const yMin = Math.min(...all.map(p => p[1]));
    const yMax = Math.max(...all.map(p => p[1]));
    const sx = value => pad + ((value - xMin) / Math.max(xMax - xMin, 1e-9)) * (width - pad * 2);
    const sy = value => height - pad - ((value - yMin) / Math.max(yMax - yMin, 1e-9)) * (height - pad * 2);
    const colors = REPORT_CHART_COLORS;
    const lines = prepared.map((curve, i) => {
        const pts = curve.points.map(([x, y]) => `${sx(x).toFixed(1)},${sy(y).toFixed(1)}`).join(" ");
        return `<polyline points="${pts}" fill="none" stroke="${colors[i % colors.length]}" stroke-width="1.8" />`;
    }).join("");
    const legend = prepared.map((curve, i) =>
        `<span class="legendItem"><span style="color:${colors[i % colors.length]}">■</span> ${esc(curve.curveId)}</span>`
    ).join("");
    const maxPoint = all.reduce((best, point) => point[1] > best[1] ? point : best, all[0]);
    const xTicks = linearTicks(xMin, xMax, 6);
    const yTicks = linearTicks(yMin, yMax, 5);
    return `
        <svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(opts.title || "multi curve chart")}">
            ${svgGrid(width, height, pad, xTicks, yTicks, sx, sy)}
            <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" class="axis" />
            <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" class="axis" />
            <text x="${pad}" y="${pad - 14}" class="tick">${esc(opts.yLabel || "curve output")}</text>
            <text x="${width - pad}" y="${height - 14}" text-anchor="end" class="tick">${esc(opts.xLabel || "curve input")}</text>
            ${lines}
            ${svgTracer(sx(maxPoint[0]), sy(maxPoint[1]), width, height, pad, `max ${reportValue(maxPoint[1], "", 2)}`)}
        </svg>
        <div class="legend">${legend}</div>`;
}

function curvePoints2d(points) {
    return Array.isArray(points)
        ? points
            .filter(p => Array.isArray(p) && p.length >= 2 && Number.isFinite(Number(p[0])) && Number.isFinite(Number(p[1])))
            .map(p => [Number(p[0]), Number(p[1])])
            .sort((a, b) => a[0] - b[0])
        : [];
}

function curvePoints3d(points) {
    return Array.isArray(points)
        ? points
            .filter(p => Array.isArray(p) && p.length >= 3 && Number.isFinite(Number(p[0])) && Number.isFinite(Number(p[1])) && Number.isFinite(Number(p[2])))
            .map(p => [Number(p[0]), Number(p[1]), Number(p[2])])
        : [];
}

function solveLinearSystem(matrix, vector) {
    const n = vector.length;
    const a = matrix.map((row, i) => row.map(Number).concat(Number(vector[i])));
    for (let col = 0; col < n; col += 1) {
        let pivot = col;
        for (let row = col + 1; row < n; row += 1) {
            if (Math.abs(a[row][col]) > Math.abs(a[pivot][col])) pivot = row;
        }
        if (Math.abs(a[pivot][col]) < 1e-12) return null;
        if (pivot !== col) [a[pivot], a[col]] = [a[col], a[pivot]];
        const div = a[col][col];
        for (let j = col; j <= n; j += 1) a[col][j] /= div;
        for (let row = 0; row < n; row += 1) {
            if (row === col) continue;
            const factor = a[row][col];
            for (let j = col; j <= n; j += 1) a[row][j] -= factor * a[col][j];
        }
    }
    return a.map(row => row[n]);
}

function fitChillerCopSurfaceFunction(points) {
    const pts = curvePoints3d(points);
    if (pts.length < 6) return null;
    const terms = ([t, plr]) => [1, t, plr, t * t, plr * plr, t * plr];
    const xtx = Array.from({ length: 6 }, () => Array(6).fill(0));
    const xtz = Array(6).fill(0);
    pts.forEach(([t, plr, cop]) => {
        const row = terms([t, plr]);
        for (let r = 0; r < 6; r += 1) {
            xtz[r] += row[r] * cop;
            for (let c = 0; c < 6; c += 1) xtx[r][c] += row[r] * row[c];
        }
    });
    const coeffs = solveLinearSystem(xtx, xtz);
    if (!coeffs || coeffs.some(v => !Number.isFinite(v))) return null;
    const predict = ([t, plr]) => {
        const row = terms([t, plr]);
        return row.reduce((sum, value, i) => sum + value * coeffs[i], 0);
    };
    const mean = pts.reduce((sum, p) => sum + p[2], 0) / pts.length;
    const ssTot = pts.reduce((sum, p) => sum + Math.pow(p[2] - mean, 2), 0);
    const ssErr = pts.reduce((sum, p) => sum + Math.pow(p[2] - predict(p), 2), 0);
    const r2 = ssTot > 0 ? 1 - ssErr / ssTot : 1;
    const errors = pts.map(p => Math.abs(p[2] - predict(p)));
    return {
        coeffs,
        r2,
        maxAbsError: Math.max(...errors),
        pointCount: pts.length,
        predict
    };
}

function renderChillerSurfaceFunction(points) {
    const el = document.getElementById("inputChillerSurfaceFunction");
    if (!el) return;
    const fit = fitChillerCopSurfaceFunction(points);
    if (!fit) {
        el.textContent = "三维面函数：点数不足或数据无法拟合。";
        return;
    }
    const pts = curvePoints3d(points);
    const loadLabel = Math.max(...pts.map(p => p[1])) > 2 ? "Load" : "PLR";
    const [a, b, c, d, e, f] = fit.coeffs;
    const signed = (value) => `${value < 0 ? "- " : "+ "}${Math.abs(value).toPrecision(6)}`;
    el.innerHTML = `
        <b>三维 COP 面函数（二次拟合，仅用于展示）</b><br>
        <code>COP(T, ${loadLabel}) = ${a.toPrecision(6)} ${signed(b)}T ${signed(c)}${loadLabel} ${signed(d)}T^2 ${signed(e)}${loadLabel}^2 ${signed(f)}T*${loadLabel}</code><br>
        <span class="muted">R²=${fmtNumber(fit.r2, 4)}，最大绝对误差=${fmtNumber(fit.maxAbsError, 4)}，拟合点数=${fit.pointCount}</span>
    `;
}

function renderChillerSurfacePlot(points) {
    const el = document.getElementById("inputChillerSurface3d");
    if (!el) return;
    const pts = curvePoints3d(points);
    if (!pts.length) {
        el.innerHTML = `<div class="empty" style="padding:12px;">No chiller COP surface data loaded.</div>`;
        return;
    }
    if (typeof Plotly === "undefined") {
        el.innerHTML = `<div class="empty" style="padding:12px;">Plotly.js is not loaded.</div>`;
        return;
    }
    const fit = fitChillerCopSurfaceFunction(pts);
    if (!fit) {
        el.innerHTML = `<div class="empty" style="padding:12px;">点数不足或数据无法拟合三维曲面。</div>`;
        return;
    }
    const tValues = pts.map(p => p[0]);
    const loadValues = pts.map(p => p[1]);
    const tMin = Math.min(...tValues);
    const tMax = Math.max(...tValues);
    const loadMin = Math.min(...loadValues);
    const loadMax = Math.max(...loadValues);
    const gridCount = 36;
    const xGrid = Array.from({ length: gridCount }, (_, i) => tMin + (tMax - tMin) * i / Math.max(gridCount - 1, 1));
    const yGrid = Array.from({ length: gridCount }, (_, i) => loadMin + (loadMax - loadMin) * i / Math.max(gridCount - 1, 1));
    const zGrid = yGrid.map(load => xGrid.map(t => fit.predict([t, load])));
    const loadLabel = loadMax > 2 ? "Load" : "PLR";
    const data = [
        {
            type: "surface",
            x: xGrid,
            y: yGrid,
            z: zGrid,
            colorscale: "Viridis",
            opacity: 0.86,
            contours: {
                z: { show: true, usecolormap: true, highlightcolor: "#111827", project: { z: true } }
            },
            colorbar: { title: "COP" },
            name: "Fitted COP Surface",
            hovertemplate: "T=%{x:.2f}<br>" + loadLabel + "=%{y:.3f}<br>COP=%{z:.3f}<extra></extra>"
        },
        {
            type: "scatter3d",
            mode: "markers",
            x: pts.map(p => p[0]),
            y: pts.map(p => p[1]),
            z: pts.map(p => p[2]),
            marker: {
                size: 4,
                color: "rgba(255,255,255,0.95)",
                line: {
                    color: "rgba(80,80,80,0.4)",
                    width: 1
                }
            },
            name: "Original table points",
            hovertemplate: "T=%{x:.2f}<br>" + loadLabel + "=%{y:.3f}<br>COP=%{z:.3f}<extra></extra>"
        }
    ];
    const layout = {
        margin: { l: 0, r: 0, t: 8, b: 0 },
        paper_bgcolor: "#ffffff",
        plot_bgcolor: "#ffffff",
        scene: {
            xaxis: { title: "T" },
            yaxis: { title: loadLabel },
            zaxis: { title: "COP" },
            camera: { eye: { x: 1.55, y: -1.7, z: 1.15 } }
        },
        legend: { orientation: "h", x: 0, y: 1.02 }
    };
    Plotly.react(el, data, layout, { responsive: true, displaylogo: false });
}

function collectReportCurves() {
    const rows = [];
    const add2dCurve = (category, sourceFile, curve) => {
        const points = curvePoints2d(curve?.points || curve?.data);
        if (!points.length) return;
        const xs = points.map(p => p[0]);
        const ys = points.map(p => p[1]);
        rows.push({
            category,
            sourceFile: sourceFile || "N/A",
            curveId: curve.curve_id || curve.id || category,
            xAxis: curve.x_axis || "x",
            yAxis: curve.output || curve.y_axis || "y",
            pointCount: points.length,
            xMin: Math.min(...xs),
            xMax: Math.max(...xs),
            yMin: Math.min(...ys),
            yMax: Math.max(...ys),
            points
        });
    };
    const addCurveList = (category, file) => {
        if (!file) return;
        if (Array.isArray(file.curves)) file.curves.forEach(curve => add2dCurve(category, file.source_file, curve));
        else add2dCurve(category, file.source_file, file);
    };
    addCurveList("Dry Cooler", standardDataFiles.dryCooler);
    addCurveList("Electrical", standardDataFiles.electrical);
    addCurveList("Pumps", standardDataFiles.pumps);
    addCurveList("MAU", standardDataFiles.fans);

    const chiller = standardDataFiles.chiller;
    const chillerPoints = curvePoints3d(chiller?.points || chiller?.data);
    if (chillerPoints.length) {
        const xs = chillerPoints.map(p => p[0]);
        const ys = chillerPoints.map(p => p[1]);
        const zs = chillerPoints.map(p => p[2]);
        rows.push({
            category: "Chiller COP Surface",
            sourceFile: chiller.source_file || "N/A",
            curveId: chiller.curve_id || "chiller_COP_H_vs_load",
            xAxis: chiller.x_axis || "condenser_entering_water_C",
            yAxis: chiller.y_axis || "load_ratio",
            zAxis: chiller.output || "COP",
            pointCount: chillerPoints.length,
            xMin: Math.min(...xs),
            xMax: Math.max(...xs),
            yMin: Math.min(...ys),
            yMax: Math.max(...ys),
            zMin: Math.min(...zs),
            zMax: Math.max(...zs),
            points3d: chillerPoints
        });
    }
    return rows;
}

function groupReportCurves(curves) {
    const groups = {};
    curves.forEach((curve) => {
        const key = `${curve.category}||${curve.sourceFile}`;
        if (!groups[key]) {
            groups[key] = {
                category: curve.category,
                sourceFile: curve.sourceFile,
                curves: []
            };
        }
        groups[key].curves.push(curve);
    });
    return Object.values(groups);
}

function svgCurveChart(curve) {
    const statsTable = curve.zAxis
        ? `<table class="mini"><tbody>${tableRows([
            [`${curve.xAxis} range`, `${reportValue(curve.xMin, "", 3)} to ${reportValue(curve.xMax, "", 3)}`],
            [`${curve.yAxis} range`, `${reportValue(curve.yMin, "", 3)} to ${reportValue(curve.yMax, "", 3)}`],
            [`${curve.zAxis} range`, `${reportValue(curve.zMin, "", 3)} to ${reportValue(curve.zMax, "", 3)}`],
            ["Point count", esc(curve.pointCount)]
        ])}</tbody></table>`
        : `<table class="mini"><tbody>${tableRows([
            [`${curve.xAxis} range`, `${reportValue(curve.xMin, "", 3)} to ${reportValue(curve.xMax, "", 3)}`],
            [`${curve.yAxis} range`, `${reportValue(curve.yMin, "", 3)} to ${reportValue(curve.yMax, "", 3)}`],
            ["Point count", esc(curve.pointCount)]
        ])}</tbody></table>`;
    if (curve.points3d) {
        const groups = {};
        curve.points3d.forEach(([x, y, z]) => {
            const key = String(x);
            groups[key] = groups[key] || [];
            groups[key].push([y, z]);
        });
        const groupKeys = Object.keys(groups).sort((a, b) => Number(a) - Number(b));
        if (!groupKeys.length) return `<div class="empty">Not enough data</div>`;
        const width = 920, height = 280, pad = 42;
        const all = groupKeys.flatMap(key => groups[key]);
        const xMin = Math.min(...all.map(p => p[0]));
        const xMax = Math.max(...all.map(p => p[0]));
        const yMin = Math.min(...all.map(p => p[1]));
        const yMax = Math.max(...all.map(p => p[1]));
        const sx = value => pad + ((value - xMin) / Math.max(xMax - xMin, 1e-9)) * (width - pad * 2);
        const sy = value => height - pad - ((value - yMin) / Math.max(yMax - yMin, 1e-9)) * (height - pad * 2);
        const colors = REPORT_CHART_COLORS;
        const lines = groupKeys.slice(0, 8).map((key, i) => {
            const pts = groups[key].sort((a, b) => a[0] - b[0]).map(([x, y]) => `${sx(x).toFixed(1)},${sy(y).toFixed(1)}`).join(" ");
        return `<polyline points="${pts}" fill="none" stroke="${colors[i % colors.length]}" stroke-width="1.8" />`;
        }).join("");
        const legend = groupKeys.slice(0, 8).map((key, i) => `<span style="color:${colors[i % colors.length]}">●</span> ${esc(curve.xAxis)}=${esc(key)}`).join(" · ");
        const maxPoint = all.reduce((best, point) => point[1] > best[1] ? point : best, all[0]);
        const xTicks = linearTicks(xMin, xMax, 6);
        const yTicks = linearTicks(yMin, yMax, 5);
        return `
            ${statsTable}
            <svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(curve.curveId)}">
                ${svgGrid(width, height, pad, xTicks, yTicks, sx, sy)}
                <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" class="axis" />
                <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" class="axis" />
                <text x="${pad}" y="${pad - 12}" class="tick">${esc(curve.zAxis || "z")}</text>
                <text x="${width - pad}" y="${height - 12}" text-anchor="end" class="tick">${esc(curve.yAxis || "y")}</text>
                ${lines}
                ${svgTracer(sx(maxPoint[0]), sy(maxPoint[1]), width, height, pad, `max ${reportValue(maxPoint[1], "", 2)}`)}
            </svg>
            <div class="legend">${legend}</div>`;
    }
    return `${statsTable}${svgXYLineChart(curve.points || [], { yLabel: curve.yAxis || "y", xLabel: curve.xAxis || "x" })}`;
}

function svgCurveGroupChart(group) {
    if (!group || !Array.isArray(group.curves) || group.curves.length === 0) {
        return `<div class="empty">Not enough data</div>`;
    }
    if (group.curves.length === 1 || group.curves[0].points3d) {
        return svgCurveChart(group.curves[0]);
    }
    const xAxes = [...new Set(group.curves.map(curve => curve.xAxis || "x"))];
    const yAxes = [...new Set(group.curves.map(curve => curve.yAxis || "y"))];
    const stats = `<table class="mini"><thead><tr><th>Curve ID</th><th>X Axis</th><th>Y Axis</th><th>X Range</th><th>Y Range</th><th>Points</th></tr></thead><tbody>${
        group.curves.map(curve => `<tr>
            <td>${esc(curve.curveId)}</td>
            <td>${esc(curve.xAxis)}</td>
            <td>${esc(curve.yAxis)}</td>
            <td>${reportValue(curve.xMin, "", 3)} to ${reportValue(curve.xMax, "", 3)}</td>
            <td>${reportValue(curve.yMin, "", 3)} to ${reportValue(curve.yMax, "", 3)}</td>
            <td>${esc(curve.pointCount)}</td>
        </tr>`).join("")
    }</tbody></table>`;
    return `${stats}${svgMultiCurveChart(group.curves, {
        title: group.category,
        xLabel: xAxes.length === 1 ? xAxes[0] : "curve input",
        yLabel: yAxes.length === 1 ? yAxes[0] : "curve output"
    })}`;
}

function epwChartSection(weatherData) {
    const charts = [
        ["Dry Bulb Temperature", weatherData.dry_bulb_C, "°C", REPORT_COLORS.dryBulb],
        ["Dew Point Temperature", weatherData.dew_point_C, "°C", REPORT_COLORS.dryBulb],
        ["Relative Humidity", weatherData.relative_humidity_percent, "%", REPORT_COLORS.relativeHumidity],
        ["Global Horizontal Radiation", weatherData.global_horizontal_radiation_Wh_m2, "Wh/m²", REPORT_COLORS.globalHorizontalRadiation],
        ["Direct Normal Radiation", weatherData.direct_normal_radiation_Wh_m2, "Wh/m²", REPORT_COLORS.directNormalRadiation],
        ["Wind Speed", weatherData.wind_speed_m_s, "m/s", REPORT_COLORS.windSpeed],
        ["Atmospheric Pressure", weatherData.atmospheric_pressure_Pa, "Pa", REPORT_COLORS.atmosphericPressure],
        ["Total Sky Cover", weatherData.total_sky_cover_tenths, "tenths", REPORT_COLORS.totalSkyCover]
    ].filter(([, values]) => Array.isArray(values) && values.length > 1);
    if (!charts.length) return `<div class="empty">No extended EPW weather fields available.</div>`;
    return `<div class="grid">${charts.map(([title, values, unit, color]) => `
        <div class="card chartCard"><h3>${esc(title)}</h3>${svgLineChart(values, { yLabel: unit, xLabel: "Hour of Year", maxPoints: 700, color })}</div>
    `).join("")}</div>`;
}

function formulasHtml() {
    const formulas = [
        ["Annual PUE", `<span class="math"><i>PUE</i><sub>annual</sub> = <span class="frac"><span>∑<sub>h=1</sub><sup>N</sup> <i>P</i><sub>facility,h</sub></span><span>∑<sub>h=1</sub><sup>N</sup> <i>P</i><sub>IT,h</sub></span></span></span>`],
        ["Facility Power Balance", `<span class="math"><i>P</i><sub>facility,h</sub> = <i>P</i><sub>IT,h</sub> + <i>P</i><sub>elec,h</sub> + <i>P</i><sub>chiller,h</sub> + <i>P</i><sub>drycooler,h</sub> + <i>P</i><sub>pump,h</sub> + <i>P</i><sub>fan,h</sub> + <i>P</i><sub>aux,h</sub></span>`],
        ["UPS Efficiency Loss", `<span class="math"><i>P</i><sub>UPS,loss</sub> = <i>P</i><sub>IT</sub> · (η<sub>UPS</sub>(<i>LR</i>)<sup>−1</sup> − 1)</span>`],
        ["Transformer Loss", `<span class="math"><i>P</i><sub>TR,loss</sub> = <i>P</i><sub>out</sub> · (η<sub>TR</sub>(<i>LR</i>)<sup>−1</sup> − 1)</span>`],
        ["Thermal Load Assembly", `<span class="math"><i>Q</i><sub>cooling,h</sub> = <i>Q</i><sub>IT,h</sub> + <i>Q</i><sub>pump,h</sub> + <i>Q</i><sub>airflow,h</sub> + <i>Q</i><sub>aux,h</sub></span>`],
        ["Chiller Power", `<span class="math"><i>P</i><sub>chiller,h</sub> = <span class="frac"><span><i>Q</i><sub>cooling,h</sub></span><span><i>COP</i>(<i>T</i><sub>cond,in,h</sub>, <i>PLR</i><sub>h</sub>)</span></span></span>`],
        ["Dry Cooler Leaving Water", `<span class="math"><i>T</i><sub>LWT,h</sub> = <i>T</i><sub>OA,h</sub> + Δ<i>T</i><sub>approach</sub></span>`],
        ["Affinity Law", `<span class="math"><i>P</i><sub>variable</sub> = <i>P</i><sub>rated</sub> · <i>s</i><sup>3</sup></span>`],
        ["Peak Facility Hour", `<span class="math"><i>h</i><sub>peak</sub> = arg max<sub>h</sub>(<i>P</i><sub>facility,h</sub>)</span>`]
    ];
    return `<div class="formulaGrid">${formulas.map(([name, eq]) => `
        <div class="formulaBox">
            <div class="formulaName">${esc(name)}</div>
            <div>${eq}</div>
        </div>
    `).join("")}</div>`;
}

const SKYVAULT_REPORT_LOGO = `data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAw0AAABUCAYAAADAiNtCAAAACXBIWXMAACE4AAAhOAFFljFgAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAACAYSURBVHgB7Z3LdhtHkoYjiwTd077BIHWOm+w+Lj2BxScwuZudpeWsBC17JeoJTC1nJfEJSD2B6eWsRO96VpKfwOXjoVpzRMAwqZ5WA6jMyagCeJFIoDLqgrr83znspklQBCurMiPij4siUFp832+fng4fKqIu/yeRGpCil/bzZ73e8QGBXIiv+6hrr/vXyqOBMfQTrnd6Ll/X6AuKfmy1WkevXwcBCeF/8x9no7vGGD/6gucdnZz8zxGBTODr+/bt+A6R+dZoahuin1ZWWodp1qxI2m3fX1oa3jFG+R4Z+/7VV/x1fq5Jm9+N3U89TwVv3hy/JAAAADNRBErJl1/6/mg4fE6Rs/AhylNPT06OHxHIlE7nz9ZJM7vWSGq/961Aed4DGKQyZlzXgSHzuN//+1NypNNZ/06R2sFa5cPa2p+3jNb7dM0exPvPJ5+0HgdBMKASMXUitaFv7H/evebeuBmljuz/PkvryAIAQF3JzGm4KaJTR6zx8wtHqHq9V4eUA3zwnZ0OX9ANDsP5+4DjkClr1gi1kdTdWa+xxug2jFE3klxX6zg8cnEcVlfX9+0PdWe+SNG9vJ7RumOv7117fb+f+SJrZFsFbptKAAdZhsPh/RucSHeUOlBKPavrs87ndbtNg7I5fVWGr+ny8thXygzyUq4ip/gfI58/hzqWjKnC7WWxLzQMTWrwvrIsdhoiw/Ys3CKjvyXXiE59COwVfJS1YbK6utElY/aTvPbTz1a+aMLGH0c9zX17vX17r9m/V/2QZcrQRNn5OcFLB62VlU1EIpORyPicYK/r7STX1eH5GNjn4zYMIzfmqZyXcXX2suZSCucu5YF1Hqzy8LgOzzuv63g8emg0O9vn53XAzl9d/sZFcIOKGthAyUG//+oxZUB0/hnznd33tt7/HZ99trKHPe56Op2NJ3ZtdgikgoN+03vZ2Wm42KQziujUgYwjmmurG8/N1c1hxq82j04WeGjnTWTAjEb7dP31CLwldS+LiIs1RPl3dBO+PLDG6CY26tnExufoRdJ9wm5Mj+3GtDvvdauddXbufEpA0n8TXGAP2h27rzxJ8lp7gLw86b/apAUQO6Rqv4hz6PKhWUVu3dq4o0N6PuNaBdZp34bj4IY9N57TjLOan49PPlvZTnNWJFBqsXbXAIchW6Z7oJf0B9hZ4Bzis9PRz3FUBw7DOYb2+fpQRpwXdSZC1XYdOLoSRTxv3pR9HZrnbJxSSpShOw4v99+eRpFYcAMX0erk+0SSNWi3o+fMp4TYvephls9mE7AH7cOkr7UHyZ1FXF82CGIFq5hziM88a7y9yGKvKRp+z3afnHetoucVz0py4ntwdnCPn4+zs1EipfU6WFU181W0OLAGzuHrBochW6I90NpkiZwGfiHn2MNZuJH229N/dQlkRhRd0TpJikQ7iw3TON7XfBhE6gS4lvFwyAel7/Iz5KnP57/onev+w8ooDo+ERKlfjus2GLwr7Exgo5aju4swCPiZZ8O6ao6D3R+/o2Rr6uNZSQbfA4nvQetYsA1FEjglKe/fUUOsrXqfQOZYm+z+XKfBwXhrNMaoLQKpmRoFxiVH2W6Y7faXPqVBee4pTsZ0WX0jcAWOwLGBRe78NP8lf3CW+aE2OJDUSLnEYPA6oAKI2r+ezlQeC3kblXMcHK6XUuobAnMZDkd3XV5vjHF6PXPrls97qJ/09WzQEYgwi90j6sxspWFy+O8SmE+iKCmYBefdRl2jBA/80pInMVLPUYr2SACrb9bJwWY9YS1qgyqLAodhOLc2ZzAIBipujekC1IYESFQGcl8LMewwCJ3RrKmM4+CazkdOqbHNRbk+J8Y42wdah77L6+2z6BMA+eLf6DSgiMQRbX4nIIY7UOjQzG0zmxfcWlFJDSBjnrLDQw2H11AcZFBqL3HEWinnglSoDQkQqAxKsBYSUqhXeVGRGoB3uOdzIf80bY801k6MEheeg5vhwv5rnYY00cLG4qlDAs7E6Ujr+4r03CjzLMJQu6cXvcc4bN0jbkHoTpsLDatYJJkV7DRJ15A3ol7vOPF+I3TwoDbMQKIyRJ2TCphjUOKiRv/t2xHSEwEoG8YcEcgcc53TkLBaH1wlyHJmQFO4SEeaM6RrHtaAzCKvmlNfQq23hVGKxnYfuejOIiIYa32PXBGqDQSuR6AyGKsOUc5EjrjgvRWF0WYHBagAlIvQFKOANgvF9tHVlqtl36DLCV9I5W70NJw4HYkyKLC31z8MH1BGsPOhPPF6+mna61URdpKSDgK7hoCdNInDJ1UbJhF1cAlRLUNBgRKHzj8zUaSsEqkOrOP4mD+izzOqxzBao4saACViMDh+aUg9IpAdyjzgs/qK05DVBt0U+NAJdbjJNyiBRMTzPrhehlNZUueFWqOTtrPu3sIGqXjDiVrfbSQajFUHJk6STwLY2U61dpJ8egRFPkRyTQqoZZgEsbokRg3YQQj1yhcn/ePNXv/4wUn/1S5/RJ/3jrf5e/Zv4aBDQHL8Tmd9lwAApaHfP36qPG+b0j3bjSe2c9XmdIDx8vQbq6t/uUsm7FIq7Cat6KUx9JOxC7WkqLbFKKOwdTQYYAKjC2wEvD0dfq+yKGg0dBialQecUkQ5wBvOWme9be9j97QNbXY6nT/90q/xpG4myXCjm+BJ5oPBq1TONjt3a6sbR47t9XyOrCOdMCZSGdw75hSpMshQai8MW7vz9ofJ9w/4I56Ezc+7ezBjkvq2SwCA0jCpubrdbm/cWV5e7CBcq0h2yWl+hNpTC66VHY+Xg/ft3HOnwUZ+ufOJEI7omL2xbj3Ny4gD1Ybbko6GIzaiUz+4bHCe/Ja/Qc4RSfu+Odrp3FJVkXqytvbnQgpFF0E0v0VYnGr3mce9rBwqjni7Oi5xZP2AQKlVhtFw2CUB0f7Qe+V8f3GgoN3+8nDJ8yTpdm04owCUkzJkg9gzc8vFxvZsAP5NCe2HKD2JC7nEwzA4oqNbt9nAgsMArmMSkT7IIh2J5caTAiP4Nlq5Y6J8aHdsZKGWHZVWV9fvipslWIWob/cKyghhbYOP4tVK1DI4EzkMKfYHTpcTN0NA6hsAoOZEToMRRFKjn+OIYe94B84CuA42mK13/SKLdolxXp3eLjpyz/e21qG4FWvlpsfOIc4zV9LCz4BTyihj7D70jBwxMPDqV8tgA1hZBBSiOhvlSe5TH4X2AIA6ExdCG7pLjrDDkGXEENQLjuSOhqMXmQxkYmOgd5x5wXNS4ugjd1SStWIdD4ff16EV6yRl5LlQMZp0Sso+wDCJfAfkQlSw3ly1oYYqQ5BkonhSer1fD0XdleCMAgBqjBcfnM5GQACHAdxElO+utdS4vIQ10hXdcxn8lRdRTqQiUUcldpzOzkaV7qiUrrVq1N85X6dPEAFvstqgnArypj9UapXhceb3l+zvReobAKC2eKT1FrmiMDgDfAgf+DaC+TyL4YA8bZbb2U7bfJUBjrLGPd4FWEOoY50pqihnZ0NOSfJJwqS/M+UI1IbkCGvYSq0yfPppK/N9Qlgvg9Q3AEBt8YzyviY3MP0YfECcjmQj0dKC+ssotTfWKwtLR5rFSaSwySbhWoeDuzGJ6ocWCStHkhRGJq57KsbxM4J1aaSBV7NaBq5pCYKc6upks0AanfoGAKgvnnLt0a3UDwTAJXi6c5yOlH66Mw9aKntxfa9/vCOeJmvM01u3NtLXeRREtLZS5cg6f0WmMWrdOnCuO2mYgVdHlUFrfUA5AbUBAAAu8IyzoWeOCACK89xXV9e/j6c7pyaI05GOD6gCjMOWuKOSDk0lWrGycyNdWza0iq5FYUeT58WQI40y8GqoMuSuSEJtAACACM+1WNULVUCg8bBBeXY6fCFNW7mComehXtksYzrSTbCBKu7nbv0tTuUqc0clNuLYuSEZwTgMM2+tmoSxXnkKteF6eE0lKkMYhkeUM2VUGaZAbQAAgBjP8fU0ohAzGRoOp6zokDJIR4qHMfV6r7pVnPXBTo7yuBWrCP/sbCQ1ynPlorWqaH2D3DslzQBqw81IDPMiIvkTlWGL3Dkq7D6D2gAAAO5OA2guk3Sk/ThlJf1051CrzSKnO+cBRyENKVEr1tio2ChdK1aeK0FCh5DnWSxaMYLa8CHC9J9CIvn2fuPmAD45Yp3Twrr4QW0AAAA4DSAhbHRM0pG6lJJ4ujOnIx2/pBrQ7x8/lbZiNdrsdDp/WvgciimdzsYT6UA+Vo3KsKZQGz6kzCqD/T1dcuegcOcUagMAoOHAaag49sD9inKG05F4ujNlkI7ELTjj6c7VS0eaRdSKValnJECRemIVnPS1ISnh1qrW2BY5MNG6lkg1gtpwgbTIGCrDVaA2AACaDpyGiqOEUeEkcDoSR56zSkdSnrdd50niYdjaMaRkkXZD+4vsqMROS1VaqyYBasMFwiLjA6gM1wC1AQDQYOA0VBxOJcmjCw8f6G9Ph8+lkefLxOlIepsjdVRj2FDVOhS3YuXi40U4DnEkWu2TgGhyd9japRIiVRuqNEdjHlKVoYhIvnVmtqgiKsMUqA0AgCYDp6EGnJ4OM82J56gzpyOZLFQMG4WO05Gq0041Dfx3cjGwtBUrFyEX2Yr1olOSSEkKxlrfK2uqmVRt0JoeUk0oq8oQITOkDxa+l0BtAAA0FDgNNcBGex9mFaHmdCQrX3yfPh2JpzvTvaIHfJWBqBhYeaI5BeyonZ2NCumoxM6JvLWqGiyytWpShGpDtwrD9+ZRZpVhdXWjSxVTGaZMFNOAHIHaAACoOnAa6kHbRhRF6SVT2MCwB3k26UicshJNd351SA2l1/v1UNpRiQ29Tmc9dwPj7GzI94xPEpR5UAX1SKo2CCP0pQIqQ45AbQAANBA4DXXBHkjW6Bc5DnyQRRFn2YClqyi1Z6O7jUlHmkXUUYmUs8HKWIdjN89WrNwpSTrNmzslVckhbKLaAJUhX6yCekAyteE+AQBARXF2GlpLS1sEyok1ElY76z8nNXam3ZGM1hlMd1aDeLrz8U7d2qmmodc/3pEUTjLcijWPolxuoSvtlMQOQ9U6YE3uR+d2uMPhsEsVBSpDAcjUhlqkvgEAmgk7DYHLD2i74Zehpzy4ES5s/ZlVh5uk8ImzsMPD2rJIR6JounNY+enOeTEOW9KOSqRDk2lHJb4n4ha6AgwdVrVlrr0/nf9mrhUqsig9K6AyFINUbahD6hsAoJksk/JektG+w8/4XChrI9rUHKKi3pcq/nj25k0FJhlbo8FEysNG9N4vfZ0nO/uKMsJejzBcgbowA7427faX20ve0gtBgXlUrGyN180gSHeNJ52SpLUvQWhWRMXdZYCj1HbPYrXBJT2kPelMtksVAipDcdh99JlV39z+plhtePz6dRAQAABUCM8alj8SmIM19IzZMtrs2MjvC04BmkTMKkD83s8/MpjqPCVOR3rVhcMwn7gVK22TDP/sbPQ9peCitapo/YO4U1K119n+DbvkSNXUhonKsEWOQGWQIaqXocixa1xXOQBA9fG0Dhvb4SYFfDDvc7ehpuanKh7WhnQkJ+JWrEoWrY86r2yIW7Hy/AcSOow8d6IOhe3R32DIdb9rZz0HJU/sOrOS4pMbUBmESLtz2Wtxv4qpbwCAZuPxhiwt1Gw81pDj6G2dJsgmxvOeoKDPHc6DlrZiZaXLtRUrGybs3EoH9bGaFDk7NUEtec4GXlXUBn4e7Tp3yRGoDOkQqg2VckYBAICJuydJukCAKT4XqzbNcWAjlB0mOA7uRK1YlXLu5sNwK9akHbK46JmL3aWtdLlTUt3UJB7MJQiSVMLAq53KYNepzrNAqlpoDwBoLpHTEE+4lPWTBxHtrLvcVAQfjoOMMGztGFLSCP60Q9Zz7oLFzkG7ba0P+8GfsxoRqQtpWukqtVfVTklzEQRJqmDgSVQG5Xki59UFqcqgKhTMgtoAAGgC53MaQt3aJWFbSBCReipzRWED9gXa8LrB0UmtQ3Er1girINgIZzRnY8kb/swf/DmrEWkG9fFEb563QTWljmqDyDC31yAOGOWMUGUo5L1lBNQGAEATOHcaeNPjDikEx0FOPJW5S82jzW1485xgXEfijkr8zLl3X8mRYKz1Pao7dVMbBIZ5EZH8JqgMU6A2AADqzpWJ0BdGDBwHMcaIO9xUHZ5g7Fqo23SinG3llWT+gRrErVWr3ylpHnVSG8qsMii3uRiTH6qWyjAFagMAoO5473/hkuOQe65rTWnfNIk5F2LDJ6BMiKJkAaWAU2PgOLjR6/16aEg9okWjzIMmOAzn1EVtKKnKwPugkaXJVfbsgdoAAKgz3nVfZMOh13/VVZ63jXas7hit3aNrQpQxP9q1us1rRdFh657qwmvMbUBD3brN/5a0s8/5v8cdflbXv0f0LDn9/vFTaSvWLOBOSb3eq0bNbKmD2iBM/wlKW8tg3xu3JaaKArUBAFBnvFnf5IPlpHe8bZWH22zQxAdsqfKvy8oWFQyvFTt6vf7xF5GzxwaooUN1oURcfEQDrtSep9SDUK98wWvMbUCnE3/tod1NbcAauvv2FJ2VXOA1WITjwA5DbTslzaPqaoOsyLi8KkMN2n9DbQAA1JXlJC+apCzsUgOJInnxwew7/JjPRkUQBAtxsCZRxCNKARuwa511NijFqUaXZjlsv34dBATmksV1T441bBQ96lc4spsWflbWVjeOHA3c9tvTf3Xt/y90hsVkb/LJjWIi+Q1UGaZw8MU+w3uuz/DEGX26qHMDAADm4RGYCR9iniD6NRi8q7zUzAZsBrn2mOXgSDz8bSldO9b5BKGm7ToYaakRPN/2uXhIiwYqQ2mB2gAAqCNwGhIwCsMjaiicax9qtZkyLQ2zHBzh4uh8GhKoQVy/srI5GBxLh8vVCmFtg7/I9srSWoYinETrMEhqumqhMkyZpHo6P7uobQAAlBk4DWAubFyGOrSOQ6rIN2Y5ODJtSMA1RZTaeZg6C63bl+tXwARJlFuWgpMNJVUZIkXRmC65UiOVYYrdMyXpa1AbAAClBU4DSERWMzwwy8GdK86DUg8cVZ8gLniHszCLSR1QQG4sRG0os8owGo0aW8vwPpNaQJHaQAAAUELgNIDExI7DyqYhlSqthVuyrq1tNHYInpTIebDGlVLkcv2P3tifgbOQAFm0u7D2yudAZagM1tHfJXfai0x9AwCAm4DTAJxg47PfP95MO8vBaLODWQ6gTEyi3QG5YMxWkcMcoTJUC6nasNDUNwAAuAE4DUAEZjmAWiLppFSggackygZUhoUSaiWpbfChNgAAygacBiAmi2Fkl2Y5+ATAgomj3o6dwgpSG4StTKEyLBhuJCHozpWR2vAH57avBAAANwCnAaQininAxbmpiGY53Lq1cYcAWDCKzB45UojagFqG6iL7W/20zqiglqmNlNEEKO9zKhvugx4BcAZOA0gNRwvjWQ6pOiv5OjTPMcsBLBrRYK6c1QaoDNVGOAskI2fU7V5++3aM4M0clKOBbhX5X8gRTR6aV4DSAacBZEI8yyF1S1bMcgALh6OzpVMbBP+2EfwNrkBlcEA2CyS1M6pc92QdwmmYAd/z9tlyukbWYQzIEc9bCsgNHyoRyBs4DQlotf6ABzEBmOUA6kKZ1IbISBGoDFqbQ8oZqAzJWZTaYA3cn5xer7xvCdyIvee3yBEjcBpGo3fOSgNUIpA3cBoSYMwYTkNCprMcRIV/l8AsB7BIyqQ2SAxzQ/Rs0u4zN6Qqg0k93bzCLEBtcJ6rU3Ab4coheMY/+WTZebZR/Py6BS7s/oP0XpArcBqSoPUWOZL3gV1m2OA66R1bxUGlSo/ALAewSMqgNggNc6sy6APKGanKUMR7KyuLUBuWllpH5IjBnIhrEc1JsesdBLLhmo6DPHnh7uO8BHkCpyEBxrE3uo2Sp5qYXBd6/eOdLGY5nJ0OX6AlKyiaMqgNQsP8qMwqQ5MDKhEFqw1v3gQvy9pGuHIInm1lzI8kxf1n26enQ9QEgtyA0zCHycbpO/yIfc7dOyXUlSxmOdCkJSscB1A0i1QbpIZ5qHXuRcZQGeQsqLbBOSXMaL2PqPUFnU6ULuuTI+M097znHZEj9rx9iLMS5AWchjnwxkmueCr3AsQqcTHLQYkk2gmY5QAKZ5Fqg9AwPyhGZSDn3Gl7HQ8brzJMKVhtULIzyX97OnxOgNY669/Z+9c5gs9ZB2nueXYwBedmezwcIq0X5AKchhmsxR18fHIkDMMjAleIZzlQ2s5KmOUACmcRakOZVQZrkNy3f6CzQTLW+beArQpFqw3i30d0p+l1ZWwH2OuwSwKMUqnveVHQwq4bO3xwHEDWwGm4AelGkTayUGeyneWAlqygGMRqgzC9g3+GVTVypxCVwe6LXXLnAPviexTdSUk6G6OhdWX8HHJKktRhoIxaC8dBC3fYcUA9IMgaOA3vkXajyCKyUGeym+VAu3AcQFGI1IZJeofLoc37zyQlJPHPTClOZSjne6saVVEbJnB66M+85zbBCGXHjA1uSUrSORkNMOSgBcnbFEdpvZOuTwCkBk7DBD6s+cFKuVE0cmiRK9NZDjYUkqr2A7McQFGI1QYb7Ut6aE8NFf4ZcgcqQxWpitow/XG7507u5/261ZdNAoY79m97blVCkeN+iUxtAet076aoCeRUx/3Vznrk9KEuEKRhedY3+SE6OxtueaRqmxcXGmrbjfDrs9PRXUme7mUkRkVTmURP7q12NmwE1zwkIZNZDv6nn648kPbCBiAJrDYseUNJlHd6aH9nSO15nno5Hi8H/I3l5bGvtf7GRoC3jGAezJSCOiZtEVSGTOHov70vAnLu0BepDUfkSPz7NvbS7LkU389dHVLX/lsD4lkChgJ7/lWua6B9Hr8iZTjllVN5fBV/MTUTNT0z2Ole66zv2beWRl3nv29Xh2b3fN0aALe8NfZvtTbCEWyE9FzrNLCzcHo6fGgNaY64t3UWT1FJUZQZwUn/76LcwybDsxzsZjhItRnGObd3bCR0+/XrICAAcoAd3ZQGlz20zRPr6JJ1PqIvGD3Zg0yqPbaYSL4sLQYqwzw4+m+dSqefmagNcXcdN0Ld2rX337eULpI+fSNscG9Fn1EVMZm/cfvPPc7jnucuhFYJ+dbuIRkoBRfrVnfsemzx/1gbIbAq0mNkg6Tjg/SkaU6tinL6TW0VhqxRnveAgAjeDG3E5xGlA7McQO6wwZWydXDGqEERkXzRJFyCypCEiRETkCNWbXAaOjqFnd9Qq3vluo/rAdeM9LnFeE5oHWLd5ESKb6fzJwy/S8EHTsPZ2eiJMKe2sXBkQRLxARf0+8dPSS3dy2KWA9rMgbxgg8ukH1aYGYbMHlSGGiCrbehKgyTcyc5KXGkDNeAqwTgMcw0eRs+TQoAyDYrUEwQX5VxxGqS9wZtM3pGFJtHr/XqYxSyH09MhIgkgNyIHN2URfybY91DE3gOVIX+kasNoNBLvddHvjIZuggyIugIW4STzOZmBMt9o0jw3TeeK0zApdAMJ4ZkM47B1j0BmZDHLwa5LmiI/AOYSmhU2tgJaHEFodEGGg/qW3IHK4IiStNU0RrI258BxyITCHIYpHLhQJVI8K0fK56bJXHEalDE+gUREDoNe2Z50AQIZMp3lYKMp0u4O7Xb7S58AyIk4Lzz9vBEhhRopSlDbBpXBHeEskNSw4xBqtUmLdYIrCWcacPvwRTjIXAuYQUovKCmaTCnX9YrToHHzJUPRs/I4DOW8sdLCm7DWre1SpIGUDOPynCr1O4FcyGpQoSOFRzWNcW6lCZVBgGQWiA1eZbL/TxXeFIGaxmHX6tFJ73ihdkCc0hvC4XMkq+fGCc87cnl5GOpSPotXnAbuH05gBoo39Ue93qtunhuFi0w91qa2RjVf495vr+4JZNigzkaLNeJ+dHj1EYHcOB9USAVMgrfBikVENV0NSagMclzVBqOUw14wG76v+v3jzUm+fEDgWmJ1QW2WpcU6r1uv/+o20pWSk+VzkxRulpN0L1WKDstqw1xxGlKOma818UYRFrJROBwcjYjosQzrtCEq9QPVGKvAHFCyQz2wDi6UmpyJnNv+8c4kNzygzCkmWHET8f2W2JCFypACt+5cahCGYebnEefLTxQ09xqLehPwMx6rC8elC7DyOWnX7TZh3eYR5PHcJEFrepBgLw3GoS5tofvS+19Y+ejjHz3lde2nfyAQOQs8g8FuFI/fvXtbyIH97t3g3R//+Nn/2k/vzngZpyk8KOo9LZr/++fZ0b/922e/W+fh3+e8lCO//8HXkGoK/20fffSZfU6ja3FTvnmUxtKU+6MM/POfZy8/+ujjH5bilDCfbl6bhLCzQP/J93P/t8W1dOb77eOPP//vBJ31GrUn5YW9j/5m9382/u7MfKFSf/3tt78fUQ7wGtr3cWjv52eeUl9QfC+nvJ+rSRRIVfTIRvP/ys84lRisWwIUPbDPzd9oAbx7d/bant3/ddPZHQen9b0yB17UdV/kItIlz3tOmUyMrB68cNrQDxxhW2S+Iq/D8tLSvjFm6+KrUdRxj9WIJhZhr67+5S6Z8Aldc2/yunGf7KZEOifP6a799NKQpyiK8YyHkKFIf7Fwq1K7wd6/+vzOpyz7z/vwBGKjNU8u9t//XtOevSJY66zvWtXhuvkYQRTIKng20GT97T2tvjaZTCUuK/aMVfRy8gwe2mcwoAoTr5u5a/eib+q9brOJnT9VmplaUStrEwUGPrcfvytPHVZh3pea9c3YQNNbFP9RtcUa4b/YGyow9mM8Xn5ZNmOr3fbby8vjO/a9BVXfwLIgMpaXlrZIm2/tg9Y2hmVj80NTU3Eu7g8uim8FcBbKxXR9rDa9ZUh9ZQ0S//L3+f61xuFPSnlWNl86Kvv6XT4XeO/kAj8Mt8yHeK9r3VEmvMONSrjusAzXenpPc8dFwx+kOGpaVTvhd/v8BUuKBqOQXpYx9ShL2u2NO8vLqt2kbplNWNei+H8O5HHtcxcXEwAAAABJRU5ErkJggg==`;

function buildHtmlReport(context) {
    const output = context.output || {};
    const hourly = Array.isArray(output.hourly_results) ? output.hourly_results : [];
    const annual = output.annual_results || {};
    const peak = output.peak_results || {};
    const isAnnualBenchmarkMode = output.calculation_mode === "excel_benchmark_compatible" || annual.calculation_mode === "excel_benchmark_compatible";
    const isExcelReplicatedHourlyMode = output.calculation_mode === "excel_replicated_hourly" || annual.calculation_mode === "excel_replicated_hourly";
    const isExperimentalHourlyMode = output.calculation_mode === "experimental_acc_hourly_shape" || annual.calculation_mode === "experimental_acc_hourly_shape";
    const isConfigurationLibraryAccV2DirectMode = isConfigurationLibraryAccV2DirectResult(output, context.input);
    const isBenchmarkMode = isAnnualBenchmarkMode || isExcelReplicatedHourlyMode || isExperimentalHourlyMode;
    const hasExperimentalPeakWarning = isExperimentalHourlyMode && annual.acc_peak_power_warning === true;
    const isAccV2DirectMode = (isExperimentalHourlyMode && annual.acc_direct_solver_curve === true) || isConfigurationLibraryAccV2DirectMode;
    const isAccMode = isBenchmarkMode || context.input?.cooling_system_type === "ACC" || annual.annual_acc_energy_kWh != null;
    const benchmark = output.benchmark_components || {};
    const benchmarkAverage = benchmark.component_average_kW || {};
    const projectInfo = getProjectReportInfo();
    const heatGains = getCoolingLoadHeatGainInput();
    const weather = standardDataFiles.weather || {};
    const weatherData = weather.data || weather.hourly_data || {};
    const weatherSource = getWeatherSourceMetadata(weather);
    const it = standardDataArray(standardDataFiles.itLoad || {}, [["data", "hourly_it_load_kW"], ["hourly_it_load_kW"], ["project", "it_load", "hourly_it_load_kW"]], ["data", "hourly_profile"], "IT_load_kW");
    const dry = standardDataArray(standardDataFiles.weather || {}, [["data", "dry_bulb_C"], ["hourly_data", "dry_bulb_C"], ["weather", "hourly_data", "dry_bulb_C"]]);
    const pueSeries = hourly.map(row => Number(row.hourly_PUE)).filter(Number.isFinite);
    const facilitySeries = hourly.map(row => Number(row.total_facility_power_kW)).filter(Number.isFinite);
    const monthlyPue = groupHourlyByMonth(hourly, row => Number(row.hourly_PUE));
    const reportCurves = collectReportCurves();
    const curveGroups = groupReportCurves(reportCurves);
    const drySummary = summarizeNumericArray(dry);
    const tempDistribution = buildTemperatureDistribution(weatherData);
    const hasTemperatureBins = Boolean(tempDistribution?.rows?.length);
    const weatherPeriod = getWeatherPeriod(weather);
    const itSummary = summarizeNumericArray(it);
    const ghiSummary = summarizeNumericArray(weatherData.global_horizontal_radiation_Wh_m2);
    const windSummary = summarizeNumericArray(weatherData.wind_speed_m_s);
    const rhSummary = summarizeNumericArray(weatherData.relative_humidity_percent);
    const place = projectInfo.location || [weather.location?.city, weather.location?.state_or_region, weather.location?.country].filter(Boolean).join(", ") || "N/A";
    const projectLat = weatherSource.project_latitude ?? projectInfo.latitude;
    const projectLon = weatherSource.project_longitude ?? projectInfo.longitude;
    const projectCoordinates = Number.isFinite(Number(projectLat)) && Number.isFinite(Number(projectLon))
        ? `${fmtNumber(Number(projectLat), 4)}, ${fmtNumber(Number(projectLon), 4)}`
        : "N/A";
    const reportTitle = "Annual Data Center PUE Performance Assessment";
    const reportScenario = String(benchmark.scenario || output.project?.scenario_name || "Normal").toLowerCase().includes("fail")
        ? "Failure"
        : "Normal";
    const peakHourlyPue = !isAnnualBenchmarkMode && Number.isFinite(Number(annual.max_hourly_PUE))
        ? Number(annual.max_hourly_PUE)
        : null;
    const peakDesignPue = !isAnnualBenchmarkMode && Number.isFinite(Number(peak.peak_PUE))
        ? Number(peak.peak_PUE)
        : null;
    const peakDesignDemandKw = peak.peak_design_facility_electrical_demand_kW ?? peak.peak_design_total_facility_power_kW ?? peak.peak_total_facility_power_kW;
    const maxHourlyDemandKw = peak.max_hourly_facility_electrical_demand_kW ?? peak.max_hourly_total_facility_power_kW;
    const peakDesignWeatherSource = peak.peak_design_weather_source || "ASHRAE_local_cache";
    const peakDesignWeatherStation = peak.peak_design_weather_station || "N/A";
    const peakDesignWeatherStationId = peak.peak_design_weather_station_id || "N/A";
    const peakDesignWeatherStationDistance = peak.peak_design_weather_station_distance_km;
    const peakDesignTemperatureBasis = peak.peak_design_temperature_basis || "ASHRAE_20_year_extreme_annual_design_condition";
    const peakDesignDisplaySource = peakDesignWeatherSource === "manual" || peakDesignWeatherSource === "User Defined Design Condition"
        ? "User Defined Design Condition"
        : "ASHRAE Climatic Design Conditions";
    const peakDesignDisplayBasis = peakDesignTemperatureBasis === "User Defined Design Condition"
        ? "User Defined Design Condition"
        : "20-year Extreme Annual Design Condition";
    const peakPueMetricHtml = isConfigurationLibraryAccV2DirectMode
        ? `<div class="metric"><div class="label">Peak Design PUE</div><div class="value">${reportValue(peakDesignPue, "", 3)}</div>${hasExperimentalPeakWarning ? `<div class="subtitle">Review against design intent.</div>` : ""}</div>`
        : `<div class="metric"><div class="label">Peak Hourly PUE</div><div class="value">${isAnnualBenchmarkMode ? "N/A" : reportValue(peakHourlyPue, "", 3)}</div>${isAnnualBenchmarkMode ? `<div class="subtitle">Annual-equivalent assessment uses average equipment values.</div>` : ""}${hasExperimentalPeakWarning ? `<div class="subtitle">Review against design intent.</div>` : ""}</div>`;
    const generated = new Date().toISOString();
    const hasAnnualField = (key) => annual[key] !== null && annual[key] !== undefined;
    const accPerformanceRows = [
        ["average_acc_cop", "Average ACC COP", "", 3],
        ["min_acc_cop", "Minimum ACC COP", "", 3],
        ["max_acc_cop", "Maximum ACC COP", "", 3],
        ["max_acc_power_kW", "Maximum ACC Power", " kW", 1],
        ["acc_capacity_clamped_hours", "ACC Capacity Clamped Hours", " h", 0]
    ]
        .filter(([key]) => hasAnnualField(key))
        .map(([key, label, suffix, digits]) => [label, reportValue(annual[key], suffix, digits)]);
    const energyRows = (isAccMode ? [
        ["IT Energy", annual.annual_IT_energy_kWh],
        ["ACC Energy", annual.annual_acc_energy_kWh],
        ["Pump Energy", annual.annual_pump_energy_kWh || 0],
        ["Indoor Equipment Energy", annual.annual_indoor_equipment_energy_kWh || annual.annual_white_space_equipment_energy_kWh],
        ["Engine Radiator Energy", annual.annual_engine_radiator_energy_kWh],
        ["Electrical Distribution Loss", annual.annual_electrical_loss_kWh],
        ...(Number(annual.annual_terminal_fan_energy_kWh) > 0 ? [["MAU Energy", annual.annual_terminal_fan_energy_kWh]] : []),
        ...(Number(annual.annual_auxiliary_energy_kWh) > 0 ? [["Other Electrical Auxiliary Energy", annual.annual_auxiliary_energy_kWh]] : [])
    ] : [
        ["IT Energy", annual.annual_IT_energy_kWh],
        [annual.annual_acc_energy_kWh > 0 ? "ACC Energy" : "Chiller Energy", annual.annual_acc_energy_kWh || annual.annual_chiller_energy_kWh || annual.annual_cooling_energy_kWh],
        ["Dry Cooler Energy", annual.annual_dry_cooler_energy_kWh],
        ["Pump Energy", annual.annual_pump_energy_kWh || 0],
        ["MAU Energy", annual.annual_terminal_fan_energy_kWh],
        ["White Space Equipment Energy", annual.annual_white_space_equipment_energy_kWh],
        ["Electrical Distribution Loss", annual.annual_electrical_loss_kWh],
        ["Other Electrical Auxiliary Energy", annual.annual_auxiliary_energy_kWh]
    ]).filter(([, value]) => Number(value) > 0);
    const energyChart = svgBarChart(energyRows.map(([label, value]) => {
        const shortLabel = label.replace(" Energy", "").replace("Electrical ", "Elec ");
        return { label: shortLabel, value: Number(value) / 1000, color: reportEnergyColor(label) };
    }), { yLabel: "MWh", showValueLabels: true, valueLabelDigits: 0 });
    const monthlyChart = svgBarChart(monthlyPue.map(row => ({ label: row.month, value: row.value, color: REPORT_COLORS.pueLine })), { yLabel: "PUE", yTickCount: 5, yTickDigits: 2, barWidthScale: 0.86 });
    const contributionSummary = buildPueContributionSummary(annual);
    const coolingUnitInfo = buildCoolingUnitArchitectureInfo(output);
    const itEnergy = Number(annual.annual_IT_energy_kWh) || 0;
    const pueContribution = (value) => itEnergy > 0 ? (Number(value) || 0) / itEnergy : null;
    const pueContributionText = (value, signed = true) => {
        if (value === null || value === undefined) return "N/A";
        if (!Number.isFinite(Number(value))) return "N/A";
        const formatted = reportValue(value, "", 3);
        return signed && Number(value) >= 0 ? `+${formatted}` : formatted;
    };
    const pueContributionRows = isAccMode ? [
        { label: "IT Base", value: 1, css: "base", signed: false },
        { label: "ACC pPUE", value: pueContribution(annual.annual_acc_energy_kWh), css: "", signed: true },
        { label: "Pump pPUE", value: pueContribution(annual.annual_pump_energy_kWh), css: "", signed: true },
        { label: "Indoor Equipment pPUE", value: pueContribution(annual.annual_indoor_equipment_energy_kWh || annual.annual_white_space_equipment_energy_kWh), css: "", signed: true },
        { label: "Engine Radiator pPUE", value: pueContribution(annual.annual_engine_radiator_energy_kWh), css: "", signed: true },
        { label: "Electrical Distribution Loss pPUE", value: pueContribution(annual.annual_electrical_loss_kWh), css: "", signed: true },
        ...(Number(annual.annual_auxiliary_energy_kWh) > 0 ? [{ label: "Other Electrical Auxiliary pPUE", value: pueContribution(annual.annual_auxiliary_energy_kWh), css: "", signed: true }] : []),
        { label: "Annual PUE", value: Number(annual.annual_average_PUE), css: "total", signed: false }
    ] : [
        { label: "IT Base", value: 1, css: "base", signed: false },
        { label: "Cooling System pPUE", value: contributionSummary.coolingPPUE, css: "", signed: true },
        { label: "├─ Chiller", value: pueContribution(annual.annual_chiller_energy_kWh), css: "child", signed: true },
        { label: "├─ Dry Cooler", value: pueContribution(annual.annual_dry_cooler_energy_kWh), css: "child", signed: true },
        { label: "├─ Pump", value: pueContribution(annual.annual_pump_energy_kWh), css: "child", signed: true },
        { label: "MAU", value: pueContribution(annual.annual_terminal_fan_energy_kWh), css: "child", signed: true },
        { label: "Electrical Distribution Loss pPUE", value: contributionSummary.electricalPPUE, css: "", signed: true },
        { label: "Other Electrical Auxiliary pPUE", value: contributionSummary.auxiliaryPPUE, css: "", signed: true },
        { label: "Annual PUE", value: Number(annual.annual_average_PUE), css: "total", signed: false }
    ];
    const benchmarkComponentRows = isBenchmarkMode ? [
        ["IT Load", benchmarkAverage.IT, annual.annual_IT_energy_kWh],
        ["ACC Power", benchmarkAverage.ACC, annual.annual_acc_energy_kWh],
        ["CHW Pump Power", benchmarkAverage.pump, annual.annual_pump_energy_kWh],
        ["Indoor CDU / RTC / MAU Equivalent", benchmarkAverage.indoor_CDU_RTC_MAU_equivalent, annual.annual_indoor_equipment_energy_kWh],
        ["Engine Radiator Power", benchmarkAverage.engine_radiator, annual.annual_engine_radiator_energy_kWh],
        ["IT Electrical Distribution Loss", benchmarkAverage.IT_electrical_loss, annual.annual_it_electrical_loss_kWh],
        ["MEP Electrical Distribution Loss", benchmarkAverage.MEP_electrical_loss, annual.annual_mep_electrical_loss_kWh],
        ["Facility Power", benchmarkAverage.facility, annual.annual_facility_energy_kWh]
    ] : [];
    const benchmarkPowerItems = isBenchmarkMode ? [
        { label: "IT Load", value: benchmarkAverage.IT },
        { label: "ACC Power", value: benchmarkAverage.ACC },
        { label: "Pump Power", value: benchmarkAverage.pump },
        { label: "Indoor Equipment", value: benchmarkAverage.indoor_CDU_RTC_MAU_equivalent },
        { label: "Engine Radiator", value: benchmarkAverage.engine_radiator },
        { label: "Electrical Distribution Loss", value: (Number(benchmarkAverage.IT_electrical_loss) || 0) + (Number(benchmarkAverage.MEP_electrical_loss) || 0) },
        { label: "Facility Power", value: benchmarkAverage.facility }
    ].filter(item => Number.isFinite(Number(item.value))) : [];
    const benchmarkPowerChart = benchmarkPowerItems.length ? svgBarChart(benchmarkPowerItems.map(item => ({ ...item, color: reportEnergyColor(item.label) })), { yLabel: "Average kW" }) : "";
    const resultChartCards = isAnnualBenchmarkMode ? [
        ...(benchmarkPowerItems.length ? [["Cooling System Component Average Power", benchmarkPowerChart]] : []),
        ...(energyRows.length ? [["Annual Energy Breakdown", energyChart]] : [])
    ] : [
        ...(pueSeries.length > 1 ? [["8760 Annual PUE Timeseries", svgLineChart(pueSeries, { yLabel: "PUE", xLabel: "Hour of Year", color: REPORT_COLORS.pueLine })]] : []),
        ...(facilitySeries.length > 1 ? [["Facility Power Timeseries", svgLineChart(facilitySeries, { yLabel: "kW", xLabel: "Hour of Year", color: REPORT_COLORS.coolingEnergy })]] : []),
        ...(energyRows.length ? [["Annual Energy Breakdown", energyChart]] : []),
        ...(monthlyPue.length ? [["Monthly Average PUE", monthlyChart]] : [])
    ];
    const curveRegisterRows = reportCurves.map(curve => [
        curve.category,
        esc(curve.curveId),
        esc(curve.sourceFile),
        curve.zAxis
            ? `${esc(curve.xAxis)} ${reportValue(curve.xMin, "", 2)}-${reportValue(curve.xMax, "", 2)}; ${esc(curve.yAxis)} ${reportValue(curve.yMin, "", 2)}-${reportValue(curve.yMax, "", 2)}; ${esc(curve.zAxis)} ${reportValue(curve.zMin, "", 2)}-${reportValue(curve.zMax, "", 2)}`
            : `${esc(curve.xAxis)} ${reportValue(curve.xMin, "", 2)}-${reportValue(curve.xMax, "", 2)}; ${esc(curve.yAxis)} ${reportValue(curve.yMin, "", 2)}-${reportValue(curve.yMax, "", 2)}`,
        esc(curve.pointCount)
    ]);

    return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>${esc(reportTitle)}</title>
<style>
    :root { --ink:#222222; --muted:#555555; --line:#D8D8D8; --soft:#F7F7F7; --accent:#7A7A7A; --green:#555555; --red:#555555; --violet:#555555; }
    body { margin:0; font-family: Inter, "Times New Roman", Georgia, serif; color:var(--ink); background:#fff; }
    .page { max-width: 1260px; margin: 0 auto; padding: 28px 24px 46px; }
    header { border-bottom: 2px solid var(--ink); padding-bottom: 18px; margin-bottom: 18px; }
    .reportHeaderTop { display:block; }
    .reportLogo { display:block; width:210px; height:auto; object-fit:contain; margin-bottom:0; }
    .reportHeaderText { flex:1 1 auto; min-width:0; }
    .pageHeaderLine { color:var(--muted); font-size:13px; letter-spacing:.035em; text-transform:uppercase; margin-bottom:8px; font-family: Arial, sans-serif; }
    h1 { margin:0 0 8px; font-size: 30px; line-height:1.15; letter-spacing: 0; font-weight:760; }
    h2 { margin:24px 0 10px; font-size: 19px; border-bottom: 1px solid var(--line); padding-bottom: 6px; font-weight:760; }
    h3 { margin:12px 0 8px; font-size: 15px; font-weight:740; }
    p { line-height: 1.65; color: var(--muted); text-align: justify; }
    code { font-family: "Courier New", monospace; font-size: 12.5px; }
    .subtitle { color:var(--muted); font-size: 14px; line-height:1.45; }
    .meta { display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
    .metric { border:1px solid var(--line); border-radius:8px; padding:10px; background:var(--soft); }
    .metric .label { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.04em; font-family: Arial, sans-serif; }
    .metric .value { font-size:21px; font-weight:760; margin-top:4px; color:var(--ink); }
    table { width:100%; border-collapse:collapse; margin:8px 0 12px; font-size: 12.5px; }
    th, td { border:1px solid var(--line); padding:6px 8px; vertical-align:top; }
    th { width:32%; text-align:left; background:#F3F3F3; }
    .mini { margin: 4px 0 10px; font-size: 12px; }
    .mini th { width: 28%; }
    .grid { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap:12px; align-items:start; }
    .curveGrid { display:grid; grid-template-columns: 1fr; gap:14px; }
    .card { border:1px solid var(--line); border-radius:8px; padding:10px; break-inside: avoid; background:#fff; }
    .chartCard { break-inside:avoid; page-break-inside:avoid; break-before:auto; }
    .chart { width:100%; height:auto; background:#fff; border:1px solid var(--line); border-radius:8px; }
    .axis { stroke:#BDBDBD; stroke-width:1; }
    .gridLine { stroke:#ECECEC; stroke-width:1; }
    .traceLine { stroke:#A35A2A; stroke-width:1; stroke-dasharray:4 4; }
    .tracePoint { fill:#FFFFFF; stroke:#A35A2A; stroke-width:1.8; }
    .traceLabel { fill:#A35A2A; font: 11px Arial, sans-serif; }
    .line { fill:none; stroke:#4E5D6C; stroke-width:1.8; }
    .bar { fill:#4E5D6C; }
    .tick { fill:#666666; font-size:11px; font-family: Arial, sans-serif; }
    .legend { color:var(--muted); font-size:11.5px; margin-top:6px; line-height:1.5; display:flex; flex-wrap:wrap; gap:8px 14px; }
    .legendItem { white-space:nowrap; }
    .note { background:#F5F5F5; border-left:4px solid var(--accent); padding:8px 10px; color:#222222; }
    .empty { border:1px dashed var(--line); border-radius:8px; padding:18px; color:var(--muted); text-align:center; }
    .caption { font-size:12px; color:#333; text-align:center; margin-top:8px; font-style:italic; }
    .specBlock { margin-top:10px; padding:8px 10px; border-left:3px solid var(--accent); background:#F7F7F7; font-size:12.5px; color:#555555; }
    .formulaGrid { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap:10px; margin:10px 0 12px; }
    .formulaBox { border:1px solid var(--line); border-radius:8px; padding:10px; background:#fff; min-height:68px; }
    .formulaName { font: 700 12px Arial, sans-serif; color:var(--muted); text-transform:uppercase; letter-spacing:.035em; margin-bottom:8px; }
    .math { font-family: "Times New Roman", Georgia, serif; font-size:18px; color:#222222; }
    .math i { font-style: italic; }
    .breakdown { font-size: 13px; }
    .breakdown th { width:auto; }
    .breakdown td:last-child { text-align:right; font-variant-numeric: tabular-nums; font-weight:700; }
    .breakdown .base td { background:#F7F7F7; font-weight:700; }
    .breakdown .child td:first-child { padding-left:24px; color:var(--muted); }
    .breakdown .total td { border-top:2px solid var(--ink); font-size:14px; background:#F7F7F7; }
    .frac { display:inline-flex; flex-direction:column; vertical-align:middle; text-align:center; line-height:1.12; margin:0 4px; }
    .frac span:first-child { border-bottom:1px solid #222222; padding:0 5px 2px; }
    .frac span:last-child { padding-top:2px; }
    @media (max-width: 900px) { .grid, .meta, .formulaGrid { grid-template-columns: 1fr; } .reportLogo { width:150px; margin-bottom:14px; } }
    @media print {
        .page { max-width:none; padding:12mm; }
        .card, .chart { break-inside: avoid; }
        .page:not(.benchmark-report) table { break-inside:avoid; }
        .benchmark-report { height:auto; min-height:0; }
        .benchmark-report section, .benchmark-report .grid, .benchmark-report .card, .benchmark-report table { height:auto; min-height:0; }
        .benchmark-report .grid { display:block; }
        .benchmark-report .card { margin:0 0 12px; break-inside:auto; }
        .benchmark-report table { break-inside:auto; }
        .chartCard, .benchmark-report .chartCard { break-inside:avoid; page-break-inside:avoid; break-before:auto; }
    }
</style>
</head>
<body>
<main class="page${isBenchmarkMode ? " benchmark-report" : ""}">
<header>
    <div class="reportHeaderTop">
        <div class="reportHeaderText">
            <div class="pageHeaderLine">JUNO | ACC Cooling System | Annual PUE Assessment</div>
            <h1>${esc(reportTitle)}</h1>
            <div class="subtitle">Project: JUNO</div>
            <div class="subtitle">Cooling Architecture: ACC + Gas Engine + CDU</div>
            <div class="subtitle">Scenario: ${esc(reportScenario)}</div>
            <div class="subtitle">Generated · ${esc(generated)}</div>
        </div>
    </div>
</header>

<section>
    <h2>1. Executive Summary</h2>
    ${isBenchmarkMode ? `<p>This assessment evaluates the annual operating performance of the JUNO data center using an hourly weather-driven simulation with the project-specific ACC cooling architecture.</p>` : ""}
    ${isAccV2DirectMode ? `<div class="note"><b>ACC V2 Direct Mode</b><br>Configuration Library-driven ACC simulation using direct hourly Solver_Curve lookup.</div>` : ""}
    ${isConfigurationLibraryAccV2DirectMode ? `<div class="note"><b>Simulation Method</b><br>True EPW × Solver_Curve<br><b>Simulation Basis</b><br>8760-hour Annual Dynamic Simulation</div>` : ""}
    ${isConfigurationLibraryAccV2DirectMode ? `<div class="note"><b>Peak Design Condition</b><br>Outdoor Design Dry Bulb: ${reportValue(peak.peak_design_outdoor_dry_bulb_C, " deg C", 1)}<br>Source: ${esc(peakDesignDisplaySource)}<br>Reference Station: ${esc(peakDesignWeatherStation)}<br>Design Criteria: ${esc(peakDesignDisplayBasis)}</div>` : ""}
    ${hasExperimentalPeakWarning ? `<div class="note" style="background:#F5F5F5;border-left-color:#7A7A7A;color:#222222;"><b>Warning:</b> Direct hourly ACC power exceeds scenario peak ACC power by more than 10%. Peak Hourly PUE should be reviewed against design intent.</div>` : ""}
    ${isAnnualBenchmarkMode ? `<div class="note">Peak hourly PUE is not reported for this annual-equivalent assessment because equipment powers are represented as annual-average values rather than hourly dispatch.</div>` : ""}
    <div class="meta">
        <div class="metric"><div class="label">Annual Average PUE</div><div class="value">${reportValue(annual.annual_average_PUE, "", 3)}</div></div>
        ${peakPueMetricHtml}
        ${isConfigurationLibraryAccV2DirectMode ? `<div class="metric"><div class="label">Max Hourly PUE</div><div class="value">${reportValue(peakHourlyPue, "", 3)}</div></div>` : ""}
        <div class="metric"><div class="label">${isConfigurationLibraryAccV2DirectMode ? "Peak Design Facility Electrical Demand" : "Peak Facility Power"}</div><div class="value">${reportValue(isConfigurationLibraryAccV2DirectMode ? peakDesignDemandKw : peak.peak_total_facility_power_kW, " kW", 0)}</div></div>
        ${isConfigurationLibraryAccV2DirectMode ? `<div class="metric"><div class="label">Max Hourly Facility Electrical Demand</div><div class="value">${reportValue(maxHourlyDemandKw, " kW", 0)}</div></div>` : ""}
        <div class="metric"><div class="label">IT Energy</div><div class="value">${reportValue((annual.annual_IT_energy_kWh || 0) / 1000, " MWh", 0)}</div></div>
        <div class="metric"><div class="label">Facility Energy</div><div class="value">${reportValue((annual.annual_facility_energy_kWh || 0) / 1000, " MWh", 0)}</div></div>
    </div>
    <table><tbody>${tableRows([
        ["Site Location", esc(place)],
        ...(isBenchmarkMode ? [
            ["Cooling Architecture", "ACC + Gas Engine + CDU"],
            ["Calculation Method", isExcelReplicatedHourlyMode ? "Project-specific hourly ACC performance model" : (isExperimentalHourlyMode ? "Configuration Library Solver_Curve direct hourly simulation" : "Annual-equivalent energy performance model")],
            ...(isExperimentalHourlyMode ? [
                ["Maximum ACC Power", reportValue(annual.max_acc_power_kW, " kW", 1)],
                ["Scenario Peak ACC Power", reportValue(annual.scenario_peak_acc_power_kW, " kW", 1)],
                ["ACC Peak / Scenario Peak", reportValue(annual.acc_peak_to_scenario_peak_ratio, "×", 3)]
            ] : []),
            ["Scenario", esc(benchmark.scenario || output.project?.scenario_name || "N/A")],
            ["Active Energy Modules / Engines", esc(output.project?.active_units ?? "N/A")],
            ["Annual IT Load Factor", reportValue(benchmark.it_annual_load_factor, "", 3)],
            ...(isExperimentalHourlyMode ? [
                ["ACC Curve Source", esc(annual.acc_curve_source || benchmark.acc_curve_source || "N/A")],
                ["External Annual Adjustment Applied", annual.acc_annual_calibration_applied === false ? "No" : "N/A"]
            ] : (isConfigurationLibraryAccV2DirectMode ? [
                ["ACC V2 Direct Mode", "Configuration Library-driven ACC simulation using direct hourly Solver_Curve lookup."],
                ["Simulation Method", "True EPW × Solver_Curve"],
                ["Simulation Basis", "8760-hour Annual Dynamic Simulation"],
                ["ACC Curve Source", esc(annual.acc_curve_source || "N/A")]
            ] : [["ACC Annual Weather Factor", reportValue(benchmark.acc_annual_temperature_factor, "", 9)]])),
            ["IT Efficiency", percentText(benchmark.it_efficiency, 4)],
            ["MEP Efficiency", percentText(benchmark.mep_efficiency, 4)]
        ] : []),
        ["Design IT Load", projectInfo.capacityMw !== null ? `${reportValue(projectInfo.capacityMw, " MW", 1)}` : "N/A"],
        ["Project Stage", esc(projectInfo.stage || "N/A")],
        ["Minimum Hourly PUE", reportValue(annual.min_hourly_PUE, "", 3)],
        ["Maximum Hourly PUE", reportValue(annual.max_hourly_PUE, "", 3)],
        ...(isConfigurationLibraryAccV2DirectMode ? [
            ["Peak Design PUE", reportValue(peak.peak_PUE, "", 3)],
            ["Peak Design Facility Electrical Demand", reportValue(peakDesignDemandKw, " kW", 0)],
            ["Max Hourly Facility Electrical Demand", reportValue(maxHourlyDemandKw, " kW", 0)],
            ["Peak Design Condition", esc(peakDesignDisplaySource)],
            ["Reference Station", esc(peakDesignWeatherStation)],
            ["Peak Design Temperature Basis", esc(peakDesignDisplayBasis)],
            ["Peak Design Outdoor Dry Bulb", reportValue(peak.peak_design_outdoor_dry_bulb_C, " deg C", 1)],
            ["Peak Design IT Load", reportValue(peak.peak_design_it_load_kW, " kW", 0)],
            ["Peak Design Cooling Load", reportValue(peak.peak_design_cooling_load_kW, " kW", 1)]
        ] : []),
        ...(isConfigurationLibraryAccV2DirectMode ? [] : [["Peak Facility Hour", esc(peak.peak_hour_index ?? "N/A")]])
    ])}</tbody></table>
</section>

<section>
    <h2>2. Climate Data</h2>
    ${isAnnualBenchmarkMode ? `<div class="note">For this annual-equivalent assessment, the weather profile is represented through an annual weather factor rather than direct hourly dispatch.</div>` : ""}
    ${isExcelReplicatedHourlyMode ? `<div class="note">Hourly dry-bulb temperature is evaluated using the project-specific ACC hourly performance model.</div>` : ""}
    ${isExperimentalHourlyMode ? `<div class="note">Hourly outdoor dry-bulb temperature and hourly load ratio are applied directly to the ACC Solver_Curve.</div>` : ""}
    ${isConfigurationLibraryAccV2DirectMode ? `<div class="note"><b>Annual Simulation Basis</b><br>Weather Source: EPW Weather File<br>Simulation Method: True EPW × Solver_Curve<br>Simulation Basis: 8760-hour Annual Dynamic Simulation</div>` : ""}
    <div class="grid">
        <div class="card"><h3>Weather Source</h3><table><tbody>${tableRows([
            ["Project Location", esc(weatherSource.project_location || projectInfo.location || "N/A")],
            ["Project Coordinates", esc(projectCoordinates)],
            ["Weather Source", esc(weatherSource.source || "N/A")],
            ["Weather Station", esc(weatherSource.matched_station || weatherSource.station || "N/A")],
            ["Distance to Weather Station", weatherSource.distance_km !== null && weatherSource.distance_km !== undefined ? `${reportValue(weatherSource.distance_km, " km", 1)}` : "N/A"],
            ["Weather Data Period", esc(weatherSource.weather_period || weatherPeriod || "N/A")],
            ["EPW File", esc(weatherSource.epw_file || "N/A")],
            ["Location", esc(weatherSource.location || "N/A")],
            ["Weather Hours", esc(weatherSource.weather_hours ?? "N/A")]
        ])}</tbody></table></div>
        ${isConfigurationLibraryAccV2DirectMode ? `<div class="card"><h3>Peak Design Condition</h3><table><tbody>${tableRows([
            ["Outdoor Dry Bulb", reportValue(peak.peak_design_outdoor_dry_bulb_C, " °C", 1)],
            ["Source", esc(peakDesignDisplaySource)],
            ["Reference Station", esc(peakDesignWeatherStation)],
            ["Design Criteria", esc(peakDesignDisplayBasis)],
            ["IT Load", reportValue(peak.peak_design_it_load_kW, " kW", 0)],
            ["Facility Electrical Demand", reportValue(peakDesignDemandKw, " kW", 0)],
            ["Peak Design PUE", reportValue(peak.peak_PUE, "", 3)]
        ])}</tbody></table></div>` : ""}
    </div>
</section>

<section>
    <h2>3. Climate Temperature Profile</h2>
    ${tempDistribution ? `
        <div class="grid">
            <div class="card"><h3>Dry Bulb Summary</h3><table><tbody>${tableRows([
                ["Minimum Dry Bulb", reportValue(tempDistribution.minTemp, " °C", 1)],
                ["Average Dry Bulb", reportValue(tempDistribution.avgTemp, " °C", 1)],
                ["Maximum Dry Bulb", reportValue(tempDistribution.maxTemp, " °C", 1)],
                ["Peak Dry Bulb Time", esc(tempDistribution.peakTime.label)],
                ["Peak Dry Bulb Hour of Year", esc(tempDistribution.hourOfYear)],
                ["Distribution Total Hours", esc(tempDistribution.totalHours)]
            ])}</tbody></table></div>
            ${hasTemperatureBins ? `<div class="card"><h3>Temperature Bin Hours</h3>${temperatureDistributionTableHtml(tempDistribution)}</div>` : ""}
        </div>
    ` : `<div class="empty">Temperature distribution unavailable: weather data not loaded.</div>`}
</section>

<section>
    <h2>4. Methodology</h2>
    ${isBenchmarkMode ? `
        <p>${isExcelReplicatedHourlyMode ? "The assessment uses an hourly weather-driven simulation. Outdoor dry-bulb temperature is applied to the project-specific ACC hourly performance model, while scenario equipment powers and electrical losses are evaluated consistently across the annual operating profile." : (isAccV2DirectMode ? "The assessment uses Configuration Library-driven ACC simulation using direct hourly Solver_Curve lookup. The simulation method is True EPW × Solver_Curve and the simulation basis is an 8760-hour Annual Dynamic Simulation." : "The annual assessment uses scenario equipment powers, annual weather factors, and project electrical path efficiencies to evaluate annual facility energy performance.")}</p>
        <div class="card">
            <h3>ACC Unit Architecture</h3>
            <p><b>${esc(output.project?.active_units ?? "N/A")} active energy modules / ACC units</b> support the ${esc(reportScenario)} scenario. ${isExcelReplicatedHourlyMode ? "Hourly ACC operation follows the project-specific weather-driven performance model." : (isAccV2DirectMode ? "ACC operation follows direct Configuration Library Solver_Curve lookup for every hour. Indoor IT-side equipment uses normal indoor unit count and IT-load-based operation." : "The annual-equivalent case uses scenario equipment powers and annual factors rather than detailed hourly dispatch.")}</p>
            <table><tbody>${tableRows([
                ["ACC Unit Capacity", `${reportValue(context.input?.cooling_unit_capacity_mw, " MW", 1)}`],
                ["Active ACC Units", esc(output.project?.active_units ?? "N/A")],
            ["Calculation Method", isAccV2DirectMode ? "Configuration Library Solver_Curve direct hourly simulation" : (isExcelReplicatedHourlyMode ? "Project-specific hourly ACC performance model" : "Annual-equivalent energy performance model")],
                ["Hourly Dispatch", isAnnualBenchmarkMode ? "Not applied in annual-equivalent assessment" : "Hourly weather-driven simulation"]
            ])}</tbody></table>
        </div>
        <h3>Calculation Methodology</h3>
        <table><tbody>${tableRows([
            ["ACC Average Power", isExcelReplicatedHourlyMode ? "<code>Hourly ACC performance profile integrated over the annual weather year</code>" : (isAccV2DirectMode ? "<code>sum(hourly ACC Solver_Curve power) / annual hours</code>" : "<code>Scenario peak ACC power × annual weather factor</code>")],
            ["Other Equipment", "<code>Scenario equipment power × annual IT load factor</code>"],
            ["Electrical Distribution Loss", "<code>Load / path efficiency - load</code>"],
            ["Annual PUE", "<code>Average facility power / Average IT power</code>"]
        ])}</tbody></table>
    ` : `
    <p>${isConfigurationLibraryAccV2DirectMode ? "The dynamic ACC calculation uses <code>compute_pue_project(dc)</code>. Each hour combines Total Cooling Load, EPW dry-bulb temperature, Configuration Library Solver_Curve ACC power, CHW pump power, CDU / RTC / MAU equipment power, engine radiator power, and electrical distribution losses in an 8760-hour Annual Dynamic Simulation." : (isAccMode ? "The dynamic ACC calculation uses <code>compute_pue_project(dc)</code>. Each hour combines IT load, outdoor dry bulb temperature, ACC power, CHW pump power, CDU / RTC / MAU equipment power, engine radiator power, and electrical distribution losses." : "The annual calculation uses <code>compute_pue_project(dc)</code>. Each hour combines IT load, outdoor dry bulb temperature, equipment curves, electrical distribution losses, cooling power, pump/MAU power, and RTC / CDU / equipment load where configured.")}</p>
    <div class="note">Solar Heat Gain and Other Auxiliary Heat Gains are included in Total Cooling Load for Configuration Library ACC V2 direct runs.</div>
    ${coolingUnitInfo ? `
        <div class="card">
            <h3>${isAccMode ? "ACC Unit Architecture" : "Cooling Unit Architecture"}</h3>
            <p>${isAccMode ? `The model uses <b>${esc(coolingUnitInfo.count !== null && coolingUnitInfo.capacityKw !== null ? `${fmtInteger(coolingUnitInfo.count)} × ${mwTextFromKw(coolingUnitInfo.capacityKw)} ACC units` : "N/A")}</b>. Dynamic mode evaluates ACC operation hour by hour from ambient dry-bulb temperature and required cooling capacity per ACC unit.` : `The model assumes <b>${esc(coolingUnitInfo.count !== null && coolingUnitInfo.capacityKw !== null ? `${fmtInteger(coolingUnitInfo.count)} × ${mwTextFromKw(coolingUnitInfo.capacityKw)} cooling units (total cooling capacity = ${mwTextFromKw(coolingUnitInfo.totalCapacityKw)})` : "N/A")}</b>. All chiller and dry cooler units are assumed to run throughout the year with equal load sharing. Unit load ratio is calculated as required cooling capacity divided by installed cooling unit capacity. N+1 or staged dispatch control is not included in this version.`}</p>
            <table><tbody>${tableRows([
                [isAccMode ? "ACC Unit Capacity" : "Cooling Unit Capacity", esc(mwTextFromKw(coolingUnitInfo.capacityKw))],
                [isAccMode ? "ACC Unit Count" : "Cooling Unit Count", coolingUnitInfo.count !== null ? esc(fmtInteger(coolingUnitInfo.count)) : "N/A"],
                [isAccMode ? "Total ACC Capacity" : "Total Cooling Unit Capacity", esc(mwTextFromKw(coolingUnitInfo.totalCapacityKw))],
                ["Dispatch Strategy", "All units running"],
                ["Load Sharing", "Equal load sharing across all cooling units"],
                ["Unit Load Ratio", "<code>Required Cooling Capacity / Installed Cooling Unit Capacity</code>"],
                ...(isAccMode ? [["ACC Power Lookup Basis", "Ambient Dry-Bulb Temperature + Required Cooling Capacity per ACC Unit"]] : []),
                ["N+1 / Staged Dispatch", "Not included"]
            ])}</tbody></table>
        </div>
    ` : ""}
    <h3>Mathematical Framework</h3>
    ${isAccMode ? `<table><tbody>${tableRows([
        ["Annual PUE", "<code>Annual facility energy / Annual IT energy</code>"],
        ["ACC Power", "Dynamic hourly ACC model"],
        ["Electrical Distribution Loss", "<code>Load / path efficiency - load</code>"]
    ])}</tbody></table>` : `${formulasHtml()}
    <table><tbody>${tableRows([
        ["PUE Definition", "<code>PUE = P_facility / P_IT</code>"],
        ["Cooling Power", "<code>P_cooling = P_chiller + P_dry_cooler</code> plus pump/fan terms reported separately where available"],
        ["Chiller COP", "<code>COP = Q_cooling / P_compressor</code>"],
        ["Dry Cooler Approach", "<code>T_LWT = T_ambient + Approach</code> when no explicit leaving-water curve is supplied"],
        ["Not Currently Modeled", "Cooling mode classification and free-cooling hours"]
    ])}</tbody></table>`}
    `}
</section>

<section>
    <h2>5. Input Datasets and Weather Analysis</h2>
    <div class="grid">
        <div class="card"><h3>IT Load Profile</h3><table><tbody>${tableRows([
            ["Source File", esc(standardDataFiles.itLoad?.source_file || "N/A")],
            ["Points", esc(it ? it.length : 0)],
            ["Average", reportValue(itSummary?.avg, " kW", 0)],
            ["Peak", reportValue(itSummary?.max, " kW", 0)],
            ["Minimum", reportValue(itSummary?.min, " kW", 0)]
        ])}</tbody></table></div>
        <div class="card"><h3>Weather Profile</h3><table><tbody>${tableRows([
            ["Source File", esc(weather.source_file || "N/A")],
            ["Source", esc(weather.source_format || "N/A")],
            ["Weather Data Period", esc(weatherPeriod || "N/A")],
            ["Dry Bulb Average", reportValue(drySummary?.avg, " °C", 1)],
            ["Dry Bulb Peak", reportValue(drySummary?.max, " °C", 1)],
            ["Dry Bulb Minimum", reportValue(drySummary?.min, " °C", 1)],
            ["Relative Humidity Average", reportValue(rhSummary?.avg, "%", 0)],
            ["Annual GHI", ghiSummary ? `${reportValue(ghiSummary.sum / 1000, " kWh/m²", 0)}` : "N/A"],
            ["Average Wind Speed", reportValue(windSummary?.avg, " m/s", 1)]
        ])}</tbody></table></div>
    </div>
    <h3>Extended EPW Data Views</h3>
    ${epwChartSection(weatherData)}
</section>

<section>
    <h2>6. Equipment Curve Register</h2>
    ${isAccMode ? `
        <p>${isExcelReplicatedHourlyMode ? "The hourly ACC performance profile is based on the project-specific cooling architecture and annual weather data." : (isAccV2DirectMode ? "ACC Solver_Curve points define direct hourly ACC power from EPW dry-bulb temperature and required cooling capacity per ACC unit." : (isAnnualBenchmarkMode ? "Detailed dynamic equipment-curve plots are not used in the annual-equivalent assessment. ACC power is represented through scenario peak ACC power and the annual weather factor." : "Configuration Library ACC equipment data is used by the dynamic hourly calculation."))}</p>
        <table><tbody>${tableRows([
            ["Configuration Source", "Configuration Library — ACC_1.5MW_GASENGINE_CDU"],
            ["Simulation Method", isAccV2DirectMode ? "True EPW × Solver_Curve" : (isExcelReplicatedHourlyMode ? "Project-specific hourly ACC performance model" : (isAnnualBenchmarkMode ? "Scenario peak ACC power" : "Dynamic ACC calculation"))],
            ["Simulation Basis", isAccV2DirectMode ? "8760-hour Annual Dynamic Simulation" : (isAnnualBenchmarkMode ? "ACC annual weather factor" : "Hourly weather and ACC model")],
            ["ACC Power Basis", isExcelReplicatedHourlyMode ? "Project-specific hourly ACC performance model" : (isAccV2DirectMode ? "Ambient Dry-Bulb Temperature + Required Cooling Capacity per ACC Unit" : (isAnnualBenchmarkMode ? "Scenario peak ACC power" : "Dynamic ACC calculation"))],
            ["Weather Representation", isAnnualBenchmarkMode ? "Annualized weather factor" : "Hourly weather data"]
        ])}</tbody></table>
    ` : `
    <p>All imported equipment parameter curves are represented below in a common technical format. These are the curve inputs available to the frontend and solver workflow at report generation time.</p>
    ${curveRegisterRows.length ? `
        <table>
            <thead><tr><th>Category</th><th>Curve ID</th><th>Source File</th><th>Domain / Range</th><th>Points</th></tr></thead>
            <tbody>${curveRegisterRows.map(row => `<tr>${row.map(cell => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody>
        </table>
        <div class="curveGrid">${curveGroups.map((group, index) => `
            <div class="card">
                <h3>Figure ${index + 1}. ${esc(group.category)} input curves</h3>
                ${svgCurveGroupChart(group)}
                ${equipmentSpecHtml(group.category)}
                <div class="caption">Input equipment curve set from ${esc(group.sourceFile)}. Curves from the same input table are plotted together.</div>
            </div>
        `).join("")}</div>
    ` : `<div class="empty">No equipment curves were imported.</div>`}
    `}
</section>

<section>
    <h2>7. Annual Simulation Results</h2>
    ${isAccMode ? `
    ${isBenchmarkMode ? `<h3>ACC Cooling System Components</h3>
    <table>
        <thead><tr><th>Component</th><th>Average Power (kW)</th><th>Annual Energy (kWh)</th></tr></thead>
        <tbody>${benchmarkComponentRows.map(([label, averageKw, annualKwh]) => `<tr><td>${esc(label)}</td><td>${reportValue(averageKw, "", 3)}</td><td>${reportValue(annualKwh, "", 0)}</td></tr>`).join("")}</tbody>
    </table>` : ""}
    <table><tbody>${tableRows([
        ["Annual PUE", reportValue(annual.annual_average_PUE, "", 9)],
        ["Annual IT Energy", reportValue(annual.annual_IT_energy_kWh, " kWh", 0)],
        ["Annual Facility Energy", reportValue(annual.annual_facility_energy_kWh, " kWh", 0)],
        ["Annual Cooling System Energy", reportValue(annual.annual_total_cooling_system_energy_kWh, " kWh", 0)],
        ["Annual ACC Energy", reportValue(annual.annual_acc_energy_kWh, " kWh", 0)],
        ["Annual Pump Energy", reportValue(annual.annual_pump_energy_kWh, " kWh", 0)],
        ["Annual Indoor Equipment Energy", reportValue(annual.annual_indoor_equipment_energy_kWh || annual.annual_white_space_equipment_energy_kWh, " kWh", 0)],
        ["Annual Engine Radiator Energy", reportValue(annual.annual_engine_radiator_energy_kWh, " kWh", 0)],
        ["Annual IT Electrical Distribution Loss", reportValue(annual.annual_it_electrical_loss_kWh, " kWh", 0)],
        ["Annual MEP Electrical Distribution Loss", reportValue(annual.annual_mep_electrical_loss_kWh, " kWh", 0)],
        ...accPerformanceRows
    ])}</tbody></table>
    ` : `
    <table><tbody>${tableRows([
        ["Annual IT Energy", reportValue(annual.annual_IT_energy_kWh, " kWh", 0)],
        ["Annual Facility Energy", reportValue(annual.annual_facility_energy_kWh, " kWh", 0)],
        ["Annual Cooling System Energy", reportValue(annual.annual_total_cooling_system_energy_kWh || 0, " kWh", 0)],
        ["Annual Chiller + Dry Cooler Energy", reportValue(annual.annual_chiller_plus_dry_cooler_energy_kWh, " kWh", 0)],
        ["Annual Chiller Energy", reportValue(annual.annual_chiller_energy_kWh, " kWh", 0)],
        ["Annual ACC Energy", reportValue(annual.annual_acc_energy_kWh, " kWh", 0)],
        ...accPerformanceRows,
        ["ACC Curve Source", esc(annual.acc_curve_source || "N/A")],
        ["Annual Engine Output", reportValue(annual.annual_engine_output_kWh, " kWh", 0)],
        ["Annual Engine Fuel Input", reportValue(annual.annual_engine_fuel_input_kWh, " kWh", 0)],
        ["Annual Engine Waste Heat", reportValue(annual.annual_engine_waste_heat_kWh, " kWh", 0)],
        ["Average Engine Efficiency", annual.average_engine_efficiency != null ? percentText(annual.average_engine_efficiency) : "N/A"],
        ["Annual Engine Radiator Energy", reportValue(annual.annual_engine_radiator_energy_kWh, " kWh", 0)],
        ["Max Engine Radiator Power", reportValue(annual.max_engine_radiator_power_kW, " kW", 1)],
        ["Radiator Curve Source", esc(annual.engine_radiator_curve_source || "N/A")],
        ["Annual Dry Cooler Energy", reportValue(annual.annual_dry_cooler_energy_kWh, " kWh", 0)],
        ["Annual Pump Energy", reportValue(annual.annual_pump_energy_kWh, " kWh", 0)],
        ["Annual MAU Energy", reportValue(annual.annual_terminal_fan_energy_kWh, " kWh", 0)],
        ["Annual CDU Energy", reportValue(annual.annual_cdu_energy_kWh, " kWh", 0)],
        ["Annual RTC Energy", reportValue(annual.annual_rtc_energy_kWh, " kWh", 0)],
        ["Annual MAU Energy", reportValue(annual.annual_mau_energy_kWh, " kWh", 0)],
        ["Annual White Space Equipment Energy", reportValue(annual.annual_white_space_equipment_energy_kWh, " kWh", 0)],
        ["Annual Electrical Distribution Loss", reportValue(annual.annual_electrical_loss_kWh, " kWh", 0)],
        ["Annual Other Electrical Auxiliary Energy", reportValue(annual.annual_auxiliary_energy_kWh, " kWh", 0)]
    ])}</tbody></table>
    `}
    <div class="grid">
        <div class="card">
            <h3>PUE Contribution Breakdown</h3>
            <table class="breakdown">
                <thead><tr><th>Component</th><th>pPUE Contribution</th></tr></thead>
                <tbody>${pueContributionRows.map(row => `
                    <tr class="${esc(row.css || "")}">
                        <td>${esc(row.label)}</td>
                        <td>${pueContributionText(row.value, row.signed)}</td>
                    </tr>
                `).join("")}</tbody>
            </table>
        </div>
        <div class="card">
            <h3>Key Findings</h3>
            ${isBenchmarkMode ? `
                <p>${isExcelReplicatedHourlyMode ? "ACC power is calculated hour by hour using the project-specific ACC performance model; supporting equipment follows the selected scenario power basis." : "ACC, CHW pump, CDU / RTC / MAU equipment, and engine radiator energy are calculated from scenario peak values and annual factors."}</p>
                <p>Electrical losses use the project IT and MEP path efficiencies.</p>
            ` : `
                <p>Cooling System contributes <b>${esc(percentText(contributionSummary.coolingShare))}</b> of the non-IT PUE overhead${contributionSummary.largestDriver && contributionSummary.largestDriver.key === "cooling" ? " and is the largest driver of annual PUE" : ""}.</p>
                <p>Electrical losses contribute <b>${esc(percentText(contributionSummary.electricalShare))}</b> of the non-IT PUE overhead.</p>
                <p>Other electrical auxiliary loads contribute <b>${esc(percentText(contributionSummary.auxiliaryShare))}</b> of the non-IT PUE overhead.</p>
            `}
            <table><tbody>${tableRows([
                ["Non-IT PUE Overhead", contributionSummary.nonItPue > 0 ? reportValue(contributionSummary.nonItPue, "", 3) : "N/A"],
                ["Largest PUE Driver", esc(contributionSummary.largestDriver ? contributionSummary.largestDriver.label : "N/A")]
            ])}</tbody></table>
        </div>
        <div class="card">
            <h3>Breakdown Basis</h3>
            <table><tbody>${tableRows(isBenchmarkMode ? [
                ["Base IT PUE", "1.000"],
                ["ACC pPUE", "<code>annual_acc_energy_kWh / annual_IT_energy_kWh</code>"],
                ["Pump pPUE", "<code>annual_pump_energy_kWh / annual_IT_energy_kWh</code>"],
                ["Indoor Equipment pPUE", "<code>annual_indoor_equipment_energy_kWh / annual_IT_energy_kWh</code>"],
                ["Engine Radiator pPUE", "<code>annual_engine_radiator_energy_kWh / annual_IT_energy_kWh</code>"],
                ["Electrical Distribution Loss pPUE", "<code>annual_electrical_loss_kWh / annual_IT_energy_kWh</code>"],
                ["Reported Annual PUE", reportValue(annual.annual_average_PUE, "", 3)]
            ] : [
                ["Base IT PUE", "1.000"],
                ["Cooling System pPUE", "<code>annual_total_cooling_system_energy_kWh / annual_IT_energy_kWh</code>"],
                ["Cooling System Includes", "ACC + CHW Pump + Indoor Equipment + Engine Radiator"],
                ["Electrical Distribution Loss pPUE", "<code>annual_electrical_loss_kWh / annual_IT_energy_kWh</code>"],
                ["Other Electrical Auxiliary pPUE", "<code>annual_auxiliary_energy_kWh / annual_IT_energy_kWh</code>"],
                ["Reported Annual PUE", reportValue(annual.annual_average_PUE, "", 3)]
            ])}</tbody></table>
            <div class="note">This section summarizes annual result components without overwriting <code>annual_average_PUE</code>.</div>
        </div>
    </div>
    ${resultChartCards.length ? `<div class="grid">${resultChartCards.map(([title, chart]) => `
        <div class="card"><h3>${esc(title)}</h3>${chart}</div>
    `).join("")}</div>` : ""}
</section>

<section>
    <h2>8. Engineering Discussion</h2>
    <p>${isBenchmarkMode
        ? (isExcelReplicatedHourlyMode
            ? `The computed annual average PUE is <b>${reportValue(annual.annual_average_PUE, "", 3)}</b> using the project-specific hourly ACC performance model. Hourly component powers and PUE are derived from the selected scenario equipment powers and electrical-loss methodology.`
            : (isExperimentalHourlyMode
            ? `The computed annual average PUE is <b>${reportValue(annual.annual_average_PUE, "", 3)}</b> and is based on direct hourly ACC Solver_Curve lookup using EPW dry-bulb temperature and hourly load ratio. ACC annual energy is calculated as the sum of hourly ACC power with no external annual adjustment.`
            : (isConfigurationLibraryAccV2DirectMode
            ? `The computed annual average PUE is <b>${reportValue(annual.annual_average_PUE, "", 3)}</b> and is based on True EPW × Solver_Curve ACC calculation with an 8760-hour Annual Dynamic Simulation basis.`
            : `The computed annual average PUE is <b>${reportValue(annual.annual_average_PUE, "", 3)}</b> and is based on the annual-equivalent assessment method. ACC power is calculated from scenario peak ACC power multiplied by the annual weather factor. CHW pump, CDU / RTC / MAU equipment, and engine radiator powers are calculated using the same annual-load-factor method. Electrical distribution losses are calculated from the project IT and MEP efficiency assumptions.`)))
        : (isConfigurationLibraryAccV2DirectMode
        ? `The computed annual average PUE is <b>${reportValue(annual.annual_average_PUE, "", 3)}</b> and is based on True EPW × Solver_Curve ACC calculation with an 8760-hour Annual Dynamic Simulation basis.`
        : `The computed annual average PUE is <b>${reportValue(annual.annual_average_PUE, "", 3)}</b>. Cooling performance should be interpreted against outdoor dry bulb conditions and the supplied COP/dry-cooler curves. Free-cooling and hybrid-cooling hour counts are not reported as calculated KPIs because the current solver does not explicitly classify operating modes.`)}</p>
    <h3>Cooling Load Components</h3>
    <table><tbody>${tableRows([
        ["Annual IT Load", reportValue(annual.annual_IT_energy_kWh, " kWh", 0)],
        ["Annual Solar Heat Gain", reportValue(annual.annual_solar_heat_gain_kWh, " kWh", 0)],
        ["Annual Other Auxiliary Heat Gains", reportValue(annual.annual_other_auxiliary_heat_gain_kWh, " kWh", 0)],
        ["Annual Cooling Load", reportValue(annual.annual_cooling_load_kWh, " kWh", 0)]
    ])}</tbody></table>
    <h3>Input Assumptions</h3>
    <table><tbody>${tableRows([
        ["Solar Heat Gain Max", reportValue(heatGains.solarHeatGainMaxKw, " kW", 1)],
        ["Other Auxiliary Heat Gains", reportValue(heatGains.otherAuxiliaryHeatGainKw, " kW", 1)]
    ])}</tbody></table>
    <table><tbody>${tableRows(isBenchmarkMode ? [
        ["Hourly Dispatch Classification", isExcelReplicatedHourlyMode ? "Hourly weather-driven simulation with derived component powers" : (isExperimentalHourlyMode ? "Configuration Library Solver_Curve direct hourly simulation" : "Not applicable in annual-equivalent assessment")]
    ] : [
        ["Free Cooling Hours", "Not modeled in current solver"],
        ["Mechanical Cooling Hours", "Not modeled in current solver"]
    ])}</tbody></table>
</section>

<section>
    <h2>9. Conclusion</h2>
    <p>This report provides a transparent annual PUE assessment based on the currently loaded input datasets and solver outputs. The ACC model directly evaluates hourly equipment performance from manufacturer Solver_Curve data. Values that are not produced by the solver are explicitly marked as contextual or not modeled.</p>
</section>
</main>
</body>
</html>`;
}

function exportHtmlReport() {
    if (!lastReportContext || !lastReportContext.output) {
        setSolverDataStatus("请先运行一次计算，再导出 HTML 报告。", "error");
        return;
    }
    let html = buildHtmlReport(lastReportContext);
    const finalLogoMarkup = `<div class="reportLogoBlock" style="display:block;width:210px;height:auto;margin:0 0 14px 0;">
  <img
    class="reportLogo"
    src="${SKYVAULT_REPORT_LOGO}"
    alt="SkyVault"
    style="display:block !important;width:210px !important;height:auto !important;max-width:210px !important;visibility:visible !important;opacity:1 !important;"
  />
</div>`;
    html = html.replace(/<div\s+class="reportLogoBlock"[\s\S]*?<\/div>\s*/g, "");
    html = html.replace(/<img\s+class="reportLogo"[^>]*>\s*/g, "");
    const headerTopOpen = '<div class="reportHeaderTop">';
    if (html.includes(headerTopOpen)) {
        html = html.replace(headerTopOpen, `${headerTopOpen}
        ${finalLogoMarkup}`);
    }
    const projectName = getProjectReportInfo().name || "pue-report";
    const safeName = projectName.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "pue-report";
    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${safeName}.html`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setSolverDataStatus("HTML 报告已生成。", "ok");
}

function timestampForFileName(date = new Date()) {
    const pad = (value) => String(value).padStart(2, "0");
    return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}_${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
}

function exportOutputJson() {
    if (!lastReportContext || !lastReportContext.output) {
        setSolverDataStatus("请先运行一次计算，再导出 JSON。", "error");
        return;
    }
    const filename = `pue_results_${timestampForFileName()}.json`;
    const json = JSON.stringify(lastReportContext.output, null, 2);
    const blob = new Blob([json], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setSolverDataStatus(`JSON 已导出：${filename}`, "ok");
}

function setSolverDataStatus(text, tone = "info") {
    if (!elSolverDataStatus) return;
    const color = tone === "error" ? "#dc2626" : tone === "ok" ? "#059669" : "#6b7280";
    elSolverDataStatus.style.color = color;
    elSolverDataStatus.textContent = text;
}

function pickHourlyValue(row, keys) {
    for (const key of keys) {
        if (row && row[key] !== undefined && row[key] !== null) return Number(row[key]);
    }
    return null;
}

function decimateHourlyRows(rows, maxPoints = 876) {
    if (!Array.isArray(rows) || rows.length <= maxPoints) return rows || [];
    const step = Math.ceil(rows.length / maxPoints);
    return rows.filter((_, index) => index % step === 0 || index === rows.length - 1);
}

function getPath(obj, path) {
    let cur = obj;
    for (const key of path) {
        if (!cur || typeof cur !== "object" || !(key in cur)) return undefined;
        cur = cur[key];
    }
    return cur;
}

function numericArray(value) {
    if (!Array.isArray(value)) return null;
    const out = value.map(Number).filter(v => Number.isFinite(v));
    return out.length > 1 ? out : null;
}

function numericArrayAny(value) {
    if (!Array.isArray(value)) return null;
    const out = value.map(Number).filter(v => Number.isFinite(v));
    return out.length > 0 ? out : null;
}

function columnFromRows(rows, key) {
    if (!Array.isArray(rows)) return null;
    const out = rows.map(row => row && Number(row[key])).filter(v => Number.isFinite(v));
    return out.length > 1 ? out : null;
}

function firstNumericArray(obj, paths) {
    for (const path of paths) {
        const arr = numericArray(getPath(obj, path));
        if (arr) return arr;
    }
    return null;
}

function firstNumericArrayAny(obj, paths) {
    for (const path of paths) {
        const arr = numericArrayAny(getPath(obj, path));
        if (arr) return arr;
    }
    return null;
}

function projectDesignCapacityKw() {
    const info = getProjectReportInfo();
    return info.capacityMw !== null ? Number(info.capacityMw) * 1000 : null;
}

function percentLoadToFraction(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return null;
    return n > 1 ? n / 100 : n;
}

function percentArrayToKw(values, designCapacityKw) {
    if (!Array.isArray(values) || !(designCapacityKw > 0)) return null;
    const converted = values
        .map(value => {
            const fraction = percentLoadToFraction(value);
            return fraction === null ? null : fraction * designCapacityKw;
        })
        .filter(value => Number.isFinite(value));
    return converted.length > 0 ? converted : null;
}

function findItLoadPercentArray(obj) {
    return firstNumericArrayAny(obj, [
        ["data", "hourly_it_load_percent"],
        ["data", "hourly_it_load_pct"],
        ["data", "hourly_it_load_%"],
        ["hourly_it_load_percent"],
        ["hourly_it_load_pct"],
        ["hourly_it_load_%"],
        ["project", "it_load", "hourly_it_load_percent"],
        ["project", "it_load", "hourly_it_load_pct"],
        ["project", "it_load", "hourly_it_load_%"],
        ["it_load", "hourly_it_load_percent"],
        ["it_load", "hourly_it_load_pct"],
        ["it_load", "hourly_it_load_%"]
    ]);
}

function normalizeItLoadPercentFile(itLoadObj) {
    if (!itLoadObj || typeof itLoadObj !== "object") return itLoadObj;
    const existingKw = firstNumericArray(itLoadObj, [
        ["data", "hourly_it_load_kW"],
        ["hourly_it_load_kW"],
        ["project", "it_load", "hourly_it_load_kW"]
    ]);
    if (existingKw) return itLoadObj;
    const percent = findItLoadPercentArray(itLoadObj);
    if (!percent) return itLoadObj;
    const designCapacityKw = projectDesignCapacityKw();
    if (!(designCapacityKw > 0)) {
        throw new Error("IT load file uses hourly_it_load_%. Please enter IT Design Capacity (MW) before importing it.");
    }
    const converted = percentArrayToKw(percent, designCapacityKw);
    if (!converted) throw new Error("Could not convert hourly_it_load_% to hourly_it_load_kW.");
    itLoadObj.data = itLoadObj.data && typeof itLoadObj.data === "object" ? itLoadObj.data : {};
    itLoadObj.data.hourly_it_load_percent = percent;
    itLoadObj.data.hourly_it_load_kW = converted;
    itLoadObj.units = itLoadObj.units && typeof itLoadObj.units === "object" ? itLoadObj.units : {};
    itLoadObj.units.hourly_it_load_percent = "%";
    itLoadObj.units.hourly_it_load_kW = "kW";
    itLoadObj.design_it_capacity_kW = designCapacityKw;
    itLoadObj.design_it_capacity_MW = designCapacityKw / 1000;
    itLoadObj.conversion = {
        source: "hourly_it_load_percent",
        formula: "IT_load_kW = percent * IT Design Capacity (MW) * 1000",
        percent_rule: "values > 1 are divided by 100; values <= 1 are treated as fractions"
    };
    return itLoadObj;
}

function sumModuleItLoadArrays(modules) {
    if (!Array.isArray(modules)) return null;
    const arrays = modules
        .map(module => numericArray(module && module.it_load_kw))
        .filter(Boolean);
    if (arrays.length === 0) return null;
    const n = Math.max(...arrays.map(arr => arr.length));
    if (n <= 1) return null;
    return Array.from({ length: n }, (_, i) =>
        arrays.reduce((sum, arr) => sum + (Number(arr[i]) || 0), 0)
    );
}

function scalarNumberFromPaths(obj, paths) {
    for (const path of paths) {
        const value = getPath(obj, path);
        if (Array.isArray(value)) continue;
        const num = Number(value);
        if (Number.isFinite(num)) return num;
    }
    return null;
}

function designCapacityKwFromInput(inputObj) {
    const directKw = scalarNumberFromPaths(inputObj, [
        ["project", "it_load", "design_it_load_kW"],
        ["project", "design_it_load_kW"],
        ["it_load", "design_it_load_kW"],
        ["design_it_load_kW"]
    ]);
    if (directKw !== null) return directKw;
    const mw = scalarNumberFromPaths(inputObj, [
        ["project", "capacity_mw"],
        ["project", "capacityMw"],
        ["project", "it_design_capacity_MW"],
        ["project", "it_design_capacity_mw"],
        ["it_design_capacity_MW"],
        ["it_design_capacity_mw"]
    ]);
    return mw !== null ? mw * 1000 : null;
}

function scalarModuleItLoad(modules) {
    if (!Array.isArray(modules)) return null;
    const total = modules.reduce((sum, module) => {
        const value = module && module.it_load_kw;
        if (Array.isArray(value)) return sum;
        const num = Number(value);
        return Number.isFinite(num) ? sum + num : sum;
    }, 0);
    return total > 0 ? total : null;
}

function normalizeAnnualProjectInput(inputObj) {
    const normalized = JSON.parse(JSON.stringify(inputObj));

    const project = normalized.project && typeof normalized.project === "object"
        ? normalized.project
        : {};
    const weather = normalized.weather && typeof normalized.weather === "object"
        ? normalized.weather
        : {};

    let hourlyIt = firstNumericArray(normalized, [
        ["project", "it_load", "hourly_it_load_kW"],
        ["project", "it_load", "hourly_it_load_kw"],
        ["project", "it_load", "hourly_IT_load_kW"],
        ["it_load", "hourly_it_load_kW"],
        ["it_load", "hourly_it_load_kw"],
        ["hourly_it_load_kW"],
        ["hourly_it_load_kw"],
        ["hourly_IT_load_kW"],
        ["power", "hourly_it_power_kw"],
        ["power", "total_it_power_kw"]
    ]);

    if (!hourlyIt) {
        const percentIt = findItLoadPercentArray(normalized);
        if (percentIt) {
            const designCapacityKw = designCapacityKwFromInput(normalized);
            hourlyIt = percentArrayToKw(percentIt, designCapacityKw);
            if (hourlyIt) {
                project.it_load = project.it_load && typeof project.it_load === "object" ? project.it_load : {};
                project.it_load.design_it_load_kW = project.it_load.design_it_load_kW || designCapacityKw;
                project.it_load.hourly_it_load_percent = percentIt;
            }
        }
    }

    if (!hourlyIt) {
        hourlyIt =
            columnFromRows(getPath(normalized, ["hourly_profile"]), "IT_load_kW") ||
            columnFromRows(getPath(normalized, ["project", "it_load", "hourly_profile"]), "IT_load_kW") ||
            columnFromRows(getPath(normalized, ["it_load", "hourly_profile"]), "IT_load_kW") ||
            sumModuleItLoadArrays(normalized.modules);
    }

    let dryBulb = firstNumericArray(normalized, [
        ["weather", "hourly_data", "dry_bulb_C"],
        ["weather", "hourly_data", "outdoor_temp_c"],
        ["weather", "dry_bulb_C"],
        ["hourly_data", "dry_bulb_C"],
        ["hourly_data", "outdoor_temp_c"],
        ["environmental_conditions", "outdoor_temp_c"],
        ["environmental_conditions", "outdoor_temp_C"],
        ["dry_bulb_C"],
        ["outdoor_temp_c"]
    ]);

    if (!dryBulb) {
        dryBulb =
            columnFromRows(getPath(normalized, ["weather", "hourly_profile"]), "dry_bulb_C") ||
            columnFromRows(getPath(normalized, ["hourly_profile"]), "dry_bulb_C");
    }

    if (!hourlyIt && dryBulb) {
        const scalarIt =
            scalarNumberFromPaths(normalized, [
                ["project", "design_it_load_kW"],
                ["power", "total_it_power_kw"],
                ["total_it_power_kw"]
            ]) ||
            scalarModuleItLoad(normalized.modules);
        if (scalarIt) hourlyIt = Array.from({ length: dryBulb.length }, () => scalarIt);
    }

    if (hourlyIt && !dryBulb) {
        const scalarDryBulb = scalarNumberFromPaths(normalized, [
            ["environmental_conditions", "outdoor_temp_c"],
            ["environmental_conditions", "outdoor_temp_C"],
            ["project", "location", "design_dry_bulb_C"],
            ["cooling", "oat_c"],
            ["outdoor_temp_c"],
            ["dry_bulb_C"]
        ]);
        if (scalarDryBulb !== null) dryBulb = Array.from({ length: hourlyIt.length }, () => scalarDryBulb);
    }

    const wetBulb = firstNumericArray(normalized, [
        ["weather", "hourly_data", "wet_bulb_C"],
        ["hourly_data", "wet_bulb_C"],
        ["environmental_conditions", "wet_bulb_c"],
        ["wet_bulb_C"]
    ]);

    const rh = firstNumericArray(normalized, [
        ["weather", "hourly_data", "relative_humidity_percent"],
        ["hourly_data", "relative_humidity_percent"],
        ["relative_humidity_percent"]
    ]);

    const hourIndex = firstNumericArray(normalized, [
        ["weather", "hourly_data", "hour_index"],
        ["hourly_data", "hour_index"],
        ["hour_index"]
    ]);

    const hasAnnualInputs = Boolean(hourlyIt && dryBulb);
    if (!hasAnnualInputs) {
        return { input: normalized, isProject: false, hourlyItCount: hourlyIt ? hourlyIt.length : 0, weatherCount: dryBulb ? dryBulb.length : 0 };
    }

    project.calculation_mode = project.calculation_mode || "project_8760";
    project.project_mode = true;
    project.it_load = project.it_load && typeof project.it_load === "object" ? project.it_load : {};
    project.it_load.hourly_it_load_kW = hourlyIt;

    weather.hourly_data = weather.hourly_data && typeof weather.hourly_data === "object" ? weather.hourly_data : {};
    weather.hourly_data.dry_bulb_C = dryBulb;
    if (wetBulb) weather.hourly_data.wet_bulb_C = wetBulb;
    if (rh) weather.hourly_data.relative_humidity_percent = rh;
    weather.hourly_data.hour_index = hourIndex && hourIndex.length === dryBulb.length
        ? hourIndex
        : Array.from({ length: Math.min(hourlyIt.length, dryBulb.length) }, (_, i) => i + 1);

    normalized.project = project;
    normalized.weather = weather;

    return { input: normalized, isProject: true, hourlyItCount: hourlyIt.length, weatherCount: dryBulb.length };
}

function hasProjectIntent(inputObj) {
    const project = inputObj && inputObj.project;
    if (!project || typeof project !== "object") return false;
    return (
        project.project_mode === true ||
        project.calculation_mode === "project_8760" ||
        project.it_load !== undefined ||
        inputObj.weather !== undefined
    );
}

function isPrecomputedProjectResult(inputObj) {
    return Boolean(
        inputObj &&
        Array.isArray(inputObj.hourly_results) &&
        inputObj.hourly_results.length > 1 &&
        inputObj.annual_results &&
        inputObj.peak_results
    );
}

function solverProjectArraysReady(inputObj) {
    const hourlyIt = getPath(inputObj, ["project", "it_load", "hourly_it_load_kW"]);
    const dryBulb = getPath(inputObj, ["weather", "hourly_data", "dry_bulb_C"]);
    return Array.isArray(hourlyIt) && hourlyIt.length > 1 && Array.isArray(dryBulb) && dryBulb.length > 1;
}

function prepareSolverJob(rawInput, curveLib) {
    if (!rawInput || typeof rawInput !== "object" || Array.isArray(rawInput)) {
        return {
            kind: "invalid",
            error: "Input JSON must be an object."
        };
    }

    if (isPrecomputedProjectResult(rawInput)) {
        return {
            kind: "precomputed_project",
            solverFn: "none",
            input: rawInput,
            output: rawInput,
            diagnostics: {
                hourlyRows: rawInput.hourly_results.length,
                message: "Detected solver output: hourly_results + annual_results + peak_results"
            }
        };
    }

    const withCurves = JSON.parse(JSON.stringify(rawInput));
    if (!withCurves.curve_library && !withCurves.curveLib && !withCurves.equipment_curves) {
        withCurves.curve_library = curveLib || { curves_1d: {}, cop_surfaces: {} };
    }

    const normalizedProject = normalizeAnnualProjectInput(withCurves);
    const normalizedInput = normalizedProject.input;
    const projectReady = solverProjectArraysReady(normalizedInput);
    const projectIntent =
        hasProjectIntent(rawInput) ||
        normalizedProject.isProject ||
        normalizedProject.hourlyItCount > 1 ||
        normalizedProject.weatherCount > 1;

    if (projectReady) {
        const hourlyIt = getPath(normalizedInput, ["project", "it_load", "hourly_it_load_kW"]);
        const dryBulb = getPath(normalizedInput, ["weather", "hourly_data", "dry_bulb_C"]);
        const n = Math.min(hourlyIt.length, dryBulb.length);
        return {
            kind: "project",
            solverFn: "compute_pue_project",
            input: normalizedInput,
            diagnostics: {
                itHours: hourlyIt.length,
                weatherHours: dryBulb.length,
                effectiveHours: n,
                exactSolverPaths: [
                    "project.it_load.hourly_it_load_kW",
                    "weather.hourly_data.dry_bulb_C"
                ],
                warning: hourlyIt.length === dryBulb.length
                    ? ""
                    : "IT and weather arrays have different lengths; solver will fill missing side with defaults."
            }
        };
    }

    if (projectIntent) {
        return {
            kind: "invalid_project",
            solverFn: "compute_pue_project",
            input: normalizedInput,
            error:
                "Project/annual input was detected, but the frontend could not build the exact solver arrays. " +
                "Required by solver.py: project.it_load.hourly_it_load_kW and weather.hourly_data.dry_bulb_C.",
            diagnostics: {
                itHours: normalizedProject.hourlyItCount,
                weatherHours: normalizedProject.weatherCount
            }
        };
    }

    return {
        kind: "single",
        solverFn: "compute_pue_v04",
        input: withCurves,
        diagnostics: {
            message: "No project annual arrays detected; using single-point solver schema."
        }
    };
}

function chartUnavailableMessage() {
    return "Chart.js is not loaded. Please check the CDN script in index.html.";
}

function hideProjectVisualization() {
    destroyResultCharts();
    const vis = document.getElementById("resultsVisualization");
    const msg = document.getElementById("noResultsMessage");
    if (vis) vis.style.display = "none";
    if (msg) msg.style.display = "block";
}

function createChart(canvasId, config) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || typeof Chart === "undefined") return null;
    if (resultCharts[canvasId]) resultCharts[canvasId].destroy();
    canvas.removeAttribute("height");
    canvas.removeAttribute("width");
    canvas.style.height = "280px";
    canvas.style.maxHeight = "280px";
    canvas.style.width = "100%";
    resultCharts[canvasId] = new Chart(canvas, config);
    return resultCharts[canvasId];
}

function updateFileStatus(id, text, tone = "info") {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.color = tone === "ok" ? "#059669" : tone === "error" ? "#dc2626" : "#6b7280";
    el.textContent = text;
}

function optionalCoordinateNumber(id, min, max) {
    const el = document.getElementById(id);
    if (!el || el.value === "") return null;
    const value = Number(el.value);
    return Number.isFinite(value) && value >= min && value <= max ? value : null;
}

function normalizeLocationText(value) {
    return String(value || "")
        .toLowerCase()
        .normalize("NFKD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/[,，]/g, "")
        .replace(/[\s._\-()/\\]+/g, "")
        .replace(/[^a-z0-9\u4e00-\u9fff]+/g, "")
        .trim();
}

async function loadLocalEpwIndex() {
    const response = await fetch("./data/epw_index.json", { cache: "no-cache" });
    if (!response.ok) {
        throw new Error(`EPW index HTTP ${response.status}`);
    }
    const index = await response.json();
    return Array.isArray(index) ? index : [];
}

function findLocalEpwMatch(locationText, epwIndex) {
    const query = normalizeLocationText(locationText);
    if (!query) return null;
    let best = null;
    let bestScore = 0;
    epwIndex.forEach((item) => {
        if (!item || typeof item !== "object") return;
        const terms = [item.city, item.country, item.station].concat(Array.isArray(item.aliases) ? item.aliases : []);
        terms.forEach((term) => {
            const normalizedTerm = normalizeLocationText(term);
            if (!normalizedTerm) return;
            let score = 0;
            if (query === normalizedTerm) score = 100;
            else if (query.includes(normalizedTerm)) score = 80;
            else if (normalizedTerm.includes(query)) score = 70;
            if (score > bestScore) {
                bestScore = score;
                best = item;
            }
        });
    });
    return best;
}

const MAX_EPW_MATCH_DISTANCE_KM = 500;

function haversineDistanceKm(lat1, lon1, lat2, lon2) {
    const radius = 6371.0088;
    const toRad = (value) => value * Math.PI / 180;
    const phi1 = toRad(lat1);
    const phi2 = toRad(lat2);
    const dPhi = toRad(lat2 - lat1);
    const dLambda = toRad(lon2 - lon1);
    const a = Math.sin(dPhi / 2) ** 2 +
        Math.cos(phi1) * Math.cos(phi2) * Math.sin(dLambda / 2) ** 2;
    return 2 * radius * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function readProjectCoordinates() {
    const latRaw = document.getElementById("projectLatitudeInput")?.value ?? "";
    const lonRaw = document.getElementById("projectLongitudeInput")?.value ?? "";
    const latitude = Number(latRaw);
    const longitude = Number(lonRaw);
    if (latRaw === "" || lonRaw === "" ||
        !Number.isFinite(latitude) || !Number.isFinite(longitude) ||
        latitude < -90 || latitude > 90 ||
        longitude < -180 || longitude > 180) {
        return null;
    }
    return { latitude, longitude };
}

function findNearestLocalEpwByCoordinates(latitude, longitude, epwIndex) {
    let best = null;
    let bestDistance = Infinity;
    epwIndex.forEach((item) => {
        if (!item || typeof item !== "object") return;
        const itemLat = Number(item.lat);
        const itemLon = Number(item.lon);
        if (!Number.isFinite(itemLat) || !Number.isFinite(itemLon)) return;
        const distance = haversineDistanceKm(latitude, longitude, itemLat, itemLon);
        if (distance < bestDistance) {
            bestDistance = distance;
            best = { ...item, distance_km: Number(distance.toFixed(1)) };
        }
    });
    return best && bestDistance <= MAX_EPW_MATCH_DISTANCE_KM ? best : null;
}

function setAutoEpwStatus(text, tone = "info") {
    const el = document.getElementById("autoEpwStatus");
    if (!el) return;
    if (!text) {
        el.textContent = "";
        el.style.display = "none";
        return;
    }
    el.style.display = "block";
    el.style.color = tone === "ok" ? "#059669" : tone === "error" ? "#dc2626" : "#6b7280";
    el.textContent = text;
}

function getWeatherHours(weatherObj) {
    const data = weatherObj && (weatherObj.data || weatherObj.hourly_data);
    return Array.isArray(data && data.dry_bulb_C) ? data.dry_bulb_C.length : 0;
}

function setWeatherSourceMetadata(weatherObj, metadata) {
    if (!weatherObj || typeof weatherObj !== "object") return;
    weatherObj.metadata = weatherObj.metadata && typeof weatherObj.metadata === "object"
        ? weatherObj.metadata
        : {};
    const sourceMeta = { ...(metadata || {}) };
    sourceMeta.weather_period = sourceMeta.weather_period || extractEpwPeriodFromFileName(sourceMeta.epw_file || weatherObj.source_file || "");
    weatherObj.metadata.weather_source = sourceMeta;
}

function getWeatherSourceMetadata(weatherObj) {
    if (!weatherObj || typeof weatherObj !== "object") return {};
    const metadata = weatherObj.metadata && typeof weatherObj.metadata === "object"
        ? weatherObj.metadata.weather_source
        : null;
    if (metadata && typeof metadata === "object") return metadata;
    return {
        source: weatherObj.source_format || "N/A",
        station: weatherObj.location && weatherObj.location.city ? weatherObj.location.city : "N/A",
        matched_station: weatherObj.location && weatherObj.location.city ? weatherObj.location.city : "N/A",
        epw_file: weatherObj.source_file || "N/A",
        location: [weatherObj.location?.city, weatherObj.location?.country].filter(Boolean).join(", "),
        project_location: "",
        project_latitude: null,
        project_longitude: null,
        distance_km: null,
        weather_period: getWeatherPeriod(weatherObj),
        weather_hours: getWeatherHours(weatherObj) || null
    };
}

async function fetchOnlineEpw(latitude, longitude, locationText) {
    const response = await fetch("http://127.0.0.1:8011/api/fetch_epw", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ latitude, longitude, location: locationText })
    });
    const text = await response.text();
    let payload = {};
    try {
        payload = text ? JSON.parse(text) : {};
    } catch (e) {
        throw new Error("Invalid EPW API response.");
    }
    if (!response.ok && !payload.message) {
        throw new Error(`EPW API HTTP ${response.status}`);
    }
    return payload;
}

async function applyMatchedEpw(match, locationText, coordinates = null, statusText = "", autoStatusText = "") {
    const epwUrl = new URL(match.epw_path, window.location.href).href;
    const response = await fetch(epwUrl, { cache: "no-cache" });
    if (!response.ok) {
        throw new Error(`Local EPW fetch failed (${response.status}).`);
    }
    const epwText = await response.text();
    const json = window.PueImportAdapter && window.PueImportAdapter.adaptEpw
        ? window.PueImportAdapter.adaptEpw(epwText)
        : null;
    if (!json) {
        throw new Error("Local EPW parse failed.");
    }
    json.source_file = match.epw_path.split("/").pop() || match.epw_path;
    json.local_epw_match = {
        city: match.city || "",
        country: match.country || "",
        source: match.source || "Local EPW",
        station: match.station || "",
        lat: match.lat,
        lon: match.lon,
        epw_path: match.epw_path,
        matched_at: new Date().toISOString()
    };
    setWeatherSourceMetadata(json, {
        source: match.source || "Local EPW",
        station: match.station || "",
        matched_station: match.station || "",
        epw_file: json.source_file,
        location: locationText || match.city || "",
        project_location: locationText || "",
        project_latitude: coordinates ? coordinates.latitude : null,
        project_longitude: coordinates ? coordinates.longitude : null,
        distance_km: Number.isFinite(Number(match.distance_km)) ? Number(match.distance_km) : null,
        weather_hours: getWeatherHours(json)
    });
    standardDataFiles.weather = json;
    const weatherHours = getWeatherHours(json);
    standardSolverInput = null;
    preferStandardFiles = true;
    updateFileStatus("statusWeather", statusText || `Climate matched: ${match.station || match.city} / ${match.source || "Local EPW"}`, "ok");
    if (weatherHours !== 8760 && weatherHours !== 8784) {
        setAutoEpwStatus(`EPW loaded, but weather hours are unusual: ${weatherHours}`, "error");
    } else if (autoStatusText) {
        setAutoEpwStatus(autoStatusText, "ok");
    } else {
        setAutoEpwStatus("", "ok");
    }
    previewInputCurves(standardDataFiles);
    renderWeatherReportPanel();
    renderTemperatureDistributionPanel();
    refreshStandardInputStatus();
    return json;
}

async function autoMatchLocalEpw() {
    const locationInput = document.getElementById("projectLocationInput");
    const locationText = locationInput ? locationInput.value.trim() : "";
    const coordinates = readProjectCoordinates();
    const resetWeatherStatusAfterMiss = () => {
        updateFileStatus("statusWeather", standardDataFiles.weather ? "已有天气数据未改变" : "未加载", "info");
    };
    updateFileStatus("statusWeather", "Matching local EPW...", "info");
    setAutoEpwStatus("", "info");
    if (!coordinates) {
        resetWeatherStatusAfterMiss();
        setAutoEpwStatus("Please enter valid Latitude and Longitude for EPW matching.", "error");
        return;
    }
    try {
        let epwIndex = await loadLocalEpwIndex();
        let match = findNearestLocalEpwByCoordinates(coordinates.latitude, coordinates.longitude, epwIndex);
        if (match && match.epw_path) {
            await applyMatchedEpw(match, locationText, coordinates);
            return;
        }

        setAutoEpwStatus("No local EPW matched. Searching online EPW...", "info");
        const onlineResult = await fetchOnlineEpw(coordinates.latitude, coordinates.longitude, locationText);
        if (!onlineResult || !onlineResult.success) {
            resetWeatherStatusAfterMiss();
            setAutoEpwStatus("No suitable online EPW found. Please upload EPW manually.", "error");
            return;
        }

        epwIndex = await loadLocalEpwIndex();
        match = findNearestLocalEpwByCoordinates(coordinates.latitude, coordinates.longitude, epwIndex);
        if (!match || !match.epw_path) {
            resetWeatherStatusAfterMiss();
            setAutoEpwStatus("Online EPW downloaded, but local index did not match. Please upload EPW manually.", "error");
            return;
        }
        const station = onlineResult.matched_station || match.station || match.city;
        const distance = Number.isFinite(Number(onlineResult.distance_km))
            ? `${Number(onlineResult.distance_km).toFixed(1)} km`
            : "distance N/A";
        await applyMatchedEpw(
            match,
            locationText,
            coordinates,
            `Climate matched: ${match.station || match.city} / ${match.source || "Local EPW"}`,
            `Online EPW downloaded: ${station} / ${distance}`
        );
    } catch (e) {
        resetWeatherStatusAfterMiss();
        setAutoEpwStatus("Local EPW not found. Start EPW API server or upload EPW manually.", "error");
    }
}

async function readJsonFile(file) {
    const text = await file.text();
    return JSON.parse(text);
}

function makeHours(n = 8760) {
    return Array.from({ length: n }, (_, i) => i + 1);
}

function standardDataArray(obj, paths, rowPath, rowKey) {
    const direct = firstNumericArray(obj, paths);
    if (direct) return direct;
    if (rowPath && rowKey) return columnFromRows(getPath(obj, rowPath), rowKey);
    return null;
}

function toSolverCurve1d(curve, defaultId, xAxis, output) {
    const id = curve.curve_id || curve.id || defaultId;
    const points = curve.points || curve.data || [];
    return {
        id,
        curve: {
            type: "1d_lookup_table",
            x_axis: curve.x_axis || xAxis,
            output: curve.output || output,
            interpolation: curve.interpolation || curve.method || "linear",
            points
        }
    };
}

function buildDemoStandardData() {
    const hours = makeHours();
    const it = hours.map((h) => {
        const hour = (h - 1) % 24;
        const day = Math.floor((h - 1) / 24);
        const weekend = day % 7 >= 5;
        const base = weekend ? 520 : (hour >= 8 && hour <= 20 ? 740 : 560);
        const seasonal = 1 + 0.06 * Math.sin((2 * Math.PI * (h - 1)) / 8760 - 0.9);
        return Math.round(base * seasonal * 10) / 10;
    });
    const dryBulb = hours.map((h) => {
        const annual = 13 + 15 * Math.sin((2 * Math.PI * (h - 1)) / 8760 - 1.2);
        const daily = 5 * Math.sin((2 * Math.PI * ((h - 1) % 24)) / 24 - 1.0);
        return Math.round((annual + daily) * 10) / 10;
    });
    const wetBulb = dryBulb.map(v => Math.round((v - 4) * 10) / 10);
    return {
        itLoad: {
            schema_version: "pue.timeseries.it_load.v1",
            type: "annual_it_load",
            units: { hour_index: "1-8760", it_load_kw: "kW" },
            data: { hour_index: hours, hourly_it_load_kW: it }
        },
        weather: {
            schema_version: "pue.timeseries.weather.v1",
            type: "annual_weather",
            units: { dry_bulb_C: "degC", wet_bulb_C: "degC" },
            data: { hour_index: hours, dry_bulb_C: dryBulb, wet_bulb_C: wetBulb }
        },
        dryCooler: {
            schema_version: "pue.curve.dry_cooler.v1",
            type: "dry_cooler_performance",
            rated_power_kW: 45,
            curves: [
                {
                    curve_id: "dry_cooler_power_vs_load",
                    x_axis: "load_ratio",
                    output: "power_kW",
                    points: [[0.2, 6], [0.4, 13], [0.6, 23], [0.8, 34], [1.0, 45]]
                },
                {
                    curve_id: "dry_cooler_leaving_water_temp_vs_oat",
                    x_axis: "outdoor_dry_bulb_C",
                    output: "leaving_water_C",
                    points: [[-10, 8], [0, 11], [10, 16], [20, 23], [30, 32], [40, 42]]
                }
            ]
        },
        chiller: {
            schema_version: "pue.curve.chiller_cop_surface.v1",
            type: "chiller_cop_surface",
            curve_id: "chiller_COP_H_vs_load",
            x_axis: "condenser_entering_water_C",
            y_axis: "load_ratio",
            output: "COP",
            points: [
                [18, 0.25, 7.2], [18, 0.5, 7.0], [18, 0.75, 6.6], [18, 1.0, 6.1],
                [25, 0.25, 6.4], [25, 0.5, 6.1], [25, 0.75, 5.8], [25, 1.0, 5.4],
                [32, 0.25, 5.5], [32, 0.5, 5.2], [32, 0.75, 4.9], [32, 1.0, 4.6]
            ]
        },
        electrical: {
            schema_version: "pue.curve.electrical.v1",
            type: "electrical_efficiency_curves",
            curves: [
                { curve_id: "UPS_efficiency_double_conversion", x_axis: "load_ratio", output: "efficiency", points: [[0.1, 0.91], [0.25, 0.945], [0.5, 0.96], [0.75, 0.965], [1.0, 0.962]] },
                { curve_id: "MV_transformer_efficiency", x_axis: "load_ratio", output: "efficiency", points: [[0.1, 0.965], [0.5, 0.985], [1.0, 0.988]] },
                { curve_id: "LV_transformer_efficiency", x_axis: "load_ratio", output: "efficiency", points: [[0.1, 0.955], [0.5, 0.978], [1.0, 0.982]] }
            ]
        },
        pumps: {
            schema_version: "pue.curve.pumps.v1",
            type: "pump_power_curves",
            curves: [
                { curve_id: "chw_pump_power_vs_it_load", x_axis: "it_load_ratio", output: "power_factor", points: [[0.2, 0.15], [0.5, 0.35], [0.75, 0.65], [1.0, 1.0]] },
                { curve_id: "cw_pump_power_vs_it_load", x_axis: "it_load_ratio", output: "power_factor", points: [[0.2, 0.18], [0.5, 0.4], [0.75, 0.7], [1.0, 1.0]] }
            ]
        },
        fans: {
            schema_version: "pue.curve.fans.v1",
            type: "terminal_fan_power_curves",
            rated_power_kW: 30,
            curves: [
                { curve_id: "terminal_fan_power_vs_it_load", x_axis: "it_load_ratio", output: "power_factor", points: [[0.2, 0.1], [0.5, 0.32], [0.75, 0.62], [1.0, 1.0]] }
            ]
        }
    };
}

function curveLibraryFromStandardFiles(files) {
    const curves = {};
    if (files.dryCooler) {
        const dryCurves = Array.isArray(files.dryCooler.curves)
            ? files.dryCooler.curves
            : [files.dryCooler];
        dryCurves.forEach((curve) => {
            const fallbackOutput = curve.curve_id === "dry_cooler_power_vs_load" ? "power_factor" : "leaving_water_C";
            const fallbackAxis = curve.curve_id === "dry_cooler_power_vs_load" ? "load_ratio" : "outdoor_dry_bulb_C";
            const dry = toSolverCurve1d(curve, curve.curve_id || "dry_cooler_power_vs_load", fallbackAxis, fallbackOutput);
            curves[dry.id] = dry.curve;
        });
    }
    if (files.chiller) {
        const id = files.chiller.curve_id || "chiller_COP_H_vs_load";
        curves[id] = {
            type: "2d_lookup_table",
            x_axis: files.chiller.x_axis || "condenser_entering_water_C",
            y_axis: files.chiller.y_axis || "load_ratio",
            output: files.chiller.output || "COP",
            interpolation: files.chiller.interpolation || "bilinear_or_pchip",
            points: files.chiller.points || files.chiller.data || []
        };
    }
    if (files.electrical && Array.isArray(files.electrical.curves)) {
        files.electrical.curves.forEach((curve) => {
            const c = toSolverCurve1d(curve, curve.curve_id, "load_ratio", "efficiency");
            curves[c.id] = c.curve;
        });
    }
    if (files.pumps && Array.isArray(files.pumps.curves)) {
        files.pumps.curves.forEach((curve) => {
            const c = toSolverCurve1d(curve, curve.curve_id, "it_load_ratio", "power_factor");
            curves[c.id] = c.curve;
        });
    }
    if (files.fans && Array.isArray(files.fans.curves)) {
        files.fans.curves.forEach((curve) => {
            const c = toSolverCurve1d(curve, curve.curve_id || "terminal_fan_power_vs_it_load", "it_load_ratio", "power_factor");
            curves[c.id] = c.curve;
        });
    }
    return { curves };
}

function syncStandardChillerSurfaceToCurveLib(chillerFile) {
    if (!chillerFile) return;
    const points = chillerFile.points || chillerFile.data || [];
    if (!Array.isArray(points) || points.length === 0) return;
    if (!window.curveLib) window.curveLib = { curves_1d: {}, cop_surfaces: {} };
    if (!window.curveLib.cop_surfaces) window.curveLib.cop_surfaces = {};
    const id = chillerFile.curve_id || "chiller_COP_H_vs_load";
    const grouped = {};
    points.forEach((p) => {
        if (!Array.isArray(p) || p.length < 3) return;
        const oat = Number(p[0]);
        const plr = Number(p[1]);
        const cop = Number(p[2]);
        if (!Number.isFinite(oat) || !Number.isFinite(plr) || !Number.isFinite(cop)) return;
        if (!grouped[oat]) grouped[oat] = [];
        grouped[oat].push([plr, cop]);
    });
    const oat_slices = Object.keys(grouped)
        .map(Number)
        .sort((a, b) => a - b)
        .map(oat => ({
            oat_c: oat,
            method: chillerFile.interpolation && String(chillerFile.interpolation).includes("pchip") ? "pchip" : "linear",
            points: grouped[oat].sort((a, b) => a[0] - b[0])
        }));
    if (oat_slices.length > 0) {
        window.curveLib.cop_surfaces[id] = {
            interpolation_oat: "linear",
            oat_slices
        };
        window.preferredCopSurfaceId = id;
        if (window.renderSelectedCopSurface) window.renderSelectedCopSurface();
    }
}

function buildSolverInputFromStandardFiles(files) {
    const it = standardDataArray(files.itLoad || {}, [
        ["data", "hourly_it_load_kW"],
        ["hourly_it_load_kW"],
        ["project", "it_load", "hourly_it_load_kW"]
    ], ["data", "hourly_profile"], "IT_load_kW");
    const dry = standardDataArray(files.weather || {}, [
        ["data", "dry_bulb_C"],
        ["hourly_data", "dry_bulb_C"],
        ["weather", "hourly_data", "dry_bulb_C"]
    ]);
    const wet = standardDataArray(files.weather || {}, [
        ["data", "wet_bulb_C"],
        ["hourly_data", "wet_bulb_C"]
    ]);
    if (!it || !dry) {
        throw new Error(`Missing annual arrays: IT hours=${it ? it.length : 0}, weather hours=${dry ? dry.length : 0}`);
    }
    const auxCoeffInput = document.getElementById("auxFixedCoeff");
    const auxCoeff = auxCoeffInput && Number.isFinite(Number(auxCoeffInput.value))
        ? Math.max(0, Number(auxCoeffInput.value))
        : 0.005;
    const dryApproachInput = document.getElementById("dryCoolerApproachC");
    const dryApproachC = dryApproachInput && Number.isFinite(Number(dryApproachInput.value))
        ? Number(dryApproachInput.value)
        : 5;
    const n = Math.min(it.length, dry.length);
    const designItLoadKw =
        scalarNumberFromPaths(files.itLoad || {}, [["design_it_capacity_kW"], ["project", "it_load", "design_it_load_kW"]]) ||
        projectDesignCapacityKw() ||
        Math.max(...it);
    const solverInput = {
        project: {
            name: "Frontend Standardized Annual PUE Project",
            calculation_mode: "project_8760",
            project_mode: true,
            it_load: {
                hourly_it_load_kW: it.slice(0, n),
                design_it_load_kW: designItLoadKw
            },
            auxiliary_loads: {
                auxiliary_fixed_load_coefficient: auxCoeff
            }
        },
        weather: {
            hourly_data: {
                hour_index: makeHours(n),
                dry_bulb_C: dry.slice(0, n),
                wet_bulb_C: wet ? wet.slice(0, n) : []
            }
        },
        curve_library: curveLibraryFromStandardFiles(files),
        equipment: {
            electrical: {
                UPS: { enabled: true, curve_ref: "UPS_efficiency_double_conversion" },
                MV_transformer: { enabled: true, curve_ref: "MV_transformer_efficiency" },
                LV_transformer: { enabled: true, curve_ref: "LV_transformer_efficiency" }
            },
            cooling: {
                chiller: { enabled: true, curve_ref: "chiller_COP_H_vs_load" },
                dry_cooler: {
                    enabled: Boolean(files.dryCooler),
                    power_curve_ref: "dry_cooler_power_vs_load",
                    leaving_water_temp_curve_ref: "dry_cooler_leaving_water_temp_vs_oat",
                    approach_C: dryApproachC,
                    rated_power_kW: files.dryCooler && files.dryCooler.rated_power_kW ? files.dryCooler.rated_power_kW : undefined
                },
                pumps: { enabled: true },
                fans: {
                    enabled: Boolean(files.fans),
                    power_curve_ref: "terminal_fan_power_vs_it_load",
                    rated_power_kW: files.fans && files.fans.rated_power_kW ? files.fans.rated_power_kW : undefined
                }
            }
        }
    };
    const selection = getCoolingSystemSelection();
    solverInput.curve_sources = buildSelectedCurveSources(selection.powerConfig);
    if (configurationLibraryData) solverInput.configuration_library = configurationLibraryData;
    return window.PueImportAdapter.applyCoolingSystemSelection(
        solverInput, selection.type, selection.capacityMw, selection.powerSource, selection.scenarioKey
    );
}

function previewInputCurves(files) {
    const it = standardDataArray(files.itLoad || {}, [["data", "hourly_it_load_kW"], ["hourly_it_load_kW"], ["project", "it_load", "hourly_it_load_kW"]], ["data", "hourly_profile"], "IT_load_kW");
    const dry = standardDataArray(files.weather || {}, [["data", "dry_bulb_C"], ["hourly_data", "dry_bulb_C"], ["weather", "hourly_data", "dry_bulb_C"]]);
    const itSample = decimateHourlyRows((it || []).map((v, i) => ({ hour_index: i + 1, value: v })), 876);
    const drySample = decimateHourlyRows((dry || []).map((v, i) => ({ hour_index: i + 1, value: v })), 876);

    createChart("inputItChart", {
        type: "line",
        data: { labels: itSample.map(r => r.hour_index), datasets: [{ label: "IT Load kW", data: itSample.map(r => r.value), borderColor: "#059669", pointRadius: 0 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } }, scales: { x: { ticks: { maxTicksLimit: 8 } } } }
    });
    createChart("inputWeatherChart", {
        type: "line",
        data: { labels: drySample.map(r => r.hour_index), datasets: [{ label: "Dry Bulb deg C", data: drySample.map(r => r.value), borderColor: "#dc2626", pointRadius: 0 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } }, scales: { x: { ticks: { maxTicksLimit: 8 } } } }
    });

    const dryCurves = files.dryCooler && Array.isArray(files.dryCooler.curves)
        ? files.dryCooler.curves
        : (files.dryCooler ? [files.dryCooler] : []);
    createChart("inputDryCoolerChart", {
        type: "line",
        data: {
            datasets: dryCurves.map((curve, i) => ({
                label: curve.curve_id || (i === 0 ? "dry_cooler_power_vs_load" : "dry_cooler_leaving_water_temp_vs_oat"),
                data: ((curve.points || curve.data) || []).map(p => ({ x: p[0], y: p[1] })),
                borderColor: ["#2563eb", "#dc2626"][i % 2],
                backgroundColor: ["#2563eb", "#dc2626"][i % 2],
                yAxisID: (curve.output || "").toLowerCase().includes("water") ? "y1" : "y",
                pointRadius: 2
            }))
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: "bottom" } },
            scales: {
                x: { type: "linear", title: { display: true, text: "load ratio or outdoor dry bulb C" } },
                y: { title: { display: true, text: "power factor or kW" }, beginAtZero: true },
                y1: { position: "right", title: { display: true, text: "leaving water C" }, grid: { drawOnChartArea: false } }
            }
        }
    });

    const chillerPts = (files.chiller && (files.chiller.points || files.chiller.data)) || [];
    const sliceKeys = [...new Set(chillerPts.map(p => p[0]))];
    createChart("inputChillerChart", {
        type: "line",
        data: {
            labels: [...new Set(chillerPts.map(p => p[1]))],
            datasets: sliceKeys.map((key, i) => ({
                label: `T=${key}`,
                data: chillerPts.filter(p => p[0] === key).map(p => p[2]),
                borderColor: ["#2563eb", "#059669", "#dc2626", "#7c3aed"][i % 4]
            }))
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } }
    });
    renderChillerSurfaceFunction(chillerPts);
    renderChillerSurfacePlot(chillerPts);

    const elecCurves = (files.electrical && files.electrical.curves) || [];
    createChart("inputElectricalChart", {
        type: "line",
        data: {
            datasets: elecCurves.map((curve, i) => ({
                label: curve.curve_id,
                data: (curve.points || []).map(p => ({ x: p[0], y: p[1] })),
                borderColor: ["#2563eb", "#059669", "#f59e0b"][i % 3],
                backgroundColor: ["#2563eb", "#059669", "#f59e0b"][i % 3],
                pointRadius: 2
            }))
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: "bottom" } },
            scales: {
                x: { type: "linear", title: { display: true, text: "load ratio" } },
                y: { title: { display: true, text: "efficiency" } }
            }
        }
    });

    const pumpCurves = (files.pumps && files.pumps.curves) || [];
    createChart("inputPumpChart", {
        type: "line",
        data: {
            datasets: pumpCurves.map((curve, i) => ({
                label: curve.curve_id,
                data: (curve.points || []).map(p => ({ x: p[0], y: p[1] })),
                borderColor: ["#2563eb", "#7c3aed"][i % 2],
                backgroundColor: ["#2563eb", "#7c3aed"][i % 2],
                pointRadius: 2
            }))
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: "bottom" } },
            scales: {
                x: { type: "linear", title: { display: true, text: "IT load ratio" } },
                y: { title: { display: true, text: "power factor or kW" }, beginAtZero: true }
            }
        }
    });

    const auxCoeffInput = document.getElementById("auxFixedCoeff");
    const auxCoeff = auxCoeffInput && Number.isFinite(Number(auxCoeffInput.value)) ? Number(auxCoeffInput.value) : 0.005;
    const auxSample = itSample.map(r => ({ hour_index: r.hour_index, value: r.value * auxCoeff }));
    createChart("inputAuxChart", {
        type: "line",
        data: { labels: auxSample.map(r => r.hour_index), datasets: [{ label: `Aux kW = IT x ${auxCoeff}`, data: auxSample.map(r => r.value), borderColor: "#7c3aed", pointRadius: 0 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } }, scales: { x: { ticks: { maxTicksLimit: 8 } } } }
    });

    const fanCurves = (files.fans && files.fans.curves) || [];
    createChart("inputFanChart", {
        type: "line",
        data: {
            datasets: fanCurves.map((curve, i) => ({
                label: curve.curve_id,
                data: (curve.points || []).map(p => ({ x: p[0], y: p[1] })),
                borderColor: ["#0f766e", "#2563eb"][i % 2],
                backgroundColor: ["#0f766e", "#2563eb"][i % 2],
                pointRadius: 2
            }))
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: "bottom" } },
            scales: {
                x: { type: "linear", title: { display: true, text: "IT load ratio" } },
                y: { title: { display: true, text: "power factor or kW" }, beginAtZero: true }
            }
        }
    });
}

function refreshStandardInputStatus() {
    const it = standardDataArray(standardDataFiles.itLoad || {}, [["data", "hourly_it_load_kW"], ["hourly_it_load_kW"], ["project", "it_load", "hourly_it_load_kW"]], ["data", "hourly_profile"], "IT_load_kW");
    const dry = standardDataArray(standardDataFiles.weather || {}, [["data", "dry_bulb_C"], ["hourly_data", "dry_bulb_C"], ["weather", "hourly_data", "dry_bulb_C"]]);
    const el = document.getElementById("standardInputStatus");
    if (el) {
        const ready = Boolean(it && dry);
        el.textContent = ready
            ? `输入就绪：IT=${it.length}小时，天气=${dry.length}小时，点击“运行计算”会自动生成 solver 输入。`
            : `等待输入：IT=${it ? it.length : 0}小时，天气=${dry ? dry.length : 0}小时。`;
        el.style.color = ready ? "#059669" : "#6b7280";
    }
}

async function handleStandardFile(slot, statusId, file) {
    try {
        const json = window.PueImportAdapter
            ? await window.PueImportAdapter.adaptFile(slot, file)
            : await readJsonFile(file);
        if (json && typeof json === "object") json.source_file = file.name;
        if (slot === "itLoad") {
            normalizeItLoadPercentFile(json);
        }
        if (slot === "weather" && json && json.source_format === "epw") {
            setWeatherSourceMetadata(json, {
                source: "Manual Upload",
                station: json.location && json.location.city ? json.location.city : "",
                epw_file: file.name,
                location: [json.location?.city, json.location?.country].filter(Boolean).join(", "),
                weather_hours: getWeatherHours(json)
            });
        }
        standardDataFiles[slot] = json;
        standardSolverInput = null;
        preferStandardFiles = true;
        if (slot === "chiller") syncStandardChillerSurfaceToCurveLib(json);
        if (slot === "weather" && json.source_format === "epw") {
            const data = json.data || {};
            const ghi = summarizeNumericArray(data.global_horizontal_radiation_Wh_m2);
            const wind = summarizeNumericArray(data.wind_speed_m_s);
            const extra = [
                ghi ? `GHI ${fmtInteger(ghi.sum / 1000)} kWh/m²` : "",
                wind ? `平均风速 ${fmtNumber(wind.avg, 1)} m/s` : ""
            ].filter(Boolean).join("，");
            updateFileStatus(statusId, `${file.name} 已导入 EPW${extra ? "：" + extra : ""}`, "ok");
        } else {
            updateFileStatus(statusId, `${file.name} 已导入为 ${json.type || "standard_json"}`, "ok");
        }
        previewInputCurves(standardDataFiles);
        renderCoolingSystemSelection();
        renderWeatherReportPanel();
        renderTemperatureDistributionPanel();
        refreshStandardInputStatus();
    } catch (e) {
        standardDataFiles[slot] = null;
        standardSolverInput = null;
        preferStandardFiles = true;
        updateFileStatus(statusId, `读取失败：${String(e.message || e)}`, "error");
        renderCoolingSystemSelection();
        refreshStandardInputStatus();
    }
}

function loadDemoStandardData() {
    const demo = buildDemoStandardData();
    Object.assign(standardDataFiles, demo);
    renderCoolingSystemSelection();
    syncStandardChillerSurfaceToCurveLib(demo.chiller);
    standardSolverInput = null;
    preferStandardFiles = true;
    updateFileStatus("statusItLoad", "演示 8760 IT 负载已加载", "ok");
    updateFileStatus("statusWeather", "演示 8760 天气已加载", "ok");
    updateFileStatus("statusDryCooler", "演示干冷器曲线已加载", "ok");
    updateFileStatus("statusChiller", "演示冷水机COP曲面已加载", "ok");
    updateFileStatus("statusElectrical", "演示电气曲线已加载", "ok");
    updateFileStatus("statusPumps", "演示水泵曲线已加载", "ok");
    updateFileStatus("statusAuxFixed", "演示Aux系数已加载", "ok");
    updateFileStatus("statusFans", "演示末端风机曲线已加载", "ok");
    previewInputCurves(standardDataFiles);
    refreshStandardInputStatus();
}

function buildStandardSolverInputToTextarea() {
    try {
        standardSolverInput = buildSolverInputFromStandardFiles(standardDataFiles);
        preferStandardFiles = true;
        syncStandardChillerSurfaceToCurveLib(standardDataFiles.chiller);
        elIn.value = pretty(standardSolverInput);
        previewInputCurves(standardDataFiles);
        refreshStandardInputStatus();
        setSolverDataStatus("标准化文件已生成 solver.py 项目输入；Run 将调用 compute_pue_project。", "ok");
        log(
            "Standardized files converted to solver input\n" +
            `IT hours=${standardSolverInput.project.it_load.hourly_it_load_kW.length}\n` +
            `Weather hours=${standardSolverInput.weather.hourly_data.dry_bulb_C.length}\n` +
            "Solver function=compute_pue_project"
        );
    } catch (e) {
        standardSolverInput = null;
        refreshStandardInputStatus();
        setSolverDataStatus(`标准化文件生成失败：${String(e.message || e)}`, "error");
        log("❌ 标准化文件生成失败：\n" + String(e.message || e));
    }
}

// The library is a sibling of pue-solver-main. Resolve every library workbook
// from this single root so configuration, scenario, equipment, input, and
// source files cannot accidentally fall back to the page's own directory.
const CONFIGURATION_LIBRARY_ROOT_URL = new URL("../Configuration Library/", document.baseURI);

async function fetchConfigurationWorkbook(relativePath) {
    const workbookUrl = new URL(relativePath, CONFIGURATION_LIBRARY_ROOT_URL);
    const response = await fetch(workbookUrl, { cache: "no-store" });
    if (!response.ok) throw new Error(`Could not load ${workbookUrl.href} (HTTP ${response.status}).`);
    const workbook = XLSX.read(await response.arrayBuffer(), { type: "array" });
    const sheets = {};
    workbook.SheetNames.forEach(name => {
        sheets[name] = XLSX.utils.sheet_to_json(workbook.Sheets[name], { defval: null });
    });
    return sheets;
}

function configurationLibraryFetchPath(relativePath) {
    return String(relativePath || "").split("/").map(segment => encodeURIComponent(segment)).join("/");
}

async function fetchConfigurationLibraryArrayBuffer(relativePath) {
    const workbookUrl = new URL(configurationLibraryFetchPath(relativePath), CONFIGURATION_LIBRARY_ROOT_URL);
    const response = await fetch(workbookUrl, { cache: "no-store" });
    if (!response.ok) throw new Error(`Could not load ${workbookUrl.href} (HTTP ${response.status}).`);
    return response.arrayBuffer();
}

function configurationLibraryPyodidePath(configurationName) {
    return `${CONFIGURATION_LIBRARY_PYODIDE_ROOT}/${configurationName}`;
}

function buildConfigurationLibraryWorkbookSyncPlan(data) {
    const configurationName = data?.configuration_name;
    const directModeItems = DIRECT_MODE_EQUIPMENT_ORDER.map(equipmentId => {
        const resolved = findLibraryEquipmentPackage(data, equipmentId);
        const aliases = DIRECT_MODE_EQUIPMENT_CANDIDATES[resolved.resolvedId] || [resolved.resolvedId];
        const sourceIds = [resolved.resolvedId, ...aliases, resolved.equipmentPackage?.equipment_id, resolved.packageKey]
            .filter(Boolean)
            .filter((value, index, values) => values.indexOf(value) === index);
        return { sourceIds, targetId: resolved.resolvedId, required: true };
    });
    const loadedItems = Object.entries(data?.equipment || {}).map(([key, item]) => {
        const loadedId = item?.equipment_id || key;
        const resolvedId = resolveDirectModeEquipmentId(loadedId);
        if (DIRECT_MODE_EQUIPMENT_ORDER.includes(resolvedId)) return null;
        return {
            sourceIds: [loadedId],
            targetId: loadedId,
            required: false
        };
    }).filter(Boolean);
    const seenTargets = new Set();
    return [...directModeItems, ...loadedItems].filter(item => {
        if (!item.sourceIds?.length || !item.targetId) return false;
        const targetPath = `equipment/${item.targetId}/${item.targetId}.xlsx`;
        if (seenTargets.has(targetPath)) return false;
        seenTargets.add(targetPath);
        item.sourceRelativePaths = item.sourceIds.map(sourceId => `${configurationName}/equipment/${sourceId}/${sourceId}.xlsx`);
        item.pyodideRelativePath = targetPath;
        return true;
    });
}

async function fetchFirstConfigurationLibraryWorkbook(relativePaths) {
    const errors = [];
    for (const relativePath of relativePaths || []) {
        try {
            return {
                relativePath,
                arrayBuffer: await fetchConfigurationLibraryArrayBuffer(relativePath)
            };
        } catch (error) {
            errors.push(`${relativePath}: ${String(error.message || error)}`);
        }
    }
    throw new Error(errors.join("; "));
}

async function fetchResolvedConfigurationEquipmentWorkbook(configurationBase, rawEquipmentId) {
    const resolvedId = resolveFrontendEquipmentId(rawEquipmentId);
    const candidateIds = [resolvedId, rawEquipmentId]
        .filter(Boolean)
        .filter((value, index, values) => values.indexOf(value) === index);
    const errors = [];
    for (const candidateId of candidateIds) {
        const packagePath = `equipment/${candidateId}/${candidateId}.xlsx`;
        try {
            return {
                resolvedId,
                rawEquipmentId,
                sourceEquipmentId: candidateId,
                packagePath,
                sheets: await fetchConfigurationWorkbook(`${configurationBase}/${packagePath}`)
            };
        } catch (error) {
            errors.push(`${packagePath}: ${String(error.message || error)}`);
        }
    }
    throw new Error(errors.join("; "));
}

function verifyConfigurationLibrarySynced(configurationPath) {
    const accWorkbookPath = `${configurationPath}/equipment/ACC_2/ACC_2.xlsx`;
    try {
        pyodide.FS.stat(accWorkbookPath);
    } catch (_) {
        throw new Error("Configuration Library workbooks were not synced into Pyodide runtime. Please reload the Configuration Library.");
    }
}

async function syncConfigurationLibraryToPyodide(selectedConfiguration) {
    if (!pyodide) throw new Error("Pyodide is not loaded.");
    const configurationName = selectedConfiguration?.configuration_name;
    if (!configurationName) throw new Error("Configuration Library path is missing. Please click Load Configuration Library before running.");
    const configurationPath = configurationLibraryPyodidePath(configurationName);
    ensurePyodideDir(configurationPath);

    const syncedPaths = [];
    const workbookPaths = [];
    const supportFiles = ["configuration.xlsx", "scenario.xlsx", "input/IT_LOAD_90_PERCENT.xlsx"];
    for (const relativePath of supportFiles) {
        const arrayBuffer = await fetchConfigurationLibraryArrayBuffer(`${configurationName}/${relativePath}`);
        const pyodidePath = `${configurationPath}/${relativePath}`;
        writeBinaryFileToPyodide(pyodidePath, arrayBuffer);
        syncedPaths.push(pyodidePath);
    }

    const workbookPlan = buildConfigurationLibraryWorkbookSyncPlan(selectedConfiguration);
    for (const item of workbookPlan) {
        let fetched;
        try {
            fetched = await fetchFirstConfigurationLibraryWorkbook(item.sourceRelativePaths);
        } catch (error) {
            throw new Error(`Could not sync Configuration Library workbook ${item.sourceRelativePaths?.[0]}: ${String(error.message || error)}`);
        }
        const pyodidePath = `${configurationPath}/${item.pyodideRelativePath}`;
        writeBinaryFileToPyodide(pyodidePath, fetched.arrayBuffer);
        syncedPaths.push(pyodidePath);
        workbookPaths.push(pyodidePath);
    }

    verifyConfigurationLibrarySynced(configurationPath);
    return {
        configuration_name: configurationName,
        configuration_path: configurationPath,
        workbook_paths: workbookPaths,
        synced_paths: syncedPaths
    };
}

function configurationKeyValues(rows, key = "Parameter", value = "Value") {
    return Object.fromEntries((rows || []).filter(row => row[key] !== null).map(row => [row[key], row[value]]));
}

function librarySheetKeyValues(rows) {
    const result = {};
    (rows || []).forEach(row => {
        const key = row.Parameter ?? row.Field ?? row.Item ?? row["Check Item"];
        const value = Object.prototype.hasOwnProperty.call(row, "Value") ? row.Value : row.Status;
        if (key !== null && key !== undefined) result[String(key)] = value;
    });
    return result;
}

function selectLibrarySolverCurve(equipmentPackage, scenarioName) {
    const electricalPath = equipmentPackage?.electrical_path;
    if (electricalPath && Number.isFinite(Number(electricalPath.it_efficiency)) && Number.isFinite(Number(electricalPath.mep_efficiency))) {
        return { status: "Electrical Path Found", sheet_name: "Solver", curve: null, electrical_path: electricalPath };
    }
    const curves = equipmentPackage?.solver_curves || {};
    const scenario = String(scenarioName || "").toLowerCase();
    const preferred = scenario === "normal" ? "Solver_Curve_Normal"
        : (["failure", "maintenance"].includes(scenario) ? "Solver_Curve_Failure" : null);
    const selected = [preferred, "Solver_Curve"].find(name => name && Array.isArray(curves[name]) && curves[name].length);
    if (selected) return { status: "Selected", sheet_name: selected, curve: curves[selected] };
    if (String(equipmentPackage?.equipment_id || "").startsWith("ACC_") && equipmentPackage?.performance_map?.length) {
        return { status: "Selected", sheet_name: "Performance_Map", curve: equipmentPackage.performance_map };
    }
    return { status: "Missing Solver_Curve", sheet_name: null, curve: null };
}

function librarySelectedCurveType(selected) {
    if (selected?.electrical_path) return "electrical_efficiency";
    const rows = selected?.curve || [];
    const first = rows.find(row => row && typeof row === "object") || {};
    const keys = new Set(Object.keys(first).map(key => normalizeEquipmentCurveKey(key)));
    const has = (...names) => names.some(name => keys.has(normalizeEquipmentCurveKey(name)));
    if (has("ambient_C") && has("load_ratio") && has("power_input_kW")) return "two_dimensional_power";
    if (has("load_ratio") && has("power_kW", "engine_output_kW", "radiator_fan_power_kW")) return "one_dimensional_power";
    if (has("load_ratio") && has("efficiency")) return "electrical_efficiency";
    if (has("load_ratio") && has("loss_fraction")) return "electrical_loss_fraction";
    if (has("load_ratio") && has("loss_kW")) return "electrical_loss_kW";
    return "Not available";
}

function displayCurveType(curveType) {
    const normalized = String(curveType || "");
    return {
        efficiency: "electrical_efficiency",
        loss_fraction: "electrical_loss_fraction",
        loss_kW: "electrical_loss_kW"
    }[normalized] || normalized;
}

function firstAvailableResultField(source, fieldNames) {
    return fieldNames.map(field => source?.[field]).find(value => value !== null && value !== undefined && value !== "");
}

function sumAvailableResultFields(source, fieldNames) {
    const values = fieldNames.map(field => source?.[field]);
    if (values.some(value => value === null || value === undefined || !Number.isFinite(Number(value)))) return null;
    return values.reduce((sum, value) => sum + Number(value), 0);
}

function maxHourlyResultField(hourlyRows, fieldNames) {
    const values = (hourlyRows || []).flatMap(row => fieldNames.map(field => Number(row?.[field]))).filter(Number.isFinite);
    return values.length ? Math.max(...values) : null;
}

function buildFrontendSolverInputFromLibrary(data, scenarioNameOverride = null) {
    const projectInfo = getProjectReportInfo();
    const totalCapacityMw = projectInfo.capacityMw;
    if (!(Number(totalCapacityMw) > 0)) return null;
    const scenarioName = scenarioNameOverride || (document.getElementById("scenarioSelect")?.value === "one_failure_three_active" ? "Failure" : "Normal");
    const sizing = calculateFrontendUnitRequirements(totalCapacityMw, data.cooling_unit_capacity_mw);
    const unitQuantity = getUnitQuantitySelection(sizing);
    const activeUnits = unitQuantity.mode === "manual"
        ? Number(unitQuantity.running_units || 0)
        : (scenarioName === "Normal" ? sizing.normalActiveUnits : sizing.failureActiveUnits);
    const installedUnits = unitQuantity.mode === "manual"
        ? Number(unitQuantity.installed_units || activeUnits || 0)
        : sizing.installedUnits;
    const indoorActiveUnits = unitQuantity.mode === "manual"
        ? installedUnits
        : sizing.indoorActiveUnits;
    const standbyUnits = unitQuantity.mode === "manual"
        ? Number(unitQuantity.standby_units || Math.max(installedUnits - activeUnits, 0))
        : Math.max(installedUnits - activeUnits, 0);
    const designItLoadKw = Number(totalCapacityMw) * 1000;
    const heatGains = getCoolingLoadHeatGainInput();
    const peakDesignWeather = getPeakDesignWeatherInput();
    const percentages = data.it_load.hourly_it_load_percent || [];
    const hourlyItLoadKw = percentages.map(percent => designItLoadKw * Number(percent) / 100);
    const selectedCurves = Object.fromEntries(DIRECT_MODE_EQUIPMENT_ORDER.map(equipmentId => {
        const resolved = findLibraryEquipmentPackage(data, equipmentId);
        return [resolved.resolvedId, selectLibrarySolverCurve(resolved.equipmentPackage, scenarioName)];
    }));
    const binding = (equipmentId, role) => {
        const resolved = findLibraryEquipmentPackage(data, equipmentId);
        const item = resolved.equipmentPackage;
        const selected = selectedCurves[resolved.resolvedId];
        return {
            enabled: item?.status !== "Missing",
            equipment_id: resolved.resolvedId,
            source_equipment_id: item?.equipment_id || null,
            role,
            package_path: item?.package_path || null,
            selected_curve_sheet: selected?.sheet_name || null,
            selected_curve_status: selected?.status || "Missing Solver_Curve",
            curve_data: selected?.curve || null
        };
    };
    const electricalPath = data.equipment.ELECTRICAL_DISTRIBUTION_2?.electrical_path || null;
    return {
        configuration_name: data.configuration_name,
        configuration_path: data.configuration_path || data.configuration_name,
        cooling_system_type: data.cooling_system_type,
        cooling_unit_capacity_mw: data.cooling_unit_capacity_mw,
        power_source: data.power_source,
        scenario_name: scenarioName,
        project: {
            name: data.configuration_name,
            calculation_mode: "project_8760",
            project_mode: true,
            latitude: projectInfo.latitude,
            longitude: projectInfo.longitude,
            site_location: {
                latitude: projectInfo.latitude,
                longitude: projectInfo.longitude
            },
            peak_design_weather_source: peakDesignWeather.peakDesignWeatherSource,
            peak_design_outdoor_dry_bulb_C: peakDesignWeather.peakDesignOutdoorDryBulbC,
            ashrae_design_conditions_url: peakDesignWeather.ashraeDesignConditionsUrl,
            location: {
                name: projectInfo.location,
                latitude: projectInfo.latitude,
                longitude: projectInfo.longitude,
                peak_design_weather_source: peakDesignWeather.peakDesignWeatherSource,
                peak_design_outdoor_dry_bulb_C: peakDesignWeather.peakDesignOutdoorDryBulbC,
                ashrae_design_conditions_url: peakDesignWeather.ashraeDesignConditionsUrl
            },
            design_it_load_kW: designItLoadKw,
            cooling_unit_capacity_kW: data.cooling_unit_capacity_mw * 1000,
            required_units: sizing.requiredUnits,
            installed_units: installedUnits,
            active_units: activeUnits,
            indoor_active_units: indoorActiveUnits,
            running_units: activeUnits,
            standby_units: standbyUnits,
            redundancy_strategy: unitQuantity.redundancy === "auto" ? sizing.redundancy : unitQuantity.redundancy,
            unit_quantity: unitQuantity,
            scenario_name: scenarioName,
            heat_gains: {
                solar_heat_gain_max_kW: heatGains.solarHeatGainMaxKw,
                solar_daytime_start_hour: heatGains.solarDaytimeStartHour,
                solar_daytime_end_hour: heatGains.solarDaytimeEndHour,
                other_auxiliary_heat_gain_kW: heatGains.otherAuxiliaryHeatGainKw
            },
            auxiliary_loads: {
                other_electrical_auxiliary_power_kW: heatGains.otherElectricalAuxiliaryPowerKw
            },
            it_load: {
                design_it_load_kW: designItLoadKw,
                hourly_it_load_percent: percentages,
                hourly_it_load_kW: hourlyItLoadKw
            }
        },
        unit_quantity: unitQuantity,
        equipment: {
            cooling: {
                ACC: binding("ACC_2", "cooling_equipment"),
                pumps: { CHW_PUMP_2: binding("CHW_PUMP_2", "pump_power") },
                engine: binding("ENGINE_3", "engine_output_reference"),
                engine_radiator: binding("ENGINE_RADIATOR_1", "engine_radiator_power")
            },
            auxiliary: Object.fromEntries(["CDU_2", "RTC_1&2", "MAU_1&2"].map(id => [id, binding(id, "white_space_auxiliary")])),
            electrical_path: electricalPath
        },
        electrical_path: electricalPath,
        heat_gains: {
            solar_heat_gain_max_kW: heatGains.solarHeatGainMaxKw,
            solar_daytime_start_hour: heatGains.solarDaytimeStartHour,
            solar_daytime_end_hour: heatGains.solarDaytimeEndHour,
            other_auxiliary_heat_gain_kW: heatGains.otherAuxiliaryHeatGainKw
        },
        peak_design_weather_source: peakDesignWeather.peakDesignWeatherSource,
        peak_design_outdoor_dry_bulb_C: peakDesignWeather.peakDesignOutdoorDryBulbC,
        ashrae_design_conditions_url: peakDesignWeather.ashraeDesignConditionsUrl,
        site_location: {
            latitude: projectInfo.latitude,
            longitude: projectInfo.longitude,
            ashrae_design_conditions_url: peakDesignWeather.ashraeDesignConditionsUrl
        },
        other_electrical_auxiliary_power_kW: heatGains.otherElectricalAuxiliaryPowerKw,
        selected_curves: selectedCurves
    };
}

function convertFrontendLibraryInputToSolverInput(libraryInput) {
    const clone = value => JSON.parse(JSON.stringify(value));
    const project = clone(libraryInput.project);
    const hourlyIt = project.it_load.hourly_it_load_kW;
    const hours = hourlyIt.length;
    const activeUnits = Number(project.active_units);
    project.auxiliary_loads = project.auxiliary_loads && typeof project.auxiliary_loads === "object" ? project.auxiliary_loads : {};
    project.auxiliary_loads.other_electrical_auxiliary_power_kW =
        project.auxiliary_loads.other_electrical_auxiliary_power_kW ?? libraryInput.other_electrical_auxiliary_power_kW ?? 0;
    project.it_load.cooling_unit_capacity_kW = project.cooling_unit_capacity_kW;
    project.it_load.cooling_unit_count = activeUnits;
    project.cooling_unit_count = activeUnits;

    const dry = standardDataArray(standardDataFiles.weather || {}, [["data", "dry_bulb_C"], ["hourly_data", "dry_bulb_C"]]);
    const wet = standardDataArray(standardDataFiles.weather || {}, [["data", "wet_bulb_C"], ["hourly_data", "wet_bulb_C"]]);
    const hasAnnualWeather = Array.isArray(dry) && dry.length >= hours;
    const weather = { hourly_data: {
        hour_index: makeHours(hours),
        dry_bulb_C: hasAnnualWeather ? dry.slice(0, hours) : Array(hours).fill(25),
        wet_bulb_C: hasAnnualWeather && wet?.length >= hours ? wet.slice(0, hours) : []
    }, metadata: hasAnnualWeather
        ? { source: "loaded_weather" }
        : { source: "library_solver_adapter_default", assumption: "25 C constant dry bulb" }
    };
    const accRows = libraryInput.selected_curves.ACC_2?.curve || [];
    const pumpRows = libraryInput.selected_curves.CHW_PUMP_2?.curve || [];
    const engineRows = libraryInput.selected_curves.ENGINE_3?.curve || [];
    const radiatorRows = libraryInput.selected_curves.ENGINE_RADIATOR_1?.curve || [];
    const accCurveId = "ACC_2_COP";
    const pumpCurveId = "CHW_PUMP_2_power_vs_load";
    const curves = {
        [accCurveId]: {
            type: "2d_lookup_table", x_axis: "ambient_C", y_axis: "load_ratio", output: "COP", interpolation: "bilinear",
            data: accRows.filter(row => row.ambient_C != null && row.load_ratio != null && row.COP != null)
                .map(row => ({ ambient_C: row.ambient_C, load_ratio: row.load_ratio, COP: row.COP }))
        },
        [pumpCurveId]: {
            type: "1d_lookup_table", x_axis: "load_ratio", output: "power_kW", interpolation: "linear",
            data: pumpRows.filter(row => row.load_ratio != null && row.power_kW != null)
                .map(row => ({ load_ratio: row.load_ratio, power_kW: row.power_kW }))
        }
    };
    return {
        configuration_name: libraryInput.configuration_name,
        configuration_path: libraryInput.configuration_path || libraryInput.configuration_name,
        cooling_system_type: libraryInput.cooling_system_type,
        cooling_unit_capacity_mw: libraryInput.cooling_unit_capacity_mw,
        power_source: libraryInput.power_source,
        scenario_name: libraryInput.scenario_name,
        acc_curve: {
            equipment_id: "ACC_2",
            source_sheet: libraryInput.selected_curves.ACC_2?.sheet_name || null,
            data: clone(accRows)
        },
        engine_curve: {
            equipment_id: "ENGINE_3",
            source_sheet: libraryInput.selected_curves.ENGINE_3?.sheet_name || null,
            data: clone(engineRows),
            default_efficiency: 0.40,
            default_efficiency_source: "temporary_assumption_pending_vendor_fuel_map"
        },
        engine_radiator_curve: {
            equipment_id: "ENGINE_RADIATOR_1",
            source_sheet: libraryInput.selected_curves.ENGINE_RADIATOR_1?.sheet_name || null,
            data: clone(radiatorRows)
        },
        project,
        peak_design_weather_source: libraryInput.peak_design_weather_source ?? project.peak_design_weather_source ?? "ashrae_auto",
        peak_design_outdoor_dry_bulb_C: libraryInput.peak_design_outdoor_dry_bulb_C ?? project.peak_design_outdoor_dry_bulb_C ?? null,
        ashrae_design_conditions_url: libraryInput.ashrae_design_conditions_url ?? project.ashrae_design_conditions_url ?? null,
        solar_heat_gain_max_kW: libraryInput.heat_gains?.solar_heat_gain_max_kW ?? 0,
        solar_daytime_start_hour: libraryInput.heat_gains?.solar_daytime_start_hour ?? 6,
        solar_daytime_end_hour: libraryInput.heat_gains?.solar_daytime_end_hour ?? 18,
        other_auxiliary_heat_gain_kW: libraryInput.heat_gains?.other_auxiliary_heat_gain_kW ?? 0,
        unit_quantity: clone(libraryInput.unit_quantity),
        weather,
        curve_library: { curves },
        equipment: {
            cooling: {
                cooling_unit_capacity_kW: project.cooling_unit_capacity_kW,
                cooling_unit_count: activeUnits,
                chiller: { enabled: true, curve_ref: accCurveId, source_equipment_id: "ACC_2" },
                ACC: { enabled: true, curve_ref: accCurveId, source_equipment_id: "ACC_2" },
                dry_cooler: { enabled: false },
                pumps: { enabled: true, power_curve_refs: [pumpCurveId], source_equipment_id: "CHW_PUMP_2" },
                fans: { enabled: false }
            },
            library_fixed_power: clone(libraryInput.equipment.auxiliary),
            electrical_path: clone(libraryInput.electrical_path)
        },
        electrical_path: clone(libraryInput.electrical_path),
        library_context: {
            scenario_name: libraryInput.scenario_name,
            required_units: project.required_units,
            installed_units: project.installed_units,
            active_units: project.active_units,
            indoor_active_units: project.indoor_active_units,
            selected_curves: clone(libraryInput.selected_curves),
            engine_output_reference: clone(libraryInput.equipment.cooling.engine),
            engine_radiator: clone(libraryInput.equipment.cooling.engine_radiator),
            auxiliary_equipment: clone(libraryInput.equipment.auxiliary),
            electrical_path: clone(libraryInput.electrical_path),
            unit_quantity: clone(libraryInput.unit_quantity),
            adapter_assumptions: clone(weather.metadata)
        }
    };
}

async function runUsingConfigurationLibrary() {
    const status = document.getElementById("configurationLibraryStatus");
    if (!configurationLibraryData) {
        if (status) status.textContent = "Load Configuration Library first.";
        return;
    }
    const calculationMode = CONFIGURATION_LIBRARY_DIRECT_CALCULATION_MODE;
    const libraryInput = buildFrontendSolverInputFromLibrary(configurationLibraryData);
    if (!libraryInput) {
        if (status) status.textContent = "Enter Total IT Capacity before running the configuration.";
        return;
    }
    let syncResult;
    setRunButtonsDisabled(true);
    try {
        await ensurePyodideReady();
        syncResult = await syncConfigurationLibraryToPyodide(configurationLibraryData);
    } catch (error) {
        if (status) {
            status.textContent = String(error.message || error);
            status.style.color = "#dc2626";
        }
        log("Configuration Library workbook sync failed:\n" + String(error.message || error));
        setRunButtonsDisabled(false);
        return;
    }
    configurationLibraryData.configuration_path = syncResult.configuration_path;
    configurationLibraryData.pyodide_sync = syncResult;
    libraryInput.configuration_path = syncResult.configuration_path;
    configurationLibraryData.standardized_solver_input = libraryInput;
    const adaptedInput = convertFrontendLibraryInputToSolverInput(libraryInput);
    applyAccCalculationEngineSelection(adaptedInput, calculationMode, libraryInput.configuration_path);
    if (!adaptedInput.acc_v2?.configuration_path) {
        if (status) {
            status.textContent = "Configuration Library path is missing. Please click Load Configuration Library before running.";
            status.style.color = "#dc2626";
        }
        return;
    }
    elIn.value = pretty(adaptedInput);
    const calculationModeLabel = "Configuration Library Direct Solver_Curve Hourly Simulation";
    if (status) status.textContent = `Running ${configurationLibraryData.configuration_name} / ${libraryInput.scenario_name} / ${calculationModeLabel}...`;
    log(
        `Configuration Library synced: ${syncResult.configuration_name}, workbooks=${syncResult.workbook_paths.length}\n` +
        syncResult.workbook_paths.slice(0, 5).join("\n")
    );
    try {
        await run({ libraryRun: true, libraryInput: adaptedInput });
    } finally {
        setRunButtonsDisabled(false);
    }
}

function renderConfigurationLibrarySummary(data) {
    const summary = document.getElementById("configurationLibrarySummary");
    if (!summary) return;
    const totalCapacity = getProjectReportInfo().capacityMw;
    const sizing = calculateFrontendUnitRequirements(totalCapacity, data.cooling_unit_capacity_mw);
    const standardized = data.standardized_solver_input || buildFrontendSolverInputFromLibrary(data);
    const activeUnits = standardized?.project?.active_units;
    const unitQuantity = standardized?.unit_quantity || getUnitQuantitySelection(sizing);
    renderUnitQuantityStatus(unitQuantity);
    const itSample = standardized?.project?.it_load?.hourly_it_load_kW?.slice(0, 3) || [];
    const electricalPath = standardized?.electrical_path;
    const annualElectrical = data.last_solver_output?.annual_results || {};
    const peakResults = data.last_solver_output?.peak_results || {};
    const hourlyElectrical = Array.isArray(data.last_solver_output?.hourly_results) ? data.last_solver_output.hourly_results : [];
    const directAccV2Disclosure = isConfigurationLibraryAccV2DirectResult(data.last_solver_output || {}, data.standardized_solver_input || null);
    const resultValue = (value, formatter) => value != null ? formatter(value) : "Not available";
    const whiteSpaceEnergy = firstAvailableResultField(annualElectrical, ["annual_white_space_equipment_energy_kWh"])
        ?? sumAvailableResultFields(annualElectrical, ["annual_cdu_energy_kWh", "annual_rtc_energy_kWh", "annual_mau_energy_kWh"]);
    const engineRadiatorMaxPower = firstAvailableResultField(annualElectrical, ["max_engine_radiator_power_kW"])
        ?? maxHourlyResultField(hourlyElectrical, ["engine_radiator_power_kW"]);
    const values = [
        ["Loaded configuration name", data.configuration_name],
        ["Cooling unit capacity", `${data.cooling_unit_capacity_mw} MW`],
        ["Equipment count", data.equipment_count],
        ["IT load hours", data.it_load.hours],
        ["Scenario list", data.scenarios.map(item => item.scenario).join(", ")],
        ["Required units", sizing === null ? "Enter Total IT Capacity" : `${sizing.requiredUnits} = ceil(${totalCapacity} / ${data.cooling_unit_capacity_mw})`],
        ["Installed units", unitQuantity?.installed_units ?? "Enter Total IT Capacity"],
        ["Running Units", unitQuantity?.running_units ?? "Enter Total IT Capacity"],
        ["Standby Units", unitQuantity?.standby_units ?? "Enter Total IT Capacity"],
        ["Active units for selected scenario", activeUnits ?? "Enter Total IT Capacity"],
        ["Redundancy", unitQuantity?.redundancy || "Auto"],
        ...(directAccV2Disclosure ? [
            ["ACC V2 Direct Mode", "Configuration Library-driven ACC simulation using direct hourly Solver_Curve lookup."],
            ["Simulation Method", "True EPW × Solver_Curve"],
            ["Simulation Basis", "8760-hour Annual Dynamic Simulation"],
            ["Peak Design Condition", peakResults.peak_design_temperature_basis || "ASHRAE_20_year_extreme_annual_design_condition"],
            ["Peak Design Weather Station", peakResults.peak_design_weather_station || "Not available"],
            ["Peak Design Weather Station ID", peakResults.peak_design_weather_station_id || "Not available"],
            ["Peak Design Weather Station Distance", peakResults.peak_design_weather_station_distance_km != null ? `${fmtNumber(peakResults.peak_design_weather_station_distance_km, 1)} km` : "Not available"],
            ["ASHRAE Online Lookup Provider", peakDesignSourceLabel(peakResults.peak_design_lookup_provider || "ASHRAE_online")],
            ["ASHRAE Online Lookup Status", peakResults.peak_design_lookup_status || "Not available"],
            ["ASHRAE Online Status", peakResults.peak_design_online_status || "Not available"],
            ["ASHRAE Online Lookup Method", peakResults.peak_design_lookup_method || "Not available"],
            ["ASHRAE Online Lookup Endpoint", peakResults.peak_design_lookup_endpoint || "Not available"],
            ["ASHRAE Online Lookup Failed", peakResults.peak_design_lookup_failure_reason || "No"],
            ["ASHRAE Lookup Fallback", peakResults.peak_design_fallback_status || (peakResults.peak_design_weather_source === "ASHRAE_local_cache" ? "Using Local ASHRAE Cache fallback" : (peakResults.peak_design_weather_source === "manual" ? "Using Manual Override fallback" : "None"))],
            ["Peak Design Outdoor Dry Bulb", peakResults.peak_design_outdoor_dry_bulb_C != null ? `${fmtNumber(peakResults.peak_design_outdoor_dry_bulb_C, 1)} deg C` : "Not available"]
        ] : []),
        ["IT Load kW sample", itSample.length ? itSample.map(value => fmtNumber(value, 1)).join(", ") : "Enter Total IT Capacity"],
        ["Electrical IT / MEP efficiency", electricalPath
            ? `${fmtNumber(electricalPath.it_efficiency * 100, 2)}% / ${fmtNumber(electricalPath.mep_efficiency * 100, 2)}%` : "Missing"],
        ["IT Electrical Distribution Loss", resultValue(annualElectrical.annual_it_electrical_loss_kWh, value => `${fmtInteger(value)} kWh`)],
        ["MEP Electrical Distribution Loss", resultValue(annualElectrical.annual_mep_electrical_loss_kWh, value => `${fmtInteger(value)} kWh`)],
        ["Total Electrical Distribution Loss", resultValue(annualElectrical.annual_electrical_loss_kWh, value => `${fmtInteger(value)} kWh`)],
        ["CHW Pump Energy", resultValue(firstAvailableResultField(annualElectrical, ["annual_chw_pump_energy_kWh", "annual_pump_energy_kWh"]), value => `${fmtInteger(value)} kWh`)],
        ["CDU Energy", resultValue(annualElectrical.annual_cdu_energy_kWh, value => `${fmtInteger(value)} kWh`)],
        ["RTC Energy", resultValue(annualElectrical.annual_rtc_energy_kWh, value => `${fmtInteger(value)} kWh`)],
        ["MAU Energy", resultValue(annualElectrical.annual_mau_energy_kWh, value => `${fmtInteger(value)} kWh`)],
        ["White Space Equipment Energy", resultValue(whiteSpaceEnergy, value => `${fmtInteger(value)} kWh`)],
        ["ACC Energy", resultValue(firstAvailableResultField(annualElectrical, ["annual_acc_energy_kWh", "annual_ACC_energy_kWh"]), value => `${fmtInteger(value)} kWh`)],
        ["Average ACC COP", resultValue(annualElectrical.average_acc_cop, value => fmtNumber(value, 3))],
        ["Max ACC Power", resultValue(annualElectrical.max_acc_power_kW, value => `${fmtNumber(value, 1)} kW`)],
        ["ACC Curve Source", annualElectrical.acc_curve_source || "Not available"],
        ["Engine Output", resultValue(firstAvailableResultField(annualElectrical, ["annual_engine_energy_kWh", "annual_engine_output_kWh"]), value => `${fmtInteger(value)} kWh`)],
        ["Engine Fuel", resultValue(annualElectrical.annual_engine_fuel_input_kWh, value => `${fmtInteger(value)} kWh`)],
        ["Waste Heat", resultValue(annualElectrical.annual_engine_waste_heat_kWh, value => `${fmtInteger(value)} kWh`)],
        ["Average Engine Efficiency", resultValue(annualElectrical.average_engine_efficiency, value => `${fmtNumber(value * 100, 2)}%`)],
        ["Engine Radiator Energy", resultValue(annualElectrical.annual_engine_radiator_energy_kWh, value => `${fmtInteger(value)} kWh`)],
        ["Engine Radiator Max Power", resultValue(engineRadiatorMaxPower, value => `${fmtNumber(value, 1)} kW`)],
        ["Radiator Curve Source", annualElectrical.engine_radiator_curve_source || "Not available"]
    ];
    summary.style.display = "grid";
    const selectedScenario = document.getElementById("scenarioSelect")?.value === "one_failure_three_active" ? "Failure" : "Normal";
    const equipmentRows = DIRECT_MODE_EQUIPMENT_ORDER.map(equipmentId => {
        const resolved = findLibraryEquipmentPackage(data, equipmentId);
        const item = resolved.equipmentPackage || { equipment_id: resolved.resolvedId, status: "Missing", solver_curves: {} };
        const selected = selectLibrarySolverCurve(item, selectedScenario);
        const packageStatus = resolved.equipmentPackage ? "Found" : "Missing Workbook";
        const metadataFields = DIRECT_MODE_CURVE_METADATA_FIELDS[resolved.resolvedId] || {};
        const solverSource = metadataFields.source ? annualElectrical[metadataFields.source] : null;
        const solverCurveType = metadataFields.type ? annualElectrical[metadataFields.type] : null;
        const curveSheets = selected.electrical_path ? ["Solver (Electrical Path)"] : Object.keys(item.solver_curves || {});
        const sheetFoundDisplay = curveSheets.length ? curveSheets.join(", ") : (resolved.equipmentPackage ? "Unknown" : "None");
        const selectedDisplay = selected.electrical_path
            ? `<b>Electrical Path Found</b><br>IT Path Efficiency: ${fmtNumber(selected.electrical_path.it_efficiency * 100, 2)}%<br>MEP Path Efficiency: ${fmtNumber(selected.electrical_path.mep_efficiency * 100, 2)}%`
            : esc(selected.sheet_name || (resolved.equipmentPackage ? "Not evaluated" : "Missing Solver_Curve"));
        const sourceStatus = !resolved.equipmentPackage ? "Missing Workbook" : (["configuration_library_solver_curve", "acc_v2_solver_curve_direct"].includes(String(solverSource || "")) || selected.sheet_name || selected.electrical_path
            ? "Using Configuration Library Solver_Curve"
            : "Not evaluated");
        const curveType = displayCurveType(solverCurveType) || (selected.sheet_name || selected.electrical_path ? librarySelectedCurveType(selected) : (resolved.equipmentPackage ? "Unknown" : "Not available"));
        return `<tr>
            <td>${esc(resolved.resolvedId)}</td><td>${esc(packageStatus)}</td>
            <td>${esc(sheetFoundDisplay)}</td>
            <td>${selectedDisplay}</td><td>${esc(sourceStatus)}</td><td>${esc(curveType)}</td>
        </tr>`;
    }).join("");
    summary.innerHTML = values.map(([label, value]) =>
        `<div class="fileSlot"><div class="panelTitle">${esc(label)}</div><div>${esc(value)}</div></div>`
    ).join("") + `<div class="fileSlot" style="grid-column:1/-1; overflow-x:auto;">
        <div class="panelTitle">Equipment Package Auto Binding — ${esc(selectedScenario)}</div>
        <table style="width:100%; min-width:720px;"><thead><tr>
            <th>Equipment ID</th><th>Package Status</th><th>Solver_Curve Sheet Found</th><th>Selected Curve</th><th>Source Status</th><th>Curve Type</th>
        </tr></thead><tbody>${equipmentRows}</tbody></table>
    </div>`;
}

async function loadSelectedConfigurationLibrary() {
    const select = document.getElementById("configurationLibrarySelect");
    const status = document.getElementById("configurationLibraryStatus");
    const button = document.getElementById("btnLoadConfigurationLibrary");
    const configurationName = select?.value || "ACC_1.5MW_GASENGINE_CDU";
    if (status) status.textContent = `Loading ${configurationName}...`;
    if (button) button.disabled = true;
    try {
        await loadConfigurationEquipmentAliases();
        const base = encodeURIComponent(configurationName);
        const configurationSheets = await fetchConfigurationWorkbook(`${base}/configuration.xlsx`);
        const equipmentPerUnit = (configurationSheets.Equipment_List || []).map(row => ({
            equipment_id: String(row.Equipment || ""),
            per_cooling_unit: Number(row["Per Cooling Unit"] || 0)
        }));
        const equipmentRequests = equipmentPerUnit.map(async ({ equipment_id: equipmentId }) => {
            const resolvedId = resolveFrontendEquipmentId(equipmentId);
            const packagePath = `equipment/${resolvedId}/${resolvedId}.xlsx`;
            try {
                const fetched = await fetchResolvedConfigurationEquipmentWorkbook(base, equipmentId);
                const sheets = fetched.sheets;
                const curveNames = ["Solver_Curve", "Solver_Curve_Normal", "Solver_Curve_Failure"].filter(name => sheets[name]);
                const information = librarySheetKeyValues(sheets.Information);
                const metadata = librarySheetKeyValues(sheets.Metadata);
                const validation = librarySheetKeyValues(sheets.Validation);
                const equipmentType = information["Equipment Type"] || metadata.equipment_type || null;
                const isElectricalPath = resolvedId.startsWith("ELECTRICAL_DISTRIBUTION") || String(equipmentType || "").toLowerCase() === "electrical distribution";
                let electricalPath = null;
                if (isElectricalPath) {
                    const efficiencies = Object.fromEntries((sheets.Solver || []).map(row => [String(row.Path || "").toUpperCase(), Number(row.overall_efficiency)]));
                    electricalPath = {
                        it_efficiency: Number.isFinite(efficiencies.IT) ? efficiencies.IT : null,
                        mep_efficiency: Number.isFinite(efficiencies.MEP) ? efficiencies.MEP : null
                    };
                }
                const electricalPathFound = electricalPath && electricalPath.it_efficiency !== null && electricalPath.mep_efficiency !== null;
                return [fetched.resolvedId, {
                    equipment_id: fetched.resolvedId,
                    source_equipment_id: fetched.rawEquipmentId,
                    source_workbook_equipment_id: fetched.sourceEquipmentId,
                    equipment_type: equipmentType,
                    package_path: fetched.packagePath,
                    status: electricalPathFound ? "Electrical Path Found" : "Found",
                    available_sheets: Object.keys(sheets),
                    solver_curves: Object.fromEntries(curveNames.map(name => [name, sheets[name]])),
                    performance_map: sheets.Performance_Map || [],
                    electrical_path: electricalPath,
                    validation_status: validation["Validation Status"] || validation.Status || "Available"
                }];
            } catch (_) {
                return [resolvedId, {
                    equipment_id: resolvedId, source_equipment_id: equipmentId, equipment_type: null, package_path: packagePath,
                    status: "Missing", available_sheets: [], solver_curves: {}, performance_map: [], electrical_path: null,
                    validation_status: "Missing equipment package"
                }];
            }
        });
        const [scenarioSheets, itSheets, equipmentEntries] = await Promise.all([
            fetchConfigurationWorkbook(`${base}/scenario.xlsx`),
            fetchConfigurationWorkbook(`${base}/input/IT_LOAD_90_PERCENT.xlsx`),
            Promise.all(equipmentRequests)
        ]);
        const parameters = configurationKeyValues(configurationSheets.Configuration);
        const scenarios = (scenarioSheets.Scenario || []).map(row => ({
            scenario: row.Scenario,
            running_unit_formula: row["Running Unit Formula"],
            description: row.Description
        }));
        const percentages = (itSheets.IT_Load || []).map(row => Number(row.hourly_it_load_percent)).filter(Number.isFinite);
        const ratios = (itSheets.IT_Load || []).map(row => Number(row.hourly_it_load_ratio)).filter(Number.isFinite);
        const itLoad = {
            schema_version: "pue.timeseries.it_load.v1",
            type: "annual_it_load",
            source_file: "input/IT_LOAD_90_PERCENT.xlsx",
            units: { hourly_it_load_percent: "%", hourly_it_load_ratio: "fraction" },
            data: { hourly_it_load_percent: percentages, "hourly_it_load_%": percentages, hourly_it_load_ratio: ratios },
            hours: percentages.length
        };
        if (projectDesignCapacityKw() > 0) normalizeItLoadPercentFile(itLoad);
        standardDataFiles.itLoad = itLoad;
        standardSolverInput = null;
        preferStandardFiles = true;
        configurationLibraryData = {
            configuration_name: parameters["Configuration Name"] || configurationName,
            cooling_system_type: parameters["Cooling System Type"],
            cooling_unit_capacity_mw: Number(parameters["Cooling Unit Capacity"]),
            power_source: parameters["Power Source"],
            equipment_per_cooling_unit: equipmentPerUnit,
            equipment_count: equipmentEntries.length,
            scenarios,
            it_load: { hours: percentages.length, hourly_it_load_percent: percentages, hourly_it_load_ratio: ratios },
            equipment: Object.fromEntries(equipmentEntries)
        };
        const librarySizing = calculateFrontendUnitRequirements(
            getProjectReportInfo().capacityMw, configurationLibraryData.cooling_unit_capacity_mw
        );
        configurationLibraryData.library_bound_input = {
            configuration: {
                configuration_name: configurationLibraryData.configuration_name,
                cooling_system_type: configurationLibraryData.cooling_system_type,
                cooling_unit_capacity_mw: configurationLibraryData.cooling_unit_capacity_mw,
                power_source: configurationLibraryData.power_source,
                equipment_per_cooling_unit: equipmentPerUnit
            },
            unit_counts: librarySizing || {
                requiredUnits: null, installedUnits: null, normalActiveUnits: null,
                failureActiveUnits: null, redundancy: "N+1"
            },
            unit_quantity: getUnitQuantitySelection(librarySizing),
            scenarios,
            equipment_packages: configurationLibraryData.equipment,
            selected_curves: Object.fromEntries(scenarios.map(scenario => [
                scenario.scenario,
                Object.fromEntries(DIRECT_MODE_EQUIPMENT_ORDER.map(equipmentId => {
                    const resolved = findLibraryEquipmentPackage(configurationLibraryData, equipmentId);
                    return [resolved.resolvedId, selectLibrarySolverCurve(resolved.equipmentPackage, scenario.scenario)];
                }))
            ])),
            it_load_profile: configurationLibraryData.it_load
        };
        configurationLibraryData.standardized_solver_input = buildFrontendSolverInputFromLibrary(configurationLibraryData);
        window.configurationLibraryData = configurationLibraryData;

        const typeSelect = document.getElementById("coolingSystemType");
        if (typeSelect && COOLING_SYSTEM_CONFIG[configurationLibraryData.cooling_system_type]) {
            typeSelect.value = configurationLibraryData.cooling_system_type;
            updateCoolingUnitCapacityOptions(configurationLibraryData.cooling_unit_capacity_mw);
        }
        const powerSelect = document.getElementById("powerSource");
        if (powerSelect) powerSelect.value = configurationLibraryData.power_source;
        renderCoolingSystemSelection();
        renderConfigurationLibrarySummary(configurationLibraryData);
        renderFrameworkDiagnosticsPanel();
        updateFileStatus("statusItLoad", `Configuration Library: IT_LOAD_90_PERCENT.xlsx (${percentages.length} hours)`, "ok");
        refreshStandardInputStatus();
        if (status) {
            status.textContent = projectDesignCapacityKw() > 0
                ? `Loaded ${configurationLibraryData.configuration_name}. Manual uploads remain available as overrides.`
                : `Loaded ${configurationLibraryData.configuration_name}. Enter Total IT Capacity to convert IT load percent to kW.`;
            status.style.color = "#059669";
        }
        const runLibraryButton = document.getElementById("btnRunConfigurationLibrary");
        if (runLibraryButton) runLibraryButton.disabled = false;
    } catch (error) {
        if (status) {
            status.textContent = `Configuration Library load failed: ${String(error.message || error)}`;
            status.style.color = "#dc2626";
        }
    } finally {
        if (button) button.disabled = false;
    }
}

function initStandardDataInputs() {
    initCoolingSystemSelection();
    const libraryButton = document.getElementById("btnLoadConfigurationLibrary");
    if (libraryButton) libraryButton.addEventListener("click", loadSelectedConfigurationLibrary);
    const librarySelect = document.getElementById("configurationLibrarySelect");
    if (librarySelect) librarySelect.addEventListener("change", renderFrameworkDiagnosticsPanel);
    const runLibraryButton = document.getElementById("btnRunConfigurationLibrary");
    if (runLibraryButton) runLibraryButton.addEventListener("click", runUsingConfigurationLibrary);
    ["unitQuantityMode", "unitRedundancyMode", "manualInstalledUnits", "manualRunningUnits", "manualStandbyUnits"].forEach((id) => {
        const input = document.getElementById(id);
        if (!input) return;
        input.addEventListener("input", () => {
            if (configurationLibraryData) {
                configurationLibraryData.standardized_solver_input = buildFrontendSolverInputFromLibrary(configurationLibraryData);
                renderConfigurationLibrarySummary(configurationLibraryData);
            } else {
                renderUnitQuantityStatus(getUnitQuantitySelection(null));
            }
        });
        input.addEventListener("change", () => {
            if (configurationLibraryData) {
                configurationLibraryData.standardized_solver_input = buildFrontendSolverInputFromLibrary(configurationLibraryData);
                renderConfigurationLibrarySummary(configurationLibraryData);
            }
        });
    });
    const bindings = [
        ["fileItLoad", "itLoad", "statusItLoad"],
        ["fileWeather", "weather", "statusWeather"],
        ["fileDryCooler", "dryCooler", "statusDryCooler"],
        ["fileChiller", "chiller", "statusChiller"],
        ["fileElectrical", "electrical", "statusElectrical"],
        ["filePumps", "pumps", "statusPumps"],
        ["fileFans", "fans", "statusFans"]
    ];
    bindings.forEach(([inputId, slot, statusId]) => {
        const input = document.getElementById(inputId);
        if (!input) return;
        input.addEventListener("change", () => {
            const file = input.files && input.files[0];
            if (file) handleStandardFile(slot, statusId, file);
        });
    });
    const demoBtn = document.getElementById("btnLoadDemoData");
    if (demoBtn) demoBtn.addEventListener("click", loadDemoStandardData);
    const buildBtn = document.getElementById("btnBuildFromFiles");
    if (buildBtn) buildBtn.addEventListener("click", buildStandardSolverInputToTextarea);
    const autoEpwBtn = document.getElementById("btnAutoMatchEpw");
    if (autoEpwBtn) autoEpwBtn.addEventListener("click", autoMatchLocalEpw);
    const auxInput = document.getElementById("auxFixedCoeff");
    if (auxInput) auxInput.addEventListener("input", () => {
        updateFileStatus("statusAuxFixed", `当前系数 ${auxInput.value || 0}`, "ok");
        previewInputCurves(standardDataFiles);
        standardSolverInput = null;
        refreshStandardInputStatus();
    });
    const dryApproachInput = document.getElementById("dryCoolerApproachC");
    if (dryApproachInput) dryApproachInput.addEventListener("input", () => {
        previewInputCurves(standardDataFiles);
        standardSolverInput = null;
        refreshStandardInputStatus();
    });
    ["solarHeatGainMaxKw", "solarDaytimeStartHour", "solarDaytimeEndHour", "otherAuxiliaryHeatGainKw", "otherElectricalAuxiliaryPowerKw"].forEach((id) => {
        const input = document.getElementById(id);
        if (!input) return;
        input.addEventListener("input", () => {
            updateSolarGainStatus();
            renderSolarGainReportPanel();
        });
    });
    ["peakDesignWeatherAuto", "peakDesignWeatherManual", "manualPeakDesignDryBulbC"].forEach((id) => {
        const input = document.getElementById(id);
        if (!input) return;
        ["input", "change"].forEach(eventName => input.addEventListener(eventName, () => {
            updatePeakDesignWeatherStatus();
            if (configurationLibraryData) {
                configurationLibraryData.standardized_solver_input = buildFrontendSolverInputFromLibrary(configurationLibraryData);
                renderConfigurationLibrarySummary(configurationLibraryData);
            }
        }));
    });
    ["projectNameInput", "projectLocationInput", "projectLatitudeInput", "projectLongitudeInput", "projectCapacityMwInput", "projectStageInput", "projectVersionInput"].forEach((id) => {
        const input = document.getElementById(id);
        if (!input) return;
        input.addEventListener("input", () => {
            updateProjectInfoStatus();
            renderProjectInfoReportPanel();
            if (id === "projectCapacityMwInput" && configurationLibraryData) {
                try {
                    normalizeItLoadPercentFile(standardDataFiles.itLoad);
                    if (configurationLibraryData.library_bound_input) {
                        const updatedSizing = calculateFrontendUnitRequirements(
                            getProjectReportInfo().capacityMw,
                            configurationLibraryData.cooling_unit_capacity_mw
                        );
                        configurationLibraryData.library_bound_input.unit_counts = updatedSizing;
                        configurationLibraryData.library_bound_input.unit_quantity = getUnitQuantitySelection(updatedSizing);
                    }
                    configurationLibraryData.standardized_solver_input = buildFrontendSolverInputFromLibrary(configurationLibraryData);
                    standardSolverInput = null;
                    refreshStandardInputStatus();
                    renderConfigurationLibrarySummary(configurationLibraryData);
                    renderScenarioSummary();
                } catch (_) {
                    // Capacity is incomplete while the user is still typing.
                }
            }
        });
    });
    [
        ["filePdfDryCooler", "Dry Cooler"],
        ["filePdfChiller", "Chiller COP Surface"],
        ["filePdfElectrical", "Electrical"],
        ["filePdfPump", "Pumps"]
    ].forEach(([inputId, category]) => {
        const input = document.getElementById(inputId);
        if (!input) return;
        input.addEventListener("change", () => handleEquipmentPdfFiles(input.files, category));
    });
    const saveMemoryBtn = document.getElementById("btnSaveProjectMemory");
    if (saveMemoryBtn) saveMemoryBtn.addEventListener("click", saveProjectMemory);
    const loadMemoryBtn = document.getElementById("btnLoadProjectMemory");
    if (loadMemoryBtn) loadMemoryBtn.addEventListener("click", () => restoreProjectMemory());
    const deleteMemoryBtn = document.getElementById("btnDeleteProjectMemory");
    if (deleteMemoryBtn) deleteMemoryBtn.addEventListener("click", deleteProjectMemory);
    updateProjectMemorySelect();
    updateProjectInfoStatus();
    updateSolarGainStatus();
    updatePeakDesignWeatherStatus();
    refreshStandardInputStatus();
}

function showProjectVisualization(outObj) {
    if (typeof Chart === "undefined") {
        log(chartUnavailableMessage());
    }

    const hourly = Array.isArray(outObj.hourly_results) ? outObj.hourly_results : [];
    const annual = outObj.annual_results || {};
    const peak = outObj.peak_results || {};

    const vis = document.getElementById("resultsVisualization");
    const msg = document.getElementById("noResultsMessage");
    if (vis) vis.style.display = "block";
    if (msg) msg.style.display = "none";
    const principle = document.getElementById("calculationPrinciple");
    if (principle) {
        const accEngineUsed = getAccEngineUsedLabel(outObj);
        const isDirectAccV2 = isConfigurationLibraryAccV2DirectResult(outObj);
        const accDisclosure = isDirectAccV2
            ? `<div style="margin:6px 0;">ACC V2 Direct Mode: Configuration Library-driven ACC simulation using direct hourly Solver_Curve lookup.</div>` +
              `<div style="margin:6px 0;">Simulation Method: True EPW × Solver_Curve</div>` +
              `<div style="margin:6px 0 8px 0;">Simulation Basis: 8760-hour Annual Dynamic Simulation</div>`
            : "";
        const peakDisclosure = isDirectAccV2
            ? `<div style="margin:6px 0 8px 0;">Peak PUE Basis: Peak Design PUE at ASHRAE 20-year Extreme Annual Design Condition, 100% design IT load, maximum solar heat gain, and configured other heat gain.</div>`
            : "";
        principle.innerHTML =
            "<b>计算原理</b><br>" +
            `<div style="margin:6px 0 8px 0;">ACC Engine Used: ${esc(accEngineUsed)}</div>` +
            accDisclosure +
            peakDisclosure +
            "全年模式调用 <code>compute_pue_project(dc)</code>。每小时读取 <code>project.it_load.hourly_it_load_kW</code> 与 <code>weather.hourly_data.dry_bulb_C</code>，" +
            "由电气效率曲线估算 UPS/变压器损耗，由 <code>chiller_COP_H_vs_load</code> COP 曲面估算冷水机功率，并按小时计算 " +
            "<code>PUE = total_facility_power_kW / IT_load_kW</code>。年度 PUE 使用全年设施能耗除以全年 IT 能耗。";
    }

    setText("summaryPueLabel", "年度平均 PUE");
    setText("summaryItLabel", "IT 年能耗 (kWh)");
    setText("summaryFacilityLabel", "设施总能耗 (kWh)");
    const isDirectAccV2Summary = isConfigurationLibraryAccV2DirectResult(outObj);
    const peakDesignDemandKw = peak.peak_design_facility_electrical_demand_kW ?? peak.peak_design_total_facility_power_kW ?? peak.peak_total_facility_power_kW;
    const maxHourlyDemandKw = peak.max_hourly_facility_electrical_demand_kW ?? peak.max_hourly_total_facility_power_kW;
    setText("summaryPeakLabel", isDirectAccV2Summary ? "峰值设计设施电气需求 (kW)" : "峰值设施功率 (kW)");
    setText("annualPueValue", fmtNumber(annual.annual_average_PUE, 3));
    setText("annualItEnergy", fmtInteger(annual.annual_IT_energy_kWh));
    setText("annualFacilityEnergy", fmtInteger(annual.annual_facility_energy_kWh));
    setText("peakFacilityPower", `${fmtInteger(isDirectAccV2Summary ? peakDesignDemandKw : peak.peak_total_facility_power_kW)} kW`);
    renderProjectInfoReportPanel();
    renderSolarGainReportPanel();
    renderWeatherReportPanel();
    renderTemperatureDistributionPanel();
    renderPueContributionSummaryPanel(annual);
    renderCoolingUnitArchitecturePanel(outObj);

    const sampled = decimateHourlyRows(hourly);
    const labels = sampled.map((row, index) => {
        const h = pickHourlyValue(row, ["hour_index", "hour"]);
        return h === null ? index : h;
    });

    createChart("pueTimeSeriesChart", {
        type: "line",
        data: {
            labels,
            datasets: [
                {
                    label: "Hourly PUE",
                    data: sampled.map(row => pickHourlyValue(row, ["hourly_PUE", "pue", "PUE"])),
                    borderColor: "#2563eb",
                    backgroundColor: "rgba(37, 99, 235, 0.12)",
                    pointRadius: 0,
                    borderWidth: 1.8,
                    tension: 0.18,
                    fill: true
                },
                {
                    label: "Peak facility hour",
                    data: sampled.map(row => {
                        const hour = pickHourlyValue(row, ["hour_index", "hour"]);
                        return hour === peak.peak_hour_index ? pickHourlyValue(row, ["hourly_PUE", "pue", "PUE"]) : null;
                    }),
                    borderColor: "#dc2626",
                    backgroundColor: "#dc2626",
                    pointRadius: 5,
                    showLine: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { position: "bottom" },
                tooltip: { callbacks: { title: items => `Hour ${items[0].label}` } }
            },
            scales: {
                x: { title: { display: true, text: "Hour of year" }, ticks: { maxTicksLimit: 12 } },
                y: { title: { display: true, text: "PUE" }, beginAtZero: false }
            }
        }
    });

    const energyBreakdown = [
        ["IT Energy", annual.annual_IT_energy_kWh, "#059669"],
        [annual.annual_acc_energy_kWh > 0 ? "ACC Energy" : "Chiller Energy", annual.annual_acc_energy_kWh || annual.annual_chiller_energy_kWh || annual.annual_cooling_energy_kWh, "#2563eb"],
        ["Dry Cooler Energy", annual.annual_dry_cooler_energy_kWh, "#14b8a6"],
        ["Pump Energy", annual.annual_pump_energy_kWh || 0, "#8b5cf6"],
        ["MAU Energy", annual.annual_terminal_fan_energy_kWh, "#0f766e"],
        ["White Space Equipment Energy", annual.annual_white_space_equipment_energy_kWh, "#ec4899"],
        ["Electrical Distribution Loss", annual.annual_electrical_loss_kWh, "#f59e0b"],
        ["Other Electrical Auxiliary Energy", annual.annual_auxiliary_energy_kWh, "#7c3aed"]
    ].filter(([, value]) => Number(value) > 0);

    createChart("energyBreakdownChart", {
        type: "pie",
        data: {
            labels: energyBreakdown.map(([label]) => label),
            datasets: [{
                data: energyBreakdown.map(([, value]) => value),
                backgroundColor: energyBreakdown.map(([, , color]) => color),
                borderColor: "#ffffff",
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: "bottom" },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.label}: ${fmtInteger(ctx.raw)} kWh`
                    }
                }
            }
        }
    });

    const peakRows = [...hourly]
        .filter(row => pickHourlyValue(row, ["total_facility_power_kW", "facility_power_kW"]) !== null)
        .sort((a, b) =>
            pickHourlyValue(b, ["total_facility_power_kW", "facility_power_kW"]) -
            pickHourlyValue(a, ["total_facility_power_kW", "facility_power_kW"])
        )
        .slice(0, 10);

    createChart("peakAnalysisChart", {
        type: "bar",
        data: {
            labels: peakRows.map(row => `Hour ${pickHourlyValue(row, ["hour_index", "hour"])}`),
            datasets: [
                {
                    label: "Facility Power (kW)",
                    data: peakRows.map(row => pickHourlyValue(row, ["total_facility_power_kW", "facility_power_kW"])),
                    backgroundColor: "#2563eb",
                    borderRadius: 6,
                    yAxisID: "y"
                },
                {
                    label: "PUE",
                    data: peakRows.map(row => pickHourlyValue(row, ["hourly_PUE", "pue", "PUE"])),
                    type: "line",
                    borderColor: "#dc2626",
                    backgroundColor: "#dc2626",
                    pointRadius: 4,
                    tension: 0.2,
                    yAxisID: "y1"
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: { legend: { position: "bottom" } },
            scales: {
                x: { title: { display: true, text: "Top peak hours" } },
                y: { title: { display: true, text: "Facility Power (kW)" }, beginAtZero: false },
                y1: {
                    position: "right",
                    title: { display: true, text: "PUE" },
                    grid: { drawOnChartArea: false }
                }
            }
        }
    });

    createChart("powerVsLoadChart", {
        type: "scatter",
        data: {
            datasets: [{
                label: "Facility power vs IT load",
                data: sampled.map(row => ({
                    x: pickHourlyValue(row, ["IT_load_kW", "it_load_kW"]),
                    y: pickHourlyValue(row, ["total_facility_power_kW", "facility_power_kW"])
                })),
                backgroundColor: "rgba(37, 99, 235, 0.45)",
                pointRadius: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: "bottom" } },
            scales: {
                x: { title: { display: true, text: "IT Load (kW)" } },
                y: { title: { display: true, text: "Facility Power (kW)" } }
            }
        }
    });

    createChart("tempVsPueChart", {
        type: "scatter",
        data: {
            datasets: [{
                label: "Outdoor temperature vs PUE",
                data: sampled.map(row => ({
                    x: pickHourlyValue(row, ["dry_bulb_C", "outdoor_temp_C"]),
                    y: pickHourlyValue(row, ["hourly_PUE", "pue", "PUE"])
                })),
                backgroundColor: "rgba(220, 38, 38, 0.45)",
                pointRadius: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: "bottom" } },
            scales: {
                x: { title: { display: true, text: "Outdoor Dry Bulb (deg C)" } },
                y: { title: { display: true, text: "PUE" }, beginAtZero: false }
            }
        }
    });

    const peakDetails = document.getElementById("peakHourDetails");
    if (peakDetails) {
        const isDirectAccV2 = isConfigurationLibraryAccV2DirectResult(outObj);
        const cards = [
            ...(isDirectAccV2 ? [
                ["Peak Design Condition", peak.peak_design_temperature_basis || "ASHRAE_20_year_extreme_annual_design_condition"],
                ["ASHRAE Weather Station", peak.peak_design_weather_station || "N/A"],
                ["Station Distance", peak.peak_design_weather_station_distance_km != null ? `${fmtNumber(peak.peak_design_weather_station_distance_km, 1)} km` : "N/A"],
                ["Design Temperature Source", "ASHRAE 20-year Extreme Annual DB Max"]
            ] : [["Peak Facility Hour", peak.peak_hour_index]]),
            [isDirectAccV2 ? "Max Hourly PUE Hour" : "Max PUE Hour", peak.max_hourly_PUE_hour_index ?? peak.peak_PUE_hour_index],
            [isDirectAccV2 ? "Peak Design PUE" : "Peak PUE", fmtNumber(peak.peak_PUE, 3)],
            ...(isDirectAccV2 ? [["Max Hourly PUE", fmtNumber(peak.max_hourly_PUE, 3)]] : []),
            ...(isDirectAccV2 ? [
                ["Peak Design Facility Electrical Demand", `${fmtInteger(peakDesignDemandKw)} kW`],
                ["Max Hourly Facility Electrical Demand", `${fmtInteger(maxHourlyDemandKw)} kW`]
            ] : []),
            [isDirectAccV2 ? "Outdoor Dry Bulb" : "Dry Bulb", `${fmtNumber(peak.peak_outdoor_dry_bulb_C, 1)} deg C`],
            ["Wet Bulb", `${fmtNumber(peak.peak_outdoor_wet_bulb_C, 1)} deg C`],
            ["IT Load", `${fmtInteger(peak.peak_IT_load_kW)} kW`],
            ...(isDirectAccV2 ? [] : [["Facility Power", `${fmtInteger(peak.peak_total_facility_power_kW)} kW`]])
        ];
        peakDetails.innerHTML = cards.map(([label, value]) => `
            <div style="border:1px solid #e5e7eb; border-radius:8px; padding:10px; background:#fafafa;">
                <div class="muted" style="font-size:12px;">${label}</div>
                <div style="font-weight:700; margin-top:4px;">${value === undefined || value === null ? "-" : value}</div>
            </div>
        `).join("");
    }
}

function showSinglePointVisualization(outObj) {
    if (typeof Chart === "undefined") {
        log(chartUnavailableMessage());
    }

    const power = outObj.power || {};
    const breakdown = outObj._breakdown_v04 || {};
    const pue = power.pue_instant;
    const itKw = power.total_it_power_kw;
    const facilityKw = power.total_facility_power_kw;
    const coolingKw = breakdown.cooling_kw || 0;
    const powerLossKw = breakdown.power_distribution_loss_kw || 0;
    const airflowKw = breakdown.airflow_kw || 0;
    const auxKw = breakdown.aux_kw || 0;
    const otherKw = breakdown.other_kw || 0;

    const vis = document.getElementById("resultsVisualization");
    const msg = document.getElementById("noResultsMessage");
    if (vis) vis.style.display = "block";
    if (msg) msg.style.display = "none";
    const principle = document.getElementById("calculationPrinciple");
    if (principle) {
        principle.innerHTML =
            "<b>计算原理</b><br>" +
            "单点模式调用 <code>compute_pue_v04(dc)</code>。当前输入没有被识别为 solver.py 的全年项目输入，因此只计算当前 IT 功率和室外温度对应的瞬时 PUE。";
    }

    setText("summaryPueLabel", "瞬时 PUE");
    setText("summaryItLabel", "IT 功率 (kW)");
    setText("summaryFacilityLabel", "设施总功率 (kW)");
    setText("summaryPeakLabel", "当前室外温度");
    setText("annualPueValue", fmtNumber(pue, 3));
    setText("annualItEnergy", fmtNumber(itKw, 1));
    setText("annualFacilityEnergy", fmtNumber(facilityKw, 1));
    setText("peakFacilityPower", `${fmtNumber(breakdown.oat_c, 1)} deg C`);
    renderProjectInfoReportPanel();
    renderSolarGainReportPanel();
    renderWeatherReportPanel();
    renderTemperatureDistributionPanel();
    renderPueContributionSummaryPanel(null);
    renderCoolingUnitArchitecturePanel(null);

    const onePoint = [{
        hour_index: "Current",
        hourly_PUE: pue,
        IT_load_kW: itKw,
        total_facility_power_kW: facilityKw,
        dry_bulb_C: breakdown.oat_c
    }];

    createChart("pueTimeSeriesChart", {
        type: "bar",
        data: {
            labels: ["Current"],
            datasets: [{
                label: "Instant PUE",
                data: [pue],
                backgroundColor: "#2563eb",
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: "bottom" } },
            scales: { y: { title: { display: true, text: "PUE" }, beginAtZero: false } }
        }
    });

    const energyBreakdown = [
        ["IT Power", itKw, "#059669"],
        ["Cooling", coolingKw, "#2563eb"],
        ["Electrical Distribution Loss", powerLossKw, "#f59e0b"],
        ["Airflow", airflowKw, "#dc2626"],
        ["Auxiliary", auxKw, "#7c3aed"],
        ["Other", otherKw, "#6b7280"]
    ].filter(([, value]) => Number(value) > 0);

    createChart("energyBreakdownChart", {
        type: "pie",
        data: {
            labels: energyBreakdown.map(([label]) => label),
            datasets: [{
                data: energyBreakdown.map(([, value]) => value),
                backgroundColor: energyBreakdown.map(([, , color]) => color),
                borderColor: "#ffffff",
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: "bottom" },
                tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${fmtNumber(ctx.raw, 1)} kW` } }
            }
        }
    });

    createChart("peakAnalysisChart", {
        type: "bar",
        data: {
            labels: ["IT", "Cooling", "Power Loss", "Airflow", "Aux", "Other"],
            datasets: [{
                label: "Power Component (kW)",
                data: [itKw, coolingKw, powerLossKw, airflowKw, auxKw, otherKw],
                backgroundColor: ["#059669", "#2563eb", "#f59e0b", "#dc2626", "#7c3aed", "#6b7280"],
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: "bottom" } },
            scales: { y: { title: { display: true, text: "kW" }, beginAtZero: true } }
        }
    });

    createChart("powerVsLoadChart", {
        type: "scatter",
        data: {
            datasets: [{
                label: "Facility power vs IT load",
                data: onePoint.map(row => ({ x: row.IT_load_kW, y: row.total_facility_power_kW })),
                backgroundColor: "rgba(37, 99, 235, 0.75)",
                pointRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: "bottom" } },
            scales: {
                x: { title: { display: true, text: "IT Load (kW)" } },
                y: { title: { display: true, text: "Facility Power (kW)" } }
            }
        }
    });

    createChart("tempVsPueChart", {
        type: "scatter",
        data: {
            datasets: [{
                label: "Outdoor temperature vs PUE",
                data: onePoint.map(row => ({ x: row.dry_bulb_C, y: row.hourly_PUE })),
                backgroundColor: "rgba(220, 38, 38, 0.75)",
                pointRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: "bottom" } },
            scales: {
                x: { title: { display: true, text: "Outdoor Dry Bulb (deg C)" } },
                y: { title: { display: true, text: "PUE" }, beginAtZero: false }
            }
        }
    });

    const peakDetails = document.getElementById("peakHourDetails");
    if (peakDetails) {
        const cards = [
            ["Mode", "Single point"],
            ["PUE", fmtNumber(pue, 3)],
            ["IT Power", `${fmtNumber(itKw, 1)} kW`],
            ["Facility Power", `${fmtNumber(facilityKw, 1)} kW`],
            ["Cooling", `${fmtNumber(coolingKw, 1)} kW`],
            ["Power Loss", `${fmtNumber(powerLossKw, 1)} kW`]
        ];
        peakDetails.innerHTML = cards.map(([label, value]) => `
            <div style="border:1px solid #e5e7eb; border-radius:8px; padding:10px; background:#fafafa;">
                <div class="muted" style="font-size:12px;">${label}</div>
                <div style="font-weight:700; margin-top:4px;">${value === undefined || value === null ? "-" : value}</div>
            </div>
        `).join("");
    }
}

const defaultJson = {
    site: {
        site_id: "OH-DC-01",
        site_name: "Ohio Demo DC"
    },

    measurement_timestamp: "2025-12-22T12:00:00Z",

    environmental_conditions: {
        outdoor_temp_c: 30,
        water_consumption_m3: 0,
        carbon_emission_kgco2e: 0
    },

    modules: [
        { module_id: "M1", it_load_kw: 800 },
        { module_id: "M2", it_load_kw: 600 }
    ],

    cooling: {
        it_heat_split: {
            liquid_cooling_it_kw: 900,
            air_cooling_it_kw: 500
        },

        heat_sources: {
            pumps_kw: null,
            airflow_kw: null,
            lighting_kw: null,
            people_kw: 0,
            infiltration_kw: 0,
            envelope_kw: 0,
            misc_kw: 0
        },

        chiller_share_by: "capacity"
    },

    ups: [
        {
            ups_id: "UPS-1",
            rated_capacity_kw: 2000,
            output_power_kw: null,
            efficiency_curve_ref: "UPS_EFF_1"
        }
    ],

    chillers: [
        {
            chiller_id: "CH-1",
            capacity_kw: 1500,
            cop_curve_ref: "CH_COP_SURF_1"
        },
        {
            chiller_id: "CH-2",
            capacity_kw: 1000,
            cop_curve_ref: "CH_COP_SURF_1"
        }
    ],

    pumps: [
        {
            pump_id: "P-CHW-1",
            control_mode: "vfd",
            rated_power_kw: 35,
            speed_ratio: 0.9
        },
        {
            pump_id: "P-CW-1",
            control_mode: "vfd",
            rated_power_kw: 25,
            speed_ratio: 0.9
        }
    ],

    airflow: [
        {
            unit_id: "FW-1",
            control_mode: "vfd",
            rated_power_kw: 18,
            speed_ratio: 0.85
        }
    ],

    control: {
        bms_power_kw: 2,
        lighting_power_kw: 6
    },

    heat_recovery: {
        enabled: false,
        exported_heat_kw: 0,
        recovered_heat_kw: 0
    },

    power: {
        total_it_power_kw: null,
        total_facility_power_kw: null,
        pue_instant: null
    }
};

elIn.value = pretty(defaultJson);
elOut.value = "";

async function init() {
    try {
        elStatus.textContent = "Page ready. Calculation engine will load when you click Run.";
        window.pyodideReady = false;

        try {
            window.curveLib = await fetch("./curves.json").then(r => r.json());
        } catch (e) {
            console.warn("curves.json 加载失败，使用空库：", e);
            window.curveLib = { curves_1d: {}, cop_surfaces: {} };
        }

        elStatus.textContent = "Page ready. Calculation engine will load when you click Run.";
        btnRun.disabled = false;

        if (window.initCurveEditors) window.initCurveEditors();
        initStandardDataInputs();

        log(
            "✅ 初始化完成（v0.4.1 heat sources）\n" +
            "当前运行逻辑：\n" +
            "- UPS：按 efficiency_curve_ref 查 curves.json 的 curves_1d\n" +
            "- Chiller：按 cop_curve_ref 查 curves.json 的 cop_surfaces\n" +
            "- Cooling load：按 IT liquid/air + heat_sources 汇总\n\n" +
            "下一步：点击 Run\n\n" +
            "提示：你可以直接编辑 curves.json / solver.py / ui.js，保存后刷新生效。"
        );
    } catch (e) {
        console.error(e);
        elStatus.textContent = "初始化失败（看 Log/Console）";
        log("❌ 初始化失败：\n" + String(e));
    }
}

async function run(options = {}) {
    if (runInProgress) return;
    runInProgress = true;
    setRunButtonsDisabled(true);
    clearRuntimeErrorDetails();

    try {
        const coolingSelection = getCoolingSystemSelection();
        const libraryRun = options && options.libraryRun === true;
        const requestedSolverFn = options && options.solverFn;
        const providedLibraryInput = libraryRun ? options.libraryInput : null;
        if (!libraryRun && coolingSelection.powerSource !== DEFAULT_POWER_SOURCE) {
            lastReportContext = null;
            if (btnExportHtmlReport) btnExportHtmlReport.disabled = true;
            if (btnExportJson) btnExportJson.disabled = true;
            elOut.value = pretty({
                error: POWER_SOURCE_MODEL_UNAVAILABLE_MESSAGE,
                cooling_system_type: coolingSelection.type,
                cooling_unit_capacity_mw: coolingSelection.capacityMw,
                power_source: coolingSelection.powerSource
            });
            setSolverDataStatus(POWER_SOURCE_MODEL_UNAVAILABLE_MESSAGE, "error");
            log(POWER_SOURCE_MODEL_UNAVAILABLE_MESSAGE);
            return;
        }
        if (!libraryRun && !coolingSelection.config?.implemented) {
            lastReportContext = null;
            if (btnExportHtmlReport) btnExportHtmlReport.disabled = true;
            if (btnExportJson) btnExportJson.disabled = true;
            elOut.value = pretty({
                error: COOLING_MODEL_UNAVAILABLE_MESSAGE,
                cooling_system_type: coolingSelection.type,
                cooling_unit_capacity_mw: coolingSelection.capacityMw,
                power_source: coolingSelection.powerSource
            });
            setSolverDataStatus(COOLING_MODEL_UNAVAILABLE_MESSAGE, "error");
            log(COOLING_MODEL_UNAVAILABLE_MESSAGE);
            return;
        }
        if (!providedLibraryInput && !standardSolverInput && preferStandardFiles) {
            standardSolverInput = buildSolverInputFromStandardFiles(standardDataFiles);
            syncStandardChillerSurfaceToCurveLib(standardDataFiles.chiller);
            elIn.value = pretty(standardSolverInput);
            previewInputCurves(standardDataFiles);
            refreshStandardInputStatus();
        }
        const rawInput = providedLibraryInput || standardSolverInput || JSON.parse(elIn.value);
        const curveLib = window.curveLib || {
            curves_1d: {},
            cop_surfaces: {}
        };

        const job = prepareSolverJob(rawInput, curveLib);

        if (job.kind === "invalid" || job.kind === "invalid_project") {
            const d = job.diagnostics || {};
            lastReportContext = null;
            if (btnExportHtmlReport) btnExportHtmlReport.disabled = true;
            if (btnExportJson) btnExportJson.disabled = true;
            hideProjectVisualization();
            elOut.value = pretty({
                error: job.error,
                diagnostics: d
            });
            setSolverDataStatus(
                `Solver input blocked: ${job.error} IT hours=${d.itHours || 0}, weather hours=${d.weatherHours || 0}`,
                "error"
            );
            log(
                "❌ Solver input blocked\n" +
                `${job.error}\n` +
                `IT hours detected=${d.itHours || 0}\n` +
                `Weather hours detected=${d.weatherHours || 0}\n\n` +
                "Frontend now refuses to silently fall back from annual/project data to single-point mode."
            );
            return;
        }

        if (job.kind === "precomputed_project") {
            elOut.value = pretty(job.output);
            showProjectVisualization(job.output);
            recordScenarioResult(coolingSelection.scenarioKey, job.output.annual_results);
            lastReportContext = { input: job.input, output: job.output, job, generatedAt: new Date().toISOString() };
            if (btnExportHtmlReport) btnExportHtmlReport.disabled = false;
            if (btnExportJson) btnExportJson.disabled = false;
            setSolverDataStatus(
                `Using precomputed solver output: hourly rows=${job.diagnostics.hourlyRows}`,
                "ok"
            );
            log(
                "Detected precomputed annual result\n" +
                `Hourly result count=${job.diagnostics.hourlyRows}\n` +
                "Skipped recompute and rendered visualization directly."
            );
            return;
        }

        const executedSolverFn = requestedSolverFn || job.solverFn;
        await ensurePyodideReady();
        if (executedSolverFn === "compute_acc_excel_replicated_hourly") {
            ensureAccExcelReplicatedHourlyLoaded();
        }
        pyodide.globals.set("dc_json_str", JSON.stringify(job.input));
        pyodide.globals.set("solver_fn", executedSolverFn);

        const outStr = pyodide.runPython(`
import json
dc = json.loads(dc_json_str)
if solver_fn == "compute_acc_excel_replicated_hourly" and "compute_acc_excel_replicated_hourly" not in globals():
    raise RuntimeError("compute_acc_excel_replicated_hourly is not loaded")
out = compute_acc_excel_replicated_hourly(dc) if solver_fn == "compute_acc_excel_replicated_hourly" else (compute_acc_experimental_hourly_shape(dc) if solver_fn == "compute_acc_experimental_hourly_shape" else (compute_acc_excel_benchmark(dc) if solver_fn == "compute_acc_excel_benchmark" else (compute_pue_project(dc) if solver_fn == "compute_pue_project" else compute_pue_v04(dc))))
json.dumps(out, indent=2)
        `);

        elOut.value = outStr;

        const outObj = JSON.parse(outStr);

        // Check if this is a 8760-hour project result
        const hourlyRows = Array.isArray(outObj.hourly_results) ? outObj.hourly_results : [];
        const isProjectResult = outObj.annual_results && hourlyRows.length > 0;
        if (outObj.error) {
            const message = String(outObj.error);
            console.error(outObj);
            lastReportContext = null;
            if (btnExportHtmlReport) btnExportHtmlReport.disabled = true;
            if (btnExportJson) btnExportJson.disabled = true;
            hideProjectVisualization();
            showRuntimeErrorDetails(message);
            if (libraryRun && configurationLibraryData) {
                configurationLibraryData.last_solver_output = null;
                const libraryStatus = document.getElementById("configurationLibraryStatus");
                if (libraryStatus) {
                    libraryStatus.textContent = message;
                    libraryStatus.style.color = "#dc2626";
                }
            }
            const d = job.diagnostics || {};
            setSolverDataStatus(
                `Solver: ${executedSolverFn} | IT hours=${d.itHours || 0} | weather hours=${d.weatherHours || 0} | output rows=${hourlyRows.length} | Error: ${message}`,
                "error"
            );
            log(`Solver error\n${message}`);
            return;
        }
        if (outObj.annual_results && Array.isArray(outObj.hourly_results) && hourlyRows.length === 0) {
            const message = outObj.error || "Solver returned zero hourly rows. No annual results were rendered.";
            lastReportContext = null;
            if (btnExportHtmlReport) btnExportHtmlReport.disabled = true;
            if (btnExportJson) btnExportJson.disabled = true;
            hideProjectVisualization();
            if (libraryRun && configurationLibraryData) {
                configurationLibraryData.last_solver_output = null;
                const libraryStatus = document.getElementById("configurationLibraryStatus");
                if (libraryStatus) {
                    libraryStatus.textContent = message;
                    libraryStatus.style.color = "#dc2626";
                }
            }
            const d = job.diagnostics || {};
            setSolverDataStatus(
                `Solver: ${executedSolverFn} | IT hours=${d.itHours || 0} | weather hours=${d.weatherHours || 0} | output rows=0 | Error: ${message}`,
                "error"
            );
            log(`Solver returned zero hourly rows\n${message}`);
            return;
        }

        if (isProjectResult) {
            clearRuntimeErrorDetails();
            // Show visualization for 8760-hour results
            showProjectVisualization(outObj);
            const outputWarnings = Array.isArray(outObj.warnings) ? outObj.warnings : [];
            if (libraryRun && configurationLibraryData) {
                configurationLibraryData.last_solver_output = outObj;
                renderConfigurationLibrarySummary(configurationLibraryData);
                const libraryStatus = document.getElementById("configurationLibraryStatus");
                if (libraryStatus) {
                    libraryStatus.textContent = `Completed ${configurationLibraryData.configuration_name} / ${providedLibraryInput.scenario_name}: Annual PUE ${fmtNumber(outObj.annual_results.annual_average_PUE, 3)}.`;
                    libraryStatus.style.color = "#059669";
                    if (outputWarnings.length) {
                        libraryStatus.textContent += ` Warning: ${outputWarnings.join(" ")}`;
                        libraryStatus.style.color = "#b45309";
                    }
                }
            }
            recordScenarioResult(coolingSelection.scenarioKey, outObj.annual_results);
            lastReportContext = { input: job.input, output: outObj, job, generatedAt: new Date().toISOString() };
            if (btnExportHtmlReport) btnExportHtmlReport.disabled = false;
            if (btnExportJson) btnExportJson.disabled = false;
            const annual = outObj.annual_results || {};
            const peak = outObj.peak_results || {};
            updatePeakDesignWeatherStatus(peak);
            const hourlyCount = Array.isArray(outObj.hourly_results) ? outObj.hourly_results.length : 0;
            const d = job.diagnostics || {};
            setSolverDataStatus(
                `Solver: ${executedSolverFn} | IT hours=${d.itHours || 0} | weather hours=${d.weatherHours || 0} | output rows=${hourlyCount}${outputWarnings.length ? ` | Warning: ${outputWarnings.join(" ")}` : ""}`,
                hourlyCount > 1 ? (outputWarnings.length ? "info" : "ok") : "error"
            );
            log(
                "Project calculation completed\n" +
                `Solver function=${executedSolverFn}\n` +
                `Exact input paths=${(d.exactSolverPaths || []).join(", ")}\n` +
                `IT hours=${d.itHours || 0}, weather hours=${d.weatherHours || 0}, output hourly rows=${hourlyCount}\n` +
                (d.warning ? `Warning=${d.warning}\n` : "") +
                `Annual PUE=${fmtNumber(annual.annual_average_PUE, 3)}\n` +
                `Annual IT energy=${fmtInteger(annual.annual_IT_energy_kWh)} kWh\n` +
                `Annual facility energy=${fmtInteger(annual.annual_facility_energy_kWh)} kWh\n` +
                `Peak design condition=${peak.peak_design_weather_source || "N/A"} ${peak.peak_design_weather_station || ""}, facility electrical demand=${fmtInteger(peak.peak_design_facility_electrical_demand_kW ?? peak.peak_total_facility_power_kW)} kW`
            );
        } else {
            clearRuntimeErrorDetails();
            // Show compact visualization for single-point results
            showSinglePointVisualization(outObj);
            lastReportContext = { input: job.input, output: outObj, job, generatedAt: new Date().toISOString() };
            if (btnExportHtmlReport) btnExportHtmlReport.disabled = false;
            if (btnExportJson) btnExportJson.disabled = false;
            setSolverDataStatus(
                `Solver: ${job.solverFn} | single-point schema`,
                "info"
            );

            // Original single-point result processing
            const p = outObj.power || {};
            const b = outObj._breakdown_v04 || {};
            const d = b._details || {};
            const ch0 = (d.chillers && d.chillers[0]) ? d.chillers[0] : null;

            const heatSources = b.cooling_heat_sources_kw || {};
            const oat = b.oat_c !== undefined
                ? b.oat_c
                : ((ch0 && ch0.oat_c !== undefined) ? ch0.oat_c : undefined);

            const coolingLoad = b.cooling_load_kw !== undefined
                ? b.cooling_load_kw
                : ((ch0 && ch0.q_kw !== undefined) ? ch0.q_kw : undefined);

            const chillerCount = Array.isArray(d.chillers) ? d.chillers.length : 0;

            log(
                "✅ v0.4.1 运行成功（单点计算）\n" +
                `Solver function=${job.solverFn}\n` +
                `IT(kW)=${p.total_it_power_kw}\n` +
                `Facility(kW)=${p.total_facility_power_kw}\n` +
                `PUE=${p.pue_instant}\n\n` +

                `OAT(°C)=${oat}\n` +
                `Cooling Load(kW)=${coolingLoad}\n` +
                `Cooling(kW)=${b.cooling_kw}\n` +
                `  - Chiller(kW)=${b.chiller_kw} | count=${chillerCount}\n` +
                `  - Pumps(kW)=${b.pumps_kw}\n` +
                `  - Airflow(kW)=${b.airflow_kw}\n` +
                `Control/Aux(kW)=${b.aux_kw}\n\n` +

                "Cooling heat sources(kW):\n" +
                `  - IT liquid=${heatSources.it_liquid_kw}\n` +
                `  - IT air=${heatSources.it_air_kw}\n` +
                `  - Pumps heat=${heatSources.pumps_kw}\n` +
                `  - Airflow heat=${heatSources.airflow_kw}\n` +
                `  - Lighting heat=${heatSources.lighting_kw}\n` +
                `  - People=${heatSources.people_kw}\n` +
                `  - Infiltration=${heatSources.infiltration_kw}\n` +
                `  - Envelope=${heatSources.envelope_kw}\n` +
                `  - Misc=${heatSources.misc_kw}\n\n` +

                "你现在可以：\n" +
                "1) 修改 liquid/air IT split → Run → chiller load 变化\n" +
                "2) 修改 pumps/airflow speed_ratio → Run → heat sources 与 PUE 同步变化\n" +
                "3) 修改 curves.json → Run → UPS / COP 变化"
            );
        }

    } catch (e) {
        console.error(e);
        const message = formatRuntimeException(e);
        lastReportContext = null;
        if (btnExportHtmlReport) btnExportHtmlReport.disabled = true;
        if (btnExportJson) btnExportJson.disabled = true;
        showRuntimeErrorDetails(message);
        setSolverDataStatus(`运行失败：${message}`, "error");
        log("❌ Run 失败：\n" + message);
    } finally {
        runInProgress = false;
        setRunButtonsDisabled(false);
    }
}

btnRun.addEventListener("click", run);
if (btnExportHtmlReport) btnExportHtmlReport.addEventListener("click", exportHtmlReport);
if (btnExportJson) btnExportJson.addEventListener("click", exportOutputJson);
elIn.addEventListener("input", () => {
    preferStandardFiles = false;
    if (standardSolverInput) {
        standardSolverInput = null;
        refreshStandardInputStatus();
        setSolverDataStatus("已切换为下方手写 JSON 输入。", "info");
    }
});
init();
