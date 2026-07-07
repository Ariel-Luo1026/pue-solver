"""Stable calculator API models.

Phase 11.5 defines shared dataclasses only. These models do not invoke solver
logic and are not wired into existing UI/report/calculation paths.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CalculationContext:
    configuration_name: str | None = None
    topology_id: str | None = None
    topology_display_name: str | None = None
    cooling_system_type: str | None = None
    power_source: str | None = None
    unit_capacity: float | int | str | None = None
    solver_mode: str | None = None
    equipment: list[dict[str, Any]] = field(default_factory=list)
    performance_requirements: list[dict[str, Any]] = field(default_factory=list)
    configuration_summary: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CalculationResult:
    annual_results: dict[str, Any] = field(default_factory=dict)
    hourly_results: list[dict[str, Any]] = field(default_factory=list)
    report_context: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    execution_metadata: dict[str, Any] = field(default_factory=dict)
    solver_version: str | None = None
    calculator_id: str | None = None


@dataclass
class HourlyResult:
    hour_index: int | None = None
    it_load_kw: float | None = None
    outdoor_dry_bulb_c: float | None = None
    outdoor_wet_bulb_c: float | None = None
    cooling_power_kw: float | None = None
    pump_power_kw: float | None = None
    fan_power_kw: float | None = None
    electrical_loss_kw: float | None = None
    auxiliary_power_kw: float | None = None
    total_facility_power_kw: float | None = None
    hourly_pue: float | None = None
    equipment_results: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def make_hourly_result(**kwargs):
    """Return a standardized HourlyResult with safe defaults."""
    return HourlyResult(**kwargs)


@dataclass
class AnnualResult:
    annual_average_pue: float | None = None
    annual_it_energy_kwh: float | None = None
    annual_facility_energy_kwh: float | None = None
    annual_cooling_energy_kwh: float | None = None
    annual_chiller_energy_kwh: float | None = None
    annual_heat_rejection_energy_kwh: float | None = None
    annual_pump_energy_kwh: float | None = None
    annual_fan_energy_kwh: float | None = None
    annual_electrical_loss_kwh: float | None = None
    annual_auxiliary_energy_kwh: float | None = None
    peak_total_facility_power_kw: float | None = None
    min_hourly_pue: float | None = None
    max_hourly_pue: float | None = None
    equipment_energy_breakdown: dict[str, Any] = field(default_factory=dict)
    monthly_average_pue: list[float] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def make_annual_result(**kwargs):
    """Return a standardized AnnualResult with safe defaults."""
    return AnnualResult(**kwargs)


@dataclass
class CalculatorCapability:
    calculator_id: str
    display_name: str
    supported_topologies: list[str] = field(default_factory=list)
    supported_solver_modes: list[str] = field(default_factory=list)
    implementation_status: str = "placeholder"
