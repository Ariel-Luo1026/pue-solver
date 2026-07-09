"""Optional ACC V2 engine hook.

Phase 13E prepares a future integration point only. ACC V2 is disabled by
default and this module is not connected to the legacy solver calculation path.
"""

from dataclasses import dataclass
from typing import Any

from acc_v2_curve_lookup import ACCOperatingPoint, lookup_acc_curve
from acc_v2_diagnostics import ACCV2Diagnostic, build_acc_v2_preview, validate_acc_dataset


ENGINE_VERSION = "acc_v2_shadow_13f"


@dataclass(frozen=True)
class ACCV2ShadowResult:
    ambient_C: float | None
    load_ratio: float | None
    capacity_kW: float | None
    power_input_kW: float | None
    cop: float | None
    lookup_success: bool
    validation_warnings: tuple[str, ...]
    validation_errors: tuple[str, ...]
    engine_version: str = ENGINE_VERSION
    required_capacity_kW: float | None = None
    capacity_clamped: bool = False


@dataclass(frozen=True)
class ACCV2ProductionResult:
    source: str
    lookup_success: bool
    fallback_used: bool
    engine_version: str
    ambient_C: float | None
    load_ratio: float | None
    capacity_kW: float | None
    power_input_kW: float | None
    cop: float | None
    diagnostics: str | None = None
    required_capacity_kW: float | None = None
    power_input_per_unit_kW: float | None = None
    capacity_clamped: bool = False
    diagnostic_load_ratio: float | None = None


@dataclass
class ACCV2Engine:
    diagnostic: ACCV2Diagnostic

    @property
    def validation_summary(self):
        return self.diagnostic.validation_summary

    @property
    def acc_preview(self):
        return self.diagnostic.acc_preview

    def evaluate_operating_point(
        self,
        ambient_C,
        load_ratio=None,
        required_capacity_kW=None,
        nominal_unit_capacity_kW=None,
    ) -> ACCOperatingPoint:
        """Return one ACC V2 operating point using the read-only lookup layer."""
        return lookup_acc_curve(
            self.acc_preview,
            ambient_C=ambient_C,
            load_ratio=load_ratio,
            required_capacity_kW=required_capacity_kW,
            nominal_unit_capacity_kW=nominal_unit_capacity_kW,
        )


def create_acc_v2_engine(configuration_path):
    """Build diagnostics and return an initialized ACC V2 engine."""
    diagnostic = build_acc_v2_preview(configuration_path)
    acc_errors = _acc_engine_blocking_errors(diagnostic)
    if acc_errors:
        raise ValueError(
            "ACC V2 diagnostics are invalid: "
            + "; ".join(acc_errors)
        )
    return ACCV2Engine(diagnostic=diagnostic)


def _acc_engine_blocking_errors(diagnostic):
    acc_preview = diagnostic.acc_preview
    if acc_preview is None:
        return ["acc_unit: workbook not found"]
    errors = []
    if not acc_preview.required_columns_present:
        errors.append(f"acc_unit: missing required columns {acc_preview.missing_columns}")
    errors.extend(validate_acc_dataset(acc_preview).errors)
    diagnostics = acc_preview.metadata.get("diagnostics") if getattr(acc_preview, "metadata", None) else None
    if diagnostics and errors:
        errors.append(diagnostics)
    return errors


def is_acc_v2_enabled(project_input):
    """Return True only when project input explicitly enables ACC V2."""
    if not isinstance(project_input, dict):
        return False
    candidates = (
        project_input.get("acc_v2_enabled"),
        _get(project_input, "feature_flags", "acc_v2_enabled"),
        _get(project_input, "feature_flags", "acc_v2"),
        _get(project_input, "acc_v2", "enabled"),
    )
    return any(value is True for value in candidates)


def _get(source: dict[str, Any], *path):
    current = source
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
