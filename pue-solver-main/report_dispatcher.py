"""Dispatch solver results to topology-specific report profile metadata."""

from copy import deepcopy

from report_profile_registry import (
    get_generic_report_profile,
    get_report_profile_for_topology,
)


def _annual_results(solver_result):
    if not isinstance(solver_result, dict):
        return {}
    annual = solver_result.get("annual_results")
    return annual if isinstance(annual, dict) else {}


def _field_value(annual, field):
    key = field.get("key")
    if key in annual:
        return annual.get(key)
    for fallback_key in field.get("fallback_keys", []):
        if fallback_key in annual:
            return annual.get(fallback_key)
    return None


def dispatch_report(topology, solver_result):
    """Return report profile metadata plus summary values for a topology.

    Unknown topologies intentionally return a generic PUE-only profile instead
    of raising; report export should remain possible for solver results that do
    not yet have topology-specific presentation metadata.
    """
    profile = get_report_profile_for_topology(topology)
    if profile is None:
        profile = get_generic_report_profile(topology or "unknown")
        profile["dispatch_status"] = "generic"
    else:
        profile["dispatch_status"] = "matched"

    annual = _annual_results(solver_result)
    summary = {}
    for field in profile.get("fields", []):
        summary[field["key"]] = _field_value(annual, field)

    dispatched = deepcopy(profile)
    dispatched["summary"] = summary
    return dispatched
