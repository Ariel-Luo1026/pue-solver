"""Optional ACC V2 engine hook.

Phase 13E prepares a future integration point only. ACC V2 is disabled by
default and this module is not connected to the legacy solver calculation path.
"""

from dataclasses import dataclass
from typing import Any

from acc_v2_curve_lookup import ACCOperatingPoint, lookup_acc_curve
from acc_v2_diagnostics import ACCV2Diagnostic, build_acc_v2_preview


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


@dataclass
class ACCV2Engine:
    diagnostic: ACCV2Diagnostic

    @property
    def validation_summary(self):
        return self.diagnostic.validation_summary

    @property
    def acc_preview(self):
        return self.diagnostic.acc_preview

    def evaluate_operating_point(self, ambient_C, load_ratio) -> ACCOperatingPoint:
        """Return one ACC V2 operating point using the read-only lookup layer."""
        return lookup_acc_curve(self.acc_preview, ambient_C=ambient_C, load_ratio=load_ratio)


def create_acc_v2_engine(configuration_path):
    """Build diagnostics and return an initialized ACC V2 engine."""
    diagnostic = build_acc_v2_preview(configuration_path)
    if diagnostic.validation_summary.validation_status != "valid":
        raise ValueError(
            "ACC V2 diagnostics are invalid: "
            + "; ".join(diagnostic.validation_summary.errors)
        )
    return ACCV2Engine(diagnostic=diagnostic)


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
