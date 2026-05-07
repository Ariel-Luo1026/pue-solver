let pyodide = null;

const elStatus = document.getElementById("status");
const elLog = document.getElementById("log");
const elIn = document.getElementById("jsonInput");
const elOut = document.getElementById("jsonOutput");
const btnRun = document.getElementById("btnRun");

function log(msg) { elLog.textContent = msg; }
function pretty(obj) { return JSON.stringify(obj, null, 2); }

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
        const inputObj = JSON.parse(elIn.value);

        inputObj.curve_library = window.curveLib || {
            curves_1d: {},
            cop_surfaces: {}
        };

        pyodide.globals.set("dc_json_str", JSON.stringify(inputObj));

        const outStr = pyodide.runPython(`
import json
dc = json.loads(dc_json_str)
out = compute_pue_v04(dc)
json.dumps(out, indent=2)
        `);

        elOut.value = outStr;

        const outObj = JSON.parse(outStr);
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
            "✅ v0.4.1 运行成功（heat sources + curve driven）\n" +
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

    } catch (e) {
        console.error(e);
        log("❌ Run 失败：\n" + String(e));
    }
}

btnRun.addEventListener("click", run);
init();