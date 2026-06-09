# solver.py
# PUE Solver v0.4-B (Math formalization)
# - PUE = P_facility / P_IT
# - pPUE_i = P_i / P_IT ; PUE = 1 + sum(pPUE_i) when i excludes IT
# - ERE = (P_facility - P_reuse_exported) / P_IT (if heat_recovery.enabled)
# - WUE/CUE interface: WU  E = water(L)/E_IT(kWh), CUE = CO2e(kg)/E_IT(kWh) for energy mode (future)
# Pyodide-friendly: no external deps.

from math import isfinite
from copy import deepcopy

# -------------------------
# helpers
# -------------------------
def _get(d, path, default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

def _num(x, default=0.0):
    try:
        if x is None:
            return default
        v = float(x)
        if not isfinite(v):
            return default
        return v
    except Exception:
        return default

def _sum_power(items, key="power_kw"):
    s = 0.0
    if not isinstance(items, list):
        return 0.0
    for it in items:
        if isinstance(it, dict):
            s += _num(it.get(key), 0.0)
    return s

def _clamp(x, lo, hi):
    if x < lo: return lo
    if x > hi: return hi
    return x

# -------------------------
# 1D interpolation (linear / pchip)
# points: [[x1,y1],[x2,y2],...], must be sorted by x asc, unique x
# -------------------------
def _prep_points(points):
    if not isinstance(points, list):
        return []
    out = []
    for p in points:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            x = _num(p[0], None)
            y = _num(p[1], None)
            if x is None or y is None:
                continue
            out.append([x, y])
    out.sort(key=lambda t: t[0])
    # unique x (keep last)
    uniq = []
    for x, y in out:
        if uniq and abs(uniq[-1][0] - x) < 1e-12:
            uniq[-1] = [x, y]
        else:
            uniq.append([x, y])
    return uniq

def _linear_interp(points, x):
    n = len(points)
    if n == 0:
        return 0.0
    if n == 1:
        return float(points[0][1])
    if x <= points[0][0]:
        return float(points[0][1])
    if x >= points[-1][0]:
        return float(points[-1][1])
    # find segment
    for i in range(n - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        if x0 <= x <= x1:
            if abs(x1 - x0) < 1e-12:
                return float(y0)
            t = (x - x0) / (x1 - x0)
            return float(y0 + t * (y1 - y0))
    return float(points[-1][1])

def _pchip_slopes(points):
    # Fritsch–Carlson monotone cubic interpolation slopes
    n = len(points)
    if n < 2:
        return [0.0] * n
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    h = [xs[i+1] - xs[i] for i in range(n-1)]
    d = [(ys[i+1] - ys[i]) / h[i] if abs(h[i]) > 1e-12 else 0.0 for i in range(n-1)]
    m = [0.0] * n

    if n == 2:
        m[0] = d[0]
        m[1] = d[0]
        return m

    # endpoint slopes
    m[0] = ((2*h[0] + h[1]) * d[0] - h[0] * d[1]) / (h[0] + h[1]) if abs(h[0]+h[1])>1e-12 else 0.0
    if m[0] * d[0] <= 0:
        m[0] = 0.0
    elif abs(d[0]) > 1e-12 and abs(m[0]) > 3*abs(d[0]):
        m[0] = 3*d[0]

    m[-1] = ((2*h[-1] + h[-2]) * d[-1] - h[-1] * d[-2]) / (h[-1] + h[-2]) if abs(h[-1]+h[-2])>1e-12 else 0.0
    if m[-1] * d[-1] <= 0:
        m[-1] = 0.0
    elif abs(d[-1]) > 1e-12 and abs(m[-1]) > 3*abs(d[-1]):
        m[-1] = 3*d[-1]

    # interior slopes
    for i in range(1, n-1):
        if d[i-1] * d[i] <= 0:
            m[i] = 0.0
        else:
            w1 = 2*h[i] + h[i-1]
            w2 = h[i] + 2*h[i-1]
            m[i] = (w1 + w2) / (w1/d[i-1] + w2/d[i]) if abs(w1/d[i-1] + w2/d[i]) > 1e-12 else 0.0
    return m

def _pchip_eval(points, x):
    n = len(points)
    if n == 0:
        return 0.0
    if n == 1:
        return float(points[0][1])

    if x <= points[0][0]:
        return float(points[0][1])
    if x >= points[-1][0]:
        return float(points[-1][1])

    m = _pchip_slopes(points)

    # locate interval
    for i in range(n - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        if x0 <= x <= x1:
            h = x1 - x0
            if abs(h) < 1e-12:
                return float(y0)
            t = (x - x0) / h
            t2 = t * t
            t3 = t2 * t
            # Hermite basis
            h00 = 2*t3 - 3*t2 + 1
            h10 = t3 - 2*t2 + t
            h01 = -2*t3 + 3*t2
            h11 = t3 - t2
            return float(h00*y0 + h10*h*m[i] + h01*y1 + h11*h*m[i+1])
    return float(points[-1][1])

def eval_curve_1d(points, x, method="pchip"):
    """
    points: [[x,y],...]
    method: 'linear' or 'pchip'
    """
    pts = _prep_points(points)
    if len(pts) == 0:
        return 0.0
    if method == "linear":
        return _linear_interp(pts, float(x))
    return _pchip_eval(pts, float(x))

# -------------------------
# 2D COP surface: slices by OAT
# Surface format:
# {
#   "interpolation_oat": "linear",
#   "oat_slices": [
#       {"oat_c": 25, "method":"pchip", "points":[[plr,cop],...]},
#       ...
#   ]
# }
# Compute COP(plr, oat): 1D interp on each slice, then linear interp across OAT
# -------------------------
def eval_cop_surface(surface, plr, oat_c):
    if not isinstance(surface, dict):
        return 0.0
    slices = surface.get("oat_slices", [])
    if not isinstance(slices, list) or len(slices) == 0:
        return 0.0

    oat = float(oat_c)
    plr = float(plr)

    # prepare slice list sorted by oat
    ss = []
    for s in slices:
        if not isinstance(s, dict):
            continue
        o = _num(s.get("oat_c"), None)
        pts = s.get("points")
        if o is None:
            continue
        method = s.get("method", "pchip")
        ss.append((o, method, pts))
    ss.sort(key=lambda t: t[0])
    if len(ss) == 0:
        return 0.0

    # clamp outside range
    if oat <= ss[0][0]:
        return float(eval_curve_1d(ss[0][2], plr, ss[0][1]))
    if oat >= ss[-1][0]:
        return float(eval_curve_1d(ss[-1][2], plr, ss[-1][1]))

    # find bracket
    for i in range(len(ss) - 1):
        o0, m0, p0 = ss[i]
        o1, m1, p1 = ss[i+1]
        if o0 <= oat <= o1:
            cop0 = float(eval_curve_1d(p0, plr, m0))
            cop1 = float(eval_curve_1d(p1, plr, m1))
            if abs(o1 - o0) < 1e-12:
                return cop0
            t = (oat - o0) / (o1 - o0)
            return float(cop0 + t*(cop1 - cop0))
    return float(eval_curve_1d(ss[-1][2], plr, ss[-1][1]))

# -------------------------
# component models (v0.4-B)
# -------------------------
def _compute_it_power(input_obj):
    # priority: measured total_it_power_kw -> sum modules -> 0
    p_it_meas = _num(_get(input_obj, ["power", "total_it_power_kw"], None), None)
    if p_it_meas is not None and p_it_meas > 0:
        return p_it_meas, "power.total_it_power_kw"
    modules = input_obj.get("modules", [])
    p_it_mod = 0.0
    if isinstance(modules, list):
        for m in modules:
            if isinstance(m, dict):
                p_it_mod += _num(m.get("it_load_kw"), 0.0)
    if p_it_mod > 0:
        return p_it_mod, "sum(modules[].it_load_kw)"
    return 0.0, "default(0)"

def _compute_ups_loss(input_obj, curve_lib, p_it_kw):
    # UPS array: each has input_power_kw/output_power_kw OR efficiency curve (load_ratio->eff)
    ups_list = input_obj.get("ups", [])
    if not isinstance(ups_list, list) or len(ups_list) == 0:
        return 0.0, []

    out_rows = []
    total_loss = 0.0

    curves_1d = (curve_lib or {}).get("curves_1d", {}) if isinstance(curve_lib, dict) else {}
    for ups in ups_list:
        if not isinstance(ups, dict):
            continue
        ups_id = ups.get("ups_id", "UPS")
        pin = _num(ups.get("input_power_kw"), None)
        pout = _num(ups.get("output_power_kw"), None)

        # If both provided, trust them
        if pin is not None and pout is not None and pin >= 0 and pout >= 0:
            loss = max(0.0, pin - pout)
            total_loss += loss
            out_rows.append({"ups_id": ups_id, "input_kw": pin, "output_kw": pout, "loss_kw": loss, "method": "measured"})
            continue

        # else estimate from IT load share + curve
        # Use output as share of IT (simple): if ups.output_power_kw missing, assume supports whole IT.
        est_pout = pout if (pout is not None and pout > 0) else p_it_kw
        # load percent if present
        load_ratio = _num(ups.get("load_percent"), None)
        if load_ratio is None:
            # if load_percent not present, approximate by output/rated not available => assume 0.5
            load_ratio = 50.0
        # normalize to 0-1
        lr = load_ratio/100.0 if load_ratio > 1.0 else load_ratio
        lr = _clamp(lr, 0.05, 1.0)

        # curve ref
        curve_ref = ups.get("eff_curve_ref") or ups.get("efficiency_curve_ref") or ups.get("curve_id")
        eff = None
        if curve_ref and isinstance(curve_ref, str) and curve_ref in curves_1d:
            c = curves_1d[curve_ref]
            pts = c.get("points", [])
            method = c.get("method", "pchip")
            eff = float(eval_curve_1d(pts, lr, method))
        else:
            eff_pct = _num(ups.get("efficiency_percent"), None)
            if eff_pct is not None and eff_pct > 1.0:
                eff = eff_pct/100.0
            elif eff_pct is not None:
                eff = eff_pct

        if eff is None:
            eff = 0.96  # conservative default

        eff = _clamp(eff, 0.5, 0.999)
        est_pin = est_pout / eff
        loss = max(0.0, est_pin - est_pout)
        total_loss += loss
        out_rows.append({"ups_id": ups_id, "input_kw": est_pin, "output_kw": est_pout, "loss_kw": loss, "method": f"curve({curve_ref})" if curve_ref else "default_eff"})
    return total_loss, out_rows

def _compute_transformer_loss(input_obj, curve_lib, p_it_kw=0.0, power_output_kw=0.0):
    # direct loss provided or estimate from transformer efficiency curves
    tr = input_obj.get("transformers", [])
    if not isinstance(tr, list):
        return 0.0, []
    rows = []
    total = 0.0
    curves_1d = (curve_lib or {}).get("curves_1d", {}) if isinstance(curve_lib, dict) else {}
    raw_curves = (curve_lib or {}).get("raw_curves", {}) if isinstance(curve_lib, dict) else {}
    for t in tr:
        if not isinstance(t, dict):
            continue
        loss = _num(t.get("total_loss_kw"), None)
        if loss is None:
            eff = None
            curve_ref = t.get("efficiency_curve_ref") or t.get("curve_ref") or t.get("transformer_curve_ref")
            if curve_ref and isinstance(curve_ref, str):
                if curve_ref in curves_1d:
                    pts = curves_1d[curve_ref].get("points", [])
                    method = curves_1d[curve_ref].get("method", "linear")
                    load_ratio = _num(t.get("load_ratio"), None)
                    if load_ratio is None:
                        load_ratio = _num(t.get("rated_load_ratio"), None)
                    if load_ratio is None:
                        load_ratio = 1.0
                    eff = _num(eval_curve_1d(pts, load_ratio, method), None)
                elif curve_ref in raw_curves:
                    load_ratio = _num(t.get("load_ratio"), None)
                    if load_ratio is None:
                        load_ratio = 1.0
                    eff = _num(_curve_value({"raw_curves": raw_curves}, curve_ref, load_ratio, None), None)
            if eff is None:
                eff_pct = _num(t.get("efficiency_percent"), None)
                if eff_pct is not None and eff_pct > 1.0:
                    eff = eff_pct / 100.0
                else:
                    eff = eff_pct
            if eff is None or eff <= 0:
                eff = None
            if eff is not None and power_output_kw is not None and power_output_kw > 0:
                loss = max(0.0, float(power_output_kw) * (1.0 / float(eff) - 1.0))
            else:
                loss = 0.0
        else:
            loss = float(loss)
        total += loss
        rows.append({"transformer_id": t.get("transformer_id", "TR"), "loss_kw": loss})
    return total, rows


def _compute_cooling_heat_sources(input_obj, p_it_kw, pumps_kw=0.0, airflow_kw=0.0, aux_detail=None):
    """
    Compute cooling thermal load from explicit heat-source breakdown.

    Design intent:
    - IT heat is split into liquid-cooling IT load and air-cooling IT load.
    - Pumps / airflow / lighting can be explicitly provided, or left as null/missing
      to use the model-computed power as heat.
    - This avoids silently defining cooling_load_kw = IT only.
    """
    cooling = input_obj.get("cooling", {}) if isinstance(input_obj.get("cooling", {}), dict) else {}
    split = cooling.get("it_heat_split", {}) if isinstance(cooling.get("it_heat_split", {}), dict) else {}
    hs = cooling.get("heat_sources", {}) if isinstance(cooling.get("heat_sources", {}), dict) else {}

    # ---- IT heat split ----
    liquid_it = _num(split.get("liquid_cooling_it_kw"), None)
    air_it = _num(split.get("air_cooling_it_kw"), None)

    # If neither is provided, use legacy fallback: all IT heat is air-side.
    # If only one is provided, infer the other from total IT.
    if liquid_it is None and air_it is None:
        liquid_it = 0.0
        air_it = float(p_it_kw)
        split_source = "default_all_it_to_air"
    elif liquid_it is None:
        liquid_it = max(0.0, float(p_it_kw) - float(air_it))
        split_source = "inferred_liquid_from_total_it"
    elif air_it is None:
        air_it = max(0.0, float(p_it_kw) - float(liquid_it))
        split_source = "inferred_air_from_total_it"
    else:
        split_source = "explicit"

    # ---- Non-IT thermal sources ----
    # If value is null/missing, use the corresponding modeled power as heat.
    pumps_in = hs.get("pumps_kw", None)
    pumps_heat = float(pumps_kw) if pumps_in is None else float(_num(pumps_in, 0.0))

    airflow_in = hs.get("airflow_kw", None)
    airflow_heat = float(airflow_kw) if airflow_in is None else float(_num(airflow_in, 0.0))

    lighting_in = hs.get("lighting_kw", None)
    if lighting_in is None:
        if isinstance(aux_detail, dict):
            lighting_heat = float(_num(aux_detail.get("lighting_power_kw"), 0.0))
        else:
            lighting_heat = 0.0
    else:
        lighting_heat = float(_num(lighting_in, 0.0))

    people_kw = float(_num(hs.get("people_kw"), 0.0))
    infiltration_kw = float(_num(hs.get("infiltration_kw"), 0.0))
    envelope_kw = float(_num(hs.get("envelope_kw"), 0.0))
    misc_kw = float(_num(hs.get("misc_kw"), 0.0))

    heat_sources = {
        "it_liquid_kw": float(liquid_it),
        "it_air_kw": float(air_it),
        "pumps_kw": float(pumps_heat),
        "airflow_kw": float(airflow_heat),
        "lighting_kw": float(lighting_heat),
        "people_kw": float(people_kw),
        "infiltration_kw": float(infiltration_kw),
        "envelope_kw": float(envelope_kw),
        "misc_kw": float(misc_kw)
    }

    cooling_load_kw = float(sum(heat_sources.values()))

    meta = {
        "it_split_source": split_source,
        "note": "cooling_load_kw is sum(cooling_heat_sources_kw)"
    }

    return cooling_load_kw, heat_sources, meta


def _compute_chiller_power(input_obj, curve_lib, p_it_kw):
    """
    Multi-chiller allocation model.

    Cooling load source:
    - input_obj["cooling"]["cooling_load_kw"] should be written by
      _compute_cooling_heat_sources() before calling this function.
    - If absent, fallback to p_it_kw only to keep the demo robust.

    Allocation:
    - default share_by = capacity
    - optional cooling.chiller_share_by = "weight"
    """
    chillers = input_obj.get("chillers", [])
    if not isinstance(chillers, list) or len(chillers) == 0:
        return 0.0, []

    cop_surfaces = (curve_lib or {}).get("cop_surfaces", {}) if isinstance(curve_lib, dict) else {}

    oat = _num(_get(input_obj, ["environmental_conditions", "outdoor_temp_c"], None), None)
    if oat is None:
        oat = _num(_get(input_obj, ["cooling", "oat_c"], None), None)
    if oat is None:
        oat = 25.0

    q_total = _num(_get(input_obj, ["cooling", "cooling_load_kw"], None), None)
    if q_total is None:
        q_total = _num(input_obj.get("cooling_load_kw"), None)
    if q_total is None:
        q_total = float(p_it_kw)

    share_by = _get(input_obj, ["cooling", "chiller_share_by"], None)
    if share_by is None:
        share_by = input_obj.get("chiller_share_by", "capacity")
    share_by = str(share_by).lower().strip()
    if share_by not in ("capacity", "weight"):
        share_by = "capacity"

    rows = []
    total_kw = 0.0
    measured_rows = []
    active = []  # (chiller_dict, capacity_kw, share_weight)

    for ch in chillers:
        if not isinstance(ch, dict):
            continue
        if ch.get("enabled", True) is False:
            continue

        cid = ch.get("chiller_id", "CH")

        # Measured chiller power is accepted as direct electric power.
        p_kw_meas = _num(ch.get("power_kw"), None)
        if p_kw_meas is not None and p_kw_meas >= 0:
            total_kw += float(p_kw_meas)
            measured_rows.append({
                "chiller_id": cid,
                "power_kw": float(p_kw_meas),
                "method": "measured"
            })
            continue

        cap = _num(ch.get("capacity_kw"), None)
        if cap is None:
            cap = _num(ch.get("rated_capacity_kw"), None)
        if cap is None or cap <= 0:
            rows.append({
                "chiller_id": cid,
                "power_kw": 0.0,
                "method": "skipped(no_capacity_no_power)"
            })
            continue

        w = _num(ch.get("share_weight"), None)
        if w is None or w <= 0:
            w = 1.0

        active.append((ch, float(cap), float(w)))

    rows.extend(measured_rows)

    if len(active) == 0:
        if q_total > 0:
            rows.append({
                "chiller_id": "SYS",
                "power_kw": 0.0,
                "method": "no_active_chillers_for_allocation"
            })
        return float(total_kw), rows

    if share_by == "weight":
        denom = sum(w for _, _, w in active)
    else:
        denom = sum(cap for _, cap, _ in active)

    if denom <= 0:
        rows.append({
            "chiller_id": "SYS",
            "power_kw": 0.0,
            "method": "invalid_allocation_denominator"
        })
        return float(total_kw), rows

    for ch, cap, w in active:
        cid = ch.get("chiller_id", "CH")

        if share_by == "weight":
            q_kw = float(q_total) * (w / denom)
        else:
            q_kw = float(q_total) * (cap / denom)

        plr = _num(ch.get("plr"), None)
        if plr is None:
            plr = q_kw / cap if cap > 0 else 1.0
        plr = _clamp(plr, 0.05, 1.0)

        cop = _num(ch.get("cop"), None)
        method = "cop_field"

        sref = ch.get("cop_curve_ref") or ch.get("cop_surface_ref") or ch.get("surface_id")
        if (cop is None or cop <= 0) and sref and isinstance(sref, str) and sref in cop_surfaces:
            try:
                cop = float(eval_cop_surface(cop_surfaces[sref], plr, oat))
                method = f"surface({sref})"
            except Exception:
                cop = None

        if cop is None or cop <= 0:
            cop = 5.5
            method = "default_cop"

        cop = _clamp(cop, 1.0, 20.0)

        p_kw = q_kw / cop
        total_kw += float(p_kw)

        rows.append({
            "chiller_id": cid,
            "power_kw": float(p_kw),
            "q_kw": float(q_kw),
            "q_kw_allocated": float(q_kw),
            "capacity_kw_used": float(cap),
            "share_by": share_by,
            "share_weight": float(w),
            "plr": float(plr),
            "oat_c": float(oat),
            "cop": float(cop),
            "method": method
        })

    return float(total_kw), rows


def _vfd_power(item):
    """
    Support:
    - explicit power_kw (highest priority)
    - vfd: rated_power_kw * speed_ratio^3
    - fallback: 0
    """
    if not isinstance(item, dict):
        return 0.0, "none"

    # 1) direct measured/model power
    p = _num(item.get("power_kw"), None)
    if p is not None and p >= 0:
        return p, "power_kw"

    # 2) VFD estimation
    mode = (item.get("control_mode") or item.get("mode") or "").lower()
    rated = _num(item.get("rated_power_kw"), None)
    sr = _num(item.get("speed_ratio"), None)
    if mode == "vfd" and rated is not None and sr is not None:
        sr = _clamp(sr, 0.0, 1.5)  # allow a bit >1 for edge cases
        return rated * (sr ** 3), "rated*speed^3"

    # 3) no data
    return 0.0, "default0"


def _compute_pumps_power(input_obj):
    pumps = input_obj.get("pumps", [])
    if not isinstance(pumps, list):
        return 0.0, []

    total = 0.0
    rows = []
    for p in pumps:
        pw, how = _vfd_power(p)
        total += pw
        if isinstance(p, dict):
            r = dict(p)
            r["_power_kw_used"] = pw
            r["_power_method"] = how
            rows.append(r)
    return total, rows


def _compute_airflow_power(input_obj):
    airflow = input_obj.get("airflow", [])
    if not isinstance(airflow, list):
        return 0.0, []

    total = 0.0
    rows = []
    for a in airflow:
        pw, how = _vfd_power(a)
        total += pw
        if isinstance(a, dict):
            r = dict(a)
            r["_power_kw_used"] = pw
            r["_power_method"] = how
            rows.append(r)
    return total, rows

def _compute_control_aux_power(input_obj):
    ctrl = input_obj.get("control", {})
    if not isinstance(ctrl, dict):
        return 0.0, {}
    keys = [
        "bms_power_kw", "dcim_power_kw", "lighting_power_kw",
        "security_power_kw", "office_hvac_kw", "other_aux_power_kw"
    ]
    s = 0.0
    for k in keys:
        s += _num(ctrl.get(k), 0.0)
    return s, ctrl

def _compute_other_fixed(input_obj):
    # Optional buckets you already have in schema
    hum = input_obj.get("humidification_dehumidification", {})
    fire = input_obj.get("fire_suppression", {})
    ev = input_obj.get("ev_chargers", {})
    s = 0.0
    if isinstance(hum, dict):
        s += _num(hum.get("humidifier_power_kw"), 0.0)
        s += _num(hum.get("dehumidification_power_kw"), 0.0)
    if isinstance(fire, dict):
        s += _num(fire.get("ventilation_power_kw"), 0.0)
        s += _num(fire.get("pump_test_power_kw"), 0.0)
    if isinstance(ev, dict):
        s += _num(ev.get("total_charging_power_kw"), 0.0)
    return s

def _compute_heat_reuse_credit(input_obj):
    hr = input_obj.get("heat_recovery", {})
    if not isinstance(hr, dict):
        return 0.0, {}
    enabled = bool(hr.get("enabled", False))
    exported = _num(hr.get("exported_heat_kw"), 0.0)
    recovered = _num(hr.get("recovered_heat_kw"), 0.0)
    credit = exported if enabled else 0.0
    return credit, {"enabled": enabled, "exported_heat_kw": exported, "recovered_heat_kw": recovered}


def _build_1d_curve_points(curve):
    pts = []
    data = curve.get("data", [])
    if not isinstance(data, list):
        return pts
    for row in data:
        if isinstance(row, dict):
            x = _num(row.get(curve.get("x_axis")), None)
            y = _num(row.get(curve.get("output")), None)
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            x = _num(row[0], None)
            y = _num(row[1], None)
        else:
            continue
        if x is None or y is None:
            continue
        pts.append([x, y])
    return pts


def _extract_2d_points(curve):
    points = []
    data = curve.get("data", [])
    if not isinstance(data, list):
        return points
    x_axis = curve.get("x_axis")
    y_axis = curve.get("y_axis")
    output = curve.get("output")
    if not x_axis or not y_axis or not output:
        return points
    for row in data:
        if isinstance(row, dict):
            x = _num(row.get(x_axis), None)
            y = _num(row.get(y_axis), None)
            z = _num(row.get(output), None)
        elif isinstance(row, (list, tuple)) and len(row) >= 3:
            x = _num(row[0], None)
            y = _num(row[1], None)
            z = _num(row[2], None)
        else:
            continue
        if x is None or y is None or z is None:
            continue
        points.append([x, y, z])
    return points


def _build_cop_surface_from_2d_curve(curve):
    points = _extract_2d_points(curve)
    if len(points) == 0:
        return None
    grouped = {}
    for x, y, z in points:
        grouped.setdefault(x, []).append([y, z])
    slices = []
    for x in sorted(grouped.keys()):
        pts = sorted(grouped[x], key=lambda item: item[0])
        slices.append({"oat_c": x, "method": "pchip", "points": pts})
    return {"interpolation_oat": "linear", "oat_slices": slices}


def _build_sparse_2d_points(curve):
    x_axis = curve.get("x_axis")
    y_axis = curve.get("y_axis")
    output = curve.get("output") or (curve.get("outputs", [None])[0] if isinstance(curve.get("outputs"), list) else None)
    if not x_axis or not y_axis or not output:
        return []
    points = []
    for row in curve.get("data", []) if isinstance(curve.get("data", []), list) else []:
        if not isinstance(row, dict):
            continue
        x = _num(row.get(x_axis), None)
        y = _num(row.get(y_axis), None)
        z = _num(row.get(output), None)
        if x is None or y is None or z is None:
            continue
        points.append([x, y, z])
    return points


def _eval_sparse_2d_points(curve, x, y):
    pts = _build_sparse_2d_points(curve)
    if len(pts) == 0 or x is None or y is None:
        return 0.0
    x = float(x)
    y = float(y)
    interp = str(curve.get("interpolation", "linear_scattered_or_nearest")).lower()
    if any(abs(px - x) < 1e-9 and abs(py - y) < 1e-9 for px, py, _ in pts):
        for px, py, pz in pts:
            if abs(px - x) < 1e-9 and abs(py - y) < 1e-9:
                return float(pz)
    if "nearest" in interp:
        best = min(pts, key=lambda item: (item[0] - x) ** 2 + (item[1] - y) ** 2)
        return float(best[2])
    weights = []
    total = 0.0
    for px, py, pz in pts:
        dist2 = (px - x) ** 2 + (py - y) ** 2
        w = 1.0 / (dist2 + 1e-6)
        weights.append((w, pz))
        total += w
    if total <= 0.0:
        return float(pts[0][2])
    return float(sum(w * pz for w, pz in weights) / total)


def _parse_equipment_curve(curve):
    if not isinstance(curve, dict):
        return None
    parsed = {
        "type": str(curve.get("type", "")).lower(),
        "x_axis": curve.get("x_axis"),
        "y_axis": curve.get("y_axis"),
        "interpolation": curve.get("interpolation", "linear"),
        "data": curve.get("data", [])
    }
    outputs = curve.get("outputs")
    if isinstance(outputs, list) and len(outputs) > 0:
        parsed["outputs"] = outputs
        parsed["output"] = curve.get("output") or outputs[0]
    else:
        parsed["output"] = curve.get("output")
    return parsed


def _normalize_equipment_curve_library(equipment_curves):
    normalized = {"curves_1d": {}, "cop_surfaces": {}, "raw_curves": {}}
    if not isinstance(equipment_curves, dict):
        return normalized
    for item_key, item in equipment_curves.items():
        if not isinstance(item, dict):
            continue
        curve = item.get("curve")
        if not isinstance(curve, dict):
            continue
        curve_id = curve.get("curve_id") or item_key
        parsed_curve = _parse_equipment_curve(curve)
        if not parsed_curve:
            continue
        normalized["raw_curves"][curve_id] = parsed_curve
        ctype = parsed_curve.get("type", "").lower()
        if ctype == "1d_lookup_table" and curve_id not in normalized["curves_1d"]:
            normalized["curves_1d"][curve_id] = {
                "x_name": parsed_curve.get("x_axis"),
                "y_name": parsed_curve.get("output"),
                "method": parsed_curve.get("interpolation", "linear"),
                "points": _build_1d_curve_points(parsed_curve)
            }
        if ctype == "2d_lookup_table" and parsed_curve.get("output", "").lower() == "cop" and curve_id not in normalized["cop_surfaces"]:
            surface = _build_cop_surface_from_2d_curve(parsed_curve)
            if surface is not None:
                normalized["cop_surfaces"][curve_id] = surface
    return normalized


def _normalize_curve_library(curve_lib):
    if not isinstance(curve_lib, dict):
        return {"curves_1d": {}, "cop_surfaces": {}, "raw_curves": {}}
    normalized = {"curves_1d": {}, "cop_surfaces": {}, "raw_curves": {}}
    if isinstance(curve_lib.get("curves_1d"), dict):
        normalized["curves_1d"] = curve_lib.get("curves_1d", {})
        normalized["raw_curves"].update(curve_lib.get("curves_1d", {}))
    if isinstance(curve_lib.get("cop_surfaces"), dict):
        normalized["cop_surfaces"] = curve_lib.get("cop_surfaces", {})
        normalized["raw_curves"].update(curve_lib.get("cop_surfaces", {}))
    if isinstance(curve_lib.get("curves"), dict):
        normalized["raw_curves"].update(curve_lib.get("curves", {}))
        for name, curve in curve_lib.get("curves", {}).items():
            if not isinstance(curve, dict):
                continue
            ctype = str(curve.get("type", "")).lower()
            if ctype == "1d_lookup_table" and name not in normalized["curves_1d"]:
                normalized["curves_1d"][name] = {
                    "x_name": curve.get("x_axis"),
                    "y_name": curve.get("output"),
                    "method": curve.get("interpolation", "linear"),
                    "points": _build_1d_curve_points(curve)
                }
            if ctype == "2d_lookup_table" and curve.get("output", "").lower() == "cop" and name not in normalized["cop_surfaces"]:
                surface = _build_cop_surface_from_2d_curve(curve)
                if surface is not None:
                    normalized["cop_surfaces"][name] = surface
    if isinstance(curve_lib.get("equipment_curves"), dict):
        eq_norm = _normalize_equipment_curve_library(curve_lib.get("equipment_curves"))
        normalized["raw_curves"].update(eq_norm.get("raw_curves", {}))
        normalized["curves_1d"].update(eq_norm.get("curves_1d", {}))
        normalized["cop_surfaces"].update(eq_norm.get("cop_surfaces", {}))
    return normalized


def _eval_quadratic_curve(curve, x):
    coeffs = curve.get("coefficients", [])
    if not isinstance(coeffs, list) or len(coeffs) < 3:
        return 0.0
    a = _num(coeffs[0], 0.0)
    b = _num(coeffs[1], 0.0)
    c = _num(coeffs[2], 0.0)
    return float(a + b * x + c * x * x)


def _eval_curve_2d_generic(curve, x, y):
    points = _extract_2d_points(curve)
    if len(points) == 0 or x is None or y is None:
        return 0.0
    slices = {}
    for px, py, pz in points:
        slices.setdefault(px, []).append([py, pz])
    sorted_x = sorted(slices.items(), key=lambda item: item[0])
    if len(sorted_x) == 0:
        return 0.0
    method = str(curve.get("interpolation", "bilinear_or_pchip")).lower()
    method_y = "pchip" if "pchip" in method else "linear"
    if x <= sorted_x[0][0]:
        return float(eval_curve_1d(slices[sorted_x[0][0]], y, method_y))
    if x >= sorted_x[-1][0]:
        return float(eval_curve_1d(slices[sorted_x[-1][0]], y, method_y))
    for i in range(len(sorted_x) - 1):
        x0, pts0 = sorted_x[i]
        x1, pts1 = sorted_x[i + 1]
        if x0 <= x <= x1:
            z0 = float(eval_curve_1d(pts0, y, method_y))
            z1 = float(eval_curve_1d(pts1, y, method_y))
            if abs(x1 - x0) < 1e-12:
                return z0
            t = (x - x0) / (x1 - x0)
            return float(z0 + t * (z1 - z0))
    return float(eval_curve_1d(slices[sorted_x[-1][0]], y, method_y))


def _curve_value(curve_lib, curve_ref, x=None, y=None):
    if not curve_ref or not isinstance(curve_ref, str) or not isinstance(curve_lib, dict):
        return None
    raw_curves = curve_lib.get("raw_curves", {})
    if curve_ref in raw_curves:
        curve = raw_curves[curve_ref]
        if not isinstance(curve, dict):
            return None
        ctype = str(curve.get("type", "")).lower()
        if ctype == "1d_lookup_table":
            pts = _build_1d_curve_points(curve)
            return _num(eval_curve_1d(pts, x, curve.get("interpolation", "linear")), None)
        if ctype == "quadratic_curve":
            return _num(_eval_quadratic_curve(curve, x), None)
        if ctype == "2d_lookup_table":
            if x is None or y is None:
                return None
            return _num(_eval_curve_2d_generic(curve, x, y), None)
        if ctype == "sparse_2d_points":
            if x is None or y is None:
                return None
            return _num(_eval_sparse_2d_points(curve, x, y), None)
        if isinstance(curve.get("points"), list):
            return _num(eval_curve_1d(curve.get("points", []), x, curve.get("method", "linear")), None)
        if isinstance(curve.get("oat_slices"), list) and x is not None and y is not None:
            return _num(eval_cop_surface(curve, y, x), None)
    return None


def _build_legacy_auxiliary_control(aux_loads):
    control = {}
    if not isinstance(aux_loads, dict):
        return control
    control["lighting_power_kw"] = _num(aux_loads.get("lighting_kW"), 0.0)
    control["security_power_kw"] = _num(aux_loads.get("security_kW"), 0.0)
    control["other_aux_power_kw"] = _num(aux_loads.get("controls_kW"), 0.0) + _num(aux_loads.get("misc_kW"), 0.0)
    return control


def _compute_constant_or_load_ratio(item):
    if not isinstance(item, dict):
        return 0.0
    rated = _num(item.get("rated_power_kW"), None)
    if rated is None:
        return 0.0
    load_ratio = _num(item.get("load_ratio"), None)
    if load_ratio is None:
        load_ratio = 1.0
    load_ratio = _clamp(load_ratio, 0.0, 1.0)
    return float(rated * load_ratio)


def _build_legacy_input_for_project(input_obj, it_load_kw=0.0, oat_c=None, wet_bulb_c=None, rh=None):
    if not isinstance(input_obj, dict):
        return {}
    legacy = {}
    curve_lib = _normalize_curve_library(input_obj.get("curve_library", None) or input_obj.get("curveLib", None) or {})
    legacy["curve_library"] = curve_lib

    equipment = input_obj.get("equipment", {}) if isinstance(input_obj.get("equipment", {}), dict) else {}
    cooling_system = input_obj.get("cooling_system", {}) if isinstance(input_obj.get("cooling_system", {}), dict) else {}
    selected_mode = str(cooling_system.get("selected_mode", "")).strip()
    free_cooling = cooling_system.get("free_cooling", {}) if isinstance(cooling_system.get("free_cooling", {}), dict) else {}

    ups_list = []
    ups_obj = equipment.get("electrical", {}).get("UPS") if isinstance(equipment.get("electrical", {}), dict) else None
    if isinstance(ups_obj, dict) and ups_obj.get("enabled", False):
        ups_entry = {"ups_id": "UPS"}
        curve_ref = ups_obj.get("curve_ref")
        if isinstance(curve_ref, str) and curve_ref:
            ups_entry["efficiency_curve_ref"] = curve_ref
        if ups_obj.get("efficiency_percent") is not None:
            ups_entry["efficiency_percent"] = ups_obj.get("efficiency_percent")
        load_percent = _num(ups_obj.get("load_percent"), None)
        if load_percent is not None:
            ups_entry["load_percent"] = load_percent
        ups_list.append(ups_entry)
    if ups_list:
        legacy["ups"] = ups_list

    transformers = []
    electrical = equipment.get("electrical", {}) if isinstance(equipment.get("electrical", {}), dict) else {}
    for key in ["MV_transformer", "LV_transformer"]:
        tr_obj = electrical.get(key)
        if isinstance(tr_obj, dict) and tr_obj.get("enabled", False):
            tentry = {"transformer_id": key}
            curve_ref = tr_obj.get("curve_ref")
            if isinstance(curve_ref, str) and curve_ref:
                tentry["efficiency_curve_ref"] = curve_ref
            if tr_obj.get("efficiency_percent") is not None:
                tentry["efficiency_percent"] = tr_obj.get("efficiency_percent")
            if tr_obj.get("rated_power_kW") is not None:
                tentry["rated_power_kw"] = tr_obj.get("rated_power_kW")
            if tr_obj.get("load_ratio") is not None:
                tentry["load_ratio"] = tr_obj.get("load_ratio")
            transformers.append(tentry)
    if transformers:
        legacy["transformers"] = transformers

    cooling = {}
    cooling_equipment = equipment.get("cooling", {}) if isinstance(equipment.get("cooling", {}), dict) else {}
    if isinstance(cooling_equipment.get("chiller"), dict) and cooling_equipment.get("chiller", {}).get("enabled", False):
        ch = cooling_equipment.get("chiller", {})
        ch_entry = {"chiller_id": "CH-1", "enabled": True}
        if ch.get("curve_ref"):
            ch_entry["cop_curve_ref"] = ch.get("curve_ref")
        cap = _num(ch.get("capacity_kw"), None)
        if cap is None:
            cap = _num(ch.get("rated_capacity_kw"), None)
        if cap is None or cap <= 0:
            cap = max(100.0, float(it_load_kw or 0.0))
        ch_entry["capacity_kw"] = cap
        legacy["chillers"] = [ch_entry]
    elif isinstance(cooling_equipment.get("ACC"), dict) and cooling_equipment.get("ACC", {}).get("enabled", False):
        acc = cooling_equipment.get("ACC", {})
        if selected_mode == "ACC_integrated_air_cooled_chiller" or selected_mode == "acc_integrated_air_cooled_chiller":
            ch_entry = {"chiller_id": "ACC-1", "enabled": True}
            if acc.get("curve_ref"):
                ch_entry["cop_curve_ref"] = acc.get("curve_ref")
            ch_entry["capacity_kw"] = max(100.0, float(it_load_kw or 0.0))
            legacy["chillers"] = [ch_entry]
    if cooling:
        cooling["oat_c"] = _num(oat_c, 25.0)
        legacy["cooling"] = cooling

    cooling_towers = []
    if isinstance(cooling_equipment.get("dry_cooler"), dict) and cooling_equipment.get("dry_cooler", {}).get("enabled", False):
        dry = cooling_equipment.get("dry_cooler", {})
        fan_ref = dry.get("fan_power_curve_ref")
        fan_power = None
        if fan_ref:
            fan_power = _curve_value(curve_lib, fan_ref, 1.0, None)
        if fan_power is None:
            fan_power = 0.0
        cooling_towers.append({"fan_power_kw": float(fan_power), "pump_power_kw": 0.0})
    if isinstance(cooling_equipment.get("closed_cooling_tower"), dict) and cooling_equipment.get("closed_cooling_tower", {}).get("enabled", False):
        cct = cooling_equipment.get("closed_cooling_tower", {})
        cooling_towers.append({"fan_power_kw": _num(cct.get("fan_power_kw"), 0.0), "pump_power_kw": _num(cct.get("pump_power_kw"), 0.0)})
    if cooling_towers:
        legacy["cooling_towers"] = cooling_towers

    pumps = []
    if isinstance(cooling_equipment.get("pumps"), dict) and cooling_equipment.get("pumps", {}).get("enabled", False):
        pumps_obj = cooling_equipment.get("pumps", {})
        pentry = {}
        if pumps_obj.get("curve_ref"):
            flow_ratio = 1.0
            if it_load_kw is not None and _num(input_obj.get("project", {}).get("it_load", {}).get("design_it_load_kW"), None):
                design = _num(input_obj.get("project", {}).get("it_load", {}).get("design_it_load_kW"), 0.0)
                if design > 0:
                    flow_ratio = _clamp(float(it_load_kw) / design, 0.0, 1.0)
            value = _curve_value(curve_lib, pumps_obj.get("curve_ref"), flow_ratio, None)
            pentry["power_kw"] = float(value or 0.0)
        pumps.append(pentry)
    if pumps:
        legacy["pumps"] = pumps

    if isinstance(cooling_equipment.get("CDU"), dict) and cooling_equipment.get("CDU", {}).get("enabled", False):
        cdu_power = _compute_constant_or_load_ratio(cooling_equipment.get("CDU", {}))
        if cdu_power > 0:
            legacy.setdefault("control", {}).setdefault("other_aux_power_kw", 0.0)
            legacy["control"]["other_aux_power_kw"] += float(cdu_power)
    if isinstance(cooling_equipment.get("FWU"), dict) and cooling_equipment.get("FWU", {}).get("enabled", False):
        fwu_power = _compute_constant_or_load_ratio(cooling_equipment.get("FWU", {}))
        if fwu_power > 0:
            legacy.setdefault("control", {}).setdefault("other_aux_power_kw", 0.0)
            legacy["control"]["other_aux_power_kw"] += float(fwu_power)

    aux_control = _build_legacy_auxiliary_control(equipment.get("auxiliary_loads", {}))
    if aux_control:
        legacy.setdefault("control", {}).update(aux_control)

    legacy.setdefault("power", {})["total_it_power_kw"] = float(it_load_kw)
    legacy.setdefault("environmental_conditions", {})["outdoor_temp_c"] = _num(oat_c, 25.0)
    if wet_bulb_c is not None:
        legacy["environmental_conditions"]["wet_bulb_temp_c"] = _num(wet_bulb_c, 0.0)
    if rh is not None:
        legacy["environmental_conditions"]["relative_humidity_percent"] = _num(rh, 0.0)
    return legacy


def _validate_project_input(input_obj, hourly_count=None):
    checks = {}
    warnings = []
    project = input_obj.get("project", {}) if isinstance(input_obj.get("project", {}), dict) else {}
    weather = input_obj.get("weather", {}) if isinstance(input_obj.get("weather", {}), dict) else {}
    curve_lib = input_obj.get("curve_library", {}) if isinstance(input_obj.get("curve_library", {}), dict) else {}
    hourly_it_load = project.get("it_load", {}).get("hourly_it_load_kW", []) if isinstance(project.get("it_load", {}), dict) else []
    dry_bulb = weather.get("hourly_data", {}).get("dry_bulb_C", []) if isinstance(weather.get("hourly_data", {}), dict) else []
    curves = curve_lib.get("curves", {}) if isinstance(curve_lib.get("curves", {}), dict) else {}
    curves_1d = curve_lib.get("curves_1d", {}) if isinstance(curve_lib.get("curves_1d", {}), dict) else {}
    cop_surfaces = curve_lib.get("cop_surfaces", {}) if isinstance(curve_lib.get("cop_surfaces", {}), dict) else {}
    checks["8760_weather_length_check"] = len(dry_bulb) == len(hourly_it_load) and len(dry_bulb) > 0
    checks["8760_IT_load_length_check"] = len(hourly_it_load) > 0
    checks["curve_data_not_empty_check"] = any(
        (isinstance(curve, dict) and bool(curve.get("data") or curve.get("points")))
        for curve in list(curves.values()) + list(curves_1d.values()) + list(cop_surfaces.values())
    )
    selected_mode = input_obj.get("cooling_system", {}).get("selected_mode", "")
    equipment = input_obj.get("equipment", {}) if isinstance(input_obj.get("equipment", {}), dict) else {}
    enabled = equipment.get("cooling", {}) if isinstance(equipment.get("cooling", {}), dict) else {}
    mode_ok = True
    if selected_mode == "ACC_integrated_air_cooled_chiller" and not isinstance(enabled.get("ACC"), dict):
        mode_ok = False
    if selected_mode == "centrifugal_chiller_plus_dry_cooler" and not isinstance(enabled.get("dry_cooler"), dict):
        mode_ok = False
    if selected_mode == "centrifugal_chiller_plus_closed_cooling_tower" and not isinstance(enabled.get("closed_cooling_tower"), dict):
        mode_ok = False
    checks["selected_cooling_mode_equipment_check"] = mode_ok
    if not checks["8760_weather_length_check"]:
        warnings.append("hourly IT load and weather data lengths mismatch or missing")
    if not checks["curve_data_not_empty_check"]:
        warnings.append("curve data appears missing or empty")
    if not mode_ok:
        warnings.append("selected cooling mode equipment is not fully defined or enabled")
    if hourly_count is not None and len(hourly_it_load) != hourly_count:
        warnings.append("provided hourly counts do not match expected 8760 length")
    return {"checks": checks, "warnings": warnings}

# -------------------------
# Main compute
# -------------------------

def compute_pue_v04(input_obj):
    """
    input_obj: dict (your JSON)
    returns: dict (result JSON)
    """
    if not isinstance(input_obj, dict):
        return {"error": "input is not an object"}

    # curve library passed from UI (recommended)
    curve_lib = input_obj.get("curve_library", None)
    if curve_lib is None:
        curve_lib = input_obj.get("curveLib", None)  # tolerate alt key
    if curve_lib is None and isinstance(input_obj.get("equipment_curves"), dict):
        curve_lib = {"equipment_curves": input_obj.get("equipment_curves")}
    if curve_lib is None:
        curve_lib = {"curves_1d": {}, "cop_surfaces": {}}
    curve_lib = _normalize_curve_library(curve_lib)

    # IT power
    p_it, p_it_src = _compute_it_power(input_obj)

    # power chain losses
    ups_loss, ups_rows = _compute_ups_loss(input_obj, curve_lib, p_it)
    tr_loss, tr_rows = _compute_transformer_loss(input_obj, curve_lib, p_it, p_it + ups_loss)
    power_dist_loss = ups_loss + tr_loss

    # Compute non-chiller powers first, because cooling heat load uses them as heat sources.
    pumps_kw, pumps_rows = _compute_pumps_power(input_obj)
    airflow_kw, airflow_rows = _compute_airflow_power(input_obj)
    aux_kw, aux_detail = _compute_control_aux_power(input_obj)
    other_kw = _compute_other_fixed(input_obj)

    # Thermal cooling load from explicit heat-source breakdown:
    # IT liquid + IT air + pumps + airflow + lighting + other thermal sources.
    cooling_load_kw, cooling_heat_sources, cooling_heat_meta = _compute_cooling_heat_sources(
        input_obj,
        p_it_kw=p_it,
        pumps_kw=pumps_kw,
        airflow_kw=airflow_kw,
        aux_detail=aux_detail
    )

    # Write resolved cooling load into input_obj so _compute_chiller_power allocation uses it.
    if not isinstance(input_obj.get("cooling", None), dict):
        input_obj["cooling"] = {}
    input_obj["cooling"]["cooling_load_kw"] = float(cooling_load_kw)

    # Chiller after resolved cooling load
    chiller_kw, ch_rows = _compute_chiller_power(input_obj, curve_lib, p_it)

    # Towers are still direct-power sum for now.
    cooling_towers = input_obj.get("cooling_towers", [])
    tower_fan_kw = 0.0
    tower_pump_kw = 0.0
    if isinstance(cooling_towers, list):
        for t in cooling_towers:
            if isinstance(t, dict):
                tower_fan_kw += _num(t.get("fan_power_kw"), 0.0)
                tower_pump_kw += _num(t.get("pump_power_kw"), 0.0)

    cooling_kw = chiller_kw + pumps_kw + tower_fan_kw + tower_pump_kw

    # Reporting OAT
    oat_c = _num(_get(input_obj, ["environmental_conditions", "outdoor_temp_c"], None), None)
    if oat_c is None:
        oat_c = _num(_get(input_obj, ["cooling", "oat_c"], None), None)
    if oat_c is None:
        oat_c = 25.0

    # Facility power: ALWAYS use model sum (predictive model)
    p_facility_model = p_it + power_dist_loss + cooling_kw + airflow_kw + aux_kw + other_kw
    p_facility = p_facility_model
    facility_src = "model_sum"

    # Optional: measured facility power for validation only (does NOT affect PUE)
    p_fac_meas = _num(_get(input_obj, ["power", "total_facility_power_kw"], None), None)
    facility_validation = None
    if p_fac_meas is not None and p_fac_meas > 0 and p_it > 0:
        abs_err = p_fac_meas - p_facility_model
        rel_err = abs_err / p_facility_model if p_facility_model > 0 else None
        facility_validation = {
            "facility_measured_kw": p_fac_meas,
            "facility_model_kw": p_facility_model,
            "abs_error_kw": abs_err,
            "rel_error": rel_err
        }

    # PUE
    pue = None
    if p_it > 0:
        pue = p_facility / p_it

    # pPUE breakdown (partial PUE components)
    def _ppue(x):
        return (x / p_it) if p_it > 0 else None

    ppue = {
        "cooling": _ppue(cooling_kw),
        "power_distribution": _ppue(power_dist_loss),
        "airflow": _ppue(airflow_kw),
        "lighting_and_aux": _ppue(aux_kw),
        "other": _ppue(other_kw)
    }

    # ERE
    reuse_credit_kw, hr_detail = _compute_heat_reuse_credit(input_obj)
    ere = None
    if p_it > 0:
        ere = (p_facility - reuse_credit_kw) / p_it

    # WUE/CUE placeholders (need energy integration later)
    env = input_obj.get("environmental_conditions", {})
    water_m3 = _num(env.get("water_consumption_m3"), 0.0) if isinstance(env, dict) else 0.0
    co2_kg = _num(env.get("carbon_emission_kgco2e"), 0.0) if isinstance(env, dict) else 0.0

    # Output
    result = {
        "site": input_obj.get("site", {}),
        "measurement_timestamp": input_obj.get("measurement_timestamp", None),

        "power": {
            "total_it_power_kw": p_it,
            "total_facility_power_kw": p_facility,
            "pue_instant": pue,
            "pPUE": ppue,
            "ere_instant": ere,
            "_sources": {
                "it_power_source": p_it_src,
                "facility_power_source": facility_src
            }
        },

        "_breakdown_v04": {
            "it_kw": p_it,
            "facility_kw": p_facility,

            "oat_c": oat_c,
            "cooling_load_kw": cooling_load_kw,
            "cooling_heat_sources_kw": cooling_heat_sources,
            "cooling_heat_meta": cooling_heat_meta,
            "it_liquid_cooling_kw": cooling_heat_sources.get("it_liquid_kw", 0.0),
            "it_air_cooling_kw": cooling_heat_sources.get("it_air_kw", 0.0),

            "power_distribution_loss_kw": power_dist_loss,
            "ups_loss_kw": ups_loss,
            "transformer_loss_kw": tr_loss,

            "cooling_kw": cooling_kw,
            "chiller_kw": chiller_kw,
            "pumps_kw": pumps_kw,
            "tower_fan_kw": tower_fan_kw,
            "tower_pump_kw": tower_pump_kw,

            "airflow_kw": airflow_kw,
            "aux_kw": aux_kw,
            "other_kw": other_kw,

            "heat_reuse_credit_kw": reuse_credit_kw,

            "_details": {
                "ups": ups_rows,
                "transformers": tr_rows,
                "chillers": ch_rows,
                "pumps": pumps_rows if isinstance(pumps_rows, list) else [],
                "airflow": airflow_rows if isinstance(airflow_rows, list) else [],
                "control": aux_detail,
                "heat_recovery": hr_detail,
                "env": {
                    "water_consumption_m3": water_m3,
                    "carbon_emission_kgco2e": co2_kg
                }
            }
        }
    }

    if facility_validation is not None:
        result["_facility_validation"] = facility_validation

    return result


def compute_pue_project(input_obj):
    """
    input_obj: dict in the project schema
    returns: dict with hourly, annual, peak, and validation summaries
    """
    if not isinstance(input_obj, dict):
        return {"error": "input is not an object"}

    # curve library passed from UI (recommended)
    curve_lib = input_obj.get("curve_library", None)
    if curve_lib is None:
        curve_lib = input_obj.get("curveLib", None)  # tolerate alt key
    if curve_lib is None and isinstance(input_obj.get("equipment_curves"), dict):
        curve_lib = {"equipment_curves": input_obj.get("equipment_curves")}
    if curve_lib is None:
        curve_lib = {"curves_1d": {}, "cop_surfaces": {}}
    curve_lib = _normalize_curve_library(curve_lib)

    project = input_obj.get("project", {}) if isinstance(input_obj.get("project", {}), dict) else {}
    weather = input_obj.get("weather", {}) if isinstance(input_obj.get("weather", {}), dict) else {}
    it_load = project.get("it_load", {}) if isinstance(project.get("it_load", {}), dict) else {}
    hourly_it_load = it_load.get("hourly_it_load_kW", []) if isinstance(it_load.get("hourly_it_load_kW", []), list) else []
    weather_data = weather.get("hourly_data", {}) if isinstance(weather.get("hourly_data", {}), dict) else {}
    dry_bulb = weather_data.get("dry_bulb_C", []) if isinstance(weather_data.get("dry_bulb_C", []), list) else []
    wet_bulb = weather_data.get("wet_bulb_C", []) if isinstance(weather_data.get("wet_bulb_C", []), list) else []
    rel_humidity = weather_data.get("relative_humidity_percent", []) if isinstance(weather_data.get("relative_humidity_percent", []), list) else []
    hour_index = weather_data.get("hour_index", []) if isinstance(weather_data.get("hour_index", []), list) else []
    design_it_load = _num(it_load.get("design_it_load_kW"), None)
    if design_it_load is None or design_it_load <= 0:
        design_it_load = max([_num(v, 0.0) for v in hourly_it_load], default=0.0)
    if design_it_load <= 0:
        design_it_load = _num(project.get("design_it_load_kW"), 0.0)
    aux_cfg = project.get("auxiliary_loads", {}) if isinstance(project.get("auxiliary_loads", {}), dict) else {}
    aux_coeff = _num(aux_cfg.get("auxiliary_fixed_load_coefficient"), None)
    if aux_coeff is None:
        aux_coeff = _num(aux_cfg.get("auxiliary_fixed_load_ratio"), None)
    if aux_coeff is None:
        aux_coeff = _num(_get(input_obj, ["equipment", "auxiliary_loads", "auxiliary_fixed_load_coefficient"], None), None)
    if aux_coeff is None:
        aux_coeff = 0.005
    aux_coeff = _clamp(float(aux_coeff), 0.0, 1.0)

    dry_cooler_cfg = _get(input_obj, ["equipment", "cooling", "dry_cooler"], {})
    if not isinstance(dry_cooler_cfg, dict):
        dry_cooler_cfg = {}
    dry_cooler_curve_ref = dry_cooler_cfg.get("power_curve_ref") or dry_cooler_cfg.get("curve_ref") or "dry_cooler_power_vs_load"
    dry_cooler_leaving_water_ref = (
        dry_cooler_cfg.get("leaving_water_temp_curve_ref")
        or dry_cooler_cfg.get("outlet_water_temp_curve_ref")
        or dry_cooler_cfg.get("condenser_water_temp_curve_ref")
        or "dry_cooler_leaving_water_temp_vs_oat"
    )
    dry_cooler_rated_power_kw = _num(dry_cooler_cfg.get("rated_power_kW"), None)
    if dry_cooler_rated_power_kw is None:
        dry_cooler_rated_power_kw = _num(dry_cooler_cfg.get("rated_power_kw"), None)
    if dry_cooler_rated_power_kw is None:
        dry_cooler_rated_power_kw = 0.03 * float(design_it_load or 0.0)
    dry_cooler_approach_c = _num(dry_cooler_cfg.get("approach_C"), None)
    if dry_cooler_approach_c is None:
        dry_cooler_approach_c = _num(dry_cooler_cfg.get("approach_c"), None)
    if dry_cooler_approach_c is None:
        dry_cooler_approach_c = 5.0

    chiller_cfg = _get(input_obj, ["equipment", "cooling", "chiller"], {})
    if not isinstance(chiller_cfg, dict):
        chiller_cfg = {}
    chiller_curve_ref = chiller_cfg.get("curve_ref") or chiller_cfg.get("cop_curve_ref") or "chiller_COP_H_vs_load"

    pumps_cfg = _get(input_obj, ["equipment", "cooling", "pumps"], {})
    if not isinstance(pumps_cfg, dict):
        pumps_cfg = {}
    pump_curve_refs = pumps_cfg.get("power_curve_refs") or pumps_cfg.get("curve_refs")
    if isinstance(pump_curve_refs, str):
        pump_curve_refs = [pump_curve_refs]
    if not isinstance(pump_curve_refs, list):
        raw_curve_names = list(curve_lib.get("raw_curves", {}).keys()) if isinstance(curve_lib, dict) else []
        pump_curve_refs = [name for name in raw_curve_names if "pump_power_vs_it_load" in str(name)]
    pumps_enabled = bool(pumps_cfg.get("enabled", True))

    fan_cfg = _get(input_obj, ["equipment", "cooling", "fans"], {})
    if not isinstance(fan_cfg, dict):
        fan_cfg = {}
    fan_curve_ref = fan_cfg.get("power_curve_ref") or fan_cfg.get("curve_ref") or "terminal_fan_power_vs_it_load"
    fan_rated_power_kw = _num(fan_cfg.get("rated_power_kW"), None)
    if fan_rated_power_kw is None:
        fan_rated_power_kw = _num(fan_cfg.get("rated_power_kw"), None)
    if fan_rated_power_kw is None:
        fan_rated_power_kw = 0.02 * float(design_it_load or 0.0)
    fans_enabled = bool(fan_cfg.get("enabled", False))

    validation = _validate_project_input(input_obj)
    result = {
        "project": project,
        "weather": weather,
        "validation": validation,
        "hourly_results": [],
        "annual_results": {},
        "peak_results": {}
    }

    if len(hourly_it_load) == 0 or len(dry_bulb) == 0:
        # fallback to a single design snapshot
        it_kw = _num(project.get("design_it_load_kW"), 0.0)
        oat_c = _num(project.get("location", {}).get("design_dry_bulb_C"), None)
        wet_c = _num(project.get("location", {}).get("design_wet_bulb_C"), None)
        input_hour = _build_legacy_input_for_project(input_obj, it_load_kw=it_kw, oat_c=oat_c, wet_bulb_c=wet_c)
        out = compute_pue_v04(input_hour)
        result["hourly_results"] = [
            {
                "hour_index": 0,
                "dry_bulb_C": oat_c,
                "wet_bulb_C": wet_c,
                "relative_humidity_percent": None,
                "IT_load_kW": it_kw,
                "cooling_power_kW": out.get("_breakdown_v04", {}).get("cooling_kw"),
                "electrical_loss_kW": out.get("_breakdown_v04", {}).get("power_distribution_loss_kw"),
                "auxiliary_power_kW": out.get("_breakdown_v04", {}).get("aux_kw", 0.0) + out.get("_breakdown_v04", {}).get("other_kw", 0.0),
                "total_facility_power_kW": out.get("power", {}).get("total_facility_power_kw"),
                "hourly_PUE": out.get("power", {}).get("pue_instant")
            }
        ]
        it_energy = it_kw
        facility_energy = out.get("power", {}).get("total_facility_power_kw", 0.0)
        cooling_energy = out.get("_breakdown_v04", {}).get("cooling_kw", 0.0)
        electrical_loss_energy = out.get("_breakdown_v04", {}).get("power_distribution_loss_kw", 0.0)
        auxiliary_energy = out.get("_breakdown_v04", {}).get("aux_kw", 0.0) + out.get("_breakdown_v04", {}).get("other_kw", 0.0)
        annual_pue = facility_energy / it_energy if it_energy > 0 else None
        result["annual_results"] = {
            "annual_average_PUE": annual_pue,
            "annual_IT_energy_kWh": it_energy,
            "annual_facility_energy_kWh": facility_energy,
            "annual_cooling_energy_kWh": cooling_energy,
            "annual_electrical_loss_kWh": electrical_loss_energy,
            "annual_auxiliary_energy_kWh": auxiliary_energy
        }
        result["peak_results"] = {
            "peak_PUE": out.get("power", {}).get("pue_instant"),
            "peak_hour_index": 0,
            "peak_outdoor_dry_bulb_C": oat_c,
            "peak_outdoor_wet_bulb_C": wet_c,
            "peak_IT_load_kW": it_kw,
            "peak_total_facility_power_kW": facility_energy
        }
        validation["checks"]["PUE_greater_than_1_check"] = annual_pue is None or annual_pue > 1.0
        validation["checks"]["peak_hour_consistency_check"] = True
        result["validation"] = validation
        return result

    n = max(len(hourly_it_load), len(dry_bulb))
    for i in range(n):
        it_kw = _num(hourly_it_load[i], 0.0) if i < len(hourly_it_load) else 0.0
        oat_c = _num(dry_bulb[i], None)
        wet_c = _num(wet_bulb[i], None) if i < len(wet_bulb) else None
        rh_val = _num(rel_humidity[i], None) if i < len(rel_humidity) else None
        idx = hour_index[i] if i < len(hour_index) else i

        load_ratio = (it_kw / design_it_load) if design_it_load and design_it_load > 0 else 0.0
        load_ratio = _clamp(load_ratio, 0.0, 1.0)

        # Direct calculation using curve_lib with simplified assumptions
        # Assume standard electrical chain: UPS + transformers
        ups_eff = _curve_value(curve_lib, "UPS_efficiency_double_conversion", load_ratio)
        if ups_eff is None or ups_eff <= 0 or ups_eff > 1:
            ups_eff = 0.95  # Default 95% efficiency
        ups_loss = (1.0 - ups_eff) * it_kw  # Loss = (1 - efficiency) * input_power

        # Transformer losses (simplified - assume one transformer)
        mv_tr_eff = _curve_value(curve_lib, "MV_transformer_efficiency", load_ratio)
        if mv_tr_eff is None or mv_tr_eff <= 0 or mv_tr_eff > 1:
            mv_tr_eff = 0.98  # Default 98% efficiency
        mv_tr_loss = (1.0 - mv_tr_eff) * (it_kw + ups_loss)

        lv_tr_eff = _curve_value(curve_lib, "LV_transformer_efficiency", load_ratio)
        if lv_tr_eff is None or lv_tr_eff <= 0 or lv_tr_eff > 1:
            lv_tr_eff = 0.97  # Default 97% efficiency
        lv_tr_loss = (1.0 - lv_tr_eff) * (it_kw + ups_loss + mv_tr_loss)

        power_dist_loss = ups_loss + mv_tr_loss + lv_tr_loss

        # Simplified variable loads (pumps, fans, etc.)
        pumps_kw = 0.01 * it_kw  # 1% of IT load
        if pumps_enabled and pump_curve_refs:
            pump_values = []
            for pump_ref in pump_curve_refs:
                pump_curve_value = _curve_value(curve_lib, str(pump_ref), load_ratio, None)
                if pump_curve_value is None:
                    continue
                raw_curve = curve_lib.get("raw_curves", {}).get(str(pump_ref), {}) if isinstance(curve_lib, dict) else {}
                output_name = str(raw_curve.get("output", "")).lower() if isinstance(raw_curve, dict) else ""
                if "kw" in output_name or "power_kw" in output_name:
                    pump_values.append(max(0.0, float(pump_curve_value)))
                else:
                    rated_each = (0.01 * float(design_it_load or 0.0)) / max(len(pump_curve_refs), 1)
                    pump_values.append(max(0.0, float(pump_curve_value) * rated_each))
            if pump_values:
                pumps_kw = sum(pump_values)
        airflow_kw = 0.02 * it_kw  # 2% of IT load
        if fans_enabled and fan_curve_ref:
            fan_curve_value = _curve_value(curve_lib, fan_curve_ref, load_ratio, None)
            if fan_curve_value is not None:
                raw_curve = curve_lib.get("raw_curves", {}).get(fan_curve_ref, {}) if isinstance(curve_lib, dict) else {}
                output_name = str(raw_curve.get("output", "")).lower() if isinstance(raw_curve, dict) else ""
                if "kw" in output_name or "power_kw" in output_name:
                    airflow_kw = max(0.0, float(fan_curve_value))
                else:
                    airflow_kw = max(0.0, float(fan_curve_value) * float(fan_rated_power_kw or 0.0))
        aux_kw = aux_coeff * it_kw
        other_kw = 0.0

        dry_cooler_kw = 0.0
        dry_curve_value = None
        dry_curve_load_value = load_ratio
        dry_cooler_power_source = "no_curve"
        if dry_cooler_curve_ref:
            dry_cooler_power_source = "curve_missing"
            raw_curve = curve_lib.get("raw_curves", {}).get(dry_cooler_curve_ref, {}) if isinstance(curve_lib, dict) else {}
            if isinstance(raw_curve, dict) and str(raw_curve.get("type", "")).lower() == "1d_lookup_table":
                raw_points = raw_curve.get("points")
                if not isinstance(raw_points, list):
                    raw_points = raw_curve.get("data", [])
                x_axis = raw_curve.get("x_axis")
                output = raw_curve.get("output")
                pts = []
                for point in raw_points if isinstance(raw_points, list) else []:
                    if isinstance(point, dict):
                        x = _num(point.get(x_axis), None)
                        y = _num(point.get(output), None)
                    elif isinstance(point, (list, tuple)) and len(point) >= 2:
                        x = _num(point[0], None)
                        y = _num(point[1], None)
                    else:
                        continue
                    if x is None or y is None:
                        continue
                    pts.append([x, y])
                if pts:
                    max_x = max(point[0] for point in pts)
                    if max_x > 2.0 and load_ratio <= 1.0:
                        dry_curve_load_value = load_ratio * 100.0
                    dry_curve_value = _num(eval_curve_1d(pts, dry_curve_load_value, raw_curve.get("interpolation", "linear")), None)
                    dry_cooler_power_source = "raw_points"
            if dry_curve_value is None:
                dry_curve_value = _curve_value(curve_lib, dry_cooler_curve_ref, dry_curve_load_value, None)
                if dry_curve_value is not None:
                    dry_cooler_power_source = "curve_value"
            if dry_curve_value is not None:
                output_name = str(raw_curve.get("output", "")).lower() if isinstance(raw_curve, dict) else ""
                if "kw" in output_name or "power_kw" in output_name:
                    dry_cooler_kw = max(0.0, float(dry_curve_value))
                    dry_cooler_power_source = f"{dry_cooler_power_source}_power_kw_direct"
                else:
                    dry_cooler_kw = max(0.0, float(dry_curve_value) * float(dry_cooler_rated_power_kw or 0.0))
                    dry_cooler_power_source = f"{dry_cooler_power_source}_power_factor_times_rated"

        condenser_entering_water_c = oat_c
        if dry_cooler_leaving_water_ref:
            leaving_water = None
            raw_curve = curve_lib.get("raw_curves", {}).get(dry_cooler_leaving_water_ref, {}) if isinstance(curve_lib, dict) else {}
            if isinstance(raw_curve, dict) and str(raw_curve.get("type", "")).lower() == "1d_lookup_table":
                raw_points = raw_curve.get("points")
                if not isinstance(raw_points, list):
                    raw_points = raw_curve.get("data", [])
                x_axis = raw_curve.get("x_axis")
                output = raw_curve.get("output")
                pts = []
                for point in raw_points if isinstance(raw_points, list) else []:
                    if isinstance(point, dict):
                        x = _num(point.get(x_axis), None)
                        y = _num(point.get(output), None)
                    elif isinstance(point, (list, tuple)) and len(point) >= 2:
                        x = _num(point[0], None)
                        y = _num(point[1], None)
                    else:
                        continue
                    if x is None or y is None:
                        continue
                    pts.append([x, y])
                if pts and oat_c is not None:
                    leaving_water = _num(eval_curve_1d(pts, oat_c, raw_curve.get("interpolation", "linear")), None)
            if leaving_water is None:
                leaving_water = _curve_value(curve_lib, dry_cooler_leaving_water_ref, oat_c, None)
            if leaving_water is not None:
                condenser_entering_water_c = float(leaving_water)
        if condenser_entering_water_c is None and oat_c is not None:
            condenser_entering_water_c = float(oat_c) + float(dry_cooler_approach_c)
        elif oat_c is not None and dry_cooler_leaving_water_ref:
            raw_curve = curve_lib.get("raw_curves", {}).get(dry_cooler_leaving_water_ref, {}) if isinstance(curve_lib, dict) else {}
            if not raw_curve:
                condenser_entering_water_c = float(oat_c) + float(dry_cooler_approach_c)

        # Thermal cooling load from IT heat sources
        it_heat_load = it_kw  # Simplified - IT heat load equals IT power
        pumps_heat = pumps_kw
        airflow_heat = airflow_kw
        other_heat = aux_kw + other_kw
        total_thermal_load = it_heat_load + pumps_heat + airflow_heat + other_heat

        # Cooling power calculation using COP curve
        cop_load_value = load_ratio
        raw_chiller_curve = curve_lib.get("raw_curves", {}).get(chiller_curve_ref, {}) if isinstance(curve_lib, dict) else {}
        chiller_y_axis = str(raw_chiller_curve.get("y_axis", "")).lower() if isinstance(raw_chiller_curve, dict) else ""
        cop_uses_percent_load = "percent" in chiller_y_axis or "pct" in chiller_y_axis
        if not cop_uses_percent_load:
            cop_surfaces = curve_lib.get("cop_surfaces", {}) if isinstance(curve_lib, dict) else {}
            surface = cop_surfaces.get(chiller_curve_ref) if isinstance(cop_surfaces, dict) else None
            if isinstance(surface, dict):
                for slice_item in surface.get("oat_slices", []) if isinstance(surface.get("oat_slices", []), list) else []:
                    for point in slice_item.get("points", []) if isinstance(slice_item, dict) and isinstance(slice_item.get("points", []), list) else []:
                        if isinstance(point, (list, tuple)) and len(point) >= 1 and _num(point[0], 0.0) > 2.0:
                            cop_uses_percent_load = True
                            break
                    if cop_uses_percent_load:
                        break
        if not cop_uses_percent_load and isinstance(raw_chiller_curve, dict):
            raw_points = raw_chiller_curve.get("points")
            if not isinstance(raw_points, list):
                raw_points = raw_chiller_curve.get("data", [])
            for point in raw_points if isinstance(raw_points, list) else []:
                y = _num(point.get(raw_chiller_curve.get("y_axis")) if isinstance(point, dict) else (point[1] if isinstance(point, (list, tuple)) and len(point) >= 2 else None), None)
                if y is not None and y > 2.0:
                    cop_uses_percent_load = True
                    break
        if cop_uses_percent_load and load_ratio <= 1.0:
            cop_load_value = load_ratio * 100.0

        cop = _curve_value(curve_lib, chiller_curve_ref, x=condenser_entering_water_c, y=cop_load_value)
        cop_source = "curve_value"
        if cop is None or cop <= 0:
            cop_surfaces = curve_lib.get("cop_surfaces", {}) if isinstance(curve_lib, dict) else {}
            surface = cop_surfaces.get(chiller_curve_ref) if isinstance(cop_surfaces, dict) else None
            if isinstance(surface, dict):
                cop = _num(eval_cop_surface(surface, cop_load_value, condenser_entering_water_c), None)
                cop_source = "cop_surface"

        if cop is None or cop <= 0:
            raw_curves = curve_lib.get("raw_curves", {}) if isinstance(curve_lib, dict) else {}
            raw_curve = raw_curves.get(chiller_curve_ref) if isinstance(raw_curves, dict) else None
            if isinstance(raw_curve, dict) and str(raw_curve.get("type", "")).lower() == "2d_lookup_table":
                raw_points = raw_curve.get("points")
                if not isinstance(raw_points, list):
                    raw_points = raw_curve.get("data", [])
                x_axis = raw_curve.get("x_axis")
                y_axis = raw_curve.get("y_axis")
                output = raw_curve.get("output")
                pts = []
                for point in raw_points if isinstance(raw_points, list) else []:
                    if isinstance(point, dict):
                        x = _num(point.get(x_axis), None)
                        y = _num(point.get(y_axis), None)
                        z = _num(point.get(output), None)
                    elif isinstance(point, (list, tuple)) and len(point) >= 3:
                        x = _num(point[0], None)
                        y = _num(point[1], None)
                        z = _num(point[2], None)
                    else:
                        continue
                    if x is None or y is None or z is None:
                        continue
                    pts.append([x, y, z])
                if pts and condenser_entering_water_c is not None:
                    slices = {}
                    for x, y, z in pts:
                        slices.setdefault(x, []).append([y, z])
                    sorted_x = sorted(slices.items(), key=lambda item: item[0])
                    method = str(raw_curve.get("interpolation", "bilinear_or_pchip")).lower()
                    method_y = "pchip" if "pchip" in method else "linear"
                    x_val = float(condenser_entering_water_c)
                    y_val = float(cop_load_value)
                    if x_val <= sorted_x[0][0]:
                        cop = _num(eval_curve_1d(slices[sorted_x[0][0]], y_val, method_y), None)
                    elif x_val >= sorted_x[-1][0]:
                        cop = _num(eval_curve_1d(slices[sorted_x[-1][0]], y_val, method_y), None)
                    else:
                        for j in range(len(sorted_x) - 1):
                            x0, pts0 = sorted_x[j]
                            x1, pts1 = sorted_x[j + 1]
                            if x0 <= x_val <= x1:
                                cop0 = float(eval_curve_1d(pts0, y_val, method_y))
                                cop1 = float(eval_curve_1d(pts1, y_val, method_y))
                                cop = cop0 if abs(x1 - x0) < 1e-12 else float(cop0 + (x_val - x0) / (x1 - x0) * (cop1 - cop0))
                                break
                    cop_source = "raw_curve_points"

        if cop is None or cop <= 0:
            cop = 3.0  # Default COP = 3.0
            cop_source = "default_3.0"
        chiller_kw = total_thermal_load / cop if cop > 0 else 0.3 * total_thermal_load
        cooling_kw = chiller_kw + dry_cooler_kw

        # Total facility power
        total_facility_power = it_kw + power_dist_loss + cooling_kw + pumps_kw + airflow_kw + aux_kw + other_kw

        # Calculate PUE
        pue = total_facility_power / it_kw if it_kw > 0 else None

        result["hourly_results"].append({
            "hour_index": idx,
            "dry_bulb_C": oat_c,
            "wet_bulb_C": wet_c,
            "relative_humidity_percent": rh_val,
            "IT_load_kW": it_kw,
            "cooling_power_kW": cooling_kw,
            "chiller_power_kW": chiller_kw,
            "dry_cooler_power_kW": dry_cooler_kw,
            "dry_cooler_power_source": dry_cooler_power_source,
            "dry_cooler_load_ratio": dry_curve_load_value,
            "dry_cooler_curve_value": dry_curve_value,
            "dry_cooler_rated_power_kw": dry_cooler_rated_power_kw,
            "condenser_entering_water_C": condenser_entering_water_c,
            "chiller_cop": cop,
            "cop_source": cop_source,
            "terminal_fan_power_kW": airflow_kw,
            "electrical_loss_kW": power_dist_loss,
            "auxiliary_power_kW": aux_kw + other_kw,
            "total_facility_power_kW": total_facility_power,
            "hourly_PUE": pue
        })

    annual_it = sum(item.get("IT_load_kW", 0.0) for item in result["hourly_results"])
    annual_facility = sum(item.get("total_facility_power_kW", 0.0) for item in result["hourly_results"])
    annual_cooling = sum(item.get("cooling_power_kW", 0.0) for item in result["hourly_results"])
    annual_chiller = sum(item.get("chiller_power_kW", 0.0) for item in result["hourly_results"])
    annual_dry_cooler = sum(item.get("dry_cooler_power_kW", 0.0) for item in result["hourly_results"])
    annual_terminal_fan = sum(item.get("terminal_fan_power_kW", 0.0) for item in result["hourly_results"])
    annual_loss = sum(item.get("electrical_loss_kW", 0.0) for item in result["hourly_results"])
    annual_aux = sum(item.get("auxiliary_power_kW", 0.0) for item in result["hourly_results"])
    annual_pue = annual_facility / annual_it if annual_it > 0 else None
    hourly_pues = [item.get("hourly_PUE") for item in result["hourly_results"] if item.get("hourly_PUE") is not None]
    peak_facility = max(result["hourly_results"], key=lambda x: x.get("total_facility_power_kW", 0.0))
    peak_pue = max(
        [item for item in result["hourly_results"] if item.get("hourly_PUE") is not None],
        key=lambda x: x.get("hourly_PUE", 0.0),
        default=peak_facility
    )
    result["annual_results"] = {
        "annual_average_PUE": annual_pue,
        "annual_IT_energy_kWh": annual_it,
        "annual_facility_energy_kWh": annual_facility,
        "annual_cooling_energy_kWh": annual_cooling,
        "annual_chiller_energy_kWh": annual_chiller,
        "annual_dry_cooler_energy_kWh": annual_dry_cooler,
        "annual_terminal_fan_energy_kWh": annual_terminal_fan,
        "annual_electrical_loss_kWh": annual_loss,
        "annual_auxiliary_energy_kWh": annual_aux,
        "min_hourly_PUE": min(hourly_pues) if hourly_pues else None,
        "max_hourly_PUE": max(hourly_pues) if hourly_pues else None
    }
    result["peak_results"] = {
        "peak_PUE": peak_pue.get("hourly_PUE"),
        "peak_PUE_hour_index": peak_pue.get("hour_index"),
        "peak_PUE_outdoor_dry_bulb_C": peak_pue.get("dry_bulb_C"),
        "peak_PUE_IT_load_kW": peak_pue.get("IT_load_kW"),
        "peak_hour_index": peak_facility.get("hour_index"),
        "peak_outdoor_dry_bulb_C": peak_facility.get("dry_bulb_C"),
        "peak_outdoor_wet_bulb_C": peak_facility.get("wet_bulb_C"),
        "peak_IT_load_kW": peak_facility.get("IT_load_kW"),
        "peak_total_facility_power_kW": peak_facility.get("total_facility_power_kW"),
        "peak_facility_hour_PUE": peak_facility.get("hourly_PUE")
    }
    validation["checks"]["PUE_greater_than_1_check"] = annual_pue is None or annual_pue > 1.0
    if isinstance(weather.get("design_peak_hour_method"), str) and weather.get("design_peak_hour_method").lower() == "highest_dry_bulb_hour":
        max_dry = max(range(len(dry_bulb)), key=lambda j: _num(dry_bulb[j], -1.0)) if len(dry_bulb) > 0 else None
        expected_peak = hour_index[max_dry] if max_dry is not None and max_dry < len(hour_index) else max_dry
        validation["checks"]["peak_hour_consistency_check"] = expected_peak == peak_facility.get("hour_index")
        if not validation["checks"]["peak_hour_consistency_check"]:
            validation["warnings"].append("peak hour PUE does not match highest dry bulb hour")
    else:
        validation["checks"]["peak_hour_consistency_check"] = True
    result["validation"] = validation
    return result


# -------------------------
# Backward-compatible aliases
# (so your UI can call older names without breaking)
# -------------------------
def compute_pue_v03(input_obj):
    return compute_pue_v04(input_obj)

def compute_pue_v02(input_obj):
    return compute_pue_v04(input_obj)

def compute_pue_v01(input_obj):
    return compute_pue_v04(input_obj)
