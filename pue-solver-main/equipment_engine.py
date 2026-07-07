"""Unified Configuration Library equipment engine.

The engine loads Solver_Curve previews once, caches them, and provides
structured lookup results for future equipment migrations.
"""

from dataclasses import dataclass, field
from typing import Any

from equipment_curve_lookup import EquipmentOperatingPoint, lookup_equipment_curve
from equipment_curve_reader import (
    EquipmentCurvePreview,
    preview_from_curve_dict,
    read_equipment_solver_curve,
)


@dataclass
class EquipmentEngineConfig:
    configuration_path: str | None = None
    preloaded_curves: dict[str, dict[str, Any]] = field(default_factory=dict)
    preloaded_previews: dict[str, EquipmentCurvePreview] = field(default_factory=dict)


class ConfigurationLibraryEquipmentEngine:
    """Reusable equipment curve lookup engine with preview caching."""

    def __init__(self, config: EquipmentEngineConfig | str | None = None, **kwargs):
        if isinstance(config, EquipmentEngineConfig):
            self.config = config
        elif isinstance(config, str):
            self.config = EquipmentEngineConfig(configuration_path=config, **kwargs)
        elif config is None:
            self.config = EquipmentEngineConfig(**kwargs)
        else:
            raise TypeError("config must be EquipmentEngineConfig, configuration path string, or None")
        self._preview_cache: dict[str, EquipmentCurvePreview] = {}

    def load_equipment(self, equipment_id):
        equipment_id = str(equipment_id)
        if equipment_id in self._preview_cache:
            return self._preview_cache[equipment_id]
        if equipment_id in self.config.preloaded_previews:
            preview = self.config.preloaded_previews[equipment_id]
        elif equipment_id in self.config.preloaded_curves:
            preview = preview_from_curve_dict(
                equipment_id,
                self.config.preloaded_curves[equipment_id],
                source_workbook="preloaded_curve_library",
                source_sheet="Solver_Curve",
            )
        elif self.config.configuration_path:
            preview = read_equipment_solver_curve(self.config.configuration_path, equipment_id)
        else:
            preview = EquipmentCurvePreview(
                equipment_id=equipment_id,
                errors=[f"No Configuration Library path or preloaded curve available for {equipment_id!r}."],
            )
        self._preview_cache[equipment_id] = preview
        return preview

    def lookup_power(self, equipment_id, load_ratio, ambient_C=None):
        preview = self.load_equipment(equipment_id)
        return lookup_equipment_curve(
            preview,
            EquipmentOperatingPoint(load_ratio=load_ratio, ambient_C=ambient_C),
        )

    def lookup_electrical_loss(self, equipment_id, load_ratio, base_power_kW=None):
        preview = self.load_equipment(equipment_id)
        return lookup_equipment_curve(
            preview,
            EquipmentOperatingPoint(load_ratio=load_ratio, base_power_kW=base_power_kW),
        )

    @property
    def cache_size(self):
        return len(self._preview_cache)
