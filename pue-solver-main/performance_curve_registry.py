"""Hierarchical default performance-curve registry.

Curves are grouped by engineering equipment type and then model ID. This
module remains metadata-only and is not imported by solver.py.
"""

from pathlib import Path, PurePosixPath

from equipment_catalog import EQUIPMENT_CATALOG

PROJECT_ROOT = Path(__file__).resolve().parent
CURVE_LIBRARY_ROOT = PurePosixPath("data/performance_curves")


def _equipment_type_directory(equipment_type):
    normalized = equipment_type.upper().replace(" ", "_").replace("-", "_")
    if normalized in {"CHW_PUMP", "CW_PUMP", "HW_PUMP", "PUMP"}:
        return "pump"
    return {
        "ACC": "acc", "ABS": "abs", "CHILLER": "chiller",
        "DRY_COOLER": "dry_cooler", "COOLING_TOWER": "cooling_tower",
        "CDU": "cdu", "MAU": "mau", "RTC": "rtc", "ENGINE": "engine",
        "ENGINE_RADIATOR": "engine_radiator", "SMOKE_WATER_HX": "heat_exchanger",
    }.get(normalized, normalized.lower())


def _curve_type(equipment_type):
    directory = _equipment_type_directory(equipment_type)
    return {
        "pump": "pump_power_curve", "acc": "acc_performance_curve",
        "abs": "abs_performance_curve", "chiller": "chiller_cop_curve",
        "dry_cooler": "dry_cooler_performance_curve",
        "cooling_tower": "cooling_tower_performance_curve",
        "engine": "engine_efficiency_curve",
        "engine_radiator": "engine_radiator_performance_curve",
        "heat_exchanger": "heat_exchanger_performance_curve",
    }.get(directory, f"{directory}_performance_curve")


def build_default_curve_path(equipment_type, equipment_id):
    """Build a portable type/model path without hardcoding full filenames."""
    directory = CURVE_LIBRARY_ROOT / _equipment_type_directory(equipment_type)
    return (directory / f"{equipment_id}.xlsx").as_posix()


def _registry_entry(equipment_id, item):
    equipment_type = _equipment_type_directory(item["equipment_type"])
    directory = (CURVE_LIBRARY_ROOT / equipment_type).as_posix() + "/"
    filename = f"{equipment_id}.xlsx"
    return {
        "equipment_id": equipment_id,
        "equipment_type": equipment_type,
        "model_number": item["model_number"],
        "curve_type": _curve_type(item["equipment_type"]),
        "default_curve_directory": directory,
        "default_curve_filename": filename,
        "default_curve_path": build_default_curve_path(item["equipment_type"], equipment_id),
        "required": True,
        "description": f"Default {item['display_name']} performance curve.",
    }


PERFORMANCE_CURVE_REGISTRY = {}
_EQUIPMENT_CURVE_INDEX = {}
for _equipment_id, _item in EQUIPMENT_CATALOG.items():
    _entry = _registry_entry(_equipment_id, _item)
    PERFORMANCE_CURVE_REGISTRY.setdefault(_entry["equipment_type"], {})[_equipment_id] = _entry
    _EQUIPMENT_CURVE_INDEX[_equipment_id] = _entry


def get_default_curve_for_equipment(equipment_id):
    """Return model metadata from the type-grouped registry."""
    return _EQUIPMENT_CURVE_INDEX.get(equipment_id)


def resolve_curve_source(equipment_id, uploaded_curves=None):
    """Resolve uploaded > existing hierarchical default > missing warning."""
    uploaded_curves = uploaded_curves or {}
    if equipment_id in uploaded_curves and uploaded_curves[equipment_id] is not None:
        return {"equipment_id": equipment_id, "source_type": "uploaded", "file": uploaded_curves[equipment_id], "warning": None}

    default = get_default_curve_for_equipment(equipment_id)
    if default and (PROJECT_ROOT / default["default_curve_path"]).is_file():
        return {"equipment_id": equipment_id, "source_type": "default", "file": default["default_curve_path"], "warning": None}

    return {
        "equipment_id": equipment_id,
        "source_type": "missing",
        "file": None,
        "warning": f"No uploaded or available default performance curve for {equipment_id}.",
    }
