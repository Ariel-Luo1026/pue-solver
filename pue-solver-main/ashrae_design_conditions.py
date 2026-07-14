"""Peak design weather condition provider.

This module intentionally uses a small local placeholder dataset. A future
provider can replace the data source without changing solver.py's interface.
"""

from json import load
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

DATA_PATH = Path(__file__).resolve().with_name("ashrae_design_conditions_data.json")

_FALLBACK_STATIONS = [
    {
        "station_name": "WINSTON FIELD, TX, USA",
        "station_id": "ASHRAE_PLACEHOLDER_WINSTON_FIELD_TX",
        "latitude": 32.693,
        "longitude": -100.951,
        "db_max_20yr_C": 44.0,
        "db_min_20yr_C": -16.9,
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


def _distance_km(latitude, longitude, station):
    station_lat = _num(station.get("latitude"))
    station_lon = _num(station.get("longitude"))
    if latitude is None or longitude is None or station_lat is None or station_lon is None:
        return 0.0
    lat1 = radians(latitude)
    lat2 = radians(station_lat)
    dlat = radians(station_lat - latitude)
    dlon = radians(station_lon - longitude)
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(a))


def get_peak_design_condition(latitude, longitude, source="ashrae_auto"):
    """Return nearest ASHRAE 20-year extreme design condition metadata."""
    latitude = _num(latitude)
    longitude = _num(longitude)
    stations = load_design_condition_stations()
    station = min(stations, key=lambda row: _distance_km(latitude, longitude, row))
    return {
        "source": "ASHRAE_20_year_extreme",
        "station_name": station.get("station_name") or "Unknown ASHRAE design station",
        "station_id": station.get("station_id") or "",
        "extreme_db_max_C": _num(station.get("db_max_20yr_C"), 44.0),
        "extreme_db_min_C": _num(station.get("db_min_20yr_C"), None),
    }
