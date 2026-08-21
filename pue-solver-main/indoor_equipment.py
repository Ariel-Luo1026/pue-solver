"""Shared indoor-equipment power evaluation for Configuration Library runtimes."""


INDOOR_EQUIPMENT_ROLES = ("cdu", "rtc", "mau")


def project_it_load_ratio(hourly_it_load_kw, design_it_load_kw):
    """Return the canonical clamped project IT load ratio."""
    design = float(design_it_load_kw or 0.0)
    if design <= 0:
        return 0.0
    return min(1.0, max(0.0, float(hourly_it_load_kw or 0.0) / design))


def evaluate_indoor_equipment(bindings, load_ratio, indoor_active_units, lookup_power_per_unit):
    """Evaluate configured/enabled CDU, RTC and MAU bindings exactly once."""
    bindings = bindings if isinstance(bindings, dict) else {}
    units = max(0, int(indoor_active_units or 0))
    powers = {role: 0.0 for role in INDOOR_EQUIPMENT_ROLES}
    sources = {role: "not_configured" for role in INDOOR_EQUIPMENT_ROLES}
    equipment_ids = {}

    for role in INDOOR_EQUIPMENT_ROLES:
        binding = bindings.get(role)
        if not isinstance(binding, dict) or binding.get("enabled") is False:
            if isinstance(binding, dict):
                sources[role] = "configured_disabled"
            continue
        equipment_id = binding.get("equipment_id") or role.upper()
        per_unit_power_kw = lookup_power_per_unit(role, equipment_id, binding, load_ratio)
        powers[role] = max(0.0, float(per_unit_power_kw or 0.0)) * units
        sources[role] = "configuration_library_solver_curve"
        equipment_ids[role] = equipment_id

    white_space_power_kw = sum(powers.values())
    return {
        "cdu_power_kW": powers["cdu"],
        "rtc_power_kW": powers["rtc"],
        "mau_power_kW": powers["mau"],
        "white_space_equipment_power_kW": white_space_power_kw,
        "indoor_active_units": units,
        "indoor_equipment_load_ratio": float(load_ratio),
        "indoor_equipment_load_ratio_basis": "it_project_load_ratio",
        "indoor_equipment_unit_count_basis": "normal_indoor_active_units",
        "indoor_equipment_curve_sources": sources,
        "indoor_equipment_ids": equipment_ids,
    }
