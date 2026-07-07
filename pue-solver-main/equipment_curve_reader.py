"""Generic Configuration Library equipment Solver_Curve reader.

This module is intentionally reusable and non-UI-facing. It reads equipment
workbooks and classifies Solver_Curve schemas, but it does not perform PUE
calculation or call solver.py.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from configuration_library_loader import _records, _resolve_actual_equipment_folder, read_xlsx_sheets
from equipment_registry import canonicalize_equipment_id


ONE_DIMENSIONAL_POWER = "one_dimensional_power"
TWO_DIMENSIONAL_POWER = "two_dimensional_power"
ELECTRICAL_EFFICIENCY = "electrical_efficiency"
ELECTRICAL_LOSS_FRACTION = "electrical_loss_fraction"
ELECTRICAL_LOSS_POWER = "electrical_loss_power"
UNKNOWN_SCHEMA = "unknown"


EQUIPMENT_ALIAS_PREFERRED_FOLDERS = {
    "acc_unit": ("ACC_2",),
    "chw_pump": ("CHW_PUMP_2",),
    "pump": ("CHW_PUMP_2",),
    "rtc": ("RTC_1&2", "RTC_2"),
    "rtc_1_2": ("RTC_1&2", "RTC_2"),
    "rtc_1&2": ("RTC_1&2", "RTC_2"),
    "auxiliary_load": ("RTC_1&2", "RTC_2"),
    "mau": ("MAU_1&2", "MAU_2"),
    "cdu": ("CDU_2",),
    "cdu_2": ("CDU_2",),
    "electrical_distribution": ("ELECTRICAL_DISTRIBUTION_2",),
    "electrical": ("ELECTRICAL_DISTRIBUTION_2",),
    "electrical_loss": ("ELECTRICAL_DISTRIBUTION_2",),
    "power_distribution": ("ELECTRICAL_DISTRIBUTION_2",),
    "distribution_loss": ("ELECTRICAL_DISTRIBUTION_2",),
    "engine_radiator": ("ENGINE_RADIATOR_1", "ENGINE_RADIATOR_2"),
    "radiator": ("ENGINE_RADIATOR_1", "ENGINE_RADIATOR_2"),
    "engine_radiator_1": ("ENGINE_RADIATOR_1", "ENGINE_RADIATOR_2"),
    "gas_engine": ("ENGINE_3", "ENGINE_2"),
    "engine": ("ENGINE_3", "ENGINE_2"),
    "generator": ("ENGINE_3", "ENGINE_2"),
    "engine_3": ("ENGINE_3", "ENGINE_2"),
}


@dataclass
class EquipmentCurvePreview:
    equipment_id: str
    curve_type: str = UNKNOWN_SCHEMA
    solver_curve_rows: list[dict[str, Any]] = field(default_factory=list)
    source_workbook: str | None = None
    source_sheet: str = "Solver_Curve"
    required_columns_present: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def find_equipment_workbook(configuration_path, equipment_id):
    """Find an equipment workbook by exact folder, canonical id, or known alias."""
    configuration_path = Path(configuration_path)
    equipment_root = configuration_path / "equipment"
    if not equipment_root.is_dir():
        return None

    candidates = _candidate_folder_names(equipment_id)
    for folder_name in candidates:
        workbook = equipment_root / folder_name / f"{folder_name}.xlsx"
        if workbook.is_file():
            return workbook

    try:
        folder_name = _resolve_actual_equipment_folder(equipment_root, canonicalize_equipment_id(equipment_id))
    except Exception:
        folder_name = None
    if folder_name:
        workbook = equipment_root / folder_name / f"{folder_name}.xlsx"
        if workbook.is_file():
            return workbook
    return None


def read_equipment_solver_curve(configuration_path, equipment_id):
    """Read and classify an equipment Solver_Curve workbook."""
    workbook = find_equipment_workbook(configuration_path, equipment_id)
    if workbook is None:
        return EquipmentCurvePreview(
            equipment_id=equipment_id,
            errors=[f"Equipment workbook missing for {equipment_id!r}."],
        )
    try:
        sheets = read_xlsx_sheets(workbook)
    except Exception as exc:
        return EquipmentCurvePreview(
            equipment_id=equipment_id,
            source_workbook=str(workbook),
            errors=[f"Could not read equipment workbook {workbook}: {exc}"],
        )
    if "Solver_Curve" not in sheets:
        return EquipmentCurvePreview(
            equipment_id=equipment_id,
            source_workbook=str(workbook),
            errors=[f"Solver_Curve sheet missing in {workbook}."],
        )
    rows = _records(sheets["Solver_Curve"])
    preview = preview_from_solver_curve_rows(
        equipment_id=equipment_id,
        rows=rows,
        source_workbook=str(workbook),
        source_sheet="Solver_Curve",
    )
    return preview


def preview_from_curve_dict(equipment_id, curve, source_workbook=None, source_sheet="Solver_Curve"):
    """Build a generic preview from an already-loaded solver curve dictionary."""
    if not isinstance(curve, dict):
        return EquipmentCurvePreview(
            equipment_id=equipment_id,
            source_workbook=source_workbook,
            source_sheet=source_sheet,
            errors=[f"Curve for {equipment_id!r} is missing or invalid."],
        )
    rows = curve.get("points")
    if not isinstance(rows, list):
        rows = curve.get("data", [])
    x_axis = curve.get("x_axis", "load_ratio")
    y_axis = curve.get("y_axis", "load_ratio")
    output = curve.get("output", "power_kW")
    normalized_rows = []
    for point in rows if isinstance(rows, list) else []:
        if isinstance(point, dict):
            row = dict(point)
            if x_axis in row and x_axis != "load_ratio" and "load_ratio" not in row:
                row["load_ratio"] = row.get(x_axis)
            if y_axis in row and y_axis != "load_ratio" and "load_ratio" not in row:
                row["load_ratio"] = row.get(y_axis)
            if output in row and output not in ("power_kW", "power_input_kW", "efficiency", "loss_fraction", "loss_kW"):
                row["power_kW"] = row.get(output)
            if "engine_output_kW" in row and "power_kW" not in row:
                row["power_kW"] = row.get("engine_output_kW")
            if "radiator_fan_power_kW" in row and "power_kW" not in row:
                row["power_kW"] = row.get("radiator_fan_power_kW")
            normalized_rows.append(row)
        elif isinstance(point, (list, tuple)) and len(point) >= 2:
            normalized_rows.append({"load_ratio": point[0], output: point[1]})
    return preview_from_solver_curve_rows(
        equipment_id=equipment_id,
        rows=normalized_rows,
        source_workbook=source_workbook,
        source_sheet=source_sheet,
    )


def preview_from_solver_curve_rows(equipment_id, rows, source_workbook=None, source_sheet="Solver_Curve"):
    rows = list(rows) if isinstance(rows, list) else []
    rows = [_normalize_power_aliases(row) for row in rows]
    curve_type, required = detect_curve_type(rows)
    preview = EquipmentCurvePreview(
        equipment_id=equipment_id,
        curve_type=curve_type,
        solver_curve_rows=rows,
        source_workbook=source_workbook,
        source_sheet=source_sheet,
        required_columns_present=curve_type != UNKNOWN_SCHEMA,
    )
    if not rows:
        preview.errors.append("Solver_Curve contains no rows.")
        return preview
    if curve_type == UNKNOWN_SCHEMA:
        preview.errors.append(
            "Unknown Solver_Curve schema. Expected load_ratio with power_kW, efficiency, "
            "loss_fraction, loss_kW, or ambient_C/load_ratio/power_input_kW."
        )
        return preview
    missing = [column for column in required if not any(column in row for row in rows)]
    if missing:
        preview.required_columns_present = False
        preview.errors.append(f"Solver_Curve missing required columns: {', '.join(missing)}.")
    return preview


def _normalize_power_aliases(row):
    if not isinstance(row, dict):
        return row
    normalized = dict(row)
    if "engine_output_kW" in normalized and "power_kW" not in normalized:
        normalized["power_kW"] = normalized.get("engine_output_kW")
    if "radiator_fan_power_kW" in normalized and "power_kW" not in normalized:
        normalized["power_kW"] = normalized.get("radiator_fan_power_kW")
    return normalized


def detect_curve_type(rows):
    columns = set()
    for row in rows or []:
        if isinstance(row, dict):
            columns.update(row.keys())
    if {"ambient_C", "load_ratio", "power_input_kW"}.issubset(columns):
        return TWO_DIMENSIONAL_POWER, ("ambient_C", "load_ratio", "power_input_kW")
    if {"load_ratio", "power_kW"}.issubset(columns):
        return ONE_DIMENSIONAL_POWER, ("load_ratio", "power_kW")
    if {"load_ratio", "efficiency"}.issubset(columns):
        return ELECTRICAL_EFFICIENCY, ("load_ratio", "efficiency")
    if {"load_ratio", "loss_fraction"}.issubset(columns):
        return ELECTRICAL_LOSS_FRACTION, ("load_ratio", "loss_fraction")
    if {"load_ratio", "loss_kW"}.issubset(columns):
        return ELECTRICAL_LOSS_POWER, ("load_ratio", "loss_kW")
    return UNKNOWN_SCHEMA, ()


def _candidate_folder_names(equipment_id):
    text = str(equipment_id)
    canonical = canonicalize_equipment_id(text)
    mapped = list(EQUIPMENT_ALIAS_PREFERRED_FOLDERS.get(text, ()))
    mapped.extend(EQUIPMENT_ALIAS_PREFERRED_FOLDERS.get(canonical, ()))
    if mapped:
        names = mapped + [text]
    else:
        names = [text]
    return list(dict.fromkeys(names))
