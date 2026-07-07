"""Unit-level equipment quantity framework.

Phase 13A defines quantity resolution only. It is not connected to solver.py,
the UI, reports, exported HTML, or any ACC calculation path.
"""

from dataclasses import dataclass, field, replace
from math import ceil
from typing import Any

from equipment_registry import canonicalize_equipment_id


QUANTITY_MODES = {"auto", "manual"}


@dataclass
class UnitQuantityConfig:
    equipment_id: str | None = None
    quantity_mode: str = "auto"
    auto_unit_capacity_kw: float | None = None
    design_load_kw: float | None = None
    auto_calculated_units: int = 0
    manual_installed_units: int | None = None
    manual_running_units: int | None = None
    manual_standby_units: int | None = None
    effective_installed_units: int = 0
    effective_running_units: int = 0
    effective_standby_units: int = 0
    redundancy_mode: str | None = None
    notes: list[str] = field(default_factory=list)


def calculate_auto_units(design_load_kw, unit_capacity_kw):
    """Return ceil(design load / unit capacity), or 0 for invalid inputs."""
    design_load = _positive_float_or_none(design_load_kw)
    unit_capacity = _positive_float_or_none(unit_capacity_kw)
    if design_load is None or unit_capacity is None:
        return 0
    return int(ceil(design_load / unit_capacity))


def resolve_unit_quantity(config):
    """Resolve auto/manual quantity settings into effective unit counts."""
    if not isinstance(config, UnitQuantityConfig):
        raise TypeError("config must be a UnitQuantityConfig")

    notes = list(config.notes)
    equipment_id = canonicalize_equipment_id(config.equipment_id)
    quantity_mode = str(config.quantity_mode or "auto").lower()
    if quantity_mode not in QUANTITY_MODES:
        notes.append(f"Unknown quantity_mode {config.quantity_mode!r}; defaulted to auto.")
        quantity_mode = "auto"

    if quantity_mode == "auto":
        auto_units = calculate_auto_units(config.design_load_kw, config.auto_unit_capacity_kw)
        if auto_units == 0:
            notes.append("Auto quantity could not be calculated because design load or unit capacity is missing or invalid.")
        return replace(
            config,
            equipment_id=equipment_id,
            quantity_mode="auto",
            auto_calculated_units=auto_units,
            effective_installed_units=auto_units,
            effective_running_units=auto_units,
            effective_standby_units=0,
            redundancy_mode="N",
            notes=notes,
        )

    installed = _non_negative_int_or_none(config.manual_installed_units)
    running = _non_negative_int_or_none(config.manual_running_units)
    standby = _non_negative_int_or_none(config.manual_standby_units)

    if installed is None:
        installed = 0
        notes.append("Manual installed units are missing or invalid; defaulted to 0.")
    if running is None:
        running = installed
        notes.append("Manual running units not provided; defaulted to installed units.")
    if standby is None:
        standby = max(installed - running, 0)
        notes.append("Manual standby units not provided; inferred from installed - running.")

    if running > installed:
        notes.append("Manual running units exceed installed units; quantity marked custom.")
    if standby != installed - running:
        notes.append("Manual standby units are inconsistent with installed - running; quantity marked custom.")

    return replace(
        config,
        equipment_id=equipment_id,
        quantity_mode="manual",
        effective_installed_units=installed,
        effective_running_units=running,
        effective_standby_units=standby,
        redundancy_mode=_infer_redundancy_mode(installed, running, standby),
        notes=notes,
    )


def build_unit_quantity_for_equipment(
    equipment_id,
    project_input,
    unit_capacity_kw=None,
    design_load_kw=None,
):
    """Build and resolve quantity config for one unit-level equipment item."""
    canonical_id = canonicalize_equipment_id(equipment_id)
    project_input = project_input if isinstance(project_input, dict) else {}
    overrides = project_input.get("equipment_quantity_overrides", {})
    override = _find_quantity_override(overrides, canonical_id)

    config = UnitQuantityConfig(
        equipment_id=canonical_id,
        quantity_mode=override.get("quantity_mode", "auto"),
        auto_unit_capacity_kw=override.get("auto_unit_capacity_kw", unit_capacity_kw),
        design_load_kw=override.get("design_load_kw", design_load_kw),
        manual_installed_units=override.get("manual_installed_units"),
        manual_running_units=override.get("manual_running_units"),
        manual_standby_units=override.get("manual_standby_units"),
    )
    return resolve_unit_quantity(config)


def _find_quantity_override(overrides, canonical_id):
    if not isinstance(overrides, dict):
        return {}
    for equipment_id, override in overrides.items():
        if canonicalize_equipment_id(equipment_id) == canonical_id and isinstance(override, dict):
            return dict(override)
    return {}


def _positive_float_or_none(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _non_negative_int_or_none(value):
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _infer_redundancy_mode(installed, running, standby):
    if running > installed or standby != installed - running:
        return "custom"
    if standby == 0:
        return "N"
    if standby == 1:
        return "N+1"
    if standby == 2:
        return "N+2"
    return "custom"
