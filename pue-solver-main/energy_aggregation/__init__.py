"""Topology-independent annual energy aggregation helpers."""

from energy_aggregation.annual_energy_aggregator import (
    AnnualEnergyAggregationError,
    aggregate_annual_energy,
)
from energy_aggregation.energy_result import AnnualEnergyResult

__all__ = [
    "AnnualEnergyAggregationError",
    "AnnualEnergyResult",
    "aggregate_annual_energy",
]
