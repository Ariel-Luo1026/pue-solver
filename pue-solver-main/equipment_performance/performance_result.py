"""Standard equipment performance result schema."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class PerformanceResult:
    """Unified result for equipment performance adapter calls."""

    equipment_id: str
    equipment_type: str
    input_conditions: dict[str, Any] = field(default_factory=dict)
    performance: dict[str, Any] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        """Return a plain dictionary suitable for JSON/report serialization."""
        return asdict(self)


def standard_performance(
    equipment_id,
    equipment_type,
    input_conditions=None,
    performance=None,
    diagnostics=None,
):
    """Create a PerformanceResult with normalized top-level dictionaries."""
    return PerformanceResult(
        equipment_id=str(equipment_id or ""),
        equipment_type=str(equipment_type or "").strip().upper(),
        input_conditions=dict(input_conditions or {}),
        performance=dict(performance or {}),
        diagnostics=dict(diagnostics or {}),
    )
