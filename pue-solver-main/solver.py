# solver.py
# PUE Solver v0.4-B (Math formalization)
# - PUE = P_facility / P_IT
# - pPUE_i = P_i / P_IT ; PUE = 1 + sum(pPUE_i) when i excludes IT
# - ERE = (P_facility - P_reuse_exported) / P_IT (if heat_recovery.enabled)
# - WUE/CUE interface: WU  E = water(L)/E_IT(kWh), CUE = CO2e(kg)/E_IT(kWh) for energy mode (future)
# Pyodide-friendly: no external deps.

from math import isfinite

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

def _compute_transformer_loss(input_obj):
    # trust provided total_loss_kw
    tr = input_obj.get("transformers", [])
    if not isinstance(tr, list):
        return 0.0, []
    rows = []
    total = 0.0
    for t in tr:
        if not isinstance(t, dict): 
            continue
        loss = _num(t.get("total_loss_kw"), 0.0)
        total += loss
        rows.append({"transformer_id": t.get("transformer_id","TR"), "loss_kw": loss})
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
    if curve_lib is None:
        curve_lib = {"curves_1d": {}, "cop_surfaces": {}}

    # IT power
    p_it, p_it_src = _compute_it_power(input_obj)

    # power chain losses
    ups_loss, ups_rows = _compute_ups_loss(input_obj, curve_lib, p_it)
    tr_loss, tr_rows = _compute_transformer_loss(input_obj)
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
