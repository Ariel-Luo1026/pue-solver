"""Engineering energy-balance helpers for future calculators."""


def calculate_heat_load(it_load_kw, supplemental_load_kw=0.0):
    return float(it_load_kw or 0.0) + float(supplemental_load_kw or 0.0)


def calculate_heat_rejection(cooling_load_kw, equipment_heat_kw=0.0):
    return float(cooling_load_kw or 0.0) + float(equipment_heat_kw or 0.0)


def calculate_energy_balance(inputs_kw=None, outputs_kw=None):
    inputs = sum(float(value or 0.0) for value in (inputs_kw or []))
    outputs = sum(float(value or 0.0) for value in (outputs_kw or []))
    return {
        "inputs_kw": inputs,
        "outputs_kw": outputs,
        "imbalance_kw": inputs - outputs,
    }
