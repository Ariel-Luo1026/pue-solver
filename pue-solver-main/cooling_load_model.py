"""Shared weather, cooling-load, and peak-design helpers for topology runtimes."""


def calculate_annual_cooling_load(project_input):
    """Return hourly cooling-load rows using the same heat-gain model as solver.py."""

    project = _dict(project_input.get("project"))
    hourly_it = _hourly_it_loads(project)
    hours = len(hourly_it)
    weather = _weather_data(project_input, hours)
    dry_bulb = weather["dry_bulb_C"]
    hour_index = weather["hour_index"]
    heat_gains = normalize_heat_gain_inputs(project_input)

    annual_min = min(dry_bulb) if dry_bulb else None
    annual_max = max(dry_bulb) if dry_bulb else None
    hourly_rows = []
    totals = {
        "annual_IT_energy_kWh": 0.0,
        "annual_solar_heat_gain_kWh": 0.0,
        "annual_other_auxiliary_heat_gain_kWh": 0.0,
        "annual_cooling_load_kWh": 0.0,
    }

    for index, it_kw in enumerate(hourly_it):
        ambient_c = dry_bulb[index]
        hour_of_day = hour_index[index] % 24
        solar_kw = solar_heat_gain_kw(ambient_c, annual_min, annual_max, hour_of_day, heat_gains)
        auxiliary_kw = heat_gains["other_auxiliary_heat_gain_kW"]
        cooling_load_kw = float(it_kw) + solar_kw + auxiliary_kw
        row = {
            "hour": index + 1,
            "hour_index": hour_index[index],
            "hour_of_day": hour_of_day,
            "it_load_kW": float(it_kw),
            "ambient_dry_bulb_C": ambient_c,
            "solar_heat_gain_kW": solar_kw,
            "other_auxiliary_heat_gain_kW": auxiliary_kw,
            "cooling_load_kW": cooling_load_kw,
        }
        hourly_rows.append(row)
        totals["annual_IT_energy_kWh"] += float(it_kw)
        totals["annual_solar_heat_gain_kWh"] += solar_kw
        totals["annual_other_auxiliary_heat_gain_kWh"] += auxiliary_kw

    totals["annual_cooling_load_kWh"] = sum(row["cooling_load_kW"] for row in hourly_rows)

    return {
        "status": "success",
        "hourly_cooling_load": hourly_rows,
        "totals": totals,
        "heat_gain_config": dict(heat_gains),
        "weather": {
            "hourly_data": {
                "hour_index": hour_index,
                "dry_bulb_C": dry_bulb,
                "wet_bulb_C": weather["wet_bulb_C"],
            },
            "metadata": weather["metadata"],
        },
    }


def calculate_peak_design_condition(project_input, peak_design_condition=None):
    """Return the common peak design cooling condition for all topologies."""

    project = _dict(project_input.get("project"))
    design_it = _num(
        _dict(project.get("it_load")).get("design_it_load_kW"),
        _num(project.get("design_it_load_kW"), None),
    )
    if design_it is None:
        hourly_it = _dict(project.get("it_load")).get("hourly_it_load_kW")
        if isinstance(hourly_it, list) and hourly_it:
            design_it = max(_num(value, 0.0) for value in hourly_it)
    design_it = float(design_it or 0.0)

    condition = _dict(peak_design_condition)
    peak_db = _num(condition.get("extreme_db_max_C"), None)
    if peak_db is None:
        peak_db = _num(project_input.get("peak_design_outdoor_dry_bulb_C"), None)
    if peak_db is None:
        peak_db = _num(project.get("peak_design_outdoor_dry_bulb_C"), None)

    heat_gains = normalize_heat_gain_inputs(project_input)
    solar_peak = heat_gains["solar_heat_gain_max_kW"]
    auxiliary_kw = heat_gains["other_auxiliary_heat_gain_kW"]
    cooling_load_kw = design_it + solar_peak + auxiliary_kw

    return {
        "peak_PUE_definition": "peak_design",
        "peak_design_it_load_kW": design_it,
        "peak_design_outdoor_dry_bulb_C": peak_db,
        "peak_design_solar_heat_gain_kW": solar_peak,
        "peak_design_other_auxiliary_heat_gain_kW": auxiliary_kw,
        "peak_design_cooling_load_kW": cooling_load_kw,
        "peak_design_weather_source": (
            condition.get("source")
            or project_input.get("peak_design_weather_source")
            or project.get("peak_design_weather_source")
        ),
        "peak_design_lookup_provider": condition.get("lookup_provider"),
        "peak_design_lookup_status": condition.get("lookup_status"),
        "peak_design_lookup_failure_reason": condition.get("failure_reason"),
        "peak_design_online_status": condition.get("online_status"),
        "peak_design_fallback_status": condition.get("fallback_status"),
        "peak_design_lookup_method": condition.get("lookup_method"),
        "peak_design_lookup_endpoint": condition.get("lookup_endpoint"),
        "peak_design_weather_station": condition.get("station_name"),
        "peak_design_weather_station_id": condition.get("station_id"),
        "peak_design_weather_station_distance_km": condition.get("station_distance_km"),
        "peak_design_temperature_basis": (
            condition.get("temperature_basis")
            or "ASHRAE_20_year_extreme_annual_design_condition"
        ),
    }


def normalize_heat_gain_inputs(project_input):
    """Normalize heat-gain inputs with the same defaults and aliases as solver.py."""

    project = _dict(project_input.get("project"))
    heat_gains = _dict(project.get("heat_gains"))

    solar_max = _num(
        project_input.get("solar_heat_gain_max_kW"),
        _num(heat_gains.get("solar_heat_gain_max_kW"), 0.0),
    )
    start_hour = _num(
        project_input.get("solar_daytime_start_hour"),
        _num(heat_gains.get("solar_daytime_start_hour"), 6),
    )
    end_hour = _num(
        project_input.get("solar_daytime_end_hour"),
        _num(heat_gains.get("solar_daytime_end_hour"), 18),
    )
    auxiliary_kw = _num(
        project_input.get("other_auxiliary_heat_gain_kW"),
        _num(heat_gains.get("other_auxiliary_heat_gain_kW"), 0.0),
    )

    return {
        "solar_heat_gain_max_kW": max(0.0, float(solar_max or 0.0)),
        "solar_daytime_start_hour": int(start_hour or 0) % 24,
        "solar_daytime_end_hour": int(end_hour or 0) % 24,
        "other_auxiliary_heat_gain_kW": max(0.0, float(auxiliary_kw or 0.0)),
        "_force_solar_heat_gain_max": bool(project_input.get("_force_solar_heat_gain_max")),
    }


def solar_heat_gain_kw(ambient_c, annual_min_ambient_c, annual_max_ambient_c, hour_of_day, heat_gain_config):
    max_kw = heat_gain_config["solar_heat_gain_max_kW"]
    if max_kw <= 0:
        return 0.0
    if heat_gain_config.get("_force_solar_heat_gain_max"):
        return max_kw
    if not _is_daytime_hour(
        hour_of_day,
        heat_gain_config["solar_daytime_start_hour"],
        heat_gain_config["solar_daytime_end_hour"],
    ):
        return 0.0
    if ambient_c is None or annual_min_ambient_c is None or annual_max_ambient_c is None:
        return 0.0
    ambient_range = annual_max_ambient_c - annual_min_ambient_c
    if ambient_range <= 0:
        normalized = 0.0
    else:
        normalized = _clamp((float(ambient_c) - annual_min_ambient_c) / ambient_range, 0.0, 1.0)
    return _clamp(max_kw * normalized * normalized, 0.0, max_kw)


def _weather_data(project_input, hours):
    weather = _dict(project_input.get("weather"))
    hourly_data = _dict(weather.get("hourly_data"))
    dry_bulb = hourly_data.get("dry_bulb_C")
    wet_bulb = hourly_data.get("wet_bulb_C")
    hour_index = hourly_data.get("hour_index")

    if isinstance(dry_bulb, list) and len(dry_bulb) >= hours:
        dry = [_num(value, 25.0) for value in dry_bulb[:hours]]
    else:
        dry = [25.0] * hours

    if isinstance(wet_bulb, list) and len(wet_bulb) >= hours:
        wet = [_num(value, None) for value in wet_bulb[:hours]]
    else:
        wet = []

    if isinstance(hour_index, list) and len(hour_index) >= hours:
        hours_out = [int(_num(value, index) or 0) for index, value in enumerate(hour_index[:hours])]
    else:
        hours_out = list(range(hours))

    return {
        "dry_bulb_C": dry,
        "wet_bulb_C": wet,
        "hour_index": hours_out,
        "metadata": weather.get("metadata") if isinstance(weather.get("metadata"), dict) else {},
    }


def _hourly_it_loads(project):
    it_load = _dict(project.get("it_load"))
    hourly_it = it_load.get("hourly_it_load_kW")
    if not isinstance(hourly_it, list) or not hourly_it:
        raise ValueError("project.it_load.hourly_it_load_kW is required.")
    return [_num(value, 0.0) for value in hourly_it]


def _is_daytime_hour(hour_of_day, start_hour, end_hour):
    if start_hour == end_hour:
        return False
    if start_hour < end_hour:
        return start_hour <= hour_of_day < end_hour
    return hour_of_day >= start_hour or hour_of_day < end_hour


def _clamp(value, low, high):
    return max(low, min(high, value))


def _num(value, default=None):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _dict(value):
    return value if isinstance(value, dict) else {}
