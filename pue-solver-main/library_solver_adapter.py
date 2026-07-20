"""Compatibility adapter from Phase 8 library input to solver.py input."""

from copy import deepcopy

from configuration_library_scanner import parse_equipment_folder_name
from equipment_registry import canonicalize_equipment_id


def _selected_curve(library_input, equipment_id):
    selected = library_input.get("selected_curves", {}).get(equipment_id, {})
    curve = selected.get("curve")
    return curve if isinstance(curve, list) else []


def _resolve_equipment_key(mapping, preferred_equipment_id, canonical_equipment_id):
    canonical_equipment_id = canonicalize_equipment_id(canonical_equipment_id)
    if preferred_equipment_id in mapping:
        return preferred_equipment_id
    for equipment_id in sorted(mapping):
        parsed = parse_equipment_folder_name(equipment_id)
        if canonicalize_equipment_id(parsed["canonical_equipment_id"]) == canonical_equipment_id:
            return equipment_id
    return preferred_equipment_id


def _acc_cop_curve(rows):
    data = [
        {
            "ambient_C": row.get("ambient_C"),
            "load_ratio": row.get("load_ratio"),
            "COP": row.get("COP"),
        }
        for row in rows
        if row.get("ambient_C") is not None and row.get("load_ratio") is not None and row.get("COP") is not None
    ]
    return {
        "type": "2d_lookup_table",
        "x_axis": "ambient_C",
        "y_axis": "load_ratio",
        "output": "COP",
        "interpolation": "bilinear",
        "data": data,
    }


def _power_curve(rows, curve_id):
    data = [
        {"load_ratio": row.get("load_ratio"), "power_kW": row.get("power_kW")}
        for row in rows
        if row.get("load_ratio") is not None and row.get("power_kW") is not None
    ]
    return {
        "type": "1d_lookup_table",
        "x_axis": "load_ratio",
        "output": "power_kW",
        "interpolation": "linear",
        "data": data,
        "curve_id": curve_id,
    }


def convert_library_input_to_solver_input(library_input):
    """Map library fields to compute_pue_project-compatible input.

    Fields that the current solver does not consume are retained under
    library_context. No solver implementation is changed by this adapter.
    """
    if not isinstance(library_input, dict):
        raise TypeError("library_input must be a dictionary")
    manifest = library_input.get("configuration_manifest", {})
    topology_id = (
        library_input.get("topology_id")
        or library_input.get("solver_dispatch_key")
        or library_input.get("configuration_library", {}).get("topology_id")
        or (manifest.get("solver_topology") if isinstance(manifest, dict) else None)
    )
    if topology_id and topology_id != "acc_gas_engine_cdu":
        raise ValueError(
            f"Unsupported solver topology for ACC adapter: {topology_id}. "
            "Only acc_gas_engine_cdu can use the current ACC Configuration Library path."
        )
    project_source = library_input.get("project", {})
    it_source = project_source.get("it_load", {})
    hourly_it = list(it_source.get("hourly_it_load_kW", []))
    if not hourly_it:
        raise ValueError("library_input is missing project.it_load.hourly_it_load_kW")
    hours = len(hourly_it)
    active_units = int(project_source.get("active_units") or 1)
    indoor_active_units = int(project_source.get("indoor_active_units") or project_source.get("installed_units") or active_units)
    capacity_kw = float(project_source.get("cooling_unit_capacity_kW") or 0.0)

    weather = deepcopy(library_input.get("weather")) if isinstance(library_input.get("weather"), dict) else None
    weather_data = weather.get("hourly_data", {}) if weather else {}
    dry_bulb = weather_data.get("dry_bulb_C")
    if not isinstance(dry_bulb, list) or len(dry_bulb) != hours:
        weather = {
            "hourly_data": {
                "hour_index": list(range(1, hours + 1)),
                "dry_bulb_C": [25.0] * hours,
                "wet_bulb_C": [],
            },
            "metadata": {"source": "library_solver_adapter_default", "assumption": "25 C constant dry bulb"},
        }
    else:
        weather.setdefault("hourly_data", {})
        weather["hourly_data"]["hour_index"] = list(range(1, hours + 1))

    selected_curves = library_input.get("selected_curves", {})
    acc_equipment_id = _resolve_equipment_key(selected_curves, "ACC_2", "acc_unit")
    pump_equipment_id = _resolve_equipment_key(selected_curves, "CHW_PUMP_2", "pump")
    engine_equipment_id = _resolve_equipment_key(selected_curves, "ENGINE_2", "gas_engine")
    radiator_equipment_id = _resolve_equipment_key(selected_curves, "ENGINE_RADIATOR_2", "engine_radiator")

    acc_rows = _selected_curve(library_input, acc_equipment_id)
    pump_rows = _selected_curve(library_input, pump_equipment_id)
    engine_rows = _selected_curve(library_input, engine_equipment_id)
    radiator_rows = _selected_curve(library_input, radiator_equipment_id)
    acc_curve_id = f"{acc_equipment_id}_COP"
    pump_curve_id = f"{pump_equipment_id}_power_vs_load"
    curves = {
        acc_curve_id: _acc_cop_curve(acc_rows),
        pump_curve_id: _power_curve(pump_rows, pump_curve_id),
    }

    project = deepcopy(project_source)
    project.setdefault("peak_design_weather_source", "ashrae_auto")
    ashrae_endpoint = library_input.get("ashrae_design_conditions_url") or project.get("ashrae_design_conditions_url")
    if ashrae_endpoint:
        project["ashrae_design_conditions_url"] = ashrae_endpoint
    if isinstance(library_input.get("site_location"), dict):
        project.setdefault("site_location", deepcopy(library_input["site_location"]))
    project["it_load"] = deepcopy(it_source)
    project["it_load"]["cooling_unit_capacity_kW"] = capacity_kw
    project["it_load"]["cooling_unit_count"] = active_units
    project["cooling_unit_count"] = active_units
    project["installed_units"] = project_source.get("installed_units")
    project["active_units"] = active_units
    project["indoor_active_units"] = indoor_active_units

    library_context = {
        "configuration_id": library_input.get("configuration_id") or library_input.get("configuration_library", {}).get("configuration_id"),
        "configuration_display_name": library_input.get("configuration_display_name") or library_input.get("configuration_library", {}).get("configuration_display_name"),
        "configuration_manifest_schema_version": library_input.get("configuration_manifest_schema_version") or library_input.get("configuration_library", {}).get("configuration_manifest_schema_version"),
        "topology_id": topology_id or "acc_gas_engine_cdu",
        "implementation_status": library_input.get("implementation_status") or library_input.get("configuration_library", {}).get("implementation_status"),
        "solver_dispatch_key": library_input.get("solver_dispatch_key") or library_input.get("configuration_library", {}).get("solver_dispatch_key") or "acc_gas_engine_cdu",
        "report_profile": library_input.get("report_profile") or library_input.get("configuration_library", {}).get("report_profile") or "acc_gas_engine_cdu",
        "configuration_name": library_input.get("configuration_library", {}).get("configuration_name"),
        "scenario_name": library_input.get("scenario_name"),
        "acc_curve": {
            "equipment_id": acc_equipment_id,
            "source_sheet": selected_curves.get(acc_equipment_id, {}).get("sheet_name"),
            "data": deepcopy(acc_rows),
        },
        "required_units": project_source.get("required_units"),
        "installed_units": project_source.get("installed_units"),
        "active_units": active_units,
        "indoor_active_units": indoor_active_units,
        "selected_curves": deepcopy(library_input.get("selected_curves", {})),
        "engine_output_reference": deepcopy(library_input.get("equipment", {}).get("cooling", {}).get("engine")),
        "engine_radiator": deepcopy(library_input.get("equipment", {}).get("cooling", {}).get("engine_radiator")),
        "auxiliary_equipment": deepcopy(library_input.get("equipment", {}).get("auxiliary", {})),
        "electrical_path": deepcopy(library_input.get("electrical_path")),
        "adapter_assumptions": weather.get("metadata", {}),
    }
    return {
        "configuration_id": library_context["configuration_id"],
        "configuration_display_name": library_context["configuration_display_name"],
        "configuration_manifest_schema_version": library_context["configuration_manifest_schema_version"],
        "topology_id": library_context["topology_id"],
        "implementation_status": library_context["implementation_status"],
        "solver_dispatch_key": library_context["solver_dispatch_key"],
        "report_profile": library_context["report_profile"],
        "cooling_system_type": library_input.get("cooling_system_type"),
        "cooling_unit_capacity_mw": library_input.get("cooling_unit_capacity_mw"),
        "power_source": library_input.get("power_source"),
        "scenario_name": library_input.get("scenario_name"),
        "acc_curve": deepcopy(library_context["acc_curve"]),
        "engine_curve": {
            "equipment_id": engine_equipment_id,
            "source_sheet": selected_curves.get(engine_equipment_id, {}).get("sheet_name"),
            "data": deepcopy(engine_rows),
            "default_efficiency": 0.40,
            "default_efficiency_source": "temporary_assumption_pending_vendor_fuel_map",
        },
        "engine_radiator_curve": {
            "equipment_id": radiator_equipment_id,
            "source_sheet": selected_curves.get(radiator_equipment_id, {}).get("sheet_name"),
            "data": deepcopy(radiator_rows),
        },
        "project": project,
        "ashrae_design_conditions_url": ashrae_endpoint,
        "site_location": deepcopy(library_input.get("site_location", {})),
        "weather": weather,
        "curve_library": {"curves": curves},
        "equipment": {
            "cooling": {
                "cooling_unit_capacity_kW": capacity_kw,
                "cooling_unit_count": active_units,
                "chiller": {"enabled": True, "curve_ref": acc_curve_id, "source_equipment_id": acc_equipment_id},
                "ACC": {"enabled": True, "curve_ref": acc_curve_id, "source_equipment_id": acc_equipment_id},
                "dry_cooler": {"enabled": False},
                "pumps": {"enabled": True, "power_curve_refs": [pump_curve_id], "source_equipment_id": pump_equipment_id},
                "fans": {"enabled": False},
            },
            "library_fixed_power": deepcopy(library_input.get("equipment", {}).get("auxiliary", {})),
            "electrical_path": deepcopy(library_input.get("electrical_path")),
        },
        "electrical_path": deepcopy(library_input.get("electrical_path")),
        "library_context": library_context,
    }
