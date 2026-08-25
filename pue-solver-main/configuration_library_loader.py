"""Loader for packaged PUE configurations stored under Configuration Library.

The loader normalizes workbook content but deliberately does not invoke or
modify solver.py. XLSX reading uses the Python standard library only.
"""

import json
from pathlib import Path
from re import match
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from configuration_manifest import (
    assert_manifest_executable,
    discover_configuration_manifests,
    load_configuration_manifest,
)
from configuration_library_scanner import parse_equipment_folder_name
from equipment_metadata import load_equipment_metadata, validate_equipment_metadata
from equipment_registry import canonicalize_equipment_id
from equipment_role_resolver import (
    resolve_equipment_role_id,
    validate_required_equipment_roles,
)
from unit_scenario_manager import (
    calculate_active_units as _manager_calculate_active_units,
    calculate_required_units as _manager_calculate_required_units,
    calculate_unit_requirements as _manager_calculate_unit_requirements,
    resolve_unit_scenario,
)

DEFAULT_LIBRARY_ROOT = Path(__file__).resolve().parent.parent / "Configuration Library"
# Resolved Configuration Library path: project root / "Configuration Library".
SHARED_ALIAS_PATH = DEFAULT_LIBRARY_ROOT / "equipment_aliases.json"
DEFAULT_EQUIPMENT_ALIASES = {
    "RTC_1": "RTC_1&2",
    "RTC_2": "RTC_1&2",
    "MAU_1": "MAU_1&2",
    "MAU_2": "MAU_1&2",
    "ENGINE_2": "ENGINE_3",
    "ENGINE_RADIATOR_2": "ENGINE_RADIATOR_1",
}

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def load_equipment_aliases(alias_path=None):
    """Load shared equipment aliases, falling back to the built-in map."""
    aliases = dict(DEFAULT_EQUIPMENT_ALIASES)
    path = Path(alias_path) if alias_path else SHARED_ALIAS_PATH
    try:
        with path.open(encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, json.JSONDecodeError, TypeError):
        return aliases
    if isinstance(loaded, dict):
        aliases.update({
            str(key): str(value)
            for key, value in loaded.items()
            if key is not None and value is not None
        })
    return aliases


def resolve_equipment_alias(equipment_id, aliases=None):
    """Return the shared canonical equipment ID for a raw equipment ID."""
    aliases = aliases if isinstance(aliases, dict) else load_equipment_aliases()
    text = str(equipment_id or "")
    return aliases.get(text) or aliases.get(text.upper()) or text


def _column_index(cell_reference):
    letters = "".join(ch for ch in cell_reference if ch.isalpha())
    value = 0
    for letter in letters.upper():
        value = value * 26 + ord(letter) - 64
    return value - 1


def _cell_value(cell, shared_strings):
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{{{_MAIN_NS}}}t"))
    value_node = cell.find(f"{{{_MAIN_NS}}}v")
    if value_node is None:
        return None
    value = value_node.text or ""
    if cell_type == "s":
        return shared_strings[int(value)]
    if cell_type in {"str", "b"}:
        return value
    try:
        number = float(value)
        return int(number) if number.is_integer() else number
    except ValueError:
        return value


def read_xlsx_sheets(path):
    """Return {sheet_name: [row_values]} for a normal OOXML workbook."""
    path = Path(path)
    with ZipFile(path) as archive:
        shared_strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared_strings = [
                "".join(node.text or "" for node in item.iter(f"{{{_MAIN_NS}}}t"))
                for item in root.findall(f"{{{_MAIN_NS}}}si")
            ]

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.get("Id"): item.get("Target") for item in relationships}
        sheets = {}
        for sheet in workbook.iter(f"{{{_MAIN_NS}}}sheet"):
            target = targets[sheet.get(f"{{{_REL_NS}}}id")]
            if target.startswith("/"):
                target = target.lstrip("/")
            elif not target.startswith("xl/"):
                target = f"xl/{target}"
            sheet_root = ET.fromstring(archive.read(target))
            rows = []
            for row_node in sheet_root.iter(f"{{{_MAIN_NS}}}row"):
                values = []
                for cell in row_node.findall(f"{{{_MAIN_NS}}}c"):
                    index = _column_index(cell.get("r", "A1"))
                    while len(values) <= index:
                        values.append(None)
                    values[index] = _cell_value(cell, shared_strings)
                while values and values[-1] is None:
                    values.pop()
                rows.append(values)
            sheets[sheet.get("name")] = rows
        return sheets


def _records(rows):
    if not rows:
        return []
    headers = [str(value).strip() if value is not None else "" for value in rows[0]]
    return [
        {header: row[index] if index < len(row) else None for index, header in enumerate(headers) if header}
        for row in rows[1:]
        if any(value is not None for value in row)
    ]


def _key_value_sheet(rows, key_header="Parameter", value_header="Value"):
    return {
        row[key_header]: row[value_header]
        for row in _records(rows)
        if row.get(key_header) is not None
    }


def load_configuration_workbook(configuration_dir):
    sheets = read_xlsx_sheets(Path(configuration_dir) / "configuration.xlsx")
    values = _key_value_sheet(sheets.get("Configuration", []))
    equipment = []
    for row in _records(sheets.get("Equipment_List", [])):
        equipment.append({
            "equipment_id": str(row.get("Equipment", "")).strip(),
            "per_cooling_unit": int(row.get("Per Cooling Unit") or 0),
        })
    return {
        "configuration_name": values.get("Configuration Name"),
        "cooling_system_type": values.get("Cooling System Type"),
        "cooling_unit_capacity_mw": float(values.get("Cooling Unit Capacity")),
        "power_source": values.get("Power Source"),
        "white_space_type": values.get("White Space Type"),
        "equipment_per_cooling_unit": equipment,
    }


def load_scenario_workbook(configuration_dir):
    sheets = read_xlsx_sheets(Path(configuration_dir) / "scenario.xlsx")
    return [
        {
            "scenario": row.get("Scenario"),
            "running_unit_formula": row.get("Running Unit Formula"),
            "description": row.get("Description"),
        }
        for row in _records(sheets.get("Scenario", []))
    ]


def load_it_profile(configuration_dir):
    sheets = read_xlsx_sheets(Path(configuration_dir) / "input" / "IT_LOAD_90_PERCENT.xlsx")
    rows = _records(sheets.get("IT_Load", []))
    percentages = [float(row["hourly_it_load_percent"]) for row in rows if row.get("hourly_it_load_percent") is not None]
    ratios = [float(row.get("hourly_it_load_ratio", percentage / 100.0)) for row, percentage in zip(rows, percentages)]
    return {
        "hourly_it_load_percent": percentages,
        "hourly_it_load_%": percentages,
        "hourly_it_load_ratio": ratios,
        "hours": len(percentages),
        "source_file": "input/IT_LOAD_90_PERCENT.xlsx",
    }


def _sheet_key_values(rows):
    records = _records(rows)
    result = {}
    for row in records:
        key = row.get("Parameter") or row.get("Field") or row.get("Item") or row.get("Check Item")
        value = row.get("Value") if "Value" in row else row.get("Status")
        if key is not None:
            result[str(key)] = value
    return result


def select_solver_curve(equipment_package, scenario_name):
    """Select the applicable solver curve; pumps always use one shared curve."""
    electrical_path = equipment_package.get("electrical_path") if equipment_package else None
    if electrical_path and electrical_path.get("it_efficiency") is not None and electrical_path.get("mep_efficiency") is not None:
        return {
            "status": "Electrical Path Found",
            "sheet_name": "Solver",
            "curve": None,
            "performance_map": equipment_package.get("performance_map"),
            "electrical_path": electrical_path,
            "equipment_metadata": equipment_package.get("equipment_metadata"),
        }
    curves = equipment_package.get("solver_curves", {}) if equipment_package else {}
    metadata = equipment_package.get("equipment_metadata") or {}
    equipment_type = str(metadata.get("equipment_type") or "").upper()
    equipment_id = str(equipment_package.get("equipment_id") or "").upper()
    if equipment_type in {"CHW_PUMP", "CW_PUMP"} or equipment_id.startswith(("CHW_PUMP", "CW_PUMP")):
        curve = curves.get("Solver_Curve")
        return {"status": "Selected" if curve else "Missing Curve", "sheet_name": "Solver_Curve" if curve else None, "curve": curve, "performance_map": equipment_package.get("performance_map"), "equipment_metadata": equipment_package.get("equipment_metadata")}
    scenario = str(scenario_name or "").strip().lower()
    preferred = None
    if scenario == "normal":
        preferred = "Solver_Curve_Normal"
    elif scenario in {"failure", "maintenance"}:
        preferred = "Solver_Curve_Failure"
    for sheet_name in (preferred, "Solver_Curve"):
        if sheet_name and curves.get(sheet_name):
            return {"status": "Selected", "sheet_name": sheet_name, "curve": curves[sheet_name], "performance_map": equipment_package.get("performance_map"), "equipment_metadata": equipment_package.get("equipment_metadata")}
    if str(equipment_package.get("equipment_id", "")).startswith("ACC_") and equipment_package.get("performance_map"):
        return {"status": "Selected", "sheet_name": "Performance_Map", "curve": equipment_package["performance_map"], "performance_map": equipment_package.get("performance_map"), "equipment_metadata": equipment_package.get("equipment_metadata")}
    return {"status": "Missing Curve", "sheet_name": None, "curve": None}


def load_equipment_packages(configuration_dir, equipment_list):
    packages = {}
    equipment_root = Path(configuration_dir) / "equipment"
    for equipment_entry in equipment_list:
        equipment_id = equipment_entry["equipment_id"]
        actual_equipment_id = _resolve_actual_equipment_folder(equipment_root, equipment_id)
        workbook = equipment_root / actual_equipment_id / f"{actual_equipment_id}.xlsx"
        package_path = workbook.relative_to(configuration_dir).as_posix()
        if not workbook.is_file():
            packages[equipment_id] = {
                "equipment_id": equipment_id,
                "actual_equipment_id": actual_equipment_id,
                "equipment_type": None,
                "package_path": package_path,
                "status": "Missing",
                "available_sheets": [],
                "solver_curves": {},
                "performance_map": [],
                "electrical_path": None,
                "validation_status": "Missing equipment package",
            }
            continue
        sheets = read_xlsx_sheets(workbook)
        curve_names = [name for name in ("Solver_Curve", "Solver_Curve_Normal", "Solver_Curve_Failure") if name in sheets]
        information = _sheet_key_values(sheets.get("Information", []))
        metadata = _sheet_key_values(sheets.get("Metadata", []))
        validation = _sheet_key_values(sheets.get("Validation", []))
        metadata_path = workbook.parent / "equipment_metadata.json"
        equipment_metadata = None
        equipment_metadata_validation = {
            "status": "error",
            "equipment_id": actual_equipment_id,
            "issues": ["equipment_metadata.json is missing."],
        }
        if metadata_path.is_file():
            try:
                equipment_metadata = load_equipment_metadata(metadata_path)
                equipment_metadata_validation = validate_equipment_metadata(
                    equipment_metadata,
                    equipment_folder=workbook.parent,
                )
            except Exception as exc:
                equipment_metadata_validation = {
                    "status": "error",
                    "equipment_id": actual_equipment_id,
                    "issues": [f"Could not load equipment_metadata.json: {exc}"],
                }
        equipment_type = information.get("Equipment Type") or metadata.get("equipment_type")
        is_electrical_path = equipment_id.startswith("ELECTRICAL_DISTRIBUTION") or str(equipment_type).strip().lower() == "electrical distribution"
        electrical_path = None
        if is_electrical_path:
            solver_rows = _records(sheets.get("Solver", []))
            efficiencies = {
                str(row.get("Path", "")).strip().upper(): row.get("overall_efficiency")
                for row in solver_rows
            }
            electrical_path = {
                "it_efficiency": float(efficiencies["IT"]) if efficiencies.get("IT") is not None else None,
                "mep_efficiency": float(efficiencies["MEP"]) if efficiencies.get("MEP") is not None else None,
            }
        package_status = "Electrical Path Found" if electrical_path and all(value is not None for value in electrical_path.values()) else "Found"
        packages[equipment_id] = {
            "equipment_id": equipment_id,
            "actual_equipment_id": actual_equipment_id,
            "equipment_type": equipment_type,
            "package_path": package_path,
            "status": package_status,
            "available_sheets": list(sheets),
            "solver_curves": {name: _records(sheets[name]) for name in curve_names},
            "performance_map": _records(sheets.get("Performance_Map", [])),
            "electrical_path": electrical_path,
            "validation_status": validation.get("Validation Status") or validation.get("Status") or "Available",
            "information": information,
            "metadata": metadata,
            "validation": validation,
            "equipment_metadata": equipment_metadata,
            "equipment_metadata_validation": equipment_metadata_validation,
        }
    return packages


def _resolve_actual_equipment_folder(equipment_root, requested_equipment_id):
    """Resolve a requested equipment ID to the actual folder by semantic type.

    The configuration workbook may keep stable logical IDs such as ENGINE_2
    while the actual library folder is named ENGINE_3. This helper preserves
    the logical package key and only redirects the workbook read to an existing
    same-type folder. No calculation data is changed.
    """
    aliased_equipment_id = resolve_equipment_alias(requested_equipment_id)
    if aliased_equipment_id != requested_equipment_id:
        alias_workbook = equipment_root / aliased_equipment_id / f"{aliased_equipment_id}.xlsx"
        if alias_workbook.is_file():
            return aliased_equipment_id

    exact_workbook = equipment_root / requested_equipment_id / f"{requested_equipment_id}.xlsx"
    if exact_workbook.is_file():
        return requested_equipment_id

    requested = parse_equipment_folder_name(requested_equipment_id)
    requested_canonical = requested["canonical_equipment_id"] or canonicalize_equipment_id(requested_equipment_id)
    if not requested_canonical or not equipment_root.is_dir():
        return requested_equipment_id

    for folder in sorted([child for child in equipment_root.iterdir() if child.is_dir()], key=lambda item: item.name.upper()):
        parsed = parse_equipment_folder_name(folder.name)
        if parsed["canonical_equipment_id"] != requested_canonical:
            continue
        workbook = folder / f"{folder.name}.xlsx"
        if workbook.is_file():
            return folder.name
    return requested_equipment_id


def build_library_bound_input(configuration, scenarios, equipment, it_profile, total_it_capacity_mw=None):
    if total_it_capacity_mw is None:
        unit_counts = {
            "required_units": None, "installed_units": None,
            "normal_active_units": None, "failure_active_units": None,
            "indoor_active_units": None,
            "redundancy": "N+1",
            "required_units_formula": "ceil(total_it_capacity_mw / cooling_unit_capacity_mw)",
            "installed_units_formula": "required_units + 1",
        }
    else:
        unit_counts = calculate_unit_requirements(total_it_capacity_mw, configuration["cooling_unit_capacity_mw"])
    selected_curves = {
        scenario["scenario"]: {
            equipment_id: select_solver_curve(package, scenario["scenario"])
            for equipment_id, package in equipment.items()
        }
        for scenario in scenarios
    }
    return {
        "configuration": configuration,
        "unit_counts": unit_counts,
        "scenarios": scenarios,
        "equipment_packages": equipment,
        "selected_curves": selected_curves,
        "it_load_profile": it_profile,
    }


def calculate_required_units(total_it_capacity_mw, cooling_unit_capacity_mw):
    """Return duty units required to cover design IT capacity."""
    return _manager_calculate_required_units(total_it_capacity_mw, cooling_unit_capacity_mw)


def calculate_installed_units(total_it_capacity_mw, cooling_unit_capacity_mw):
    """Return N+1 installed units: duty requirement plus one redundant unit."""
    return calculate_required_units(total_it_capacity_mw, cooling_unit_capacity_mw) + 1


def calculate_unit_requirements(total_it_capacity_mw, cooling_unit_capacity_mw):
    return _manager_calculate_unit_requirements(total_it_capacity_mw, cooling_unit_capacity_mw)


def calculate_running_units(installed_units, running_unit_formula):
    return _manager_calculate_active_units(installed_units, installed_units, running_unit_formula)


def discover_configuration_library(library_root=None, include_invalid=False):
    """Return manifest metadata for Configuration Library folders."""
    root = Path(library_root) if library_root else DEFAULT_LIBRARY_ROOT
    return discover_configuration_manifests(root, include_invalid=include_invalid)


def load_configuration_library(configuration_name, library_root=None, total_it_capacity_mw=None):
    root = Path(library_root) if library_root else DEFAULT_LIBRARY_ROOT
    configuration_dir = root / configuration_name
    if not configuration_dir.is_dir():
        raise FileNotFoundError(configuration_dir)
    manifest = load_configuration_manifest(configuration_dir)
    assert_manifest_executable(manifest)
    if (configuration_dir / "configuration.xlsx").is_file():
        configuration = load_configuration_workbook(configuration_dir)
        scenarios = load_scenario_workbook(configuration_dir)
        it_profile = load_it_profile(configuration_dir)
    else:
        configuration = _manifest_only_configuration(configuration_name, manifest)
        scenarios = _default_manifest_only_scenarios(manifest)
        it_profile = _default_manifest_only_it_profile()
    equipment = load_equipment_packages(configuration_dir, configuration["equipment_per_cooling_unit"])
    _validate_manifest_equipment_roles(manifest, equipment)
    library_bound_input = build_library_bound_input(
        configuration, scenarios, equipment, it_profile, total_it_capacity_mw
    )
    manifest_metadata = _manifest_metadata(manifest)
    return {
        **configuration,
        "configuration_id": manifest["configuration_id"],
        "configuration_display_name": manifest["display_name"],
        "configuration_manifest": manifest,
        "configuration_manifest_metadata": manifest_metadata,
        "topology_id": manifest["solver_topology"],
        "implementation_status": manifest["implementation_status"],
        "solver_dispatch_key": manifest["solver_topology"],
        "report_profile": manifest["report_profile"],
        "scenarios": scenarios,
        "it_load": it_profile,
        "equipment": equipment,
        "library_bound_input": library_bound_input,
        "standardized_input": {
            "cooling_system_type": configuration["cooling_system_type"],
            "cooling_unit_capacity_mw": configuration["cooling_unit_capacity_mw"],
            "power_source": configuration["power_source"],
            "project": {"it_load": it_profile},
            "configuration_library": {
                **manifest_metadata,
                "configuration_name": configuration_name,
                "equipment_per_cooling_unit": configuration["equipment_per_cooling_unit"],
                "scenarios": scenarios,
                "equipment_packages": equipment,
                "selected_curves": library_bound_input["selected_curves"],
                "unit_sizing_rule": {
                    "required_units": "ceil(total_it_capacity_mw / cooling_unit_capacity_mw)",
                    "installed_units": "required_units + 1",
                    "redundancy": "N+1",
                    "normal_active_units": "installed_units",
                    "failure_active_units": "required_units",
                },
            },
        },
    }


def _validate_manifest_equipment_roles(manifest, equipment_packages):
    validate_required_equipment_roles(manifest, equipment_packages)


def _manifest_metadata(manifest):
    return {
        "configuration_id": manifest.get("configuration_id"),
        "configuration_display_name": manifest.get("display_name"),
        "configuration_manifest_schema_version": manifest.get("schema_version"),
        "manifest_cooling_system_type": manifest.get("cooling_system_type"),
        "topology_id": manifest.get("solver_topology"),
        "implementation_status": manifest.get("implementation_status"),
        "solver_dispatch_key": manifest.get("solver_topology"),
        "report_profile": manifest.get("report_profile"),
    }


def build_solver_input_from_library(config_name, total_it_capacity_mw, scenario_name, library_root=None):
    """Build a Phase 8 standardized input without invoking solver.py."""
    loaded = load_configuration_library(
        config_name, library_root=library_root, total_it_capacity_mw=total_it_capacity_mw
    )
    scenario = next(
        (item for item in loaded["scenarios"] if str(item["scenario"]).lower() == str(scenario_name).lower()),
        None,
    )
    if scenario is None:
        raise ValueError(f"Unknown scenario: {scenario_name}")

    design_it_load_kw = float(total_it_capacity_mw) * 1000.0
    unit_scenario = resolve_unit_scenario(
        total_it_capacity_mw,
        loaded["cooling_unit_capacity_mw"],
        scenario_name=scenario["scenario"],
        scenario_formula=scenario["running_unit_formula"],
    )
    sizing = {
        "required_units": unit_scenario["required_units"],
        "installed_units": unit_scenario["installed_units"],
        "normal_active_units": unit_scenario["role_quantities"]["indoor_units"]["active_units"],
        "failure_active_units": unit_scenario["required_units"],
        "indoor_active_units": unit_scenario["role_quantities"]["indoor_units"]["active_units"],
        "redundancy": unit_scenario["redundancy_mode"],
    }
    active_units = unit_scenario["active_units"]
    percentages = loaded["it_load"]["hourly_it_load_percent"]
    hourly_it_load_kw = [design_it_load_kw * float(percent) / 100.0 for percent in percentages]
    selected_curves = {
        equipment_id: select_solver_curve(package, scenario["scenario"])
        for equipment_id, package in loaded["equipment"].items()
    }

    manifest = loaded["configuration_manifest"]
    topology_id = manifest.get("solver_topology")

    def equipment_binding(equipment_id, role):
        package = loaded["equipment"][equipment_id]
        selected = selected_curves[equipment_id]
        return {
            "enabled": package["status"] != "Missing",
            "equipment_id": equipment_id,
            "role": role,
            "package_path": package["package_path"],
            "selected_curve_sheet": selected["sheet_name"],
            "selected_curve_status": selected["status"],
            "curve_data": selected["curve"],
            "performance_map": package.get("performance_map"),
            "electrical_path": selected.get("electrical_path"),
            "equipment_metadata": package.get("equipment_metadata"),
            "information": package.get("information"),
            "metadata": package.get("metadata"),
            "equipment_metadata_validation": package.get("equipment_metadata_validation"),
        }

    if topology_id == "chiller_dry_cooler":
        chiller_id = resolve_equipment_role_id(manifest, "chiller", loaded["equipment"])
        dry_cooler_id = resolve_equipment_role_id(manifest, "dry_cooler", loaded["equipment"])
        pump_id = resolve_equipment_role_id(manifest, "chw_pump", loaded["equipment"])
        cw_pump_id = resolve_equipment_role_id(manifest, "cw_pump", loaded["equipment"])
        electrical_id = resolve_equipment_role_id(manifest, "electrical_distribution", loaded["equipment"])
        auxiliary_ids = []
        if "indoor_cooling" in manifest.get("equipment_roles", {}):
            auxiliary_ids = resolve_equipment_role_id(manifest, "indoor_cooling", loaded["equipment"]) or []
        engine_id = None
        radiator_id = None
        if str(loaded["power_source"] or "").strip().lower().replace("_", " ") == "gas engine":
            engine_id = resolve_equipment_role_id(manifest, "engine", loaded["equipment"])
            radiator_id = resolve_equipment_role_id(manifest, "engine_radiator", loaded["equipment"])

        electrical_path = loaded["equipment"][electrical_id]["electrical_path"]
        equipment = {
            "cooling": {
                "chiller": equipment_binding(chiller_id, "chiller"),
                "dry_cooler": equipment_binding(dry_cooler_id, "dry_cooler"),
                "pumps": {
                    pump_id: equipment_binding(pump_id, "chw_pump_power"),
                    cw_pump_id: equipment_binding(cw_pump_id, "cw_pump_power"),
                },
                **({"engine": equipment_binding(engine_id, "engine_output_reference")} if engine_id else {}),
                **({"engine_radiator": equipment_binding(radiator_id, "engine_radiator_power")} if radiator_id else {}),
            },
            "auxiliary": {
                equipment_id: equipment_binding(equipment_id, "white_space_auxiliary")
                for equipment_id in auxiliary_ids
            },
            "electrical_path": electrical_path,
        }
        return {
            "cooling_system_type": loaded["cooling_system_type"],
            "cooling_unit_capacity_mw": loaded["cooling_unit_capacity_mw"],
            "power_source": loaded["power_source"],
            "scenario_name": scenario["scenario"],
            "configuration_id": loaded["configuration_id"],
            "configuration_display_name": loaded["configuration_display_name"],
            "configuration_manifest_schema_version": loaded["configuration_manifest_metadata"]["configuration_manifest_schema_version"],
            "topology_id": loaded["topology_id"],
            "implementation_status": loaded["implementation_status"],
            "solver_dispatch_key": loaded["solver_dispatch_key"],
            "report_profile": loaded["report_profile"],
            "configuration_manifest": loaded["configuration_manifest"],
            "project": {
                "name": loaded["configuration_name"],
                "calculation_mode": "project_8760",
                "project_mode": True,
                "peak_design_weather_source": "ashrae_auto",
                "site_location": {},
                "location": {
                    "peak_design_weather_source": "ashrae_auto",
                },
                "design_it_load_kW": design_it_load_kw,
                "cooling_unit_capacity_kW": loaded["cooling_unit_capacity_mw"] * 1000.0,
                "required_units": sizing["required_units"],
                "installed_units": sizing["installed_units"],
                "active_units": active_units,
                "indoor_active_units": sizing["normal_active_units"],
                "engine_active_units": unit_scenario["role_quantities"]["engine_units"]["active_units"],
                "engine_radiator_active_units": unit_scenario["role_quantities"]["engine_units"]["active_units"],
                "redundancy_strategy": "N+1",
                "scenario_name": scenario["scenario"],
                "it_load": {
                    "design_it_load_kW": design_it_load_kw,
                    "hourly_it_load_percent": percentages,
                    "hourly_it_load_kW": hourly_it_load_kw,
                },
            },
            "site_location": {},
            "equipment": equipment,
            "electrical_path": electrical_path,
            "selected_curves": selected_curves,
            "configuration_library": {
                **loaded["configuration_manifest_metadata"],
                "configuration_name": loaded["configuration_name"],
                "library_bound_input": loaded["library_bound_input"],
            },
        }

    acc_id = resolve_equipment_role_id(manifest, "primary_cooling", loaded["equipment"])
    pump_id = resolve_equipment_role_id(manifest, "chw_pump", loaded["equipment"])
    engine_id = resolve_equipment_role_id(manifest, "engine", loaded["equipment"])
    radiator_id = resolve_equipment_role_id(manifest, "engine_radiator", loaded["equipment"])
    electrical_id = resolve_equipment_role_id(manifest, "electrical_distribution", loaded["equipment"])
    if "indoor_cooling" in manifest.get("equipment_roles", {}):
        auxiliary_ids = resolve_equipment_role_id(manifest, "indoor_cooling", loaded["equipment"])
    else:
        auxiliary_ids = [
            resolve_equipment_role_id(manifest, role, loaded["equipment"])
            for role in ("cdu", "rtc", "mau")
        ]

    electrical_path = loaded["equipment"][electrical_id]["electrical_path"]
    equipment = {
        "cooling": {
            "ACC": equipment_binding(acc_id, "cooling_equipment"),
            "pumps": {pump_id: equipment_binding(pump_id, "pump_power")},
            "engine": equipment_binding(engine_id, "engine_output_reference"),
            "engine_radiator": equipment_binding(radiator_id, "engine_radiator_power"),
        },
        "auxiliary": {
            equipment_id: equipment_binding(equipment_id, "white_space_auxiliary")
            for equipment_id in auxiliary_ids
        },
        "electrical_path": electrical_path,
    }
    return {
        "cooling_system_type": loaded["cooling_system_type"],
        "cooling_unit_capacity_mw": loaded["cooling_unit_capacity_mw"],
        "power_source": loaded["power_source"],
        "scenario_name": scenario["scenario"],
        "configuration_id": loaded["configuration_id"],
        "configuration_display_name": loaded["configuration_display_name"],
        "configuration_manifest_schema_version": loaded["configuration_manifest_metadata"]["configuration_manifest_schema_version"],
        "topology_id": loaded["topology_id"],
        "implementation_status": loaded["implementation_status"],
        "solver_dispatch_key": loaded["solver_dispatch_key"],
        "report_profile": loaded["report_profile"],
        "configuration_manifest": loaded["configuration_manifest"],
        "project": {
            "name": loaded["configuration_name"],
            "calculation_mode": "project_8760",
            "project_mode": True,
            "peak_design_weather_source": "ashrae_auto",
            "site_location": {},
            "location": {
                "peak_design_weather_source": "ashrae_auto",
            },
            "design_it_load_kW": design_it_load_kw,
            "cooling_unit_capacity_kW": loaded["cooling_unit_capacity_mw"] * 1000.0,
            "required_units": sizing["required_units"],
            "installed_units": sizing["installed_units"],
            "active_units": active_units,
            "indoor_active_units": sizing["normal_active_units"],
            "redundancy_strategy": "N+1",
            "scenario_name": scenario["scenario"],
            "it_load": {
                "design_it_load_kW": design_it_load_kw,
                "hourly_it_load_percent": percentages,
                "hourly_it_load_kW": hourly_it_load_kw,
            },
        },
        "site_location": {},
        "equipment": equipment,
        "electrical_path": electrical_path,
        "selected_curves": selected_curves,
        "configuration_library": {
            **loaded["configuration_manifest_metadata"],
            "configuration_name": loaded["configuration_name"],
            "library_bound_input": loaded["library_bound_input"],
        },
    }


def _resolve_loaded_equipment_id(equipment_packages, preferred_equipment_id, canonical_equipment_id):
    canonical_equipment_id = canonicalize_equipment_id(canonical_equipment_id)
    if preferred_equipment_id in equipment_packages:
        return preferred_equipment_id
    for equipment_id in sorted(equipment_packages):
        parsed = parse_equipment_folder_name(equipment_id)
        if canonicalize_equipment_id(parsed["canonical_equipment_id"]) == canonical_equipment_id:
            return equipment_id
    raise KeyError(f"No equipment package found for {preferred_equipment_id} / {canonical_equipment_id}")


def _manifest_only_configuration(configuration_name, manifest):
    equipment_ids = []
    for role_value in (manifest.get("equipment_roles") or {}).values():
        values = role_value if isinstance(role_value, list) else [role_value]
        for equipment_id in values:
            if equipment_id and equipment_id not in equipment_ids:
                equipment_ids.append(str(equipment_id))
    capacity_mw = manifest.get("cooling_unit_capacity_mw")
    if capacity_mw is None:
        capacity_mw = _capacity_mw_from_configuration_id(configuration_name) or 1.0
    return {
        "configuration_name": manifest.get("display_name") or configuration_name,
        "cooling_system_type": manifest.get("cooling_system_type"),
        "cooling_unit_capacity_mw": capacity_mw,
        "power_source": manifest.get("power_source") or _power_source_from_configuration_id(configuration_name),
        "white_space_type": "CDU",
        "equipment_per_cooling_unit": [
            {"equipment_id": equipment_id, "per_cooling_unit": 1}
            for equipment_id in equipment_ids
        ],
    }


def _default_manifest_only_scenarios(manifest=None):
    configured = (manifest or {}).get("scenarios")
    if isinstance(configured, list) and configured:
        return [dict(item) for item in configured if isinstance(item, dict)]
    return [
        {
            "scenario": "Normal",
            "running_unit_formula": "installed_units",
            "description": "Manifest-only default normal operation.",
        }
    ]


def _default_manifest_only_it_profile(hours=8760, percent=90.0):
    percentages = [float(percent)] * int(hours)
    ratios = [float(percent) / 100.0] * int(hours)
    return {
        "hourly_it_load_percent": percentages,
        "hourly_it_load_%": percentages,
        "hourly_it_load_ratio": ratios,
        "hours": int(hours),
        "source_file": "manifest_only_default_90_percent",
    }


def _capacity_mw_from_configuration_id(configuration_name):
    text = str(configuration_name or "").upper()
    found = match(r".*?([0-9]+(?:\.[0-9]+)?)\s*MW", text)
    return float(found.group(1)) if found else None


def _power_source_from_configuration_id(configuration_name):
    text = str(configuration_name or "").upper()
    if "GASENGINE" in text or "GAS_ENGINE" in text:
        return "Gas Engine"
    if "GRID" in text:
        return "Grid"
    return "Unknown"
