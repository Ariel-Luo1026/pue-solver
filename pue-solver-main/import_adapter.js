// import_adapter.js
// Converts raw user files (JSON / EPW / Excel / XML) into the standard JSON
// objects consumed by ui.js before they are assembled for solver.py.

(function () {
    const TEXT_EXTS = [".json", ".epw", ".xml", ".csv", ".txt"];
    const EXCEL_EXTS = [".xlsx", ".xls"];

    function extOf(file) {
        const name = (file && file.name ? file.name : "").toLowerCase();
        const idx = name.lastIndexOf(".");
        return idx >= 0 ? name.slice(idx) : "";
    }

    function num(value) {
        if (value === null || value === undefined || value === "") return null;
        const n = Number(String(value).trim());
        return Number.isFinite(n) ? n : null;
    }

    function normalizeHeader(value) {
        return String(value || "")
            .trim()
            .toLowerCase()
            .replace(/\s+/g, "_")
            .replace(/[()/%]/g, "")
            .replace(/__+/g, "_");
    }

    async function readText(file) {
        return await file.text();
    }

    async function readWorkbookRows(file) {
        if (typeof XLSX === "undefined") {
            throw new Error("Excel parser is not loaded. Check the SheetJS script in index.html.");
        }
        const buf = await file.arrayBuffer();
        const workbook = XLSX.read(buf, { type: "array" });
        const sheetName = workbook.SheetNames[0];
        if (!sheetName) throw new Error("Excel workbook has no sheets.");
        const sheet = workbook.Sheets[sheetName];
        return XLSX.utils.sheet_to_json(sheet, { defval: null });
    }

    function rowsColumn(rows, candidates) {
        if (!Array.isArray(rows) || rows.length === 0) return null;
        const keys = Object.keys(rows[0] || {});
        const map = new Map(keys.map(k => [normalizeHeader(k), k]));
        let found = null;
        for (const c of candidates) {
            const key = map.get(normalizeHeader(c));
            if (key) {
                found = key;
                break;
            }
        }
        if (!found) return null;
        const values = rows.map(r => num(r[found])).filter(v => v !== null);
        return values.length > 0 ? values : null;
    }

    function rowsColumnWithKey(rows, candidates) {
        if (!Array.isArray(rows) || rows.length === 0) return null;
        const keys = Object.keys(rows[0] || {});
        const map = new Map(keys.map(k => [normalizeHeader(k), k]));
        let found = null;
        for (const c of candidates) {
            const key = map.get(normalizeHeader(c));
            if (key) {
                found = key;
                break;
            }
        }
        if (!found) return null;
        const values = rows.map(r => num(r[found])).filter(v => v !== null);
        return values.length > 0 ? { key: found, normalizedKey: normalizeHeader(found), values } : null;
    }

    function rowValue(row, candidates) {
        const keys = Object.keys(row || {});
        const map = new Map(keys.map(k => [normalizeHeader(k), k]));
        for (const c of candidates) {
            const key = map.get(normalizeHeader(c));
            if (!key) continue;
            const value = num(row[key]);
            if (value !== null) return value;
        }
        return null;
    }

    function groupedCurves2d(rows, defaultCurveId, xCandidates, yCandidates, xAxis, defaultOutput) {
        const curveIdCol = Object.keys(rows[0] || {}).find(k => normalizeHeader(k) === "curve_id");
        const grouped = {};
        if (!curveIdCol) return null;
        rows.forEach(row => {
            const id = String(row[curveIdCol] || "").trim();
            if (!id) return;
            const x = rowValue(row, xCandidates);
            const yCol = rowsColumnWithKey([row], yCandidates);
            const y = yCol && yCol.values.length > 0 ? yCol.values[0] : null;
            if (x === null || y === null) return;
            if (!grouped[id]) grouped[id] = { points: [], output: yCol.normalizedKey.includes("kw") ? "power_kW" : defaultOutput };
            grouped[id].points.push([x, y]);
        });
        const curves = Object.keys(grouped).map(id => ({
            curve_id: id || defaultCurveId,
            x_axis: xAxis,
            output: grouped[id].output,
            points: grouped[id].points
        })).filter(c => c.points.length > 0);
        return curves.length > 0 ? curves : null;
    }

    function rowsPoints2d(rows, xCandidates, yCandidates) {
        const xs = rowsColumn(rows, xCandidates);
        const ys = rowsColumn(rows, yCandidates);
        if (!xs || !ys) return null;
        const n = Math.min(xs.length, ys.length);
        return Array.from({ length: n }, (_, i) => [xs[i], ys[i]]);
    }

    function rowsPoints3d(rows, xCandidates, yCandidates, zCandidates) {
        const xs = rowsColumn(rows, xCandidates);
        const ys = rowsColumn(rows, yCandidates);
        const zs = rowsColumn(rows, zCandidates);
        if (!xs || !ys || !zs) return null;
        const n = Math.min(xs.length, ys.length, zs.length);
        return Array.from({ length: n }, (_, i) => [xs[i], ys[i], zs[i]]);
    }

    function adaptJson(json) {
        return json;
    }

    function adaptEpw(text) {
        const lines = text.split(/\r?\n/).filter(Boolean);
        const dataLines = lines.slice(8);
        const dry = [];
        const dew = [];
        const rh = [];
        const hourIndex = [];

        dataLines.forEach((line, i) => {
            const cols = line.split(",");
            if (cols.length < 9) return;
            const dryBulb = num(cols[6]);
            const dewPoint = num(cols[7]);
            const relHumidity = num(cols[8]);
            if (dryBulb === null) return;
            hourIndex.push(i + 1);
            dry.push(dryBulb);
            if (dewPoint !== null) dew.push(dewPoint);
            if (relHumidity !== null) rh.push(relHumidity);
        });

        return {
            schema_version: "pue.timeseries.weather.v1",
            type: "annual_weather",
            source_format: "epw",
            units: {
                dry_bulb_C: "degC",
                dew_point_C: "degC",
                relative_humidity_percent: "%"
            },
            data: {
                hour_index: hourIndex,
                dry_bulb_C: dry,
                dew_point_C: dew,
                relative_humidity_percent: rh
            }
        };
    }

    function adaptItExcelRows(rows) {
        const it = rowsColumn(rows, [
            "hourly_it_load_kW",
            "IT_load_kW",
            "it_load_kw",
            "IT Load kW",
            "load_kw",
            "power_kw"
        ]);
        if (!it) throw new Error("Could not find IT load column. Expected IT_load_kW or hourly_it_load_kW.");
        const hour = rowsColumn(rows, ["hour_index", "hour", "hour_of_year"]) ||
            Array.from({ length: it.length }, (_, i) => i + 1);
        return {
            schema_version: "pue.timeseries.it_load.v1",
            type: "annual_it_load",
            source_format: "excel",
            units: { hour_index: "1-8760", hourly_it_load_kW: "kW" },
            data: {
                hour_index: hour.slice(0, it.length),
                hourly_it_load_kW: it
            }
        };
    }

    function adaptWeatherExcelRows(rows) {
        const dry = rowsColumn(rows, ["dry_bulb_C", "dry bulb C", "outdoor_temp_c", "OAT", "temperature_c"]);
        if (!dry) throw new Error("Could not find dry bulb column. Expected dry_bulb_C or outdoor_temp_c.");
        const wet = rowsColumn(rows, ["wet_bulb_C", "wet bulb C", "wetbulb_c"]);
        const rh = rowsColumn(rows, ["relative_humidity_percent", "rh", "relative humidity"]);
        const hour = rowsColumn(rows, ["hour_index", "hour", "hour_of_year"]) ||
            Array.from({ length: dry.length }, (_, i) => i + 1);
        return {
            schema_version: "pue.timeseries.weather.v1",
            type: "annual_weather",
            source_format: "excel",
            units: { dry_bulb_C: "degC", wet_bulb_C: "degC" },
            data: {
                hour_index: hour.slice(0, dry.length),
                dry_bulb_C: dry,
                wet_bulb_C: wet || [],
                relative_humidity_percent: rh || []
            }
        };
    }

    function adaptCurveExcelRows(rows, slot) {
        if (slot === "chiller") {
            const points = rowsPoints3d(
                rows,
                ["condenser_entering_water_C", "cooling_water_entering_C", "oat_c", "temperature_c", "x"],
                ["load_ratio", "plr", "load_percent", "y"],
                ["COP", "cop", "z"]
            );
            if (!points) throw new Error("Chiller Excel needs columns for temperature, load_ratio/PLR, and COP.");
            return {
                schema_version: "pue.curve.chiller_cop_surface.v1",
                type: "chiller_cop_surface",
                source_format: "excel",
                curve_id: "chiller_COP_H_vs_load",
                x_axis: "condenser_entering_water_C",
                y_axis: "load_ratio",
                output: "COP",
                interpolation: "bilinear_or_pchip",
                points
            };
        }

        if (slot === "electrical") {
            const curveIdCol = Object.keys(rows[0] || {}).find(k => normalizeHeader(k) === "curve_id");
            const grouped = {};
            if (curveIdCol) {
                rows.forEach(row => {
                    const id = String(row[curveIdCol] || "").trim();
                    if (!id) return;
                    grouped[id] = grouped[id] || [];
                    const x = rowValue(row, ["load_ratio", "load ratio", "x"]);
                    const y = rowValue(row, ["efficiency", "eta", "y"]);
                    if (x !== null && y !== null) grouped[id].push([x, y]);
                });
            }
            const curves = Object.keys(grouped).map(id => ({
                curve_id: id,
                x_axis: "load_ratio",
                output: "efficiency",
                points: grouped[id]
            })).filter(c => c.points.length > 0);
            if (curves.length === 0) {
                const points = rowsPoints2d(rows, ["load_ratio", "x"], ["efficiency", "y"]);
                if (!points) throw new Error("Electrical Excel needs load_ratio and efficiency columns.");
                curves.push({
                    curve_id: "UPS_efficiency_double_conversion",
                    x_axis: "load_ratio",
                    output: "efficiency",
                    points
                });
            }
            return {
                schema_version: "pue.curve.electrical.v1",
                type: "electrical_efficiency_curves",
                source_format: "excel",
                curves
            };
        }

        if (slot === "pumps") {
            const grouped = groupedCurves2d(
                rows,
                "chw_pump_power_vs_it_load",
                ["it_load_ratio", "load_ratio", "x"],
                ["power_kw", "power_kW", "power_factor", "y"],
                "it_load_ratio",
                "power_factor"
            );
            if (grouped) {
                return {
                    schema_version: "pue.curve.pumps.v1",
                    type: "pump_power_curves",
                    source_format: "excel",
                    curves: grouped
                };
            }
            const points = rowsPoints2d(rows, ["it_load_ratio", "load_ratio", "x"], ["power_factor", "power_kw", "y"]);
            if (!points) throw new Error("Pump Excel needs it_load_ratio/load_ratio and power_factor/power_kw columns.");
            return {
                schema_version: "pue.curve.pumps.v1",
                type: "pump_power_curves",
                source_format: "excel",
                curves: [
                    {
                        curve_id: "chw_pump_power_vs_it_load",
                        x_axis: "it_load_ratio",
                        output: "power_factor",
                        points
                    }
                ]
            };
        }

        if (slot === "fans") {
            const grouped = groupedCurves2d(
                rows,
                "terminal_fan_power_vs_it_load",
                ["it_load_ratio", "load_ratio", "airflow_ratio", "x"],
                ["power_kw", "power_kW", "fan_power_kw", "power_factor", "y"],
                "it_load_ratio",
                "power_factor"
            );
            if (grouped) {
                return {
                    schema_version: "pue.curve.fans.v1",
                    type: "terminal_fan_power_curves",
                    source_format: "excel",
                    curves: grouped
                };
            }
            const points = rowsPoints2d(rows, ["it_load_ratio", "load_ratio", "airflow_ratio", "x"], ["power_factor", "power_kw", "fan_power_kw", "y"]);
            if (!points) throw new Error("Fan Excel needs it_load_ratio/load_ratio and power_factor/power_kw columns.");
            return {
                schema_version: "pue.curve.fans.v1",
                type: "terminal_fan_power_curves",
                source_format: "excel",
                curves: [
                    {
                        curve_id: "terminal_fan_power_vs_it_load",
                        x_axis: "it_load_ratio",
                        output: "power_factor",
                        points
                    }
                ]
            };
        }

        if (slot === "dryCooler") {
            const powerX = rowsColumnWithKey(rows, ["load_ratio", "it_load_ratio", "plr", "x"]);
            const powerY = rowsColumnWithKey(rows, ["power_kw", "fan_power_kw", "power_kW", "power_factor", "power", "y"]);
            const powerPoints = powerX && powerY
                ? Array.from({ length: Math.min(powerX.values.length, powerY.values.length) }, (_, i) => [powerX.values[i], powerY.values[i]])
                : null;
            const powerOutput = powerY && powerY.normalizedKey.includes("kw") ? "power_kW" : "power_factor";
            const leavingWaterTempPoints = rowsPoints2d(
                rows,
                ["outdoor_dry_bulb_C", "oat_c", "temperature_c"],
                ["leaving_water_C", "leaving_water_temp_C", "outlet_water_C", "outlet_water_temp_C", "condenser_entering_water_C", "cooling_water_entering_C"]
            );
            if (!powerPoints) throw new Error("Dry cooler Excel needs load_ratio/it_load_ratio and power_factor/power_kw columns.");
            return {
                schema_version: "pue.curve.dry_cooler.v1",
                type: "dry_cooler_performance",
                source_format: "excel",
                curves: [
                    {
                        curve_id: "dry_cooler_power_vs_load",
                        x_axis: "load_ratio",
                        output: powerOutput,
                        points: powerPoints
                    },
                    ...(leavingWaterTempPoints ? [{
                        curve_id: "dry_cooler_leaving_water_temp_vs_oat",
                        x_axis: "outdoor_dry_bulb_C",
                        output: "leaving_water_C",
                        points: leavingWaterTempPoints
                    }] : [])
                ],
                interpolation: "linear",
            };
        }

        throw new Error(`Unsupported Excel slot: ${slot}`);
    }

    function adaptXml(text, slot) {
        const doc = new DOMParser().parseFromString(text, "application/xml");
        const parserError = doc.querySelector("parsererror");
        if (parserError) throw new Error("Invalid XML file.");

        const pointNodes = [
            ...Array.from(doc.getElementsByTagName("point")),
            ...Array.from(doc.getElementsByTagName("Point"))
        ];
        const pointFromNode = (p) => {
            const x = num(p.getAttribute("x") || p.getAttribute("load_ratio") || p.getAttribute("plr") || p.getAttribute("oat_c") || p.getAttribute("outdoor_dry_bulb_C") || p.getAttribute("temperature"));
            const y = num(p.getAttribute("y") || p.getAttribute("efficiency") || p.getAttribute("leaving_water_C") || p.getAttribute("outlet_water_C") || p.getAttribute("capacity_factor") || p.getAttribute("power_factor"));
            const z = num(p.getAttribute("z") || p.getAttribute("cop") || p.getAttribute("COP"));
            return z === null ? [x, y] : [x, y, z];
        };
        const points = pointNodes.map(pointFromNode).filter(p => p.every(v => v !== null));

        if (slot === "chiller") {
            const pts3 = points.filter(p => p.length === 3);
            if (pts3.length === 0) throw new Error("Chiller XML needs point x/y/z or temperature/plr/cop attributes.");
            return {
                schema_version: "pue.curve.chiller_cop_surface.v1",
                type: "chiller_cop_surface",
                source_format: "xml",
                curve_id: doc.documentElement.getAttribute("curve_id") || "chiller_COP_H_vs_load",
                x_axis: "condenser_entering_water_C",
                y_axis: "load_ratio",
                output: "COP",
                interpolation: "bilinear_or_pchip",
                points: pts3
            };
        }

        const pts2 = points.filter(p => p.length === 2);
        if (pts2.length === 0) throw new Error("XML needs point x/y attributes.");
        if (slot === "dryCooler") {
            const curveNodes = [
                ...Array.from(doc.getElementsByTagName("curve")),
                ...Array.from(doc.getElementsByTagName("Curve"))
            ];
            const curves = curveNodes.map((node, i) => {
                const children = [
                    ...Array.from(node.getElementsByTagName("point")),
                    ...Array.from(node.getElementsByTagName("Point"))
                ];
                const nodePoints = children.map(pointFromNode).filter(p => p.length === 2 && p.every(v => v !== null));
                if (nodePoints.length === 0) return null;
                return {
                    curve_id: node.getAttribute("curve_id") || node.getAttribute("id") || (i === 0 ? "dry_cooler_power_vs_load" : "dry_cooler_leaving_water_temp_vs_oat"),
                    x_axis: node.getAttribute("x_axis") || (i === 0 ? "load_ratio" : "outdoor_dry_bulb_C"),
                    output: node.getAttribute("output") || (i === 0 ? "power_factor" : "leaving_water_C"),
                    points: nodePoints
                };
            }).filter(Boolean);
            if (curves.length > 0) {
                return {
                    schema_version: "pue.curve.dry_cooler.v1",
                    type: "dry_cooler_performance",
                    source_format: "xml",
                    curves
                };
            }
            return {
                schema_version: "pue.curve.dry_cooler.v1",
                type: "dry_cooler_performance",
                source_format: "xml",
                curves: [{
                    curve_id: doc.documentElement.getAttribute("curve_id") || "dry_cooler_power_vs_load",
                    x_axis: doc.documentElement.getAttribute("x_axis") || "load_ratio",
                    output: doc.documentElement.getAttribute("output") || "power_factor",
                    points: pts2
                }]
            };
        }
        if (slot === "electrical") {
            return {
                schema_version: "pue.curve.electrical.v1",
                type: "electrical_efficiency_curves",
                source_format: "xml",
                curves: [{
                    curve_id: doc.documentElement.getAttribute("curve_id") || "UPS_efficiency_double_conversion",
                    x_axis: "load_ratio",
                    output: "efficiency",
                    points: pts2
                }]
            };
        }
        if (slot === "pumps") {
            return {
                schema_version: "pue.curve.pumps.v1",
                type: "pump_power_curves",
                source_format: "xml",
                curves: [{
                    curve_id: doc.documentElement.getAttribute("curve_id") || "chw_pump_power_vs_it_load",
                    x_axis: "it_load_ratio",
                    output: "power_factor",
                    points: pts2
                }]
            };
        }
        if (slot === "fans") {
            return {
                schema_version: "pue.curve.fans.v1",
                type: "terminal_fan_power_curves",
                source_format: "xml",
                curves: [{
                    curve_id: doc.documentElement.getAttribute("curve_id") || "terminal_fan_power_vs_it_load",
                    x_axis: doc.documentElement.getAttribute("x_axis") || "it_load_ratio",
                    output: doc.documentElement.getAttribute("output") || "power_factor",
                    points: pts2
                }]
            };
        }
        throw new Error(`Unsupported XML slot: ${slot}`);
    }

    async function adaptFile(slot, file) {
        const ext = extOf(file);
        if (ext === ".json") return adaptJson(JSON.parse(await readText(file)));
        if (ext === ".epw") return adaptEpw(await readText(file));
        if (ext === ".xml") return adaptXml(await readText(file), slot);
        if (EXCEL_EXTS.includes(ext)) {
            const rows = await readWorkbookRows(file);
            if (slot === "itLoad") return adaptItExcelRows(rows);
            if (slot === "weather") return adaptWeatherExcelRows(rows);
            return adaptCurveExcelRows(rows, slot);
        }
        if (TEXT_EXTS.includes(ext)) {
            throw new Error(`${ext} is text, but no adapter is defined for slot ${slot}. Use JSON/XML/EPW or Excel.`);
        }
        throw new Error(`Unsupported file extension: ${ext || "(none)"}`);
    }

    window.PueImportAdapter = {
        adaptFile,
        adaptEpw,
        adaptJson,
        adaptXml,
        adaptItExcelRows,
        adaptWeatherExcelRows,
        adaptCurveExcelRows
    };
})();
