let pyodide = null;

const elStatus = document.getElementById("status");
const elLog = document.getElementById("log");
const elIn = document.getElementById("jsonInput");
const elOut = document.getElementById("jsonOutput");
const btnRun = document.getElementById("btnRun");
const btnExportHtmlReport = document.getElementById("btnExportHtmlReport");
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
const equipmentPdfSpecs = {};

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
    const stage = textValue("projectStageInput");
    return {
        name: textValue("projectNameInput"),
        location: textValue("projectLocationInput"),
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

function getSolarGainReportInput() {
    return {
        annualKwh: optionalNonNegativeNumber("solarGainAnnualKwh"),
        peakKw: optionalNonNegativeNumber("solarGainPeakKw")
    };
}

function updateSolarGainStatus() {
    const status = document.getElementById("statusSolarGain");
    if (!status) return;
    const solar = getSolarGainReportInput();
    if (solar.annualKwh === null && solar.peakKw === null) {
        status.textContent = "报告展示项：不会写入 solver 输入";
        status.style.color = "#6b7280";
        return;
    }
    const parts = [];
    if (solar.annualKwh !== null) parts.push(`年得热 ${fmtInteger(solar.annualKwh)} kWh`);
    if (solar.peakKw !== null) parts.push(`峰值得热 ${fmtNumber(solar.peakKw, 1)} kW`);
    status.textContent = `${parts.join("，")}；仅用于报告展示`;
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
    const solar = getSolarGainReportInput();
    if (solar.annualKwh === null && solar.peakKw === null) {
        panel.style.display = "none";
        panel.innerHTML = "";
        return;
    }
    const values = [];
    if (solar.annualKwh !== null) values.push(`年日照得热量：<b>${fmtInteger(solar.annualKwh)} kWh</b>`);
    if (solar.peakKw !== null) values.push(`峰值日照得热：<b>${fmtNumber(solar.peakKw, 1)} kW</b>`);
    panel.style.display = "block";
    panel.innerHTML =
        "<b>报告补充：日照得热负荷</b><br>" +
        values.join("；") +
        "。该项仅作为围护结构/外部热扰动背景说明，未写入 solver 输入，也不参与 PUE、设施能耗、冷源能耗或峰值小时计算。";
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

function renderWeatherReportPanel() {
    const panel = document.getElementById("weatherReportPanel");
    if (!panel) return;
    const weather = standardDataFiles.weather || {};
    const data = weather.data || weather.hourly_data || {};
    const source = String(weather.source_format || "").toLowerCase();
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
        "。这些信息用于解释气候背景和太阳得热风险，当前不参与 PUE 计算。";
}

function classifyEquipmentCategory(text, filename = "") {
    const hay = `${filename} ${text}`.toLowerCase();
    if (/chiller|冷水机|cop|centrifugal/.test(hay)) return "Chiller COP Surface";
    if (/dry\s*cooler|干冷|adiabatic|fluid cooler/.test(hay)) return "Dry Cooler";
    if (/pump|水泵|chw|cw pump/.test(hay)) return "Pumps";
    if (/fan|terminal|末端|airflow|ahu|crac|cra h/.test(hay)) return "Terminal Fans";
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
    return {
        saved_at: new Date().toISOString(),
        project_info: {
            name: document.getElementById("projectNameInput")?.value || "",
            location: document.getElementById("projectLocationInput")?.value || "",
            capacity_mw: document.getElementById("projectCapacityMwInput")?.value || "",
            stage: document.getElementById("projectStageInput")?.value || "",
            version: document.getElementById("projectVersionInput")?.value || "v1.0"
        },
        report_only_inputs: {
            solar_gain_annual_kwh: document.getElementById("solarGainAnnualKwh")?.value || "",
            solar_gain_peak_kw: document.getElementById("solarGainPeakKw")?.value || "",
            aux_fixed_coeff: document.getElementById("auxFixedCoeff")?.value || "0.005",
            dry_cooler_approach_c: document.getElementById("dryCoolerApproachC")?.value || "5"
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
        if (document.getElementById("projectCapacityMwInput")) document.getElementById("projectCapacityMwInput").value = info.capacity_mw || "";
        if (document.getElementById("projectStageInput")) document.getElementById("projectStageInput").value = info.stage || "";
        if (document.getElementById("projectVersionInput")) document.getElementById("projectVersionInput").value = info.version || "v1.0";
        if (document.getElementById("solarGainAnnualKwh")) document.getElementById("solarGainAnnualKwh").value = report.solar_gain_annual_kwh || "";
        if (document.getElementById("solarGainPeakKw")) document.getElementById("solarGainPeakKw").value = report.solar_gain_peak_kw || "";
        if (document.getElementById("auxFixedCoeff")) document.getElementById("auxFixedCoeff").value = report.aux_fixed_coeff || "0.005";
        if (document.getElementById("dryCoolerApproachC")) document.getElementById("dryCoolerApproachC").value = report.dry_cooler_approach_c || "5";

        Object.keys(standardDataFiles).forEach(key => { standardDataFiles[key] = payload.standard_data_files?.[key] || null; });
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
        renderProjectInfoReportPanel();
        renderSolarGainReportPanel();
        renderWeatherReportPanel();
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
    return `
        <svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(opts.title || "line chart")}">
            ${svgGrid(width, height, pad, xTicks, yTicks, sx, sy)}
            <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" class="axis" />
            <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" class="axis" />
            <text x="${pad}" y="${pad - 12}" class="tick">${esc(opts.yLabel || "")}</text>
            <text x="${width - pad}" y="${height - 12}" text-anchor="end" class="tick">${esc(opts.xLabel || "")}</text>
            <polyline points="${points}" class="line" />
            ${svgTracer(sx(maxPoint.index), sy(maxPoint.value), width, height, pad, `max ${reportValue(maxPoint.value, "", 2)}`)}
        </svg>`;
}

function svgBarChart(items, opts = {}) {
    const width = opts.width || 920;
    const height = opts.height || 280;
    const pad = 42;
    const rows = (items || []).filter(item => Number.isFinite(Number(item.value)));
    if (!rows.length) return `<div class="empty">Not enough data</div>`;
    const max = Math.max(...rows.map(item => Number(item.value)), 1);
    const barGap = 8;
    const barWidth = (width - pad * 2 - barGap * (rows.length - 1)) / rows.length;
    const bars = rows.map((item, i) => {
        const value = Number(item.value);
        const h = ((height - pad * 2) * value) / max;
        const x = pad + i * (barWidth + barGap);
        const y = height - pad - h;
        return `
            <rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${Math.max(1, barWidth).toFixed(1)}" height="${h.toFixed(1)}" class="bar" />
            <text x="${(x + barWidth / 2).toFixed(1)}" y="${height - 16}" text-anchor="middle" class="tick">${esc(item.label)}</text>`;
    }).join("");
    return `
        <svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(opts.title || "bar chart")}">
            <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" class="axis" />
            <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" class="axis" />
            <text x="${pad}" y="${pad - 12}" class="tick">${esc(opts.yLabel || "")}</text>
            <text x="${pad + 4}" y="${pad + 12}" class="tick">${reportValue(max, "", 2)}</text>
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
    return `
        <svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(opts.title || "curve chart")}">
            ${svgGrid(width, height, pad, xTicks, yTicks, sx, sy)}
            <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" class="axis" />
            <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" class="axis" />
            <text x="${pad}" y="${pad - 12}" class="tick">${esc(opts.yLabel || "")}</text>
            <text x="${width - pad}" y="${height - 12}" text-anchor="end" class="tick">${esc(opts.xLabel || "")}</text>
            <polyline points="${poly}" class="line" />
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
    const colors = ["#2563EB", "#059669", "#DC2626", "#7C3AED", "#EA580C", "#0891B2", "#DB2777", "#65A30D"];
    const lines = prepared.map((curve, i) => {
        const pts = curve.points.map(([x, y]) => `${sx(x).toFixed(1)},${sy(y).toFixed(1)}`).join(" ");
        return `<polyline points="${pts}" fill="none" stroke="${colors[i % colors.length]}" stroke-width="2.2" />`;
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
    addCurveList("Terminal Fans", standardDataFiles.fans);

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
        const colors = ["#2563EB", "#059669", "#DC2626", "#7C3AED", "#EA580C", "#0891B2"];
        const lines = groupKeys.slice(0, 8).map((key, i) => {
            const pts = groups[key].sort((a, b) => a[0] - b[0]).map(([x, y]) => `${sx(x).toFixed(1)},${sy(y).toFixed(1)}`).join(" ");
            return `<polyline points="${pts}" fill="none" stroke="${colors[i % colors.length]}" stroke-width="2" />`;
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
        ["Dry Bulb Temperature", weatherData.dry_bulb_C, "°C"],
        ["Dew Point Temperature", weatherData.dew_point_C, "°C"],
        ["Relative Humidity", weatherData.relative_humidity_percent, "%"],
        ["Global Horizontal Radiation", weatherData.global_horizontal_radiation_Wh_m2, "Wh/m²"],
        ["Direct Normal Radiation", weatherData.direct_normal_radiation_Wh_m2, "Wh/m²"],
        ["Wind Speed", weatherData.wind_speed_m_s, "m/s"],
        ["Atmospheric Pressure", weatherData.atmospheric_pressure_Pa, "Pa"],
        ["Total Sky Cover", weatherData.total_sky_cover_tenths, "tenths"]
    ].filter(([, values]) => Array.isArray(values) && values.length > 1);
    if (!charts.length) return `<div class="empty">No extended EPW weather fields available.</div>`;
    return `<div class="grid">${charts.map(([title, values, unit]) => `
        <div class="card"><h3>${esc(title)}</h3>${svgLineChart(values, { yLabel: unit, xLabel: "Hour of Year", maxPoints: 700 })}</div>
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

function buildHtmlReport(context) {
    const output = context.output || {};
    const hourly = Array.isArray(output.hourly_results) ? output.hourly_results : [];
    const annual = output.annual_results || {};
    const peak = output.peak_results || {};
    const projectInfo = getProjectReportInfo();
    const solar = getSolarGainReportInput();
    const weather = standardDataFiles.weather || {};
    const weatherData = weather.data || weather.hourly_data || {};
    const it = standardDataArray(standardDataFiles.itLoad || {}, [["data", "hourly_it_load_kW"], ["hourly_it_load_kW"], ["project", "it_load", "hourly_it_load_kW"]], ["data", "hourly_profile"], "IT_load_kW");
    const dry = standardDataArray(standardDataFiles.weather || {}, [["data", "dry_bulb_C"], ["hourly_data", "dry_bulb_C"], ["weather", "hourly_data", "dry_bulb_C"]]);
    const pueSeries = hourly.map(row => Number(row.hourly_PUE)).filter(Number.isFinite);
    const facilitySeries = hourly.map(row => Number(row.total_facility_power_kW)).filter(Number.isFinite);
    const monthlyPue = groupHourlyByMonth(hourly, row => Number(row.hourly_PUE));
    const reportCurves = collectReportCurves();
    const curveGroups = groupReportCurves(reportCurves);
    const drySummary = summarizeNumericArray(dry);
    const itSummary = summarizeNumericArray(it);
    const ghiSummary = summarizeNumericArray(weatherData.global_horizontal_radiation_Wh_m2);
    const windSummary = summarizeNumericArray(weatherData.wind_speed_m_s);
    const rhSummary = summarizeNumericArray(weatherData.relative_humidity_percent);
    const place = projectInfo.location || [weather.location?.city, weather.location?.state_or_region, weather.location?.country].filter(Boolean).join(", ") || "N/A";
    const reportTitle = projectInfo.name || "Annual Data Center PUE Performance Assessment";
    const generated = new Date().toISOString();
    const energyRows = [
        ["IT Energy", annual.annual_IT_energy_kWh],
        ["Chiller Energy", annual.annual_chiller_energy_kWh || annual.annual_cooling_energy_kWh],
        ["Dry Cooler Energy", annual.annual_dry_cooler_energy_kWh],
        ["Terminal Fan Energy", annual.annual_terminal_fan_energy_kWh],
        ["Electrical Loss", annual.annual_electrical_loss_kWh],
        ["Auxiliary Energy", annual.annual_auxiliary_energy_kWh]
    ].filter(([, value]) => Number(value) > 0);
    const energyChart = svgBarChart(energyRows.map(([label, value]) => ({ label: label.replace(" Energy", "").replace("Electrical ", "Elec "), value: Number(value) / 1000 })), { yLabel: "MWh" });
    const monthlyChart = svgBarChart(monthlyPue.map(row => ({ label: row.month, value: row.value })), { yLabel: "PUE" });
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
    :root { --ink:#0F172A; --muted:#475569; --line:#CBD5E1; --soft:#F8FAFC; --accent:#2563EB; --green:#059669; --red:#DC2626; --violet:#7C3AED; }
    body { margin:0; font-family: Inter, "Times New Roman", Georgia, serif; color:var(--ink); background:#fff; }
    .page { max-width: 1260px; margin: 0 auto; padding: 28px 24px 46px; }
    header { border-bottom: 2px solid var(--ink); padding-bottom: 18px; margin-bottom: 18px; }
    h1 { margin:0 0 8px; font-size: 30px; line-height:1.15; letter-spacing: 0; font-weight:760; }
    h2 { margin:24px 0 10px; font-size: 19px; border-bottom: 1px solid var(--line); padding-bottom: 6px; font-weight:760; }
    h3 { margin:12px 0 8px; font-size: 15px; font-weight:740; }
    p { line-height: 1.65; color: var(--muted); text-align: justify; }
    code { font-family: "Courier New", monospace; font-size: 12.5px; }
    .subtitle { color:var(--muted); font-size: 14px; line-height:1.45; }
    .meta { display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
    .metric { border:1px solid var(--line); border-radius:8px; padding:10px; background:var(--soft); }
    .metric .label { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.04em; font-family: Arial, sans-serif; }
    .metric .value { font-size:21px; font-weight:760; margin-top:4px; color:var(--accent); }
    table { width:100%; border-collapse:collapse; margin:8px 0 12px; font-size: 12.5px; }
    th, td { border:1px solid var(--line); padding:6px 8px; vertical-align:top; }
    th { width:32%; text-align:left; background:#EEF2F7; }
    .mini { margin: 4px 0 10px; font-size: 12px; }
    .mini th { width: 28%; }
    .grid { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap:12px; align-items:start; }
    .curveGrid { display:grid; grid-template-columns: 1fr; gap:14px; }
    .card { border:1px solid var(--line); border-radius:8px; padding:10px; break-inside: avoid; background:#fff; }
    .chart { width:100%; height:auto; background:#fff; border:1px solid var(--line); border-radius:8px; }
    .axis { stroke:#94A3B8; stroke-width:1; }
    .gridLine { stroke:#E2E8F0; stroke-width:1; }
    .traceLine { stroke:#0F172A; stroke-width:1; stroke-dasharray:4 4; opacity:.42; }
    .tracePoint { fill:#fff; stroke:#0F172A; stroke-width:1.8; }
    .traceLabel { fill:#0F172A; font: 11px Arial, sans-serif; }
    .line { fill:none; stroke:var(--accent); stroke-width:2; }
    .bar { fill:var(--accent); opacity:.9; }
    .tick { fill:#64748B; font-size:11px; font-family: Arial, sans-serif; }
    .legend { color:var(--muted); font-size:11.5px; margin-top:6px; line-height:1.5; display:flex; flex-wrap:wrap; gap:8px 14px; }
    .legendItem { white-space:nowrap; }
    .note { background:#EFF6FF; border-left:4px solid var(--accent); padding:8px 10px; color:#1E3A8A; }
    .empty { border:1px dashed var(--line); border-radius:8px; padding:18px; color:var(--muted); text-align:center; }
    .caption { font-size:12px; color:#333; text-align:center; margin-top:8px; font-style:italic; }
    .specBlock { margin-top:10px; padding:8px 10px; border-left:3px solid var(--accent); background:#F8FAFC; font-size:12.5px; color:#334155; }
    .formulaGrid { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap:10px; margin:10px 0 12px; }
    .formulaBox { border:1px solid var(--line); border-radius:8px; padding:10px; background:#fff; min-height:68px; }
    .formulaName { font: 700 12px Arial, sans-serif; color:var(--muted); text-transform:uppercase; letter-spacing:.035em; margin-bottom:8px; }
    .math { font-family: "Times New Roman", Georgia, serif; font-size:18px; color:#111827; }
    .math i { font-style: italic; }
    .frac { display:inline-flex; flex-direction:column; vertical-align:middle; text-align:center; line-height:1.12; margin:0 4px; }
    .frac span:first-child { border-bottom:1px solid #111; padding:0 5px 2px; }
    .frac span:last-child { padding-top:2px; }
    @media (max-width: 900px) { .grid, .meta, .formulaGrid { grid-template-columns: 1fr; } }
    @media print { .page { max-width:none; padding:12mm; } .card, table, .chart { break-inside: avoid; } }
</style>
</head>
<body>
<main class="page">
<header>
    <h1>${esc(reportTitle)}</h1>
    <div class="subtitle">Integrated Cooling Plant and Electrical Infrastructure Energy Analysis</div>
    <div class="subtitle">Generated by Codex HTML Report Generator · ${esc(generated)}</div>
</header>

<section>
    <h2>1. Executive Summary</h2>
    <div class="meta">
        <div class="metric"><div class="label">Annual Average PUE</div><div class="value">${reportValue(annual.annual_average_PUE, "", 3)}</div></div>
        <div class="metric"><div class="label">Peak Facility Power</div><div class="value">${reportValue(peak.peak_total_facility_power_kW, " kW", 0)}</div></div>
        <div class="metric"><div class="label">IT Energy</div><div class="value">${reportValue((annual.annual_IT_energy_kWh || 0) / 1000, " MWh", 0)}</div></div>
        <div class="metric"><div class="label">Facility Energy</div><div class="value">${reportValue((annual.annual_facility_energy_kWh || 0) / 1000, " MWh", 0)}</div></div>
    </div>
    <table><tbody>${tableRows([
        ["Site Location", esc(place)],
        ["Design IT Load", projectInfo.capacityMw !== null ? `${reportValue(projectInfo.capacityMw, " MW", 1)}` : "N/A"],
        ["Project Stage", esc(projectInfo.stage || "N/A")],
        ["Minimum Hourly PUE", reportValue(annual.min_hourly_PUE, "", 3)],
        ["Maximum Hourly PUE", reportValue(annual.max_hourly_PUE, "", 3)],
        ["Peak Facility Hour", esc(peak.peak_hour_index ?? "N/A")]
    ])}</tbody></table>
</section>

<section>
    <h2>2. Methodology</h2>
    <p>The annual calculation uses <code>compute_pue_project(dc)</code>. Each hour combines IT load, outdoor dry bulb temperature, equipment curves, electrical losses, cooling power, pump/fan power, and auxiliary load coefficient where configured.</p>
    <div class="note">Project metadata, EPW extended weather information, and user-entered solar heat gain are report-only context in this version. They do not modify solver inputs or calculated PUE.</div>
    <h3>Mathematical Framework</h3>
    ${formulasHtml()}
    <table><tbody>${tableRows([
        ["PUE Definition", "<code>PUE = P_facility / P_IT</code>"],
        ["Cooling Power", "<code>P_cooling = P_chiller + P_dry_cooler</code> plus pump/fan terms reported separately where available"],
        ["Chiller COP", "<code>COP = Q_cooling / P_compressor</code>"],
        ["Dry Cooler Approach", "<code>T_LWT = T_ambient + Approach</code> when no explicit leaving-water curve is supplied"],
        ["Not Currently Modeled", "Cooling mode classification, free-cooling hours, solar heat gain impact on cooling load"]
    ])}</tbody></table>
</section>

<section>
    <h2>3. Input Datasets and Weather Analysis</h2>
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
    <h2>4. Equipment Curve Register</h2>
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
</section>

<section>
    <h2>5. Annual Simulation Results</h2>
    <table><tbody>${tableRows([
        ["Annual IT Energy", reportValue(annual.annual_IT_energy_kWh, " kWh", 0)],
        ["Annual Facility Energy", reportValue(annual.annual_facility_energy_kWh, " kWh", 0)],
        ["Annual Cooling Energy", reportValue(annual.annual_cooling_energy_kWh, " kWh", 0)],
        ["Annual Chiller Energy", reportValue(annual.annual_chiller_energy_kWh, " kWh", 0)],
        ["Annual Dry Cooler Energy", reportValue(annual.annual_dry_cooler_energy_kWh, " kWh", 0)],
        ["Annual Terminal Fan Energy", reportValue(annual.annual_terminal_fan_energy_kWh, " kWh", 0)],
        ["Annual Electrical Loss", reportValue(annual.annual_electrical_loss_kWh, " kWh", 0)],
        ["Annual Auxiliary Energy", reportValue(annual.annual_auxiliary_energy_kWh, " kWh", 0)]
    ])}</tbody></table>
    <div class="grid">
        <div class="card"><h3>8760 Annual PUE Timeseries</h3>${svgLineChart(pueSeries, { yLabel: "PUE", xLabel: "Hour of Year" })}</div>
        <div class="card"><h3>Facility Power Timeseries</h3>${svgLineChart(facilitySeries, { yLabel: "kW", xLabel: "Hour of Year" })}</div>
        <div class="card"><h3>Annual Energy Breakdown</h3>${energyChart}</div>
        <div class="card"><h3>Monthly Average PUE</h3>${monthlyChart}</div>
    </div>
</section>

<section>
    <h2>6. Engineering Discussion</h2>
    <p>The computed annual average PUE is <b>${reportValue(annual.annual_average_PUE, "", 3)}</b>. Cooling performance should be interpreted against outdoor dry bulb conditions and the supplied COP/dry-cooler curves. Free-cooling and hybrid-cooling hour counts are not reported as calculated KPIs because the current solver does not explicitly classify operating modes.</p>
    <table><tbody>${tableRows([
        ["Report-only Solar Heat Gain", solar.annualKwh !== null || solar.peakKw !== null ? `${solar.annualKwh !== null ? reportValue(solar.annualKwh, " kWh", 0) : "N/A annual"}; ${solar.peakKw !== null ? reportValue(solar.peakKw, " kW peak", 1) : "N/A peak"}` : "Not provided"],
        ["Free Cooling Hours", "Not modeled in current solver"],
        ["Mechanical Cooling Hours", "Not modeled in current solver"]
    ])}</tbody></table>
</section>

<section>
    <h2>7. Conclusion</h2>
    <p>This report provides a transparent annual PUE assessment based on the currently loaded input datasets and solver outputs. Values that are not produced by the solver are explicitly marked as contextual or not modeled.</p>
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
    const html = buildHtmlReport(lastReportContext);
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
        renderWeatherReportPanel();
        refreshStandardInputStatus();
    } catch (e) {
        standardDataFiles[slot] = null;
        standardSolverInput = null;
        preferStandardFiles = true;
        updateFileStatus(statusId, `读取失败：${String(e.message || e)}`, "error");
        refreshStandardInputStatus();
    }
}

function loadDemoStandardData() {
    const demo = buildDemoStandardData();
    Object.assign(standardDataFiles, demo);
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
    ["solarGainAnnualKwh", "solarGainPeakKw"].forEach((id) => {
        const input = document.getElementById(id);
        if (!input) return;
        input.addEventListener("input", () => {
            updateSolarGainStatus();
            renderSolarGainReportPanel();
        });
    });
    ["projectNameInput", "projectLocationInput", "projectCapacityMwInput", "projectStageInput", "projectVersionInput"].forEach((id) => {
        const input = document.getElementById(id);
        if (!input) return;
        input.addEventListener("input", () => {
            updateProjectInfoStatus();
            renderProjectInfoReportPanel();
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
    renderProjectInfoReportPanel();
    renderSolarGainReportPanel();
    renderWeatherReportPanel();

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
            ["Peak Facility Hour", peak.peak_hour_index],
            ["Max PUE Hour", peak.peak_PUE_hour_index],
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
    renderProjectInfoReportPanel();
    renderSolarGainReportPanel();
    renderWeatherReportPanel();

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
        if (!standardSolverInput && preferStandardFiles) {
            standardSolverInput = buildSolverInputFromStandardFiles(standardDataFiles);
            syncStandardChillerSurfaceToCurveLib(standardDataFiles.chiller);
            elIn.value = pretty(standardSolverInput);
            previewInputCurves(standardDataFiles);
            refreshStandardInputStatus();
        }
        const rawInput = standardSolverInput || JSON.parse(elIn.value);
        const curveLib = window.curveLib || {
            curves_1d: {},
            cop_surfaces: {}
        };

        const job = prepareSolverJob(rawInput, curveLib);

        if (job.kind === "invalid" || job.kind === "invalid_project") {
            const d = job.diagnostics || {};
            lastReportContext = null;
            if (btnExportHtmlReport) btnExportHtmlReport.disabled = true;
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
            lastReportContext = { input: job.input, output: job.output, job, generatedAt: new Date().toISOString() };
            if (btnExportHtmlReport) btnExportHtmlReport.disabled = false;
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
            lastReportContext = { input: job.input, output: outObj, job, generatedAt: new Date().toISOString() };
            if (btnExportHtmlReport) btnExportHtmlReport.disabled = false;
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
            lastReportContext = { input: job.input, output: outObj, job, generatedAt: new Date().toISOString() };
            if (btnExportHtmlReport) btnExportHtmlReport.disabled = false;
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
        lastReportContext = null;
        if (btnExportHtmlReport) btnExportHtmlReport.disabled = true;
        setSolverDataStatus(`运行失败：${String(e.message || e)}`, "error");
        log("❌ Run 失败：\n" + String(e));
    }
}

btnRun.addEventListener("click", run);
if (btnExportHtmlReport) btnExportHtmlReport.addEventListener("click", exportHtmlReport);
elIn.addEventListener("input", () => {
    preferStandardFiles = false;
    if (standardSolverInput) {
        standardSolverInput = null;
        refreshStandardInputStatus();
        setSolverDataStatus("已切换为下方手写 JSON 输入。", "info");
    }
});
init();
