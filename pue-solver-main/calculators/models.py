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
class CalculatorCapability:
    calculator_id: str
    display_name: str
    supported_topologies: list[str] = field(default_factory=list)
    supported_solver_modes: list[str] = field(default_factory=list)
    implementation_status: str = "placeholder"
