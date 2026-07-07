"""Reusable hourly simulation loop skeleton.

Phase 12B introduces loop ownership only. Engineering calculations remain in
legacy solver.py paths until a later explicit migration phase.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HourlyContext:
    hour_index: int
    outdoor_temperature: float | None = None
    wet_bulb_temperature: float | None = None
    it_load: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class SimulationHooks:
    """Optional extension points for future hourly calculators."""

    def before_hour(self, hourly_context):
        pass

    def after_hour(self, hourly_context, result):
        pass


class HourlySimulationEngine:
    """Own the hourly loop without performing engineering calculations."""

    def __init__(self, hours=None, hooks=None):
        self.hours = list(hours or [])
        self.hooks = hooks or SimulationHooks()
        self.results = []

    def before_simulation(self):
        pass

    def after_simulation(self):
        pass

    def run_single_hour(self, hourly_context):
        self.hooks.before_hour(hourly_context)
        result = {
            "hour_index": hourly_context.hour_index,
            "metadata": dict(hourly_context.metadata),
        }
        self.hooks.after_hour(hourly_context, result)
        return result

    def run_hours(self, hours=None):
        active_hours = list(self.hours if hours is None else hours)
        self.before_simulation()
        self.results = [self.run_single_hour(hour) for hour in active_hours]
        self.after_simulation()
        return self.results
