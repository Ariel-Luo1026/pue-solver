"""Equipment metadata loading and validation for Configuration Library folders."""

import json
from copy import deepcopy
from pathlib import Path

from equipment_curve_registry import validate_curve_type_supported
from equipment_type_registry import get_equipment_type, normalize_equipment_type


REQUIRED_EQUIPMENT_METADATA_FIELDS = [
    "equipment_id",
    "equipment_type",
    "display_name",
    "curve_type",
    "unit_system",
    "status",
]

OPTIONAL_EQUIPMENT_METADATA_FIELDS = [
    "schema_version",
    "manufacturer",
    "model",
    "rated_capacity_kW",
    "power_input_type",
    "solver_curve_sheet",
    "notes",
]


def load_equipment_metadata(path):
    """Load and normalize equipment_metadata.json from a file or folder path."""
    metadata_path = Path(path)
    if metadata_path.is_dir():
        metadata_path = metadata_path / "equipment_metadata.json"
    with metadata_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return normalize_equipment_metadata(payload, metadata_path)


def normalize_equipment_metadata(metadata, source_path=None):
    """Return a normalized metadata object while preserving declared values."""
    data = deepcopy(metadata) if isinstance(metadata, dict) else {}
    if data.get("equipment_type"):
        data["equipment_type"] = normalize_equipment_type(data["equipment_type"])
    if "schema_version" not in data:
        data["schema_version"] = "1.0"
    if "solver_curve_sheet" not in data:
        data["solver_curve_sheet"] = "Solver_Curve"
    if source_path is not None:
        data["_metadata_path"] = str(source_path)
    return data


def validate_equipment_metadata(metadata, equipment_folder=None):
    """Validate metadata schema and registry compatibility."""
    issues = []
    data = normalize_equipment_metadata(metadata) if isinstance(metadata, dict) else {}
    if not isinstance(metadata, dict):
        issues.append("Missing equipment metadata: equipment_metadata.json is missing or invalid.")
    for field in REQUIRED_EQUIPMENT_METADATA_FIELDS:
        if data.get(field) in (None, ""):
            issues.append(f"Missing required equipment metadata field: {field}")

    equipment_type = data.get("equipment_type")
    registry_item = get_equipment_type(equipment_type)
    if equipment_type and registry_item is None:
        issues.append(f"Unknown equipment_type: {equipment_type}")

    curve_type = data.get("curve_type")
    curve_schema = ""
    if equipment_type and registry_item and curve_type:
        curve_validation = validate_curve_type_supported(equipment_type, curve_type)
        if curve_validation["status"] == "error":
            issues.extend(curve_validation["issues"])
        else:
            curve_schema = curve_validation.get("curve_schema", "")

    folder = Path(equipment_folder) if equipment_folder is not None else None
    if folder is not None:
        if data.get("equipment_id") and data.get("equipment_id") != folder.name:
            issues.append(f"equipment_id {data.get('equipment_id')} does not match folder name {folder.name}")
        workbook = folder / f"{folder.name}.xlsx"
        if not workbook.is_file():
            issues.append(f"Referenced workbook missing: {workbook.name}")

    return {
        "status": "error" if issues else "valid",
        "equipment_id": data.get("equipment_id", ""),
        "equipment_type": data.get("equipment_type", ""),
        "curve_type": data.get("curve_type", ""),
        "curve_schema": curve_schema,
        "issues": issues,
        "metadata": data,
    }


def validate_equipment_folder(equipment_folder):
    """Validate the preferred equipment folder structure."""
    folder = Path(equipment_folder)
    metadata_path = folder / "equipment_metadata.json"
    if not metadata_path.is_file():
        return {
            "status": "error",
            "equipment_id": folder.name,
            "equipment_type": "",
            "curve_type": "",
            "curve_schema": "",
            "issues": ["Missing equipment metadata: equipment_metadata.json is missing."],
            "metadata": {},
        }
    try:
        metadata = load_equipment_metadata(metadata_path)
    except Exception as exc:
        return {
            "status": "error",
            "equipment_id": folder.name,
            "equipment_type": "",
            "curve_type": "",
            "curve_schema": "",
            "issues": [f"Could not load equipment_metadata.json: {exc}"],
            "metadata": {},
        }
    return validate_equipment_metadata(metadata, equipment_folder=folder)
