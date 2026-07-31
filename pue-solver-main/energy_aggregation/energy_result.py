"""Standard annual energy result schema."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class AnnualEnergyResult:
    """Unified annual energy and PUE breakdown."""

    annual_it_energy_kWh: float
    annual_facility_energy_kWh: float
    annual_cooling_energy_kWh: float
    components: dict[str, dict[str, Any]] = field(default_factory=dict)
    PUE: float | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self):
        """Return a plain dictionary suitable for reports and JSON export."""
        return asdict(self)
