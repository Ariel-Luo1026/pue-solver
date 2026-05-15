let pyodide = null;

const elStatus = document.getElementById("status");
const elLog = document.getElementById("log");
const elIn = document.getElementById("jsonInput");
const elOut = document.getElementById("jsonOutput");
const btnRun = document.getElementById("btnRun");
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

function log(msg) { elLog.textContent = msg; }
function pretty(obj) { return JSON.stringify(obj, null, 2); }

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
    return {
        project: {
            name: "Frontend Standardized Annual PUE Project",
            calculation_mode: "project_8760",
            project_mode: true,
            it_load: {
                hourly_it_load_kW: it.slice(0, n),
                design_it_load_kW: Math.max(...it)
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

    const elecCurves = (files.electrical && files.electrical.curves) || [];
    createChart("inputElectricalChart", {
        type: "line",
        data: {
            labels: elecCurves[0] && Array.isArray(elecCurves[0].points) ? elecCurves[0].points.map(p => p[0]) : [],
            datasets: elecCurves.map((curve, i) => ({
                label: curve.curve_id,
                data: (curve.points || []).map(p => p[1]),
                borderColor: ["#2563eb", "#059669", "#f59e0b"][i % 3]
            }))
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } }
    });

    const pumpCurves = (files.pumps && files.pumps.curves) || [];
    createChart("inputPumpChart", {
        type: "line",
        data: {
            labels: pumpCurves[0] && Array.isArray(pumpCurves[0].points) ? pumpCurves[0].points.map(p => p[0]) : [],
            datasets: pumpCurves.map((curve, i) => ({
                label: curve.curve_id,
                data: (curve.points || []).map(p => p[1]),
                borderColor: ["#2563eb", "#7c3aed"][i % 2]
            }))
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } }
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
            labels: fanCurves[0] && Array.isArray(fanCurves[0].points) ? fanCurves[0].points.map(p => p[0]) : [],
            datasets: fanCurves.map((curve, i) => ({
                label: curve.curve_id,
                data: (curve.points || []).map(p => p[1]),
                borderColor: ["#0f766e", "#2563eb"][i % 2]
            }))
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } }
    });
}

function refreshStandardInputStatus() {
    const it = standardDataArray(standardDataFiles.itLoad || {}, [["data", "hourly_it_load_kW"], ["hourly_it_load_kW"], ["project", "it_load", "hourly_it_load_kW"]], ["data", "hourly_profile"], "IT_load_kW");
    const dry = standardDataArray(standardDataFiles.weather || {}, [["data", "dry_bulb_C"], ["hourly_data", "dry_bulb_C"], ["weather", "hourly_data", "dry_bulb_C"]]);
    const el = document.getElementById("standardInputStatus");
    if (el) {
        el.textContent = `标准化输入状态：IT=${it ? it.length : 0}小时，天气=${dry ? dry.length : 0}小时，${standardSolverInput ? "已生成Solver输入" : "尚未生成Solver输入"}`;
        el.style.color = standardSolverInput ? "#059669" : "#6b7280";
    }
}

async function handleStandardFile(slot, statusId, file) {
    try {
        const json = window.PueImportAdapter
            ? await window.PueImportAdapter.adaptFile(slot, file)
            : await readJsonFile(file);
        standardDataFiles[slot] = json;
        standardSolverInput = null;
        if (slot === "chiller") syncStandardChillerSurfaceToCurveLib(json);
        updateFileStatus(statusId, `${file.name} 已导入为 ${json.type || "standard_json"}`, "ok");
        previewInputCurves(standardDataFiles);
        refreshStandardInputStatus();
    } catch (e) {
        standardDataFiles[slot] = null;
        standardSolverInput = null;
        updateFileStatus(statusId, `读取失败：${String(e.message || e)}`, "error");
        refreshStandardInputStatus();
    }
}

function loadDemoStandardData() {
    const demo = buildDemoStandardData();
    Object.assign(standardDataFiles, demo);
    syncStandardChillerSurfaceToCurveLib(demo.chiller);
    standardSolverInput = null;
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

function initStandardDataInputs() {
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
        principle.innerHTML =
            "<b>计算原理</b><br>" +
            "全年模式调用 <code>compute_pue_project(dc)</code>。每小时读取 <code>project.it_load.hourly_it_load_kW</code> 与 <code>weather.hourly_data.dry_bulb_C</code>，" +
            "由电气效率曲线估算 UPS/变压器损耗，由 <code>chiller_COP_H_vs_load</code> COP 曲面估算冷水机功率，并按小时计算 " +
            "<code>PUE = total_facility_power_kW / IT_load_kW</code>。年度 PUE 使用全年设施能耗除以全年 IT 能耗。";
    }

    setText("summaryPueLabel", "年度平均 PUE");
    setText("summaryItLabel", "IT 年能耗 (kWh)");
    setText("summaryFacilityLabel", "设施总能耗 (kWh)");
    setText("summaryPeakLabel", "峰值设施功率 (kW)");
    setText("annualPueValue", fmtNumber(annual.annual_average_PUE, 3));
    setText("annualItEnergy", fmtInteger(annual.annual_IT_energy_kWh));
    setText("annualFacilityEnergy", fmtInteger(annual.annual_facility_energy_kWh));
    setText("peakFacilityPower", `${fmtInteger(peak.peak_total_facility_power_kW)} kW`);

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
        ["Chiller Energy", annual.annual_chiller_energy_kWh || annual.annual_cooling_energy_kWh, "#2563eb"],
        ["Dry Cooler Energy", annual.annual_dry_cooler_energy_kWh, "#14b8a6"],
        ["Terminal Fan Energy", annual.annual_terminal_fan_energy_kWh, "#0f766e"],
        ["Electrical Loss", annual.annual_electrical_loss_kWh, "#f59e0b"],
        ["Auxiliary Energy", annual.annual_auxiliary_energy_kWh, "#7c3aed"]
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
        const cards = [
            ["Peak Hour", peak.peak_hour_index],
            ["Peak PUE", fmtNumber(peak.peak_PUE, 3)],
            ["Dry Bulb", `${fmtNumber(peak.peak_outdoor_dry_bulb_C, 1)} deg C`],
            ["Wet Bulb", `${fmtNumber(peak.peak_outdoor_wet_bulb_C, 1)} deg C`],
            ["IT Load", `${fmtInteger(peak.peak_IT_load_kW)} kW`],
            ["Facility Power", `${fmtInteger(peak.peak_total_facility_power_kW)} kW`]
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
        ["Electrical Loss", powerLossKw, "#f59e0b"],
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
        elStatus.textContent = "正在加载 Pyodide…";
        pyodide = await loadPyodide();

        const pyText = await fetch("./solver.py").then(r => r.text());
        await pyodide.runPythonAsync(pyText);

        window.pyodide = pyodide;
        window.pyodideReady = true;

        try {
            window.curveLib = await fetch("./curves.json").then(r => r.json());
        } catch (e) {
            console.warn("curves.json 加载失败，使用空库：", e);
            window.curveLib = { curves_1d: {}, cop_surfaces: {} };
        }

        elStatus.textContent = "Pyodide 已就绪：solver.py 已加载。";
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
        elStatus.textContent = "Pyodide 加载失败（看 Log/Console）";
        log("❌ 初始化失败：\n" + String(e));
    }
}

async function run() {
    if (!pyodide) return;

    try {
        const rawInput = standardSolverInput || JSON.parse(elIn.value);
        const curveLib = window.curveLib || {
            curves_1d: {},
            cop_surfaces: {}
        };

        const job = prepareSolverJob(rawInput, curveLib);

        if (job.kind === "invalid" || job.kind === "invalid_project") {
            const d = job.diagnostics || {};
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

        pyodide.globals.set("dc_json_str", JSON.stringify(job.input));
        pyodide.globals.set("solver_fn", job.solverFn);

        const outStr = pyodide.runPython(`
import json
dc = json.loads(dc_json_str)
out = compute_pue_project(dc) if solver_fn == "compute_pue_project" else compute_pue_v04(dc)
json.dumps(out, indent=2)
        `);

        elOut.value = outStr;

        const outObj = JSON.parse(outStr);

        // Check if this is a 8760-hour project result
        const isProjectResult = outObj.annual_results && outObj.hourly_results;

        if (isProjectResult) {
            // Show visualization for 8760-hour results
            showProjectVisualization(outObj);
            const annual = outObj.annual_results || {};
            const peak = outObj.peak_results || {};
            const hourlyCount = Array.isArray(outObj.hourly_results) ? outObj.hourly_results.length : 0;
            const d = job.diagnostics || {};
            setSolverDataStatus(
                `Solver: ${job.solverFn} | IT hours=${d.itHours || 0} | weather hours=${d.weatherHours || 0} | output rows=${hourlyCount}`,
                hourlyCount > 1 ? "ok" : "error"
            );
            log(
                "Project calculation completed\n" +
                `Solver function=${job.solverFn}\n` +
                `Exact input paths=${(d.exactSolverPaths || []).join(", ")}\n` +
                `IT hours=${d.itHours || 0}, weather hours=${d.weatherHours || 0}, output hourly rows=${hourlyCount}\n` +
                (d.warning ? `Warning=${d.warning}\n` : "") +
                `Annual PUE=${fmtNumber(annual.annual_average_PUE, 3)}\n` +
                `Annual IT energy=${fmtInteger(annual.annual_IT_energy_kWh)} kWh\n` +
                `Annual facility energy=${fmtInteger(annual.annual_facility_energy_kWh)} kWh\n` +
                `Peak hour=${peak.peak_hour_index}, facility power=${fmtInteger(peak.peak_total_facility_power_kW)} kW`
            );
        } else {
            // Show compact visualization for single-point results
            showSinglePointVisualization(outObj);
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
        log("❌ Run 失败：\n" + String(e));
    }
}

btnRun.addEventListener("click", run);
elIn.addEventListener("input", () => {
    if (standardSolverInput) {
        standardSolverInput = null;
        refreshStandardInputStatus();
        setSolverDataStatus("已切换为下方手写 JSON 输入。", "info");
    }
});
init();
