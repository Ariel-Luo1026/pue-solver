"""Topology-independent equipment performance adapters."""

from equipment_performance.performance_dispatcher import (
    EquipmentPerformanceDispatchError,
    calculate_equipment_performance,
    dispatch_performance_adapter,
)
from equipment_performance.performance_result import PerformanceResult

__all__ = [
    "EquipmentPerformanceDispatchError",
    "PerformanceResult",
    "calculate_equipment_performance",
    "dispatch_performance_adapter",
]
