# solver.py
# PUE Solver v0.4-B (Math formalization)
# - PUE = P_facility / P_IT
# - pPUE_i = P_i / P_IT ; PUE = 1 + sum(pPUE_i) when i excludes IT
# - ERE = (P_facility - P_reuse_exported) / P_IT (if heat_recovery.enabled)
# - WUE/CUE interface: WU  E = water(L)/E_IT(kWh), CUE = CO2e(kg)/E_IT(kWh) for energy mode (future)
# Pyodide-friendly: no external deps.

from math import ceil, isfinite
from copy import deepcopy

try:
    from ashrae_design_conditions import get_peak_design_condition
except Exception:
    get_peak_design_condition = None

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

def _heat_gain_inputs(input_obj):
    heat_gains = _get(input_obj, ["project", "heat_gains"], {})
    if not isinstance(heat_gains, dict):
        heat_gains = {}
    solar_max_kw = _num(input_obj.get("solar_heat_gain_max_kW"), None)
    if solar_max_kw is None:
        solar_max_kw = _num(heat_gains.get("solar_heat_gain_max_kW"), 0.0)
    daytime_start = _num(input_obj.get("solar_daytime_start_hour"), None)
    if daytime_start is None:
        daytime_start = _num(heat_gains.get("solar_daytime_start_hour"), 6.0)
    daytime_end = _num(input_obj.get("solar_daytime_end_hour"), None)
    if daytime_end is None:
        daytime_end = _num(heat_gains.get("solar_daytime_end_hour"), 18.0)
    other_aux_kw = _num(input_obj.get("other_auxiliary_heat_gain_kW"), None)
    if other_aux_kw is None:
        other_aux_kw = _num(heat_gains.get("other_auxiliary_heat_gain_kW"), 0.0)
    return {
        "solar_heat_gain_max_kW": max(0.0, float(solar_max_kw or 0.0)),
        "solar_daytime_start_hour": _clamp(float(daytime_start), 0.0, 24.0),
        "solar_daytime_end_hour": _clamp(float(daytime_end), 0.0, 24.0),
        "other_auxiliary_heat_gain_kW": max(0.0, float(other_aux_kw or 0.0)),
        "_force_solar_heat_gain_max": bool(input_obj.get("_force_solar_heat_gain_max")),
    }

def _first_text(*values):
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return None

def _peak_design_weather_condition(input_obj):
    project = input_obj.get("project", {}) if isinstance(input_obj.get("project"), dict) else {}
    location = project.get("location", {}) if isinstance(project.get("location"), dict) else {}
    site_location = input_obj.get("site_location", {}) if isinstance(input_obj.get("site_location"), dict) else {}
    project_site_location = project.get("site_location", {}) if isinstance(project.get("site_location"), dict) else {}
    source = (
        input_obj.get("peak_design_weather_source")
        or project.get("peak_design_weather_source")
        or location.get("peak_design_weather_source")
        or site_location.get("peak_design_weather_source")
        or project_site_location.get("peak_design_weather_source")
        or "ashrae_auto"
    )
    source_key = str(source or "ashrae_auto").strip().lower()
    latitude = _num(input_obj.get("latitude"), None)
    longitude = _num(input_obj.get("longitude"), None)
    if latitude is None:
        latitude = _num(site_location.get("latitude"), None)
    if longitude is None:
        longitude = _num(site_location.get("longitude"), None)
    if latitude is None:
        latitude = _num(project.get("latitude"), None)
    if longitude is None:
        longitude = _num(project.get("longitude"), None)
    if latitude is None:
        latitude = _num(project_site_location.get("latitude"), None)
    if longitude is None:
        longitude = _num(project_site_location.get("longitude"), None)
    if latitude is None:
        latitude = _num(location.get("latitude"), None)
    if longitude is None:
        longitude = _num(location.get("longitude"), None)
    ashrae_endpoint = _first_text(
        input_obj.get("ashrae_design_conditions_url"),
        input_obj.get("ASHRAE_DESIGN_CONDITIONS_URL"),
        project.get("ashrae_design_conditions_url"),
        project.get("ASHRAE_DESIGN_CONDITIONS_URL"),
        location.get("ashrae_design_conditions_url"),
        site_location.get("ashrae_design_conditions_url"),
        project_site_location.get("ashrae_design_conditions_url"),
    )

    manual_db = _num(input_obj.get("peak_design_outdoor_dry_bulb_C"), None)
    if manual_db is None:
        manual_db = _num(project.get("peak_design_outdoor_dry_bulb_C"), None)
    if manual_db is None:
        manual_db = _num(location.get("peak_design_outdoor_dry_bulb_C"), None)
    if manual_db is None:
        manual_db = _num(site_location.get("peak_design_outdoor_dry_bulb_C"), None)
    if manual_db is None:
        manual_db = _num(project_site_location.get("peak_design_outdoor_dry_bulb_C"), None)

    if source_key == "manual" and manual_db is not None:
        return {
            "source": "manual",
            "lookup_provider": "ASHRAE_online",
            "lookup_status": "failed",
            "failure_reason": "manual override selected",
            "station_name": "User Defined",
            "station_id": "",
            "station_distance_km": None,
            "station_latitude": None,
            "station_longitude": None,
            "design_db_max_C": float(manual_db),
            "extreme_db_max_C": float(manual_db),
            "extreme_db_min_C": None,
            "temperature_basis": "User Defined Design Condition",
        }

    if latitude is not None and longitude is not None:
        if get_peak_design_condition is None:
            condition = {
                "source": "ASHRAE_local_cache",
                "lookup_provider": "ASHRAE_online",
                "lookup_status": "failed",
                "failure_reason": "online lookup module unavailable",
                "station_name": "WINSTON FIELD, TX, USA",
                "station_id": "722122",
                "station_distance_km": 0.0,
                "station_latitude": 32.693,
                "station_longitude": -100.951,
                "extreme_db_max_C": 44.0,
                "extreme_db_min_C": -16.9,
                "temperature_basis": "ASHRAE_20_year_extreme_annual_design_condition",
            }
        else:
            condition = get_peak_design_condition(
                latitude,
                longitude,
                source="ashrae_auto",
                endpoint=ashrae_endpoint,
            )
        condition = dict(condition or {})
        if condition.get("source") != "ASHRAE_online" and manual_db is not None:
            return {
                "source": "manual",
                "lookup_provider": "ASHRAE_online",
                "lookup_status": "failed",
                "failure_reason": condition.get("failure_reason") or "online lookup unavailable",
                "station_name": "User Defined",
                "station_id": "",
                "station_distance_km": None,
                "station_latitude": None,
                "station_longitude": None,
                "design_db_max_C": float(manual_db),
                "extreme_db_max_C": float(manual_db),
                "extreme_db_min_C": None,
                "temperature_basis": "User Defined Design Condition",
            }
        condition.setdefault("source", "ASHRAE_local_cache")
        condition.setdefault("lookup_provider", "ASHRAE_online")
        condition.setdefault("lookup_status", "success" if condition.get("source") == "ASHRAE_online" else "failed")
        condition.setdefault("failure_reason", "" if condition.get("source") == "ASHRAE_online" else "online lookup unavailable")
        condition.setdefault("station_name", "Unknown ASHRAE design station")
        condition.setdefault("station_id", "")
        condition.setdefault("station_distance_km", 0.0)
        condition.setdefault("temperature_basis", "ASHRAE_20_year_extreme_annual_design_condition")
        return condition

    if manual_db is not None:
        return {
            "source": "manual",
            "lookup_provider": "ASHRAE_online",
            "lookup_status": "failed",
            "failure_reason": "manual override selected",
            "station_name": "User Defined",
            "station_id": "",
            "station_distance_km": None,
            "station_latitude": None,
            "station_longitude": None,
            "design_db_max_C": float(manual_db),
            "extreme_db_max_C": float(manual_db),
            "extreme_db_min_C": None,
            "temperature_basis": "User Defined Design Condition",
        }

    if get_peak_design_condition is None:
        condition = {
            "source": "ASHRAE_local_cache",
            "lookup_provider": "ASHRAE_online",
            "lookup_status": "failed",
            "failure_reason": "online lookup module unavailable",
            "station_name": "WINSTON FIELD, TX, USA",
            "station_id": "722122",
            "station_distance_km": 0.0,
            "station_latitude": 32.693,
            "station_longitude": -100.951,
            "extreme_db_max_C": 44.0,
            "extreme_db_min_C": -16.9,
            "temperature_basis": "ASHRAE_20_year_extreme_annual_design_condition",
        }
    else:
        condition = get_peak_design_condition(
            latitude,
            longitude,
            source="ashrae_auto",
            endpoint=ashrae_endpoint,
        )
    condition = dict(condition or {})
    condition.setdefault("source", "ASHRAE_local_cache")
    condition.setdefault("lookup_provider", "ASHRAE_online")
    condition.setdefault("lookup_status", "success" if condition.get("source") == "ASHRAE_online" else "failed")
    condition.setdefault("failure_reason", "" if condition.get("source") == "ASHRAE_online" else "online lookup unavailable")
    condition.setdefault("station_name", "Unknown ASHRAE design station")
    condition.setdefault("station_id", "")
    condition.setdefault("station_distance_km", 0.0)
    condition.setdefault("temperature_basis", "ASHRAE_20_year_extreme_annual_design_condition")
    return condition

def _hour_of_day(hour_index, fallback_index):
    raw = _num(hour_index, fallback_index)
    return int(raw) % 24

def _is_daytime_hour(hour_of_day, start_hour, end_hour):
    if start_hour == end_hour:
        return False
    if start_hour < end_hour:
        return start_hour <= hour_of_day < end_hour
    return hour_of_day >= start_hour or hour_of_day < end_hour

def _solar_heat_gain_kw(ambient_c, annual_min_ambient_c, annual_max_ambient_c, hour_of_day, heat_gain_config):
    max_kw = heat_gain_config["solar_heat_gain_max_kW"]
    if max_kw <= 0:
        return 0.0
    if heat_gain_config.get("_force_solar_heat_gain_max"):
        return max_kw
    if not _is_daytime_hour(hour_of_day, heat_gain_config["solar_daytime_start_hour"], heat_gain_config["solar_daytime_end_hour"]):
        return 0.0
    if ambient_c is None or annual_min_ambient_c is None or annual_max_ambient_c is None:
        return 0.0
    ambient_range = annual_max_ambient_c - annual_min_ambient_c
    if ambient_range <= 0:
        normalized = 0.0
    else:
        normalized = _clamp((float(ambient_c) - annual_min_ambient_c) / ambient_range, 0.0, 1.0)
    return _clamp(max_kw * normalized * normalized, 0.0, max_kw)

def run_acc_v2_shadow(project_input, ambient_C, load_ratio, configuration_path=None, required_capacity_kW=None, nominal_unit_capacity_kW=None):
    """Run ACC V2 in isolated shadow mode; never modifies legacy calculations."""
    from acc_v2_engine import ACCV2ShadowResult, ENGINE_VERSION, is_acc_v2_enabled

    if not is_acc_v2_enabled(project_input):
        return None
    if configuration_path is None:
        configuration_path = _get(project_input, ["acc_v2", "configuration_path"])
    if configuration_path is None or ambient_C is None or load_ratio is None:
        return ACCV2ShadowResult(
            ambient_C=ambient_C,
            load_ratio=load_ratio,
            capacity_kW=None,
            power_input_kW=None,
            cop=None,
            lookup_success=False,
            validation_warnings=(),
            validation_errors=("ACC V2 shadow missing configuration_path, ambient_C, or load_ratio.",),
            engine_version=ENGINE_VERSION,
        )
    try:
        from acc_v2_engine import create_acc_v2_engine

        engine = create_acc_v2_engine(configuration_path)
        point = engine.evaluate_operating_point(
            ambient_C=ambient_C,
            load_ratio=load_ratio,
            required_capacity_kW=required_capacity_kW,
            nominal_unit_capacity_kW=nominal_unit_capacity_kW,
        )
        validation = engine.validation_summary
        return ACCV2ShadowResult(
            ambient_C=point.ambient_C,
            load_ratio=point.load_ratio,
            capacity_kW=point.capacity_kW,
            power_input_kW=point.power_input_kW,
            cop=point.cop,
            lookup_success=True,
            validation_warnings=tuple(validation.warnings),
            validation_errors=tuple(validation.errors),
            engine_version=ENGINE_VERSION,
            required_capacity_kW=point.required_capacity_kW,
            capacity_clamped=point.capacity_clamped,
        )
    except Exception as exc:
        return ACCV2ShadowResult(
            ambient_C=ambient_C,
            load_ratio=load_ratio,
            capacity_kW=None,
            power_input_kW=None,
            cop=None,
            lookup_success=False,
            validation_warnings=(),
            validation_errors=(f"ACC V2 shadow failed: {exc}",),
            engine_version=ENGINE_VERSION,
        )

def get_acc_operating_point(project_input, ambient_C=None, load_ratio=None, configuration_path=None):
    """Optional ACC V2 hook; disabled by default and not used by legacy formulas."""
    return run_acc_v2_shadow(project_input, ambient_C, load_ratio, configuration_path)

def resolve_acc_operating_point(
    project_input,
    acc_curve,
    load_ratio,
    cooling_load_kw,
    active_units,
    oat_c=None,
    configuration_path=None,
    acc_v2_engine=None,
    acc_v2_engine_error=None,
    required_capacity_per_unit_kw=None,
    nominal_unit_capacity_kw=None,
):
    """Resolve ACC operating point source with mandatory legacy fallback."""
    result, _temperature_power_factor = _resolve_acc_operating_point_for_solver(
        project_input,
        acc_curve,
        load_ratio,
        cooling_load_kw,
        active_units,
        oat_c,
        configuration_path,
        acc_v2_engine=acc_v2_engine,
        acc_v2_engine_error=acc_v2_engine_error,
        required_capacity_per_unit_kw=required_capacity_per_unit_kw,
        nominal_unit_capacity_kw=nominal_unit_capacity_kw,
    )
    return result

def _resolve_acc_operating_point_for_solver(
    project_input,
    acc_curve,
    load_ratio,
    cooling_load_kw,
    active_units,
    oat_c=None,
    configuration_path=None,
    acc_v2_engine=None,
    acc_v2_engine_error=None,
    required_capacity_per_unit_kw=None,
    nominal_unit_capacity_kw=None,
):
    from acc_v2_engine import ACCV2ProductionResult, ENGINE_VERSION, is_acc_v2_enabled

    legacy_power, legacy_cop, legacy_source, legacy_ambient, legacy_temperature_power_factor = _evaluate_acc_equipment_curve(
        acc_curve, load_ratio, cooling_load_kw, active_units, oat_c=oat_c
    )
    legacy_result = ACCV2ProductionResult(
        source=legacy_source,
        lookup_success=False,
        fallback_used=False,
        engine_version="legacy",
        ambient_C=legacy_ambient,
        load_ratio=load_ratio,
        capacity_kW=None,
        power_input_kW=legacy_power,
        cop=legacy_cop,
        diagnostics=None,
        required_capacity_kW=required_capacity_per_unit_kw,
        power_input_per_unit_kW=legacy_power / max(1, int(active_units)) if legacy_power is not None else None,
        capacity_clamped=False,
        diagnostic_load_ratio=load_ratio,
    )

    if not is_acc_v2_enabled(project_input):
        return legacy_result, legacy_temperature_power_factor
    if configuration_path is None:
        configuration_path = _get(project_input, ["acc_v2", "configuration_path"])
    if required_capacity_per_unit_kw is None and cooling_load_kw is not None:
        required_capacity_per_unit_kw = float(cooling_load_kw) / max(1, int(active_units))
    if configuration_path is None or oat_c is None or required_capacity_per_unit_kw is None:
        return _fallback_acc_v2_result(legacy_result), legacy_temperature_power_factor
    if acc_v2_engine_error is not None:
        return _fallback_acc_v2_result(legacy_result, diagnostics=str(acc_v2_engine_error)), legacy_temperature_power_factor
    try:
        engine = acc_v2_engine
        if engine is None:
            from acc_v2_engine import create_acc_v2_engine

            engine = create_acc_v2_engine(configuration_path)
        point = engine.evaluate_operating_point(
            ambient_C=oat_c,
            load_ratio=load_ratio,
            required_capacity_kW=required_capacity_per_unit_kw,
            nominal_unit_capacity_kW=nominal_unit_capacity_kw,
        )
        total_power_kw = point.power_input_kW * max(1, int(active_units))
        return ACCV2ProductionResult(
            source="acc_v2",
            lookup_success=True,
            fallback_used=False,
            engine_version=ENGINE_VERSION,
            ambient_C=point.ambient_C,
            load_ratio=point.load_ratio,
            capacity_kW=point.capacity_kW,
            power_input_kW=total_power_kw,
            cop=point.cop,
            diagnostics=None,
            required_capacity_kW=point.required_capacity_kW,
            power_input_per_unit_kW=point.power_input_kW,
            capacity_clamped=point.capacity_clamped,
            diagnostic_load_ratio=point.diagnostic_load_ratio,
        ), None
    except Exception as exc:
        return _fallback_acc_v2_result(legacy_result, diagnostics=str(exc)), legacy_temperature_power_factor

def _fallback_acc_v2_result(legacy_result, diagnostics=None):
    from acc_v2_engine import ACCV2ProductionResult

    return ACCV2ProductionResult(
        source=legacy_result.source,
        lookup_success=False,
        fallback_used=True,
        engine_version="legacy",
        ambient_C=legacy_result.ambient_C,
        load_ratio=legacy_result.load_ratio,
        capacity_kW=legacy_result.capacity_kW,
        power_input_kW=legacy_result.power_input_kW,
        cop=legacy_result.cop,
        diagnostics=diagnostics or getattr(legacy_result, "diagnostics", None),
        required_capacity_kW=getattr(legacy_result, "required_capacity_kW", None),
        power_input_per_unit_kW=getattr(legacy_result, "power_input_per_unit_kW", None),
        capacity_clamped=getattr(legacy_result, "capacity_clamped", False),
        diagnostic_load_ratio=getattr(legacy_result, "diagnostic_load_ratio", None),
    )

def _acc_direct_mode_diagnostics(input_obj, acc_operating_point=None):
    diagnostics = getattr(acc_operating_point, "diagnostics", None)
    if diagnostics:
        return diagnostics
    configuration_path = _get(input_obj, ["acc_v2", "configuration_path"]) or input_obj.get("configuration_path")
    if not configuration_path:
        return None
    try:
        from equipment_curve_reader import read_equipment_solver_curve

        preview = read_equipment_solver_curve(configuration_path, "ACC_2")
        metadata = getattr(preview, "metadata", {}) or {}
        diagnostics = metadata.get("diagnostics")
        if diagnostics:
            return diagnostics
    except Exception as exc:
        return f"ACC workbook diagnostics unavailable: {exc}"
    return None

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


def _library_fixed_power_per_unit(binding, load_ratio):
    """Evaluate a Phase 10B library fixed-power curve, returning kW/unit."""
    if not isinstance(binding, dict) or binding.get("enabled", True) is False:
        return 0.0
    rows = binding.get("curve_data", [])
    if not isinstance(rows, list):
        return 0.0
    points = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        x = _num(row.get("load_ratio"), None)
        y = _num(row.get("power_kW"), None)
        if x is not None and y is not None:
            points.append([x, y])
    if not points:
        return 0.0
    return max(0.0, float(eval_curve_1d(points, load_ratio, "linear")))


def _library_equipment_binding(bindings, candidate_ids):
    """Return a Configuration Library equipment binding by exact or prefix ID."""
    if not isinstance(bindings, dict):
        return None, None
    normalized_candidates = [str(item).upper() for item in candidate_ids]
    for equipment_id, binding in bindings.items():
        equipment_id_text = str(equipment_id)
        binding_equipment_id = str(binding.get("equipment_id")) if isinstance(binding, dict) else ""
        keys = [equipment_id_text.upper(), binding_equipment_id.upper()]
        if any(key in normalized_candidates for key in keys):
            return equipment_id_text, binding
    for equipment_id, binding in bindings.items():
        equipment_id_text = str(equipment_id).upper()
        binding_equipment_id = str(binding.get("equipment_id", "")).upper() if isinstance(binding, dict) else ""
        if any(equipment_id_text.startswith(prefix) or binding_equipment_id.startswith(prefix) for prefix in normalized_candidates):
            return str(equipment_id), binding
    return None, None


def _curve_from_library_binding(binding, curve_id):
    """Convert a loaded Configuration Library binding into a generic curve dict."""
    rows = binding.get("curve_data", []) if isinstance(binding, dict) else []
    return {
        "type": "1d_lookup_table",
        "x_axis": "load_ratio",
        "output": "power_kW",
        "interpolation": "linear",
        "data": rows if isinstance(rows, list) else [],
        "curve_id": curve_id,
    }


def _lookup_library_power_per_unit_with_engine(
    configuration_equipment_engines,
    equipment_id,
    binding,
    load_ratio,
    equipment_label,
    ambient_C=None,
):
    """Evaluate loaded Configuration Library load_ratio -> power_kW data through the generic engine."""
    if not isinstance(binding, dict):
        raise ValueError(f"{equipment_label} equipment binding is missing.")
    from equipment_engine import ConfigurationLibraryEquipmentEngine, EquipmentEngineConfig

    engine_equipment_id = binding.get("equipment_id") or equipment_id or equipment_label
    curve_id = f"{engine_equipment_id}_power_vs_load"
    engine_key = f"{equipment_label}:{engine_equipment_id}"
    if engine_key not in configuration_equipment_engines:
        configuration_equipment_engines[engine_key] = ConfigurationLibraryEquipmentEngine(
            EquipmentEngineConfig(
                preloaded_curves={
                    engine_equipment_id: _curve_from_library_binding(binding, curve_id)
                }
            )
        )
    lookup_result = configuration_equipment_engines[engine_key].lookup_power(
        engine_equipment_id,
        load_ratio,
        ambient_C=ambient_C,
    )
    if not lookup_result.lookup_success:
        raise ValueError("; ".join(lookup_result.errors) or f"{equipment_label} lookup failed.")
    return max(0.0, float(lookup_result.power_kW or 0.0))


def _electrical_efficiency_curve(equipment_id, path_name, efficiency):
    """Build a generic electrical efficiency curve from loaded equipment data."""
    curve_id = f"{equipment_id}_{path_name}_efficiency"
    return {
        "type": "1d_lookup_table",
        "x_axis": "load_ratio",
        "output": "efficiency",
        "interpolation": "linear",
        "data": [
            {"load_ratio": 0.0, "efficiency": efficiency},
            {"load_ratio": 1.0, "efficiency": efficiency},
        ],
        "curve_id": curve_id,
    }


def _evaluate_acc_equipment_curve(acc_curve, load_ratio, cooling_load_kw, active_units, oat_c=None):
    """Return ACC power/COP using ambient interpolation, with load-ratio fallback."""
    if not isinstance(acc_curve, dict) or not isinstance(acc_curve.get("data"), list):
        return None, None, "not_applied", None, None
    power_points = []
    cop_points = []
    ambient_power_points = []
    ambient_cop_points = []
    ambient_capacity_points = []
    power_field = None
    for row in acc_curve.get("data", []):
        if not isinstance(row, dict):
            continue
        x = _num(row.get("load_ratio"), None)
        if x is None:
            percent = _num(row.get("percent_load"), None)
            x = percent / 100.0 if percent is not None else None
        if x is None:
            continue
        power = _num(row.get("power_kW"), None)
        if power is not None:
            power_field = "power_kW"
        else:
            power = _num(row.get("power_input_kW"), None)
            if power is not None:
                power_field = "power_input_kW"
        cop_value = _num(row.get("COP"), None)
        if cop_value is None:
            cop_value = _num(row.get("unit_efficiency_COP"), None)
        if power is not None:
            power_points.append([x, power])
        if cop_value is not None:
            cop_points.append([x, cop_value])
        ambient = _num(row.get("ambient_C"), None)
        capacity = _num(row.get("capacity_kW"), None)
        if ambient is not None:
            if power is not None:
                ambient_power_points.append([ambient, power])
            if cop_value is not None:
                ambient_cop_points.append([ambient, cop_value])
            if capacity is not None:
                ambient_capacity_points.append([ambient, capacity])
    source_sheet = acc_curve.get("source_sheet") or "unknown"
    equipment_id = acc_curve.get("equipment_id") or "ACC"
    if oat_c is not None and ambient_power_points:
        ambient_power_points = _prep_points(ambient_power_points)
        interpolated_power = max(0.0, float(eval_curve_1d(ambient_power_points, oat_c, "linear")))
        design_power = ambient_power_points[-1][1]
        temperature_power_factor = interpolated_power / design_power if design_power > 0 else None
        ambient_cop = float(eval_curve_1d(ambient_cop_points, oat_c, "linear")) if ambient_cop_points else None
        if (ambient_cop is None or ambient_cop <= 0) and ambient_capacity_points and interpolated_power > 0:
            ambient_capacity = float(eval_curve_1d(ambient_capacity_points, oat_c, "linear"))
            ambient_cop = ambient_capacity / interpolated_power
        scenario_peak_power = _num(acc_curve.get("scenario_peak_acc_power_kw"), None)
        if scenario_peak_power is not None and scenario_peak_power >= 0 and temperature_power_factor is not None:
            total_power = float(scenario_peak_power) * temperature_power_factor
            power_method = "ambient_normalized_scenario_peak"
        else:
            total_power = interpolated_power * max(1, int(active_units))
            power_method = "ambient_power_input_kW"
        return total_power, ambient_cop, f"{equipment_id}:{source_sheet}:{power_method}", float(oat_c), temperature_power_factor

    curve_cop = float(eval_curve_1d(cop_points, load_ratio, "linear")) if cop_points else None
    if power_points:
        per_unit_power = max(0.0, float(eval_curve_1d(power_points, load_ratio, "linear")))
        total_power = per_unit_power * max(1, int(active_units))
        effective_cop = curve_cop if curve_cop is not None and curve_cop > 0 else (
            cooling_load_kw / total_power if total_power > 0 else None
        )
        return total_power, effective_cop, f"{equipment_id}:{source_sheet}:{power_field}", None, None
    if curve_cop is not None and curve_cop > 0:
        return cooling_load_kw / curve_cop, curve_cop, f"{equipment_id}:{source_sheet}:COP", None, None
    return None, None, f"{equipment_id}:{source_sheet}:missing_power_and_cop", None, None


def _evaluate_engine_curve(engine_curve, load_ratio, active_units):
    """Evaluate ENGINE_2 reporting values without changing facility PUE loads."""
    if not isinstance(engine_curve, dict) or not isinstance(engine_curve.get("data"), list):
        return 0.0, None, 0.0, 0.0, "not_applied"
    output_points = []
    efficiency_points = []
    fuel_points = []
    bsfc_points = []
    for row in engine_curve.get("data", []):
        if not isinstance(row, dict):
            continue
        x = _num(row.get("load_ratio"), None)
        output = _num(row.get("engine_output_kW"), None)
        efficiency = _num(row.get("engine_efficiency"), None)
        if efficiency is None:
            efficiency = _num(row.get("efficiency"), None)
        fuel_input = _num(row.get("fuel_input_kW"), None)
        if fuel_input is None:
            fuel_input = _num(row.get("fuel_rate_kW"), None)
        bsfc = _num(row.get("bsfc_g_per_kWh"), None)
        if bsfc is None:
            bsfc = _num(row.get("bsfc"), None)
        if x is None:
            continue
        if output is not None:
            output_points.append([x, output])
        if efficiency is not None:
            efficiency_points.append([x, efficiency])
        if fuel_input is not None:
            fuel_points.append([x, fuel_input])
        if bsfc is not None:
            bsfc_points.append([x, bsfc])
    if not output_points:
        return 0.0, None, 0.0, 0.0, "missing_engine_output"
    units = max(1, int(active_units))
    per_unit_output = max(0.0, float(eval_curve_1d(output_points, load_ratio, "linear")))
    total_output = per_unit_output * units
    source_sheet = engine_curve.get("source_sheet") or "unknown"
    equipment_id = engine_curve.get("equipment_id") or "ENGINE"
    if fuel_points:
        total_fuel = max(0.0, float(eval_curve_1d(fuel_points, load_ratio, "linear"))) * units
        efficiency = total_output / total_fuel if total_fuel > 0 else None
        source = "fuel_rate"
    elif bsfc_points:
        bsfc = max(0.0, float(eval_curve_1d(bsfc_points, load_ratio, "linear")))
        lhv_kwh_per_kg = _num(engine_curve.get("fuel_lhv_kWh_per_kg"), 13.1)
        total_fuel = total_output * (bsfc / 1000.0) * lhv_kwh_per_kg
        efficiency = total_output / total_fuel if total_fuel > 0 else None
        source = "bsfc"
    else:
        efficiency = float(eval_curve_1d(efficiency_points, load_ratio, "linear")) if efficiency_points else _num(engine_curve.get("default_efficiency"), 0.40)
        efficiency = _clamp(float(efficiency), 1e-6, 1.0)
        total_fuel = total_output / efficiency
        source = "efficiency_curve" if efficiency_points else str(engine_curve.get("default_efficiency_source") or "default_efficiency")
    waste_heat = max(0.0, total_fuel - total_output)
    return total_output, efficiency, total_fuel, waste_heat, f"{equipment_id}:{source_sheet}:{source}"


def _evaluate_engine_radiator_curve(radiator_curve, load_ratio, active_units, engine_waste_heat_kw):
    """Evaluate scenario radiator fan power when engine waste heat is present."""
    if engine_waste_heat_kw <= 0 or not isinstance(radiator_curve, dict):
        return 0.0, "not_applied"
    points = []
    power_field = None
    for row in radiator_curve.get("data", []) if isinstance(radiator_curve.get("data"), list) else []:
        if not isinstance(row, dict):
            continue
        x = _num(row.get("load_ratio"), None)
        power = _num(row.get("radiator_fan_power_kW"), None)
        if power is not None:
            power_field = "radiator_fan_power_kW"
        else:
            power = _num(row.get("power_kW"), None)
            if power is not None:
                power_field = "power_kW"
        if x is not None and power is not None:
            points.append([x, power])
    equipment_id = radiator_curve.get("equipment_id") or "ENGINE_RADIATOR"
    source_sheet = radiator_curve.get("source_sheet") or "unknown"
    if not points:
        return 0.0, f"{equipment_id}:{source_sheet}:missing_power"
    per_unit_power = max(0.0, float(eval_curve_1d(points, load_ratio, "linear")))
    return per_unit_power * max(1, int(active_units)), f"{equipment_id}:{source_sheet}:{power_field}"


def _max_acc_capacity_kw(acc_curve):
    """Return the maximum ACC capacity_kW available in a loaded ACC Solver_Curve."""
    if not isinstance(acc_curve, dict):
        return None
    capacities = []
    for row in acc_curve.get("data", []) if isinstance(acc_curve.get("data"), list) else []:
        if not isinstance(row, dict):
            continue
        capacity = _num(row.get("capacity_kW"), None)
        if capacity is None:
            capacity = _num(row.get("capacity_kw"), None)
        if capacity is not None and capacity > 0:
            capacities.append(float(capacity))
    return max(capacities) if capacities else None


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
    other_electrical_auxiliary_power_kw = _num(aux_cfg.get("other_electrical_auxiliary_power_kW"), None)
    if other_electrical_auxiliary_power_kw is None:
        other_electrical_auxiliary_power_kw = _num(aux_cfg.get("other_electrical_auxiliary_power_kw"), None)
    if other_electrical_auxiliary_power_kw is None:
        other_electrical_auxiliary_power_kw = 0.0
    other_electrical_auxiliary_power_kw = max(0.0, float(other_electrical_auxiliary_power_kw))

    # Optional terminal-to-upstream electrical path efficiencies. When absent,
    # retain the legacy UPS/transformer curve loss calculation unchanged.
    electrical_path = input_obj.get("electrical_path", {}) if isinstance(input_obj.get("electrical_path", {}), dict) else {}
    if not electrical_path:
        electrical_path = _get(input_obj, ["equipment", "electrical_path"], {})
    if not isinstance(electrical_path, dict):
        electrical_path = {}
    it_path_efficiency = _num(electrical_path.get("it_efficiency"), None)
    mep_path_efficiency = _num(electrical_path.get("mep_efficiency"), None)
    electrical_path_enabled = (
        it_path_efficiency is not None and 0.0 < it_path_efficiency <= 1.0
        and mep_path_efficiency is not None and 0.0 < mep_path_efficiency <= 1.0
    )

    cooling_cfg = _get(input_obj, ["equipment", "cooling"], {})
    if not isinstance(cooling_cfg, dict):
        cooling_cfg = {}
    cooling_unit_capacity_kw = _num(cooling_cfg.get("cooling_unit_capacity_kW"), None)
    if cooling_unit_capacity_kw is None:
        cooling_unit_capacity_kw = _num(cooling_cfg.get("cooling_unit_capacity_kw"), None)
    if cooling_unit_capacity_kw is None:
        cooling_unit_capacity_kw = _num(_get(input_obj, ["project", "it_load", "cooling_unit_capacity_kW"], None), None)
    if cooling_unit_capacity_kw is None:
        cooling_unit_capacity_kw = 2000.0
    cooling_unit_count = _num(cooling_cfg.get("cooling_unit_count"), None)
    if cooling_unit_count is None:
        cooling_unit_count = _num(_get(input_obj, ["project", "it_load", "cooling_unit_count"], None), None)
    if cooling_unit_count is None:
        cooling_unit_count = ceil(float(design_it_load or 0.0) / cooling_unit_capacity_kw) if cooling_unit_capacity_kw > 0 else 1
    cooling_unit_count = max(1, int(ceil(float(cooling_unit_count))))
    library_active_units = _num(project.get("active_units"), cooling_unit_count)
    library_active_units = max(1, int(ceil(float(library_active_units))))
    indoor_active_units = _num(project.get("indoor_active_units"), library_active_units)
    indoor_active_units = max(1, int(ceil(float(indoor_active_units))))
    library_fixed_power = _get(input_obj, ["equipment", "library_fixed_power"], {})
    if not isinstance(library_fixed_power, dict) or not library_fixed_power:
        library_fixed_power = _get(input_obj, ["library_context", "auxiliary_equipment"], {})
    if not isinstance(library_fixed_power, dict):
        library_fixed_power = {}
    acc_curve = input_obj.get("acc_curve", {}) if isinstance(input_obj.get("acc_curve", {}), dict) else {}
    if not acc_curve:
        acc_curve = _get(input_obj, ["library_context", "acc_curve"], {})
    if not isinstance(acc_curve, dict):
        acc_curve = {}
    engine_curve = input_obj.get("engine_curve", {}) if isinstance(input_obj.get("engine_curve", {}), dict) else {}
    engine_radiator_curve = input_obj.get("engine_radiator_curve", {}) if isinstance(input_obj.get("engine_radiator_curve", {}), dict) else {}

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
        dry_cooler_rated_power_kw = 0.03 * float(cooling_unit_capacity_kw or 0.0)
    dry_cooler_heat_rejection_capacity_kw = _num(dry_cooler_cfg.get("heat_rejection_capacity_kW"), None)
    if dry_cooler_heat_rejection_capacity_kw is None:
        dry_cooler_heat_rejection_capacity_kw = _num(dry_cooler_cfg.get("heat_rejection_capacity_kw"), None)
    if dry_cooler_heat_rejection_capacity_kw is None:
        dry_cooler_heat_rejection_capacity_kw = 2000.0
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
        pump_curve_refs = []
        for name in raw_curve_names:
            raw_curve = curve_lib.get("raw_curves", {}).get(name, {}) if isinstance(curve_lib, dict) else {}
            output_name = str(raw_curve.get("output", "")).lower() if isinstance(raw_curve, dict) else ""
            curve_name = str(name).lower()
            if "pump_power_vs_it_load" in curve_name or ("pump" in curve_name and ("power" in output_name or "kw" in output_name)):
                pump_curve_refs.append(name)
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
    configuration_library_direct_mode = (
        isinstance(input_obj.get("library_context"), dict)
        or isinstance(input_obj.get("configuration_library"), dict)
    )

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
                "chiller_power_kW": out.get("_breakdown_v04", {}).get("chiller_kw", 0.0),
                "cooling_power_kW": out.get("_breakdown_v04", {}).get("cooling_kw", 0.0),
                "pump_power_kW": out.get("_breakdown_v04", {}).get("pumps_kw", 0.0),
                "pumps_kw": out.get("_breakdown_v04", {}).get("pumps_kw", 0.0),
                "airflow_power_kW": out.get("_breakdown_v04", {}).get("airflow_kw", 0.0),
                "electrical_loss_kW": out.get("_breakdown_v04", {}).get("power_distribution_loss_kw"),
                "auxiliary_power_kW": out.get("_breakdown_v04", {}).get("aux_kw", 0.0) + out.get("_breakdown_v04", {}).get("other_kw", 0.0),
                "total_facility_power_kW": out.get("power", {}).get("total_facility_power_kw"),
                "hourly_PUE": out.get("power", {}).get("pue_instant")
            }
        ]
        it_energy = it_kw
        facility_energy = out.get("power", {}).get("total_facility_power_kw", 0.0)
        cooling_energy = out.get("_breakdown_v04", {}).get("cooling_kw", 0.0)
        chiller_energy = out.get("_breakdown_v04", {}).get("chiller_kw", 0.0)
        dry_cooler_energy = 0.0
        pump_energy = out.get("_breakdown_v04", {}).get("pumps_kw", 0.0)
        terminal_fan_energy = out.get("_breakdown_v04", {}).get("airflow_kw", 0.0)
        electrical_loss_energy = out.get("_breakdown_v04", {}).get("power_distribution_loss_kw", 0.0)
        auxiliary_energy = out.get("_breakdown_v04", {}).get("aux_kw", 0.0) + out.get("_breakdown_v04", {}).get("other_kw", 0.0)
        annual_pue = facility_energy / it_energy if it_energy > 0 else None
        result["annual_results"] = {
            "annual_average_PUE": annual_pue,
            "annual_IT_energy_kWh": it_energy,
            "annual_it_energy_kWh": it_energy,
            "annual_facility_energy_kWh": facility_energy,
            # Current cooling_kw is chiller + dry cooler only; keep legacy key for compatibility.
            "annual_cooling_energy_kWh": cooling_energy,
            "annual_chiller_plus_dry_cooler_energy_kWh": cooling_energy,
            "annual_total_cooling_system_energy_kWh": chiller_energy + dry_cooler_energy + pump_energy + terminal_fan_energy,
            "annual_dry_cooler_fan_energy_kWh": 0.0,
            "average_dry_cooler_fan_power_kW": 0.0,
            "max_dry_cooler_fan_power_kW": 0.0,
            "dry_cooler_pue_contribution": 0.0,
            "dry_cooler_over_capacity_hours": 0,
            "dry_cooler_max_heat_rejection_kW": None,
            "dry_cooler_max_load_ratio_raw": None,
            "annual_pump_energy_kWh": pump_energy,
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
    dry_cooler_over_capacity_count = 0
    configuration_equipment_engines = {}
    heat_gain_config = _heat_gain_inputs(input_obj)
    dry_values = [_num(value, None) for value in dry_bulb]
    dry_values = [value for value in dry_values if value is not None]
    annual_min_ambient_c = min(dry_values) if dry_values else None
    annual_max_ambient_c = max(dry_values) if dry_values else None
    acc_v2_engine = input_obj.get("_acc_v2_engine_override")
    acc_v2_engine_error = None
    acc_v2_direct_mode_enabled = False
    acc_v2_configuration_path = _get(input_obj, ["acc_v2", "configuration_path"])
    try:
        from acc_v2_engine import create_acc_v2_engine, is_acc_v2_enabled

        acc_v2_direct_mode_enabled = is_acc_v2_enabled(input_obj)
        if acc_v2_engine is None and acc_v2_direct_mode_enabled and acc_v2_configuration_path is not None:
            acc_v2_engine = create_acc_v2_engine(acc_v2_configuration_path)
    except Exception as exc:
        acc_v2_engine_error = str(exc)
    peak_design_cooling_load_kw = (
        float(design_it_load or 0.0)
        + heat_gain_config["solar_heat_gain_max_kW"]
        + heat_gain_config["other_auxiliary_heat_gain_kW"]
    )
    peak_design_required_capacity_per_acc_unit_kw = (
        peak_design_cooling_load_kw / max(1, int(library_active_units))
        if peak_design_cooling_load_kw > 0
        else None
    )
    acc_v2_pump_capacity_warning = None
    if configuration_library_direct_mode and acc_v2_direct_mode_enabled and not (
        peak_design_required_capacity_per_acc_unit_kw is not None
        and peak_design_required_capacity_per_acc_unit_kw > 0
    ):
        acc_v2_pump_capacity_warning = (
            "Peak design required capacity per ACC unit unavailable; "
            "CHW Pump load ratio fell back to existing unit_load_ratio basis."
        )
        validation.setdefault("warnings", []).append(acc_v2_pump_capacity_warning)
    for i in range(n):
        it_kw = _num(hourly_it_load[i], 0.0) if i < len(hourly_it_load) else 0.0
        oat_c = _num(dry_bulb[i], None)
        wet_c = _num(wet_bulb[i], None) if i < len(wet_bulb) else None
        rh_val = _num(rel_humidity[i], None) if i < len(rel_humidity) else None
        idx = hour_index[i] if i < len(hour_index) else i
        hour_of_day = _hour_of_day(idx, i)

        load_ratio = (it_kw / design_it_load) if design_it_load and design_it_load > 0 else 0.0
        load_ratio = _clamp(load_ratio, 0.0, 1.0)
        project_load_ratio = load_ratio
        solar_heat_gain_kw = _solar_heat_gain_kw(
            oat_c,
            annual_min_ambient_c,
            annual_max_ambient_c,
            hour_of_day,
            heat_gain_config,
        )
        other_auxiliary_heat_gain_kw = heat_gain_config["other_auxiliary_heat_gain_kW"]
        cooling_load_kw = it_kw + solar_heat_gain_kw + other_auxiliary_heat_gain_kw
        cooling_unit_total_capacity_kw = cooling_unit_count * cooling_unit_capacity_kw
        unit_load_ratio_raw = (
            it_kw / cooling_unit_total_capacity_kw
            if cooling_unit_total_capacity_kw and cooling_unit_total_capacity_kw > 0
            else 0.0
        )
        unit_load_ratio = _clamp(unit_load_ratio_raw, 0.0, 1.0)
        acc_active_capacity_kw = library_active_units * cooling_unit_capacity_kw
        acc_capacity_load_ratio_raw = (
            cooling_load_kw / acc_active_capacity_kw
            if acc_active_capacity_kw and acc_active_capacity_kw > 0
            else 0.0
        )
        acc_capacity_load_ratio = _clamp(acc_capacity_load_ratio_raw, 0.0, 1.0)
        acc_required_capacity_per_unit_kw = cooling_load_kw / max(1, int(library_active_units))

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
        pump_load_ratio = unit_load_ratio
        chw_pump_load_ratio_basis = "unit_load_ratio"
        chw_pump_reference_capacity_kw = None
        chw_pump_load_ratio_warning = None
        if configuration_library_direct_mode and acc_v2_direct_mode_enabled:
            if (
                peak_design_required_capacity_per_acc_unit_kw is not None
                and peak_design_required_capacity_per_acc_unit_kw > 0
            ):
                pump_load_ratio = _clamp(
                    acc_required_capacity_per_unit_kw / peak_design_required_capacity_per_acc_unit_kw,
                    0.0,
                    1.0,
                )
                chw_pump_load_ratio_basis = "design_required_capacity_per_acc_unit"
                chw_pump_reference_capacity_kw = peak_design_required_capacity_per_acc_unit_kw
            else:
                chw_pump_load_ratio_warning = acc_v2_pump_capacity_warning
        chw_pump_power_per_unit_kw = 0.0
        cw_pump_power_per_unit_kw = 0.0
        pump_power_per_unit_kw = 0.0
        pump_power_total_check = True
        chw_pump_curve_source = "legacy_non_configuration_mode"
        configuration_library_chw_pump_requested = False
        configuration_library_chw_pump_error = None
        pump_debug_rows = []
        if pumps_enabled and pump_curve_refs:
            pump_values_per_unit = []
            for pump_ref in pump_curve_refs:
                pump_curve_value = None
                pump_curve_load_value = pump_load_ratio
                pump_source = "curve_missing"
                pump_ref_text = str(pump_ref)
                source_equipment_id = str(pumps_cfg.get("source_equipment_id") or "")
                is_configuration_library_chw_pump = (
                    "CHW_PUMP_2" in pump_ref_text.upper()
                    or source_equipment_id.upper() == "CHW_PUMP_2"
                )
                if is_configuration_library_chw_pump:
                    configuration_library_chw_pump_requested = True
                raw_curve = curve_lib.get("raw_curves", {}).get(str(pump_ref), {}) if isinstance(curve_lib, dict) else {}
                if is_configuration_library_chw_pump:
                    try:
                        from equipment_engine import ConfigurationLibraryEquipmentEngine, EquipmentEngineConfig

                        equipment_engine_id = source_equipment_id or "CHW_PUMP_2"
                        if equipment_engine_id not in configuration_equipment_engines:
                            configuration_equipment_engines[equipment_engine_id] = ConfigurationLibraryEquipmentEngine(
                                EquipmentEngineConfig(preloaded_curves={equipment_engine_id: raw_curve})
                            )
                        lookup_result = configuration_equipment_engines[equipment_engine_id].lookup_power(
                            equipment_engine_id,
                            pump_curve_load_value,
                        )
                        if not lookup_result.lookup_success:
                            raise ValueError("; ".join(lookup_result.errors) or "CHW_PUMP_2 lookup failed.")
                        pump_curve_load_value = lookup_result.load_ratio
                        pump_curve_value = lookup_result.power_kW
                        pump_source = "configuration_library_solver_curve"
                    except Exception as exc:
                        configuration_library_chw_pump_error = str(exc)
                        pump_curve_value = None
                elif isinstance(raw_curve, dict) and str(raw_curve.get("type", "")).lower() == "1d_lookup_table":
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
                        if max_x > 2.0 and pump_load_ratio <= 1.0:
                            pump_curve_load_value = pump_load_ratio * 100.0
                        pump_curve_value = _num(eval_curve_1d(pts, pump_curve_load_value, raw_curve.get("interpolation", "linear")), None)
                        pump_source = "raw_points"
                if pump_curve_value is None and not is_configuration_library_chw_pump:
                    pump_curve_value = _curve_value(curve_lib, str(pump_ref), pump_curve_load_value, None)
                    if pump_curve_value is not None:
                        pump_source = "curve_value"
                if pump_curve_value is None:
                    continue
                output_name = str(raw_curve.get("output", "")).lower() if isinstance(raw_curve, dict) else ""
                if pump_source == "configuration_library_solver_curve" or "kw" in output_name or "power_kw" in output_name:
                    pump_kw = max(0.0, float(pump_curve_value))
                    pump_source = (
                        "configuration_library_solver_curve"
                        if is_configuration_library_chw_pump
                        else f"{pump_source}_power_kw_direct"
                    )
                else:
                    rated_each = (0.01 * float(cooling_unit_capacity_kw or 0.0)) / max(len(pump_curve_refs), 1)
                    pump_kw = max(0.0, float(pump_curve_value) * rated_each)
                    pump_source = f"{pump_source}_power_factor_times_rated"
                if pump_source == "configuration_library_solver_curve":
                    chw_pump_curve_source = "configuration_library_solver_curve"
                pump_values_per_unit.append(pump_kw)
                pump_ref_lower = str(pump_ref).lower()
                if "chw" in pump_ref_lower:
                    chw_pump_power_per_unit_kw += pump_kw
                elif "cw" in pump_ref_lower:
                    cw_pump_power_per_unit_kw += pump_kw
                pump_debug_rows.append({
                    "curve_ref": str(pump_ref),
                    "source": pump_source,
                    "load_ratio": pump_curve_load_value,
                    "curve_value": pump_curve_value,
                    "power_per_unit_kW": pump_kw,
                    "total_power_kW": pump_kw * cooling_unit_count
                })
            if pump_values_per_unit:
                pump_power_per_unit_kw = sum(pump_values_per_unit)
                pumps_kw = pump_power_per_unit_kw * cooling_unit_count
                pump_power_total_check = abs((pump_power_per_unit_kw * cooling_unit_count) - pumps_kw) <= 1e-9
        if (
            configuration_library_direct_mode
            and pumps_enabled
            and (
                configuration_library_chw_pump_requested
                or str(pumps_cfg.get("source_equipment_id") or "").upper() == "CHW_PUMP_2"
            )
            and chw_pump_curve_source != "configuration_library_solver_curve"
        ):
            reason = configuration_library_chw_pump_error or "CHW_PUMP_2 curve reference is missing or produced no valid operating point."
            error_message = (
                "CHW_PUMP_2 Solver_Curve missing or invalid. Configuration Library direct mode "
                "requires CHW_PUMP_2 load_ratio \u2192 power_kW data. "
                f"Reason: {reason}"
            )
            validation.setdefault("errors", []).append(error_message)
            result["validation"] = validation
            result["error"] = error_message
            return result
        airflow_kw = 0.0 if configuration_library_direct_mode else 0.02 * it_kw
        fan_curve_value = None
        fan_curve_load_value = load_ratio
        fan_power_source = "configuration_library_solver_curve" if configuration_library_direct_mode else ("disabled" if not fans_enabled else "curve_missing")
        terminal_fan_excluded_due_to_mau_curve = False
        if not configuration_library_direct_mode and fans_enabled and fan_curve_ref:
            raw_curve = curve_lib.get("raw_curves", {}).get(fan_curve_ref, {}) if isinstance(curve_lib, dict) else {}
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
                        fan_curve_load_value = load_ratio * 100.0
                    fan_curve_value = _num(eval_curve_1d(pts, fan_curve_load_value, raw_curve.get("interpolation", "linear")), None)
                    fan_power_source = "raw_points"
            if fan_curve_value is None:
                fan_curve_value = _curve_value(curve_lib, fan_curve_ref, fan_curve_load_value, None)
                if fan_curve_value is not None:
                    fan_power_source = "curve_value"
            if fan_curve_value is not None:
                raw_curve = curve_lib.get("raw_curves", {}).get(fan_curve_ref, {}) if isinstance(curve_lib, dict) else {}
                output_name = str(raw_curve.get("output", "")).lower() if isinstance(raw_curve, dict) else ""
                fan_value = float(fan_curve_value)
                rated_fan_kw = float(fan_rated_power_kw or 0.0)
                if "kw" in output_name or "power_kw" in output_name:
                    if rated_fan_kw > 0.0 and fan_value > rated_fan_kw * 2.0:
                        airflow_kw = max(0.0, fan_value / 100.0 * rated_fan_kw)
                        fan_power_source = f"{fan_power_source}_power_percent_times_rated"
                    else:
                        airflow_kw = max(0.0, fan_value)
                        fan_power_source = f"{fan_power_source}_power_kw_direct"
                else:
                    if fan_value > 2.0:
                        airflow_kw = max(0.0, fan_value / 100.0 * rated_fan_kw)
                        fan_power_source = f"{fan_power_source}_power_percent_times_rated"
                    else:
                        airflow_kw = max(0.0, fan_value * rated_fan_kw)
                        fan_power_source = f"{fan_power_source}_power_factor_times_rated"
        if configuration_library_direct_mode:
            aux_kw = other_electrical_auxiliary_power_kw
            auxiliary_power_source = "manual_input"
        else:
            aux_kw = aux_coeff * it_kw
            auxiliary_power_source = "coefficient"
        other_kw = 0.0

        dry_cooler_kw = 0.0
        dry_cooler_power_per_unit_kw = 0.0
        dry_curve_value = None
        dry_curve_load_value = unit_load_ratio
        heat_rejection_to_dry_cooler_kw = None
        heat_rejection_per_dry_cooler_unit_kw = None
        dry_cooler_load_kw = None
        facility_load_kw = it_kw + pumps_kw + airflow_kw + aux_kw + other_kw
        dry_cooler_load_ratio_raw = None
        dry_cooler_load_ratio = None
        dry_cooler_capacity_warning = None
        dry_cooler_power_source = "no_curve"

        condenser_entering_water_source = "unavailable"
        condenser_entering_water_c = None
        if oat_c is not None:
            condenser_entering_water_c = float(oat_c) + float(dry_cooler_approach_c)
            condenser_entering_water_source = "outdoor_dry_bulb_plus_approach"

        # Thermal cooling load from IT heat sources
        it_heat_load = it_kw  # Simplified - IT heat load equals IT power
        pumps_heat = pumps_kw
        airflow_heat = airflow_kw
        other_heat = aux_kw + other_kw
        total_thermal_load = it_heat_load + pumps_heat + airflow_heat + other_heat

        # Cooling power calculation using COP curve
        cop_load_value = unit_load_ratio
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
        if cop_uses_percent_load and unit_load_ratio <= 1.0:
            cop_load_value = unit_load_ratio * 100.0

        cop_surface_x_min = None
        cop_surface_x_max = None
        cop_lookup_x = condenser_entering_water_c
        cop_lookup_y = cop_load_value
        cop_x_values = []
        if isinstance(raw_chiller_curve, dict) and str(raw_chiller_curve.get("type", "")).lower() == "2d_lookup_table":
            raw_points_for_debug = raw_chiller_curve.get("points")
            if not isinstance(raw_points_for_debug, list):
                raw_points_for_debug = raw_chiller_curve.get("data", [])
            x_axis_for_debug = raw_chiller_curve.get("x_axis")
            for point in raw_points_for_debug if isinstance(raw_points_for_debug, list) else []:
                if isinstance(point, dict):
                    x_item = _num(point.get(x_axis_for_debug), None)
                elif isinstance(point, (list, tuple)) and len(point) >= 1:
                    x_item = _num(point[0], None)
                else:
                    x_item = None
                if x_item is not None:
                    cop_x_values.append(x_item)
        if not cop_x_values:
            cop_surfaces = curve_lib.get("cop_surfaces", {}) if isinstance(curve_lib, dict) else {}
            surface = cop_surfaces.get(chiller_curve_ref) if isinstance(cop_surfaces, dict) else None
            if isinstance(surface, dict):
                for slice_item in surface.get("oat_slices", []) if isinstance(surface.get("oat_slices", []), list) else []:
                    if isinstance(slice_item, dict):
                        x_item = _num(slice_item.get("oat_c"), None)
                        if x_item is not None:
                            cop_x_values.append(x_item)
        if cop_x_values:
            cop_surface_x_min = min(cop_x_values)
            cop_surface_x_max = max(cop_x_values)
            if condenser_entering_water_c is not None:
                cop_lookup_x = _clamp(float(condenser_entering_water_c), cop_surface_x_min, cop_surface_x_max)

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
        acc_operating_point, acc_temperature_power_factor = _resolve_acc_operating_point_for_solver(
            input_obj,
            acc_curve,
            acc_capacity_load_ratio,
            cooling_load_kw,
            library_active_units,
            oat_c=oat_c,
            acc_v2_engine=acc_v2_engine,
            acc_v2_engine_error=acc_v2_engine_error,
            required_capacity_per_unit_kw=acc_required_capacity_per_unit_kw,
            nominal_unit_capacity_kw=cooling_unit_capacity_kw,
        )
        acc_power_kw = acc_operating_point.power_input_kW
        acc_cop = acc_operating_point.cop
        acc_curve_source = acc_operating_point.source
        acc_ambient_c = acc_operating_point.ambient_C
        acc_power_input_per_unit_kw = getattr(acc_operating_point, "power_input_per_unit_kW", None)
        acc_capacity_clamped = bool(getattr(acc_operating_point, "capacity_clamped", False))
        acc_diagnostic_load_ratio = getattr(acc_operating_point, "diagnostic_load_ratio", acc_capacity_load_ratio)
        if configuration_library_direct_mode:
            if getattr(acc_operating_point, "fallback_used", False):
                error_message = (
                    "ACC Solver_Curve missing or invalid. Configuration Library direct mode "
                    "requires ACC Solver_Curve data and does not allow ACC legacy fallback."
                )
                acc_diagnostics = _acc_direct_mode_diagnostics(input_obj, acc_operating_point)
                if acc_diagnostics:
                    error_message = f"{error_message}\n{acc_diagnostics}"
                validation.setdefault("errors", []).append(error_message)
                result["validation"] = validation
                result["error"] = error_message
                return result
            if acc_power_kw is None:
                error_message = (
                    "ACC Solver_Curve missing or invalid. Configuration Library direct mode "
                    "requires ACC load_ratio and/or ambient Solver_Curve power data."
                )
                acc_diagnostics = _acc_direct_mode_diagnostics(input_obj, acc_operating_point)
                if acc_diagnostics:
                    error_message = f"{error_message}\n{acc_diagnostics}"
                validation.setdefault("errors", []).append(error_message)
                result["validation"] = validation
                result["error"] = error_message
                return result
            if acc_curve_source == "acc_v2":
                acc_curve_source = "acc_v2_solver_curve_direct"
            else:
                acc_curve_source = "configuration_library_solver_curve"
        if acc_power_kw is not None:
            chiller_kw = acc_power_kw
            cop = acc_cop
        heat_rejection_to_dry_cooler_kw = it_kw
        heat_rejection_per_dry_cooler_unit_kw = heat_rejection_to_dry_cooler_kw / cooling_unit_count if cooling_unit_count > 0 else heat_rejection_to_dry_cooler_kw
        dry_cooler_load_kw = heat_rejection_to_dry_cooler_kw
        dry_cooler_load_ratio_raw = unit_load_ratio_raw
        if dry_cooler_load_ratio_raw is not None:
            if dry_cooler_load_ratio_raw > 1.0:
                dry_cooler_over_capacity_count += 1
                dry_cooler_capacity_warning = (
                    "Dry cooler unit load exceeds installed cooling unit capacity. "
                    f"Project load {heat_rejection_to_dry_cooler_kw:.2f} kW; "
                    f"installed capacity {cooling_unit_total_capacity_kw:.2f} kW."
                )
            dry_cooler_load_ratio = min(dry_cooler_load_ratio_raw, 1.0)
            dry_curve_load_value = dry_cooler_load_ratio

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
                    lookup_x = dry_curve_load_value
                    if max_x > 2.0 and lookup_x <= 1.0:
                        lookup_x = lookup_x * 100.0
                    dry_curve_load_value = lookup_x
                    dry_curve_value = _num(eval_curve_1d(pts, dry_curve_load_value, raw_curve.get("interpolation", "linear")), None)
                    dry_cooler_power_source = "raw_points"
            if dry_curve_value is None:
                dry_curve_value = _curve_value(curve_lib, dry_cooler_curve_ref, dry_curve_load_value, None)
                if dry_curve_value is not None:
                    dry_cooler_power_source = "curve_value"
            if dry_curve_value is not None:
                output_name = str(raw_curve.get("output", "")).lower() if isinstance(raw_curve, dict) else ""
                if "kw" in output_name or "power_kw" in output_name:
                    dry_cooler_power_per_unit_kw = max(0.0, float(dry_curve_value))
                    dry_cooler_kw = dry_cooler_power_per_unit_kw * cooling_unit_count
                    dry_cooler_power_source = f"{dry_cooler_power_source}_fan_power_kw_direct"
                else:
                    dry_cooler_power_per_unit_kw = max(0.0, float(dry_curve_value) * float(dry_cooler_rated_power_kw or 0.0))
                    dry_cooler_kw = dry_cooler_power_per_unit_kw * cooling_unit_count
                    dry_cooler_power_source = f"{dry_cooler_power_source}_fan_power_factor_times_rated"
        cooling_kw = chiller_kw + dry_cooler_kw

        # Optional Configuration Library fixed-power white-space equipment.
        # These are MEP terminal loads and do not alter legacy auxiliary logic.
        cdu_curve_source = "legacy_non_configuration_mode"
        rtc_curve_source = "legacy_non_configuration_mode"
        mau_curve_source = "legacy_non_configuration_mode"
        cdu_power_kw = 0.0
        rtc_power_kw = 0.0
        mau_power_kw = 0.0
        cdu_equipment_id, cdu_binding = _library_equipment_binding(library_fixed_power, ("CDU_2", "CDU"))
        rtc_equipment_id, rtc_binding = _library_equipment_binding(library_fixed_power, ("RTC_1&2", "RTC_2", "RTC"))
        mau_equipment_id, mau_binding = _library_equipment_binding(library_fixed_power, ("MAU_1&2", "MAU_2", "MAU"))
        if configuration_library_direct_mode:
            for label, display_id, equipment_id, binding in (
                ("cdu", "CDU_2", cdu_equipment_id, cdu_binding),
                ("rtc", "RTC_1&2", rtc_equipment_id, rtc_binding),
                ("mau", "MAU_1&2", mau_equipment_id, mau_binding),
            ):
                try:
                    power_per_unit = _lookup_library_power_per_unit_with_engine(
                        configuration_equipment_engines,
                        equipment_id or display_id,
                        binding,
                        project_load_ratio,
                        label,
                    )
                    if label == "cdu":
                        cdu_power_kw = power_per_unit * indoor_active_units
                        cdu_curve_source = "configuration_library_solver_curve"
                    elif label == "rtc":
                        rtc_power_kw = power_per_unit * indoor_active_units
                        rtc_curve_source = "configuration_library_solver_curve"
                    else:
                        mau_power_kw = power_per_unit * indoor_active_units
                        mau_curve_source = "configuration_library_solver_curve"
                except Exception as exc:
                    error_message = (
                        f"{display_id} Solver_Curve missing or invalid. Configuration Library direct mode "
                        f"requires {display_id} load_ratio \u2192 power_kW data. "
                        f"Reason: {exc}"
                    )
                    validation.setdefault("errors", []).append(error_message)
                    result["validation"] = validation
                    result["error"] = error_message
                    return result
        else:
            cdu_power_kw = _library_fixed_power_per_unit(cdu_binding, project_load_ratio) * indoor_active_units
            rtc_power_kw = _library_fixed_power_per_unit(rtc_binding, project_load_ratio) * indoor_active_units
            mau_power_kw = _library_fixed_power_per_unit(mau_binding, project_load_ratio) * indoor_active_units
        white_space_equipment_power_kw = cdu_power_kw + rtc_power_kw + mau_power_kw
        if configuration_library_direct_mode:
            airflow_kw = 0.0
            fan_curve_value = 0.0
            fan_power_source = "configuration_library_mau_curve_excluded_to_avoid_duplicate"
            terminal_fan_excluded_due_to_mau_curve = mau_power_kw > 0.0
        engine_curve_type = None
        engine_radiator_curve_type = None
        if configuration_library_direct_mode:
            try:
                engine_binding = {
                    "equipment_id": "ENGINE_3",
                    "curve_data": engine_curve.get("data", []) if isinstance(engine_curve, dict) else [],
                }
                engine_power_per_unit = _lookup_library_power_per_unit_with_engine(
                    configuration_equipment_engines,
                    "ENGINE_3",
                    engine_binding,
                    project_load_ratio,
                    "engine",
                )
                engine_output_kw = engine_power_per_unit * library_active_units
                efficiency_points = []
                for row in engine_binding["curve_data"]:
                    if not isinstance(row, dict):
                        continue
                    x = _num(row.get("load_ratio"), None)
                    efficiency = _num(row.get("engine_efficiency"), None)
                    if efficiency is None:
                        efficiency = _num(row.get("efficiency"), None)
                    if x is not None and efficiency is not None:
                        efficiency_points.append([x, efficiency])
                if efficiency_points:
                    engine_efficiency = float(eval_curve_1d(efficiency_points, project_load_ratio, "linear"))
                else:
                    engine_efficiency = _num(engine_curve.get("default_efficiency") if isinstance(engine_curve, dict) else None, 0.40)
                engine_efficiency = _clamp(float(engine_efficiency), 1e-6, 1.0)
                engine_fuel_input_kw = engine_output_kw / engine_efficiency
                engine_waste_heat_kw = max(0.0, engine_fuel_input_kw - engine_output_kw)
                engine_curve_source = "configuration_library_solver_curve"
                engine_curve_type = "one_dimensional_power"
            except Exception as exc:
                error_message = (
                    "ENGINE_3 Solver_Curve missing or invalid. Configuration Library direct mode "
                    f"requires ENGINE_3 load_ratio \u2192 power_kW data. Reason: {exc}"
                )
                validation.setdefault("errors", []).append(error_message)
                result["validation"] = validation
                result["error"] = error_message
                return result
            try:
                radiator_binding = {
                    "equipment_id": "ENGINE_RADIATOR_1",
                    "curve_data": engine_radiator_curve.get("data", []) if isinstance(engine_radiator_curve, dict) else [],
                }
                from equipment_engine import ConfigurationLibraryEquipmentEngine, EquipmentEngineConfig

                radiator_engine_key = "engine_radiator:ENGINE_RADIATOR_1"
                if radiator_engine_key not in configuration_equipment_engines:
                    configuration_equipment_engines[radiator_engine_key] = ConfigurationLibraryEquipmentEngine(
                        EquipmentEngineConfig(
                            preloaded_curves={
                                "ENGINE_RADIATOR_1": _curve_from_library_binding(
                                    radiator_binding,
                                    "ENGINE_RADIATOR_1_power_vs_load",
                                )
                            }
                        )
                    )
                radiator_result = configuration_equipment_engines[radiator_engine_key].lookup_power(
                    "ENGINE_RADIATOR_1",
                    project_load_ratio,
                    ambient_C=oat_c,
                )
                if not radiator_result.lookup_success:
                    raise ValueError("; ".join(radiator_result.errors) or "ENGINE_RADIATOR_1 lookup failed.")
                radiator_power_per_unit = max(0.0, float(radiator_result.power_kW or radiator_result.power_input_kW or 0.0))
                engine_radiator_power_kw = radiator_power_per_unit * library_active_units
                engine_radiator_curve_source = "configuration_library_solver_curve"
                engine_radiator_curve_type = radiator_result.curve_type
            except Exception as exc:
                error_message = (
                    "ENGINE_RADIATOR_1 Solver_Curve missing or invalid. Configuration Library direct mode "
                    f"requires ENGINE_RADIATOR_1 load_ratio \u2192 power_kW data. Reason: {exc}"
                )
                validation.setdefault("errors", []).append(error_message)
                result["validation"] = validation
                result["error"] = error_message
                return result
        else:
            engine_output_kw, engine_efficiency, engine_fuel_input_kw, engine_waste_heat_kw, engine_curve_source = _evaluate_engine_curve(
                engine_curve, project_load_ratio, library_active_units
            )
            engine_radiator_power_kw, engine_radiator_curve_source = _evaluate_engine_radiator_curve(
                engine_radiator_curve, project_load_ratio, library_active_units, engine_waste_heat_kw
            )

        # Total facility power
        it_terminal_load_kw = it_kw
        mep_terminal_load_kw = cooling_kw + pumps_kw + airflow_kw + aux_kw + other_kw + white_space_equipment_power_kw + engine_radiator_power_kw
        electrical_distribution_curve_source = "legacy_non_configuration_mode"
        electrical_distribution_curve_type = None
        electrical_distribution_base_power_kw = None
        if configuration_library_direct_mode:
            electrical_error = None
            if not electrical_path_enabled:
                electrical_error = (
                    "ELECTRICAL_DISTRIBUTION_2 equipment data is missing valid IT and MEP efficiencies."
                )
            else:
                try:
                    from equipment_engine import ConfigurationLibraryEquipmentEngine, EquipmentEngineConfig

                    electrical_equipment_id = "ELECTRICAL_DISTRIBUTION_2"
                    it_curve_id = f"{electrical_equipment_id}:IT"
                    mep_curve_id = f"{electrical_equipment_id}:MEP"
                    engine_key = "electrical_distribution:ELECTRICAL_DISTRIBUTION_2"
                    if engine_key not in configuration_equipment_engines:
                        configuration_equipment_engines[engine_key] = ConfigurationLibraryEquipmentEngine(
                            EquipmentEngineConfig(
                                preloaded_curves={
                                    it_curve_id: _electrical_efficiency_curve(
                                        electrical_equipment_id, "IT", it_path_efficiency
                                    ),
                                    mep_curve_id: _electrical_efficiency_curve(
                                        electrical_equipment_id, "MEP", mep_path_efficiency
                                    ),
                                }
                            )
                        )
                    electrical_engine = configuration_equipment_engines[engine_key]
                    it_loss_result = electrical_engine.lookup_electrical_loss(
                        it_curve_id,
                        project_load_ratio,
                        base_power_kW=it_terminal_load_kw,
                    )
                    mep_loss_result = electrical_engine.lookup_electrical_loss(
                        mep_curve_id,
                        project_load_ratio,
                        base_power_kW=mep_terminal_load_kw,
                    )
                    if not it_loss_result.lookup_success:
                        raise ValueError("; ".join(it_loss_result.errors) or "IT electrical distribution lookup failed.")
                    if not mep_loss_result.lookup_success:
                        raise ValueError("; ".join(mep_loss_result.errors) or "MEP electrical distribution lookup failed.")
                    it_electrical_loss_kw = max(0.0, float(it_loss_result.loss_kW or 0.0))
                    mep_electrical_loss_kw = max(0.0, float(mep_loss_result.loss_kW or 0.0))
                    power_dist_loss = it_electrical_loss_kw + mep_electrical_loss_kw
                    it_upstream_power_kw = it_terminal_load_kw + it_electrical_loss_kw
                    mep_upstream_power_kw = mep_terminal_load_kw + mep_electrical_loss_kw
                    total_facility_power = it_upstream_power_kw + mep_upstream_power_kw
                    electrical_distribution_curve_source = "configuration_library_solver_curve"
                    electrical_distribution_curve_type = "efficiency"
                    electrical_distribution_base_power_kw = it_terminal_load_kw + mep_terminal_load_kw
                except Exception as exc:
                    electrical_error = str(exc)
            if electrical_distribution_curve_source != "configuration_library_solver_curve":
                reason = electrical_error or "ELECTRICAL_DISTRIBUTION_2 lookup failed."
                error_message = (
                    "ELECTRICAL_DISTRIBUTION_2 Solver_Curve missing or invalid. Configuration Library direct mode "
                    "requires electrical distribution loss data using one of: load_ratio + efficiency, "
                    "load_ratio + loss_fraction, or load_ratio + loss_kW. "
                    f"Reason: {reason}"
                )
                validation.setdefault("errors", []).append(error_message)
                result["validation"] = validation
                result["error"] = error_message
                return result
        elif electrical_path_enabled:
            it_upstream_power_kw = it_terminal_load_kw / it_path_efficiency
            mep_upstream_power_kw = mep_terminal_load_kw / mep_path_efficiency
            it_electrical_loss_kw = it_upstream_power_kw - it_terminal_load_kw
            mep_electrical_loss_kw = mep_upstream_power_kw - mep_terminal_load_kw
            power_dist_loss = it_electrical_loss_kw + mep_electrical_loss_kw
            total_facility_power = it_upstream_power_kw + mep_upstream_power_kw
        else:
            it_electrical_loss_kw = power_dist_loss
            mep_electrical_loss_kw = 0.0
            it_upstream_power_kw = it_terminal_load_kw + it_electrical_loss_kw
            mep_upstream_power_kw = mep_terminal_load_kw
            # Preserve the legacy addition order for bit-for-bit compatibility.
            total_facility_power = it_kw + power_dist_loss + cooling_kw + pumps_kw + airflow_kw + aux_kw + other_kw + white_space_equipment_power_kw + engine_radiator_power_kw

        # Calculate PUE
        pue = total_facility_power / it_kw if it_kw > 0 else None

        result["hourly_results"].append({
            "hour_index": idx,
            "dry_bulb_C": oat_c,
            "outdoor_dry_bulb_C": oat_c,
            "wet_bulb_C": wet_c,
            "relative_humidity_percent": rh_val,
            "IT_load_kW": it_kw,
            "it_load_kW": it_kw,
            "solar_heat_gain_kW": solar_heat_gain_kw,
            "other_auxiliary_heat_gain_kW": other_auxiliary_heat_gain_kw,
            "cooling_load_kW": cooling_load_kw,
            "design_it_load_kW": design_it_load,
            "cooling_unit_capacity_kW": cooling_unit_capacity_kw,
            "cooling_unit_count": cooling_unit_count,
            "cooling_unit_total_capacity_kW": cooling_unit_total_capacity_kw,
            "project_load_ratio": project_load_ratio,
            "unit_load_ratio": unit_load_ratio,
            "unit_load_ratio_raw": unit_load_ratio_raw,
            "cooling_power_kW": cooling_kw,
            "chiller_power_kW": chiller_kw,
            "acc_power_kW": acc_power_kw if acc_power_kw is not None else 0.0,
            "acc_required_capacity_per_unit_kW": acc_required_capacity_per_unit_kw,
            "acc_power_input_per_unit_kW": acc_power_input_per_unit_kw,
            "acc_power_input_kW": acc_power_kw if acc_power_kw is not None else 0.0,
            "acc_capacity_clamped": acc_capacity_clamped,
            "acc_diagnostic_load_ratio": acc_diagnostic_load_ratio,
            "acc_cop": acc_cop,
            "acc_curve_source": acc_curve_source,
            "acc_ambient_C": acc_ambient_c,
            "acc_temperature_power_factor": acc_temperature_power_factor,
            "acc_load_ratio": unit_load_ratio,
            "dry_cooler_power_kW": dry_cooler_kw,
            "dry_cooler_fan_power_kW": dry_cooler_kw,
            "dry_cooler_power_per_unit_kW": dry_cooler_power_per_unit_kw,
            "dry_cooler_power_source": dry_cooler_power_source,
            "heat_rejection_to_dry_cooler_kW": heat_rejection_to_dry_cooler_kw,
            "heat_rejection_per_dry_cooler_unit_kW": heat_rejection_per_dry_cooler_unit_kw,
            "dry_cooler_heat_rejection_capacity_kW": dry_cooler_heat_rejection_capacity_kw,
            "dry_cooler_total_heat_rejection_capacity_kW": cooling_unit_total_capacity_kw,
            "dry_cooler_load_ratio": dry_cooler_load_ratio,
            "dry_cooler_load_ratio_raw": dry_cooler_load_ratio_raw,
            "dry_cooler_unit_load_ratio": dry_cooler_load_ratio,
            "dry_cooler_load_kW": dry_cooler_load_kw,
            "facility_load_kW": facility_load_kw,
            "dry_cooler_curve_value": dry_curve_value,
            "dry_cooler_curve_lookup_value": dry_curve_load_value,
            "dry_cooler_rated_power_kw": dry_cooler_rated_power_kw,
            "dry_cooler_capacity_warning": dry_cooler_capacity_warning,
            "dry_cooler_approach_C": dry_cooler_approach_c,
            "condenser_entering_water_C": condenser_entering_water_c,
            "condenser_entering_water_source": condenser_entering_water_source,
            "chiller_cop": cop,
            "chiller_cop_load_ratio": cop_load_value,
            "cop_lookup_x": cop_lookup_x,
            "cop_lookup_y": cop_lookup_y,
            "cop_surface_x_min": cop_surface_x_min,
            "cop_surface_x_max": cop_surface_x_max,
            "cop_source": cop_source,
            "pump_load_ratio": pump_load_ratio,
            "chw_pump_load_ratio_basis": chw_pump_load_ratio_basis,
            "chw_pump_reference_capacity_kW": chw_pump_reference_capacity_kw,
            "peak_design_required_capacity_per_acc_unit_kW": peak_design_required_capacity_per_acc_unit_kw,
            "chw_pump_load_ratio_warning": chw_pump_load_ratio_warning,
            "chw_pump_power_per_unit_kW": chw_pump_power_per_unit_kw,
            "cw_pump_power_per_unit_kW": cw_pump_power_per_unit_kw,
            "pump_power_per_unit_kW": pump_power_per_unit_kw,
            "pump_power_total_check": pump_power_total_check,
            "pump_power_kW": pumps_kw,
            "pumps_kw": pumps_kw,
            "chw_pump_curve_source": chw_pump_curve_source,
            "pump_power_details": pump_debug_rows,
            "airflow_power_kW": airflow_kw,
            "terminal_fan_power_kW": airflow_kw,
            "terminal_fan_curve_ref": fan_curve_ref,
            "terminal_fan_enabled": fans_enabled,
            "terminal_fan_rated_power_kW": fan_rated_power_kw,
            "terminal_fan_load_ratio": fan_curve_load_value,
            "terminal_fan_curve_value": fan_curve_value,
            "terminal_fan_power_source": fan_power_source,
            "terminal_fan_excluded_due_to_mau_curve": terminal_fan_excluded_due_to_mau_curve,
            "electrical_loss_kW": power_dist_loss,
            "it_terminal_load_kW": it_terminal_load_kw,
            "it_upstream_power_kW": it_upstream_power_kw,
            "mep_terminal_load_kW": mep_terminal_load_kw,
            "mep_upstream_power_kW": mep_upstream_power_kw,
            "it_electrical_loss_kW": it_electrical_loss_kw,
            "mep_electrical_loss_kW": mep_electrical_loss_kw,
            "electrical_path_applied": electrical_path_enabled,
            "electrical_distribution_curve_source": electrical_distribution_curve_source,
            "electrical_distribution_curve_type": electrical_distribution_curve_type,
            "electrical_distribution_base_power_kW": electrical_distribution_base_power_kw,
            "cdu_power_kW": cdu_power_kw,
            "cdu_curve_source": cdu_curve_source,
            "rtc_power_kW": rtc_power_kw,
            "rtc_curve_source": rtc_curve_source,
            "mau_power_kW": mau_power_kw,
            "mau_curve_source": mau_curve_source,
            "indoor_active_units": indoor_active_units,
            "indoor_equipment_load_ratio_basis": "it_project_load_ratio",
            "indoor_equipment_unit_count_basis": "normal_indoor_active_units",
            "white_space_equipment_power_kW": white_space_equipment_power_kw,
            "engine_output_kW": engine_output_kw,
            "engine_power_kW": engine_output_kw,
            "engine_efficiency": engine_efficiency,
            "engine_fuel_input_kW": engine_fuel_input_kw,
            "engine_waste_heat_kW": engine_waste_heat_kw,
            "engine_curve_source": engine_curve_source,
            "engine_curve_type": engine_curve_type,
            "engine_radiator_power_kW": engine_radiator_power_kw,
            "engine_radiator_curve_source": engine_radiator_curve_source,
            "engine_radiator_curve_type": engine_radiator_curve_type,
            "auxiliary_power_kW": aux_kw + other_kw,
            "auxiliary_power_source": auxiliary_power_source,
            "total_facility_power_kW": total_facility_power,
            "hourly_PUE": pue
        })

    annual_it = sum(item.get("IT_load_kW", 0.0) for item in result["hourly_results"])
    annual_solar_heat_gain = sum(item.get("solar_heat_gain_kW", 0.0) for item in result["hourly_results"])
    annual_other_auxiliary_heat_gain = sum(item.get("other_auxiliary_heat_gain_kW", 0.0) for item in result["hourly_results"])
    annual_cooling_load = sum(item.get("cooling_load_kW", item.get("IT_load_kW", 0.0)) for item in result["hourly_results"])
    annual_facility = sum(item.get("total_facility_power_kW", 0.0) for item in result["hourly_results"])
    annual_cooling = sum(item.get("cooling_power_kW", 0.0) for item in result["hourly_results"])
    annual_chiller = sum(item.get("chiller_power_kW", 0.0) for item in result["hourly_results"])
    annual_dry_cooler = sum(item.get("dry_cooler_power_kW", 0.0) for item in result["hourly_results"])
    dry_cooler_fan_values = [item.get("dry_cooler_fan_power_kW", item.get("dry_cooler_power_kW", 0.0)) for item in result["hourly_results"]]
    dry_cooler_heat_rejection_values = [
        item.get("heat_rejection_to_dry_cooler_kW")
        for item in result["hourly_results"]
        if item.get("heat_rejection_to_dry_cooler_kW") is not None
    ]
    dry_cooler_load_ratio_raw_values = [
        item.get("dry_cooler_load_ratio_raw")
        for item in result["hourly_results"]
        if item.get("dry_cooler_load_ratio_raw") is not None
    ]
    annual_dry_cooler_fan = sum(dry_cooler_fan_values)
    average_dry_cooler_fan = annual_dry_cooler_fan / len(dry_cooler_fan_values) if dry_cooler_fan_values else 0.0
    max_dry_cooler_fan = max(dry_cooler_fan_values) if dry_cooler_fan_values else 0.0
    dry_cooler_over_capacity_hours = sum(1 for item in result["hourly_results"] if item.get("dry_cooler_capacity_warning"))
    dry_cooler_max_heat_rejection = max(dry_cooler_heat_rejection_values) if dry_cooler_heat_rejection_values else None
    dry_cooler_max_load_ratio_raw = max(dry_cooler_load_ratio_raw_values) if dry_cooler_load_ratio_raw_values else None
    annual_pump = sum(item.get("pump_power_kW", 0.0) for item in result["hourly_results"])
    chw_pump_curve_sources = [
        item.get("chw_pump_curve_source")
        for item in result["hourly_results"]
        if item.get("chw_pump_curve_source") not in (None, "not_applied")
    ]
    annual_terminal_fan = sum(item.get("terminal_fan_power_kW", 0.0) for item in result["hourly_results"])
    annual_loss = sum(item.get("electrical_loss_kW", 0.0) for item in result["hourly_results"])
    electrical_distribution_curve_sources = [
        item.get("electrical_distribution_curve_source")
        for item in result["hourly_results"]
        if item.get("electrical_distribution_curve_source") not in (None, "not_applied")
    ]
    electrical_distribution_curve_types = [
        item.get("electrical_distribution_curve_type")
        for item in result["hourly_results"]
        if item.get("electrical_distribution_curve_type") not in (None, "not_applied")
    ]
    annual_it_terminal = sum(item.get("it_terminal_load_kW", item.get("IT_load_kW", 0.0)) for item in result["hourly_results"])
    annual_it_upstream = sum(item.get("it_upstream_power_kW", item.get("IT_load_kW", 0.0)) for item in result["hourly_results"])
    annual_mep_terminal = sum(item.get("mep_terminal_load_kW", 0.0) for item in result["hourly_results"])
    annual_mep_upstream = sum(item.get("mep_upstream_power_kW", item.get("mep_terminal_load_kW", 0.0)) for item in result["hourly_results"])
    annual_it_electrical_loss = sum(item.get("it_electrical_loss_kW", item.get("electrical_loss_kW", 0.0)) for item in result["hourly_results"])
    annual_mep_electrical_loss = sum(item.get("mep_electrical_loss_kW", 0.0) for item in result["hourly_results"])
    annual_cdu = sum(item.get("cdu_power_kW", 0.0) for item in result["hourly_results"])
    annual_rtc = sum(item.get("rtc_power_kW", 0.0) for item in result["hourly_results"])
    annual_mau = sum(item.get("mau_power_kW", 0.0) for item in result["hourly_results"])
    cdu_curve_sources = [
        item.get("cdu_curve_source")
        for item in result["hourly_results"]
        if item.get("cdu_curve_source") not in (None, "not_applied")
    ]
    rtc_curve_sources = [
        item.get("rtc_curve_source")
        for item in result["hourly_results"]
        if item.get("rtc_curve_source") not in (None, "not_applied")
    ]
    mau_curve_sources = [
        item.get("mau_curve_source")
        for item in result["hourly_results"]
        if item.get("mau_curve_source") not in (None, "not_applied")
    ]
    annual_white_space_equipment = sum(item.get("white_space_equipment_power_kW", 0.0) for item in result["hourly_results"])
    annual_acc = sum(item.get("acc_power_kW", 0.0) for item in result["hourly_results"])
    acc_capacity_clamped_hours = sum(1 for item in result["hourly_results"] if item.get("acc_capacity_clamped"))
    acc_cop_values = [item.get("acc_cop") for item in result["hourly_results"] if item.get("acc_cop") is not None]
    acc_temperature_power_factors = [item.get("acc_temperature_power_factor") for item in result["hourly_results"] if item.get("acc_temperature_power_factor") is not None]
    max_acc_power = max((item.get("acc_power_kW", 0.0) for item in result["hourly_results"]), default=0.0)
    acc_curve_sources = [item.get("acc_curve_source") for item in result["hourly_results"] if item.get("acc_curve_source") not in (None, "not_applied")]
    annual_engine_output = sum(item.get("engine_output_kW", 0.0) for item in result["hourly_results"])
    annual_engine_fuel = sum(item.get("engine_fuel_input_kW", 0.0) for item in result["hourly_results"])
    annual_engine_waste_heat = sum(item.get("engine_waste_heat_kW", 0.0) for item in result["hourly_results"])
    engine_efficiency_values = [item.get("engine_efficiency") for item in result["hourly_results"] if item.get("engine_efficiency") is not None]
    engine_curve_sources = [item.get("engine_curve_source") for item in result["hourly_results"] if item.get("engine_curve_source") not in (None, "not_applied")]
    engine_curve_types = [item.get("engine_curve_type") for item in result["hourly_results"] if item.get("engine_curve_type") not in (None, "not_applied")]
    annual_engine_radiator = sum(item.get("engine_radiator_power_kW", 0.0) for item in result["hourly_results"])
    max_engine_radiator = max((item.get("engine_radiator_power_kW", 0.0) for item in result["hourly_results"]), default=0.0)
    engine_radiator_sources = [item.get("engine_radiator_curve_source") for item in result["hourly_results"] if item.get("engine_radiator_curve_source") not in (None, "not_applied")]
    engine_radiator_curve_types = [item.get("engine_radiator_curve_type") for item in result["hourly_results"] if item.get("engine_radiator_curve_type") not in (None, "not_applied")]
    annual_aux = sum(item.get("auxiliary_power_kW", 0.0) for item in result["hourly_results"])
    auxiliary_power_sources = [
        item.get("auxiliary_power_source")
        for item in result["hourly_results"]
        if item.get("auxiliary_power_source") not in (None, "not_applied")
    ]
    annual_pue = annual_facility / annual_it_terminal if annual_it_terminal > 0 else None
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
        "annual_it_energy_kWh": annual_it,
        "annual_solar_heat_gain_kWh": annual_solar_heat_gain,
        "annual_other_auxiliary_heat_gain_kWh": annual_other_auxiliary_heat_gain,
        "annual_cooling_load_kWh": annual_cooling_load,
        "annual_IT_terminal_energy_kWh": annual_it_terminal,
        "annual_IT_upstream_energy_kWh": annual_it_upstream,
        "annual_MEP_terminal_energy_kWh": annual_mep_terminal,
        "annual_MEP_upstream_energy_kWh": annual_mep_upstream,
        "annual_facility_energy_kWh": annual_facility,
        # Current cooling_kw is chiller + dry cooler only; keep legacy key for compatibility.
        "annual_cooling_energy_kWh": annual_cooling,
        "annual_chiller_plus_dry_cooler_energy_kWh": annual_cooling,
        "annual_total_cooling_system_energy_kWh": annual_chiller + annual_dry_cooler + annual_pump + annual_terminal_fan,
        "annual_chiller_energy_kWh": annual_chiller,
        "annual_dry_cooler_energy_kWh": annual_dry_cooler,
        "annual_dry_cooler_fan_energy_kWh": annual_dry_cooler_fan,
        "average_dry_cooler_fan_power_kW": average_dry_cooler_fan,
        "max_dry_cooler_fan_power_kW": max_dry_cooler_fan,
        "dry_cooler_pue_contribution": annual_dry_cooler_fan / annual_it if annual_it > 0 else None,
        "dry_cooler_over_capacity_hours": dry_cooler_over_capacity_hours,
        "dry_cooler_max_heat_rejection_kW": dry_cooler_max_heat_rejection,
        "dry_cooler_max_load_ratio_raw": dry_cooler_max_load_ratio_raw,
        "annual_pump_energy_kWh": annual_pump,
        "chw_pump_curve_source": chw_pump_curve_sources[0] if chw_pump_curve_sources else "legacy_non_configuration_mode",
        "annual_terminal_fan_energy_kWh": annual_terminal_fan,
        "annual_electrical_loss_kWh": annual_loss,
        "electrical_distribution_curve_source": (
            electrical_distribution_curve_sources[0]
            if electrical_distribution_curve_sources
            else "legacy_non_configuration_mode"
        ),
        "electrical_distribution_curve_type": (
            electrical_distribution_curve_types[0]
            if electrical_distribution_curve_types
            else None
        ),
        "annual_it_electrical_loss_kWh": annual_it_electrical_loss,
        "annual_mep_electrical_loss_kWh": annual_mep_electrical_loss,
        "annual_cdu_energy_kWh": annual_cdu,
        "cdu_curve_source": cdu_curve_sources[0] if cdu_curve_sources else "legacy_non_configuration_mode",
        "annual_rtc_energy_kWh": annual_rtc,
        "rtc_curve_source": rtc_curve_sources[0] if rtc_curve_sources else "legacy_non_configuration_mode",
        "annual_mau_energy_kWh": annual_mau,
        "mau_curve_source": mau_curve_sources[0] if mau_curve_sources else "legacy_non_configuration_mode",
        "annual_white_space_equipment_energy_kWh": annual_white_space_equipment,
        "annual_acc_energy_kWh": annual_acc,
        "acc_capacity_clamped_hours": acc_capacity_clamped_hours,
        "average_acc_cop": sum(acc_cop_values) / len(acc_cop_values) if acc_cop_values else None,
        "min_acc_cop": min(acc_cop_values) if acc_cop_values else None,
        "max_acc_cop": max(acc_cop_values) if acc_cop_values else None,
        "average_acc_temperature_power_factor": sum(acc_temperature_power_factors) / len(acc_temperature_power_factors) if acc_temperature_power_factors else None,
        "max_acc_power_kW": max_acc_power,
        "acc_curve_source": acc_curve_sources[0] if acc_curve_sources else "not_applied",
        "annual_engine_output_kWh": annual_engine_output,
        "annual_engine_energy_kWh": annual_engine_output,
        "annual_engine_fuel_input_kWh": annual_engine_fuel,
        "annual_engine_waste_heat_kWh": annual_engine_waste_heat,
        "average_engine_efficiency": sum(engine_efficiency_values) / len(engine_efficiency_values) if engine_efficiency_values else None,
        "engine_curve_source": engine_curve_sources[0] if engine_curve_sources else "not_applied",
        "engine_curve_type": engine_curve_types[0] if engine_curve_types else None,
        "annual_engine_radiator_energy_kWh": annual_engine_radiator,
        "max_engine_radiator_power_kW": max_engine_radiator,
        "engine_radiator_curve_source": engine_radiator_sources[0] if engine_radiator_sources else "not_applied",
        "engine_radiator_curve_type": engine_radiator_curve_types[0] if engine_radiator_curve_types else None,
        "annual_auxiliary_energy_kWh": annual_aux,
        "auxiliary_power_source": auxiliary_power_sources[0] if auxiliary_power_sources else None,
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
        "peak_facility_hour_PUE": peak_facility.get("hourly_PUE"),
        "max_hourly_PUE": peak_pue.get("hourly_PUE"),
        "max_hourly_PUE_hour_index": peak_pue.get("hour_index"),
        "max_hourly_PUE_outdoor_dry_bulb_C": peak_pue.get("dry_bulb_C"),
        "max_hourly_PUE_IT_load_kW": peak_pue.get("IT_load_kW"),
        "max_hourly_total_facility_power_kW": peak_pue.get("total_facility_power_kW"),
        "max_hourly_facility_electrical_demand_kW": peak_pue.get("total_facility_power_kW")
    }
    design_it_load_source = _num(it_load.get("design_it_load_kW"), None)
    if design_it_load_source is None or design_it_load_source <= 0:
        design_it_load_source = _num(project.get("design_it_load_kW"), None)
    should_calculate_peak_design = (
        configuration_library_direct_mode
        and acc_v2_direct_mode_enabled
        and not input_obj.get("_skip_peak_design_pue")
    )
    if should_calculate_peak_design:
        if design_it_load_source is None or design_it_load_source <= 0:
            validation.setdefault("warnings", []).append(
                "Peak Design PUE was not calculated because design_it_load_kW is missing; peak_PUE retains max hourly PUE."
            )
        else:
            peak_design_condition = _peak_design_weather_condition(input_obj)
            peak_design_ambient_c = _num(peak_design_condition.get("extreme_db_max_C"), None)
        if design_it_load_source is not None and design_it_load_source > 0 and peak_design_ambient_c is None:
            validation.setdefault("warnings", []).append(
                "Peak Design PUE was not calculated because peak design dry-bulb temperature is unavailable; peak_PUE retains max hourly PUE."
            )
        elif design_it_load_source is not None and design_it_load_source > 0:
            peak_design_hour_index = None
            peak_design_input = deepcopy(input_obj)
            peak_design_project = peak_design_input.setdefault("project", {})
            peak_design_it_load = peak_design_project.setdefault("it_load", {})
            peak_design_it_load["design_it_load_kW"] = float(design_it_load_source)
            peak_design_it_load["hourly_it_load_kW"] = [float(design_it_load_source)]
            peak_design_it_load["hourly_it_load_percent"] = [100.0]
            peak_design_project["design_it_load_kW"] = float(design_it_load_source)
            peak_design_weather = peak_design_input.setdefault("weather", {}).setdefault("hourly_data", {})
            peak_design_weather["hour_index"] = [0]
            peak_design_weather["dry_bulb_C"] = [float(peak_design_ambient_c)]
            peak_design_weather["wet_bulb_C"] = []
            peak_design_weather["relative_humidity_percent"] = []
            peak_design_input["_skip_peak_design_pue"] = True
            peak_design_input["_force_solar_heat_gain_max"] = True
            if acc_v2_engine is not None:
                peak_design_input["_acc_v2_engine_override"] = acc_v2_engine
            try:
                peak_design_result = compute_pue_project(peak_design_input)
                peak_design_hour = (
                    peak_design_result.get("hourly_results", [None])[0]
                    if isinstance(peak_design_result.get("hourly_results"), list)
                    and peak_design_result.get("hourly_results")
                    else None
                )
                if not isinstance(peak_design_hour, dict):
                    raise ValueError(peak_design_result.get("error") or "Peak design evaluation produced no hourly row.")
                peak_design_total_facility = peak_design_hour.get("total_facility_power_kW")
                peak_design_pue = (
                    peak_design_total_facility / float(design_it_load_source)
                    if peak_design_total_facility is not None and design_it_load_source > 0
                    else peak_design_hour.get("hourly_PUE")
                )
                result["peak_results"].update({
                    "peak_PUE": peak_design_pue,
                    "peak_PUE_definition": "peak_design",
                    "peak_PUE_hour_index": peak_design_hour_index,
                    "peak_PUE_outdoor_dry_bulb_C": peak_design_ambient_c,
                    "peak_PUE_IT_load_kW": float(design_it_load_source),
                    "peak_design_total_facility_power_kW": peak_design_total_facility,
                    "peak_design_facility_electrical_demand_kW": peak_design_total_facility,
                    "peak_design_it_load_kW": float(design_it_load_source),
                    "peak_design_cooling_load_kW": peak_design_hour.get("cooling_load_kW"),
                    "peak_design_weather_source": peak_design_condition.get("source"),
                    "peak_design_lookup_provider": peak_design_condition.get("lookup_provider"),
                    "peak_design_lookup_status": peak_design_condition.get("lookup_status"),
                    "peak_design_lookup_failure_reason": peak_design_condition.get("failure_reason"),
                    "peak_design_weather_station": peak_design_condition.get("station_name"),
                    "peak_design_weather_station_id": peak_design_condition.get("station_id"),
                    "peak_design_weather_station_distance_km": peak_design_condition.get("station_distance_km"),
                    "peak_design_weather_station_latitude": peak_design_condition.get("station_latitude"),
                    "peak_design_weather_station_longitude": peak_design_condition.get("station_longitude"),
                    "peak_design_temperature_basis": peak_design_condition.get("temperature_basis"),
                    "peak_design_outdoor_dry_bulb_C": peak_design_ambient_c,
                    "peak_design_hour_index": peak_design_hour_index,
                    "peak_design_ACC_power_kW": peak_design_hour.get("acc_power_kW"),
                    "peak_design_CHW_pump_power_kW": peak_design_hour.get("pump_power_kW"),
                    "peak_design_CDU_power_kW": peak_design_hour.get("cdu_power_kW"),
                    "peak_design_RTC_power_kW": peak_design_hour.get("rtc_power_kW"),
                    "peak_design_MAU_power_kW": peak_design_hour.get("mau_power_kW"),
                    "peak_design_engine_radiator_power_kW": peak_design_hour.get("engine_radiator_power_kW"),
                    "peak_design_other_electrical_auxiliary_power_kW": peak_design_hour.get("auxiliary_power_kW"),
                    "peak_design_electrical_loss_kW": peak_design_hour.get("electrical_loss_kW"),
                    "peak_design_ACC_required_capacity_per_unit_kW": peak_design_hour.get("acc_required_capacity_per_unit_kW"),
                    "peak_design_CHW_pump_load_ratio": peak_design_hour.get("pump_load_ratio"),
                    "peak_design_CHW_pump_reference_capacity_kW": peak_design_hour.get("chw_pump_reference_capacity_kW"),
                    "peak_design_required_capacity_per_acc_unit_kW": peak_design_hour.get("peak_design_required_capacity_per_acc_unit_kW"),
                    "peak_design_indoor_active_units": peak_design_hour.get("indoor_active_units"),
                    "peak_design_project_load_ratio": peak_design_hour.get("project_load_ratio"),
                    "peak_design_mep_terminal_load_kW": peak_design_hour.get("mep_terminal_load_kW"),
                    "peak_design_it_electrical_loss_kW": peak_design_hour.get("it_electrical_loss_kW"),
                    "peak_design_mep_electrical_loss_kW": peak_design_hour.get("mep_electrical_loss_kW"),
                    "peak_design_terminal_fan_power_kW": peak_design_hour.get("terminal_fan_power_kW"),
                    "peak_total_facility_power_kW": peak_design_total_facility,
                    "peak_hour_index": peak_design_hour_index,
                    "peak_outdoor_dry_bulb_C": peak_design_ambient_c,
                    "peak_outdoor_wet_bulb_C": peak_design_hour.get("wet_bulb_C"),
                    "peak_IT_load_kW": float(design_it_load_source),
                })
            except Exception as exc:
                validation.setdefault("warnings", []).append(
                    f"Peak Design PUE evaluation failed; peak_PUE retains max hourly PUE. Reason: {exc}"
                )
    validation["checks"]["PUE_greater_than_1_check"] = annual_pue is None or annual_pue > 1.0
    if isinstance(weather.get("design_peak_hour_method"), str) and weather.get("design_peak_hour_method").lower() == "highest_dry_bulb_hour":
        max_dry = max(range(len(dry_bulb)), key=lambda j: _num(dry_bulb[j], -1.0)) if len(dry_bulb) > 0 else None
        expected_peak = hour_index[max_dry] if max_dry is not None and max_dry < len(hour_index) else max_dry
        validation["checks"]["peak_hour_consistency_check"] = expected_peak == peak_facility.get("hour_index")
        if not validation["checks"]["peak_hour_consistency_check"]:
            validation["warnings"].append("peak hour PUE does not match highest dry bulb hour")
    else:
        validation["checks"]["peak_hour_consistency_check"] = True
    if dry_cooler_over_capacity_count > 0:
        validation["warnings"].append(
            "Dry cooler heat rejection load exceeds rated heat rejection capacity in "
            f"{dry_cooler_over_capacity_count} hourly records; dry cooler load_ratio was capped at 1.0 "
            "for fan power curve lookup."
        )
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
