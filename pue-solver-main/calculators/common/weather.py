"""Weather input helpers for future calculators.

Phase 11 utilities only; existing solver.py weather handling is unchanged.
"""


def normalize_weather_input(weather_input):
    """Return a normalized weather dictionary shape."""
    if not isinstance(weather_input, dict):
        return {"hourly_data": {}}
    if isinstance(weather_input.get("hourly_data"), dict):
        return weather_input
    return {"hourly_data": dict(weather_input)}


def extract_outdoor_temperature(weather_input):
    """Return outdoor dry-bulb temperature series when available."""
    weather = normalize_weather_input(weather_input)
    hourly = weather.get("hourly_data", {})
    return list(hourly.get("dry_bulb_C") or hourly.get("outdoor_dry_bulb_C") or [])


def extract_wet_bulb_temperature(weather_input):
    """Return outdoor wet-bulb temperature series when available."""
    weather = normalize_weather_input(weather_input)
    hourly = weather.get("hourly_data", {})
    return list(hourly.get("wet_bulb_C") or hourly.get("outdoor_wet_bulb_C") or [])


def extract_hour_of_year(weather_input):
    """Return hour-of-year index series when available."""
    weather = normalize_weather_input(weather_input)
    hourly = weather.get("hourly_data", {})
    hours = hourly.get("hour_index") or hourly.get("hour_of_year")
    if hours is not None:
        return list(hours)
    dry_bulb = extract_outdoor_temperature(weather)
    return list(range(1, len(dry_bulb) + 1))
