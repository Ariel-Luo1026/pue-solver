"""Unified engineering report section framework."""

from report_sections.report_section_registry import (
    COMMON_REPORT_SECTIONS,
    COMMON_REPORT_SECTION_IDS,
    build_report_sections,
    list_common_report_sections,
    topology_specific_sections,
)

__all__ = [
    "COMMON_REPORT_SECTIONS",
    "COMMON_REPORT_SECTION_IDS",
    "build_report_sections",
    "list_common_report_sections",
    "topology_specific_sections",
]
