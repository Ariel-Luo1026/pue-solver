"""Future calculation routing adapter.

Phase 7 adapter skeleton. It prepares topology/equipment/performance
context for future dynamic routing, but deliberately does not import or
invoke solver.py and performs no numerical calculations.
"""

from configuration_library_scanner import scan_single_configuration
from configuration_validator import validate_configuration_manifest
from calculators import get_calculator_for_context
from calculators.models import CalculationContext
from performance_requirement_registry import get_topology_performance_requirements
from topology_registry import get_topology_by_cooling_type, get_topology_equipment


def get_calculation_context(project_input):
    """Build a calculation context from project/configuration metadata only."""
    project_input = project_input or {}
    cooling_system_type = _first_present(
        project_input,
        ("cooling_system_type",),
        ("Cooling System Type",),
        ("project", "cooling_system_type"),
        ("project", "Cooling System Type"),
        ("configuration_library", "cooling_system_type"),
        ("configuration_library", "Cooling System Type"),
    )
    power_source = _first_present(
        project_input,
        ("power_source",),
        ("Power Source",),
        ("project", "power_source"),
        ("project", "Power Source"),
        ("configuration_library", "power_source"),
        ("configuration_library", "Power Source"),
    )
    unit_capacity = _first_present(
        project_input,
        ("cooling_unit_capacity_mw",),
        ("Cooling Unit Capacity",),
        ("project", "cooling_unit_capacity_mw"),
        ("project", "cooling_unit_capacity_kW"),
        ("project", "cooling_unit_capacity_kw"),
        ("configuration_library", "cooling_unit_capacity_mw"),
        ("configuration_library", "Cooling Unit Capacity"),
    )
    configuration_name = _first_present(
        project_input,
        ("configuration_name",),
        ("Configuration Name",),
        ("configuration_library", "configuration_name"),
        ("configuration_library", "name"),
        ("project", "configuration_name"),
        ("project", "name"),
    )

    topology = get_topology_by_cooling_type(cooling_system_type) if cooling_system_type else None
    equipment = get_topology_equipment(topology["topology_id"]) if topology else []
    performance_requirements = (
        get_topology_performance_requirements(topology["topology_id"]) if topology else []
    )
    configuration_summary = _configuration_summary(project_input)

    return {
        "topology": topology,
        "equipment": equipment,
        "performance_requirements": performance_requirements,
        "configuration_summary": configuration_summary,
        "calculation_mode": None,
        "power_source": power_source,
        "cooling_system_type": cooling_system_type,
        "unit_capacity": _normalize_unit_capacity(unit_capacity),
        "configuration_name": configuration_name,
    }


def build_standard_context(project_input):
    """Return the standardized CalculationContext dataclass.

    This optional helper preserves existing adapter behavior by wrapping
    get_calculation_context() instead of replacing it.
    """
    context = get_calculation_context(project_input)
    solver_mode = resolve_solver_mode(context)
    topology = context.get("topology") or {}
    return CalculationContext(
        configuration_name=context.get("configuration_name"),
        topology_id=topology.get("topology_id"),
        topology_display_name=topology.get("display_name"),
        cooling_system_type=context.get("cooling_system_type"),
        power_source=context.get("power_source"),
        unit_capacity=context.get("unit_capacity"),
        solver_mode=solver_mode,
        equipment=context.get("equipment") or [],
        performance_requirements=context.get("performance_requirements") or [],
        configuration_summary=context.get("configuration_summary"),
        metadata={
            "source": "calculation_adapter.build_standard_context",
            "legacy_context_available": True,
        },
    )


def resolve_solver_mode(context):
    """Return future solver routing mode without performing calculations."""
    topology = (context or {}).get("topology") or {}
    if topology.get("cooling_system_type") == "ACC":
        return "acc_hourly"
    return "placeholder"


def run_calculation_adapter(project_input):
    """Build context and resolve future solver mode without invoking solver.py."""
    context = get_calculation_context(project_input)
    mode = resolve_solver_mode(context)
    context["calculation_mode"] = mode
    return {
        "context": context,
        "solver_mode": mode,
    }


def run_project_via_adapter(project_input):
    """Run a project through the optional modular adapter path.

    This is not connected to the existing UI. It routes to an implemented
    calculator when one exists and otherwise raises a clear unsupported error.
    """
    context = get_calculation_context(project_input)
    mode = resolve_solver_mode(context)
    context["calculation_mode"] = mode
    context["solver_mode"] = mode
    calculator = get_calculator_for_context(context)
    if calculator is None:
        topology_id = (context.get("topology") or {}).get("topology_id")
        raise NotImplementedError(
            f"No calculator implemented for topology {topology_id} / solver mode {mode}"
        )
    return calculator.run(project_input)


def get_calculator_for_project(project_input):
    """Return matching calculator metadata for a project input, if any.

    This prepares future routing only. It does not call calculator.run() and
    does not perform any numerical calculation.
    """
    context = get_calculation_context(project_input)
    mode = resolve_solver_mode(context)
    context["calculation_mode"] = mode
    context["solver_mode"] = mode
    calculator = get_calculator_for_context(context)
    return calculator.metadata() if calculator else None


def _configuration_summary(project_input):
    if project_input.get("configuration_summary"):
        return project_input["configuration_summary"]
    if project_input.get("configuration_manifest"):
        return validate_configuration_manifest(project_input["configuration_manifest"])
    if project_input.get("configuration_path"):
        return validate_configuration_manifest(
            scan_single_configuration(project_input["configuration_path"])
        )
    return None


def _first_present(source, *paths):
    for path in paths:
        value = _get_path(source, path)
        if value is not None:
            return value
    return None


def _get_path(source, path):
    current = source
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _normalize_unit_capacity(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    return int(number) if number.is_integer() else number
