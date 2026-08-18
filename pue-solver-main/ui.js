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
const btnExportTimeAlignmentCsv = document.getElementById("btnExportTimeAlignmentCsv");
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
let projectItLoadProfileOverride = null;
let lastReportContext = null;
let timeAlignmentAuditCache = null;
let scenarioResults = [];
window.scenario_results = scenarioResults;
let configurationLibraryData = null;
let configurationLibraryCatalog = [];
let automaticEpwReady = false;
let simulationReady = false;
let lastAccCalculationEngineSelection = "acc_v2";
const equipmentPdfSpecs = {};
const CONFIGURATION_LIBRARY_DIRECT_CALCULATION_MODE = "acc_v2_direct_solver_curve_hourly";
const CONFIGURATION_LIBRARY_ACC_ENGINE = "acc_v2_configuration_library";
const CONFIGURATION_LIBRARY_PYODIDE_ROOT = "Configuration Library";
const ASHRAE_PROXY_URL = "http://127.0.0.1:8011/api/ashrae_design_condition";
const PHASE19B_TRACE = true;
const SUPPORTED_CONFIGURATION_TOPOLOGIES = Object.freeze(["acc_gas_engine_cdu", "chiller_dry_cooler"]);
const SUPPORTED_CONFIGURATION_TOPOLOGY = "acc_gas_engine_cdu";
const CONFIGURATION_TOPOLOGY_STATUS = Object.freeze({
    acc_gas_engine_cdu: { display: "ACC Gas Engine CDU", status: "implemented", adapter: "acc_gas_engine_cdu" },
    chiller_dry_cooler: { display: "Chiller + Dry Cooler", status: "implemented", adapter: "chiller_dry_cooler" },
    water_cooled_chiller: { display: "Water-Cooled Chiller", status: "placeholder", adapter: null },
    chiller_cooling_tower: { display: "Chiller + Cooling Tower", status: "placeholder", adapter: null },
    liquid_cooling: { display: "Liquid Cooling", status: "placeholder", adapter: null },
    abs_dry_cooler: { display: "ABS + Dry Cooler", status: "placeholder", adapter: null },
    abs_cooling_tower: { display: "ABS + Cooling Tower", status: "placeholder", adapter: null }
});
const COMMON_REPORT_SECTIONS = Object.freeze([
    "Project Summary",
    "Weather & Design Conditions",
    "Cooling Load Summary",
    "Cooling System Configuration",
    "Operating Scenario",
    "Peak Capacity Validation",
    "Equipment Performance",
    "Annual Energy Breakdown",
    "PUE Summary",
    "Engineering Conclusion"
]);
const REPORT_PROFILE_REGISTRY = Object.freeze({
    acc_gas_engine_cdu: {
        profile_id: "acc_gas_engine_cdu",
        display_name: "ACC Gas Engine CDU Report",
        cooling_system_type: "ACC + Gas Engine + CDU",
        topology: "acc_gas_engine_cdu",
        simulation_engine: "ACC V2 Configuration Library Engine",
        performance_model: "ACC V2 Direct Mode: Configuration Library Solver_Curve hourly simulation",
        simulation_basis: "8760-hour Annual Dynamic Simulation",
        common_sections: COMMON_REPORT_SECTIONS,
        topology_specific_sections: ["ACC COP", "ACC Power"],
        fields: [
            "annual_average_PUE",
            "annual_IT_energy_kWh",
            "annual_facility_energy_kWh",
            "annual_total_cooling_system_energy_kWh",
            "annual_acc_energy_kWh",
            "annual_pump_energy_kWh",
            "annual_white_space_equipment_energy_kWh",
            "annual_engine_energy_kWh",
            "annual_engine_radiator_energy_kWh",
            "annual_electrical_loss_kWh"
        ]
    },
    chiller_dry_cooler: {
        profile_id: "chiller_dry_cooler",
        display_name: "Chiller + Dry Cooler Report",
        cooling_system_type: "Chiller + Dry Cooler",
        topology: "chiller_dry_cooler",
        configuration_status: "Implemented",
        simulation_engine: "Topology Dispatcher Runtime",
        performance_model: "Configuration Library Solver_Curve hourly simulation",
        simulation_basis: "8760-hour Annual Dynamic Simulation",
        common_sections: COMMON_REPORT_SECTIONS,
        topology_specific_sections: ["Chiller COP", "Dry Cooler Performance"],
        fields: [
            "annual_average_PUE",
            "annual_IT_energy_kWh",
            "annual_facility_energy_kWh",
            "annual_chiller_energy_kWh",
            "annual_dry_cooler_energy_kWh",
            "annual_pump_energy_kWh",
            "annual_electrical_loss_kWh",
            "average_chiller_COP",
            "min_chiller_COP",
            "max_chiller_COP",
            "dry_cooler_capacity_kW",
            "configuration_status"
        ]
    },
    water_cooled_chiller: {
        profile_id: "water_cooled_chiller",
        display_name: "Water-Cooled Chiller Report",
        cooling_system_type: "Water-Cooled Chiller",
        topology: "water_cooled_chiller",
        common_sections: COMMON_REPORT_SECTIONS,
        topology_specific_sections: [],
        fields: ["annual_average_PUE", "annual_IT_energy_kWh", "annual_facility_energy_kWh"]
    },
    liquid_cooling: {
        profile_id: "liquid_cooling",
        display_name: "Liquid Cooling Report",
        cooling_system_type: "Liquid Cooling",
        topology: "liquid_cooling",
        common_sections: COMMON_REPORT_SECTIONS,
        topology_specific_sections: [],
        fields: ["annual_average_PUE", "annual_IT_energy_kWh", "annual_facility_energy_kWh"]
    }
});
const GENERIC_REPORT_PROFILE = Object.freeze({
    profile_id: "generic_pue",
    display_name: "Generic PUE Summary",
    cooling_system_type: "Unknown Cooling System",
    topology: "unknown",
    simulation_engine: "Topology Dispatcher Runtime",
    performance_model: "Standardized hourly simulation",
    simulation_basis: "Annual Dynamic Simulation",
    common_sections: COMMON_REPORT_SECTIONS,
    topology_specific_sections: [],
    fields: ["annual_average_PUE", "annual_IT_energy_kWh", "annual_facility_energy_kWh"]
});
const EQUIPMENT_CURVE_SCHEMA_REGISTRY = Object.freeze({
    ACC: {
        ambient_capacity_power: "ambient_capacity_power_2D",
        ambient_capacity_power_2D: "ambient_capacity_power_2D"
    },
    CHILLER: {
        cop_curve: "cop_map_2D",
        cop_map_2D: "cop_map_2D"
    },
    DRY_COOLER: {
        ambient_capacity_power: "ambient_capacity_power_1D",
        ambient_capacity_power_1D: "ambient_capacity_power_1D",
        outdoor_temperature_power: "outdoor_temperature_power_1D",
        outdoor_temperature_power_1D: "outdoor_temperature_power_1D"
    },
    CHW_PUMP: {
        load_ratio_power: "load_ratio_power_1D",
        load_ratio_power_1D: "load_ratio_power_1D"
    },
    CDU: {
        load_ratio_power: "load_ratio_power_1D",
        load_ratio_power_1D: "load_ratio_power_1D"
    },
    RTC: {
        load_ratio_power: "load_ratio_power_1D",
        load_ratio_power_1D: "load_ratio_power_1D"
    },
    MAU: {
        load_ratio_power: "load_ratio_power_1D",
        load_ratio_power_1D: "load_ratio_power_1D"
    },
    ENGINE: {
        load_ratio_engine_output: "load_ratio_engine_output_1D"
    },
    ENGINE_RADIATOR: {
        load_ratio_power: "load_ratio_power_1D",
        load_ratio_power_1D: "load_ratio_power_1D"
    },
    ELECTRICAL_DISTRIBUTION: {
        electrical_path_efficiency: "efficiency_curve",
        efficiency_curve: "efficiency_curve"
    }
});
function equipmentCurveSchema(equipmentType, curveType) {
    const normalizedType = String(equipmentType || "").trim().toUpperCase();
    const normalizedCurve = String(curveType || "").trim();
    return EQUIPMENT_CURVE_SCHEMA_REGISTRY[normalizedType]?.[normalizedCurve] || "Not available";
}
const DIRECT_MODE_PYTHON_MODULES = Object.freeze([
    "equipment_registry.py",
    "equipment_type_registry.py",
    "equipment_curve_registry.py",
    "equipment_metadata.py",
    "configuration_library_scanner.py",
    "configuration_manifest.py",
    "equipment_role_resolver.py",
    "unit_scenario_manager.py",
    "pump_load_framework.py",
    "configuration_library_loader.py",
    "configuration_validator.py",
    "equipment_curve_reader.py",
    "equipment_curve_lookup.py",
    "equipment_engine.py",
    "unit_quantity.py",
    "configuration_direct_mode_audit.py",
    "cooling_load_model.py",
    "ashrae_online_lookup.py",
    "ashrae_design_conditions.py",
    "ashrae_design_conditions_data.json",
    "acc_v2_curve_lookup.py",
    "acc_v2_curve_reader.py",
    "acc_v2_diagnostics.py",
    "acc_v2_engine.py",
    "equipment_engines/__init__.py",
    "equipment_engines/chiller.py",
    "equipment_engines/dry_cooler.py",
    "equipment_engines/equipment_engine_dispatcher.py",
    "equipment_performance/__init__.py",
    "equipment_performance/performance_result.py",
    "equipment_performance/acc_adapter.py",
    "equipment_performance/chiller_adapter.py",
    "equipment_performance/dry_cooler_adapter.py",
    "equipment_performance/performance_dispatcher.py",
    "energy_aggregation/__init__.py",
    "energy_aggregation/energy_result.py",
    "energy_aggregation/annual_energy_aggregator.py",
    "capacity_validation.py",
    "report_renderer.py",
    "report_sections/__init__.py",
    "report_sections/report_section_registry.py",
    "report_profile_registry.py",
    "report_dispatcher.py",
    "solver.py",
    "library_solver_adapter.py",
    "topology_adapters/__init__.py",
    "topology_adapters/acc_gas_engine_cdu.py",
    "topology_adapters/chiller_dry_cooler_runtime.py",
    "topology_adapters/chiller_dry_cooler.py",
    "topology_registry.py",
    "topology_dispatcher.py"
]);

function log(msg) { elLog.textContent = msg; }
function pretty(obj) { return JSON.stringify(obj, null, 2); }

function reportProfileForTopology(topologyId) {
    return REPORT_PROFILE_REGISTRY[topologyId] || { ...GENERIC_REPORT_PROFILE, topology: topologyId || "unknown" };
}

function dispatchReportProfile(topologyId, solverResult = {}) {
    const profile = reportProfileForTopology(topologyId);
    const annual = solverResult?.annual_results || {};
    const hourly = Array.isArray(solverResult?.hourly_results) ? solverResult.hourly_results : [];
    const performanceValue = (row, resultKey, field, fallback) => row?.[resultKey]?.performance?.[field] ?? fallback;
    const chillerCops = hourly.map(row => Number(performanceValue(row, "chiller_performance_result", "COP", row?.chiller_COP))).filter(Number.isFinite);
    const dryCoolerCapacities = hourly.map(row => Number(performanceValue(row, "dry_cooler_performance_result", "capacity_kW", row?.dry_cooler_capacity_kW))).filter(Number.isFinite);
    const derived = {
        average_chiller_COP: chillerCops.length ? chillerCops.reduce((sum, value) => sum + value, 0) / chillerCops.length : null,
        min_chiller_COP: chillerCops.length ? Math.min(...chillerCops) : null,
        max_chiller_COP: chillerCops.length ? Math.max(...chillerCops) : null,
        dry_cooler_capacity_kW: dryCoolerCapacities.length ? Math.max(...dryCoolerCapacities) : null,
        configuration_status: solverResult?.implementation_status || null
    };
    const summary = {};
    for (const field of profile.fields || []) {
        summary[field] = annual[field] ?? derived[field] ?? null;
    }
    const operatingScenario = buildOperatingScenarioSummary(solverResult);
    const capacityValidation = buildCapacityValidationSummary(topologyId, solverResult, operatingScenario);
    const annualEnergyBreakdown = buildAnnualEnergyBreakdown(solverResult);
    const reportSections = buildReportSections(topologyId, solverResult, profile, operatingScenario, capacityValidation, annualEnergyBreakdown);
    const visualizationData = buildReportVisualizationData(hourly);
    const equipmentCurveRegister = buildEquipmentCurveRegister(solverResult);
    const equipmentPerformance = buildEquipmentPerformance(annualEnergyBreakdown, { ...annual, ...derived });
    const coolingLoadBreakdown = buildCoolingLoadBreakdown(annual);
    return { ...profile, summary, operating_scenario: operatingScenario, capacity_validation: capacityValidation, annual_energy_breakdown: annualEnergyBreakdown, report_sections: reportSections, visualization_data: visualizationData, equipment_curve_register: equipmentCurveRegister, equipment_performance: equipmentPerformance, cooling_load_breakdown: coolingLoadBreakdown, dispatch_status: REPORT_PROFILE_REGISTRY[topologyId] ? "matched" : "generic" };
}

function buildReportVisualizationData(hourlyRows = []) {
    const number = (row, keys) => {
        for (const key of keys) {
            const value = Number(row?.[key]);
            if (Number.isFinite(value)) return value;
        }
        return null;
    };
    const normalized = (hourlyRows || []).filter(row => row && typeof row === "object").map((row, index) => ({
        row,
        hour: number(row, ["hour_index", "hour"]) ?? index + 1,
        temperature_C: number(row, ["dry_bulb_C", "outdoor_dry_bulb_C", "outdoor_temp_C", "weather_dry_bulb_C", "dry_bulb", "ambient_dry_bulb_C"]),
        pue: number(row, ["pue", "hourly_PUE", "PUE"]),
        facility_power_kW: number(row, ["facility_power_kW", "total_facility_power_kW"]),
        it_load_kW: number(row, ["it_load_kW", "IT_load_kW"])
    }));
    const temperatureVsPue = normalized
        .filter(row => row.temperature_C !== null && row.pue !== null)
        .map(row => ({ temperature_C: row.temperature_C, pue: row.pue }));
    const peakFacility = normalized.filter(row => row.facility_power_kW !== null)
        .reduce((peak, row) => !peak || row.facility_power_kW > peak.facility_power_kW ? row : peak, null);
    const maxPue = normalized.filter(row => row.pue !== null)
        .reduce((peak, row) => !peak || row.pue > peak.pue ? row : peak, null);
    return {
        temperature_vs_pue: temperatureVsPue,
        monthly_pue: buildMonthlyPueData(normalized),
        peak_summary: {
            peak_facility_hour: peakFacility?.hour ?? null,
            peak_pue: peakFacility?.pue ?? null,
            peak_facility_power_kW: peakFacility?.facility_power_kW ?? null,
            peak_it_load_kW: peakFacility?.it_load_kW ?? null,
            peak_outdoor_dry_bulb_C: peakFacility?.temperature_C ?? null,
            max_hourly_pue: maxPue?.pue ?? null,
            max_hourly_pue_hour: maxPue?.hour ?? null
        }
    };
}

function buildMonthlyPueData(normalizedRows = []) {
    const monthHours = [744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744];
    const monthly = [];
    let offset = 0;
    monthHours.forEach((hours, index) => {
        const rows = normalizedRows.slice(offset, offset + hours);
        offset += hours;
        const facilityEnergy = rows.reduce((sum, row) => sum + (Number.isFinite(row.facility_power_kW) ? row.facility_power_kW : 0), 0);
        const itEnergy = rows.reduce((sum, row) => sum + (Number.isFinite(row.it_load_kW) ? row.it_load_kW : 0), 0);
        if (itEnergy > 0) monthly.push({ month: index + 1, average_pue: facilityEnergy / itEnergy });
    });
    return monthly;
}

function buildEquipmentCurveRegister(solverResult = {}) {
    const selectedCurves = solverResult?.library_context?.selected_curves || solverResult?.selected_curves || {};
    return Object.entries(selectedCurves).flatMap(([equipmentId, curve]) => {
        if (!curve || typeof curve !== "object") return [];
        const sheet = curve.sheet_name || curve.selected_curve_sheet;
        const metadata = curve.equipment_metadata || {};
        const curveType = metadata.curve_type || curve.curve_type || sheet;
        if (!sheet && !curve.electrical_path && !curveType) return [];
        const variables = Array.isArray(metadata.independent_variables) ? metadata.independent_variables : [];
        const modelBasis = variables.length
            ? `Hourly ${variables.join(" and ")} lookup`
            : (curve.electrical_path ? "Hourly electrical path efficiency lookup" : "Hourly temperature and load lookup");
        return [{
            equipment_id: equipmentId,
            curve_source: "Configuration Library Solver_Curve",
            curve_type: curveType || "Equipment Performance Curve",
            model_basis: modelBasis
        }];
    });
}

function buildEquipmentPerformance(annualEnergyBreakdown = {}, summary = {}) {
    const normalizedSummary = Object.fromEntries(Object.entries(summary).map(([key, value]) => [String(key).toLowerCase(), value]));
    return Object.entries(annualEnergyBreakdown.components || {}).flatMap(([equipment, component]) => {
        const energy = Number(component?.energy_kWh);
        if (!Number.isFinite(energy)) return [];
        const metricValue = Number(normalizedSummary[`average_${String(equipment).toLowerCase()}_cop`]);
        return [{
            equipment,
            annual_energy_kWh: energy,
            performance_metric: Number.isFinite(metricValue) ? "Average COP" : null,
            metric_value: Number.isFinite(metricValue) ? metricValue : null
        }];
    });
}

function buildCoolingLoadBreakdown(annual = {}) {
    const numberOrNull = value => Number.isFinite(Number(value)) ? Number(value) : null;
    return {
        annual_it_load_kWh: numberOrNull(annual.annual_IT_energy_kWh),
        annual_solar_heat_gain_kWh: numberOrNull(annual.annual_solar_heat_gain_kWh),
        annual_other_auxiliary_heat_gain_kWh: numberOrNull(annual.annual_other_auxiliary_heat_gain_kWh),
        annual_cooling_load_kWh: numberOrNull(annual.annual_cooling_load_kWh)
    };
}

function buildAnnualEnergyBreakdown(solverResult = {}) {
    if (solverResult?.standard_annual_energy) return solverResult.standard_annual_energy;
    const annual = solverResult?.annual_results || {};
    const components = {};
    const add = (key, value) => {
        const numeric = Number(value);
        if (Number.isFinite(numeric)) components[key] = { energy_kWh: numeric, sources: ["annual_results"] };
    };
    add("ACC", annual.annual_acc_energy_kWh);
    add("CHILLER", annual.annual_chiller_energy_kWh);
    add("DRY_COOLER", annual.annual_dry_cooler_energy_kWh);
    add("CHW_PUMP", annual.annual_pump_energy_kWh);
    add("INDOOR_EQUIPMENT", annual.annual_white_space_equipment_energy_kWh ?? annual.annual_indoor_equipment_energy_kWh);
    add("ENGINE", annual.annual_engine_energy_kWh);
    add("ENGINE_RADIATOR", annual.annual_engine_radiator_energy_kWh);
    add("ELECTRICAL_LOSS", annual.annual_electrical_loss_kWh);
    const cooling = ["ACC", "CHILLER", "DRY_COOLER", "CHW_PUMP", "ENGINE_RADIATOR"].reduce((sum, key) => sum + Number(components[key]?.energy_kWh || 0), 0);
    return {
        annual_it_energy_kWh: annual.annual_IT_energy_kWh,
        annual_facility_energy_kWh: annual.annual_facility_energy_kWh,
        annual_cooling_energy_kWh: cooling,
        components,
        PUE: annual.annual_average_PUE,
        warnings: []
    };
}

function buildOperatingScenarioSummary(solverResult = {}) {
    const project = solverResult?.project || {};
    const unitScenario = solverResult?.library_context?.runtime_assumptions?.unit_scenario || {};
    const roleQuantities = unitScenario.role_quantities || {};
    const firstRow = Array.isArray(solverResult?.hourly_results) ? solverResult.hourly_results.find(Boolean) || {} : {};
    const numberOrNull = value => Number.isFinite(Number(value)) ? Number(value) : null;
    const summary = {
        scenario_name: unitScenario.scenario_name || solverResult?.scenario_name || project.scenario_name || null,
        redundancy_mode: unitScenario.redundancy_mode || project.redundancy_strategy || null,
        installed_units: numberOrNull(unitScenario.installed_units ?? project.installed_units),
        required_units: numberOrNull(unitScenario.required_units ?? project.required_units),
        active_units: numberOrNull(unitScenario.active_units ?? project.active_units),
        standby_units: numberOrNull(unitScenario.standby_units ?? project.standby_units),
        failed_units: numberOrNull(unitScenario.failed_units)
    };
    const roleValue = (role, key, fallback) => numberOrNull(roleQuantities?.[role]?.[key] ?? fallback);
    const activeChiller = roleValue("chiller_units", "active_units", firstRow.active_chiller_units);
    const activeDryCooler = roleValue("dry_cooler_units", "active_units", firstRow.active_dry_cooler_units);
    const activePump = roleValue("pump_units", "active_units", firstRow.active_pump_units);
    if (activeChiller !== null) summary.active_chiller_units = activeChiller;
    if (activeDryCooler !== null) summary.active_dry_cooler_units = activeDryCooler;
    if (activePump !== null) summary.active_pump_units = activePump;
    return summary;
}

function buildCapacityValidationSummary(topologyId, solverResult = {}, operatingScenario = {}) {
    if (solverResult?.capacity_validation) return solverResult.capacity_validation;
    const peak = solverResult?.peak_results || {};
    const project = solverResult?.project || {};
    const hourly = Array.isArray(solverResult?.hourly_results) ? solverResult.hourly_results : [];
    const firstRow = hourly.find(Boolean) || {};
    const peakCoolingLoad = Number(peak.peak_design_cooling_load_kW ?? Math.max(...hourly.map(row => Number(row?.cooling_load_kW)).filter(Number.isFinite)));
    const unitCapacity = Number(project.cooling_unit_capacity_kW ?? firstRow.cooling_unit_capacity_kW ?? firstRow.chiller_unit_capacity_kW);
    const installedUnits = Number(operatingScenario.installed_units);
    const activeUnits = Number(operatingScenario.active_units);
    const installedCapacity = Number.isFinite(unitCapacity) && Number.isFinite(installedUnits) ? unitCapacity * installedUnits : null;
    const activeCapacity = Number.isFinite(unitCapacity) && Number.isFinite(activeUnits) ? unitCapacity * activeUnits : null;
    const margin = Number.isFinite(activeCapacity) && Number.isFinite(peakCoolingLoad) ? activeCapacity - peakCoolingLoad : null;
    const warnings = [];
    if (!Number.isFinite(peakCoolingLoad)) warnings.push("Peak design cooling load is unavailable.");
    if (!Number.isFinite(activeCapacity)) warnings.push("Active capacity is unavailable.");
    return {
        status: margin !== null && margin < 0 ? "error" : (warnings.length ? "warning" : "valid"),
        topology: topologyId || "unknown",
        scenario_name: operatingScenario.scenario_name || null,
        redundancy_mode: operatingScenario.redundancy_mode || null,
        peak_cooling_load_kW: Number.isFinite(peakCoolingLoad) ? peakCoolingLoad : null,
        installed_capacity_kW: installedCapacity,
        active_capacity_kW: activeCapacity,
        capacity_margin_kW: margin,
        capacity_margin_percent: margin !== null && peakCoolingLoad ? margin / peakCoolingLoad * 100 : null,
        failed_units: operatingScenario.failed_units ?? null,
        warnings
    };
}

function buildReportSections(topologyId, solverResult = {}, profile = {}, operatingScenario = {}, capacityValidation = {}, annualEnergyBreakdown = {}) {
    const annual = solverResult?.annual_results || {};
    const peak = solverResult?.peak_results || {};
    const project = solverResult?.project || {};
    const hourly = Array.isArray(solverResult?.hourly_results) ? solverResult.hourly_results : [];
    const summary = profile.summary || {};
    const row = (label, value) => ({ label, value });
    const section = (id, title, rows = [], status = null) => {
        const payload = { id, title, rows: rows.filter(item => item && item.value !== undefined && item.value !== null && item.value !== "") };
        if (status) payload.status = status;
        return payload;
    };
    const scenarioRows = Object.entries({
        "Scenario": operatingScenario.scenario_name,
        "Redundancy Mode": operatingScenario.redundancy_mode,
        "Required Units": operatingScenario.required_units,
        "Installed Units": operatingScenario.installed_units,
        "Active Units": operatingScenario.active_units,
        "Standby Units": operatingScenario.standby_units,
        "Failed Units": operatingScenario.failed_units,
        "Active Chiller Units": operatingScenario.active_chiller_units,
        "Active Dry Cooler Units": operatingScenario.active_dry_cooler_units,
        "Active Pumps": operatingScenario.active_pump_units
    }).map(([label, value]) => row(label, value));
    const capacityRows = Object.entries({
        "Peak Cooling Load": capacityValidation.peak_cooling_load_kW,
        "Installed Capacity": capacityValidation.installed_capacity_kW,
        "Active Capacity": capacityValidation.active_capacity_kW,
        "Capacity Margin": capacityValidation.capacity_margin_kW,
        "Margin Percentage": capacityValidation.capacity_margin_percent,
        "Validation Status": capacityValidation.status
    }).map(([label, value]) => row(label, value));
    const energyComponents = annualEnergyBreakdown.components || {};
    const energyRows = [
        row("IT Energy", annualEnergyBreakdown.annual_it_energy_kWh),
        ...Object.entries(energyComponents).map(([key, value]) => row(reportKeyLabel(key), value?.energy_kWh)),
        row("Cooling Energy", annualEnergyBreakdown.annual_cooling_energy_kWh),
        row("Facility Energy", annualEnergyBreakdown.annual_facility_energy_kWh),
        row("PUE", annualEnergyBreakdown.PUE)
    ];
    const performanceRows = [];
    const seen = new Set();
    for (const hourlyRow of hourly) {
        if (!hourlyRow || typeof hourlyRow !== "object") continue;
        for (const [key, value] of Object.entries(hourlyRow)) {
            if (!key.endsWith("_performance_result") || !value || typeof value !== "object") continue;
            const uniqueKey = `${value.equipment_id || key}:${value.equipment_type || "UNKNOWN"}`;
            if (seen.has(uniqueKey)) continue;
            seen.add(uniqueKey);
            const performance = value.performance || {};
            performanceRows.push({
                equipment: value.equipment_id || key,
                equipment_type: value.equipment_type || "UNKNOWN",
                power_kW: performance.power_kW,
                COP: performance.COP,
                load_ratio: performance.load_ratio,
                capacity_ratio: performance.capacity_ratio,
                diagnostics: value.diagnostics || {}
            });
        }
    }
    if (!performanceRows.length && (annual.average_acc_cop != null || annual.max_acc_power_kW != null)) {
        performanceRows.push(
            row("Average ACC COP", annual.average_acc_cop),
            row("Minimum ACC COP", annual.min_acc_cop),
            row("Maximum ACC COP", annual.max_acc_cop),
            row("Maximum ACC Power", annual.max_acc_power_kW),
            row("ACC Capacity Clamped Hours", annual.acc_capacity_clamped_hours)
        );
    }
    const summaryRows = Object.entries(summary).map(([key, value]) => row(reportKeyLabel(key), value));
    return {
        common: [
            section("project_summary", "Project Summary", [
                row("Configuration", solverResult.configuration_id || project.configuration_id),
                row("Cooling System Type", profile.cooling_system_type || solverResult.cooling_system_type),
                row("Solver Topology", topologyId),
                row("Report Profile", profile.profile_id),
                row("Implementation Status", solverResult.implementation_status || profile.status)
            ]),
            section("weather_design_conditions", "Weather & Design Conditions", [
                row("Weather Source", peak.peak_design_weather_source || project.weather_source),
                row("EPW Location", project.location || project.site_location),
                row("Simulation Hours", hourly.length || null),
                row("Peak Dry Bulb", peak.peak_design_outdoor_dry_bulb_C),
                row("Peak Cooling Design Point", peak.peak_design_cooling_load_kW)
            ]),
            section("cooling_load_summary", "Cooling Load Summary", [
                row("Design IT Load", peak.peak_design_it_load_kW || project.design_it_load_kW),
                row("Annual IT Energy", annual.annual_IT_energy_kWh || annualEnergyBreakdown.annual_it_energy_kWh),
                row("Solar Heat Gain", annual.annual_solar_heat_gain_kWh),
                row("Other Auxiliary Heat Gain", annual.annual_other_auxiliary_heat_gain_kWh),
                row("Peak Cooling Load", peak.peak_design_cooling_load_kW),
                row("Annual Cooling Load", annual.annual_cooling_load_kWh)
            ]),
            section("cooling_system_configuration", "Cooling System Configuration", [
                row("Cooling System Type", profile.cooling_system_type || solverResult.cooling_system_type),
                row("Solver Topology", topologyId),
                row("Configuration Status", solverResult.implementation_status || profile.configuration_status),
                ...summaryRows
            ]),
            section("operating_scenario", "Operating Scenario", scenarioRows),
            section("peak_capacity_validation", "Peak Capacity Validation", capacityRows, capacityValidation.status),
            section("equipment_performance", "Equipment Performance", performanceRows),
            section("annual_energy_breakdown", "Annual Energy Breakdown", energyRows),
            section("pue_summary", "PUE Summary", [
                row("Annual PUE", annualEnergyBreakdown.PUE ?? annual.annual_average_PUE),
                row("Annual IT Energy", annualEnergyBreakdown.annual_it_energy_kWh ?? annual.annual_IT_energy_kWh),
                row("Annual Facility Energy", annualEnergyBreakdown.annual_facility_energy_kWh ?? annual.annual_facility_energy_kWh)
            ]),
            section("engineering_conclusion", "Engineering Conclusion", [
                row("Conclusion", buildEngineeringConclusion(capacityValidation).text)
            ], buildEngineeringConclusion(capacityValidation).status)
        ],
        topology_specific: (profile.topology_specific_sections || []).map(title => ({ title, rows: [] })),
        engineering_conclusion: buildEngineeringConclusion(capacityValidation),
        topology: topologyId || "unknown",
        annual_energy_breakdown: annualEnergyBreakdown,
        operating_scenario: operatingScenario,
        capacity_validation: capacityValidation
    };
}

function buildEngineeringConclusion(capacityValidation = {}) {
    const status = String(capacityValidation.status || "warning").toLowerCase();
    const marginPercent = Number(capacityValidation.capacity_margin_percent);
    if (status === "error") {
        return {
            status: "FAIL",
            text: "Available cooling capacity is insufficient for peak design demand."
        };
    }
    if (status === "valid" && (!Number.isFinite(marginPercent) || marginPercent >= 10)) {
        return {
            status: "PASS",
            text: "Cooling system satisfies peak design cooling demand under selected operating scenario."
        };
    }
    return {
        status: "WARNING",
        text: "Cooling capacity margin is limited under failure scenario."
    };
}

function phase19bTrace(label, data = null) {
    if (!PHASE19B_TRACE) return;
    const payload = data && typeof data === "object" ? JSON.parse(JSON.stringify(data)) : data;
    console.log(`[Phase19B] ${label}`, payload ?? "");
}

function setRunButtonsDisabled(disabled) {
    refreshSimulationReadiness();
    if (btnRun) btnRun.disabled = disabled || !simulationReady;
}

function coolingLoadAdjustmentInputsReady() {
    return [
        ["solarHeatGainMaxKw", 0, null],
        ["solarDaytimeStartHour", 0, 24],
        ["solarDaytimeEndHour", 0, 24],
        ["otherAuxiliaryHeatGainKw", 0, null],
        ["otherElectricalAuxiliaryPowerKw", 0, null]
    ].every(([id, minimum, maximum]) => {
        const input = document.getElementById(id);
        const value = input?.value === "" ? NaN : Number(input?.value);
        return Number.isFinite(value) && value >= minimum && (maximum === null || value <= maximum);
    });
}

function getSimulationReadiness() {
    const selectedConfigurationId = document.getElementById("configurationLibrarySelect")?.value || "";
    const loadedConfigurationId = configurationLibraryData?.configuration_id
        || configurationLibraryData?.configuration_manifest?.configuration_id
        || "";
    const configurationReady = Boolean(configurationLibraryData)
        && Boolean(selectedConfigurationId)
        && selectedConfigurationId === loadedConfigurationId;
    const validation = configurationReady
        ? (configurationLibraryData.configuration_validation || validateFrontendConfigurationLibrary(configurationLibraryData))
        : null;
    const equipmentBindingsReady = configurationReady
        && validation?.status === "valid"
        && !(validation.missing_roles || []).length
        && !(validation.missing_curves || []).length;
    const weatherHours = getWeatherHours(standardDataFiles.weather);
    const weatherReady = automaticEpwReady && [8760, 8784].includes(weatherHours);
    const itProfile = configurationLibraryData?.it_load;
    const itLoadHours = Number(itProfile?.hours || 0);
    const calendarAlignment = validateItCalendarAgainstEpw(itProfile, standardDataFiles.weather);
    if (itProfile) Object.assign(itProfile, calendarAlignment);
    const profileValid = ["valid", "valid_with_overload_warning"].includes(itProfile?.validation_status);
    const itLoadReady = configurationReady
        && weatherReady
        && profileValid
        && calendarAlignment.calendar_epw_match_valid !== false
        && [8760, 8784].includes(itLoadHours)
        && itLoadHours === weatherHours;
    const coolingInputsReady = coolingLoadAdjustmentInputsReady();
    return {
        configurationReady,
        equipmentBindingsReady,
        weatherReady,
        itLoadReady,
        coolingInputsReady,
        weatherHours,
        itLoadHours,
        validation,
        itProfile,
        simulationReady: configurationReady && equipmentBindingsReady && weatherReady && itLoadReady && coolingInputsReady
    };
}

function refreshSimulationReadiness() {
    const readiness = getSimulationReadiness();
    simulationReady = readiness.simulationReady;
    window.simulationReady = simulationReady;
    window.simulationReadiness = readiness;
    const checks = document.getElementById("simulationReadinessChecks");
    const status = document.getElementById("simulationReadinessStatus");
    const message = document.getElementById("simulationReadinessMessage");
    const checkRow = (ready, readyText, notReadyText, detail = "") =>
        `<div style="margin-top:6px; color:${ready ? "#059669" : "#dc2626"};">${ready ? "✓" : "✕"} ${esc(ready ? readyText : notReadyText)}${detail ? `<div class="hint" style="margin-left:20px;">${esc(detail)}</div>` : ""}</div>`;
    const missingBindings = [
        ...(readiness.validation?.missing_roles || []),
        ...(readiness.validation?.missing_curves || [])
    ];
    const weatherMetadata = getWeatherSourceMetadata(standardDataFiles.weather);
    if (checks) checks.innerHTML = [
        checkRow(readiness.configurationReady, "Configuration Library Loaded", "Configuration Library Not Loaded", readiness.configurationReady ? loadedConfigurationReadinessName() : ""),
        checkRow(readiness.equipmentBindingsReady, "Equipment Curves Bound", "Equipment Curves Incomplete", missingBindings.length ? `Missing: ${missingBindings.join(", ")}` : ""),
        checkRow(readiness.weatherReady, `EPW Weather Loaded — ${readiness.weatherHours} hours`, "EPW Weather Not Ready", readiness.weatherReady ? [weatherMetadata.station, weatherMetadata.source].filter(Boolean).join(" / ") : ""),
        checkRow(readiness.itLoadReady, `Annual IT Load Profile Ready — ${readiness.itLoadHours} hours`, "Annual IT Load Profile Invalid", readiness.itProfile?.validation_errors?.join("; ") || readiness.itProfile?.calendar_epw_match_error || (readiness.weatherReady && readiness.itLoadHours !== readiness.weatherHours ? `IT profile hours: ${readiness.itLoadHours}; weather hours: ${readiness.weatherHours}; mismatch` : readiness.itProfile?.validation_warning || readiness.itProfile?.calendar_validation_warning || "")),
        checkRow(readiness.coolingInputsReady, "Cooling Load Inputs Ready", "Cooling Load Inputs Invalid")
    ].join("");
    if (status) {
        status.textContent = simulationReady ? "READY FOR ANNUAL SIMULATION" : "SIMULATION INPUTS NOT READY";
        status.style.color = simulationReady ? "#059669" : "#dc2626";
    }
    if (message) message.textContent = !readiness.configurationReady ? "Load a Configuration Library before running."
        : !readiness.equipmentBindingsReady ? "Required equipment curve binding is incomplete."
        : !readiness.weatherReady ? "EPW weather is not ready."
        : !readiness.itLoadReady ? (readiness.itProfile?.hour_sequence_error || readiness.itProfile?.calendar_sequence_error || readiness.itProfile?.calendar_epw_match_error || "IT load profile must match the annual weather length.")
        : !readiness.coolingInputsReady ? "Check Cooling Load Adjustment inputs."
        : "All required inputs and bindings are ready.";
    renderItLoadProfileStatus(readiness.itProfile);
    if (btnRun) btnRun.disabled = !simulationReady;
    return readiness;
}

function loadedConfigurationReadinessName() {
    return configurationLibraryData?.configuration_name
        || configurationLibraryData?.configuration_display_name
        || configurationLibraryData?.configuration_id
        || "";
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
    const text = await fetch(`./${fileName}`, { cache: "no-store" }).then(response => {
        if (!response.ok) throw new Error(`Failed to load ${fileName}`);
        return response.text();
    });
    const directory = String(fileName || "").split("/").slice(0, -1).join("/");
    if (directory) ensurePyodideDir(directory);
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
    phase19bTrace("applyAccCalculationEngineSelection", {
        run_mode: inputObj.run_mode,
        acc_v2_enabled: inputObj.acc_v2.enabled,
        acc_v2_configuration_path: inputObj.acc_v2.configuration_path,
        ashrae_top: inputObj.ashrae_design_conditions_url,
        ashrae_project: inputObj.project?.ashrae_design_conditions_url
    });
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
    const type = configurationLibraryData?.cooling_system_type || DEFAULT_COOLING_SYSTEM_TYPE;
    const capacityMw = Number(configurationLibraryData?.cooling_unit_capacity_mw || DEFAULT_COOLING_UNIT_CAPACITY_MW);
    const powerSource = configurationLibraryData?.power_source || DEFAULT_POWER_SOURCE;
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
    const aliasUrl = new URL("equipment_aliases.json", CONFIGURATION_LIBRARY_ROOT_URL);
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
    const libraryLoaded = Boolean(configurationLibraryData);
    const directModeActive = isConfigurationLibraryDirectModeActive({ type, capacityMw, powerSource });
    const displayValues = {
        coolingSystemType: libraryLoaded ? type : "Not loaded",
        coolingUnitCapacity: libraryLoaded ? `${capacityMw} MW` : "Not loaded",
        powerSource: libraryLoaded ? powerSource : "Not loaded"
    };
    Object.entries(displayValues).forEach(([id, value]) => {
        const field = document.getElementById(id);
        if (field) field.textContent = value;
        const source = document.getElementById(`${id}Source`);
        if (source) source.textContent = libraryLoaded
            ? "Loaded from Configuration Library"
            : "Source: Configuration Library (not loaded)";
    });
    const renderList = (id, values) => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = values.map(value => `<li>${esc(value)}</li>`).join("");
    };
    renderList("whiteSpaceEquipmentList", !libraryLoaded ? ["Load Configuration Library to view equipment"] : directModeActive
        ? DIRECT_MODE_WHITE_SPACE_EQUIPMENT
        : (powerConfig?.white_space_equipment || []).map(equipmentIdDisplayName));
    renderList("graySpaceEquipmentList", !libraryLoaded ? ["Load Configuration Library to view equipment"] : directModeActive
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
    renderList("coolingPerformanceCurveList", libraryLoaded ? curveRows : ["Load Configuration Library to view curve dependencies"]);
    if (libraryLoaded) checkSelectedDefaultCurveFiles(powerConfig);
    const status = document.getElementById("coolingSystemStatus");
    if (status) {
        const libraryRunnable = directModeActive;
        const runnable = (config?.implemented && powerSource === DEFAULT_POWER_SOURCE) || libraryRunnable;
        status.textContent = !libraryLoaded ? "Load a Configuration Library to define the cooling system." : runnable ? `${type}, ${capacityMw} MW, ${powerSource}, ${scenario.display_name}: ${libraryRunnable ? "Configuration Library calculation model" : "calculation model"} available.`
            : powerSource !== DEFAULT_POWER_SOURCE ? POWER_SOURCE_MODEL_UNAVAILABLE_MESSAGE : COOLING_MODEL_UNAVAILABLE_MESSAGE;
        status.style.color = libraryLoaded && runnable ? "#059669" : "#b45309";
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
    renderCoolingSystemSelection();
}

function initCoolingSystemSelection() {
    const scenarioSelect = document.getElementById("scenarioSelect");
    if (!scenarioSelect) return;
    scenarioSelect.innerHTML = Object.values(SCENARIO_REGISTRY)
        .map(scenario => `<option value="${scenario.scenario_key}">${scenario.display_name}</option>`).join("");
    scenarioSelect.value = DEFAULT_SCENARIO_KEY;
    renderCoolingSystemSelection();
    scenarioSelect.addEventListener("change", () => {
        renderCoolingSystemSelection();
        if (configurationLibraryData) {
            configurationLibraryData.standardized_solver_input = buildFrontendSolverInputFromLibrary(configurationLibraryData);
            renderConfigurationLibrarySummary(configurationLibraryData);
        }
        standardSolverInput = null;
        refreshStandardInputStatus();
        refreshSimulationReadiness();
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
    const proxyUrl = manualSelected ? null : ASHRAE_PROXY_URL;
    return {
        peakDesignWeatherSource: manualSelected ? "manual" : "ashrae_auto",
        peakDesignOutdoorDryBulbC: manualSelected ? manualDryBulb : null,
        ashraeDesignConditionsUrl: proxyUrl
    };
}

async function fetchAshraeProxyDesignConditionForLibrary(libraryInput) {
    const project = libraryInput?.project || {};
    const latitude = Number(project.latitude ?? project.site_location?.latitude ?? project.location?.latitude);
    const longitude = Number(project.longitude ?? project.site_location?.longitude ?? project.location?.longitude);
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
        phase19bTrace("fetchAshraeProxyDesignConditionForLibrary:skipped missing coordinates", { latitude, longitude });
        return null;
    }
    const url = new URL(ASHRAE_PROXY_URL);
    url.searchParams.set("latitude", String(latitude));
    url.searchParams.set("longitude", String(longitude));
    phase19bTrace("fetchAshraeProxyDesignConditionForLibrary:browser GET", { url: url.href });
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`ASHRAE proxy HTTP ${response.status}`);
    const payload = await response.json();
    phase19bTrace("fetchAshraeProxyDesignConditionForLibrary:browser response", payload);
    return payload;
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

function renderReportSections(reportSections) {
    const sections = normalizeReportSections(reportSections);
    if (!sections.length) return `<div class="empty">No structured report sections were provided.</div>`;
    return sections.map(section => renderReportSection(section)).join("");
}

function normalizeReportSections(reportSections) {
    if (Array.isArray(reportSections)) {
        return reportSections.filter(section => section && typeof section === "object");
    }
    if (!reportSections || typeof reportSections !== "object") return [];
    return ["common", "topology_specific"]
        .flatMap(key => Array.isArray(reportSections[key]) ? reportSections[key] : [])
        .filter(section => section && typeof section === "object");
}

function renderReportSection(section) {
    const title = section.title || section.id || "Report Section";
    const rows = Array.isArray(section.rows) ? section.rows : [];
    const status = section.status ? `<div class="note">Status: ${esc(section.status)}</div>` : "";
    const body = rows.length ? renderReportSectionRows(rows) : `<div class="empty">No rows reported.</div>`;
    return `<div class="card reportSection" data-section="${esc(section.id || "")}"><h3>${esc(title)}</h3>${status}${body}</div>`;
}

function renderReportSectionRows(rows) {
    const normalizedRows = rows
        .filter(row => row !== null && row !== undefined)
        .map(row => (row && typeof row === "object" && !Array.isArray(row)) ? row : { value: row });
    if (!normalizedRows.length) return `<div class="empty">No rows reported.</div>`;
    const allKeySet = new Set(normalizedRows.flatMap(row => Object.keys(row)));
    const allKeys = Array.from(allKeySet);
    if (allKeys.every(key => key === "label" || key === "value")) {
        return `<table><tbody>${normalizedRows.map(row => `<tr><th>${renderReportCell(row.label)}</th><td>${renderReportCell(row.value)}</td></tr>`).join("")}</tbody></table>`;
    }
    return `<table><thead><tr>${allKeys.map(key => `<th>${esc(reportKeyLabel(key))}</th>`).join("")}</tr></thead><tbody>${
        normalizedRows.map(row => `<tr>${allKeys.map(key => `<td>${renderReportCell(row[key])}</td>`).join("")}</tr>`).join("")
    }</tbody></table>`;
}

function renderReportCell(value) {
    if (value === null || value === undefined || value === "") return "N/A";
    if (Array.isArray(value)) return esc(value.join(", "));
    if (typeof value === "object") return esc(JSON.stringify(value));
    if (typeof value === "number") return esc(Number.isInteger(value) ? String(value) : value.toFixed(3));
    return esc(value);
}

function reportKeyLabel(key) {
    return String(key || "")
        .replace(/_/g, " ")
        .replace(/\b\w/g, char => char.toUpperCase());
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
        { key: "auxiliary", label: "Other Electrical Auxiliary Power", ppue: ppue(annual.annual_other_electrical_auxiliary_energy_kWh ?? annual.annual_auxiliary_energy_kWh) }
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
        ["Cooling Load Assembly", `<span class="math"><i>Q</i><sub>cooling,h</sub> = <i>Q</i><sub>IT,h</sub> + <i>Q</i><sub>solar,h</sub> + <i>Q</i><sub>other_aux,h</sub></span>`],
        ["Equipment Performance Lookup", `<span class="math"><i>P</i><sub>equipment,h</sub> = <i>f</i>(<i>T</i><sub>outdoor,h</sub>, <i>load</i><sub>h</sub>, <i>Solver_Curve</i>)</span>`],
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
    return buildHtmlReportFromSections(context);
}

function buildHtmlReportFromSections(context) {
    const output = context.output || {};
    const annual = output.annual_results || {};
    const peak = output.peak_results || {};
    const hourly = Array.isArray(output.hourly_results) ? output.hourly_results : [];
    const manifest = context.input?.configuration_manifest || {};
    const solverTopology = context.input?.topology_id || context.input?.solver_dispatch_key || manifest.solver_topology || "unknown";
    const report = dispatchReportProfile(solverTopology, output);
    const reportSections = report.report_sections || buildReportSections(
        solverTopology,
        output,
        report,
        report.operating_scenario || {},
        report.capacity_validation || {},
        report.annual_energy_breakdown || {}
    );
    const projectInfo = getProjectReportInfo();
    const weather = standardDataFiles.weather || {};
    const weatherData = weather.data || weather.hourly_data || {};
    const weatherSource = getWeatherSourceMetadata(weather);
    const dry = standardDataArray(standardDataFiles.weather || {}, [["data", "dry_bulb_C"], ["hourly_data", "dry_bulb_C"], ["weather", "hourly_data", "dry_bulb_C"]]);
    const pueSeries = hourly.map(row => pickHourlyValue(row, ["pue", "hourly_PUE", "PUE"])).filter(Number.isFinite);
    const facilitySeries = hourly.map(row => pickHourlyValue(row, ["facility_power_kW", "total_facility_power_kW"])).filter(Number.isFinite);
    const facilityVsIt = hourly.map(row => [
        pickHourlyValue(row, ["it_load_kW", "IT_load_kW"]),
        pickHourlyValue(row, ["facility_power_kW", "total_facility_power_kW"])
    ]).filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y));
    const monthlyPue = report.visualization_data.monthly_pue;
    const reportCurves = collectReportCurves();
    const curveGroups = groupReportCurves(reportCurves);
    const tempDistribution = buildTemperatureDistribution(weatherData);
    const drySummary = summarizeNumericArray(dry);
    const annualEnergyBreakdown = report.annual_energy_breakdown || {};
    const pumpRows = hourly.filter(row => Number.isFinite(Number(row.pump_load_ratio_raw)));
    const pumpReference = pumpRows[0]?.pump_reference_capacity_per_unit_kW;
    const pumpActiveCount = pumpRows[0]?.pump_active_unit_count ?? pumpRows[0]?.active_pump_units;
    const pumpMaxRawRatio = pumpRows.length ? Math.max(...pumpRows.map(row => Number(row.pump_load_ratio_raw))) : null;
    const pumpOverloadHours = pumpRows.filter(row => row.pump_overload || row.pump_clamped_high).length;
    const pumpClampedHours = pumpRows.filter(row => row.pump_clamped_low || row.pump_clamped_high).length;
    const cwPumpRows = hourly.filter(row => Number.isFinite(Number(row.cw_pump_load_ratio_raw)));
    const cwPumpReference = cwPumpRows[0]?.cw_pump_reference_capacity_per_unit_kW;
    const cwPumpActiveCount = cwPumpRows[0]?.cw_pump_active_unit_count;
    const cwPumpMaxRawRatio = cwPumpRows.length ? Math.max(...cwPumpRows.map(row => Number(row.cw_pump_load_ratio_raw))) : null;
    const cwPumpOverloadHours = cwPumpRows.filter(row => row.cw_pump_overload).length;
    const cwPumpClampedHours = cwPumpRows.filter(row => row.cw_pump_load_ratio_clamped_low || row.cw_pump_load_ratio_clamped_high).length;
    const energyRows = [
        ["IT Energy", annualEnergyBreakdown.annual_it_energy_kWh ?? annual.annual_IT_energy_kWh],
        ...Object.entries(annualEnergyBreakdown.components || {}).map(([key, data]) => [reportKeyLabel(key), data?.energy_kWh]),
        ["Facility Energy", annualEnergyBreakdown.annual_facility_energy_kWh ?? annual.annual_facility_energy_kWh]
    ].filter(([, value]) => Number(value) > 0);
    const energyChart = energyRows.length ? svgBarChart(energyRows.map(([label, value]) => ({
        label: label.replace(" Energy", "").replace("Electrical ", "Elec "),
        value: Number(value) / 1000,
        color: reportEnergyColor(label)
    })), { yLabel: "MWh", showValueLabels: true, valueLabelDigits: 0 }) : "";
    const annualResultCharts = [
        ...(energyChart ? [["Annual Energy Breakdown", energyChart]] : []),
        ...(monthlyPue.length ? [["Monthly Average PUE", svgBarChart(monthlyPue.map(row => ({ label: row.month, value: row.average_pue, color: REPORT_COLORS.pueLine })), { yLabel: "PUE", yTickCount: 5, yTickDigits: 2, barWidthScale: 0.86 })]] : [])
    ];
    const operatingCharts = [
        ...(pueSeries.length > 1 ? [["PUE Hourly Profile", svgLineChart(pueSeries, { yLabel: "PUE", xLabel: "Hour of Year", color: REPORT_COLORS.pueLine })]] : []),
        ...(facilityVsIt.length > 1 ? [["Facility Power vs IT Load", svgXYLineChart(facilityVsIt, { xLabel: "IT Load (kW)", yLabel: "Facility Power (kW)", color: REPORT_COLORS.coolingEnergy })]] : []),
        ...(report.visualization_data.temperature_vs_pue.length > 1 ? [["Outdoor Temperature vs PUE", svgXYLineChart(
            report.visualization_data.temperature_vs_pue.map(row => [row.temperature_C, row.pue]),
            { xLabel: "Outdoor Dry Bulb (deg C)", yLabel: "PUE", color: REPORT_COLORS.pueLine }
        )]] : [])
    ];
    const reportTitle = "Annual Data Center PUE Performance Assessment";
    const generated = new Date().toISOString();
    const coolingSystemDisplay = report.cooling_system_type || context.input?.cooling_system_type || "N/A";
    const scenarioName = output.project?.scenario_name || report.operating_scenario?.scenario_name || "Normal";
    const peakSummary = report.visualization_data.peak_summary;
    const peakDemandBreakdown = buildPeakDemandBreakdown(output, peakSummary);
    const reportAnnualEnergyRows = annualEquipmentEnergyRows(annual);
    const reportContextRows = engineeringContextRows(output, report, context.input || {});
    const alignmentAudit = getTimeAlignmentAudit(context.input?.project?.it_load || null, standardDataFiles.weather);
    const alignmentSummary = alignmentAudit.summary;
    const alignmentFirst = alignmentAudit.rows[0];
    const alignmentLast = alignmentAudit.rows[alignmentAudit.rows.length - 1];
    const peakDesignSource = String(peak.peak_design_weather_source || "").trim();
    const peakDesignDryBulbAvailable = peak.peak_design_outdoor_dry_bulb_C != null
        && peak.peak_design_outdoor_dry_bulb_C !== ""
        && Number.isFinite(Number(peak.peak_design_outdoor_dry_bulb_C));
    const peakDesignPueAvailable = peak.peak_PUE_definition === "peak_design"
        && peakDesignDryBulbAvailable
        && peak.peak_PUE != null
        && peak.peak_PUE !== ""
        && Number.isFinite(Number(peak.peak_PUE));
    const peakDesignIsManual = peakDesignSource.toLowerCase() === "manual";
    const peakDesignIsLocalCache = ["ashrae_local_cache", "ashrae_local_fallback"].includes(peakDesignSource.toLowerCase());
    const peakDesignIsOnline = ["ashrae_online", "ashrae_online_proxy"].includes(peakDesignSource.toLowerCase());
    const peakDesignSourceDisplay = peakDesignIsManual
        ? (peakDesignDryBulbAvailable ? "Manual Override" : "Unavailable")
        : (peakDesignIsLocalCache && peakDesignDryBulbAvailable
            ? "ASHRAE 20-year Extreme Design Condition (Local Cache)"
            : (peakDesignIsOnline && peakDesignDryBulbAvailable
                ? "ASHRAE 20-year Extreme Design Condition (Online)"
                : "Unavailable"));
    const peakDesignLookupDisplay = peakDesignIsManual
        ? (peakDesignDryBulbAvailable ? "Manual Override" : "Unavailable")
        : (peakDesignIsLocalCache && peakDesignDryBulbAvailable
            ? "Local Cache"
            : (peakDesignIsOnline && peakDesignDryBulbAvailable
                ? "Online"
                : "Unavailable"));
    const peakDesignWarning = !peakDesignDryBulbAvailable
        ? `Peak design condition is unavailable${peak.peak_design_lookup_failure_reason ? `: ${esc(peak.peak_design_lookup_failure_reason)}` : "."} Peak Design PUE cannot be substantiated as ASHRAE-based.`
        : "";
    const peakDesignFacilityPower = peak.peak_design_facility_electrical_demand_kW
        ?? peak.peak_design_total_facility_power_kW;
    const peakDesignEquipmentRows = [
        ["ACC Total Power, kW", peak.peak_design_ACC_power_kW],
        ["Chiller Total Power, kW", peak.peak_design_chiller_power_kW],
        ["Chiller COP", peak.peak_design_chiller_COP],
        ["Dry Cooler Total Power, kW", peak.peak_design_dry_cooler_power_kW],
        ["CHW Pump Power, kW", peak.peak_design_CHW_pump_power_kW],
        ["CW Pump Power, kW", peak.peak_design_CW_pump_power_kW],
        ["RTC Power, kW", peak.peak_design_RTC_power_kW],
        ["CDU Power, kW", peak.peak_design_CDU_power_kW],
        ["MAU Power, kW", peak.peak_design_MAU_power_kW],
        ["Engine Radiator Power, kW", peak.peak_design_engine_radiator_power_kW],
        ["Other Active Equipment Power, kW", peak.peak_design_other_electrical_auxiliary_power_kW],
        ["Electrical Loss, kW", peak.peak_design_electrical_loss_kW]
    ].filter(([, value]) => Number.isFinite(Number(value)))
        .map(([label, value]) => [label, reportValue(value, "", label === "Chiller COP" ? 3 : 1)]);
    const importedCurveRows = reportCurves.map(curve => [
        curve.category,
        esc(curve.curveId),
        esc(curve.sourceFile),
        curve.zAxis
            ? `${esc(curve.xAxis)} ${reportValue(curve.xMin, "", 2)}-${reportValue(curve.xMax, "", 2)}; ${esc(curve.yAxis)} ${reportValue(curve.yMin, "", 2)}-${reportValue(curve.yMax, "", 2)}; ${esc(curve.zAxis)} ${reportValue(curve.zMin, "", 2)}-${reportValue(curve.zMax, "", 2)}`
            : `${esc(curve.xAxis)} ${reportValue(curve.xMin, "", 2)}-${reportValue(curve.xMax, "", 2)}; ${esc(curve.yAxis)} ${reportValue(curve.yMin, "", 2)}-${reportValue(curve.yMax, "", 2)}`,
        esc(curve.pointCount)
    ]);
    const libraryCurveRows = report.equipment_curve_register.map(curve => [
        esc(curve.equipment_id),
        esc(curve.curve_source),
        esc(curve.curve_type),
        esc(curve.model_basis)
    ]);
    const performanceRows = report.equipment_performance || [];
    const coolingLoad = report.cooling_load_breakdown || {};
    const performanceCards = performanceRows.map(row => {
        const key = String(row.equipment || "").toLowerCase();
        const matchingCurve = (report.equipment_curve_register || []).find(curve => equipmentRoleFamily(curve.equipment_id) === equipmentRoleFamily(row.equipment));
        const modelDescription = matchingCurve && /ambient.*capacity/i.test(String(matchingCurve.curve_type || ""))
            ? "Ambient temperature and capacity lookup"
            : matchingCurve?.model_basis;
        const details = [
            ["Annual Energy", reportValue(row.annual_energy_kWh, " kWh", 0)],
            ...(row.performance_metric ? [[row.performance_metric, reportValue(row.metric_value, "", 3)]] : []),
            ...(Number.isFinite(Number(report.summary?.[`min_${key}_COP`])) ? [["Minimum COP", reportValue(report.summary[`min_${key}_COP`], "", 3)]] : []),
            ...(Number.isFinite(Number(report.summary?.[`max_${key}_COP`])) ? [["Maximum COP", reportValue(report.summary[`max_${key}_COP`], "", 3)]] : []),
            ...(modelDescription ? [["Performance Model", esc(modelDescription)]] : [])
        ];
        return `<div class="card"><h3>${esc(reportKeyLabel(row.equipment))} Performance</h3><table><tbody>${tableRows(details)}</tbody></table></div>`;
    });
    const pueContributionText = (value, signed = true) => {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return "N/A";
        const formatted = reportValue(numeric, "", 3);
        return signed && numeric >= 0 ? `+${formatted}` : formatted;
    };
    const engineeringConclusion = report.engineering_conclusion || buildEngineeringConclusion(report.capacity_validation || {});

    return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>${esc(reportTitle)}</title>
<style>
    :root { --ink:#222222; --muted:#555555; --line:#D8D8D8; --soft:#F7F7F7; --accent:#7A7A7A; }
    body { margin:0; font-family: Inter, "Times New Roman", Georgia, serif; color:var(--ink); background:#fff; }
    .page { max-width: 1260px; margin: 0 auto; padding: 28px 24px 46px; }
    header { border-bottom: 2px solid var(--ink); padding-bottom: 18px; margin-bottom: 18px; }
    h1 { margin:0 0 8px; font-size: 30px; line-height:1.15; letter-spacing: 0; font-weight:760; }
    h2 { margin:24px 0 10px; font-size: 19px; border-bottom: 1px solid var(--line); padding-bottom: 6px; font-weight:760; }
    h3 { margin:12px 0 8px; font-size: 15px; font-weight:740; }
    p { line-height: 1.65; color: var(--muted); text-align: justify; }
    table { border-collapse: collapse; width:100%; margin:8px 0 14px; font-size: 13px; }
    th, td { border:1px solid var(--line); padding:7px 8px; vertical-align:top; text-align:left; }
    th { background:var(--soft); font-weight:700; width:34%; }
    .meta, .grid, .curveGrid, .formulaGrid { display:grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap:12px; }
    .metric, .card, .formulaBox { border:1px solid var(--line); padding:12px; background:#fff; }
    .label, .subtitle, .caption, .note, .empty { color:var(--muted); font-size:12px; }
    .value { font-size:22px; font-weight:760; margin-top:4px; }
    .note, .empty { border-left:3px solid var(--accent); background:var(--soft); padding:10px 12px; margin:8px 0 12px; }
    .chart { width:100%; height:auto; }
    .axis, .gridline { stroke:#999; stroke-width:1; }
    .tick { fill:#666; font-size:10px; }
    .reportLogo { display:block; width:210px; height:auto; object-fit:contain; margin-bottom:0; }
</style>
</head>
<body>
<main class="page">
<header>
    <div class="reportHeaderTop">
        <img class="reportLogo" src="${SKYVAULT_REPORT_LOGO}" alt="SkyVault" />
    </div>
    <div class="pageHeaderLine">JUNO | Cooling System | Annual PUE Assessment</div>
    <h1>${esc(reportTitle)}</h1>
    <div class="subtitle">Project: JUNO</div>
    <div class="subtitle">Cooling Architecture: ${esc(coolingSystemDisplay)}</div>
    <div class="subtitle">Scenario: ${esc(scenarioName)}</div>
    <div class="subtitle">Generated: ${esc(generated)}</div>
</header>
<section>
    <h2>1. Engineering Summary</h2>
    <p>This assessment evaluates annual operating performance using the selected cooling configuration, weather data, equipment curves, and structured report sections returned by the report dispatcher.</p>
    <div class="meta">
        <div class="metric"><div class="label">Annual Average PUE</div><div class="value">${reportValue(annual.annual_average_PUE, "", 3)}</div></div>
        <div class="metric"><div class="label">Peak Design PUE</div><div class="value">${peakDesignPueAvailable ? reportValue(peak.peak_PUE, "", 3) : "N/A"}</div></div>
        <div class="metric"><div class="label">Maximum Hourly PUE</div><div class="value">${reportValue(peakSummary.max_hourly_pue, "", 3)}</div></div>
        <div class="metric"><div class="label">Annual Facility Energy</div><div class="value">${reportValue((annual.annual_facility_energy_kWh || 0) / 1000, " MWh", 0)}</div></div>
        <div class="metric"><div class="label">Annual Observed Peak Facility Demand</div><div class="value">${reportValue(peakSummary.peak_facility_power_kW, " kW", 1)}</div></div>
        <div class="metric"><div class="label">Peak Design Facility Demand</div><div class="value">${reportValue(peakDesignFacilityPower, " kW", 1)}</div></div>
        <div class="metric"><div class="label">Active Scenario</div><div class="value">${esc(scenarioName)}</div></div>
    </div>
    <div class="note">Annual Observed Peak Facility Demand is the maximum facility electrical demand observed during the annual hourly simulation using the IT load profile and EPW weather data. Peak Design Facility Demand is the facility electrical demand at 100% design IT load and the selected ASHRAE peak design outdoor condition.</div>
    ${peakDesignPueAvailable ? "" : `<div class="note">Peak Design PUE is unavailable because no valid peak design condition result was produced. Maximum Hourly PUE is reported separately and has not been substituted.</div>`}
    <h3>Configuration Context</h3>
    <table><tbody>${tableRows(reportContextRows.map(([label, value]) => [label, esc(value)]))}</tbody></table>
    <table><tbody>${tableRows([
        ["Site Location", esc(projectInfo.location || weatherSource.project_location || "N/A")],
        ["Cooling System Type", esc(coolingSystemDisplay)],
        ["Cooling Architecture", esc(solverTopology)],
        ["Report Configuration", esc(report.profile_id || "generic_pue")],
        ["Weather Source", esc(weatherSource.source || "N/A")]
    ])}</tbody></table>
</section>
<section>
    <h2>IT / Weather Time Alignment</h2>
    ${alignmentSummary ? `<table><tbody>${tableRows([
        ["Annual Rows", esc(alignmentSummary.annual_rows)],
        ["IT Load Time Basis", esc(alignmentSummary.it_time_basis)],
        ["Hour Sequence Validation", esc(alignmentSummary.hour_sequence_validation)],
        ["Calendar Time Basis", esc(alignmentSummary.calendar_time_basis)],
        ["Calendar Sequence Validation", esc(alignmentSummary.calendar_sequence_validation)],
        ["Calendar Hour Convention", esc(alignmentSummary.calendar_hour_convention)],
        ["IT / Weather Calendar Alignment", esc(alignmentSummary.weather_alignment)],
        ["EPW Hour Convention", esc(alignmentSummary.epw_hour_convention)],
        ["First Row Alignment", esc(alignmentFirst ? alignmentAuditRowCells(alignmentFirst).join(" | ") : "N/A")],
        ["Last Row Alignment", esc(alignmentLast ? alignmentAuditRowCells(alignmentLast).join(" | ") : "N/A")],
        ["Alignment Errors", esc(alignmentSummary.alignment_errors)]
    ])}</tbody></table><div class="note">Full hourly alignment audit available through CSV export.</div>` : '<div class="empty">Time alignment audit unavailable.</div>'}
</section>
<section>
    <h2>2. Energy &amp; PUE Summary</h2>
    <table><tbody>${tableRows([
        ["Annual Average PUE", reportValue(annual.annual_average_PUE, "", 3)],
        ["Annual IT Energy", engineeringEnergyDisplay(annual.annual_IT_energy_kWh)],
        ["Annual Facility Energy", engineeringEnergyDisplay(annual.annual_facility_energy_kWh)],
        [annualFacilityEnergySummary(outObj).label, engineeringEnergyDisplay(annualFacilityEnergySummary(outObj).energy_kWh)],
        ["Annual Electrical Distribution Loss", engineeringEnergyDisplay(annual.annual_electrical_loss_kWh)]
    ])}</tbody></table>
</section>
<section>
    <h2>3. Peak Facility Demand</h2>
    <table><tbody>${tableRows([
        ["Annual Observed Peak Facility Demand", reportValue(peakSummary.peak_facility_power_kW, " kW", 3)],
        ["Peak Hour", reportValue(peakSummary.peak_facility_hour, "", 0)],
        ["IT Load at Peak", reportValue(peakSummary.peak_it_load_kW, " kW", 1)],
        ["Outdoor DB at Peak", reportValue(peakSummary.peak_outdoor_dry_bulb_C, " deg C", 1)],
        ["Peak Design Facility Demand", reportValue(peakDesignFacilityPower, " kW", 3)],
        ["Design IT Load", reportValue(peak.peak_design_it_load_kW, " kW", 1)],
        ["Design Outdoor DB", reportValue(peak.peak_design_outdoor_dry_bulb_C, " deg C", 1)],
        ["Scenario", esc(scenarioName)]
    ])}</tbody></table>
</section>
<section>
    <h2>4. Annual Equipment Energy Breakdown</h2>
    <table><thead><tr><th>Component</th><th>Annual Energy</th><th>% of Facility Energy</th></tr></thead><tbody>${[
        ...reportAnnualEnergyRows,
        ["Total Facility Energy", annual.annual_facility_energy_kWh]
    ].map(([label, energy]) => `<tr><th>${esc(label)}</th><td>${engineeringEnergyDisplay(energy)}</td><td>${Number(annual.annual_facility_energy_kWh) > 0 ? reportValue(Number(energy) / Number(annual.annual_facility_energy_kWh) * 100, "%", 2) : "N/A"}</td></tr>`).join("")}</tbody></table>
</section>
<section>
    <h2>5. Peak Demand Breakdown</h2>
    <table><thead><tr><th>Component</th><th>Annual Observed Peak</th><th>Peak Design</th></tr></thead><tbody>${[
        ...peakDemandBreakdown.rows,
        ["Total Facility Demand", peakDemandBreakdown.annualTotal, peakDemandBreakdown.designTotal]
    ].map(([label, observed, design]) => `<tr><th>${esc(label)}</th><td>${reportValue(observed, " kW", 3)}</td><td>${reportValue(design, " kW", 3)}</td></tr>`).join("")}</tbody></table>
    <div class="note">Reconciliation: Annual ${peakDemandBreakdown.annualReconciles ? "PASS" : "ERROR"}; Peak Design ${peakDemandBreakdown.designReconciles ? "PASS" : "ERROR"}. ENGINE_3 generation output is excluded from facility electrical demand.</div>
</section>
<section>
    <h2>6. Equipment Performance</h2>
    ${performanceCards.length ? `<div class="grid">${performanceCards.join("")}</div>` : `<div class="empty">Equipment performance summary unavailable.</div>`}
    ${Number(annual.annual_engine_output_kWh) > 0 ? `<h3>Generation-Side Reference</h3><table><tbody>${tableRows([
        ["Annual Engine Output", engineeringEnergyDisplay(annual.annual_engine_output_kWh)],
        ["Annual Fuel Input", engineeringEnergyDisplay(annual.annual_engine_fuel_input_kWh)],
        ["Average Efficiency", reportValue(annual.average_engine_efficiency, "", 3)],
        ["Annual Waste Heat", engineeringEnergyDisplay(annual.annual_engine_waste_heat_kWh)]
    ])}</tbody></table>` : ""}
    <div class="note">ENGINE_3 is generation-side equipment and is excluded from Facility Demand and PUE electrical consumption.</div>
</section>
<section>
    <h2>7. Engineering / Calculation Notes</h2>
    <h3>Weather and Input Data</h3>
    <div class="grid">
        <div class="card"><h3>Weather Summary</h3><table><tbody>${tableRows([
            ["Dry Bulb Average", reportValue(drySummary?.avg, " deg C", 1)],
            ["Annual EPW Peak Dry-Bulb Temperature", reportValue(drySummary?.max, " deg C", 1)],
            ["Dry Bulb Minimum", reportValue(drySummary?.min, " deg C", 1)]
        ])}</tbody></table></div>
        <div class="card"><h3>Weather Source</h3><table><tbody>${tableRows([
            ["Annual Simulation Weather Source", `EPW / 8760-hour TMY data (${esc(weatherSource.source || "source unavailable")})`],
            ["EPW File", esc(weatherSource.epw_file || weather.source_file || "N/A")],
            ["Weather Data Period", esc(getWeatherPeriod(weather) || "N/A")]
        ])}</tbody></table></div>
    </div>
    <h3>Peak Design Condition</h3>
    <table><tbody>${tableRows([
        ["Peak Design Weather Source", esc(peakDesignSourceDisplay)],
        ["Peak Design Condition Source", esc(peakDesignSourceDisplay)],
        ["ASHRAE Station Name", esc(peak.peak_design_weather_station || "Not available")],
        ["ASHRAE Station ID", esc(peak.peak_design_weather_station_id || "Not available")],
        ["Design Outdoor Dry-Bulb Temperature, deg C", peakDesignDryBulbAvailable ? reportValue(peak.peak_design_outdoor_dry_bulb_C, "", 1) : "Not available"],
        ["Lookup Status", esc(peakDesignLookupDisplay)],
        ["Peak Design IT Load, kW", reportValue(peak.peak_design_it_load_kW, "", 1)],
        ["Peak Design Solar Heat Gain, kW", reportValue(peak.peak_design_solar_heat_gain_kW, "", 1)],
        ["Peak Design Other Auxiliary Heat Gain, kW", reportValue(peak.peak_design_other_auxiliary_heat_gain_kW, "", 1)],
        ["Peak Design Cooling Load, kW", reportValue(peak.peak_design_cooling_load_kW, "", 1)],
        ["Peak Design Facility Demand, kW", reportValue(peakDesignFacilityPower, "", 1)],
        ["Peak Design PUE", peakDesignPueAvailable ? reportValue(peak.peak_PUE, "", 3) : "N/A"],
        ...peakDesignEquipmentRows
    ])}</tbody></table>
    ${(peakDesignIsOnline || peakDesignIsLocalCache) && peakDesignDryBulbAvailable
        ? `<div class="note">Peak Design PUE is calculated at the ASHRAE 20-year extreme outdoor dry-bulb design condition and is independent of the maximum dry-bulb temperature contained in the annual EPW weather file.</div>`
        : (peakDesignIsManual && peakDesignDryBulbAvailable
            ? `<div class="note">Peak Design PUE is calculated using the displayed manual-override outdoor dry-bulb design condition and is independent of the maximum dry-bulb temperature contained in the annual EPW weather file.</div>`
            : "")}
    ${peakDesignWarning ? `<div class="note">${peakDesignWarning}</div>` : ""}
    ${tempDistribution ? temperatureDistributionTableHtml(tempDistribution) : `<div class="empty">Temperature distribution unavailable.</div>`}
    ${epwChartSection(weatherData)}
</section>
<section>
    <h3>Detailed Cooling System Performance</h3>
    ${performanceCards.length ? `<h3>Equipment Performance Summary</h3><div class="grid">${performanceCards.join("")}</div>` : ""}
    <h3>Cooling Load Breakdown</h3>
    <table><tbody>${tableRows([
        ["Annual IT Load", reportValue(coolingLoad.annual_it_load_kWh, " kWh", 3)],
        ["Annual Solar Heat Gain", reportValue(coolingLoad.annual_solar_heat_gain_kWh, " kWh", 3)],
        ["Annual Other Auxiliary Heat Gain", reportValue(coolingLoad.annual_other_auxiliary_heat_gain_kWh, " kWh", 3)],
        ["Annual Cooling Load", reportValue(coolingLoad.annual_cooling_load_kWh, " kWh", 3)]
    ])}</tbody></table>
    ${annualEnergyBreakdown.warnings?.length ? `<div class="note">${annualEnergyBreakdown.warnings.map(item => esc(item)).join("<br>")}</div>` : ""}
</section>
<section>
    <h3>Simulation Methodology</h3>
    <p>Hourly cooling loads combine IT load, solar heat gain, and other auxiliary heat gain. Equipment power is obtained from the selected Configuration Library performance lookup, and annual PUE is calculated from annual facility and IT energy.</p>
    <p>CHW Pump Load Ratio = Cooling Load per Active CHW Pump ÷ Fixed Single-CHW-Pump Reference Capacity.</p>
    <p>CW Pump Load Ratio = Heat Rejection Load per Active CW Pump ÷ Fixed Single-CW-Pump Reference Capacity.</p>
    <p>Normal and Failure use the same Solver_Curve for each pump type; only scenario-specific active pump counts change.</p>
    <p>Each hourly ratio uses a fixed single-pump reference capacity; it is not derived from peak load.</p>
    <p>Dry Cooler Power Model: Single-unit dry-cooler input power is determined from outdoor dry-bulb temperature using the DRYCOOLER_6 Solver_Curve. Total dry-cooler power equals per-unit curve power multiplied by active dry-cooler count.</p>
    <p>Engineering temperature-only power estimate based on the supplied dry-cooler capacity data and fan-affinity assumptions.</p>
    ${Number.isFinite(Number(annual.dry_cooler_curve_min_temperature_C)) ? `<h3>Dry Cooler Power Diagnostics</h3><table><tbody>${tableRows([
        ["Minimum Curve Temperature", reportValue(annual.dry_cooler_curve_min_temperature_C, " deg C", 1)],
        ["Maximum Curve Temperature", reportValue(annual.dry_cooler_curve_max_temperature_C, " deg C", 1)],
        ["Minimum Curve Power", reportValue(annual.dry_cooler_curve_min_power_kW, " kW", 2)],
        ["Rated Power Cap", reportValue(annual.dry_cooler_rated_power_cap_kW, " kW", 2)],
        ["Annual Dry Cooler Energy", reportValue(annual.annual_dry_cooler_energy_kWh, " kWh", 1)],
        ["Maximum Dry Cooler Total Power", reportValue(annual.max_dry_cooler_total_power_kW, " kW", 1)],
        ["Peak Design Dry Cooler Power", reportValue(peak.peak_design_dry_cooler_power_kW, " kW", 1)],
        ["Temperature Clamp Hours", esc(annual.dry_cooler_temperature_clamp_hours)]
    ])}</tbody></table>` : ""}
    ${pumpRows.length ? `<h3>Pump Annual Diagnostics</h3><table><tbody>${tableRows([
        ["Fixed Reference Capacity per Pump", reportValue(pumpReference, " kW", 1)],
        ["Active Pump Count", esc(pumpActiveCount)],
        ["Maximum Raw Pump Load Ratio", reportValue(pumpMaxRawRatio, "", 3)],
        ["Overload Hours", esc(pumpOverloadHours)],
        ["Clamped Hours", esc(pumpClampedHours)],
        ["Annual Pump Energy (CHW)", reportValue(annual.annual_chw_pump_energy_kWh ?? annual.annual_pump_energy_kWh, " kWh", 1)]
    ])}</tbody></table>` : ""}
    ${cwPumpRows.length ? `<h3>CW Pump Annual Diagnostics</h3><table><tbody>${tableRows([
        ["Fixed Reference Capacity per CW Pump", reportValue(cwPumpReference, " kW", 1)],
        ["Active CW Pump Count", esc(cwPumpActiveCount)],
        ["Maximum CW Pump Load Ratio", reportValue(cwPumpMaxRawRatio, "", 3)],
        ["CW Pump Overload Hours", esc(cwPumpOverloadHours)],
        ["CW Pump Clamped Hours", esc(cwPumpClampedHours)],
        ["Annual CW Pump Energy", reportValue(annual.annual_cw_pump_energy_kWh, " kWh", 1)]
    ])}</tbody></table>` : ""}
    ${formulasHtml()}
</section>
<section>
    <h3>Detailed Annual Performance Results</h3>
    <div class="grid">
        <div class="card"><h3>PUE Contribution Breakdown</h3><table class="breakdown"><thead><tr><th>Component</th><th>pPUE Contribution</th></tr></thead><tbody>${
            [["IT Base", 1], ...Object.entries(annualEnergyBreakdown.components || {}).map(([key, data]) => [`${reportKeyLabel(key)} pPUE`, (Number(data?.energy_kWh) || 0) / (Number(annual.annual_IT_energy_kWh) || 1)]), ["Annual PUE", annual.annual_average_PUE]]
                .map(([label, value]) => `<tr><td>${esc(label)}</td><td>${pueContributionText(value, label !== "IT Base" && label !== "Annual PUE")}</td></tr>`).join("")
        }</tbody></table></div>
        <div class="card"><h3>Key Findings</h3><p>Cooling, electrical, auxiliary, and future equipment contributions are derived from reported component rows.</p><table><tbody>${tableRows([
            ["Non-IT PUE Overhead", reportValue((Number(annual.annual_average_PUE) || 0) - 1, "", 3)],
            ["Reported Components", esc(Object.keys(annualEnergyBreakdown.components || {}).map(reportKeyLabel).join(", ") || "N/A")]
        ])}</tbody></table></div>
    </div>
    ${annualResultCharts.length ? `<div class="grid">${annualResultCharts.map(([title, chart]) => `<div class="card"><h3>${esc(title)}</h3>${chart}</div>`).join("")}</div>` : ""}
</section>
<section>
    <h3>Operating Characteristics</h3>
    ${operatingCharts.length ? `<div class="grid">${operatingCharts.map(([title, chart]) => `<div class="card"><h3>${esc(title)}</h3>${chart}</div>`).join("")}</div>` : ""}
</section>
<section>
    <h3>Engineering Conclusion</h3>
    <div class="note"><b>${esc(engineeringConclusion.status || "WARNING")}</b><br>${esc(engineeringConclusion.text || "Cooling capacity margin is limited under selected scenario.")}</div>
    <p>Values not produced by the solver are explicitly marked as contextual or not modeled.</p>
</section>
<section>
    <h2>Appendix A: Equipment Curve Register</h2>
    <p>Imported equipment parameter curves are retained here for technical traceability.</p>
    ${libraryCurveRows.length ? `<table><thead><tr><th>Equipment</th><th>Curve Source</th><th>Curve Type</th><th>Model Basis</th></tr></thead><tbody>${libraryCurveRows.map(row => `<tr>${row.map(cell => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody></table>`
    : (importedCurveRows.length ? `<table><thead><tr><th>Category</th><th>Curve ID</th><th>Source File</th><th>Domain / Range</th><th>Points</th></tr></thead><tbody>${importedCurveRows.map(row => `<tr>${row.map(cell => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody></table>` : "")}
    ${curveGroups.length ? `<div class="curveGrid">${curveGroups.map((group, index) => `<div class="card"><h3>Figure A-${index + 1}. ${esc(group.category)} input curves</h3>${svgCurveGroupChart(group)}<div class="caption">Input equipment curve set from ${esc(group.sourceFile)}.</div></div>`).join("")}</div>` : ""}
</section>
</main>
</body>
</html>`;
}

function buildLegacyHtmlReport(context) {
    return buildHtmlReportFromSections(context);
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

const TIME_ALIGNMENT_CSV_COLUMNS = Object.freeze([
    "Annual_Row", "Internal_Index", "IT_Hour_ID", "IT_Time_Basis", "IT_Calendar_Time_Basis",
    "IT_Timestamp", "IT_Month", "IT_Day", "IT_Hour", "IT_Hour_Convention",
    "EPW_Month", "EPW_Day", "EPW_Hour", "EPW_Hour_Convention", "IT_Load_Input",
    "IT_Load_Input_Unit", "IT_Load_kW", "Hour_ID_Status", "Calendar_Status",
    "Weather_Alignment_Status", "Overall_Alignment_Status"
]);

function alignmentTimestampDisplay(calendar, convention) {
    if (!calendar) return "Not Provided";
    const pad = value => String(value).padStart(2, "0");
    return convention === "0_23_clock_hour"
        ? `${pad(calendar.month)}-${pad(calendar.day)} ${pad(calendar.hour_of_day)}:00`
        : `${pad(calendar.month)}-${pad(calendar.day)} Hour ${pad(calendar.hour_of_day)}`;
}

function buildTimeAlignmentAudit(profile, weatherFile) {
    if (!profile || !Array.isArray(profile.hourly_it_load_kW)) return { rows: [], summary: null };
    const weather = weatherFile?.data || weatherFile?.hourly_data || {};
    const months = Array.isArray(weather.month) ? weather.month : [];
    const days = Array.isArray(weather.day) ? weather.day : [];
    const epwHours = Array.isArray(weather.epw_hour) ? weather.epw_hour : [];
    const rows = profile.hourly_it_load_kW.map((loadKw, index) => {
        const explicitHour = profile.has_explicit_hour_ids === true;
        const generatedHour = profile.time_basis === "generated_hour_of_year";
        const calendar = profile.has_explicit_calendar_ids ? profile.calendar_ids?.[index] : null;
        const hourStatus = explicitHour ? (profile.hour_sequence_valid ? "PASS" : "ERROR")
            : generatedHour ? "GENERATED" : "NOT PROVIDED";
        const calendarStatus = calendar ? (profile.calendar_sequence_valid ? "PASS" : "ERROR") : "NOT PROVIDED";
        const weatherStatus = calendar ? (profile.calendar_epw_match_valid ? "PASS" : "ERROR") : "NOT CHECKED";
        const overall = hourStatus === "ERROR" || calendarStatus === "ERROR" || weatherStatus === "ERROR" ? "ERROR"
            : profile.time_basis === "row_order_only" ? "WARNING — ROW ORDER ONLY"
            : generatedHour ? "PASS — GENERATED HOUR ID"
            : calendar && explicitHour ? "PASS"
            : calendar ? "PASS — CALENDAR" : "PASS — HOUR ID ONLY";
        const inputValue = profile.source_basis === "percent" ? profile.hourly_it_load_percent?.[index] : loadKw;
        return {
            annual_row: index + 1,
            internal_index: index,
            hour_of_year: index + 1,
            it_hour_id: explicitHour || generatedHour ? profile.hour_ids?.[index] ?? index + 1 : null,
            it_time_basis: profile.time_basis,
            it_calendar_time_basis: profile.calendar_time_basis || "none",
            it_timestamp_display: alignmentTimestampDisplay(calendar, profile.calendar_hour_convention),
            it_month: calendar?.month ?? null,
            it_day: calendar?.day ?? null,
            it_hour: calendar?.hour_of_day ?? null,
            it_calendar_hour_convention: profile.calendar_hour_convention || null,
            epw_month: months[index] ?? null,
            epw_day: days[index] ?? null,
            epw_hour: epwHours[index] ?? null,
            epw_hour_convention: "1_24_epw_hour",
            it_load_input: inputValue,
            it_load_input_unit: profile.source_basis === "percent" ? "%" : "kW",
            it_load_kW: Number(loadKw),
            hour_id_status: hourStatus,
            calendar_status: calendarStatus,
            weather_alignment_status: weatherStatus,
            overall_alignment_status: overall
        };
    });
    const errors = rows.filter(row => row.overall_alignment_status === "ERROR").length;
    return { rows, summary: {
        annual_rows: rows.length,
        it_time_basis: profile.time_basis,
        hour_sequence_validation: profile.hour_sequence_valid === false ? "ERROR" : explicitAuditHourStatus(profile),
        calendar_time_basis: profile.calendar_time_basis || "none",
        calendar_sequence_validation: profile.calendar_sequence_valid === true ? "PASS" : profile.calendar_sequence_valid === false ? "ERROR" : "NOT PROVIDED",
        calendar_hour_convention: profile.calendar_hour_convention || "N/A",
        weather_alignment: profile.calendar_epw_match_valid === true ? "PASS" : profile.calendar_epw_match_valid === false ? "ERROR" : "NOT CHECKED",
        epw_hour_convention: "1_24_epw_hour",
        first_annual_row: rows.length ? 1 : null,
        last_annual_row: rows.length || null,
        alignment_errors: errors,
        warning: profile.time_basis === "row_order_only" ? "Hour and calendar identifiers were not supplied; chronological alignment relies on file row order." : null
    }};
}

function explicitAuditHourStatus(profile) {
    if (profile.time_basis === "generated_hour_of_year") return "GENERATED";
    return profile.has_explicit_hour_ids ? "PASS" : "WARNING";
}

function getTimeAlignmentAudit(profile = null, weatherFile = standardDataFiles.weather) {
    const resolvedProfile = profile || lastReportContext?.input?.project?.it_load || configurationLibraryData?.it_load;
    const weatherData = weatherFile?.data || weatherFile?.hourly_data || {};
    const cacheKey = [resolvedProfile, weatherFile, resolvedProfile?.hourly_it_load_kW, resolvedProfile?.calendar_epw_match_valid, weatherData.month, weatherData.day, weatherData.epw_hour];
    if (timeAlignmentAuditCache && timeAlignmentAuditCache.key.every((value, index) => value === cacheKey[index])) return timeAlignmentAuditCache.audit;
    const audit = buildTimeAlignmentAudit(resolvedProfile, weatherFile);
    timeAlignmentAuditCache = { key: cacheKey, audit };
    return audit;
}

function csvSafeCell(value) {
    if (value === null || value === undefined) return "";
    const numeric = typeof value === "number";
    let text = numeric ? (Number.isFinite(value) ? String(value) : "") : String(value);
    if (!numeric && /^[=+\-@]/.test(text)) text = `'${text}`;
    return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function timeAlignmentAuditCsv(audit) {
    const field = {
        Annual_Row: "annual_row", Internal_Index: "internal_index", IT_Hour_ID: "it_hour_id", IT_Time_Basis: "it_time_basis",
        IT_Calendar_Time_Basis: "it_calendar_time_basis", IT_Timestamp: "it_timestamp_display", IT_Month: "it_month",
        IT_Day: "it_day", IT_Hour: "it_hour", IT_Hour_Convention: "it_calendar_hour_convention", EPW_Month: "epw_month",
        EPW_Day: "epw_day", EPW_Hour: "epw_hour", EPW_Hour_Convention: "epw_hour_convention", IT_Load_Input: "it_load_input",
        IT_Load_Input_Unit: "it_load_input_unit", IT_Load_kW: "it_load_kW", Hour_ID_Status: "hour_id_status",
        Calendar_Status: "calendar_status", Weather_Alignment_Status: "weather_alignment_status", Overall_Alignment_Status: "overall_alignment_status"
    };
    return [TIME_ALIGNMENT_CSV_COLUMNS.join(","), ...(audit?.rows || []).map(row => TIME_ALIGNMENT_CSV_COLUMNS.map(column => csvSafeCell(row[field[column]])).join(","))].join("\r\n");
}

function exportTimeAlignmentAuditCsv() {
    const audit = getTimeAlignmentAudit();
    if (!audit.rows.length) return setSolverDataStatus("No time alignment audit is available.", "error");
    const blob = new Blob(["\uFEFF", timeAlignmentAuditCsv(audit)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "IT_Weather_Time_Alignment_Audit.csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setSolverDataStatus(`CSV exported: ${audit.rows.length} alignment rows.`, "ok");
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

function validateItLoadHourSequence(rawHourIds, hours, hasExplicitHourIds) {
    const generated = Array.from({ length: hours }, (_, index) => index + 1);
    if (!hasExplicitHourIds) return {
        hour_ids: generated, has_explicit_hour_ids: false, time_basis: "row_order_only",
        hour_sequence_valid: true, hour_sequence_error: null,
        validation_warning: "Hour identifiers were not supplied; chronological alignment relies on file row order."
    };
    const ids = Array.isArray(rawHourIds) ? rawHourIds.map(value => {
        if (value === null || value === undefined || String(value).trim() === "") return null;
        const number = Number(value);
        return Number.isFinite(number) ? number : null;
    }) : [];
    let error = null;
    if (![8760, 8784].includes(hours)) error = `Explicit Hour_of_Year sequence must contain exactly 8760 or 8784 rows; received ${hours}.`;
    if (!error && ids.length !== hours) error = `Hour identifier count ${ids.length} does not match IT value count ${hours}.`;
    for (let index = 0; !error && index < ids.length; index += 1) {
        const found = ids[index];
        const expected = index + 1;
        if (!Number.isInteger(found)) {
            error = `Expected Hour ${expected} but found ${rawHourIds[index] === null || rawHourIds[index] === "" ? "blank" : String(rawHourIds[index])}; hour identifiers must be integers.`;
        } else if (found !== expected) {
            const seen = new Set();
            const firstDuplicate = ids.find(value => seen.has(value) || !seen.add(value));
            const present = new Set(ids.filter(Number.isInteger));
            const firstMissing = generated.find(value => !present.has(value));
            if (firstDuplicate !== undefined && firstMissing !== undefined) {
                error = `Invalid IT Load Profile: duplicate Hour_of_Year ${firstDuplicate} and missing Hour_of_Year ${firstMissing}.`;
            } else {
                error = `Expected Hour ${expected} but found Hour ${found}.`;
            }
        }
    }
    return {
        hour_ids: ids, has_explicit_hour_ids: true, time_basis: "hour_of_year",
        hour_sequence_valid: !error, hour_sequence_error: error, validation_warning: null
    };
}

function calendarDaysInMonth(month, leap) {
    return [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1] || 0;
}

function isLeapCalendarYear(year) {
    return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
}

function excelSerialCalendarParts(value) {
    const serial = Number(value);
    if (!Number.isFinite(serial)) return null;
    const wholeDays = Math.floor(serial);
    const milliseconds = Math.round((serial - wholeDays) * 86400000);
    const date = new Date(Date.UTC(1899, 11, 30) + wholeDays * 86400000 + milliseconds);
    return { year: date.getUTCFullYear(), month: date.getUTCMonth() + 1, day: date.getUTCDate(), hour: date.getUTCHours() };
}

function parseCalendarDateValue(value) {
    if (value instanceof Date && !Number.isNaN(value.getTime())) return { year: value.getFullYear(), month: value.getMonth() + 1, day: value.getDate() };
    if (typeof value === "number") {
        const parsed = excelSerialCalendarParts(value);
        return parsed && { year: parsed.year, month: parsed.month, day: parsed.day };
    }
    const text = String(value ?? "").trim();
    let match = text.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/);
    if (match) return { year: Number(match[1]), month: Number(match[2]), day: Number(match[3]) };
    match = text.match(/^(\d{1,2})[-/](\d{1,2})(?:[-/](\d{4}))?$/);
    return match ? { year: match[3] ? Number(match[3]) : null, month: Number(match[1]), day: Number(match[2]) } : null;
}

function parseCalendarTimeValue(value) {
    if (value instanceof Date && !Number.isNaN(value.getTime())) return value.getHours();
    if (typeof value === "number") {
        if (value >= 0 && value < 1) return Math.round(value * 24 * 60) / 60;
        return value;
    }
    const match = String(value ?? "").trim().match(/^(\d{1,2})(?::(\d{2}))?(?::\d{2}(?:\.\d+)?)?$/);
    if (!match || Number(match[2] || 0) !== 0) return null;
    return Number(match[1]);
}

function parseCalendarTimestampValue(value) {
    if (value instanceof Date && !Number.isNaN(value.getTime())) {
        return { year: value.getFullYear(), month: value.getMonth() + 1, day: value.getDate(), hour: value.getHours() };
    }
    if (typeof value === "number") return excelSerialCalendarParts(value);
    const text = String(value ?? "").trim();
    const match = text.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})[T\s](\d{1,2})(?::(\d{2}))?(?::\d{2}(?:\.\d+)?)?(?:\s*(?:Z|[+-]\d{2}:?\d{2}))?$/);
    if (!match || Number(match[5] || 0) !== 0) return null;
    return { year: Number(match[1]), month: Number(match[2]), day: Number(match[3]), hour: Number(match[4]) };
}

function expectedAnnualCalendar(hours, hourConvention) {
    const leap = hours === 8784;
    const rows = [];
    for (let month = 1; month <= 12; month += 1) {
        for (let day = 1; day <= calendarDaysInMonth(month, leap); day += 1) {
            for (let epwHour = 1; epwHour <= 24; epwHour += 1) {
                rows.push({ month, day, hour_of_day: hourConvention === "0_23_clock_hour" ? epwHour - 1 : epwHour });
            }
        }
    }
    return rows;
}

function validateItLoadCalendar(calendarInput, hours) {
    const none = {
        calendar_ids: [], has_explicit_calendar_ids: false, calendar_time_basis: "none",
        calendar_hour_convention: null, calendar_sequence_valid: null, calendar_sequence_error: null,
        calendar_validation_warning: "Calendar timestamps were not supplied; IT/weather alignment is validated by Hour-of-Year or row order.",
        calendar_epw_match_valid: null, calendar_epw_match_error: null
    };
    if (!calendarInput) return none;
    const basis = calendarInput.basis;
    const source = basis === "timestamp" ? calendarInput.timestamp
        : basis === "date_time" ? calendarInput.date
        : calendarInput.month;
    let error = ![8760, 8784].includes(hours) ? `Calendar sequence must contain exactly 8760 or 8784 rows; received ${hours}.` : null;
    if (!error && (!Array.isArray(source) || source.length !== hours)) error = `Calendar timestamp count does not match the ${hours}-row IT profile.`;
    if (!error && basis === "date_time" && (!Array.isArray(calendarInput.date) || !Array.isArray(calendarInput.time))) error = "Date and Time columns must both be supplied.";
    if (!error && basis === "month_day_hour" && (!Array.isArray(calendarInput.month) || !Array.isArray(calendarInput.day) || !Array.isArray(calendarInput.hour))) error = "Month, Day, and explicit Hour-of-Day columns must all be supplied.";
    const parsed = [];
    for (let index = 0; !error && index < hours; index += 1) {
        let item = null;
        if (basis === "timestamp") item = parseCalendarTimestampValue(calendarInput.timestamp[index]);
        if (basis === "date_time") {
            const date = parseCalendarDateValue(calendarInput.date[index]);
            const hour = parseCalendarTimeValue(calendarInput.time[index]);
            if (date && hour !== null) item = { ...date, hour };
        }
        if (basis === "month_day_hour") item = {
            year: Array.isArray(calendarInput.year) ? Number(calendarInput.year[index]) : null,
            month: Number(calendarInput.month[index]), day: Number(calendarInput.day[index]), hour: Number(calendarInput.hour[index])
        };
        if (!item || !Number.isInteger(item.month) || !Number.isInteger(item.day) || !Number.isInteger(item.hour)
            || (basis === "month_day_hour" && Array.isArray(calendarInput.year) && !Number.isInteger(item.year))) {
            error = `Invalid calendar timestamp at annual row ${index + 1}.`;
            break;
        }
        const leapForDate = item.year ? isLeapCalendarYear(item.year) : hours === 8784;
        if (item.month < 1 || item.month > 12 || item.day < 1 || item.day > calendarDaysInMonth(item.month, leapForDate)) {
            error = `Invalid calendar date at annual row ${index + 1}.`;
            break;
        }
        parsed.push(item);
    }
    const hoursSeen = parsed.map(item => item.hour);
    const hasZero = hoursSeen.includes(0);
    const has24 = hoursSeen.includes(24);
    let convention = null;
    if (!error && hasZero && !has24 && hoursSeen.every(hour => hour >= 0 && hour <= 23)) convention = "0_23_clock_hour";
    else if (!error && has24 && !hasZero && hoursSeen.every(hour => hour >= 1 && hour <= 24)) convention = "1_24_epw_hour";
    else if (!error) error = "Calendar hour convention is ambiguous or inconsistent; expected a complete 0–23 or 1–24 sequence.";
    const expected = convention ? expectedAnnualCalendar(hours, convention) : [];
    for (let index = 0; !error && index < parsed.length; index += 1) {
        const found = parsed[index];
        const wanted = expected[index];
        if (found.month !== wanted.month || found.day !== wanted.day || found.hour !== wanted.hour_of_day) {
            error = `Invalid IT Load Profile: calendar chronology mismatch at annual row ${index + 1}.`;
        }
    }
    const explicitYears = parsed.map(item => item.year).filter(year => Number.isInteger(year));
    if (!error && explicitYears.length) {
        const year = explicitYears[0];
        if (explicitYears.length !== parsed.length || explicitYears.some(value => value !== year)) error = "Calendar year values must be present and consistent for every row.";
        else if (isLeapCalendarYear(year) !== (hours === 8784)) error = `Calendar year ${year} is incompatible with a ${hours}-hour profile.`;
    }
    return {
        calendar_ids: parsed.map(item => ({ month: item.month, day: item.day, hour_of_day: item.hour })),
        has_explicit_calendar_ids: true, calendar_time_basis: basis, calendar_hour_convention: convention,
        calendar_sequence_valid: !error, calendar_sequence_error: error, calendar_validation_warning: null,
        calendar_epw_match_valid: null, calendar_epw_match_error: null
    };
}

function validateItCalendarAgainstEpw(profile, weatherFile) {
    if (!profile?.has_explicit_calendar_ids) return { calendar_epw_match_valid: null, calendar_epw_match_error: null };
    if (profile.calendar_sequence_valid !== true) return { calendar_epw_match_valid: false, calendar_epw_match_error: profile.calendar_sequence_error };
    const weather = weatherFile?.data || weatherFile?.hourly_data || {};
    const months = weather.month;
    const days = weather.day;
    const hours = weather.epw_hour;
    if (!Array.isArray(months) || !Array.isArray(days) || !Array.isArray(hours)) {
        return { calendar_epw_match_valid: false, calendar_epw_match_error: "Loaded weather does not expose EPW calendar fields for timestamp cross-validation." };
    }
    if (months.length !== profile.hours || days.length !== profile.hours || hours.length !== profile.hours) {
        return { calendar_epw_match_valid: false, calendar_epw_match_error: `IT calendar has ${profile.hours} rows but EPW calendar has ${months.length} rows.` };
    }
    for (let index = 0; index < profile.calendar_ids.length; index += 1) {
        const it = profile.calendar_ids[index];
        const itEpwHour = profile.calendar_hour_convention === "0_23_clock_hour" ? it.hour_of_day + 1 : it.hour_of_day;
        if (it.month !== Number(months[index]) || it.day !== Number(days[index]) || itEpwHour !== Number(hours[index])) {
            const pad = value => String(value).padStart(2, "0");
            return {
                calendar_epw_match_valid: false,
                calendar_epw_match_error: `Invalid IT Load Profile: calendar alignment mismatch at annual row ${index + 1}. IT timestamp is ${pad(it.month)}-${pad(it.day)} Hour ${pad(itEpwHour)}, but EPW timestamp is ${pad(months[index])}-${pad(days[index])} Hour ${pad(hours[index])}.`
            };
        }
    }
    return { calendar_epw_match_valid: true, calendar_epw_match_error: null };
}

function canonicalItLoadProfile({ hourlyKw, hourlyPercent = null, hourIds = null, hasExplicitHourIds = false, timeBasis = null, calendarInput = null, designItKw, sourceType, sourceName, sourceBasis = "kW" }) {
    const kw = Array.isArray(hourlyKw) ? hourlyKw.map(Number) : [];
    const percent = Array.isArray(hourlyPercent)
        ? hourlyPercent.map(Number)
        : kw.map(value => designItKw > 0 ? value / designItKw * 100 : null);
    const errors = [];
    if (![8760, 8784].includes(kw.length)) errors.push(`expected 8760 or 8784 hourly rows; received ${kw.length}`);
    if (kw.some(value => !Number.isFinite(value))) errors.push("all hourly IT values must be numeric");
    if (kw.some(value => value < 0)) errors.push("hourly IT values must not be negative");
    const sequence = validateItLoadHourSequence(hourIds, kw.length, hasExplicitHourIds);
    const calendar = validateItLoadCalendar(calendarInput, kw.length);
    if (timeBasis === "generated_hour_of_year") sequence.validation_warning = null;
    if (!sequence.hour_sequence_valid) errors.push(sequence.hour_sequence_error);
    if (calendar.calendar_sequence_valid === false) errors.push(calendar.calendar_sequence_error);
    const overloadHours = designItKw > 0 ? kw.filter(value => value > designItKw).length : 0;
    const valid = errors.length === 0;
    const averageKw = kw.length ? kw.reduce((sum, value) => sum + value, 0) / kw.length : null;
    return {
        design_it_load_kW: designItKw,
        source_type: sourceType,
        source_name: sourceName,
        source_basis: sourceBasis,
        hours: kw.length,
        hourly_it_load_kW: kw,
        hourly_it_load_percent: percent,
        hour_ids: sequence.hour_ids,
        has_explicit_hour_ids: sequence.has_explicit_hour_ids,
        time_basis: timeBasis || sequence.time_basis,
        hour_sequence_valid: sequence.hour_sequence_valid,
        hour_sequence_error: sequence.hour_sequence_error,
        validation_warning: sequence.validation_warning,
        calendar_input: calendarInput,
        ...calendar,
        validation_status: valid ? (overloadHours ? "valid_with_overload_warning" : "valid") : "error",
        validation_errors: errors,
        overload_hours: overloadHours,
        average_kW: averageKw,
        average_ratio: averageKw !== null && designItKw > 0 ? averageKw / designItKw : null,
        min_kW: kw.length ? Math.min(...kw) : null,
        max_kW: kw.length ? Math.max(...kw) : null
    };
}

function canonicalItLoadFromPercent(percentages, designItKw, sourceType, sourceName, timeOptions = {}) {
    const values = Array.isArray(percentages) ? percentages.map(Number) : [];
    return canonicalItLoadProfile({
        hourlyKw: values.map(value => designItKw * value / 100),
        hourlyPercent: values,
        designItKw,
        sourceType,
        sourceName,
        sourceBasis: "percent",
        ...timeOptions
    });
}

function refreshCanonicalItLoadForCapacity(profile, designItKw) {
    if (!profile) return null;
    let refreshed;
    if (profile.source_basis === "percent") {
        refreshed = canonicalItLoadFromPercent(profile.hourly_it_load_percent, designItKw, profile.source_type, profile.source_name, {
            hourIds: profile.hour_ids, hasExplicitHourIds: profile.has_explicit_hour_ids, timeBasis: profile.time_basis,
            calendarInput: profile.calendar_input || null
        });
    } else {
        refreshed = canonicalItLoadProfile({
            hourlyKw: profile.hourly_it_load_kW,
            designItKw,
            sourceType: profile.source_type,
            sourceName: profile.source_name,
            sourceBasis: "kW",
            hourIds: profile.hour_ids,
            hasExplicitHourIds: profile.has_explicit_hour_ids,
            timeBasis: profile.time_basis,
            calendarInput: profile.calendar_input || null
        });
    }
    refreshed.calendar_epw_match_valid = profile.calendar_epw_match_valid ?? refreshed.calendar_epw_match_valid;
    refreshed.calendar_epw_match_error = profile.calendar_epw_match_error ?? refreshed.calendar_epw_match_error;
    return refreshed;
}

function renderItLoadProfileStatus(profile = configurationLibraryData?.it_load) {
    const target = document.getElementById("itLoadProfileStatus");
    if (!target) return;
    if (!profile) {
        target.innerHTML = '<span style="color:#dc2626;">IT Load Profile Not Ready</span>';
        return;
    }
    const ready = profile.validation_status === "valid" || profile.validation_status === "valid_with_overload_warning";
    const warning = profile.overload_hours ? `; overload hours: ${profile.overload_hours}` : "";
    const timeDetail = profile.has_explicit_hour_ids || profile.time_basis === "generated_hour_of_year"
        ? `Hour sequence: ${profile.hour_sequence_valid ? `Valid (1–${profile.hours})` : "Error"}`
        : "Time basis: Row Order<br>Warning: No Hour_of_Year column supplied.";
    const calendarDetail = profile.has_explicit_calendar_ids
        ? `Calendar: ${profile.calendar_sequence_valid ? "Valid" : "Error"} (${esc(profile.calendar_time_basis)}; ${esc(profile.calendar_hour_convention || "undetermined")})<br>` +
            `IT / EPW alignment: ${profile.calendar_epw_match_valid === true ? "PASS" : profile.calendar_epw_match_valid === false ? "ERROR" : "PENDING"}`
        : "Calendar: Not Provided";
    target.innerHTML = `<b style="color:${ready ? "#059669" : "#dc2626"};">${ready ? "✓ Loaded" : "✕ Invalid"}</b><br>` +
        `Source: ${esc(profile.source_name || profile.source_type || "Unknown")}<br>` +
        `Hours: ${profile.hours || 0}; Average: ${fmtNumber(profile.average_kW, 1)} kW (${fmtNumber((profile.average_ratio || 0) * 100, 1)}%); ` +
        `Min/Max: ${fmtNumber(profile.min_kW, 1)} / ${fmtNumber(profile.max_kW, 1)} kW${esc(warning)}<br>${timeDetail}<br>${calendarDetail}` +
        `${profile.validation_errors?.length ? `<br>${esc(profile.validation_errors.join("; "))}` : ""}`;
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
    phase19bTrace("prepareSolverJob:start", {
        ashrae_top: rawInput?.ashrae_design_conditions_url,
        ashrae_project: rawInput?.project?.ashrae_design_conditions_url,
        run_mode: rawInput?.run_mode,
        acc_v2_configuration_path: rawInput?.acc_v2?.configuration_path,
        has_project: Boolean(rawInput?.project),
        has_weather: Boolean(rawInput?.weather)
    });
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
    phase19bTrace("prepareSolverJob:after normalizeAnnualProjectInput", {
        ashrae_top: normalizedInput?.ashrae_design_conditions_url,
        ashrae_project: normalizedInput?.project?.ashrae_design_conditions_url,
        hourlyItCount: normalizedProject.hourlyItCount,
        weatherCount: normalizedProject.weatherCount,
        isProject: normalizedProject.isProject
    });
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
        const job = {
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
        phase19bTrace("prepareSolverJob:return project", {
            solverFn: job.solverFn,
            ashrae_top: job.input?.ashrae_design_conditions_url,
            ashrae_project: job.input?.project?.ashrae_design_conditions_url,
            itHours: hourlyIt.length,
            weatherHours: dryBulb.length
        });
        return job;
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

function resetAutomaticEpwBindingState() {
    automaticEpwReady = false;
    standardDataFiles.weather = null;
    standardSolverInput = null;
    updateFileStatus("statusWeather", "Climate Station: Waiting for Configuration Library loading", "info");
    setAutoEpwStatus("Weather Data: Waiting for Configuration Library loading", "info");
    const modeStatus = document.getElementById("automaticEpwModeStatus");
    if (modeStatus) modeStatus.textContent = "Automatic EPW Matching";
    refreshSimulationReadiness();
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
    automaticEpwReady = weatherHours === 8760 || weatherHours === 8784;
    standardSolverInput = null;
    preferStandardFiles = true;
    updateFileStatus("statusWeather", `Climate Station: ${match.station || match.city} / ${match.source || "Local EPW"}`, "ok");
    const modeStatus = document.getElementById("automaticEpwModeStatus");
    if (modeStatus) modeStatus.textContent = automaticEpwReady ? "✓ Automatic EPW Matching" : "Automatic EPW Matching";
    if (weatherHours !== 8760 && weatherHours !== 8784) {
        setAutoEpwStatus(`Weather Data: EPW loaded, but weather hours are unusual: ${weatherHours}`, "error");
    } else {
        setAutoEpwStatus(`Weather Data: ${weatherHours} hourly weather loaded`, "ok");
    }
    previewInputCurves(standardDataFiles);
    renderWeatherReportPanel();
    renderTemperatureDistributionPanel();
    refreshStandardInputStatus();
    setRunButtonsDisabled(false);
    return json;
}

async function autoMatchLocalEpw() {
    const locationInput = document.getElementById("projectLocationInput");
    const locationText = locationInput ? locationInput.value.trim() : "";
    const coordinates = readProjectCoordinates();
    const resetWeatherStatusAfterMiss = () => {
        automaticEpwReady = false;
        updateFileStatus("statusWeather", "Climate Station: EPW match unavailable", "error");
        refreshSimulationReadiness();
    };
    updateFileStatus("statusWeather", "Matching local EPW...", "info");
    setAutoEpwStatus("", "info");
    if (!coordinates) {
        resetWeatherStatusAfterMiss();
        setAutoEpwStatus("Please enter valid Latitude and Longitude for EPW matching.", "error");
        return false;
    }
    try {
        let epwIndex = await loadLocalEpwIndex();
        let match = findNearestLocalEpwByCoordinates(coordinates.latitude, coordinates.longitude, epwIndex);
        if (match && match.epw_path) {
            await applyMatchedEpw(match, locationText, coordinates);
            return automaticEpwReady;
        }

        setAutoEpwStatus("No local EPW matched. Searching online EPW...", "info");
        const onlineResult = await fetchOnlineEpw(coordinates.latitude, coordinates.longitude, locationText);
        if (!onlineResult || !onlineResult.success) {
            resetWeatherStatusAfterMiss();
            setAutoEpwStatus("No suitable online EPW found. Check the local EPW library or EPW API service.", "error");
            return false;
        }

        epwIndex = await loadLocalEpwIndex();
        match = findNearestLocalEpwByCoordinates(coordinates.latitude, coordinates.longitude, epwIndex);
        if (!match || !match.epw_path) {
            resetWeatherStatusAfterMiss();
            setAutoEpwStatus("Online EPW downloaded, but the local EPW index did not match.", "error");
            return false;
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
        return automaticEpwReady;
    } catch (e) {
        resetWeatherStatusAfterMiss();
        setAutoEpwStatus("Local EPW not found. Start the EPW API server or check the local EPW library.", "error");
        return false;
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
        const ready = Boolean(configurationLibraryData && dry);
        el.textContent = ready
            ? "输入就绪：设备模型由 Configuration Library 自动加载，天气数据和冷却负荷修正参数已准备完成，点击运行计算执行年度PUE模拟。 Input ready: Equipment models are automatically loaded from Configuration Library. Weather data and cooling load adjustment parameters are prepared. Click Run Simulation to execute annual PUE calculation."
            : `等待输入：Configuration Library=${configurationLibraryData ? "已加载" : "未加载"}，天气=${dry ? `${dry.length}小时` : "未加载"}。`;
        el.style.color = ready ? "#059669" : "#6b7280";
    }
}

async function handleStandardFile(slot, statusId, file) {
    try {
        const json = window.PueImportAdapter
            ? await window.PueImportAdapter.adaptFile(slot, file)
            : await readJsonFile(file);
        if (json && typeof json === "object") json.source_file = file.name;
        const uploadedRawKw = slot === "itLoad" ? (getPath(json, ["data", "hourly_it_load_kW"]) ?? getPath(json, ["hourly_it_load_kW"])) : null;
        const uploadedRawPercent = slot === "itLoad" ? (getPath(json, ["data", "hourly_it_load_percent"]) ?? getPath(json, ["hourly_it_load_percent"])) : null;
        const uploadedItHadKw = Array.isArray(uploadedRawKw);
        if (slot === "itLoad") {
            normalizeItLoadPercentFile(json);
            const designItKw = projectDesignCapacityKw();
            const hourlyKw = uploadedItHadKw ? uploadedRawKw : [];
            const hourlyPercent = Array.isArray(uploadedRawPercent) ? uploadedRawPercent : [];
            const uploadedHourIds = getPath(json, ["data", "hour_index"]) ?? getPath(json, ["hour_ids"]);
            const timeOptions = {
                hourIds: uploadedHourIds,
                hasExplicitHourIds: json.has_explicit_hour_ids === true || Array.isArray(uploadedHourIds),
                calendarInput: getPath(json, ["data", "calendar_input"]) || null
            };
            projectItLoadProfileOverride = uploadedItHadKw
                ? canonicalItLoadProfile({ hourlyKw, designItKw, sourceType: "user_uploaded", sourceName: `User Uploaded — ${file.name}`, sourceBasis: "kW", ...timeOptions })
                : canonicalItLoadFromPercent(hourlyPercent, designItKw, "user_uploaded", `User Uploaded — ${file.name}`, timeOptions);
            if (projectItLoadProfileOverride.validation_status === "error") {
                throw new Error(`IT Load Profile Upload Failed: ${projectItLoadProfileOverride.validation_errors.join("; ")}`);
            }
            if (configurationLibraryData) {
                configurationLibraryData.it_load = projectItLoadProfileOverride;
                configurationLibraryData.standardized_solver_input = buildFrontendSolverInputFromLibrary(configurationLibraryData);
            }
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
        if (slot === "itLoad") renderItLoadProfileStatus(projectItLoadProfileOverride);
        refreshSimulationReadiness();
    } catch (e) {
        if (slot === "itLoad") {
            projectItLoadProfileOverride = {
                design_it_load_kW: projectDesignCapacityKw(), source_type: "user_uploaded",
                source_name: `User Uploaded — ${file?.name || "unknown file"}`, source_basis: "unknown",
                hours: 0, hourly_it_load_kW: [], hourly_it_load_percent: [], validation_status: "error",
                hour_ids: [], has_explicit_hour_ids: false, time_basis: "unknown", hour_sequence_valid: false,
                hour_sequence_error: String(e.message || e), validation_warning: null,
                validation_errors: [String(e.message || e)], overload_hours: 0,
                average_kW: null, average_ratio: null, min_kW: null, max_kW: null
            };
            if (configurationLibraryData) configurationLibraryData.it_load = projectItLoadProfileOverride;
        }
        standardDataFiles[slot] = null;
        standardSolverInput = null;
        preferStandardFiles = true;
        updateFileStatus(statusId, `读取失败：${String(e.message || e)}`, "error");
        renderCoolingSystemSelection();
        refreshStandardInputStatus();
        if (slot === "itLoad") renderItLoadProfileStatus(projectItLoadProfileOverride);
        refreshSimulationReadiness();
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
const CONFIGURATION_LIBRARY_INDEX_URL = new URL("configuration_library_index.json", CONFIGURATION_LIBRARY_ROOT_URL);

function configurationStatusLabel(status) {
    const labels = {
        implemented: "Available",
        test_only: "Test Only",
        framework_ready_data_missing: "Framework Ready / Data Missing",
        placeholder: "Planned",
        disabled: "Disabled"
    };
    return labels[status] || "Unavailable";
}

function topologyStatusForManifest(manifest) {
    const topologyId = manifest?.solver_topology || manifest?.topology_id;
    return CONFIGURATION_TOPOLOGY_STATUS[topologyId] || {
        display: topologyId || "Unknown",
        status: "unknown",
        adapter: null
    };
}

function isConfigurationManifestRunnable(manifest) {
    const topology = topologyStatusForManifest(manifest);
    return manifest?.implementation_status === "implemented"
        && topology.status === "implemented"
        && Boolean(topology.adapter);
}

function configurationLibraryLoadMode(manifest) {
    return manifest?.solver_topology === "acc_gas_engine_cdu" ? "legacy" : "manifest";
}

async function loadConfigurationLibraryCatalog() {
    const status = document.getElementById("configurationLibraryStatus");
    const select = document.getElementById("configurationLibrarySelect");
    try {
        const response = await fetch(CONFIGURATION_LIBRARY_INDEX_URL, { cache: "no-store" });
        if (!response.ok) throw new Error(`Could not load ${CONFIGURATION_LIBRARY_INDEX_URL.href} (HTTP ${response.status}).`);
        const index = await response.json();
        const entries = Array.isArray(index.configurations) ? index.configurations : [];
        configurationLibraryCatalog = await Promise.all(entries.map(async entry => {
            const manifestPath = entry.manifest_path || `${entry.configuration_id}/configuration_manifest.json`;
            const manifestUrl = new URL(configurationLibraryFetchPath(manifestPath), CONFIGURATION_LIBRARY_ROOT_URL);
            const manifestResponse = await fetch(manifestUrl, { cache: "no-store" });
            if (!manifestResponse.ok) throw new Error(`Could not load ${manifestUrl.href} (HTTP ${manifestResponse.status}).`);
            const manifest = await manifestResponse.json();
            return {
                ...manifest,
                manifest_path: manifestPath,
                runnable: isConfigurationManifestRunnable(manifest)
            };
        }));
        renderConfigurationLibraryCatalog();
        if (status && configurationLibraryCatalog.length) {
            status.textContent = `Configuration Library catalog loaded: ${configurationLibraryCatalog.length} manifest(s).`;
            status.style.color = "#374151";
        }
    } catch (error) {
        configurationLibraryCatalog = [];
        if (select) {
            select.innerHTML = `<option value="">Configuration catalog unavailable</option>`;
        }
        if (status) {
            status.textContent = `Configuration Library catalog load failed: ${String(error.message || error)}`;
            status.style.color = "#dc2626";
        }
    }
}

function renderConfigurationLibraryCatalog() {
    const select = document.getElementById("configurationLibrarySelect");
    if (!select) return;
    if (!configurationLibraryCatalog.length) {
        select.innerHTML = `<option value="">No Configuration Library manifests found</option>`;
        return;
    }
    select.innerHTML = configurationLibraryCatalog.map(manifest => {
        const statusLabel = configurationStatusLabel(manifest.implementation_status);
        const topology = topologyStatusForManifest(manifest);
        const label = `${manifest.display_name || manifest.configuration_id} — Topology: ${topology.display} (${statusLabel})`;
        return `<option value="${esc(manifest.configuration_id)}" ${manifest.runnable ? "" : "disabled"}>${esc(label)}</option>`;
    }).join("");
    const firstRunnable = configurationLibraryCatalog.find(item => item.runnable);
    if (firstRunnable) select.value = firstRunnable.configuration_id;
}

function selectedConfigurationManifest() {
    const select = document.getElementById("configurationLibrarySelect");
    const configurationId = select?.value || "";
    return configurationLibraryCatalog.find(item => item.configuration_id === configurationId) || null;
}

function manifestEquipmentRoleIds(manifest) {
    const roles = manifest?.equipment_roles || {};
    return [...new Set(Object.values(roles).flatMap(value => Array.isArray(value) ? value : [value]).filter(Boolean).map(String))];
}

function roleValueFromManifest(manifest, roleName, required = true) {
    const roles = manifest?.equipment_roles || {};
    const requiredRoles = new Set(manifest?.required_roles || []);
    const optionalRoles = new Set(manifest?.optional_roles || []);
    const roleValue = roles[roleName];
    if (roleValue === undefined || roleValue === null || roleValue === "" || (Array.isArray(roleValue) && !roleValue.length)) {
        if (!required || (optionalRoles.has(roleName) && !requiredRoles.has(roleName))) {
            console.log(`[Configuration Library] Optional equipment role not configured: ${roleName}`);
            return null;
        }
        throw new Error(`Configuration manifest is missing required equipment role: ${roleName}`);
    }
    return roleValue;
}

function equipmentRoleFamily(equipmentId) {
    const family = equipmentCurveFamily(resolveFrontendEquipmentId(equipmentId));
    if (family.includes("CHILLER")) return "CHILLER";
    if (family === "DRYCOOLER" || family.includes("DRY_COOLER")) return "DRY_COOLER";
    return family;
}

function resolveEquipmentRoleIdFromMapping(manifest, roleName, mapping, required = true) {
    const roleValue = roleValueFromManifest(manifest, roleName, required);
    if (roleValue === null) return null;
    if (Array.isArray(roleValue)) {
        return roleValue.map(equipmentId => resolveDeclaredEquipmentIdFromMapping(manifest, roleName, equipmentId, mapping));
    }
    return resolveDeclaredEquipmentIdFromMapping(manifest, roleName, roleValue, mapping);
}

function resolveDeclaredEquipmentIdFromMapping(manifest, roleName, declaredEquipmentId, mapping) {
    const configurationId = manifest?.configuration_id || "unknown";
    const declared = String(declaredEquipmentId);
    if (Object.prototype.hasOwnProperty.call(mapping || {}, declared)) return declared;
    const aliasResolved = resolveFrontendEquipmentId(declared);
    if (Object.prototype.hasOwnProperty.call(mapping || {}, aliasResolved)) return aliasResolved;
    const declaredFamily = equipmentRoleFamily(declared);
    const matches = Object.keys(mapping || {}).filter(equipmentId => equipmentRoleFamily(equipmentId) === declaredFamily);
    if (matches.length === 1) return matches[0];
    if (matches.length > 1) {
        throw new Error(`Configuration ${configurationId} role ${roleName}=${declared} is ambiguous: ${matches.join(", ")}`);
    }
    throw new Error(`Configuration ${configurationId} role ${roleName} references missing equipment ${declared}`);
}

function validateFrontendConfigurationLibrary(data) {
    const manifest = data?.configuration_manifest || {};
    const selectedCurves = data?.selected_curves || data?.standardized_solver_input?.selected_curves || {};
    const missingRoles = [];
    const missingCurves = [];
    const warnings = [];
    ["configuration_id", "cooling_system_type", "solver_topology"].forEach(field => {
        if (!manifest[field]) warnings.push(`Manifest missing required field: ${field}`);
    });
    const topology = topologyStatusForManifest(manifest);
    if (!CONFIGURATION_TOPOLOGY_STATUS[manifest.solver_topology]) {
        warnings.push(`Unknown solver_topology: ${manifest.solver_topology || "<missing>"}`);
    }
    (manifest.required_roles || []).forEach(roleName => {
        let roleIds;
        try {
            roleIds = resolveEquipmentRoleIdFromMapping(manifest, roleName, selectedCurves);
        } catch (error) {
            missingRoles.push(roleName);
            warnings.push(String(error.message || error));
            return;
        }
        (Array.isArray(roleIds) ? roleIds : [roleIds]).forEach(equipmentId => {
            const packageItem = findLibraryEquipmentPackage(data, equipmentId).equipmentPackage;
            const selected = selectedCurves[equipmentId] || {};
            const metadata = packageItem?.equipment_metadata;
            if (!metadata) {
                warnings.push(`${equipmentId}: equipment_metadata.json is missing`);
            } else {
                if (metadata.equipment_id && metadata.equipment_id !== packageItem.equipment_id) {
                    warnings.push(`${equipmentId}: equipment_metadata equipment_id does not match loaded equipment folder`);
                }
                ["equipment_id", "equipment_type", "display_name", "curve_type", "unit_system", "status"].forEach(field => {
                    if (metadata[field] === null || metadata[field] === undefined || metadata[field] === "") {
                        warnings.push(`${equipmentId}: equipment_metadata missing ${field}`);
                    }
                });
            }
            const hasCurve = selected.electrical_path
                || selected.status === "Electrical Path Found"
                || (selected.status === "Selected" && selected.sheet_name);
            if (!packageItem || packageItem.status === "Missing" || !hasCurve) {
                missingCurves.push(`${roleName}=${equipmentId}`);
            }
        });
    });
    return {
        status: (missingRoles.length || missingCurves.length || warnings.length) ? "error" : "valid",
        configuration_id: manifest.configuration_id || data?.configuration_id || data?.configuration_name || "",
        topology: manifest.solver_topology || data?.topology_id || "",
        topology_display: topology.display,
        missing_roles: missingRoles,
        missing_curves: missingCurves,
        warnings
    };
}

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

async function fetchConfigurationLibraryJson(relativePath) {
    const jsonUrl = new URL(configurationLibraryFetchPath(relativePath), CONFIGURATION_LIBRARY_ROOT_URL);
    const response = await fetch(jsonUrl, { cache: "no-store" });
    if (!response.ok) throw new Error(`Could not load ${jsonUrl.href} (HTTP ${response.status}).`);
    return response.json();
}

function configurationLibraryPyodidePath(configurationName) {
    return `${CONFIGURATION_LIBRARY_PYODIDE_ROOT}/${configurationName}`;
}

function buildConfigurationLibraryWorkbookSyncPlan(data) {
    const configurationName = data?.configuration_name;
    const roleEquipmentIds = manifestEquipmentRoleIds(data?.configuration_manifest);
    const directModeItems = roleEquipmentIds.map(equipmentId => {
        const resolved = findLibraryEquipmentPackage(data, equipmentId);
        const aliases = DIRECT_MODE_EQUIPMENT_CANDIDATES[resolved.resolvedId] || [resolved.resolvedId];
        const sourceIds = [resolved.resolvedId, ...aliases, resolved.equipmentPackage?.equipment_id, resolved.packageKey]
            .filter(Boolean)
            .filter((value, index, values) => values.indexOf(value) === index);
        return { sourceIds, targetId: resolved.resolvedId, required: true };
    });
    const roleTargets = new Set(directModeItems.map(item => item.targetId));
    const loadedItems = Object.entries(data?.equipment || {}).map(([key, item]) => {
        const loadedId = item?.equipment_id || key;
        const resolvedId = resolveDirectModeEquipmentId(loadedId);
        if (roleTargets.has(resolvedId)) return null;
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

async function loadConfigurationEquipmentEntries(configurationName, manifest) {
    const base = encodeURIComponent(configurationName);
    const equipmentLoadIds = manifestEquipmentRoleIds(manifest);
    const equipmentRequests = equipmentLoadIds.map(async equipmentId => {
        const resolvedId = resolveFrontendEquipmentId(equipmentId);
        const packagePath = `equipment/${resolvedId}/${resolvedId}.xlsx`;
        try {
            const fetched = await fetchResolvedConfigurationEquipmentWorkbook(base, equipmentId);
            const sheets = fetched.sheets;
            const equipmentMetadata = await fetchConfigurationLibraryJson(`${configurationName}/equipment/${fetched.sourceEquipmentId}/equipment_metadata.json`).catch(() => null);
            const curveNames = ["Solver_Curve", "Solver_Curve_Normal", "Solver_Curve_Failure"].filter(name => sheets[name]);
            const information = librarySheetKeyValues(sheets.Information);
            const metadata = librarySheetKeyValues(sheets.Metadata);
            const validation = librarySheetKeyValues(sheets.Validation);
            const equipmentType = information["Equipment Type"] || metadata.equipment_type || equipmentMetadata?.equipment_type || null;
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
                validation_status: validation["Validation Status"] || validation.Status || "Available",
                equipment_metadata: equipmentMetadata
            }];
        } catch (_) {
            return [resolvedId, {
                equipment_id: resolvedId, source_equipment_id: equipmentId, equipment_type: null, package_path: packagePath,
                status: "Missing", available_sheets: [], solver_curves: {}, performance_map: [], electrical_path: null,
                validation_status: "Missing equipment package",
                equipment_metadata: null
            }];
        }
    });
    return Promise.all(equipmentRequests);
}

function defaultConfigurationLibraryScenarios() {
    return [
        { scenario: "Normal", running_unit_formula: "installed_units", description: "Normal operating scenario" },
        { scenario: "Failure", running_unit_formula: "required_units", description: "Failure operating scenario" }
    ];
}

function defaultConfigurationLibraryItLoad(configurationName, hours = 8760) {
    const percentages = Array(hours).fill(90);
    const ratios = Array(hours).fill(0.9);
    return {
        standard_file: {
            schema_version: "pue.timeseries.it_load.v1",
            type: "annual_it_load",
            source_file: `${configurationName}/configuration_manifest.json`,
            units: { hourly_it_load_percent: "%", hourly_it_load_ratio: "fraction" },
            data: { hourly_it_load_percent: percentages, "hourly_it_load_%": percentages, hourly_it_load_ratio: ratios },
            hours
        },
        payload: { hours, hourly_it_load_percent: percentages, hourly_it_load_ratio: ratios },
        source_type: "compatibility_default",
        source_name: "Compatibility Default — 90% Constant"
    };
}

function manifestPowerSource(configurationName, manifest) {
    const text = `${configurationName || ""} ${manifest?.display_name || ""}`.toUpperCase();
    return text.includes("GASENGINE") || text.includes("GAS ENGINE") ? "Gas Engine" : "Grid";
}

function manifestCoolingSystemType(manifest) {
    return topologyStatusForManifest(manifest).display || manifest?.cooling_system_type || "Configuration Library";
}

function manifestCoolingUnitCapacityMw(manifest, equipmentEntries) {
    const equipment = Object.fromEntries(equipmentEntries || []);
    const priorityRoles = ["primary_cooling", "chiller", "dry_cooler"];
    for (const roleName of priorityRoles) {
        let resolvedIds;
        try {
            resolvedIds = resolveEquipmentRoleIdFromMapping(manifest, roleName, equipment, false);
        } catch (_) {
            resolvedIds = null;
        }
        for (const equipmentId of (Array.isArray(resolvedIds) ? resolvedIds : [resolvedIds]).filter(Boolean)) {
            const metadata = equipment[equipmentId]?.equipment_metadata || {};
            const capacityKw = Number(metadata.rated_capacity_kW ?? metadata.nominal_capacity_kW ?? metadata.capacity_kW);
            if (Number.isFinite(capacityKw) && capacityKw > 0) return capacityKw / 1000;
        }
    }
    return DEFAULT_COOLING_UNIT_CAPACITY_MW;
}

function verifyConfigurationLibrarySynced(configurationPath, selectedConfiguration) {
    const manifest = selectedConfiguration?.configuration_manifest || {};
    const firstEquipmentId = manifestEquipmentRoleIds(manifest)[0];
    if (!firstEquipmentId) {
        throw new Error("Configuration manifest does not declare any equipment roles.");
    }
    const resolved = findLibraryEquipmentPackage(selectedConfiguration, firstEquipmentId);
    const equipmentId = resolved.resolvedId;
    const equipmentPath = `${configurationPath}/equipment/${equipmentId}/${equipmentId}.xlsx`;
    try {
        pyodide.FS.stat(equipmentPath);
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
    const loadMode = selectedConfiguration?.configuration_load_mode || configurationLibraryLoadMode(selectedConfiguration?.configuration_manifest || selectedConfiguration);
    const supportFiles = loadMode === "legacy"
        ? ["configuration.xlsx", "scenario.xlsx", "input/IT_LOAD_90_PERCENT.xlsx"]
        : [];
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

    verifyConfigurationLibrarySynced(configurationPath, selectedConfiguration);
    return {
        configuration_name: configurationName,
        configuration_path: configurationPath,
        configuration_load_mode: loadMode,
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
        return {
            status: "Electrical Path Found",
            sheet_name: "Solver",
            curve: null,
            electrical_path: electricalPath,
            equipment_metadata: equipmentPackage?.equipment_metadata || null,
            equipment_type: equipmentPackage?.equipment_type || equipmentPackage?.equipment_metadata?.equipment_type || null,
            package_path: equipmentPackage?.package_path || null
        };
    }
    const curves = equipmentPackage?.solver_curves || {};
    const equipmentType = String(equipmentPackage?.equipment_type || equipmentPackage?.equipment_metadata?.equipment_type || "").toUpperCase();
    const equipmentId = String(equipmentPackage?.equipment_id || "").toUpperCase();
    if (["CHW_PUMP", "CW_PUMP"].includes(equipmentType) || /^(CHW|CW)_PUMP/.test(equipmentId)) {
        const curve = Array.isArray(curves.Solver_Curve) && curves.Solver_Curve.length ? curves.Solver_Curve : null;
        return {
            status: curve ? "Selected" : "Missing Curve",
            sheet_name: curve ? "Solver_Curve" : null,
            curve,
            equipment_metadata: equipmentPackage?.equipment_metadata || null,
            equipment_type: equipmentType || null,
            package_path: equipmentPackage?.package_path || null
        };
    }
    const scenario = String(scenarioName || "").toLowerCase();
    const preferred = scenario === "normal" ? "Solver_Curve_Normal"
        : (["failure", "maintenance"].includes(scenario) ? "Solver_Curve_Failure" : null);
    const selected = [preferred, "Solver_Curve"].find(name => name && Array.isArray(curves[name]) && curves[name].length);
    if (selected) return {
        status: "Selected",
        sheet_name: selected,
        curve: curves[selected],
        equipment_metadata: equipmentPackage?.equipment_metadata || null,
        equipment_type: equipmentPackage?.equipment_type || equipmentPackage?.equipment_metadata?.equipment_type || null,
        package_path: equipmentPackage?.package_path || null
    };
    if (String(equipmentPackage?.equipment_id || "").startsWith("ACC_") && equipmentPackage?.performance_map?.length) {
        return {
            status: "Selected",
            sheet_name: "Performance_Map",
            curve: equipmentPackage.performance_map,
            equipment_metadata: equipmentPackage?.equipment_metadata || null,
            equipment_type: equipmentPackage?.equipment_type || equipmentPackage?.equipment_metadata?.equipment_type || null,
            package_path: equipmentPackage?.package_path || null
        };
    }
    return {
        status: "Missing Solver_Curve",
        sheet_name: null,
        curve: null,
        equipment_metadata: equipmentPackage?.equipment_metadata || null,
        equipment_type: equipmentPackage?.equipment_type || equipmentPackage?.equipment_metadata?.equipment_type || null,
        package_path: equipmentPackage?.package_path || null
    };
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
    return buildGenericConfigurationLibraryPayload(data, scenarioNameOverride);
}

function buildGenericConfigurationLibraryPayload(data, scenarioNameOverride = null) {
    phase19bTrace("buildFrontendSolverInputFromLibrary:start", {
        configuration_name: data?.configuration_name,
        scenarioNameOverride,
        existing_data_path: data?.configuration_path
    });
    const manifest = data?.configuration_manifest || {};
    const topologyId = manifest.solver_topology || data?.topology_id || data?.solver_dispatch_key;
    if (!SUPPORTED_CONFIGURATION_TOPOLOGIES.includes(topologyId)) {
        throw new Error(`Unsupported solver topology for Configuration Library direct mode: ${topologyId || "missing"}.`);
    }
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
    const libraryAshraeUrl = ASHRAE_PROXY_URL;
    const dryCoolerApproachC = Number(document.getElementById("dryCoolerApproachC")?.value || 5);
    phase19bTrace("buildFrontendSolverInputFromLibrary:ashrae assignment", {
        peakDesignWeather,
        assigned_ashrae_design_conditions_url: libraryAshraeUrl
    });
    const resolvedItProfile = refreshCanonicalItLoadForCapacity(data.it_load, designItLoadKw);
    const percentages = resolvedItProfile?.hourly_it_load_percent || [];
    const hourlyItLoadKw = resolvedItProfile?.hourly_it_load_kW || [];
    const hours = hourlyItLoadKw.length;
    const dryBulbWeather = standardDataArray(standardDataFiles.weather || {}, [["data", "dry_bulb_C"], ["hourly_data", "dry_bulb_C"]]);
    const wetBulbWeather = standardDataArray(standardDataFiles.weather || {}, [["data", "wet_bulb_C"], ["hourly_data", "wet_bulb_C"]]);
    const hasAnnualWeather = Array.isArray(dryBulbWeather) && dryBulbWeather.length >= hours;
    const weather = { hourly_data: {
        hour_index: makeHours(hours),
        dry_bulb_C: hasAnnualWeather ? dryBulbWeather.slice(0, hours) : Array(hours).fill(25),
        wet_bulb_C: hasAnnualWeather && wetBulbWeather?.length >= hours ? wetBulbWeather.slice(0, hours) : []
    }, metadata: hasAnnualWeather
        ? { source: "loaded_weather" }
        : { source: "library_solver_adapter_default", assumption: "25 C constant dry bulb" }
    };
    const selectedCurves = Object.fromEntries(manifestEquipmentRoleIds(manifest).map(equipmentId => {
        const resolved = findLibraryEquipmentPackage(data, equipmentId);
        return [resolved.resolvedId, selectLibrarySolverCurve(resolved.equipmentPackage, scenarioName)];
    }));
    const bindingForResolvedId = (resolvedId, role) => {
        const resolved = findLibraryEquipmentPackage(data, resolvedId);
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
            curve_data: selected?.curve || null,
            performance_map: item?.performance_map || null,
            electrical_path: selected?.electrical_path || item?.electrical_path || null,
            equipment_type: selected?.equipment_type || item?.equipment_type || item?.equipment_metadata?.equipment_type || null,
            curve_type: item?.equipment_metadata?.curve_type || null,
            curve_schema: item?.equipment_metadata?.curve_schema || null,
            equipment_metadata: selected?.equipment_metadata || item?.equipment_metadata || null
        };
    };
    const roleBindings = Object.fromEntries(Object.keys(manifest?.equipment_roles || {}).map(roleName => {
        const roleRequired = (manifest?.required_roles || []).includes(roleName);
        const resolvedIds = resolveEquipmentRoleIdFromMapping(manifest, roleName, data.equipment, roleRequired);
        if (resolvedIds === null) return [roleName, null];
        const bindings = (Array.isArray(resolvedIds) ? resolvedIds : [resolvedIds])
            .map(id => bindingForResolvedId(id, roleName));
        return [roleName, Array.isArray(resolvedIds) ? bindings : bindings[0]];
    }));
    const equipmentBindings = Object.fromEntries(Object.values(roleBindings)
        .flatMap(value => Array.isArray(value) ? value : [value])
        .filter(Boolean)
        .map(binding => [binding.equipment_id, binding]));
    const electricalBinding = roleBindings.electrical_distribution;
    const electricalPath = (Array.isArray(electricalBinding) ? electricalBinding[0] : electricalBinding)?.electrical_path || null;
    const manifestMetadata = {
        configuration_id: manifest.configuration_id || data.configuration_id || data.configuration_name,
        configuration_display_name: manifest.display_name || data.configuration_display_name || data.configuration_name,
        configuration_manifest_schema_version: manifest.schema_version || data.configuration_manifest_schema_version || null,
        manifest_cooling_system_type: manifest.cooling_system_type || data.manifest_cooling_system_type || topologyId,
        topology_id: topologyId,
        implementation_status: manifest.implementation_status || data.implementation_status,
        solver_dispatch_key: manifest.solver_topology || data.solver_dispatch_key || topologyId,
        report_profile: manifest.report_profile || data.report_profile || topologyId
    };
    return {
        ...manifestMetadata,
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
            ashrae_design_conditions_url: libraryAshraeUrl,
            location: {
                name: projectInfo.location,
                latitude: projectInfo.latitude,
                longitude: projectInfo.longitude,
                peak_design_weather_source: peakDesignWeather.peakDesignWeatherSource,
                peak_design_outdoor_dry_bulb_C: peakDesignWeather.peakDesignOutdoorDryBulbC,
                ashrae_design_conditions_url: libraryAshraeUrl
            },
            design_it_load_kW: designItLoadKw,
            cooling_unit_capacity_kW: data.cooling_unit_capacity_mw * 1000,
            required_units: sizing.requiredUnits,
            installed_units: installedUnits,
            active_units: activeUnits,
            indoor_active_units: indoorActiveUnits,
            running_units: activeUnits,
            standby_units: standbyUnits,
            dry_cooler_approach_C: dryCoolerApproachC,
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
                ...resolvedItProfile,
                design_it_load_kW: designItLoadKw
            }
        },
        unit_quantity: unitQuantity,
        equipment: {
            role_bindings: roleBindings,
            equipment_bindings: equipmentBindings,
            electrical_path: electricalPath
        },
        electrical_path: electricalPath,
        weather,
        dry_cooler_approach_C: dryCoolerApproachC,
        heat_gains: {
            solar_heat_gain_max_kW: heatGains.solarHeatGainMaxKw,
            solar_daytime_start_hour: heatGains.solarDaytimeStartHour,
            solar_daytime_end_hour: heatGains.solarDaytimeEndHour,
            other_auxiliary_heat_gain_kW: heatGains.otherAuxiliaryHeatGainKw
        },
        peak_design_weather_source: peakDesignWeather.peakDesignWeatherSource,
        peak_design_outdoor_dry_bulb_C: peakDesignWeather.peakDesignOutdoorDryBulbC,
        ashrae_design_conditions_url: libraryAshraeUrl,
        site_location: {
            latitude: projectInfo.latitude,
            longitude: projectInfo.longitude,
            ashrae_design_conditions_url: libraryAshraeUrl
        },
        other_electrical_auxiliary_power_kW: heatGains.otherElectricalAuxiliaryPowerKw,
        it_load_profile_source_type: resolvedItProfile?.source_type,
        it_load_profile_source_name: resolvedItProfile?.source_name,
        it_load_profile_hours: resolvedItProfile?.hours,
        it_load_profile_average_kW: resolvedItProfile?.average_kW,
        it_load_profile_average_ratio: resolvedItProfile?.average_ratio,
        it_load_profile_min_kW: resolvedItProfile?.min_kW,
        it_load_profile_max_kW: resolvedItProfile?.max_kW,
        it_load_profile_validation_status: resolvedItProfile?.validation_status,
        it_load_profile_time_basis: resolvedItProfile?.time_basis,
        it_load_profile_hour_sequence_validation: resolvedItProfile?.hour_sequence_valid
            ? (resolvedItProfile?.has_explicit_hour_ids || resolvedItProfile?.time_basis === "generated_hour_of_year" ? "PASS" : "WARNING")
            : "ERROR",
        it_load_profile_calendar_time_basis: resolvedItProfile?.calendar_time_basis,
        it_load_profile_calendar_sequence_validation: resolvedItProfile?.calendar_sequence_valid,
        it_load_profile_calendar_epw_match_valid: resolvedItProfile?.calendar_epw_match_valid,
        it_load_profile_calendar_hour_convention: resolvedItProfile?.calendar_hour_convention,
        selected_curves: selectedCurves,
        configuration_manifest: JSON.parse(JSON.stringify(manifest))
    };
}

function convertFrontendLibraryInputToSolverInput(libraryInput) {
    phase19bTrace("convertFrontendLibraryInputToSolverInput:start", {
        ashrae_top: libraryInput?.ashrae_design_conditions_url,
        ashrae_project: libraryInput?.project?.ashrae_design_conditions_url,
        configuration_path: libraryInput?.configuration_path,
        scenario_name: libraryInput?.scenario_name
    });
    const topologyId = libraryInput?.topology_id || libraryInput?.solver_dispatch_key || libraryInput?.configuration_manifest?.solver_topology;
    if (!SUPPORTED_CONFIGURATION_TOPOLOGIES.includes(topologyId)) {
        throw new Error(`Unsupported solver topology for Configuration Library dispatch: ${topologyId || "missing"}.`);
    }
    return JSON.parse(JSON.stringify(libraryInput));
}

async function runUsingConfigurationLibrary() {
    phase19bTrace("Run Using Configuration Library starts", {
        hasConfigurationLibraryData: Boolean(configurationLibraryData),
        configuration_name: configurationLibraryData?.configuration_name,
        ui_script: "ui.js?v=20260716-phase19b-trace"
    });
    const status = document.getElementById("configurationLibraryStatus");
    if (!configurationLibraryData) {
        if (status) status.textContent = "Load Configuration Library first.";
        return;
    }
    if (!automaticEpwReady) {
        if (status) {
            status.textContent = "Automatic EPW weather matching must complete successfully before running the annual simulation.";
            status.style.color = "#dc2626";
        }
        if (btnRun) btnRun.disabled = true;
        return;
    }
    if (!isConfigurationManifestRunnable(configurationLibraryData.configuration_manifest)) {
        if (status) {
            status.textContent = "This configuration requires validated Solver_Curve data and solver module implementation.";
            status.style.color = "#dc2626";
        }
        return;
    }
    const validation = validateFrontendConfigurationLibrary(configurationLibraryData);
    configurationLibraryData.configuration_validation = validation;
    if (validation.status === "error") {
        renderConfigurationLibrarySummary(configurationLibraryData);
        if (status) {
            status.textContent = `Configuration validation failed: ${[...validation.missing_roles, ...validation.missing_curves, ...validation.warnings].join("; ")}`;
            status.style.color = "#dc2626";
        }
        return;
    }
    const calculationMode = CONFIGURATION_LIBRARY_DIRECT_CALCULATION_MODE;
    let libraryInput;
    try {
        libraryInput = buildFrontendSolverInputFromLibrary(configurationLibraryData);
    } catch (error) {
        if (status) {
            status.textContent = String(error.message || error);
            status.style.color = "#dc2626";
        }
        return;
    }
    phase19bTrace("runUsingConfigurationLibrary:libraryInput built", {
        ashrae_top: libraryInput?.ashrae_design_conditions_url,
        ashrae_project: libraryInput?.project?.ashrae_design_conditions_url,
        project: {
            latitude: libraryInput?.project?.latitude,
            longitude: libraryInput?.project?.longitude,
            active_units: libraryInput?.project?.active_units,
            design_it_load_kW: libraryInput?.project?.design_it_load_kW
        }
    });
    if (!libraryInput) {
        if (status) status.textContent = "Enter Total IT Capacity before running the configuration.";
        return;
    }
    try {
        const proxyCondition = await fetchAshraeProxyDesignConditionForLibrary(libraryInput);
        if (proxyCondition) {
            libraryInput.peak_design_condition_override = proxyCondition;
            libraryInput.project.peak_design_condition_override = proxyCondition;
            phase19bTrace("runUsingConfigurationLibrary:proxy condition override assigned", {
                lookup_status: proxyCondition.lookup_status,
                lookup_method: proxyCondition.lookup_method,
                lookup_provider: proxyCondition.lookup_provider,
                station_name: proxyCondition.station_name,
                design_db_max_C: proxyCondition.design_db_max_C
            });
        }
    } catch (error) {
        libraryInput.ashrae_proxy_prefetch_failure = String(error.message || error);
        phase19bTrace("runUsingConfigurationLibrary:proxy prefetch failed; solver will receive proxy URL", {
            failure: libraryInput.ashrae_proxy_prefetch_failure,
            ashrae_top: libraryInput.ashrae_design_conditions_url,
            ashrae_project: libraryInput.project?.ashrae_design_conditions_url
        });
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
    const topologyId = libraryInput?.topology_id || libraryInput?.solver_dispatch_key || libraryInput?.configuration_manifest?.solver_topology;
    const adaptedInput = convertFrontendLibraryInputToSolverInput(libraryInput);
    configurationLibraryData.final_solver_input = adaptedInput;
    const solverFn = "dispatch_topology";
    phase19bTrace("runUsingConfigurationLibrary:adaptedInput after engine selection", {
        ashrae_top: adaptedInput?.ashrae_design_conditions_url,
        ashrae_project: adaptedInput?.project?.ashrae_design_conditions_url,
        run_mode: adaptedInput?.run_mode,
        acc_v2: adaptedInput?.acc_v2,
        final_json_passed_to_run: adaptedInput
    });
    elIn.value = pretty(adaptedInput);
    const calculationModeLabel = "Configuration Library Direct Solver_Curve Hourly Simulation";
    if (status) status.textContent = `Running ${configurationLibraryData.configuration_name} / ${libraryInput.scenario_name} / ${calculationModeLabel}...`;
    log(
        `Configuration Library synced: ${syncResult.configuration_name}, workbooks=${syncResult.workbook_paths.length}\n` +
        syncResult.workbook_paths.slice(0, 5).join("\n")
    );
    try {
        await run({ libraryRun: true, libraryInput: adaptedInput, solverFn });
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
    const finalSolverInput = data.final_solver_input || null;
    const validation = data.configuration_validation || validateFrontendConfigurationLibrary(data);
    data.configuration_validation = validation;
    const ashraeEndpointSent = finalSolverInput?.ashrae_design_conditions_url || finalSolverInput?.project?.ashrae_design_conditions_url || standardized?.ashrae_design_conditions_url || standardized?.project?.ashrae_design_conditions_url || "Not available";
    const hourlyElectrical = Array.isArray(data.last_solver_output?.hourly_results) ? data.last_solver_output.hourly_results : [];
    const directAccV2Disclosure = isConfigurationLibraryAccV2DirectResult(data.last_solver_output || {}, data.standardized_solver_input || null);
    const resultValue = (value, formatter) => value != null ? formatter(value) : "Not available";
    const whiteSpaceEnergy = firstAvailableResultField(annualElectrical, ["annual_white_space_equipment_energy_kWh"])
        ?? sumAvailableResultFields(annualElectrical, ["annual_cdu_energy_kWh", "annual_rtc_energy_kWh", "annual_mau_energy_kWh"]);
    const engineRadiatorMaxPower = firstAvailableResultField(annualElectrical, ["max_engine_radiator_power_kW"])
        ?? maxHourlyResultField(hourlyElectrical, ["engine_radiator_power_kW"]);
    const metadataValues = [
        ["Configuration ID", data.configuration_id || data.configuration_name],
        ["Configuration Display Name", data.configuration_display_name || data.configuration_name],
        ["Configuration Name", data.configuration_name],
        ["Cooling System Type", data.cooling_system_type || "Not available"],
        ["Topology ID", data.topology_id || "Not available"],
        ["Configuration Validation", String(validation.status || "unknown").toUpperCase()],
        ["Validation Missing Roles", validation.missing_roles?.length ? validation.missing_roles.join(", ") : "None"],
        ["Validation Missing Curves", validation.missing_curves?.length ? validation.missing_curves.join(", ") : "None"],
        ["Validation Warnings", validation.warnings?.length ? validation.warnings.join("; ") : "None"],
        ["Implementation Status", data.implementation_status || "Not available"],
        ["Solver Dispatch Key", data.solver_dispatch_key || "Not available"],
        ["Report Profile", data.report_profile || "Not available"],
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
            ["ASHRAE Endpoint Sent to Solver", ashraeEndpointSent],
            ["ASHRAE Endpoint Received by Solver", peakResults.peak_design_lookup_endpoint || "Not available"],
            ["Lookup Method", peakResults.peak_design_lookup_method || "Not available"],
            ["Lookup Provider", peakDesignSourceLabel(peakResults.peak_design_lookup_provider || "ASHRAE_online")],
            ["ASHRAE Online Lookup Failed", peakResults.peak_design_lookup_failure_reason || "No"],
            ["ASHRAE Lookup Fallback", peakResults.peak_design_fallback_status || (peakResults.peak_design_weather_source === "ASHRAE_local_cache" ? "Using Local ASHRAE Cache fallback" : (peakResults.peak_design_weather_source === "manual" ? "Using Manual Override fallback" : "None"))],
            ["Peak Design Outdoor Dry Bulb", peakResults.peak_design_outdoor_dry_bulb_C != null ? `${fmtNumber(peakResults.peak_design_outdoor_dry_bulb_C, 1)} deg C` : "Not available"]
        ] : []),
        ["IT Load kW sample", itSample.length ? itSample.map(value => fmtNumber(value, 1)).join(", ") : "Enter Total IT Capacity"],
        ["Electrical IT / MEP efficiency", electricalPath
            ? `${fmtNumber(electricalPath.it_efficiency * 100, 2)}% / ${fmtNumber(electricalPath.mep_efficiency * 100, 2)}%` : "Missing"]
    ];
    const calculationValues = [
        ["IT Electrical Distribution Loss", resultValue(annualElectrical.annual_it_electrical_loss_kWh, value => `${fmtInteger(value)} kWh`)],
        ["MEP Electrical Distribution Loss", resultValue(annualElectrical.annual_mep_electrical_loss_kWh, value => `${fmtInteger(value)} kWh`)],
        ["Total Electrical Distribution Loss", resultValue(annualElectrical.annual_electrical_loss_kWh, value => `${fmtInteger(value)} kWh`)],
        ["CHW Pump Energy", resultValue(firstAvailableResultField(annualElectrical, ["annual_chw_pump_energy_kWh", "annual_pump_energy_kWh"]), value => `${fmtInteger(value)} kWh`)],
        ["Chiller Energy", resultValue(annualElectrical.annual_chiller_energy_kWh, value => `${fmtInteger(value)} kWh`)],
        ["Dry Cooler Energy", resultValue(annualElectrical.annual_dry_cooler_energy_kWh, value => `${fmtInteger(value)} kWh`)],
        ["Average Chiller COP", resultValue(dispatchReportProfile(data.topology_id, data.last_solver_output || {}).summary.average_chiller_COP, value => fmtNumber(value, 3))],
        ["Minimum Chiller COP", resultValue(dispatchReportProfile(data.topology_id, data.last_solver_output || {}).summary.min_chiller_COP, value => fmtNumber(value, 3))],
        ["Maximum Chiller COP", resultValue(dispatchReportProfile(data.topology_id, data.last_solver_output || {}).summary.max_chiller_COP, value => fmtNumber(value, 3))],
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
    const bindingSummaryRows = [];
    const equipmentRows = manifestEquipmentRoleIds(data.configuration_manifest).map(equipmentId => {
        const resolved = findLibraryEquipmentPackage(data, equipmentId);
        const item = resolved.equipmentPackage || { equipment_id: resolved.resolvedId, status: "Missing", solver_curves: {} };
        const selected = selectLibrarySolverCurve(item, selectedScenario);
        const packageStatus = resolved.equipmentPackage ? "Found" : "Missing Workbook";
        const equipmentMetadata = item.equipment_metadata || {};
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
        const equipmentType = equipmentMetadata.equipment_type || item.equipment_type || "Not available";
        const metadataCurveType = equipmentMetadata.curve_type || "Not available";
        const curveSchema = equipmentCurveSchema(equipmentType, metadataCurveType);
        const bindingName = ({
            CHILLER: "Chiller",
            DRY_COOLER: "Dry Cooler",
            CHW_PUMP: "CHW Pump",
            CW_PUMP: "CW Pump",
            ELECTRICAL_DISTRIBUTION: "Electrical Distribution"
        })[String(equipmentType).toUpperCase()] || String(equipmentType).replaceAll("_", " ");
        bindingSummaryRows.push({
            label: `${bindingName} Solver_Curve`,
            available: Boolean(selected.sheet_name || selected.electrical_path)
        });
        return `<tr>
            <td>${esc(resolved.resolvedId)}</td><td>${esc(equipmentType)}</td>
            <td>${esc(metadataCurveType)}</td><td>${esc(curveSchema)}</td><td>${esc(equipmentMetadata.status || packageStatus)}</td><td>${esc(packageStatus)}</td>
            <td>${esc(sheetFoundDisplay)}</td>
            <td>${selectedDisplay}</td><td>${esc(sourceStatus)}</td><td>${esc(curveType)}</td>
        </tr>`;
    }).join("");
    const bindingStatus = document.getElementById("configurationLibraryBindingStatus");
    if (bindingStatus) {
        bindingStatus.innerHTML = `<div class="panelTitle">Configuration Library Loaded:</div>${bindingSummaryRows.map(item =>
            `<div>${item.available ? "✓" : "⚠"} ${esc(item.label)}</div>`
        ).join("")}`;
    }
    const valueCards = values => values.map(([label, value]) =>
        `<div class="fileSlot"><div class="panelTitle">${esc(label)}</div><div>${esc(value)}</div></div>`
    ).join("");
    summary.innerHTML = `
        <details id="configurationMetadataDetails" class="advancedDetails" style="grid-column:1/-1; margin-bottom:0;">
            <summary>Configuration Metadata</summary>
            <div class="fileGrid">${valueCards(metadataValues)}</div>
        </details>
        <details id="configurationCalculationSummaryDetails" class="advancedDetails" style="grid-column:1/-1; margin-bottom:0;">
            <summary>Calculation Summary</summary>
            <div class="fileGrid">${valueCards(calculationValues)}</div>
        </details>
        <details id="configurationEquipmentBindingDetails" class="advancedDetails" style="grid-column:1/-1; margin-bottom:0;">
            <summary>Equipment Binding Details</summary>
            <div class="fileSlot" style="overflow-x:auto;">
                <table style="width:100%; min-width:720px;"><thead><tr>
                    <th>Equipment ID</th><th>Equipment Type</th><th>Curve Type</th><th>Curve Schema</th><th>Metadata Status</th><th>Package Status</th><th>Solver_Curve Sheet Found</th><th>Selected Curve</th><th>Source Status</th><th>Curve Type</th>
                </tr></thead><tbody>${equipmentRows}</tbody></table>
            </div>
        </details>`;
}

async function loadSelectedConfigurationLibrary() {
    const select = document.getElementById("configurationLibrarySelect");
    const status = document.getElementById("configurationLibraryStatus");
    const button = document.getElementById("btnLoadConfigurationLibrary");
    const selectedManifest = selectedConfigurationManifest();
    const configurationName = selectedManifest?.configuration_id || select?.value || "";
    if (!selectedManifest) {
        if (status) {
            status.textContent = "No Configuration Library manifest is selected.";
            status.style.color = "#dc2626";
        }
        return;
    }
    if (!selectedManifest.runnable) {
        if (status) {
            const topology = topologyStatusForManifest(selectedManifest);
            status.textContent = `Topology: ${topology.display} (Status: ${configurationStatusLabel(topology.status)}). This configuration requires validated Solver_Curve data and solver module implementation.`;
            status.style.color = "#b45309";
        }
        return;
    }
    if (status) status.textContent = `Loading ${configurationName}...`;
    if (button) button.disabled = true;
    try {
        await loadConfigurationEquipmentAliases();
        const base = encodeURIComponent(configurationName);
        const loadMode = configurationLibraryLoadMode(selectedManifest);
        let configurationSheets = null;
        let parameters = {};
        let equipmentPerUnit = [];
        let scenarios = defaultConfigurationLibraryScenarios();
        let itLoadSourceFile = "configuration_manifest.json";
        let percentages = [];
        let ratios = [];
        let equipmentEntries = [];
        let packagedHourIds = null;

        if (loadMode === "legacy") {
            configurationSheets = await fetchConfigurationWorkbook(`${base}/configuration.xlsx`);
            parameters = configurationKeyValues(configurationSheets.Configuration);
            equipmentPerUnit = (configurationSheets.Equipment_List || []).map(row => ({
                equipment_id: String(row.Equipment || ""),
                per_cooling_unit: Number(row["Per Cooling Unit"] || 0)
            }));
            const [scenarioSheets, itSheets, loadedEquipmentEntries] = await Promise.all([
                fetchConfigurationWorkbook(`${base}/scenario.xlsx`),
                fetchConfigurationWorkbook(`${base}/input/IT_LOAD_90_PERCENT.xlsx`),
                loadConfigurationEquipmentEntries(configurationName, selectedManifest)
            ]);
            equipmentEntries = loadedEquipmentEntries;
            scenarios = (scenarioSheets.Scenario || []).map(row => ({
                scenario: row.Scenario,
                running_unit_formula: row["Running Unit Formula"],
                description: row.Description
            }));
            percentages = (itSheets.IT_Load || []).map(row => Number(row.hourly_it_load_percent)).filter(Number.isFinite);
            ratios = (itSheets.IT_Load || []).map(row => Number(row.hourly_it_load_ratio)).filter(Number.isFinite);
            packagedHourIds = (itSheets.IT_Load || []).map(row => row.Hour_of_Year ?? row["Hour of Year"] ?? row.hour_index ?? row.Hour);
            itLoadSourceFile = "input/IT_LOAD_90_PERCENT.xlsx";
        } else {
            equipmentEntries = await loadConfigurationEquipmentEntries(configurationName, selectedManifest);
            const manifestItLoad = defaultConfigurationLibraryItLoad(configurationName);
            percentages = manifestItLoad.payload.hourly_it_load_percent;
            ratios = manifestItLoad.payload.hourly_it_load_ratio;
            parameters = {
                "Configuration Name": configurationName,
                "Cooling System Type": manifestCoolingSystemType(selectedManifest),
                "Cooling Unit Capacity": manifestCoolingUnitCapacityMw(selectedManifest, equipmentEntries),
                "Power Source": manifestPowerSource(configurationName, selectedManifest)
            };
        }
        const sourceType = loadMode === "legacy" ? "configuration_library_profile" : "compatibility_default";
        const sourceName = loadMode === "legacy" ? "Configuration Library Profile — IT_LOAD_90_PERCENT.xlsx" : "Compatibility Default — 90% Constant";
        const designItKw = projectDesignCapacityKw();
        const packagedProfile = canonicalItLoadFromPercent(percentages, designItKw, sourceType, sourceName, loadMode === "legacy"
            ? { hourIds: packagedHourIds, hasExplicitHourIds: true, timeBasis: "hour_of_year" }
            : { hourIds: Array.from({ length: percentages.length }, (_, index) => index + 1), hasExplicitHourIds: false, timeBasis: "generated_hour_of_year" });
        const resolvedProfile = projectItLoadProfileOverride
            ? refreshCanonicalItLoadForCapacity(projectItLoadProfileOverride, designItKw)
            : packagedProfile;
        const itLoad = {
            schema_version: "pue.timeseries.it_load.v1",
            type: "annual_it_load",
            source_file: itLoadSourceFile,
            units: { hourly_it_load_percent: "%", hourly_it_load_ratio: "fraction" },
            data: { hourly_it_load_percent: percentages, "hourly_it_load_%": percentages, hourly_it_load_ratio: ratios },
            hours: percentages.length
        };
        if (projectDesignCapacityKw() > 0) normalizeItLoadPercentFile(itLoad);
        standardDataFiles.itLoad = itLoad;
        standardSolverInput = null;
        preferStandardFiles = true;
        configurationLibraryData = {
            configuration_id: selectedManifest.configuration_id,
            configuration_display_name: selectedManifest.display_name,
            configuration_manifest_schema_version: selectedManifest.schema_version,
            topology_id: selectedManifest.solver_topology,
            implementation_status: selectedManifest.implementation_status,
            solver_dispatch_key: selectedManifest.solver_topology,
            report_profile: selectedManifest.report_profile,
            manifest_cooling_system_type: selectedManifest.cooling_system_type,
            configuration_load_mode: loadMode,
            configuration_manifest: selectedManifest,
            configuration_name: parameters["Configuration Name"] || configurationName,
            cooling_system_type: parameters["Cooling System Type"],
            cooling_unit_capacity_mw: Number(parameters["Cooling Unit Capacity"]),
            power_source: parameters["Power Source"],
            equipment_per_cooling_unit: equipmentPerUnit,
            equipment_count: equipmentEntries.length,
            scenarios,
            it_load: resolvedProfile,
            equipment: Object.fromEntries(equipmentEntries)
        };
        const initialScenario = document.getElementById("scenarioSelect")?.value === "one_failure_three_active" ? "Failure" : "Normal";
        configurationLibraryData.selected_curves = Object.fromEntries(manifestEquipmentRoleIds(configurationLibraryData.configuration_manifest).map(equipmentId => {
            const resolved = findLibraryEquipmentPackage(configurationLibraryData, equipmentId);
            return [resolved.resolvedId, selectLibrarySolverCurve(resolved.equipmentPackage, initialScenario)];
        }));
        configurationLibraryData.configuration_validation = validateFrontendConfigurationLibrary(configurationLibraryData);
        refreshSimulationReadiness();
        const librarySizing = calculateFrontendUnitRequirements(
            getProjectReportInfo().capacityMw, configurationLibraryData.cooling_unit_capacity_mw
        );
        configurationLibraryData.library_bound_input = {
            configuration: {
                configuration_id: configurationLibraryData.configuration_id,
                configuration_display_name: configurationLibraryData.configuration_display_name,
                topology_id: configurationLibraryData.topology_id,
                implementation_status: configurationLibraryData.implementation_status,
                solver_dispatch_key: configurationLibraryData.solver_dispatch_key,
                report_profile: configurationLibraryData.report_profile,
                configuration_load_mode: configurationLibraryData.configuration_load_mode,
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
                Object.fromEntries(manifestEquipmentRoleIds(configurationLibraryData.configuration_manifest).map(equipmentId => {
                    const resolved = findLibraryEquipmentPackage(configurationLibraryData, equipmentId);
                    return [resolved.resolvedId, selectLibrarySolverCurve(resolved.equipmentPackage, scenario.scenario)];
                }))
            ])),
            it_load_profile: configurationLibraryData.it_load
        };
        configurationLibraryData.standardized_solver_input = buildFrontendSolverInputFromLibrary(configurationLibraryData);
        window.configurationLibraryData = configurationLibraryData;
        renderItLoadProfileStatus(resolvedProfile);

        renderCoolingSystemSelection();
        renderConfigurationLibrarySummary(configurationLibraryData);
        renderFrameworkDiagnosticsPanel();
        updateFileStatus(
            "statusItLoad",
            loadMode === "legacy"
                ? `Configuration Library: IT_LOAD_90_PERCENT.xlsx (${percentages.length} hours)`
                : `Compatibility Default — 90% Constant (${percentages.length} hours)`,
            "ok"
        );
        resetAutomaticEpwBindingState();
        const epwMatched = await autoMatchLocalEpw();
        configurationLibraryData.standardized_solver_input = buildFrontendSolverInputFromLibrary(configurationLibraryData);
        renderConfigurationLibrarySummary(configurationLibraryData);
        refreshStandardInputStatus();
        renderItLoadProfileStatus(configurationLibraryData.it_load);
        refreshSimulationReadiness();
        if (status) {
            status.textContent = epwMatched
                ? `Loaded ${configurationLibraryData.configuration_name}. Equipment models and EPW weather are ready.`
                : `Loaded ${configurationLibraryData.configuration_name}, but automatic EPW weather matching did not complete.`;
            status.style.color = epwMatched ? "#059669" : "#dc2626";
        }
        refreshSimulationReadiness();
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
    loadConfigurationLibraryCatalog();
    const libraryButton = document.getElementById("btnLoadConfigurationLibrary");
    if (libraryButton) libraryButton.addEventListener("click", loadSelectedConfigurationLibrary);
    const librarySelect = document.getElementById("configurationLibrarySelect");
    if (librarySelect) librarySelect.addEventListener("change", () => {
        configurationLibraryData = null;
        window.configurationLibraryData = null;
        resetAutomaticEpwBindingState();
        const summary = document.getElementById("configurationLibrarySummary");
        if (summary) {
            summary.innerHTML = "";
            summary.style.display = "none";
        }
        const bindingStatus = document.getElementById("configurationLibraryBindingStatus");
        if (bindingStatus) bindingStatus.textContent = "Equipment binding status will appear after the Configuration Library is loaded.";
        renderCoolingSystemSelection();
        const manifest = selectedConfigurationManifest();
        const status = document.getElementById("configurationLibraryStatus");
        if (status && manifest) {
            const topology = topologyStatusForManifest(manifest);
            status.textContent = `Topology: ${topology.display} (Status: ${configurationStatusLabel(topology.status)}).`;
            status.style.color = manifest.runnable ? "#374151" : "#b45309";
        }
        renderFrameworkDiagnosticsPanel();
        refreshSimulationReadiness();
    });
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
            refreshSimulationReadiness();
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
                    configurationLibraryData.it_load = refreshCanonicalItLoadForCapacity(configurationLibraryData.it_load, projectDesignCapacityKw());
                    if (projectItLoadProfileOverride) projectItLoadProfileOverride = refreshCanonicalItLoadForCapacity(projectItLoadProfileOverride, projectDesignCapacityKw());
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
                    renderItLoadProfileStatus(configurationLibraryData.it_load);
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
    refreshSimulationReadiness();
}

function buildPeakDemandBreakdown(outObj, peakSummary) {
    const hourly = Array.isArray(outObj?.hourly_results) ? outObj.hourly_results : [];
    const peak = outObj?.peak_results || {};
    const annualRow = hourly.reduce((selected, row) => {
        const value = Number(row?.total_facility_power_kW ?? row?.facility_power_kW);
        if (!Number.isFinite(value)) return selected;
        const selectedValue = Number(selected?.total_facility_power_kW ?? selected?.facility_power_kW);
        return !selected || value > selectedValue ? row : selected;
    }, null) || {};
    const value = candidate => Number.isFinite(Number(candidate)) ? Number(candidate) : 0;
    const hasValue = candidate => candidate !== null && candidate !== undefined && Number.isFinite(Number(candidate));
    const directModeAuxiliary = annualRow.auxiliary_power_basis === "direct_mode_other_electrical_auxiliary_input";
    const auxiliaryRows = directModeAuxiliary
        ? [["Other Electrical Auxiliary Power", value(annualRow.other_electrical_auxiliary_power_kW), value(peak.peak_design_other_electrical_auxiliary_power_kW)]]
        : [["Auxiliary Fixed Power", value(annualRow.auxiliary_fixed_power_kW), value(peak.peak_design_auxiliary_fixed_power_kW)]];
    const hasSeparateElectricalLosses = [
        annualRow.it_electrical_loss_kW,
        annualRow.mep_electrical_loss_kW,
        peak.peak_design_it_electrical_loss_kW,
        peak.peak_design_mep_electrical_loss_kW
    ].some(hasValue);
    const electricalLossRows = hasSeparateElectricalLosses
        ? [
            ["IT Electrical Distribution Loss", value(annualRow.it_electrical_loss_kW), value(peak.peak_design_it_electrical_loss_kW)],
            ["MEP Electrical Distribution Loss", value(annualRow.mep_electrical_loss_kW), value(peak.peak_design_mep_electrical_loss_kW)]
        ]
        : [["Electrical Distribution Loss", value(annualRow.electrical_loss_kW), value(peak.peak_design_electrical_loss_kW)]];
    const rows = [
        ["IT Load", value(annualRow.IT_load_kW ?? annualRow.it_load_kW), value(peak.peak_design_it_load_kW)],
        ["ACC / Chiller Power", value(annualRow.acc_power_kW ?? annualRow.chiller_power_kW), value(peak.peak_design_ACC_power_kW ?? peak.peak_design_chiller_power_kW)],
        ["Dry Cooler Power", value(annualRow.dry_cooler_power_kW), value(peak.peak_design_dry_cooler_power_kW)],
        ["CHW Pump Power", value(annualRow.CHW_pump_power_kW ?? annualRow.pump_power_kW), value(peak.peak_design_CHW_pump_power_kW)],
        ["CW Pump Power", value(annualRow.cw_pump_power_total_kW ?? annualRow.CW_pump_power_kW), value(peak.peak_design_CW_pump_power_kW)],
        ["CDU Power", value(annualRow.cdu_power_kW), value(peak.peak_design_CDU_power_kW)],
        ["RTC Power", value(annualRow.rtc_power_kW), value(peak.peak_design_RTC_power_kW)],
        ["MAU Power", value(annualRow.mau_power_kW), value(peak.peak_design_MAU_power_kW)],
        ...auxiliaryRows,
        ["ENGINE_RADIATOR Power", value(annualRow.engine_radiator_power_kW), value(peak.peak_design_engine_radiator_power_kW)],
        ...electricalLossRows
    ];
    const annualTotal = value(peakSummary?.peak_facility_power_kW ?? annualRow.total_facility_power_kW);
    const designTotal = value(peak.peak_design_facility_electrical_demand_kW ?? peak.peak_design_total_facility_power_kW);
    const annualSum = rows.reduce((sum, row) => sum + row[1], 0);
    const designSum = rows.reduce((sum, row) => sum + row[2], 0);
    return {
        rows,
        annualTotal,
        designTotal,
        annualReconciles: Math.abs(annualSum - annualTotal) < 1e-6,
        designReconciles: Math.abs(designSum - designTotal) < 1e-6
    };
}

function renderPeakDemandBreakdown(breakdown) {
    const body = document.getElementById("peakDemandBreakdownBody");
    if (!body) return;
    const rows = [...breakdown.rows, ["Total Facility Demand", breakdown.annualTotal, breakdown.designTotal]];
    body.innerHTML = `
        <table style="width:100%; border-collapse:collapse;">
            <thead><tr><th>Component</th><th>Annual Observed Peak</th><th>Peak Design</th></tr></thead>
            <tbody>${rows.map(([label, annualValue, designValue], index) => `
                <tr${index === rows.length - 1 ? ' style="font-weight:700;"' : ""}>
                    <td>${esc(label)}</td><td>${fmtNumber(annualValue, 3)} kW</td><td>${fmtNumber(designValue, 3)} kW</td>
                </tr>`).join("")}</tbody>
        </table>
        <div class="muted" style="margin-top:8px;">Reconciliation: Annual ${breakdown.annualReconciles ? "PASS" : "ERROR"}; Peak Design ${breakdown.designReconciles ? "PASS" : "ERROR"}. ENGINE_3 generation output is excluded from facility electrical demand.</div>`;
}

function engineeringEnergyDisplay(kWh) {
    const value = Number(kWh);
    if (!Number.isFinite(value)) return "N/A";
    return `${fmtNumber(value / 1e6, 3)} GWh`;
}

function annualFacilityEnergySummary(outObj = {}) {
    const annual = outObj.annual_results || {};
    const topology = outObj.topology_id || outObj.solver_dispatch_key;
    if (topology === "chiller_dry_cooler") {
        return {
            label: "Annual Cooling System Energy",
            energy_kWh: annual.annual_total_cooling_system_energy_kWh
        };
    }
    return {
        label: "Annual MEP / Facility Auxiliary Energy",
        energy_kWh: annual.annual_MEP_terminal_energy_kWh
    };
}

function annualEquipmentEnergyRows(annual = {}) {
    const rows = [
        ["IT", annual.annual_IT_energy_kWh],
        [annual.annual_acc_energy_kWh > 0 ? "ACC" : "Chiller", annual.annual_acc_energy_kWh || annual.annual_chiller_energy_kWh],
        ["Dry Cooler", annual.annual_dry_cooler_energy_kWh],
        ["CHW Pump", annual.annual_chw_pump_energy_kWh ?? annual.annual_pump_energy_kWh],
        ["CW Pump", annual.annual_cw_pump_energy_kWh],
        ["CDU", annual.annual_cdu_energy_kWh],
        ["RTC", annual.annual_rtc_energy_kWh],
        ["MAU", annual.annual_mau_energy_kWh],
        ["ENGINE_RADIATOR", annual.annual_engine_radiator_energy_kWh],
        ["Other Electrical Auxiliary Energy", annual.annual_other_electrical_auxiliary_energy_kWh ?? annual.annual_auxiliary_energy_kWh],
        ["Electrical Distribution Loss", annual.annual_electrical_loss_kWh]
    ];
    return rows.filter(([, energy]) => Number.isFinite(Number(energy)) && Number(energy) > 0);
}

function engineeringContextRows(outObj = {}, report = {}, input = {}) {
    const project = outObj.project || {};
    const manifest = input.configuration_manifest || {};
    const weatherMetadata = outObj.weather?.metadata || standardDataFiles.weather?.metadata || {};
    const capacityMw = Number(input.cooling_unit_capacity_mw);
    const designItKw = Number(project.design_it_load_kW ?? input.project?.design_it_load_kW ?? input.design_it_load_kW ?? input.design_IT_capacity_kW);
    const itProfile = input.project?.it_load || input.it_load || {};
    const timeBasis = itProfile.time_basis === "hour_of_year" ? "Hour of Year"
        : itProfile.time_basis === "generated_hour_of_year" ? "Generated Hour of Year"
        : itProfile.time_basis === "row_order_only" ? "Row Order Only" : "N/A";
    const sequenceStatus = itProfile.hour_sequence_valid === false ? "ERROR"
        : itProfile.has_explicit_hour_ids || itProfile.time_basis === "generated_hour_of_year" ? "PASS" : "WARNING";
    const calendarBasis = itProfile.calendar_time_basis === "date_time" ? "Date + Time"
        : itProfile.calendar_time_basis === "month_day_hour" ? "Month + Day + Hour"
        : itProfile.calendar_time_basis === "timestamp" ? "Timestamp" : "None";
    const calendarStatus = itProfile.calendar_sequence_valid === true ? "PASS"
        : itProfile.calendar_sequence_valid === false ? "ERROR" : "NOT PROVIDED";
    const alignmentStatus = itProfile.calendar_epw_match_valid === true ? "PASS"
        : itProfile.calendar_epw_match_valid === false ? "ERROR" : "NOT PROVIDED";
    return [
        ["Configuration", input.configuration_display_name || input.configuration_name || manifest.display_name || outObj.configuration_display_name || outObj.configuration_id || "N/A"],
        ["Cooling System Type", input.cooling_system_type || manifest.cooling_system_type || report.cooling_system_type || outObj.cooling_system_type || "N/A"],
        ["Cooling Unit Capacity", Number.isFinite(capacityMw) ? `${fmtNumber(capacityMw, 3)} MW` : "N/A"],
        ["Power Source", input.power_source || outObj.power_source || "N/A"],
        ["Scenario", project.scenario_name || input.scenario_name || report.operating_scenario?.scenario_name || "N/A"],
        ["Design IT Capacity", Number.isFinite(designItKw) ? `${fmtNumber(designItKw / 1000, 3)} MW` : "N/A"],
        ["Weather / Climate Station", weatherMetadata.station_name || weatherMetadata.source || getWeatherSourceMetadata(standardDataFiles.weather || {}).station_name || "Loaded annual weather"],
        ["IT Load Time Basis", timeBasis],
        ["Hour Sequence Validation", sequenceStatus],
        ["IT Calendar Time Basis", calendarBasis],
        ["Calendar Sequence Validation", calendarStatus],
        ["IT / Weather Calendar Alignment", alignmentStatus],
        ["Calendar Hour Convention", itProfile.calendar_hour_convention || "N/A"]
    ];
}

function alignmentAuditRowCells(row) {
    return [
        row.annual_row,
        row.it_hour_id ?? "Not Provided",
        row.it_timestamp_display,
        row.epw_month === null ? "Not Available" : `${String(row.epw_month).padStart(2, "0")}-${String(row.epw_day).padStart(2, "0")} H${String(row.epw_hour).padStart(2, "0")}`,
        Number.isFinite(row.it_load_kW) ? row.it_load_kW.toFixed(3) : "N/A",
        row.overall_alignment_status
    ];
}

function renderTimeAlignmentAudit() {
    const audit = getTimeAlignmentAudit();
    const summary = document.getElementById("timeAlignmentAuditSummary");
    const preview = document.getElementById("timeAlignmentAuditPreview");
    if (btnExportTimeAlignmentCsv) btnExportTimeAlignmentCsv.disabled = !audit.rows.length;
    if (!audit.summary) {
        if (summary) summary.textContent = "Run a validated annual simulation to inspect alignment.";
        if (preview) preview.innerHTML = "";
        return;
    }
    const s = audit.summary;
    if (summary) summary.innerHTML = [
        ["Annual Rows", s.annual_rows], ["IT Load Time Basis", s.it_time_basis], ["Hour Sequence", s.hour_sequence_validation],
        ["Calendar Time Basis", s.calendar_time_basis], ["Calendar Sequence", s.calendar_sequence_validation],
        ["Calendar Hour Convention", s.calendar_hour_convention], ["IT / Weather Alignment", s.weather_alignment],
        ["EPW Hour Convention", s.epw_hour_convention], ["Alignment Errors", s.alignment_errors]
    ].map(([label, value]) => `<span style="display:inline-block;margin:3px 16px 3px 0;"><b>${esc(label)}:</b> ${esc(value)}</span>`).join("") +
        (s.warning ? `<div style="color:#b45309;margin-top:6px;">${esc(s.warning)}</div>` : "");
    if (preview) {
        const sample = audit.rows.length <= 10 ? audit.rows : [...audit.rows.slice(0, 5), null, ...audit.rows.slice(-5)];
        preview.innerHTML = `<table><thead><tr><th>Row</th><th>IT Hour</th><th>IT Time</th><th>EPW Time</th><th>IT Load kW</th><th>Status</th></tr></thead><tbody>${sample.map(row => row
            ? `<tr>${alignmentAuditRowCells(row).map(value => `<td>${esc(value)}</td>`).join("")}</tr>`
            : '<tr><td colspan="6" style="text-align:center;">…</td></tr>').join("")}</tbody></table>`;
    }
}

function inspectTimeAlignmentAuditRow() {
    const audit = getTimeAlignmentAudit();
    const input = document.getElementById("timeAlignmentAuditRowInput");
    const target = document.getElementById("timeAlignmentAuditLookup");
    const annualRow = Number(input?.value);
    const record = Number.isInteger(annualRow) && annualRow >= 1 ? audit.rows[annualRow - 1] : null;
    if (!target) return;
    if (!record) {
        target.textContent = `Enter an annual row from 1 to ${audit.rows.length || 0}.`;
        return;
    }
    target.innerHTML = `<b>Annual Row ${record.annual_row}</b> → Internal Index ${record.internal_index}<br>` +
        `IT Hour ID: ${esc(record.it_hour_id ?? "Not Provided")}; IT timestamp: ${esc(record.it_timestamp_display)}; ` +
        `EPW: ${esc(record.epw_month)}-${esc(record.epw_day)} Hour ${esc(record.epw_hour)}; ` +
        `IT input: ${esc(record.it_load_input)} ${esc(record.it_load_input_unit)}; IT load: ${record.it_load_kW.toFixed(3)} kW; ` +
        `Status: ${esc(record.overall_alignment_status)}`;
}

function renderEngineeringResultsSummary(outObj, report, peakSummary) {
    const annual = outObj.annual_results || {};
    const project = outObj.project || {};
    const hourly = Array.isArray(outObj.hourly_results) ? outObj.hourly_results : [];
    const context = document.getElementById("engineeringContextStrip");
    const scenario = project.scenario_name || outObj.scenario_name || report?.operating_scenario?.scenario_name || "N/A";
    if (context) context.innerHTML = engineeringContextRows(outObj, report, configurationLibraryData || {})
        .map(([label, value]) => `<span style="display:inline-block; margin:4px 18px 4px 0;"><b>${esc(label)}:</b> ${esc(value)}</span>`).join("");
    setText("activeScenarioValue", scenario);
    renderTimeAlignmentAudit();

    const energy = document.getElementById("annualEnergySummaryBody");
    if (energy) energy.innerHTML = `<table><tbody>
        <tr><th>Annual Average PUE</th><td>${fmtNumber(annual.annual_average_PUE, 3)}</td></tr>
        <tr><th>Annual IT Energy</th><td>${engineeringEnergyDisplay(annual.annual_IT_energy_kWh)}</td></tr>
        <tr><th>Annual Facility Energy</th><td>${engineeringEnergyDisplay(annual.annual_facility_energy_kWh)}</td></tr>
        <tr><th>${esc(annualFacilityEnergySummary(outObj).label)}</th><td>${engineeringEnergyDisplay(annualFacilityEnergySummary(outObj).energy_kWh)}</td></tr>
        <tr><th>Annual Electrical Distribution Loss</th><td>${engineeringEnergyDisplay(annual.annual_electrical_loss_kWh)}</td></tr>
    </tbody></table>`;

    const equipment = document.getElementById("annualEquipmentEnergyBody");
    if (equipment) {
        const facility = Number(annual.annual_facility_energy_kWh) || 0;
        const rows = annualEquipmentEnergyRows(annual);
        equipment.innerHTML = `<table><thead><tr><th>Component</th><th>Annual Energy</th><th>% of Facility Energy</th></tr></thead><tbody>${[
            ...rows,
            ["Total Facility Energy", facility]
        ].map(([label, value]) => `<tr><td>${esc(label)}</td><td>${engineeringEnergyDisplay(value)}</td><td>${facility > 0 ? fmtNumber(Number(value) / facility * 100, 2) : "N/A"}%</td></tr>`).join("")}</tbody></table>`;
    }

    const performance = document.getElementById("equipmentPerformanceSummaryBody");
    const maximumHourlyValue = key => {
        const values = hourly.map(row => Number(row[key])).filter(Number.isFinite);
        return values.length ? Math.max(...values) : null;
    };
    if (performance) performance.innerHTML = `<table><tbody>${[
        ["ACC Average COP", annual.average_acc_cop],
        ["ACC Minimum COP", annual.min_acc_cop],
        ["ACC Maximum COP", annual.max_acc_cop],
        ["Maximum ACC Power", Number.isFinite(Number(annual.max_acc_power_kW)) ? `${fmtNumber(annual.max_acc_power_kW, 3)} kW` : null],
        ["ACC Capacity-Clamped Hours", annual.acc_capacity_clamped_hours],
        ["Maximum CHW Pump Load Ratio", maximumHourlyValue("pump_load_ratio_raw")],
        ["Maximum CHW Pump Power", Number.isFinite(maximumHourlyValue("pump_power_kW")) ? `${fmtNumber(maximumHourlyValue("pump_power_kW"), 3)} kW` : null],
        ["Maximum CW Pump Load Ratio", maximumHourlyValue("cw_pump_load_ratio_raw")],
        ["Maximum CW Pump Power", Number.isFinite(maximumHourlyValue("cw_pump_power_kW")) ? `${fmtNumber(maximumHourlyValue("cw_pump_power_kW"), 3)} kW` : null],
        ["Maximum ENGINE_RADIATOR Load Ratio", maximumHourlyValue("engine_radiator_load_ratio")],
        ["Maximum ENGINE_RADIATOR Fan Power", Number.isFinite(Number(annual.max_engine_radiator_power_kW)) ? `${fmtNumber(annual.max_engine_radiator_power_kW, 3)} kW` : null],
        ["Annual ENGINE_RADIATOR Fan Energy", Number.isFinite(Number(annual.annual_engine_radiator_energy_kWh)) ? engineeringEnergyDisplay(annual.annual_engine_radiator_energy_kWh) : null]
    ].filter(([, value]) => value !== null && value !== undefined).map(([label, value]) => `<tr><th>${esc(label)}</th><td>${esc(value)}</td></tr>`).join("")}</tbody></table>
        ${Number(annual.annual_engine_output_kWh) > 0 ? `<h4>Generation-Side Reference</h4><table><tbody>${[
            ["Annual Engine Output", engineeringEnergyDisplay(annual.annual_engine_output_kWh)],
            ["Annual Fuel Input", engineeringEnergyDisplay(annual.annual_engine_fuel_input_kWh)],
            ["Average Efficiency", Number.isFinite(Number(annual.average_engine_efficiency)) ? fmtNumber(annual.average_engine_efficiency, 3) : null],
            ["Annual Waste Heat", engineeringEnergyDisplay(annual.annual_engine_waste_heat_kWh)]
        ].filter(([, value]) => value !== null && value !== undefined && value !== "N/A").map(([label, value]) => `<tr><th>${esc(label)}</th><td>${esc(value)}</td></tr>`).join("")}</tbody></table>` : ""}
        <div class="muted">ENGINE_3 is generation-side equipment and is excluded from Facility Demand and PUE electrical consumption.</div>`;
}

function showProjectVisualization(outObj) {
    if (typeof Chart === "undefined") {
        log(chartUnavailableMessage());
    }

    const hourly = Array.isArray(outObj.hourly_results) ? outObj.hourly_results : [];
    const annual = outObj.annual_results || {};
    const peak = outObj.peak_results || {};
    const topologyId = outObj.topology_id || outObj.report_profile || outObj.solver_dispatch_key || "unknown";
    const report = dispatchReportProfile(topologyId, outObj);
    const peakSummary = report.visualization_data.peak_summary;
    const peakDemandBreakdown = buildPeakDemandBreakdown(outObj, peakSummary);
    renderEngineeringResultsSummary(outObj, report, peakSummary);

    const vis = document.getElementById("resultsVisualization");
    const msg = document.getElementById("noResultsMessage");
    if (vis) vis.style.display = "block";
    if (msg) msg.style.display = "none";
    const principle = document.getElementById("calculationPrinciple");
    if (principle) {
        principle.innerHTML =
            "<b>计算原理</b><br>" +
            `<div style="margin:6px 0;">Cooling System: ${esc(report.cooling_system_type)}</div>` +
            `<div style="margin:6px 0;">Simulation Engine: ${esc(report.simulation_engine)}</div>` +
            `<div style="margin:6px 0;">Performance Model: ${esc(report.performance_model)}</div>` +
            `<div style="margin:6px 0 8px 0;">Simulation Basis: ${esc(report.simulation_basis)}</div>`;
    }

    setText("summaryPueLabel", "年度平均 PUE");
    setText("summaryItLabel", "Annual IT Energy");
    setText("summaryFacilityLabel", "Annual Facility Energy");
    const peakFacilityPowerKw = peakSummary?.peak_facility_power_kW ?? peak.peak_total_facility_power_kW;
    const peakDesignFacilityPowerKw = peak.peak_design_facility_electrical_demand_kW
        ?? peak.peak_design_total_facility_power_kW;
    setText("summaryPeakLabel", "Annual Observed Peak Facility Demand");
    setText("summaryPeakDesignLabel", "Peak Design Facility Demand");
    setText("annualPueValue", fmtNumber(annual.annual_average_PUE, 3));
    setText("annualItEnergy", engineeringEnergyDisplay(annual.annual_IT_energy_kWh));
    setText("annualFacilityEnergy", engineeringEnergyDisplay(annual.annual_facility_energy_kWh));
    setText("peakFacilityPower", `${fmtInteger(peakFacilityPowerKw)} kW`);
    setText("peakDesignFacilityPower", Number.isFinite(Number(peakDesignFacilityPowerKw))
        ? `${fmtInteger(peakDesignFacilityPowerKw)} kW`
        : "N/A");
    renderProjectInfoReportPanel();
    renderSolarGainReportPanel();
    renderWeatherReportPanel();
    renderTemperatureDistributionPanel();
    renderPueContributionSummaryPanel(annual);
    renderCoolingUnitArchitecturePanel(outObj);
    renderPeakDemandBreakdown(peakDemandBreakdown);

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
        ["Other Electrical Auxiliary Energy", annual.annual_other_electrical_auxiliary_energy_kWh ?? annual.annual_auxiliary_energy_kWh, "#7c3aed"]
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
                data: report.visualization_data.temperature_vs_pue.map(row => ({
                    x: row.temperature_C,
                    y: row.pue
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
        const scenarioName = outObj.project?.scenario_name || outObj.scenario_name || "N/A";
        const cards = [
            ["Annual Observed Peak Facility Demand", `${fmtInteger(peakSummary.peak_facility_power_kW)} kW`],
            ["Peak Hour", peakSummary.peak_facility_hour],
            ["IT Load at Peak", `${fmtInteger(peakSummary.peak_it_load_kW)} kW`],
            ["Outdoor DB at Peak", `${fmtNumber(peakSummary.peak_outdoor_dry_bulb_C, 1)} deg C`],
            ["Peak Design Facility Demand", Number.isFinite(Number(peakDesignFacilityPowerKw)) ? `${fmtInteger(peakDesignFacilityPowerKw)} kW` : "N/A"],
            ["Design IT Load", Number.isFinite(Number(peak.peak_design_it_load_kW)) ? `${fmtInteger(peak.peak_design_it_load_kW)} kW` : "N/A"],
            ["Design Outdoor DB", Number.isFinite(Number(peak.peak_design_outdoor_dry_bulb_C)) ? `${fmtNumber(peak.peak_design_outdoor_dry_bulb_C, 1)} deg C` : "N/A"],
            ["Scenario", scenarioName],
            ["Maximum Hourly PUE", fmtNumber(peakSummary.max_hourly_pue, 3)],
            ["Hour of Maximum Hourly PUE", peakSummary.max_hourly_pue_hour]
        ];
        peakDetails.innerHTML = cards.map(([label, value]) => `
            <div style="border:1px solid #e5e7eb; border-radius:8px; padding:10px; background:#fafafa;">
                <div class="muted" style="font-size:12px;">${label}</div>
                <div style="font-weight:700; margin-top:4px;">${value === undefined || value === null ? "-" : value}</div>
            </div>
        `).join("");
        peakDetails.insertAdjacentHTML("beforeend", `
            <div class="muted" style="grid-column:1/-1; margin-top:4px;">Maximum facility electrical demand observed during the annual hourly simulation using the IT load profile and EPW weather data.</div>
            <div class="muted" style="grid-column:1/-1;">Facility electrical demand at 100% design IT load and the selected ASHRAE peak design outdoor condition.</div>
        `);
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
        btnRun.disabled = !configurationLibraryData;

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
    phase19bTrace("run:start", {
        libraryRun: options?.libraryRun === true,
        requestedSolverFn: options?.solverFn || null,
        providedLibraryInputAshraeTop: options?.libraryInput?.ashrae_design_conditions_url,
        providedLibraryInputAshraeProject: options?.libraryInput?.project?.ashrae_design_conditions_url
    });
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
        phase19bTrace("run:rawInput selected", {
            source: providedLibraryInput ? "providedLibraryInput" : (standardSolverInput ? "standardSolverInput" : "elIn"),
            ashrae_top: rawInput?.ashrae_design_conditions_url,
            ashrae_project: rawInput?.project?.ashrae_design_conditions_url,
            run_mode: rawInput?.run_mode,
            acc_v2: rawInput?.acc_v2
        });
        const curveLib = window.curveLib || {
            curves_1d: {},
            cop_surfaces: {}
        };

        const job = prepareSolverJob(rawInput, curveLib);
        phase19bTrace("run:job prepared", {
            kind: job.kind,
            solverFn: job.solverFn,
            ashrae_top: job.input?.ashrae_design_conditions_url,
            ashrae_project: job.input?.project?.ashrae_design_conditions_url,
            diagnostics: job.diagnostics
        });

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
        phase19bTrace("run:final JSON passed into Pyodide", {
            executedSolverFn,
            ashrae_top: job.input?.ashrae_design_conditions_url,
            ashrae_project: job.input?.project?.ashrae_design_conditions_url,
            json: job.input
        });

        const outStr = pyodide.runPython(`
import json
dc = json.loads(dc_json_str)
print("[Phase19B:Pyodide] solver_fn=", solver_fn)
print("[Phase19B:Pyodide] dc.ashrae_design_conditions_url=", dc.get("ashrae_design_conditions_url"))
print("[Phase19B:Pyodide] dc.project.ashrae_design_conditions_url=", (dc.get("project") or {}).get("ashrae_design_conditions_url"))
print("[Phase19B:Pyodide] dc.run_mode=", dc.get("run_mode"))
print("[Phase19B:Pyodide] dc.acc_v2=", dc.get("acc_v2"))
if solver_fn == "compute_acc_excel_replicated_hourly" and "compute_acc_excel_replicated_hourly" not in globals():
    raise RuntimeError("compute_acc_excel_replicated_hourly is not loaded")
if solver_fn == "dispatch_topology":
    from topology_dispatcher import dispatch_topology
    out = dispatch_topology(dc.get("configuration_manifest") or {}, dc)
else:
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

btnRun.addEventListener("click", runUsingConfigurationLibrary);
if (btnExportHtmlReport) btnExportHtmlReport.addEventListener("click", exportHtmlReport);
if (btnExportJson) btnExportJson.addEventListener("click", exportOutputJson);
if (btnExportTimeAlignmentCsv) btnExportTimeAlignmentCsv.addEventListener("click", exportTimeAlignmentAuditCsv);
document.getElementById("btnInspectTimeAlignment")?.addEventListener("click", inspectTimeAlignmentAuditRow);
elIn.addEventListener("input", () => {
    preferStandardFiles = false;
    if (standardSolverInput) {
        standardSolverInput = null;
        refreshStandardInputStatus();
        setSolverDataStatus("已切换为下方手写 JSON 输入。", "info");
    }
});
init();
