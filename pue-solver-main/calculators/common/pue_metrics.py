"""PUE metric helpers for future calculators."""


def calculate_pue(facility_power, it_power):
    it = float(it_power or 0.0)
    if it == 0:
        return None
    return float(facility_power or 0.0) / it


def calculate_partial_pue(component_power, it_power):
    return calculate_pue(component_power, it_power)


def calculate_cooling_contribution(cooling_power, facility_power):
    facility = float(facility_power or 0.0)
    if facility == 0:
        return None
    return float(cooling_power or 0.0) / facility


def calculate_power_breakdown(**components):
    total = sum(float(value or 0.0) for value in components.values())
    return {
        "components": {key: float(value or 0.0) for key, value in components.items()},
        "total": total,
    }
