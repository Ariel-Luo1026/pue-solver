"""Map legacy solver result dictionaries to standardized calculator models.

Phase 12E creates mapping helpers only. They are not connected to
ACCCalculator.run() or any UI/report/export path.
"""

from copy import deepcopy

from calculators.models import (
    CalculationResult,
    make_annual_result,
    make_hourly_result,
)


def map_legacy_hourly_result(row):
    """Map one legacy hourly result row to HourlyResult."""
    row = row if isinstance(row, dict) else {}
    return make_hourly_result(
        hour_index=_first_present(row, "hour_index", "hour", "Hour"),
        it_load_kw=_first_present(row, "IT_load_kW", "it_load_kW", "it_load_kw"),
        outdoor_dry_bulb_c=_first_present(row, "dry_bulb_C", "outdoor_dry_bulb_C"),
        outdoor_wet_bulb_c=_first_present(row, "wet_bulb_C", "outdoor_wet_bulb_C"),
        cooling_power_kw=_first_present(row, "cooling_power_kW", "cooling_kw", "chiller_power_kW"),
        pump_power_kw=_first_present(row, "pump_power_kW", "pumps_kw"),
        fan_power_kw=_first_present(row, "fan_power_kW", "airflow_power_kW", "terminal_fan_power_kW"),
        electrical_loss_kw=_first_present(row, "electrical_loss_kW", "power_distribution_loss_kw"),
        auxiliary_power_kw=_first_present(row, "auxiliary_power_kW", "aux_power_kW"),
        total_facility_power_kw=_first_present(row, "total_facility_power_kW", "total_facility_power_kw"),
        hourly_pue=_first_present(row, "hourly_PUE", "hourly_pue", "PUE"),
        equipment_results=deepcopy(row.get("equipment_results", {})) if isinstance(row.get("equipment_results", {}), dict) else {},
        warnings=list(row.get("warnings", [])) if isinstance(row.get("warnings", []), list) else [],
        metadata={"source": "legacy_solver", "raw_keys": sorted(str(key) for key in row)},
    )


def map_legacy_annual_result(annual_results):
    """Map legacy annual result fields to AnnualResult."""
    annual_results = annual_results if isinstance(annual_results, dict) else {}
    return make_annual_result(
        annual_average_pue=_first_present(annual_results, "annual_average_PUE", "annual_average_pue"),
        annual_it_energy_kwh=_first_present(annual_results, "annual_IT_energy_kWh", "annual_it_energy_kWh"),
        annual_facility_energy_kwh=_first_present(annual_results, "annual_facility_energy_kWh"),
        annual_cooling_energy_kwh=_first_present(annual_results, "annual_cooling_energy_kWh"),
        annual_chiller_energy_kwh=_first_present(annual_results, "annual_chiller_energy_kWh"),
        annual_heat_rejection_energy_kwh=_first_present(
            annual_results,
            "annual_heat_rejection_energy_kWh",
            "annual_acc_energy_kWh",
            "annual_engine_radiator_energy_kWh",
        ),
        annual_pump_energy_kwh=_first_present(annual_results, "annual_pump_energy_kWh"),
        annual_fan_energy_kwh=_first_present(
            annual_results,
            "annual_terminal_fan_energy_kWh",
            "annual_fan_energy_kWh",
            "annual_airflow_energy_kWh",
        ),
        annual_electrical_loss_kwh=_first_present(annual_results, "annual_electrical_loss_kWh"),
        annual_auxiliary_energy_kwh=_first_present(
            annual_results,
            "annual_auxiliary_energy_kWh",
            "annual_aux_energy_kWh",
        ),
        peak_total_facility_power_kw=_first_present(
            annual_results,
            "peak_total_facility_power_kW",
            "max_total_facility_power_kW",
        ),
        min_hourly_pue=_first_present(annual_results, "min_hourly_PUE", "min_hourly_pue"),
        max_hourly_pue=_first_present(annual_results, "max_hourly_PUE", "max_hourly_pue"),
        equipment_energy_breakdown=_equipment_energy_breakdown(annual_results),
        monthly_average_pue=list(annual_results.get("monthly_average_PUE", annual_results.get("monthly_average_pue", [])))
        if isinstance(annual_results.get("monthly_average_PUE", annual_results.get("monthly_average_pue", [])), list) else [],
        warnings=list(annual_results.get("warnings", [])) if isinstance(annual_results.get("warnings", []), list) else [],
        metadata={"source": "legacy_solver", "raw_keys": sorted(str(key) for key in annual_results)},
    )


def map_legacy_result(result, calculator_id="legacy_acc"):
    """Map a full legacy solver result dictionary to CalculationResult."""
    result = result if isinstance(result, dict) else {}
    return CalculationResult(
        annual_results=map_legacy_annual_result(result.get("annual_results", {})),
        hourly_results=[
            map_legacy_hourly_result(row)
            for row in result.get("hourly_results", [])
            if isinstance(row, dict)
        ],
        report_context=deepcopy(result.get("report_context", {})) if isinstance(result.get("report_context", {}), dict) else {},
        warnings=list(result.get("warnings", [])) if isinstance(result.get("warnings", []), list) else [],
        errors=list(result.get("errors", [])) if isinstance(result.get("errors", []), list) else [],
        execution_metadata={
            "source": "legacy_solver",
            "legacy_keys": sorted(str(key) for key in result),
        },
        solver_version=result.get("solver_version"),
        calculator_id=calculator_id,
    )


def _first_present(source, *keys):
    for key in keys:
        if key in source and source[key] is not None:
            return source[key]
    return None


def _equipment_energy_breakdown(annual_results):
    mapping = {
        "acc_unit": "annual_acc_energy_kWh",
        "chiller": "annual_chiller_energy_kWh",
        "heat_rejection": "annual_heat_rejection_energy_kWh",
        "pump": "annual_pump_energy_kWh",
        "fan": "annual_terminal_fan_energy_kWh",
        "electrical_distribution": "annual_electrical_loss_kWh",
        "auxiliary": "annual_auxiliary_energy_kWh",
    }
    return {
        equipment_id: annual_results[key]
        for equipment_id, key in mapping.items()
        if key in annual_results and annual_results[key] is not None
    }
