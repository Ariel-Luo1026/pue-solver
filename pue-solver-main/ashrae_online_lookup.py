"""Online ASHRAE design-condition lookup adapter.

The public solver calls this module through ``ashrae_design_conditions`` so
provider wiring stays out of solver.py.  By default the adapter follows the
public ASHRAE Meteo workflow:

``request_places.php`` finds the nearest station, then
``request_meteo_parametres.php`` returns that station's climatic design data.

Set ``ASHRAE_DESIGN_CONDITIONS_URL`` to an ASHRAE-compatible JSON endpoint only
when overriding the built-in ASHRAE Meteo workflow.
"""

from json import loads
from math import asin, cos, isfinite, radians, sin, sqrt
from os import environ
from socket import timeout as SocketTimeout
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

ASHRAE_METEO_BASE_URL = "https://ashrae-meteo.info/v3.0/"
ASHRAE_METEO_PLACES_ENDPOINT = ASHRAE_METEO_BASE_URL + "request_places.php"
ASHRAE_METEO_PARAMETERS_ENDPOINT = ASHRAE_METEO_BASE_URL + "request_meteo_parametres.php"


def normalize_ashrae_url(url, default=ASHRAE_METEO_PLACES_ENDPOINT):
    """Return a valid HTTP(S) ASHRAE URL, defaulting to the official endpoint."""
    value = "" if url is None else str(url).strip()
    if not value:
        return default
    if value.startswith(("https://", "http://")):
        return value
    if value.startswith("//"):
        return "https:" + value
    value = value.lstrip("/")
    if value.startswith("v3.0/"):
        return "https://ashrae-meteo.info/" + value
    if value in {"request_places.php", "request_meteo_parametres.php"}:
        return ASHRAE_METEO_BASE_URL + value
    return "https://" + value


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


def _failure(reason, lookup_method=None, endpoint=None):
    result = {
        "lookup_status": "failed",
        "failure_reason": reason,
        "lookup_provider": "ASHRAE_online",
        "source": "ASHRAE_online",
    }
    if lookup_method:
        result["lookup_method"] = lookup_method
    if endpoint:
        result["lookup_endpoint"] = endpoint
    return result


def _payload_structure(payload):
    if isinstance(payload, dict):
        structure = {
            "type": "dict",
            "keys": sorted(str(key) for key in payload.keys()),
        }
        stations = payload.get("meteo_stations")
        if isinstance(stations, list):
            structure["meteo_stations_count"] = len(stations)
            if stations and isinstance(stations[0], dict):
                structure["first_meteo_station_keys"] = sorted(str(key) for key in stations[0].keys())
        return structure
    if isinstance(payload, list):
        structure = {
            "type": "list",
            "length": len(payload),
        }
        if payload and isinstance(payload[0], dict):
            structure["first_item_keys"] = sorted(str(key) for key in payload[0].keys())
        return structure
    return {"type": type(payload).__name__}


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
                "n-year_return_period_values_of_extreme_DB_20_max",
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
    station_name = _first_present(row, ("station_name", "name", "station", "place"))
    station_id = _first_present(row, ("station_id", "wmo", "wmo_id", "id"))
    station_latitude = _num(_first_present(row, ("station_latitude", "latitude", "lat")))
    station_longitude = _num(_first_present(row, ("station_longitude", "longitude", "lon", "lng", "long")))
    extreme_db_max = _design_db_value(row)
    if not station_name or not station_id or station_latitude is None or station_longitude is None or extreme_db_max is None:
        return None
    distance = _num(_first_present(row, ("distance_km", "station_distance_km")))
    if distance is None:
        distance = _distance_km(latitude, longitude, station_latitude, station_longitude)
    if not isfinite(distance):
        return None
    lookup_method = _first_present(row, ("lookup_method", "method"))
    lookup_endpoint = _first_present(row, ("lookup_endpoint", "endpoint"))
    lookup_provider = _first_present(row, ("lookup_provider", "provider"))
    result = {
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
    if lookup_method:
        result["lookup_method"] = str(lookup_method)
    if lookup_endpoint:
        result["lookup_endpoint"] = str(lookup_endpoint)
    if lookup_provider:
        result["lookup_provider"] = str(lookup_provider)
    return result


def _station_failure_reason(row):
    if not isinstance(row, dict):
        return "Invalid ASHRAE response format"
    station_name = _first_present(row, ("station_name", "name", "station", "place"))
    station_id = _first_present(row, ("station_id", "wmo", "wmo_id", "id"))
    station_latitude = _num(_first_present(row, ("station_latitude", "latitude", "lat")))
    station_longitude = _num(_first_present(row, ("station_longitude", "longitude", "lon", "lng", "long")))
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


def _lookup_from_rows(latitude, longitude, rows, lookup_method=None, endpoint=None):
    candidates = []
    failure_reasons = []
    for row in rows:
        normalized = normalize_online_station(row, latitude, longitude)
        if normalized is None:
            failure_reasons.append(_station_failure_reason(row))
        else:
            if lookup_method:
                normalized["lookup_method"] = lookup_method
            if endpoint:
                normalized["lookup_endpoint"] = endpoint
            candidates.append(normalized)
    if not candidates:
        for reason in ("ASHRAE online response missing design temperature", "Invalid ASHRAE response format"):
            if reason in failure_reasons:
                return _failure(reason, lookup_method=lookup_method, endpoint=endpoint)
        return _failure("Invalid ASHRAE response format", lookup_method=lookup_method, endpoint=endpoint)
    return min(candidates, key=lambda row: row["distance_km"])


def _urlencoded_post(url, params, timeout):
    url = normalize_ashrae_url(url)
    body = urlencode(params).encode("utf-8")
    with urlopen(url, data=body, timeout=timeout) as response:
        return response.read().decode("utf-8-sig")


def _loads_json_text(body):
    return loads(str(body or "").lstrip("\ufeff").strip())


def _fetch_endpoint(latitude, longitude, endpoint, timeout):
    endpoint = normalize_ashrae_url(endpoint)
    separator = "&" if "?" in endpoint else "?"
    url = f"{endpoint}{separator}{urlencode({'latitude': latitude, 'longitude': longitude})}"
    with urlopen(url, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return loads(body)


def _fetch_ashrae_meteo_places(latitude, longitude, timeout, ashrae_version="2025", number=10):
    body = _urlencoded_post(
        ASHRAE_METEO_PLACES_ENDPOINT,
        {
            "lat": f"{float(latitude):.3f}",
            "long": f"{float(longitude):.3f}",
            "number": int(number),
            "ashrae_version": str(ashrae_version),
        },
        timeout,
    )
    return _loads_json_text(body)


def _fetch_ashrae_meteo_parameters(wmo, timeout, ashrae_version="2025"):
    body = _urlencoded_post(
        ASHRAE_METEO_PARAMETERS_ENDPOINT,
        {
            "wmo": str(wmo),
            "ashrae_version": str(ashrae_version),
            "si_ip": "SI",
        },
        timeout,
    )
    return _loads_json_text(body)


def _ashrae_version():
    return str(environ.get("ASHRAE_METEO_VERSION") or environ.get("ASHRAE_VERSION") or "2025")


def _meteo_stations(payload):
    if isinstance(payload, dict) and isinstance(payload.get("meteo_stations"), list):
        return [row for row in payload.get("meteo_stations") if isinstance(row, dict)]
    return []


def _nearest_meteo_station(latitude, longitude, places):
    candidates = []
    for row in _meteo_stations(places):
        station_name = row.get("place")
        station_id = row.get("wmo")
        station_latitude = _num(row.get("lat"))
        station_longitude = _num(row.get("long"))
        if not station_name or not station_id or station_latitude is None or station_longitude is None:
            continue
        distance = _num(row.get("tt"), None)
        if distance is None:
            distance = _distance_km(latitude, longitude, station_latitude, station_longitude)
        else:
            distance *= 6371.0
        if isfinite(distance):
            candidates.append(
                {
                    "station_name": str(station_name),
                    "station_id": str(station_id),
                    "station_latitude": station_latitude,
                    "station_longitude": station_longitude,
                    "distance_km": float(distance),
                }
            )
    if not candidates:
        return None
    return min(candidates, key=lambda row: row["distance_km"])


def _normalize_ashrae_meteo_station(station, latitude, longitude):
    if not isinstance(station, dict):
        return None
    return normalize_online_station(
        {
            "station_name": station.get("place"),
            "station_id": station.get("wmo"),
            "station_latitude": station.get("lat"),
            "station_longitude": station.get("long"),
            "distance_km": _num(station.get("tt"), 0.0) * 6371.0 if _num(station.get("tt"), None) is not None else None,
            "design_db_max_C": station.get("n-year_return_period_values_of_extreme_DB_20_max"),
            "extreme_db_min_C": station.get("n-year_return_period_values_of_extreme_DB_20_min"),
            "lookup_method": "ASHRAE_web",
            "lookup_endpoint": ASHRAE_METEO_PARAMETERS_ENDPOINT,
            "temperature_basis": "ASHRAE_20_year_extreme_annual_design_condition",
        },
        latitude,
        longitude,
    )


def _query_ashrae_meteo(latitude, longitude, timeout_seconds):
    version = _ashrae_version()
    places = _fetch_ashrae_meteo_places(latitude, longitude, timeout_seconds, ashrae_version=version)
    diagnostics = {"request_places": _payload_structure(places)}
    nearest = _nearest_meteo_station(latitude, longitude, places)
    if nearest is None:
        failure = _failure(
            "station data missing",
            lookup_method="ASHRAE_web",
            endpoint=ASHRAE_METEO_PLACES_ENDPOINT,
        )
        failure["ashrae_raw_diagnostics"] = diagnostics
        return failure
    parameters = _fetch_ashrae_meteo_parameters(nearest["station_id"], timeout_seconds, ashrae_version=version)
    diagnostics["request_meteo_parametres"] = _payload_structure(parameters)
    parameter_stations = _meteo_stations(parameters)
    if not parameter_stations:
        failure = _failure(
            "station data missing",
            lookup_method="ASHRAE_web",
            endpoint=ASHRAE_METEO_PARAMETERS_ENDPOINT,
        )
        failure["ashrae_raw_diagnostics"] = diagnostics
        return failure
    normalized = _normalize_ashrae_meteo_station(parameter_stations[0], latitude, longitude)
    if normalized is None:
        failure = _failure(
            _station_failure_reason(parameter_stations[0]),
            lookup_method="ASHRAE_web",
            endpoint=ASHRAE_METEO_PARAMETERS_ENDPOINT,
        )
        failure["ashrae_raw_diagnostics"] = diagnostics
        return failure
    normalized["distance_km"] = nearest["distance_km"]
    normalized["lookup_method"] = "ASHRAE_web"
    normalized["lookup_endpoint"] = ASHRAE_METEO_PARAMETERS_ENDPOINT
    normalized["ashrae_raw_diagnostics"] = diagnostics
    return normalized


def query_ashrae_online(latitude, longitude, timeout_seconds=10, endpoint=None):
    """Return nearest online ASHRAE design-condition station or failure status."""
    latitude = _num(latitude)
    longitude = _num(longitude)
    if latitude is None or longitude is None:
        return _failure("project coordinates missing")
    if str(environ.get("ASHRAE_ONLINE_LOOKUP_DISABLED", "")).strip().lower() in {"1", "true", "yes"}:
        return _failure("online lookup disabled", lookup_method="ASHRAE_web")
    endpoint = endpoint or environ.get("ASHRAE_DESIGN_CONDITIONS_URL")
    if endpoint:
        endpoint = normalize_ashrae_url(endpoint)
    lookup_method = "ASHRAE_proxy" if endpoint and "/api/ashrae_design_condition" in endpoint else ("ASHRAE_API" if endpoint else "ASHRAE_web")
    try:
        if endpoint:
            payload = _fetch_endpoint(latitude, longitude, endpoint, timeout_seconds)
            rows = _extract_station_rows(payload)
            if not rows:
                return _failure("Invalid ASHRAE response format", lookup_method=lookup_method, endpoint=endpoint)
            return _lookup_from_rows(latitude, longitude, rows, lookup_method=lookup_method, endpoint=endpoint)
        return _query_ashrae_meteo(latitude, longitude, timeout_seconds)
    except (SocketTimeout, TimeoutError):
        return _failure("ASHRAE online request timeout", lookup_method=lookup_method, endpoint=endpoint or ASHRAE_METEO_BASE_URL)
    except HTTPError as exc:
        return _failure(f"ASHRAE online HTTP error: {exc.code}", lookup_method=lookup_method, endpoint=endpoint or ASHRAE_METEO_BASE_URL)
    except URLError as exc:
        return _failure(f"Online ASHRAE provider unavailable: {exc.reason}", lookup_method=lookup_method, endpoint=endpoint or ASHRAE_METEO_BASE_URL)
    except ValueError:
        return _failure("Invalid ASHRAE response format", lookup_method=lookup_method, endpoint=endpoint or ASHRAE_METEO_BASE_URL)
    except Exception as exc:
        return _failure(
            f"Online ASHRAE provider unavailable: {exc.__class__.__name__}: {exc}",
            lookup_method=lookup_method,
            endpoint=endpoint or ASHRAE_METEO_BASE_URL,
        )


def lookup_online_ashrae_design_condition(latitude, longitude, endpoint=None, timeout=10):
    """Backward-compatible wrapper for the Phase 18E provider interface."""
    return query_ashrae_online(latitude, longitude, timeout_seconds=timeout, endpoint=endpoint)
