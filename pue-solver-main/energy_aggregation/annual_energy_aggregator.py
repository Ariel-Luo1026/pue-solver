"""Topology-independent annual energy aggregation.

This module derives annual energy from hourly output and standardized
PerformanceResult payloads. It does not call solver.py or equipment formulas.
"""

from energy_aggregation.energy_result import AnnualEnergyResult


class AnnualEnergyAggregationError(ValueError):
    """Raised when annual aggregation cannot be performed."""


COOLING_COMPONENTS = {
    "ACC",
    "CHILLER",
    "DRY_COOLER",
    "COOLING_TOWER",
    "CHW_PUMP",
    "CW_PUMP",
    "PUMP",
}

KNOWN_COMPONENTS = COOLING_COMPONENTS | {
    "INDOOR_EQUIPMENT",
    "ELECTRICAL_LOSS",
    "AUXILIARY",
}


PERFORMANCE_RESULT_COMPONENT_KEYS = {
    "chiller_performance_result": "CHILLER",
    "dry_cooler_performance_result": "DRY_COOLER",
    "acc_performance_result": "ACC",
}

PERFORMANCE_RESULT_ACTIVE_UNIT_FIELDS = {
    "chiller_performance_result": "active_chiller_units",
    "dry_cooler_performance_result": "active_dry_cooler_units",
    "acc_performance_result": "active_acc_units",
}


LEGACY_COMPONENT_FIELDS = (
    ("ACC", ("acc_power_kW", "acc_power_input_kW")),
    ("CHILLER", ("chiller_power_kW",)),
    ("DRY_COOLER", ("dry_cooler_power_kW", "dry_cooler_fan_power_kW")),
    ("CHW_PUMP", ("pump_power_kW", "pumps_kw")),
    ("INDOOR_EQUIPMENT", ("white_space_equipment_power_kW",)),
    ("ELECTRICAL_LOSS", ("electrical_loss_kW",)),
    ("AUXILIARY", ("auxiliary_power_kW",)),
)


def aggregate_annual_energy(solver_result=None, hourly_results=None, timestep_hours=1.0):
    """Aggregate annual energy from standardized or legacy hourly rows."""
    result = solver_result if isinstance(solver_result, dict) else {}
    hourly = hourly_results
    if hourly is None:
        hourly = result.get("hourly_results")
    if not isinstance(hourly, list) or not hourly:
        raise AnnualEnergyAggregationError("Annual energy aggregation failed: hourly_results is empty.")

    timestep = _to_float(timestep_hours, "timestep_hours")
    if timestep <= 0:
        raise AnnualEnergyAggregationError("Annual energy aggregation failed: timestep_hours must be greater than 0.")

    components = {}
    warnings = []
    it_energy = 0.0
    facility_energy = 0.0
    has_facility_power = False
    found_performance_or_legacy = False

    for row in hourly:
        if not isinstance(row, dict):
            warnings.append("Skipped non-dictionary hourly row.")
            continue
        it_kw = _first_number(row.get("it_load_kW"), row.get("IT_load_kW"))
        if it_kw is not None:
            it_energy += it_kw * timestep
        facility_kw = _first_number(
            row.get("facility_power_kW"),
            row.get("total_facility_power_kW"),
            row.get("facility_load_kW"),
        )
        if facility_kw is not None:
            has_facility_power = True
            facility_energy += facility_kw * timestep

        used_fields = set()
        for result_key, fallback_type in PERFORMANCE_RESULT_COMPONENT_KEYS.items():
            performance_result = row.get(result_key)
            if not isinstance(performance_result, dict):
                continue
            equipment_type = _equipment_type(performance_result, fallback_type)
            power_kw = _performance_power(performance_result)
            if power_kw is None:
                warnings.append(f"{equipment_type} performance result missing performance.power_kW.")
                continue
            active_units = _first_number(row.get(PERFORMANCE_RESULT_ACTIVE_UNIT_FIELDS.get(result_key)), 1.0)
            _add_component(components, equipment_type, power_kw * active_units * timestep, source="PerformanceResult")
            found_performance_or_legacy = True
            _mark_legacy_fields_used(used_fields, equipment_type)

        for equipment_type, field_names in LEGACY_COMPONENT_FIELDS:
            power_kw = _first_unused_number(row, field_names, used_fields)
            if power_kw is None:
                continue
            _add_component(components, equipment_type, power_kw * timestep, source="legacy_hourly_field")
            found_performance_or_legacy = True

        for key, value in row.items():
            if not str(key).endswith("_performance_result"):
                continue
            if key in PERFORMANCE_RESULT_COMPONENT_KEYS:
                continue
            if not isinstance(value, dict):
                continue
            equipment_type = _equipment_type(value, "UNKNOWN")
            power_kw = _performance_power(value)
            if power_kw is None:
                warnings.append(f"{equipment_type} performance result missing performance.power_kW.")
                continue
            _add_component(components, equipment_type, power_kw * timestep, source="PerformanceResult")
            found_performance_or_legacy = True
            if equipment_type not in KNOWN_COMPONENTS:
                warnings.append(f"Unknown equipment type in {key}: {equipment_type}.")

    if not found_performance_or_legacy:
        raise AnnualEnergyAggregationError(
            "Annual energy aggregation failed: no PerformanceResult or supported legacy power fields found."
        )
    if it_energy <= 0:
        raise AnnualEnergyAggregationError("Annual energy aggregation failed: annual IT energy is zero.")

    cooling_energy = sum(
        component["energy_kWh"]
        for name, component in components.items()
        if name in COOLING_COMPONENTS
    )
    if not has_facility_power:
        facility_energy = (
            it_energy
            + cooling_energy
            + _component_energy(components, "INDOOR_EQUIPMENT")
            + _component_energy(components, "ELECTRICAL_LOSS")
            + _component_energy(components, "AUXILIARY")
        )
    pue = facility_energy / it_energy if it_energy else None
    return AnnualEnergyResult(
        annual_it_energy_kWh=it_energy,
        annual_facility_energy_kWh=facility_energy,
        annual_cooling_energy_kWh=cooling_energy,
        components=components,
        PUE=pue,
        warnings=_dedupe(warnings),
    ).to_dict()


def _add_component(components, equipment_type, energy_kwh, source):
    key = str(equipment_type or "UNKNOWN").strip().upper() or "UNKNOWN"
    component = components.setdefault(key, {"energy_kWh": 0.0, "sources": []})
    component["energy_kWh"] += float(energy_kwh)
    if source not in component["sources"]:
        component["sources"].append(source)


def _equipment_type(performance_result, fallback):
    return str(performance_result.get("equipment_type") or fallback or "UNKNOWN").strip().upper()


def _performance_power(performance_result):
    performance = performance_result.get("performance") if isinstance(performance_result, dict) else None
    if not isinstance(performance, dict):
        return None
    return _first_number(performance.get("power_kW"))


def _mark_legacy_fields_used(used_fields, equipment_type):
    for name, fields in LEGACY_COMPONENT_FIELDS:
        if name == equipment_type:
            used_fields.update(fields)


def _first_unused_number(row, field_names, used_fields):
    for field_name in field_names:
        if field_name in used_fields:
            continue
        value = _first_number(row.get(field_name))
        if value is not None:
            used_fields.add(field_name)
            return value
    return None


def _component_energy(components, key):
    component = components.get(key)
    return float(component.get("energy_kWh", 0.0)) if isinstance(component, dict) else 0.0


def _first_number(*values):
    for value in values:
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _to_float(value, label):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise AnnualEnergyAggregationError(f"Invalid numeric value for {label}: {value!r}") from None


def _dedupe(values):
    seen = set()
    result = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
