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
