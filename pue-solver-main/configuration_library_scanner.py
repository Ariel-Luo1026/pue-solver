"""Non-invasive Configuration Library manifest scanner.

Phase 5 scanner skeleton. It inspects folder names and directory structure
only; it does not read workbooks, invoke solver.py, or modify configuration
library contents.
"""

from pathlib import Path
import re

from topology_registry import get_topology


TOPOLOGY_NAME_PREFIXES = (
    ("CHILLER_COOLINGTOWER", "chiller_cooling_tower"),
    ("CHILLER_DRYCOOLER", "chiller_dry_cooler"),
    ("ABS_COOLINGTOWER", "abs_cooling_tower"),
    ("ABS_DRYCOOLER", "abs_dry_cooler"),
    ("ACC", "acc"),
)

POWER_SOURCE_TOKENS = {
    "GASENGINE": "Gas Engine",
    "GRID": "Grid",
}

EQUIPMENT_FOLDER_PREFIX_MAP = {
    "ACC": ("acc_unit", None),
    "CDU": ("cdu", None),
    "CHW_PUMP": ("pump", None),
    "CW_PUMP": ("pump", None),
    "PUMP": ("pump", None),
    "ELECTRICAL_DISTRIBUTION": ("electrical_distribution", None),
    "ENGINE": ("gas_engine", None),
    "CHILLER": ("chiller", None),
    "DRY_COOLER": ("dry_cooler", None),
    "COOLING_TOWER": ("cooling_tower", None),
    "ABS": ("absorption_chiller", None),
    "SMOKE_WATER_HX": ("heat_exchanger", None),
    "HEAT_EXCHANGER": ("heat_exchanger", None),
    "ENGINE_RADIATOR": (
        "heat_exchanger",
        "ENGINE_RADIATOR detected; mapped tentatively to heat_exchanger.",
    ),
    "MAU": (
        "terminal_fan",
        "MAU detected; mapped tentatively to terminal_fan.",
    ),
    "RTC": (
        "auxiliary_load",
        "RTC detected; mapping is tentative.",
    ),
}


def scan_configuration_library(root_path):
    """Return manifests for configuration folders under a library root."""
    root = Path(root_path)
    if not root.exists():
        return []
    return [
        scan_single_configuration(path)
        for path in sorted(root.iterdir(), key=lambda item: item.name.lower())
        if path.is_dir()
    ]


def scan_single_configuration(configuration_path):
    """Return a manifest for a single configuration folder."""
    path = Path(configuration_path)
    configuration_name = path.name
    topology_id = _detect_topology_id(configuration_name)
    topology = get_topology(topology_id) if topology_id else None
    topology_equipment_ids = topology["equipment_ids"] if topology else []

    equipment_path = path / "equipment"
    equipment_folders = _list_child_folder_names(equipment_path)
    detected_equipment_ids, unexpected_equipment_folders, mapping_messages = _map_equipment_folders(
        equipment_folders
    )

    missing_expected_equipment_ids = [
        equipment_id
        for equipment_id in topology_equipment_ids
        if equipment_id not in detected_equipment_ids
    ]

    validation_messages = []
    if topology_id is None:
        validation_messages.append(
            f"Could not detect topology from configuration name {configuration_name!r}."
        )
    validation_messages.extend(_structure_validation_messages(path))
    validation_messages.extend(mapping_messages)
    for folder_name in unexpected_equipment_folders:
        validation_messages.append(
            f"Unexpected equipment folder {folder_name!r} detected; no registry mapping is defined."
        )
    for equipment_id in missing_expected_equipment_ids:
        validation_messages.append(
            f"Expected topology equipment_id {equipment_id!r} was not detected in equipment folders."
        )

    return {
        "configuration_name": configuration_name,
        "configuration_path": str(path),
        "detected_cooling_system_type": topology["cooling_system_type"] if topology else None,
        "detected_power_source": _detect_power_source(configuration_name),
        "detected_unit_capacity": _detect_unit_capacity(configuration_name),
        "configuration_file_exists": (path / "configuration.xlsx").is_file(),
        "scenario_file_exists": (path / "scenario.xlsx").is_file(),
        "input_folder_exists": (path / "input").is_dir(),
        "equipment_folder_exists": equipment_path.is_dir(),
        "equipment_folders": equipment_folders,
        "detected_equipment_ids": detected_equipment_ids,
        "missing_expected_equipment_ids": missing_expected_equipment_ids,
        "unexpected_equipment_folders": unexpected_equipment_folders,
        "topology_id": topology_id,
        "topology_display_name": topology["display_name"] if topology else None,
        "topology_equipment_ids": topology_equipment_ids,
        "validation_status": "ok" if not validation_messages else "warning",
        "validation_messages": validation_messages,
    }


def _detect_topology_id(configuration_name):
    normalized = _normalize_token(configuration_name)
    for prefix, topology_id in TOPOLOGY_NAME_PREFIXES:
        if normalized.startswith(prefix):
            return topology_id
    return None


def _detect_power_source(configuration_name):
    normalized = _normalize_token(configuration_name)
    tokens = normalized.split("_")
    for token, power_source in POWER_SOURCE_TOKENS.items():
        if token in tokens:
            return power_source
    return None


def _detect_unit_capacity(configuration_name):
    match = re.search(r"(?<![A-Z0-9])(\d+(?:\.\d+)?)\s*MW(?![A-Z0-9])", configuration_name, re.IGNORECASE)
    if not match:
        return None
    return f"{match.group(1)} MW"


def _list_child_folder_names(path):
    if not path.is_dir():
        return []
    return sorted([child.name for child in path.iterdir() if child.is_dir()], key=str.upper)


def _map_equipment_folders(equipment_folders):
    detected_equipment_ids = []
    unexpected_equipment_folders = []
    validation_messages = []

    for folder_name in equipment_folders:
        equipment_id, message = _map_equipment_folder(folder_name)
        if equipment_id is None:
            unexpected_equipment_folders.append(folder_name)
            continue
        if equipment_id not in detected_equipment_ids:
            detected_equipment_ids.append(equipment_id)
        if message:
            validation_messages.append(message)

    return detected_equipment_ids, unexpected_equipment_folders, validation_messages


def _map_equipment_folder(folder_name):
    normalized = _strip_trailing_instance_number(_normalize_token(folder_name))
    for prefix in sorted(EQUIPMENT_FOLDER_PREFIX_MAP, key=len, reverse=True):
        if normalized == prefix or normalized.startswith(f"{prefix}_"):
            return EQUIPMENT_FOLDER_PREFIX_MAP[prefix]
    return None, None


def _structure_validation_messages(path):
    checks = (
        ("configuration.xlsx", (path / "configuration.xlsx").is_file()),
        ("scenario.xlsx", (path / "scenario.xlsx").is_file()),
        ("input folder", (path / "input").is_dir()),
        ("equipment folder", (path / "equipment").is_dir()),
    )
    return [f"Missing {label}." for label, exists in checks if not exists]


def _normalize_token(value):
    return re.sub(r"_+", "_", re.sub(r"[^A-Z0-9.]+", "_", str(value).upper())).strip("_")


def _strip_trailing_instance_number(value):
    return re.sub(r"_\d+(?:\.\d+)?$", "", value)
