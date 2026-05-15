// editor.js
let copChart = null;
let curvesFileHandle = null;

// curveLib 会由 ui.js 在 init 时放到 window.curveLib
function getLib() {
    if (!window.curveLib) window.curveLib = { curves_1d: {}, cop_surfaces: {} };
    if (!window.curveLib.curves_1d) window.curveLib.curves_1d = {};
    if (!window.curveLib.cop_surfaces) window.curveLib.cop_surfaces = {};
    if (!window.curveLib.curves) window.curveLib.curves = {};
    return window.curveLib;
}

function parsePoints(text) {
    const lines = (text || "").split(/\r?\n/).map(s => s.trim()).filter(Boolean);
    const pts = [];
    for (const ln of lines) {
        const m = ln.split(",").map(s => s.trim());
        if (m.length < 2) continue;
        const x = Number(m[0]), y = Number(m[1]);
        if (Number.isFinite(x) && Number.isFinite(y)) pts.push([x, y]);
    }
    pts.sort((a, b) => a[0] - b[0]);
    // 去重 x
    const out = [];
    for (const [x, y] of pts) {
        if (out.length && Math.abs(out[out.length - 1][0] - x) < 1e-12) out[out.length - 1] = [x, y];
        else out.push([x, y]);
    }
    return out;
}

function ensureLinearScales(pointsXY) {
    const xs = pointsXY.map(p => p.x);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    return { minX, maxX };
}

function buildChart(canvasId, rawPts, smoothPts, title, xLabel, yLabel) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    const rawXY = rawPts.map(p => ({ x: p[0], y: p[1] }));
    const smoothXY = smoothPts.map(p => ({ x: p[0], y: p[1] }));
    const { minX, maxX } = ensureLinearScales(smoothXY.length ? smoothXY : rawXY);

    const config = {
        type: "scatter",
        data: {
            datasets: [
                {
                    label: "Smooth",
                    data: smoothXY,
                    showLine: true,
                    pointRadius: 0,
                    borderWidth: 2,
                    parsing: false
                },
                {
                    label: "Raw Points",
                    data: rawXY,
                    showLine: false,
                    pointRadius: 5,
                    parsing: false,
                    dragData: false,
                    dragX: false,
                    dragY: false
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: true },
                title: { display: true, text: title },
                dragData: {
                    round: 4,
                    onDragEnd: () => {
                        // 拖完点后：同步回 textarea 并自动预览（更像工程软件）
                        if (canvasId === "upsChart") syncUpsFromChart();
                        if (canvasId === "copChart") syncCopFromChart();
                    }
                }
            },
            scales: {
                x: {
                    type: "linear",
                    min: minX,
                    max: maxX,
                    ticks: { autoSkip: false, maxTicksLimit: 6, precision: 2 },
                    title: { display: true, text: xLabel }
                },
                y: {
                    type: "linear",
                    ticks: { maxTicksLimit: 6, precision: 2 },
                    title: { display: true, text: yLabel }
                }
            }
        }
    };

    if (copChart) copChart.destroy();
    copChart = new Chart(ctx, config);
}

async function smooth1D(points, method) {
    // 用 pyodide 里的 eval_curve_1d（solver.py 已提供）
    if (!window.pyodideReady || !window.pyodide) throw new Error("Pyodide 未就绪");
    if (points.length < 2) return [];
    const xMin = points[0][0], xMax = points[points.length - 1][0];
    const xs = [];
    const N = 60;
    for (let i = 0; i < N; i++) xs.push(xMin + (xMax - xMin) * i / (N - 1));

    window.pyodide.globals.set("pts_json", JSON.stringify(points));
    window.pyodide.globals.set("xs_json", JSON.stringify(xs));
    window.pyodide.globals.set("mth", method);

    const res = window.pyodide.runPython(`
import json
pts = json.loads(pts_json)
xs = json.loads(xs_json)
m = mth
out = []
for x in xs:
    y = eval_curve_1d(pts, x, m)
    out.append([x, float(y)])
out
  `);
    return res;
}

// ---------- UPS ----------
async function upsPreview() {
    const id = document.getElementById("upsCurveId").value.trim();
    const method = document.getElementById("upsMethod").value.trim();
    const pts = parsePoints(document.getElementById("upsPoints").value);
    const msg = document.getElementById("upsMsg");

    if (!id) return msg.textContent = "Curve ID 不能为空";
    if (pts.length < 2) return msg.textContent = "至少需要 2 个点";

    const smooth = await smooth1D(pts, method);
    buildChart("upsChart", pts, smooth, `UPS curve (${method})`, "load_ratio", "efficiency");
    msg.textContent = `预览完成：method=${method}，点数=${pts.length}`;
    renderCopSurfacePreview(document.getElementById("copSurfId").value.trim());

}

function syncUpsFromChart() {
    if (!upsChart) return;
    const raw = upsChart.data.datasets[1].data
        .map(p => [Number(p.x), Number(p.y)])
        .sort((a, b) => a[0] - b[0]);
    document.getElementById("upsPoints").value = raw.map(p => `${p[0]},${p[1]}`).join("\n");
    // 自动重算 smooth
    upsPreview();
}

function upsSaveToLib() {
    const lib = getLib();
    const id = document.getElementById("upsCurveId").value.trim();
    const method = document.getElementById("upsMethod").value.trim();
    const pts = parsePoints(document.getElementById("upsPoints").value);
    const msg = document.getElementById("upsMsg");

    if (!id) return msg.textContent = "Curve ID 不能为空";
    if (pts.length < 2) return msg.textContent = "至少需要 2 个点";

    lib.curves_1d[id] = {
        x_name: "load_ratio",
        y_name: "efficiency",
        method,
        points: pts
    };
    msg.textContent = `✅ 已保存到曲线库：curves_1d.${id}`;
}

// ---------- COP 2D ----------
async function copPreview() {
    const method = document.getElementById("copMethod").value.trim();
    const pts = parsePoints(document.getElementById("copPoints").value);
    const msg = document.getElementById("copMsg");
    if (pts.length < 2) return msg.textContent = "至少需要 2 个点";
    const smooth = await smooth1D(pts, method);
    buildChart("copChart", pts, smooth, `COP slice (${method})`, "PLR", "COP");
    msg.textContent = `预览完成：method=${method}，点数=${pts.length}`;
}

function syncCopFromChart() {
    if (!copChart) return;
    const raw = copChart.data.datasets[1].data
        .map(p => [Number(p.x), Number(p.y)])
        .sort((a, b) => a[0] - b[0]);
    document.getElementById("copPoints").value = raw.map(p => `${p[0]},${p[1]}`).join("\n");
    copPreview();
}

function refreshSliceList() {
    const lib = getLib();
    const sid = getSelectedCopSurfaceId();
    const el = document.getElementById("copSlices");
    if (!el) return;
    const surf = lib.cop_surfaces[sid];
    if (!surf || !surf.oat_slices || surf.oat_slices.length === 0) {
        el.textContent = "当前切片列表：空";
        return;
    }
    const oats = surf.oat_slices.map(s => s.oat_c).sort((a, b) => a - b);
    el.textContent = "当前切片列表（OAT）： " + oats.join("°C, ") + "°C";
}

function getSelectedCopSurfaceId() {
    const select = document.getElementById("copSurfaceSelect");
    if (select && select.value) return select.value;
    const legacy = document.getElementById("copSurfId");
    if (legacy && legacy.value) return legacy.value.trim();
    const lib = getLib();
    return Object.keys(lib.cop_surfaces || {})[0] || "";
}

function populateCopSurfaceSelect() {
    const select = document.getElementById("copSurfaceSelect");
    if (!select) return;
    const previous = window.preferredCopSurfaceId || select.value;
    const lib = getLib();
    const ids = Object.keys(lib.cop_surfaces || {});
    select.innerHTML = "";
    if (ids.length === 0) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "未找到 cop_surfaces 曲面";
        select.appendChild(opt);
        return;
    }
    ids.forEach((id) => {
        const opt = document.createElement("option");
        opt.value = id;
        opt.textContent = id;
        select.appendChild(opt);
    });
    if (ids.includes(previous)) select.value = previous;
    window.preferredCopSurfaceId = "";
}

async function renderSelectedCopSurface() {
    populateCopSurfaceSelect();
    const sid = getSelectedCopSurfaceId();
    const msg = document.getElementById("copMsg");
    if (!sid) {
        clearCopSurfaceCanvas("曲线库中没有可展示的 COP 曲面");
        if (msg) msg.textContent = "请通过 curves.json 或标准化冷水机曲线加载 COP 曲面。";
        return;
    }
    renderCopSurfacePreview(sid);
    refreshSliceList();
    await renderCopSlicePreviewFromSurface(sid);
    if (msg) msg.textContent = `当前展示曲面：${sid}`;
}

async function renderCopSlicePreviewFromSurface(surfaceId) {
    const lib = getLib();
    const surf = lib.cop_surfaces?.[surfaceId];
    if (!surf || !Array.isArray(surf.oat_slices) || surf.oat_slices.length === 0) return;
    const slices = surf.oat_slices.slice().sort((a, b) => a.oat_c - b.oat_c);
    const mid = slices[Math.floor(slices.length / 2)];
    const pts = (mid.points || []).slice().sort((a, b) => a[0] - b[0]);
    if (pts.length < 2) return;
    const smooth = await smooth1D(pts, mid.method || "linear");
    buildChart("copChart", pts, smooth, `COP slice @ ${mid.oat_c}°C`, "PLR", "COP");
}

function copAddOrReplaceSlice() {
    const lib = getLib();
    const sid = document.getElementById("copSurfId").value.trim();
    const oat = Number(document.getElementById("copOat").value);
    const method = document.getElementById("copMethod").value.trim();
    const pts = parsePoints(document.getElementById("copPoints").value);
    const msg = document.getElementById("copMsg");

    if (!sid) return msg.textContent = "Surface ID 不能为空";
    if (!Number.isFinite(oat)) return msg.textContent = "OAT 必须是数字";
    if (pts.length < 2) return msg.textContent = "至少需要 2 个点";

    if (!lib.cop_surfaces[sid]) {
        lib.cop_surfaces[sid] = { interpolation_oat: "linear", oat_slices: [] };
    }

    const surf = lib.cop_surfaces[sid];
    surf.interpolation_oat = "linear";
    surf.oat_slices = surf.oat_slices || [];

    // 覆盖同 oat
    const idx = surf.oat_slices.findIndex(s => Number(s.oat_c) === oat);
    const slice = { oat_c: oat, method, points: pts };

    if (idx >= 0) surf.oat_slices[idx] = slice;
    else surf.oat_slices.push(slice);

    msg.textContent = `✅ 已写入曲线库：cop_surfaces.${sid} @ OAT=${oat}`;
    refreshSliceList();
    renderCopSurfacePreview(sid);

}

function copClearSurface() {
    const lib = getLib();
    const sid = document.getElementById("copSurfId").value.trim();
    if (sid && lib.cop_surfaces[sid]) delete lib.cop_surfaces[sid];
    document.getElementById("copMsg").textContent = `已清空曲面：${sid}`;
    refreshSliceList();
    clearCopSurfaceCanvas(`曲面已清空：${sid}`);

}

// ---------- curves.json 文件读写 ----------
async function pickCurvesFile() {
    const el = document.getElementById("curvesStatus");
    if (!window.showOpenFilePicker) {
        el.textContent = "浏览器不支持直接写回文件（将使用导出下载）";
        return;
    }
    const [handle] = await showOpenFilePicker({
        types: [{ description: "JSON", accept: { "application/json": [".json"] } }],
        multiple: false
    });
    curvesFileHandle = handle;
    const file = await handle.getFile();
    const text = await file.text();
    window.curveLib = JSON.parse(text);
    el.textContent = `已打开：${file.name}（可写回）`;
    refreshSliceList();
}

async function saveCurvesFile() {
    const el = document.getElementById("curvesStatus");
    const lib = getLib();
    const text = JSON.stringify(lib, null, 2);

    if (curvesFileHandle && curvesFileHandle.createWritable) {
        const w = await curvesFileHandle.createWritable();
        await w.write(text);
        await w.close();
        el.textContent = `✅ 已保存回：${curvesFileHandle.name || "curves.json"}`;
    } else {
        el.textContent = "未授权写回：请用“导出 curves.json（下载）”覆盖文件";
    }
}

function exportCurvesDownload() {
    const lib = getLib();
    const text = JSON.stringify(lib, null, 2);
    const blob = new Blob([text], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "curves.json";
    a.click();
    URL.revokeObjectURL(url);
}

// ---------- init ----------
function bindEditorEvents() {
    const pick = document.getElementById("btnPickCurves");
    const save = document.getElementById("btnSaveCurves");
    const exp = document.getElementById("btnExportCurves");
    const select = document.getElementById("copSurfaceSelect");
    const reload = document.getElementById("btnCopReloadSurface");

    if (pick) pick.onclick = async () => {
        await pickCurvesFile();
        renderSelectedCopSurface();
    };
    if (save) save.onclick = saveCurvesFile;
    if (exp) exp.onclick = exportCurvesDownload;
    if (select) select.onchange = renderSelectedCopSurface;
    if (reload) reload.onclick = renderSelectedCopSurface;

    renderSelectedCopSurface();

}

// 给 ui.js 调用
window.initCurveEditors = bindEditorEvents;
window.renderSelectedCopSurface = renderSelectedCopSurface;

// ==============================
// COP 2D surface preview (heatmap)
// ==============================
function clamp(x, a, b) { return Math.max(a, Math.min(b, x)); }

// 简单蓝->红热力色
function heatColor(t) {
    t = clamp(t, 0, 1);
    const r = Math.round(255 * t);
    const g = Math.round(90 * (1 - Math.abs(t - 0.5) * 2));
    const b = Math.round(255 * (1 - t));
    return { r, g, b };
}

// fallback 线性插值
function interp1Linear(points, x) {
    const pts = points.slice().sort((a, b) => a[0] - b[0]);
    if (pts.length === 0) return null;
    if (x <= pts[0][0]) return pts[0][1];
    if (x >= pts[pts.length - 1][0]) return pts[pts.length - 1][1];
    for (let i = 1; i < pts.length; i++) {
        const [x2, y2] = pts[i];
        const [x1, y1] = pts[i - 1];
        if (x <= x2) {
            const t = (x - x1) / (x2 - x1);
            return y1 + (y2 - y1) * t;
        }
    }
    return pts[pts.length - 1][1];
}

// 统一插值入口：优先用 solver.py 的 eval_curve_1d（最一致）
// 如果 pyodide 不可用，退回线性
function interp1(points, x, method) {
    try {
        if (window.pyodideReady && window.pyodide) {
            window.pyodide.globals.set("pts_json", JSON.stringify(points));
            window.pyodide.globals.set("xq", x);
            window.pyodide.globals.set("mth", method || "linear");
            const y = window.pyodide.runPython(`
import json
pts = json.loads(pts_json)
float(eval_curve_1d(pts, xq, mth))
            `);
            return y;
        }
    } catch (e) {
        console.warn("interp1 fallback to linear:", e);
    }
    return interp1Linear(points, x);
}

// curves.json 结构：cop_surfaces[ID] = {interpolation_oat, oat_slices:[{oat_c, method, points}]}
function evalCopSurface(surfaceId, plr, oat) {
    const lib = getLib();
    const surf = lib.cop_surfaces?.[surfaceId];
    if (!surf) return null;

    const slices = (surf.oat_slices || []).slice().sort((a, b) => a.oat_c - b.oat_c);
    if (slices.length === 0) return null;

    // 找包围切片
    let s1 = slices[0], s2 = slices[slices.length - 1];
    for (let i = 0; i < slices.length; i++) {
        if (oat <= slices[i].oat_c) {
            s2 = slices[i];
            s1 = slices[Math.max(0, i - 1)];
            break;
        }
    }

    const c1 = interp1(s1.points || [], plr, s1.method || "linear");
    if (s1.oat_c === s2.oat_c) return c1;

    const c2 = interp1(s2.points || [], plr, s2.method || "linear");
    if (c1 == null) return null;
    if (c2 == null) return c1;

    // OAT 插值（当前只做 linear）
    const t = (oat - s1.oat_c) / (s2.oat_c - s1.oat_c);
    return c1 + (c2 - c1) * t;
}

function clearCopSurfaceCanvas(msg = "") {
    const canvas = document.getElementById("copSurfaceCanvas");
    const hint = document.getElementById("copSurfaceHint");
    if (canvas) {
        const ctx = canvas.getContext("2d");
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = "rgba(0,0,0,0.5)";
        ctx.font = "12px sans-serif";
        if (msg) ctx.fillText(msg, 10, 20);
    }
    if (hint) hint.textContent = msg;
}

function renderCopSurfacePreview(surfaceId) {
    const canvas = document.getElementById("copSurfaceCanvas");
    const hint = document.getElementById("copSurfaceHint");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const lib = getLib();
    const surf = lib.cop_surfaces?.[surfaceId];
    if (!surf || !surf.oat_slices || surf.oat_slices.length === 0) {
        clearCopSurfaceCanvas("曲面为空：请先添加 OAT 切片");
        return;
    }

    const slices = surf.oat_slices.slice().sort((a, b) => a.oat_c - b.oat_c);
    const oatMin = slices[0].oat_c;
    const oatMax = slices[slices.length - 1].oat_c;

    const nx = 80; // PLR grid
    const ny = 45; // OAT grid
    const plrMin = 0.0, plrMax = 1.0;

    // 扫描 min/max
    let vmin = Infinity, vmax = -Infinity;
    const grid = Array.from({ length: ny }, () => new Array(nx).fill(null));

    for (let j = 0; j < ny; j++) {
        const oat = oatMin + (oatMax - oatMin) * (j / (ny - 1));
        for (let i = 0; i < nx; i++) {
            const plr = plrMin + (plrMax - plrMin) * (i / (nx - 1));
            const v = evalCopSurface(surfaceId, plr, oat);
            grid[j][i] = v;
            if (v != null && isFinite(v)) {
                vmin = Math.min(vmin, v);
                vmax = Math.max(vmax, v);
            }
        }
    }

    if (!isFinite(vmin) || !isFinite(vmax) || vmin === vmax) {
        clearCopSurfaceCanvas("曲面数据不足/插值失败：检查切片点");
        return;
    }

    // 画热力图：上方=高 OAT
    const w = canvas.width, h = canvas.height;
    const img = ctx.createImageData(w, h);

    for (let y = 0; y < h; y++) {
        const py = y / (h - 1);
        const jj = Math.round((1 - py) * (ny - 1)); // invert
        for (let x = 0; x < w; x++) {
            const px = x / (w - 1);
            const ii = Math.round(px * (nx - 1));
            const v = grid[jj][ii];
            const t = (v - vmin) / (vmax - vmin);
            const c = heatColor(t);
            const idx = (y * w + x) * 4;
            img.data[idx + 0] = c.r;
            img.data[idx + 1] = c.g;
            img.data[idx + 2] = c.b;
            img.data[idx + 3] = 255;
        }
    }
    ctx.putImageData(img, 0, 0);

    // 标签
    ctx.fillStyle = "rgba(0,0,0,0.75)";
    ctx.font = "12px sans-serif";
    ctx.fillText(`PLR ${plrMin.toFixed(1)} → ${plrMax.toFixed(1)}`, 12, h - 10);
    ctx.save();
    ctx.translate(12, 18);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(`OAT ${oatMin.toFixed(0)} → ${oatMax.toFixed(0)} °C`, 0, 0);
    ctx.restore();

    const oatList = slices.map(s => s.oat_c).sort((a, b) => a - b).join(", ");
    if (hint) hint.textContent = `COP range: ${vmin.toFixed(3)} ~ ${vmax.toFixed(3)} | slices(OAT): ${oatList} °C`;

    // 悬停显示
    canvas.onmousemove = (ev) => {
        const r = canvas.getBoundingClientRect();
        const px = clamp((ev.clientX - r.left) / r.width, 0, 1);
        const py = clamp((ev.clientY - r.top) / r.height, 0, 1);
        const plr = plrMin + (plrMax - plrMin) * px;
        const oat = oatMax - (oatMax - oatMin) * py;
        const cop = evalCopSurface(surfaceId, plr, oat);
        if (hint) hint.textContent =
            `PLR=${plr.toFixed(3)}, OAT=${oat.toFixed(2)}°C → COP=${(cop == null ? "NA" : cop.toFixed(4))} | range ${vmin.toFixed(3)}~${vmax.toFixed(3)} | slices: ${oatList}°C`;
    };
}
function clearCopSurfaceCanvas(msg = "") {
    const el = document.getElementById("copSurface3d");
    const hint = document.getElementById("copSurfaceHint");
    if (el) el.innerHTML = "";
    if (hint) hint.textContent = msg;
}

function renderCopSurfacePreview(surfaceId) {
    const lib = getLib();
    const surf = lib.cop_surfaces?.[surfaceId];
    const hint = document.getElementById("copSurfaceHint");
    const el = document.getElementById("copSurface3d");
    if (!el) return;

    // Plotly 未加载时兜底
    if (typeof Plotly === "undefined") {
        if (hint) hint.textContent = "Plotly 未加载：请检查 index.html 是否已引入 plotly.min.js";
        return;
    }

    if (!surf || !surf.oat_slices || surf.oat_slices.length === 0) {
        clearCopSurfaceCanvas("曲面为空：请先添加 OAT 切片");
        return;
    }

    const slices = surf.oat_slices.slice().sort((a, b) => a.oat_c - b.oat_c);
    const oatMin = slices[0].oat_c;
    const oatMax = slices[slices.length - 1].oat_c;

    // 网格（越大越精细但更慢）
    const nx = 55; // PLR
    const ny = 35; // OAT
    const plrMin = 0.0, plrMax = 1.0;

    const xs = Array.from({ length: nx }, (_, i) => plrMin + (plrMax - plrMin) * i / (nx - 1));
    const ys = Array.from({ length: ny }, (_, j) => oatMin + (oatMax - oatMin) * j / (ny - 1));

    // z[ny][nx]
    const z = ys.map(oat => xs.map(plr => evalCopSurface(surfaceId, plr, oat)));

    // min/max 提示用
    let vmin = Infinity, vmax = -Infinity;
    for (const row of z) {
        for (const v of row) {
            if (v != null && isFinite(v)) { vmin = Math.min(vmin, v); vmax = Math.max(vmax, v); }
        }
    }

    const oatList = slices.map(s => s.oat_c).sort((a, b) => a - b).join(", ");
    if (hint) hint.textContent = `slices(OAT): ${oatList} °C | COP range: ${vmin.toFixed(3)} ~ ${vmax.toFixed(3)}`;

    Plotly.react(
        el,
        [{
            type: "surface",
            x: xs,
            y: ys,
            z: z,
            // ✅ 让“具象化”的关键：等值线投影（像工程软件）
            contours: {
                z: {
                    show: true,
                    usecolormap: true,
                    highlightcolor: "#111827",
                    project: { z: true }
                }
            }
        }],
        {
            margin: { l: 0, r: 0, b: 0, t: 0 },
            scene: {
                xaxis: { title: "PLR", range: [plrMin, plrMax] },
                yaxis: { title: "OAT (°C)", range: [oatMin, oatMax] },
                zaxis: { title: "COP" },
            }
        },
        { displayModeBar: false, responsive: true }
    );
}
