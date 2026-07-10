"""Audit helpers for Configuration Library Direct Mode results.

This module validates result dictionaries only. It does not perform equipment
calculation, alter result values, print, log, or call solver paths.
"""

from dataclasses import dataclass, field
import json
from typing import Any


DIRECT_MODE_ALLOWED_SOURCES = {
    "acc_curve_source": {"configuration_library_solver_curve", "acc_v2_solver_curve_direct"},
    "chw_pump_curve_source": {"configuration_library_solver_curve"},
    "mau_curve_source": {"configuration_library_solver_curve"},
    "rtc_curve_source": {"configuration_library_solver_curve"},
    "cdu_curve_source": {"configuration_library_solver_curve"},
    "electrical_distribution_curve_source": {"configuration_library_solver_curve"},
    "engine_curve_source": {"configuration_library_solver_curve"},
    "engine_radiator_curve_source": {"configuration_library_solver_curve"},
}

LEGACY_TERMS = (
    "legacy_pump_curve_fallback",
    "legacy_non_configuration_mode",
    "terminal_fan_curve_source",
    "experimental_acc_ambient_shape_annual_calibration",
    "legacy electrical fallback",
)

CALIBRATION_TERMS = (
    "calibrated",
    "annual calibration",
    "annual energy performance calibration",
    "benchmark target",
    "weather-driven sensitivity",
    "fallback to legacy",
)

ENERGY_FIELDS = {
    "annual_acc_energy_kWh": ("acc_power_kW",),
    "annual_pump_energy_kWh": ("pump_power_kW", "chw_pump_power_kW"),
    "annual_mau_energy_kWh": ("mau_power_kW",),
    "annual_rtc_energy_kWh": ("rtc_power_kW",),
    "annual_cdu_energy_kWh": ("cdu_power_kW",),
    "annual_engine_energy_kWh": ("engine_power_kW", "engine_output_kW"),
    "annual_engine_radiator_energy_kWh": ("engine_radiator_power_kW",),
    "annual_electrical_loss_kWh": ("electrical_loss_kW",),
}


@dataclass
class DirectModeAuditResult:
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    equipment_sources: dict[str, Any] = field(default_factory=dict)
    energy_consistency: dict[str, Any] = field(default_factory=dict)
    legacy_terms_found: list[str] = field(default_factory=list)


def _num(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _sum_hourly(hourly_rows, candidate_fields):
    total = 0.0
    for row in hourly_rows:
        if not isinstance(row, dict):
            continue
        value = None
        for field_name in candidate_fields:
            if field_name in row:
                value = row.get(field_name)
                break
        total += _num(value, 0.0)
    return total


def _term_scan(result):
    serialized = json.dumps(result, sort_keys=True, default=str).lower()
    return [term for term in LEGACY_TERMS + CALIBRATION_TERMS if term in serialized]


def audit_direct_mode_result(result, tolerance=1e-4):
    errors = []
    warnings = []
    equipment_sources = {}
    energy_consistency = {}
    legacy_terms_found = []

    if not isinstance(result, dict):
        return DirectModeAuditResult(
            passed=False,
            errors=["Direct Mode audit expected a result dictionary."],
        )
    if result.get("error"):
        errors.append(f"Direct Mode result contains error: {result.get('error')}")

    hourly_rows = result.get("hourly_results", [])
    annual = result.get("annual_results", {})
    if not isinstance(hourly_rows, list) or not hourly_rows:
        errors.append("Direct Mode result has no hourly_results rows.")
        hourly_rows = []
    if not isinstance(annual, dict) or not annual:
        errors.append("Direct Mode result has no annual_results dictionary.")
        annual = {}

    first_hour = hourly_rows[0] if hourly_rows and isinstance(hourly_rows[0], dict) else {}
    for source_field, allowed_values in DIRECT_MODE_ALLOWED_SOURCES.items():
        source_value = annual.get(source_field, first_hour.get(source_field))
        equipment_sources[source_field] = source_value
        if source_value not in allowed_values:
            allowed_text = ", ".join(sorted(allowed_values))
            errors.append(f"{source_field}={source_value!r}; expected {allowed_text}.")

    legacy_terms_found = _term_scan(result)
    if legacy_terms_found:
        errors.append(f"Direct Mode result contains forbidden terms: {', '.join(legacy_terms_found)}.")

    for annual_field, hourly_fields in ENERGY_FIELDS.items():
        if annual_field not in annual:
            errors.append(f"{annual_field} missing from annual_results.")
            continue
        hourly_sum = _sum_hourly(hourly_rows, hourly_fields)
        annual_value = _num(annual.get(annual_field), None)
        delta = None if annual_value is None else abs(annual_value - hourly_sum)
        passed = annual_value is not None and delta <= tolerance
        energy_consistency[annual_field] = {
            "annual_value": annual_value,
            "hourly_sum": hourly_sum,
            "delta": delta,
            "passed": passed,
        }
        if not passed:
            errors.append(f"{annual_field}={annual_value!r} does not match hourly sum {hourly_sum!r}.")

    for index, row in enumerate(hourly_rows):
        if not isinstance(row, dict):
            continue
        mau_power = _num(row.get("mau_power_kW"), None)
        terminal_fan_power = _num(row.get("terminal_fan_power_kW"), None)
        airflow_power = _num(row.get("airflow_power_kW"), None)
        if mau_power is None:
            errors.append(f"hour {index}: mau_power_kW missing.")
            continue
        if terminal_fan_power is not None and abs(terminal_fan_power) > tolerance:
            errors.append(f"hour {index}: terminal_fan_power_kW duplicates mau_power_kW; expected 0 when MAU curve is counted in white_space_equipment_power_kW.")
        if airflow_power is not None and abs(airflow_power) > tolerance:
            errors.append(f"hour {index}: airflow_power_kW duplicates mau_power_kW; expected 0 when MAU curve is counted in white_space_equipment_power_kW.")
        direct_power = (
            _num(row.get("cdu_power_kW"), 0.0)
            + _num(row.get("rtc_power_kW"), 0.0)
            + _num(row.get("mau_power_kW"), 0.0)
            + _num(row.get("engine_radiator_power_kW"), 0.0)
        )
        if direct_power > 0 and abs(_num(row.get("auxiliary_power_kW"), 0.0) - direct_power) <= tolerance:
            errors.append(f"hour {index}: auxiliary_power_kW appears to hide direct equipment power.")

    return DirectModeAuditResult(
        passed=not errors,
        errors=errors,
        warnings=warnings,
        equipment_sources=equipment_sources,
        energy_consistency=energy_consistency,
        legacy_terms_found=legacy_terms_found,
    )
