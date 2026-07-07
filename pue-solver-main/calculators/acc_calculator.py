"""ACC calculator wrapper and input parser.

Phase 12A begins migrating ACC input parsing only. ACC formulas remain in the
legacy solver.py path, and ACCCalculator.run() is still a thin runtime wrapper
around the existing public entry point.
"""

from copy import deepcopy
from dataclasses import dataclass, field
import re
from typing import Any

from calculators.base_calculator import BaseCalculator
from calculators.hourly_engine import HourlySimulationEngine


@dataclass
class ACCInputContext:
    project_name: str | None = None
    location: Any = None
    cooling_system_type: str | None = None
    power_source: str | None = None
    unit_capacity_kw: float | None = None
    unit_count: int | None = None
    design_it_load_kw: float | None = None
    hourly_it_load_kw: list[float] = field(default_factory=list)
    weather_hours: int | None = None
    scenario: str | None = None
    active_engines: int | None = None
    raw_project_input: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def build_acc_input_context(project_input):
    """Parse ACC project input metadata without calculating PUE or energy."""
    source = project_input if isinstance(project_input, dict) else {}
    project = _dict_at(source, "project")
    weather = _dict_at(source, "weather")
    it_load = _dict_at(project, "it_load")
    cooling = _get_path(source, ["equipment", "cooling"], {})
    if not isinstance(cooling, dict):
        cooling = {}

    hourly_it_load = _numeric_list(it_load.get("hourly_it_load_kW"))
    dry_bulb = _numeric_list(_get_path(weather, ["hourly_data", "dry_bulb_C"], []))
    wet_bulb = _numeric_list(_get_path(weather, ["hourly_data", "wet_bulb_C"], []))
    hour_index = _get_path(weather, ["hourly_data", "hour_index"], [])
    weather_hours = max(
        len(dry_bulb),
        len(wet_bulb),
        len(hour_index) if isinstance(hour_index, list) else 0,
    ) or None

    unit_capacity_kw = _first_number(
        cooling.get("cooling_unit_capacity_kW"),
        cooling.get("cooling_unit_capacity_kw"),
        _get_path(project, ["it_load", "cooling_unit_capacity_kW"]),
        source.get("cooling_unit_capacity_kW"),
        source.get("cooling_unit_capacity_kw"),
    )
    if unit_capacity_kw is None:
        unit_capacity_kw = _capacity_to_kw(_first_present(
            source,
            ("cooling_unit_capacity_mw",),
            ("Cooling Unit Capacity",),
            ("configuration_library", "cooling_unit_capacity_mw"),
        ))

    unit_count = _as_int(_first_number(
        cooling.get("cooling_unit_count"),
        project.get("cooling_unit_count"),
        it_load.get("cooling_unit_count"),
    ))
    design_it_load_kw = _first_number(
        it_load.get("design_it_load_kW"),
        project.get("design_it_load_kW"),
        max(hourly_it_load) if hourly_it_load else None,
    )
    cooling_system_type = _first_present(
        source,
        ("cooling_system_type",),
        ("Cooling System Type",),
        ("configuration_library", "cooling_system_type"),
    ) or project.get("cooling_system_type") or "ACC"
    power_source = _first_present(
        source,
        ("power_source",),
        ("Power Source",),
        ("configuration_library", "power_source"),
    ) or project.get("power_source")

    return ACCInputContext(
        project_name=project.get("name") or source.get("configuration_name"),
        location=deepcopy(project.get("location")),
        cooling_system_type=cooling_system_type,
        power_source=power_source,
        unit_capacity_kw=unit_capacity_kw,
        unit_count=unit_count,
        design_it_load_kw=design_it_load_kw,
        hourly_it_load_kw=hourly_it_load,
        weather_hours=weather_hours,
        scenario=project.get("scenario_name") or _get_path(source, ["library_context", "scenario_name"]),
        active_engines=_as_int(project.get("active_units")),
        raw_project_input=deepcopy(source),
        metadata={
            "parser": "ACCCalculator.build_acc_input_context",
            "formula_migration": False,
            "legacy_run_path": "solver.compute_pue_project",
        },
    )


class ACCCalculator(BaseCalculator):
    calculator_id = "acc_calculator"
    display_name = "ACC Calculator"
    supported_topology_ids = ["acc"]
    supported_solver_modes = ["acc_hourly"]

    def build_context(self, project_input):
        return build_acc_input_context(project_input)

    def validate(self, project_input):
        context = self.build_context(project_input)
        warnings = []
        if context.cooling_system_type and context.cooling_system_type != "ACC":
            warnings.append(f"Expected ACC cooling system type, got {context.cooling_system_type!r}.")
        if not context.hourly_it_load_kw:
            warnings.append("Hourly IT load profile is not present; legacy solver may use fallback behavior.")
        if context.weather_hours is None:
            warnings.append("Weather profile is not present; legacy solver may use fallback behavior.")
        return warnings

    def create_hourly_engine(self, hours=None):
        """Create the future hourly loop engine without wiring it into run()."""
        return HourlySimulationEngine(hours=hours)

    def run(self, project_input):
        from solver import compute_pue_project

        return compute_pue_project(project_input)


def _dict_at(source, key):
    value = source.get(key, {}) if isinstance(source, dict) else {}
    return value if isinstance(value, dict) else {}


def _get_path(source, path, default=None):
    current = source
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def _first_present(source, *paths):
    for path in paths:
        value = _get_path(source, path)
        if value is not None:
            return value
    return None


def _first_number(*values):
    for value in values:
        number = _as_float(value)
        if number is not None:
            return number
    return None


def _as_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value):
    number = _as_float(value)
    return int(number) if number is not None else None


def _numeric_list(values):
    if not isinstance(values, list):
        return []
    numbers = []
    for value in values:
        number = _as_float(value)
        if number is not None:
            numbers.append(number)
    return numbers


def _capacity_to_kw(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) * 1000.0
    text = str(value).strip()
    match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*(MW|KW)?", text, re.IGNORECASE)
    if not match:
        return None
    number = float(match.group(1))
    unit = (match.group(2) or "MW").lower()
    return number if unit == "kw" else number * 1000.0
