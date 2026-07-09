"""Read-only ACC V2 curve diagnostics.

This module composes the Phase 13B reader and Phase 13C lookup engine into
structured diagnostics only. It does not import solver.py or alter any
calculation, UI, report, export, or benchmark path.
"""

from dataclasses import dataclass, field
from typing import Any

from acc_v2_curve_lookup import lookup_acc_curve, lookup_cdu_curve, lookup_rtc_curve
from acc_v2_curve_reader import ACCV2CurvePreview, read_acc_v2_equipment_curves


@dataclass(frozen=True)
class CurveSummary:
    minimum_ambient_C: float | None = None
    maximum_ambient_C: float | None = None
    ambient_count: int = 0
    minimum_load_ratio: float | None = None
    maximum_load_ratio: float | None = None
    load_ratio_count: int = 0
    number_of_points: int = 0
    capacity_range: tuple[float | None, float | None] = (None, None)
    power_range: tuple[float | None, float | None] = (None, None)
    cop_range: tuple[float | None, float | None] = (None, None)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationSummary:
    validation_status: str
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ACCV2Diagnostic:
    preview: ACCV2CurvePreview
    acc_preview: Any | None
    rtc_preview: Any | None
    cdu_preview: Any | None
    validation_summary: ValidationSummary
    curve_summaries: dict[str, CurveSummary] = field(default_factory=dict)
    lookup_samples: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


def build_acc_v2_preview(configuration_path):
    """Build a read-only ACC V2 diagnostic object for a configuration path."""
    preview = read_acc_v2_equipment_curves(configuration_path)
    acc_preview = preview.equipment_curves.get("acc_unit")
    rtc_preview = preview.equipment_curves.get("rtc")
    cdu_preview = preview.equipment_curves.get("cdu")

    validation = validate_acc_dataset(acc_preview)
    warnings = list(preview.warnings) + list(validation.warnings)
    errors = list(preview.errors) + list(validation.errors)
    acc_diagnostics = acc_preview.metadata.get("diagnostics") if getattr(acc_preview, "metadata", None) else None
    if acc_diagnostics and errors:
        errors.append(acc_diagnostics)
    curve_summaries = {
        "acc_unit": summarize_acc_curve(acc_preview),
        "rtc": summarize_rtc_curve(rtc_preview),
        "cdu": summarize_cdu_curve(cdu_preview),
    }
    samples = sample_lookup_report(preview)
    for equipment_id, sample in samples.items():
        for message in sample.get("errors", []):
            errors.append(f"{equipment_id}: {message}")

    return ACCV2Diagnostic(
        preview=preview,
        acc_preview=acc_preview,
        rtc_preview=rtc_preview,
        cdu_preview=cdu_preview,
        validation_summary=ValidationSummary(
            validation_status="valid" if not errors else "invalid",
            warnings=tuple(warnings),
            errors=tuple(errors),
        ),
        curve_summaries=curve_summaries,
        lookup_samples=samples,
        warnings=tuple(warnings),
        errors=tuple(errors),
        metadata={"configuration_name": preview.configuration_name},
    )


def summarize_acc_curve(preview):
    rows = _rows(preview)
    numeric = [_parse_acc_row(row, index) for index, row in enumerate(rows, start=1)]
    valid = [row for row, errors in numeric if not errors]
    if not valid:
        return CurveSummary(number_of_points=len(rows), metadata={"equipment_id": "acc_unit"})

    ambient_values = sorted({row["ambient_C"] for row in valid})
    load_values = sorted({row["load_ratio"] for row in valid})
    capacities = [row["capacity_kW"] for row in valid]
    powers = [row["power_input_kW"] for row in valid]
    cops = [row["unit_efficiency_kW_per_kW"] for row in valid]
    return CurveSummary(
        minimum_ambient_C=ambient_values[0],
        maximum_ambient_C=ambient_values[-1],
        ambient_count=len(ambient_values),
        minimum_load_ratio=load_values[0],
        maximum_load_ratio=load_values[-1],
        load_ratio_count=len(load_values),
        number_of_points=len(valid),
        capacity_range=(min(capacities), max(capacities)),
        power_range=(min(powers), max(powers)),
        cop_range=(min(cops), max(cops)),
        metadata={"equipment_id": "acc_unit"},
    )


def summarize_rtc_curve(preview):
    return _summarize_power_curve(preview, "rtc")


def summarize_cdu_curve(preview):
    return _summarize_power_curve(preview, "cdu")


def validate_acc_dataset(preview):
    """Validate ACC data and return warnings/errors instead of raising."""
    rows = _rows(preview)
    if not rows:
        return ValidationSummary("invalid", errors=("ACC dataset contains no rows.",))

    warnings = []
    errors = []
    parsed_rows = []
    seen = set()
    for index, row in enumerate(rows, start=1):
        parsed, row_errors = _parse_acc_row(row, index)
        errors.extend(row_errors)
        if row_errors:
            continue
        if parsed["capacity_kW"] <= 0:
            errors.append(f"Row {index}: capacity_kW must be positive.")
        if parsed["power_input_kW"] <= 0:
            errors.append(f"Row {index}: power_input_kW must be positive.")
        if parsed["unit_efficiency_kW_per_kW"] <= 0:
            errors.append(f"Row {index}: unit_efficiency_kW_per_kW must be positive.")
        point = (parsed["ambient_C"], parsed["load_ratio"])
        if point in seen:
            errors.append(f"Duplicate ACC operating point: {point}.")
        seen.add(point)
        parsed_rows.append(parsed)

    if parsed_rows:
        ambient_values = sorted({row["ambient_C"] for row in parsed_rows})
        load_values = sorted({row["load_ratio"] for row in parsed_rows})
        expected_count = len(ambient_values) * len(load_values)
        if len(parsed_rows) != expected_count:
            errors.append("ACC ambient/load grid is incomplete.")
        elif len(parsed_rows) == 1:
            warnings.append("ACC dataset contains a single operating point.")
    return ValidationSummary(
        validation_status="valid" if not errors else "invalid",
        warnings=tuple(warnings),
        errors=tuple(errors),
        metadata={"row_count": len(rows)},
    )


def sample_lookup_report(preview_or_diagnostic):
    """Return structured lookup samples for ACC, RTC, and CDU curves."""
    if isinstance(preview_or_diagnostic, ACCV2Diagnostic):
        preview = preview_or_diagnostic.preview
    else:
        preview = preview_or_diagnostic
    equipment_curves = getattr(preview, "equipment_curves", {}) or {}
    samples = {}

    acc_preview = equipment_curves.get("acc_unit")
    if acc_preview:
        samples["acc_unit"] = _safe_acc_samples(acc_preview)
    rtc_preview = equipment_curves.get("rtc")
    if rtc_preview:
        samples["rtc"] = _safe_power_samples(rtc_preview, lookup_rtc_curve)
    cdu_preview = equipment_curves.get("cdu")
    if cdu_preview:
        samples["cdu"] = _safe_power_samples(cdu_preview, lookup_cdu_curve)
    return samples


def _safe_acc_samples(preview):
    errors = []
    points = []
    summary = summarize_acc_curve(preview)
    if summary.number_of_points == 0:
        return {"samples": points, "errors": ["ACC curve has no valid sample points."]}
    requests = {
        "minimum": (summary.minimum_ambient_C, summary.minimum_load_ratio),
        "midpoint": (
            _midpoint(summary.minimum_ambient_C, summary.maximum_ambient_C),
            _midpoint(summary.minimum_load_ratio, summary.maximum_load_ratio),
        ),
        "maximum": (summary.maximum_ambient_C, summary.maximum_load_ratio),
    }
    for label, (ambient, load) in requests.items():
        try:
            point = lookup_acc_curve(preview, ambient, load)
            points.append({"label": label, "request": {"ambient_C": ambient, "load_ratio": load}, "result": point})
        except ValueError as exc:
            errors.append(str(exc))
    return {"samples": points, "errors": errors}


def _safe_power_samples(preview, lookup_fn):
    errors = []
    points = []
    summary = _summarize_power_curve(preview, getattr(preview, "equipment_id", "equipment"))
    if summary.number_of_points == 0:
        return {"samples": points, "errors": ["Power curve has no valid sample points."]}
    for label, load in {
        "minimum": summary.minimum_load_ratio,
        "midpoint": _midpoint(summary.minimum_load_ratio, summary.maximum_load_ratio),
        "maximum": summary.maximum_load_ratio,
    }.items():
        try:
            point = lookup_fn(preview, load)
            points.append({"label": label, "request": {"load_ratio": load}, "result": point})
        except ValueError as exc:
            errors.append(str(exc))
    return {"samples": points, "errors": errors}


def _summarize_power_curve(preview, equipment_id):
    rows = _rows(preview)
    parsed = [_parse_power_row(row, index) for index, row in enumerate(rows, start=1)]
    valid = [row for row, errors in parsed if not errors]
    if not valid:
        return CurveSummary(number_of_points=len(rows), metadata={"equipment_id": equipment_id})
    load_values = sorted({row["load_ratio"] for row in valid})
    powers = [row["power_kW"] for row in valid]
    return CurveSummary(
        minimum_load_ratio=load_values[0],
        maximum_load_ratio=load_values[-1],
        load_ratio_count=len(load_values),
        number_of_points=len(valid),
        power_range=(min(powers), max(powers)),
        metadata={"equipment_id": equipment_id},
    )


def _parse_acc_row(row, index):
    errors = []
    parsed = {}
    for field in ("ambient_C", "load_ratio", "capacity_kW", "power_input_kW", "unit_efficiency_kW_per_kW"):
        value = _float_or_none(row.get(field))
        if value is None:
            errors.append(f"Row {index}: {field} is missing or non-numeric.")
        parsed[field] = value
    return parsed, errors


def _parse_power_row(row, index):
    errors = []
    parsed = {}
    for field in ("load_ratio", "power_kW"):
        value = _float_or_none(row.get(field))
        if value is None:
            errors.append(f"Row {index}: {field} is missing or non-numeric.")
        parsed[field] = value
    return parsed, errors


def _rows(preview):
    return list(getattr(preview, "solver_curve_rows", None) or [])


def _float_or_none(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _midpoint(a, b):
    if a is None or b is None:
        return None
    return (a + b) / 2.0
