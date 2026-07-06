"""Loader for packaged PUE configurations stored under Configuration Library.

The loader normalizes workbook content but deliberately does not invoke or
modify solver.py. XLSX reading uses the Python standard library only.
"""

from math import ceil
from pathlib import Path
from re import match
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from configuration_library_scanner import parse_equipment_folder_name

SUPPORTED_CONFIGURATIONS = {"ACC_1.5MW_GASENGINE_CDU"}
DEFAULT_LIBRARY_ROOT = Path(__file__).resolve().parent.parent / "Configuration Library"

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


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
    """Select a scenario sheet first, then generic Solver_Curve."""
    electrical_path = equipment_package.get("electrical_path") if equipment_package else None
    if electrical_path and electrical_path.get("it_efficiency") is not None and electrical_path.get("mep_efficiency") is not None:
        return {
            "status": "Electrical Path Found",
            "sheet_name": "Solver",
            "curve": None,
            "electrical_path": electrical_path,
        }
    curves = equipment_package.get("solver_curves", {}) if equipment_package else {}
    scenario = str(scenario_name or "").strip().lower()
    preferred = None
    if scenario == "normal":
        preferred = "Solver_Curve_Normal"
    elif scenario in {"failure", "maintenance"}:
        preferred = "Solver_Curve_Failure"
    for sheet_name in (preferred, "Solver_Curve"):
        if sheet_name and curves.get(sheet_name):
            return {"status": "Selected", "sheet_name": sheet_name, "curve": curves[sheet_name]}
    if str(equipment_package.get("equipment_id", "")).startswith("ACC_") and equipment_package.get("performance_map"):
        return {"status": "Selected", "sheet_name": "Performance_Map", "curve": equipment_package["performance_map"]}
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
        }
    return packages


def _resolve_actual_equipment_folder(equipment_root, requested_equipment_id):
    """Resolve a requested equipment ID to the actual folder by semantic type.

    The configuration workbook may keep stable logical IDs such as ENGINE_2
    while the actual library folder is named ENGINE_3. This helper preserves
    the logical package key and only redirects the workbook read to an existing
    same-type folder. No calculation data is changed.
    """
    exact_workbook = equipment_root / requested_equipment_id / f"{requested_equipment_id}.xlsx"
    if exact_workbook.is_file():
        return requested_equipment_id

    requested = parse_equipment_folder_name(requested_equipment_id)
    requested_canonical = requested["canonical_equipment_id"]
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
    return ceil(float(total_it_capacity_mw) / float(cooling_unit_capacity_mw))


def calculate_installed_units(total_it_capacity_mw, cooling_unit_capacity_mw):
    """Return N+1 installed units: duty requirement plus one redundant unit."""
    return calculate_required_units(total_it_capacity_mw, cooling_unit_capacity_mw) + 1


def calculate_unit_requirements(total_it_capacity_mw, cooling_unit_capacity_mw):
    required_units = calculate_required_units(total_it_capacity_mw, cooling_unit_capacity_mw)
    installed_units = required_units + 1
    return {
        "required_units": required_units,
        "installed_units": installed_units,
        "normal_active_units": installed_units,
        "failure_active_units": required_units,
        "redundancy": "N+1",
    }


def calculate_running_units(installed_units, running_unit_formula):
    formula = " ".join(str(running_unit_formula).strip().lower().split())
    if formula == "installed_units":
        return int(installed_units)
    if match(r"^installed_units\s*-\s*1$", formula):
        return max(0, int(installed_units) - 1)
    raise ValueError(f"Unsupported running unit formula: {running_unit_formula}")


def load_configuration_library(configuration_name, library_root=None, total_it_capacity_mw=None):
    if configuration_name not in SUPPORTED_CONFIGURATIONS:
        raise ValueError(f"Unsupported configuration: {configuration_name}")
    root = Path(library_root) if library_root else DEFAULT_LIBRARY_ROOT
    configuration_dir = root / configuration_name
    if not configuration_dir.is_dir():
        raise FileNotFoundError(configuration_dir)
    configuration = load_configuration_workbook(configuration_dir)
    scenarios = load_scenario_workbook(configuration_dir)
    it_profile = load_it_profile(configuration_dir)
    equipment = load_equipment_packages(configuration_dir, configuration["equipment_per_cooling_unit"])
    library_bound_input = build_library_bound_input(
        configuration, scenarios, equipment, it_profile, total_it_capacity_mw
    )
    return {
        **configuration,
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
    sizing = calculate_unit_requirements(total_it_capacity_mw, loaded["cooling_unit_capacity_mw"])
    active_units = calculate_running_units(sizing["installed_units"], scenario["running_unit_formula"])
    percentages = loaded["it_load"]["hourly_it_load_percent"]
    hourly_it_load_kw = [design_it_load_kw * float(percent) / 100.0 for percent in percentages]
    selected_curves = {
        equipment_id: select_solver_curve(package, scenario["scenario"])
        for equipment_id, package in loaded["equipment"].items()
    }

    acc_id = _resolve_loaded_equipment_id(loaded["equipment"], "ACC_2", "acc_unit")
    pump_id = _resolve_loaded_equipment_id(loaded["equipment"], "CHW_PUMP_2", "pump")
    engine_id = _resolve_loaded_equipment_id(loaded["equipment"], "ENGINE_2", "gas_engine")
    radiator_id = _resolve_loaded_equipment_id(loaded["equipment"], "ENGINE_RADIATOR_2", "heat_exchanger")
    electrical_id = _resolve_loaded_equipment_id(
        loaded["equipment"], "ELECTRICAL_DISTRIBUTION_2", "electrical_distribution"
    )
    auxiliary_ids = [
        _resolve_loaded_equipment_id(loaded["equipment"], preferred, canonical)
        for preferred, canonical in (
            ("CDU_2", "cdu"),
            ("RTC_2", "auxiliary_load"),
            ("MAU_2", "terminal_fan"),
        )
    ]

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
        }

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
        "project": {
            "name": loaded["configuration_name"],
            "calculation_mode": "project_8760",
            "project_mode": True,
            "design_it_load_kW": design_it_load_kw,
            "cooling_unit_capacity_kW": loaded["cooling_unit_capacity_mw"] * 1000.0,
            "required_units": sizing["required_units"],
            "installed_units": sizing["installed_units"],
            "active_units": active_units,
            "redundancy_strategy": "N+1",
            "scenario_name": scenario["scenario"],
            "it_load": {
                "design_it_load_kW": design_it_load_kw,
                "hourly_it_load_percent": percentages,
                "hourly_it_load_kW": hourly_it_load_kw,
            },
        },
        "equipment": equipment,
        "electrical_path": electrical_path,
        "selected_curves": selected_curves,
        "configuration_library": {
            "configuration_name": loaded["configuration_name"],
            "library_bound_input": loaded["library_bound_input"],
        },
    }


def _resolve_loaded_equipment_id(equipment_packages, preferred_equipment_id, canonical_equipment_id):
    if preferred_equipment_id in equipment_packages:
        return preferred_equipment_id
    for equipment_id in sorted(equipment_packages):
        parsed = parse_equipment_folder_name(equipment_id)
        if parsed["canonical_equipment_id"] == canonical_equipment_id:
            return equipment_id
    raise KeyError(f"No equipment package found for {preferred_equipment_id} / {canonical_equipment_id}")
