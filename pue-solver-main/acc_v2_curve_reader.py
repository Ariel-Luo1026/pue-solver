"""ACC V2 equipment curve reader preview.

Phase 13B reads and validates equipment workbooks only. It is intentionally
not connected to solver.py, ACCCalculator.run(), UI, reports, or exported HTML.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from configuration_library_loader import (
    _records,
    _resolve_actual_equipment_folder,
    read_xlsx_sheets,
)
from equipment_registry import canonicalize_equipment_id


STANDARD_SHEETS = ("Information", "Metadata", "Performance_Map", "Solver_Curve", "Validation")
ACC_OPTIONAL_SHEETS = (
    "Efficiency_Map",
    "Power_Input_Map",
    "Capacity_Map",
    "Condenser_Performance",
)

ACC_SOLVER_CURVE_COLUMNS = (
    "ambient_C",
    "capacity_kW",
    "power_input_kW",
)
ACC_DERIVABLE_COP_COLUMNS = ("capacity_kW", "power_input_kW")
RTC_SOLVER_CURVE_COLUMNS = ("load_ratio", "power_kW")
CDU_SOLVER_CURVE_COLUMNS = ("load_ratio", "power_kW")
CHW_PUMP_SOLVER_CURVE_COLUMNS = ("load_ratio", "power_kW")


@dataclass
class EquipmentCurvePreview:
    equipment_id: str
    folder_name: str | None
    workbook_path: str | None
    sheet_names: list[str] = field(default_factory=list)
    solver_curve_rows: list[dict[str, Any]] = field(default_factory=list)
    required_columns_present: bool = False
    missing_columns: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ACCV2CurvePreview:
    configuration_name: str
    equipment_curves: dict[str, EquipmentCurvePreview] = field(default_factory=dict)
    validation_status: str = "unknown"
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def find_equipment_workbook(configuration_path, equipment_id):
    """Find an equipment workbook by canonical or legacy equipment ID."""
    configuration_path = Path(configuration_path)
    equipment_root = configuration_path / "equipment"
    folder_name = _resolve_actual_equipment_folder(equipment_root, canonicalize_equipment_id(equipment_id))
    workbook_path = equipment_root / folder_name / f"{folder_name}.xlsx"
    return workbook_path if workbook_path.is_file() else None


def read_equipment_solver_curve(workbook_path, expected_columns):
    """Read Solver_Curve rows from an equipment workbook."""
    workbook_path = Path(workbook_path)
    is_acc = _is_acc_workbook_path(workbook_path)
    if is_acc:
        _print_acc_workbook_before_open(workbook_path)
    sheets = read_xlsx_sheets(workbook_path)
    if is_acc:
        _print_acc_workbook_loaded(sheets)
        _print_acc_solver_curve_selection("Solver_Curve", sheets)
    if "Solver_Curve" not in sheets:
        if is_acc:
            print(f"ACC Solver_Curve sheet missing; available sheet names={list(sheets)}")
        raise ValueError(f"Solver_Curve sheet missing in {workbook_path}")
    rows = _records(sheets["Solver_Curve"])
    if is_acc:
        _print_acc_solver_curve_rows(rows)
    validate_solver_curve_columns(rows, expected_columns)
    return rows


def validate_solver_curve_columns(rows, expected_columns):
    """Validate solver-curve columns and return a validation dictionary."""
    available_columns = set()
    for row in rows or []:
        available_columns.update(row.keys())
    missing_columns = [column for column in expected_columns if column not in available_columns]
    warnings = []
    if not rows:
        warnings.append("Solver_Curve contains no data rows.")
    for row_index, row in enumerate(rows or [], start=2):
        load_ratio = _float_or_none(row.get("load_ratio"))
        if load_ratio is not None and not 0 <= load_ratio <= 1:
            warnings.append(f"Row {row_index}: load_ratio {load_ratio} is outside 0–1.")
    return {
        "required_columns_present": not missing_columns,
        "missing_columns": missing_columns,
        "warnings": warnings,
    }


def derive_acc_cop_if_missing(row):
    """Return a copied ACC row with derived COP when possible plus warnings."""
    derived = dict(row)
    warnings = []
    cop = _float_or_none(derived.get("unit_efficiency_kW_per_kW"))
    if cop is not None:
        return derived, warnings

    capacity_kw = _float_or_none(derived.get("capacity_kW"))
    power_input_kw = _float_or_none(derived.get("power_input_kW"))
    if capacity_kw is not None and power_input_kw and power_input_kw > 0:
        derived["unit_efficiency_kW_per_kW"] = capacity_kw / power_input_kw
        warnings.append("unit_efficiency_kW_per_kW missing; derived COP from capacity_kW / power_input_kW.")
    else:
        warnings.append("unit_efficiency_kW_per_kW missing and could not be derived.")
    return derived, warnings


def read_acc_v2_equipment_curves(configuration_path):
    """Read preview curves for ACC V2 required equipment."""
    configuration_path = Path(configuration_path)
    equipment_specs = {
        "acc_unit": ACC_SOLVER_CURVE_COLUMNS,
        "rtc": RTC_SOLVER_CURVE_COLUMNS,
        "cdu": CDU_SOLVER_CURVE_COLUMNS,
        "pump": CHW_PUMP_SOLVER_CURVE_COLUMNS,
    }
    preview = ACCV2CurvePreview(
        configuration_name=configuration_path.name,
        metadata={"configuration_path": str(configuration_path)},
    )

    for equipment_id, expected_columns in equipment_specs.items():
        curve_preview = _read_single_equipment_preview(configuration_path, equipment_id, expected_columns)
        preview.equipment_curves[equipment_id] = curve_preview
        preview.warnings.extend(f"{equipment_id}: {warning}" for warning in curve_preview.warnings)
        if not curve_preview.required_columns_present:
            preview.errors.append(
                f"{equipment_id}: missing required columns {curve_preview.missing_columns}"
            )
        if curve_preview.workbook_path is None:
            preview.errors.append(f"{equipment_id}: workbook not found")

    preview.validation_status = "valid" if not preview.errors else "invalid"
    return preview


def _read_single_equipment_preview(configuration_path, equipment_id, expected_columns):
    workbook_path = find_equipment_workbook(configuration_path, equipment_id)
    if workbook_path is None:
        diagnostics = _build_acc_diagnostics(None, requested_sheet_name="Solver_Curve") if equipment_id == "acc_unit" else ""
        return EquipmentCurvePreview(
            equipment_id=equipment_id,
            folder_name=None,
            workbook_path=None,
            required_columns_present=False,
            missing_columns=list(expected_columns),
            warnings=["Required equipment workbook not found."],
            metadata={"canonical_equipment_id": canonicalize_equipment_id(equipment_id), "diagnostics": diagnostics}
            if diagnostics else {"canonical_equipment_id": canonicalize_equipment_id(equipment_id)},
        )

    is_acc = equipment_id == "acc_unit"
    if is_acc:
        _print_acc_workbook_before_open(workbook_path)
    sheets = read_xlsx_sheets(workbook_path)
    sheet_names = list(sheets)
    if is_acc:
        _print_acc_workbook_loaded(sheets)
        _print_acc_solver_curve_selection("Solver_Curve", sheets)
    warnings = _optional_sheet_warnings(sheet_names, equipment_id)
    selected_sheet_name = _select_solver_curve_sheet(equipment_id, sheet_names)
    diagnostics = _build_acc_diagnostics(workbook_path, sheets=sheets, requested_sheet_name="Solver_Curve") if is_acc else ""
    if selected_sheet_name is None:
        if is_acc:
            print(f"ACC Solver_Curve sheet missing; available sheet names={sheet_names}")
        return EquipmentCurvePreview(
            equipment_id=equipment_id,
            folder_name=workbook_path.parent.name,
            workbook_path=str(workbook_path),
            sheet_names=sheet_names,
            required_columns_present=False,
            missing_columns=list(expected_columns),
            warnings=warnings + ["Solver_Curve sheet missing."],
            metadata={"canonical_equipment_id": canonicalize_equipment_id(equipment_id), **({"diagnostics": diagnostics} if diagnostics else {})},
        )

    rows = _records(sheets[selected_sheet_name])
    if is_acc:
        _print_acc_solver_curve_rows(rows)
        diagnostics = _build_acc_diagnostics(workbook_path, sheets=sheets, requested_sheet_name="Solver_Curve", rows=rows)
    if equipment_id == "acc_unit":
        rows, cop_warnings = _derive_acc_rows(rows)
        warnings.extend(cop_warnings)
        expected_columns = tuple(
            column for column in expected_columns if column != "unit_efficiency_kW_per_kW"
        )
        warnings.extend(_acc_curve_warnings(rows))

    validation = validate_solver_curve_columns(rows, expected_columns)
    warnings.extend(validation["warnings"])
    return EquipmentCurvePreview(
        equipment_id=equipment_id,
        folder_name=workbook_path.parent.name,
        workbook_path=str(workbook_path),
        sheet_names=sheet_names,
        solver_curve_rows=rows,
        required_columns_present=validation["required_columns_present"],
        missing_columns=validation["missing_columns"],
        warnings=warnings,
        metadata={
            "canonical_equipment_id": canonicalize_equipment_id(equipment_id),
            "selected_solver_curve_sheet": selected_sheet_name,
            **({"diagnostics": diagnostics} if diagnostics else {}),
        },
    )


def _derive_acc_rows(rows):
    derived_rows = []
    warnings = []
    for row_index, row in enumerate(rows, start=2):
        derived, row_warnings = derive_acc_cop_if_missing(row)
        derived_rows.append(derived)
        warnings.extend(f"Row {row_index}: {warning}" for warning in row_warnings)
    return derived_rows, warnings


def _optional_sheet_warnings(sheet_names, equipment_id):
    expected_optional = STANDARD_SHEETS
    if equipment_id == "acc_unit":
        expected_optional = STANDARD_SHEETS + ACC_OPTIONAL_SHEETS
    return [
        f"Optional sheet {sheet_name!r} is missing."
        for sheet_name in expected_optional
        if sheet_name != "Solver_Curve" and sheet_name not in sheet_names
    ]


def _select_solver_curve_sheet(equipment_id, sheet_names):
    if equipment_id == "pump" or canonicalize_equipment_id(equipment_id).startswith("CHW_PUMP"):
        return "Solver_Curve" if "Solver_Curve" in sheet_names else None
    return "Solver_Curve" if "Solver_Curve" in sheet_names else None


def _acc_curve_warnings(rows):
    warnings = []
    seen_points = set()
    for row_index, row in enumerate(rows, start=2):
        ambient = row.get("ambient_C")
        if ambient is None:
            warnings.append(f"Row {row_index}: ambient_C is missing.")
        point = (ambient, row.get("capacity_kW"))
        if point in seen_points:
            warnings.append(f"Row {row_index}: duplicate ambient_C/capacity_kW point {point}.")
        seen_points.add(point)
    return warnings


def _float_or_none(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_acc_workbook_path(workbook_path):
    return str(Path(workbook_path).stem).upper().startswith("ACC_")


def _print_acc_workbook_before_open(workbook_path):
    workbook_path = Path(workbook_path)
    exists = workbook_path.is_file()
    file_size = workbook_path.stat().st_size if exists else None
    print(f"ACC workbook path={workbook_path}")
    print(f"ACC workbook exists={exists}")
    print(f"ACC workbook file size={file_size}")


def _print_acc_workbook_loaded(sheets):
    print("ACC workbook loaded successfully")
    print(f"ACC workbook sheet names={list(sheets)}")


def _print_acc_solver_curve_selection(requested_sheet_name, sheets):
    print(f"ACC Solver_Curve requested sheet name={requested_sheet_name}")
    print(f"ACC Solver_Curve available sheet names={list(sheets)}")


def _print_acc_solver_curve_rows(rows):
    columns = []
    for row in rows or []:
        for column in row.keys():
            if column not in columns:
                columns.append(column)
    print(f"ACC Solver_Curve row count={len(rows or [])}")
    print(f"ACC Solver_Curve column count={len(columns)}")
    print(f"ACC Solver_Curve first five rows={(rows or [])[:5]}")


def _build_acc_diagnostics(workbook_path, sheets=None, requested_sheet_name="Solver_Curve", rows=None):
    lines = ["ACC workbook diagnostics:"]
    if workbook_path is None:
        lines.extend([
            "workbook path=None",
            "file exists=False",
            "file size=None",
        ])
    else:
        workbook_path = Path(workbook_path)
        exists = workbook_path.is_file()
        file_size = workbook_path.stat().st_size if exists else None
        lines.extend([
            f"workbook path={workbook_path}",
            f"file exists={exists}",
            f"file size={file_size}",
        ])
    sheet_names = list(sheets) if isinstance(sheets, dict) else []
    lines.extend([
        f"workbook sheet names={sheet_names}",
        f"requested sheet name={requested_sheet_name}",
        f"available sheet names={sheet_names}",
    ])
    if rows is None and isinstance(sheets, dict) and requested_sheet_name in sheets:
        rows = _records(sheets[requested_sheet_name])
    if rows is not None:
        columns = []
        for row in rows or []:
            for column in row.keys():
                if column not in columns:
                    columns.append(column)
        lines.extend([
            f"detected header row={columns}",
            f"row count={len(rows or [])}",
            f"column count={len(columns)}",
            f"first five rows={(rows or [])[:5]}",
        ])
    return "\n".join(lines)
