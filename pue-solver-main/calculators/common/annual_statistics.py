"""Annual statistics helpers for future calculators."""


def _numbers(values):
    return [float(value) for value in values or [] if value is not None]


def calculate_average(values):
    numbers = _numbers(values)
    return sum(numbers) / len(numbers) if numbers else None


def calculate_peak(values):
    numbers = _numbers(values)
    return max(numbers) if numbers else None


def calculate_minimum(values):
    numbers = _numbers(values)
    return min(numbers) if numbers else None


def calculate_total_energy(power_values, timestep_hours=1.0):
    return sum(_numbers(power_values)) * float(timestep_hours)


def calculate_load_factor(power_values):
    average = calculate_average(power_values)
    peak = calculate_peak(power_values)
    if average is None or peak in (None, 0):
        return None
    return average / peak
