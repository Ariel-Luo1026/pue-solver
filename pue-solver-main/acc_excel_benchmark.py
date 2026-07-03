"""Excel-compatible ACC benchmark calculator.

This module intentionally does not call or modify the dynamic hourly solver.
It reproduces the ACC_1.5MW_GASENGINE_CDU benchmark workbook equations.
"""


ACC_ANNUAL_FACTOR = 0.53019973837616008
IT_ANNUAL_FACTOR = 0.9
ANNUAL_HOURS = 8760
IT_EFFICIENCY = 0.97231900702513507
MEP_EFFICIENCY = 0.99590439959999999

SCENARIOS = {
    "normal": {
        "name": "Normal",
        "peak_acc_power_kw": 1080.0,
        "peak_pump_power_kw": 60.0,
        "peak_indoor_equipment_power_kw": 80.0,
        "peak_engine_radiator_power_kw": 120.0,
        "active_units": 4,
    },
    "failure": {
        "name": "Failure",
        "peak_acc_power_kw": 1050.0,
        "peak_pump_power_kw": 60.0,
        "peak_indoor_equipment_power_kw": 80.0,
        "peak_engine_radiator_power_kw": 108.0,
        "active_units": 3,
    },
    "maintenance": {
        "name": "Maintenance",
        "peak_acc_power_kw": 1050.0,
        "peak_pump_power_kw": 60.0,
        "peak_indoor_equipment_power_kw": 80.0,
        "peak_engine_radiator_power_kw": 108.0,
        "active_units": 3,
    },
}


def _linear_interpolate_clamped(points, value):
    ordered = sorted((float(x), float(y)) for x, y in points)
    if not ordered:
        return None
    if value <= ordered[0][0]:
        return ordered[0][1]
    if value >= ordered[-1][0]:
        return ordered[-1][1]
    for (x0, y0), (x1, y1) in zip(ordered, ordered[1:]):
        if x0 <= value <= x1:
            if x1 == x0:
                return y1
            fraction = (value - x0) / (x1 - x0)
            return y0 + fraction * (y1 - y0)
    return ordered[-1][1]


def compute_acc_experimental_hourly_shape(input_obj):
    """Create an experimental EPW hourly shape while preserving the Excel annual ACC target."""
    if not isinstance(input_obj, dict):
        return {"error": "input is not an object"}
    scenario_key = str(input_obj.get("scenario_name") or "Normal").strip().lower()
    scenario = SCENARIOS.get(scenario_key)
    if scenario is None:
        return {"error": f"unsupported benchmark scenario: {scenario_key}"}

    project = input_obj.get("project", {}) if isinstance(input_obj.get("project"), dict) else {}
    it_profile = project.get("it_load", {}).get("hourly_it_load_kW", [])
    weather = input_obj.get("weather", {}) if isinstance(input_obj.get("weather"), dict) else {}
    weather_data = weather.get("hourly_data", {}) if isinstance(weather.get("hourly_data"), dict) else {}
    dry_bulb = weather_data.get("dry_bulb_C", [])
    if not isinstance(it_profile, list) or len(it_profile) != ANNUAL_HOURS:
        return {"error": "hourly benchmark requires 8760 IT load values"}
    if not isinstance(dry_bulb, list) or len(dry_bulb) != ANNUAL_HOURS:
        return {"error": "hourly benchmark requires 8760 dry-bulb temperature values"}

    curve_rows = input_obj.get("acc_curve", {}).get("data", [])
    temperature_power_points = [
        (row["ambient_C"], row["power_input_kW"])
        for row in curve_rows
        if row.get("ambient_C") is not None and row.get("power_input_kW") is not None
    ]
    if len(temperature_power_points) < 2:
        return {"error": "hourly benchmark requires at least two ACC ambient/power curve points"}
    design_power = max(temperature_power_points, key=lambda item: float(item[0]))[1]
    if float(design_power) <= 0:
        return {"error": "ACC design-point power must be positive"}

    raw_factors = [
        _linear_interpolate_clamped(temperature_power_points, float(temperature)) / float(design_power)
        for temperature in dry_bulb
    ]
    raw_acc_power = [scenario["peak_acc_power_kw"] * factor for factor in raw_factors]
    target_annual_acc_energy = scenario["peak_acc_power_kw"] * ACC_ANNUAL_FACTOR * ANNUAL_HOURS
    raw_annual_acc_energy = sum(raw_acc_power)
    if raw_annual_acc_energy <= 0:
        return {"error": "raw hourly ACC energy must be positive"}
    scale_factor = target_annual_acc_energy / raw_annual_acc_energy
    hourly_acc_power = [power * scale_factor for power in raw_acc_power]

    design_it_kw = float(project.get("design_it_load_kW") or 4400.0)
    hourly_results = []
    for index, (it_value, oat_c, acc_kw, raw_factor) in enumerate(
        zip(it_profile, dry_bulb, hourly_acc_power, raw_factors), start=1
    ):
        it_kw = float(it_value)
        load_factor = it_kw / design_it_kw if design_it_kw > 0 else 0.0
        pump_kw = scenario["peak_pump_power_kw"] * load_factor
        indoor_kw = scenario["peak_indoor_equipment_power_kw"] * load_factor
        radiator_kw = scenario["peak_engine_radiator_power_kw"] * load_factor
        non_it_kw = acc_kw + pump_kw + indoor_kw + radiator_kw
        it_loss_kw = it_kw / IT_EFFICIENCY - it_kw
        mep_loss_kw = non_it_kw / MEP_EFFICIENCY - non_it_kw
        facility_kw = it_kw + non_it_kw + it_loss_kw + mep_loss_kw
        pue = facility_kw / it_kw if it_kw > 0 else None
        hourly_results.append({
            "hour_index": index,
            "dry_bulb_C": float(oat_c),
            "IT_load_kW": it_kw,
            "acc_power_kW": acc_kw,
            "acc_temperature_power_factor": raw_factor * scale_factor,
            "acc_raw_temperature_power_factor": raw_factor,
            "acc_curve_source": "experimental_acc_ambient_shape_annual_calibration",
            "pump_power_kW": pump_kw,
            "indoor_equipment_power_kW": indoor_kw,
            "engine_radiator_power_kW": radiator_kw,
            "it_electrical_loss_kW": it_loss_kw,
            "mep_electrical_loss_kW": mep_loss_kw,
            "electrical_loss_kW": it_loss_kw + mep_loss_kw,
            "total_facility_power_kW": facility_kw,
            "hourly_PUE": pue,
        })

    def total(field):
        return sum(float(row.get(field) or 0.0) for row in hourly_results)

    annual_it = total("IT_load_kW")
    annual_facility = total("total_facility_power_kW")
    annual_acc = total("acc_power_kW")
    annual_pump = total("pump_power_kW")
    annual_indoor = total("indoor_equipment_power_kW")
    annual_radiator = total("engine_radiator_power_kW")
    annual_it_loss = total("it_electrical_loss_kW")
    annual_mep_loss = total("mep_electrical_loss_kW")
    valid_pue_rows = [row for row in hourly_results if row["hourly_PUE"] is not None]
    peak_pue = max(valid_pue_rows, key=lambda row: row["hourly_PUE"])
    min_pue = min(valid_pue_rows, key=lambda row: row["hourly_PUE"])
    peak_facility = max(hourly_results, key=lambda row: row["total_facility_power_kW"])
    max_acc_power = max(row["acc_power_kW"] for row in hourly_results)
    scenario_peak_acc_power = scenario["peak_acc_power_kw"]
    acc_peak_ratio = max_acc_power / scenario_peak_acc_power if scenario_peak_acc_power > 0 else None
    acc_peak_warning = acc_peak_ratio is not None and acc_peak_ratio > 1.10
    warnings = ([
        "Experimental hourly ACC power exceeds scenario peak ACC power by more than 10%; peak hourly PUE is experimental and is not a validated design peak."
    ] if acc_peak_warning else [])
    annual_pue = annual_facility / annual_it if annual_it > 0 else None
    average = lambda energy: energy / ANNUAL_HOURS
    annual_results = {
        "calculation_mode": "experimental_acc_hourly_shape",
        "annual_average_PUE": annual_pue,
        "annual_IT_energy_kWh": annual_it,
        "annual_it_energy_kWh": annual_it,
        "annual_facility_energy_kWh": annual_facility,
        "annual_acc_energy_kWh": annual_acc,
        "annual_pump_energy_kWh": annual_pump,
        "annual_indoor_equipment_energy_kWh": annual_indoor,
        "annual_engine_radiator_energy_kWh": annual_radiator,
        "annual_it_electrical_loss_kWh": annual_it_loss,
        "annual_mep_electrical_loss_kWh": annual_mep_loss,
        "annual_electrical_loss_kWh": annual_it_loss + annual_mep_loss,
        "annual_total_cooling_system_energy_kWh": annual_acc + annual_pump + annual_indoor + annual_radiator,
        "average_IT_power_kW": average(annual_it),
        "average_acc_power_kW": average(annual_acc),
        "average_pump_power_kW": average(annual_pump),
        "average_indoor_equipment_power_kW": average(annual_indoor),
        "average_engine_radiator_power_kW": average(annual_radiator),
        "average_it_electrical_loss_kW": average(annual_it_loss),
        "average_mep_electrical_loss_kW": average(annual_mep_loss),
        "average_facility_power_kW": average(annual_facility),
        "min_hourly_PUE": min_pue["hourly_PUE"],
        "max_hourly_PUE": peak_pue["hourly_PUE"],
        "acc_hourly_calibration_scale_factor": scale_factor,
        "max_acc_power_kW": max_acc_power,
        "scenario_peak_acc_power_kW": scenario_peak_acc_power,
        "acc_peak_to_scenario_peak_ratio": acc_peak_ratio,
        "acc_peak_power_warning": acc_peak_warning,
    }
    return {
        "calculation_mode": "experimental_acc_hourly_shape",
        "calculation_mode_label": "Experimental ACC Hourly Shape Mode",
        "calculation_note": "This mode generates a synthetic hourly ACC profile using EPW dry-bulb temperature and the available ACC Solver_Curve, then scales annual ACC energy to match the Excel benchmark. It is not a validated Excel hourly method.",
        "warnings": warnings,
        "project": {**project, "scenario_name": scenario["name"], "active_units": scenario["active_units"]},
        "hourly_results": hourly_results,
        "annual_results": annual_results,
        "peak_results": {
            "peak_PUE": peak_pue["hourly_PUE"],
            "peak_PUE_hour_index": peak_pue["hour_index"],
            "peak_PUE_outdoor_dry_bulb_C": peak_pue["dry_bulb_C"],
            "peak_hour_index": peak_facility["hour_index"],
            "peak_outdoor_dry_bulb_C": peak_facility["dry_bulb_C"],
            "peak_IT_load_kW": peak_facility["IT_load_kW"],
            "peak_total_facility_power_kW": peak_facility["total_facility_power_kW"],
            "peak_facility_hour_PUE": peak_facility["hourly_PUE"],
        },
        "benchmark_components": {
            "scenario": scenario["name"],
            "annual_hours": ANNUAL_HOURS,
            "it_annual_load_factor": annual_it / (design_it_kw * ANNUAL_HOURS),
            "acc_annual_temperature_factor": ACC_ANNUAL_FACTOR,
            "it_efficiency": IT_EFFICIENCY,
            "mep_efficiency": MEP_EFFICIENCY,
            "acc_hourly_calibration_scale_factor": scale_factor,
            "component_average_kW": {
                "IT": average(annual_it), "ACC": average(annual_acc), "pump": average(annual_pump),
                "indoor_CDU_RTC_MAU_equivalent": average(annual_indoor),
                "engine_radiator": average(annual_radiator), "IT_electrical_loss": average(annual_it_loss),
                "MEP_electrical_loss": average(annual_mep_loss), "facility": average(annual_facility),
            },
        },
    }


def compute_acc_excel_replicated_hourly(input_obj):
    """Replicate the 05_Appendix01 hourly ACC factor and workbook power formulas."""
    if not isinstance(input_obj, dict):
        return {"error": "input is not an object"}
    scenario_key = str(input_obj.get("scenario_name") or "Normal").strip().lower()
    scenario = SCENARIOS.get(scenario_key)
    if scenario is None:
        return {"error": f"unsupported benchmark scenario: {scenario_key}"}
    project = input_obj.get("project", {}) if isinstance(input_obj.get("project"), dict) else {}
    weather = input_obj.get("weather", {}) if isinstance(input_obj.get("weather"), dict) else {}
    weather_data = weather.get("hourly_data", {}) if isinstance(weather.get("hourly_data"), dict) else {}
    dry_bulb = weather_data.get("dry_bulb_C", [])
    if not isinstance(dry_bulb, list) or len(dry_bulb) != ANNUAL_HOURS:
        return {"error": "Excel replicated hourly mode requires 8760 dry-bulb temperature values"}

    design_it_kw = float(project.get("design_it_load_kW") or 4400.0)
    it_kw = design_it_kw * IT_ANNUAL_FACTOR
    design_ambient_c = 46.1       # 05_Appendix01!B8
    low_temperature_c = 5.0      # 05_Appendix01!B10
    base_normalized_ratio = 0.381  # 05_Appendix01!B11
    hourly_results = []
    for index, temperature in enumerate(dry_bulb, start=1):
        oat_c = float(temperature)
        temperature_fraction = min(1.0, max(0.0, (oat_c - low_temperature_c) / (design_ambient_c - low_temperature_c)))
        acc_factor = IT_ANNUAL_FACTOR * (
            base_normalized_ratio + (1.0 - base_normalized_ratio) * temperature_fraction
        )
        acc_kw = scenario["peak_acc_power_kw"] * acc_factor
        pump_kw = scenario["peak_pump_power_kw"] * IT_ANNUAL_FACTOR
        indoor_kw = scenario["peak_indoor_equipment_power_kw"] * IT_ANNUAL_FACTOR
        radiator_kw = scenario["peak_engine_radiator_power_kw"] * IT_ANNUAL_FACTOR
        non_it_kw = acc_kw + pump_kw + indoor_kw + radiator_kw
        it_loss_kw = it_kw / IT_EFFICIENCY - it_kw
        mep_loss_kw = non_it_kw / MEP_EFFICIENCY - non_it_kw
        facility_kw = it_kw + non_it_kw + it_loss_kw + mep_loss_kw
        hourly_results.append({
            "hour_index": index,
            "dry_bulb_C": oat_c,
            "IT_load_kW": it_kw,
            "acc_power_kW": acc_kw,
            "acc_temperature_power_factor": acc_factor,
            "acc_curve_source": "Annual_PUE_detailed_calculation_JUNO Field.xlsx:05_Appendix01:H31:H8790",
            "pump_power_kW": pump_kw,
            "indoor_equipment_power_kW": indoor_kw,
            "engine_radiator_power_kW": radiator_kw,
            "it_electrical_loss_kW": it_loss_kw,
            "mep_electrical_loss_kW": mep_loss_kw,
            "electrical_loss_kW": it_loss_kw + mep_loss_kw,
            "total_facility_power_kW": facility_kw,
            "hourly_PUE": facility_kw / it_kw if it_kw > 0 else None,
        })

    def total(field):
        return sum(float(row.get(field) or 0.0) for row in hourly_results)
    annual_it = total("IT_load_kW")
    annual_facility = total("total_facility_power_kW")
    annual_acc = total("acc_power_kW")
    annual_pump = total("pump_power_kW")
    annual_indoor = total("indoor_equipment_power_kW")
    annual_radiator = total("engine_radiator_power_kW")
    annual_it_loss = total("it_electrical_loss_kW")
    annual_mep_loss = total("mep_electrical_loss_kW")
    peak_acc = max(hourly_results, key=lambda row: row["acc_power_kW"])
    peak_facility = max(hourly_results, key=lambda row: row["total_facility_power_kW"])
    peak_pue = max(hourly_results, key=lambda row: row["hourly_PUE"])
    min_pue = min(hourly_results, key=lambda row: row["hourly_PUE"])
    annual_pue = annual_facility / annual_it
    average = lambda energy: energy / ANNUAL_HOURS
    annual_results = {
        "calculation_mode": "excel_replicated_hourly",
        "annual_average_PUE": annual_pue,
        "annual_IT_energy_kWh": annual_it,
        "annual_it_energy_kWh": annual_it,
        "annual_facility_energy_kWh": annual_facility,
        "annual_acc_energy_kWh": annual_acc,
        "annual_pump_energy_kWh": annual_pump,
        "annual_indoor_equipment_energy_kWh": annual_indoor,
        "annual_engine_radiator_energy_kWh": annual_radiator,
        "annual_it_electrical_loss_kWh": annual_it_loss,
        "annual_mep_electrical_loss_kWh": annual_mep_loss,
        "annual_electrical_loss_kWh": annual_it_loss + annual_mep_loss,
        "annual_total_cooling_system_energy_kWh": annual_acc + annual_pump + annual_indoor + annual_radiator,
        "average_IT_power_kW": average(annual_it),
        "average_acc_power_kW": average(annual_acc),
        "average_pump_power_kW": average(annual_pump),
        "average_indoor_equipment_power_kW": average(annual_indoor),
        "average_engine_radiator_power_kW": average(annual_radiator),
        "average_it_electrical_loss_kW": average(annual_it_loss),
        "average_mep_electrical_loss_kW": average(annual_mep_loss),
        "average_facility_power_kW": average(annual_facility),
        "min_hourly_PUE": min_pue["hourly_PUE"],
        "max_hourly_PUE": peak_pue["hourly_PUE"],
        "max_acc_power_kW": peak_acc["acc_power_kW"],
        "scenario_peak_acc_power_kW": scenario["peak_acc_power_kw"],
        "acc_peak_to_scenario_peak_ratio": peak_acc["acc_power_kW"] / scenario["peak_acc_power_kw"],
        "excel_hourly_acc_factor_average": average(sum(row["acc_temperature_power_factor"] for row in hourly_results)),
    }
    return {
        "calculation_mode": "excel_replicated_hourly",
        "calculation_mode_label": "Excel Replicated Hourly Mode",
        "calculation_note": "Hourly ACC factor replicates 05_Appendix01 column H; other hourly powers are derived from the workbook scenario and electrical-loss formulas.",
        "project": {**project, "scenario_name": scenario["name"], "active_units": scenario["active_units"]},
        "hourly_results": hourly_results,
        "annual_results": annual_results,
        "peak_results": {
            "peak_PUE": peak_pue["hourly_PUE"],
            "peak_PUE_hour_index": peak_pue["hour_index"],
            "peak_PUE_outdoor_dry_bulb_C": peak_pue["dry_bulb_C"],
            "peak_hour_index": peak_facility["hour_index"],
            "peak_outdoor_dry_bulb_C": peak_facility["dry_bulb_C"],
            "peak_IT_load_kW": peak_facility["IT_load_kW"],
            "peak_total_facility_power_kW": peak_facility["total_facility_power_kW"],
            "peak_facility_hour_PUE": peak_facility["hourly_PUE"],
        },
        "benchmark_components": {
            "scenario": scenario["name"], "annual_hours": ANNUAL_HOURS,
            "it_annual_load_factor": IT_ANNUAL_FACTOR,
            "acc_annual_temperature_factor": annual_results["excel_hourly_acc_factor_average"],
            "it_efficiency": IT_EFFICIENCY, "mep_efficiency": MEP_EFFICIENCY,
            "component_average_kW": {
                "IT": average(annual_it), "ACC": average(annual_acc), "pump": average(annual_pump),
                "indoor_CDU_RTC_MAU_equivalent": average(annual_indoor),
                "engine_radiator": average(annual_radiator), "IT_electrical_loss": average(annual_it_loss),
                "MEP_electrical_loss": average(annual_mep_loss), "facility": average(annual_facility),
            },
        },
    }


def compute_acc_excel_benchmark(input_obj):
    """Return an annual/project result using the benchmark workbook method."""
    if not isinstance(input_obj, dict):
        return {"error": "input is not an object"}
    scenario_key = str(input_obj.get("scenario_name") or "Normal").strip().lower()
    scenario = SCENARIOS.get(scenario_key)
    if scenario is None:
        return {"error": f"unsupported benchmark scenario: {scenario_key}"}

    project = input_obj.get("project", {}) if isinstance(input_obj.get("project"), dict) else {}
    design_it_kw = float(project.get("design_it_load_kW") or 4400.0)
    it_kw = design_it_kw * IT_ANNUAL_FACTOR
    acc_kw = scenario["peak_acc_power_kw"] * ACC_ANNUAL_FACTOR
    pump_kw = scenario["peak_pump_power_kw"] * IT_ANNUAL_FACTOR
    indoor_kw = scenario["peak_indoor_equipment_power_kw"] * IT_ANNUAL_FACTOR
    radiator_kw = scenario["peak_engine_radiator_power_kw"] * IT_ANNUAL_FACTOR
    non_it_kw = acc_kw + pump_kw + indoor_kw + radiator_kw
    it_loss_kw = it_kw / IT_EFFICIENCY - it_kw
    mep_loss_kw = non_it_kw / MEP_EFFICIENCY - non_it_kw
    facility_kw = it_kw + non_it_kw + it_loss_kw + mep_loss_kw
    pue = facility_kw / it_kw if it_kw > 0 else None

    hourly_row = {
        "hour_index": 1,
        "IT_load_kW": it_kw,
        "acc_power_kW": acc_kw,
        "acc_temperature_power_factor": ACC_ANNUAL_FACTOR,
        "acc_curve_source": "excel_benchmark_annual_factor",
        "pump_power_kW": pump_kw,
        "indoor_equipment_power_kW": indoor_kw,
        "engine_radiator_power_kW": radiator_kw,
        "it_electrical_loss_kW": it_loss_kw,
        "mep_electrical_loss_kW": mep_loss_kw,
        "electrical_loss_kW": it_loss_kw + mep_loss_kw,
        "total_facility_power_kW": facility_kw,
        "hourly_PUE": pue,
    }
    hourly_results = [{**hourly_row, "hour_index": hour} for hour in range(1, ANNUAL_HOURS + 1)]
    annual_results = {
        "calculation_mode": "excel_benchmark_compatible",
        "annual_average_PUE": pue,
        "annual_IT_energy_kWh": it_kw * ANNUAL_HOURS,
        "annual_it_energy_kWh": it_kw * ANNUAL_HOURS,
        "annual_facility_energy_kWh": facility_kw * ANNUAL_HOURS,
        "annual_acc_energy_kWh": acc_kw * ANNUAL_HOURS,
        "annual_pump_energy_kWh": pump_kw * ANNUAL_HOURS,
        "annual_indoor_equipment_energy_kWh": indoor_kw * ANNUAL_HOURS,
        "annual_engine_radiator_energy_kWh": radiator_kw * ANNUAL_HOURS,
        "annual_it_electrical_loss_kWh": it_loss_kw * ANNUAL_HOURS,
        "annual_mep_electrical_loss_kWh": mep_loss_kw * ANNUAL_HOURS,
        "annual_electrical_loss_kWh": (it_loss_kw + mep_loss_kw) * ANNUAL_HOURS,
        "annual_total_cooling_system_energy_kWh": non_it_kw * ANNUAL_HOURS,
        "average_IT_power_kW": it_kw,
        "average_acc_power_kW": acc_kw,
        "average_pump_power_kW": pump_kw,
        "average_indoor_equipment_power_kW": indoor_kw,
        "average_engine_radiator_power_kW": radiator_kw,
        "average_it_electrical_loss_kW": it_loss_kw,
        "average_mep_electrical_loss_kW": mep_loss_kw,
        "average_facility_power_kW": facility_kw,
        "min_hourly_PUE": pue,
        "max_hourly_PUE": pue,
    }
    return {
        "calculation_mode": "excel_benchmark_compatible",
        "calculation_mode_label": "Excel Benchmark Compatible Mode",
        "calculation_note": "This result uses Excel Benchmark Compatible Mode based on scenario peak power and annual temperature factor.",
        "project": {**project, "scenario_name": scenario["name"], "active_units": scenario["active_units"]},
        "hourly_results": hourly_results,
        "annual_results": annual_results,
        "peak_results": {
            "peak_PUE": pue,
            "peak_PUE_hour_index": 1,
            "peak_hour_index": 1,
            "peak_IT_load_kW": it_kw,
            "peak_total_facility_power_kW": facility_kw,
        },
        "benchmark_components": {
            "scenario": scenario["name"],
            "annual_hours": ANNUAL_HOURS,
            "it_annual_load_factor": IT_ANNUAL_FACTOR,
            "acc_annual_temperature_factor": ACC_ANNUAL_FACTOR,
            "it_efficiency": IT_EFFICIENCY,
            "mep_efficiency": MEP_EFFICIENCY,
            "component_average_kW": {
                "IT": it_kw,
                "ACC": acc_kw,
                "pump": pump_kw,
                "indoor_CDU_RTC_MAU_equivalent": indoor_kw,
                "engine_radiator": radiator_kw,
                "IT_electrical_loss": it_loss_kw,
                "MEP_electrical_loss": mep_loss_kw,
                "facility": facility_kw,
            },
        },
        "validation": {"checks": {"excel_benchmark_equations_applied": True}, "warnings": []},
    }
