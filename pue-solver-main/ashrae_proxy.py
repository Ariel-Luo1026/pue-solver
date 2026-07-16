"""Local ASHRAE online lookup proxy.

This module runs outside the browser/Pyodide runtime and performs the ASHRAE
Meteo requests server-side, avoiding browser CORS limits.  The callable API is
kept small so the development HTTP server can expose it directly.
"""

from ashrae_online_lookup import query_ashrae_online


def _failure(reason, status="failed"):
    return {
        "lookup_status": "failed",
        "online_status": status,
        "failure_reason": reason,
        "fallback_status": "manual_override_required",
        "source": "ASHRAE_online_proxy",
        "lookup_provider": "ASHRAE_online_proxy",
        "lookup_method": "ASHRAE_proxy",
    }


def query_ashrae_design_condition(latitude, longitude, timeout_seconds=10):
    """Return normalized ASHRAE design condition data through the local proxy."""
    try:
        result = query_ashrae_online(latitude, longitude, timeout_seconds=timeout_seconds)
    except Exception as exc:
        return _failure(f"browser_network_failure: {exc.__class__.__name__}: {exc}")

    if not isinstance(result, dict):
        return _failure("invalid proxy response")

    if result.get("lookup_status") != "success":
        return _failure(result.get("failure_reason") or "ASHRAE online proxy lookup failed")

    return {
        "station_name": result.get("station_name"),
        "station_id": result.get("station_id"),
        "latitude": result.get("station_latitude", result.get("latitude")),
        "longitude": result.get("station_longitude", result.get("longitude")),
        "distance_km": result.get("distance_km"),
        "design_db_max_C": result.get("design_db_max_C"),
        "extreme_db_max_C": result.get("extreme_db_max_C", result.get("design_db_max_C")),
        "source": "ASHRAE_online_proxy",
        "lookup_provider": "ASHRAE_online_proxy",
        "lookup_method": "ASHRAE_proxy",
        "lookup_status": "success",
        "online_status": "success",
        "failure_reason": "",
        "fallback_status": "not_used",
        "design_condition_basis": result.get("design_condition_basis", "20-year Extreme Annual Design Condition"),
        "temperature_basis": result.get(
            "temperature_basis",
            "ASHRAE_20_year_extreme_annual_design_condition",
        ),
    }
