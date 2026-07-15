"""Online ASHRAE design-condition lookup adapter.

The public solver calls this module through ``ashrae_design_conditions`` so
provider wiring stays out of solver.py.  Set ``ASHRAE_DESIGN_CONDITIONS_URL``
to an ASHRAE-compatible endpoint; the adapter queries it with ``latitude`` and
``longitude`` parameters and normalizes the JSON response.
"""

from json import loads
from math import asin, cos, isfinite, radians, sin, sqrt
from os import environ
from socket import timeout as SocketTimeout
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


def _num(value, default=None):
    try:
        if value is None or value == "":
            return default
        number = float(value)
        if not isfinite(number):
            return default
        return number
    except (TypeError, ValueError):
        return default


def _failure(reason):
    return {
        "lookup_status": "failed",
        "failure_reason": reason,
        "lookup_provider": "ASHRAE_online",
        "source": "ASHRAE_online",
    }


def _distance_km(latitude_a, longitude_a, latitude_b, longitude_b):
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


def _first_present(row, keys):
    if not isinstance(row, dict):
        return None
    for key in keys:
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
    return None


def _design_db_value(row):
    return _num(
        _first_present(
            row,
            (
                "design_db_max_C",
                "extreme_db_max_C",
                "extreme_annual_db_max_C",
                "db_max_20yr_C",
                "dbMax20YearC",
            ),
        )
    )


def normalize_online_station(row, latitude=None, longitude=None):
    """Return the shared peak-design station shape, or None for invalid data."""
    if isinstance(row, dict) and isinstance(row.get("station"), dict):
        merged = dict(row.get("station"))
        merged.update({key: value for key, value in row.items() if key != "station"})
        row = merged
    if not isinstance(row, dict):
        return None
    station_name = _first_present(row, ("station_name", "name", "station"))
    station_id = _first_present(row, ("station_id", "wmo", "wmo_id", "id"))
    station_latitude = _num(_first_present(row, ("station_latitude", "latitude", "lat")))
    station_longitude = _num(_first_present(row, ("station_longitude", "longitude", "lon", "lng")))
    extreme_db_max = _design_db_value(row)
    if not station_name or not station_id or station_latitude is None or station_longitude is None or extreme_db_max is None:
        return None
    distance = _num(_first_present(row, ("distance_km", "station_distance_km")))
    if distance is None:
        distance = _distance_km(latitude, longitude, station_latitude, station_longitude)
    if not isfinite(distance):
        return None
    return {
        "station_name": str(station_name),
        "station_id": str(station_id),
        "station_latitude": station_latitude,
        "station_longitude": station_longitude,
        "latitude": station_latitude,
        "longitude": station_longitude,
        "distance_km": float(distance),
        "design_db_max_C": float(extreme_db_max),
        "extreme_db_max_C": float(extreme_db_max),
        "extreme_db_min_C": _num(_first_present(row, ("extreme_db_min_C", "db_min_20yr_C"))),
        "source": "ASHRAE_online",
        "lookup_status": "success",
        "failure_reason": "",
        "lookup_provider": "ASHRAE_online",
        "design_condition_basis": "20-year Extreme Annual Design Condition",
        "temperature_basis": (
            _first_present(row, ("temperature_basis", "basis"))
            or "ASHRAE_20_year_extreme_annual_design_condition"
        ),
    }


def _station_failure_reason(row):
    if not isinstance(row, dict):
        return "Invalid ASHRAE response format"
    station_name = _first_present(row, ("station_name", "name", "station"))
    station_id = _first_present(row, ("station_id", "wmo", "wmo_id", "id"))
    station_latitude = _num(_first_present(row, ("station_latitude", "latitude", "lat")))
    station_longitude = _num(_first_present(row, ("station_longitude", "longitude", "lon", "lng")))
    if not station_name or not station_id or station_latitude is None or station_longitude is None:
        return "Invalid ASHRAE response format"
    if _design_db_value(row) is None:
        return "ASHRAE online response missing design temperature"
    return "Invalid ASHRAE response format"


def _extract_station_rows(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("stations", "results", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return [payload]


def _lookup_from_rows(latitude, longitude, rows):
    candidates = []
    failure_reasons = []
    for row in rows:
        normalized = normalize_online_station(row, latitude, longitude)
        if normalized is None:
            failure_reasons.append(_station_failure_reason(row))
        else:
            candidates.append(normalized)
    if not candidates:
        for reason in ("ASHRAE online response missing design temperature", "Invalid ASHRAE response format"):
            if reason in failure_reasons:
                return _failure(reason)
        return _failure("Invalid ASHRAE response format")
    return min(candidates, key=lambda row: row["distance_km"])


def _fetch_endpoint(latitude, longitude, endpoint, timeout):
    separator = "&" if "?" in endpoint else "?"
    url = f"{endpoint}{separator}{urlencode({'latitude': latitude, 'longitude': longitude})}"
    with urlopen(url, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return loads(body)


def query_ashrae_online(latitude, longitude, timeout_seconds=10, endpoint=None):
    """Return nearest online ASHRAE design-condition station or failure status."""
    latitude = _num(latitude)
    longitude = _num(longitude)
    if latitude is None or longitude is None:
        return _failure("project coordinates missing")
    if str(environ.get("ASHRAE_ONLINE_LOOKUP_DISABLED", "")).strip().lower() in {"1", "true", "yes"}:
        return _failure("online lookup disabled")
    endpoint = endpoint or environ.get("ASHRAE_DESIGN_CONDITIONS_URL")
    if not endpoint:
        return _failure("Online ASHRAE provider unavailable")
    try:
        payload = _fetch_endpoint(latitude, longitude, endpoint, timeout_seconds)
    except (SocketTimeout, TimeoutError):
        return _failure("ASHRAE online request timeout")
    except HTTPError as exc:
        return _failure(f"ASHRAE online HTTP error: {exc.code}")
    except URLError as exc:
        return _failure(f"Online ASHRAE provider unavailable: {exc.reason}")
    except ValueError:
        return _failure("Invalid ASHRAE response format")
    except Exception as exc:
        return _failure(f"Online ASHRAE provider unavailable: {exc.__class__.__name__}: {exc}")
    rows = _extract_station_rows(payload)
    if not rows:
        return _failure("Invalid ASHRAE response format")
    return _lookup_from_rows(latitude, longitude, rows)


def lookup_online_ashrae_design_condition(latitude, longitude, endpoint=None, timeout=10):
    """Backward-compatible wrapper for the Phase 18E provider interface."""
    return query_ashrae_online(latitude, longitude, timeout_seconds=timeout, endpoint=endpoint)
