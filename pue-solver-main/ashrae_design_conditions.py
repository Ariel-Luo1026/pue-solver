"""Peak design weather condition provider."""

from json import load
from math import asin, cos, isfinite, radians, sin, sqrt
from pathlib import Path

try:
    from ashrae_online_lookup import lookup_online_ashrae_design_condition
except Exception:
    lookup_online_ashrae_design_condition = None

DATA_PATH = Path(__file__).resolve().with_name("ashrae_design_conditions_data.json")

_FALLBACK_STATIONS = [
    {
        "station_name": "WINSTON FIELD, TX, USA",
        "station_id": "722122",
        "country": "USA",
        "state": "TX",
        "latitude": 32.693,
        "longitude": -100.951,
        "db_max_20yr_C": 44.0,
        "db_min_20yr_C": -16.9,
        "design_conditions": {
            "extreme_annual_db_max_C": 44.0,
            "basis": "ASHRAE_20_year_extreme_annual_design_condition",
        },
    }
]


def _num(value, default=None):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_design_condition_stations(data_path=None):
    path = Path(data_path) if data_path else DATA_PATH
    try:
        with path.open(encoding="utf-8") as handle:
            rows = load(handle)
    except (OSError, ValueError, TypeError):
        rows = _FALLBACK_STATIONS
    if not isinstance(rows, list):
        rows = _FALLBACK_STATIONS
    return [row for row in rows if isinstance(row, dict)] or list(_FALLBACK_STATIONS)


def haversine_distance_km(latitude_a, longitude_a, latitude_b, longitude_b):
    latitude_a = _num(latitude_a)
    longitude_a = _num(longitude_a)
    latitude_b = _num(latitude_b)
    longitude_b = _num(longitude_b)
    if latitude_a is None or longitude_a is None or latitude_b is None or longitude_b is None:
        return float("inf")
    lat1 = radians(latitude_a)
    lat2 = radians(latitude_b)
    dlat = radians(latitude_b - latitude_a)
    dlon = radians(longitude_b - longitude_a)
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(a))


def _station_design_conditions(station):
    design_conditions = station.get("design_conditions")
    if not isinstance(design_conditions, dict):
        design_conditions = {}
    return {
        "extreme_annual_db_max_C": _num(
            design_conditions.get("extreme_annual_db_max_C"),
            _num(station.get("db_max_20yr_C"), 44.0),
        ),
        "basis": (
            design_conditions.get("basis")
            or "ASHRAE_20_year_extreme_annual_design_condition"
        ),
    }


def _station_result(station, distance_km):
    conditions = _station_design_conditions(station)
    return {
        "station_id": station.get("station_id") or "",
        "station_name": station.get("station_name") or "Unknown ASHRAE design station",
        "country": station.get("country") or "",
        "state": station.get("state") or "",
        "distance_km": float(distance_km),
        "latitude": _num(station.get("latitude"), None),
        "longitude": _num(station.get("longitude"), None),
        "extreme_annual_db_max_C": conditions["extreme_annual_db_max_C"],
        "basis": conditions["basis"],
    }


def find_nearest_ashrae_station(latitude, longitude, station_database):
    """Return nearest ASHRAE station and its 20-year DB max condition."""
    stations = [row for row in station_database if isinstance(row, dict)]
    if not stations:
        stations = list(_FALLBACK_STATIONS)
    latitude = _num(latitude)
    longitude = _num(longitude)
    best = min(
        stations,
        key=lambda row: haversine_distance_km(
            latitude,
            longitude,
            row.get("latitude"),
            row.get("longitude"),
        ),
    )
    distance = haversine_distance_km(latitude, longitude, best.get("latitude"), best.get("longitude"))
    if not isfinite(distance):
        valid_stations = [
            row
            for row in stations
            if isfinite(haversine_distance_km(latitude, longitude, row.get("latitude"), row.get("longitude")))
        ]
        if valid_stations:
            return find_nearest_ashrae_station(latitude, longitude, valid_stations)
        best = _FALLBACK_STATIONS[0]
        distance = haversine_distance_km(latitude, longitude, best.get("latitude"), best.get("longitude"))
    return _station_result(best, distance)


def get_peak_design_condition(latitude, longitude, source="ashrae_auto", endpoint=None, timeout_seconds=10):
    """Return nearest ASHRAE 20-year extreme design condition metadata."""
    latitude = _num(latitude)
    longitude = _num(longitude)
    stations = load_design_condition_stations()
    lookup_status = "failed"
    lookup_failure_reason = ""
    if latitude is None or longitude is None:
        matched = _station_result(stations[0], 0.0)
        source_label = "ASHRAE_local_cache"
        lookup_failure_reason = "project coordinates missing"
    else:
        matched = None
        if str(source or "ashrae_auto").strip().lower() in {"ashrae_auto", "automatic", "auto"}:
            if lookup_online_ashrae_design_condition is not None:
                online = lookup_online_ashrae_design_condition(latitude, longitude, endpoint=endpoint, timeout=timeout_seconds)
                lookup_status = online.get("lookup_status", "success") if isinstance(online, dict) else "failed"
                lookup_failure_reason = online.get("failure_reason", "") if isinstance(online, dict) else "invalid response"
                if isinstance(online, dict) and lookup_status == "success":
                    matched = {
                        "station_name": online["station_name"],
                        "station_id": online["station_id"],
                        "distance_km": online["distance_km"],
                        "latitude": online.get("station_latitude", online["latitude"]),
                        "longitude": online.get("station_longitude", online["longitude"]),
                        "extreme_annual_db_max_C": online.get("design_db_max_C", online["extreme_db_max_C"]),
                        "basis": online["temperature_basis"],
                    }
                    source_label = "ASHRAE_online"
                    lookup_failure_reason = ""
            else:
                lookup_failure_reason = "online lookup module unavailable"
        if matched is None:
            matched = find_nearest_ashrae_station(latitude, longitude, stations)
            source_label = "ASHRAE_local_cache"
            if not lookup_failure_reason:
                lookup_failure_reason = "online lookup unavailable"
    return {
        "source": source_label,
        "lookup_provider": "ASHRAE_online",
        "lookup_status": lookup_status if source_label == "ASHRAE_online" else "failed",
        "failure_reason": "" if source_label == "ASHRAE_online" else lookup_failure_reason,
        "station_name": matched["station_name"],
        "station_id": matched["station_id"],
        "station_distance_km": matched["distance_km"],
        "station_latitude": matched["latitude"],
        "station_longitude": matched["longitude"],
        "design_db_max_C": matched["extreme_annual_db_max_C"],
        "extreme_db_max_C": matched["extreme_annual_db_max_C"],
        "extreme_db_min_C": None,
        "temperature_basis": matched["basis"],
    }
