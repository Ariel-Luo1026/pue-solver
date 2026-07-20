"""Configuration Library validation summary layer.

Phase 6 validation skeleton. It consumes scanner manifests and produces
human-readable completeness summaries without invoking solver.py.
"""

from configuration_library_scanner import parse_equipment_folder_name, scan_configuration_library
from equipment_metadata import validate_equipment_metadata
from equipment_registry import equipment_ids_equivalent
from equipment_role_resolver import EquipmentRoleResolutionError, resolve_equipment_role_id
from topology_registry import get_topology


TENTATIVE_FOLDER_PREFIX_MAPPINGS = {
    # These are engineering canonical names. Legacy aliases remain compatible,
    # but they are not exact engineering definitions:
    # auxiliary_load -> rtc, terminal_fan -> mau, heat_exchanger -> engine_radiator.
    "ENGINE_RADIATOR": "engine_radiator",
    "MAU": "mau",
    "RTC": "rtc",
}


def validate_configuration_manifest(manifest):
    """Return a validation summary for a scanner manifest."""
    topology_equipment_ids = list(manifest.get("topology_equipment_ids") or [])
    detected_equipment_ids = list(manifest.get("detected_equipment_ids", []))
    present_equipment_ids = [
        expected_id
        for expected_id in topology_equipment_ids
        if any(equipment_ids_equivalent(expected_id, detected_id) for detected_id in detected_equipment_ids)
    ]
    missing_equipment_ids = [
        expected_id
        for expected_id in topology_equipment_ids
        if not any(equipment_ids_equivalent(expected_id, detected_id) for detected_id in detected_equipment_ids)
    ] or list(manifest.get("missing_expected_equipment_ids") or [])
    unexpected_equipment_folders = list(manifest.get("unexpected_equipment_folders") or [])
    tentative_equipment_mappings = _detect_tentative_equipment_mappings(
        manifest.get("equipment_folders", []),
        manifest.get("detected_equipment_instances", []),
    )
    validation_messages = list(manifest.get("validation_messages") or [])

    validation_status = _validation_status(
        manifest,
        missing_equipment_ids,
        unexpected_equipment_folders,
        tentative_equipment_mappings,
    )
    completeness_score = _completeness_score(present_equipment_ids, topology_equipment_ids)

    return {
        "configuration_name": manifest.get("configuration_name"),
        "topology_id": manifest.get("topology_id"),
        "topology_display_name": manifest.get("topology_display_name"),
        "detected_cooling_system_type": manifest.get("detected_cooling_system_type"),
        "detected_power_source": manifest.get("detected_power_source"),
        "detected_unit_capacity": manifest.get("detected_unit_capacity"),
        "validation_status": validation_status,
        "completeness_score": completeness_score,
        "present_equipment_ids": present_equipment_ids,
        "missing_equipment_ids": missing_equipment_ids,
        "unexpected_equipment_folders": unexpected_equipment_folders,
        "tentative_equipment_mappings": tentative_equipment_mappings,
        "validation_messages": validation_messages,
        "recommended_next_actions": _recommended_next_actions(
            manifest,
            missing_equipment_ids,
            unexpected_equipment_folders,
            tentative_equipment_mappings,
        ),
    }


def validate_configuration_library(configuration):
    """Validate a loaded Configuration Library input or scan a filesystem root."""
    if isinstance(configuration, dict):
        return validate_loaded_configuration_library(configuration)
    return [
        validate_configuration_manifest(manifest)
        for manifest in scan_configuration_library(configuration)
    ]


def validate_loaded_configuration_library(configuration):
    """Return a runtime validation summary for a loaded Configuration Library input."""
    manifest = configuration.get("configuration_manifest") or {}
    configuration_id = (
        manifest.get("configuration_id")
        or configuration.get("configuration_id")
        or configuration.get("configuration_name")
        or ""
    )
    topology_id = manifest.get("solver_topology") or configuration.get("topology_id") or ""
    missing_roles = []
    missing_curves = []
    warnings = []
    equipment_validation = []

    for field in ("configuration_id", "cooling_system_type", "solver_topology"):
        if not manifest.get(field):
            warnings.append(f"Manifest missing required field: {field}")

    topology = get_topology(topology_id)
    if topology is None:
        warnings.append(f"Unknown solver_topology: {topology_id or '<missing>'}")

    selected_curves = configuration.get("selected_curves") or {}
    equipment_bindings = _flatten_equipment_bindings(configuration.get("equipment") or {})
    equipment_packages = _flatten_equipment_packages(configuration)
    for role_name in manifest.get("required_roles") or []:
        try:
            resolved_ids = resolve_equipment_role_id(manifest, role_name, selected_curves)
        except EquipmentRoleResolutionError as exc:
            missing_roles.append(role_name)
            warnings.append(str(exc))
            continue
        for equipment_id in _as_list(resolved_ids):
            binding = equipment_bindings.get(equipment_id) or {}
            if binding.get("enabled") is False or binding.get("selected_curve_status") == "Missing Solver_Curve":
                missing_curves.append(f"{role_name}={equipment_id}")
                continue
            selected = selected_curves.get(equipment_id) or {}
            package = equipment_packages.get(equipment_id) or {}
            validation = _validate_equipment_metadata_binding(equipment_id, role_name, binding, selected, package)
            equipment_validation.append(validation)
            if validation["status"] == "error":
                warnings.extend([f"{equipment_id}: {issue}" for issue in validation["issues"]])
            if not _has_usable_curve(selected, binding):
                missing_curves.append(f"{role_name}={equipment_id}")

    status = "valid"
    if warnings or missing_roles or missing_curves:
        status = "error"
    return {
        "status": status,
        "configuration_id": configuration_id,
        "topology": topology_id,
        "missing_roles": missing_roles,
        "missing_curves": missing_curves,
        "warnings": warnings,
        "equipment_validation": equipment_validation,
    }


def _as_list(value):
    return value if isinstance(value, list) else [value]


def _has_usable_curve(selected, binding):
    if selected:
        if selected.get("electrical_path"):
            return True
        if selected.get("status") == "Electrical Path Found":
            return True
        return selected.get("status") == "Selected" and bool(selected.get("sheet_name"))
    if selected.get("electrical_path") or binding.get("electrical_path"):
        return True
    if selected.get("status") == "Electrical Path Found" or binding.get("selected_curve_status") == "Electrical Path Found":
        return True
    if selected.get("status") == "Selected" and selected.get("sheet_name"):
        return True
    if binding.get("selected_curve_status") == "Selected" and binding.get("selected_curve_sheet"):
        return True
    return False


def _flatten_equipment_bindings(equipment):
    flattened = {}
    cooling = equipment.get("cooling") if isinstance(equipment.get("cooling"), dict) else {}
    for value in cooling.values():
        if isinstance(value, dict) and "equipment_id" in value:
            flattened[value["equipment_id"]] = value
        elif isinstance(value, dict):
            for item in value.values():
                if isinstance(item, dict) and "equipment_id" in item:
                    flattened[item["equipment_id"]] = item
    auxiliary = equipment.get("auxiliary") if isinstance(equipment.get("auxiliary"), dict) else {}
    for key, value in auxiliary.items():
        if isinstance(value, dict):
            flattened[value.get("equipment_id") or key] = value
    return flattened


def _flatten_equipment_packages(configuration):
    packages = {}
    library_bound_input = (
        configuration.get("configuration_library", {})
        .get("library_bound_input", {})
    )
    for key, value in (library_bound_input.get("equipment_packages") or {}).items():
        if isinstance(value, dict):
            packages[value.get("equipment_id") or key] = value
            if value.get("actual_equipment_id"):
                packages[value["actual_equipment_id"]] = value
    return packages


def _validate_equipment_metadata_binding(equipment_id, role_name, binding, selected, package):
    metadata = (
        binding.get("equipment_metadata")
        or package.get("equipment_metadata")
        or selected.get("equipment_metadata")
    )
    validation = validate_equipment_metadata(metadata)
    issues = list(validation.get("issues") or [])
    detected_curve_type = _detect_standard_curve_type(selected, binding)
    declared_curve_type = validation.get("curve_type") or (metadata or {}).get("curve_type")
    if declared_curve_type and detected_curve_type and declared_curve_type != detected_curve_type:
        issues.append(
            f"Curve type mismatch: expected {declared_curve_type}; found {detected_curve_type}"
        )
    return {
        "status": "error" if issues else "valid",
        "equipment_id": equipment_id,
        "role": role_name,
        "equipment_type": validation.get("equipment_type") or "",
        "curve_type": declared_curve_type or "",
        "curve_schema": validation.get("curve_schema") or "",
        "detected_curve_type": detected_curve_type or "",
        "issues": issues,
    }


def _detect_standard_curve_type(selected, binding):
    if selected.get("electrical_path") or binding.get("electrical_path"):
        return "electrical_path_efficiency"
    rows = selected.get("curve") if isinstance(selected.get("curve"), list) else binding.get("curve_data")
    columns = set()
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict):
            columns.update(row.keys())
    if {"ambient_C", "load_ratio", "power_input_kW"}.issubset(columns):
        return "ambient_capacity_power"
    if {"ambient_C", "capacity_kW", "power_kW"}.issubset(columns):
        return "ambient_capacity_power"
    if {"CEFT_C", "load_ratio", "COP_kW_per_kW"}.issubset(columns):
        return "cop_curve"
    if {"Outdoor_Dry_Bulb_C", "Heat_Rejection_Capacity_kW", "Estimated_Fan_Power_kW"}.issubset(columns):
        return "ambient_capacity_power"
    if {"load_ratio", "engine_output_kW"}.issubset(columns):
        return "load_ratio_engine_output"
    if {"load_ratio", "power_kW"}.issubset(columns):
        return "load_ratio_power"
    if {"load_ratio", "radiator_fan_power_kW"}.issubset(columns):
        return "load_ratio_power"
    if {"load_ratio", "efficiency"}.issubset(columns):
        return "electrical_efficiency"
    if {"load_ratio", "loss_fraction"}.issubset(columns):
        return "electrical_loss_fraction"
    if {"load_ratio", "loss_kW"}.issubset(columns):
        return "electrical_loss_power"
    return ""


def _validation_status(
    manifest,
    missing_equipment_ids,
    unexpected_equipment_folders,
    tentative_equipment_mappings,
):
    if (
        not manifest.get("topology_id")
        or not manifest.get("configuration_file_exists")
        or not manifest.get("scenario_file_exists")
        or not manifest.get("equipment_folder_exists")
    ):
        return "invalid"
    if (
        missing_equipment_ids
        or tentative_equipment_mappings
        or unexpected_equipment_folders
        or not manifest.get("input_folder_exists")
    ):
        return "warning"
    return "valid"


def _completeness_score(present_equipment_ids, topology_equipment_ids):
    if not topology_equipment_ids:
        return 0
    return len(set(present_equipment_ids)) / len(set(topology_equipment_ids))


def _detect_tentative_equipment_mappings(equipment_folders, detected_equipment_instances=None):
    mappings = []
    parsed_instances = detected_equipment_instances or [
        parse_equipment_folder_name(folder_name)
        for folder_name in equipment_folders
    ]
    for parsed in parsed_instances:
        folder_name = parsed.get("folder_name") or parsed.get("original_name")
        prefix = parsed.get("equipment_type_token")
        equipment_id = TENTATIVE_FOLDER_PREFIX_MAPPINGS.get(prefix)
        if not equipment_id:
            continue
        mappings.append({
            "equipment_folder": folder_name,
            "equipment_id": equipment_id,
            "message": f"{folder_name} → {equipment_id} is tentative.",
        })
    return mappings


def _recommended_next_actions(
    manifest,
    missing_equipment_ids,
    unexpected_equipment_folders,
    tentative_equipment_mappings,
):
    actions = []
    if not manifest.get("configuration_file_exists"):
        actions.append("Add configuration.xlsx")
    if not manifest.get("scenario_file_exists"):
        actions.append("Add scenario.xlsx")
    if not manifest.get("equipment_folder_exists"):
        actions.append("Add equipment folder")
    if not manifest.get("input_folder_exists"):
        actions.append("Add input folder")
    if not manifest.get("topology_id"):
        actions.append("Rename configuration folder to include a supported topology prefix")
    for equipment_id in missing_equipment_ids:
        actions.append(f"Add missing equipment folder: {equipment_id}")
    for mapping in tentative_equipment_mappings:
        actions.append(
            f"Review tentative mapping: {mapping['equipment_folder']} → {mapping['equipment_id']}"
        )
    for folder_name in unexpected_equipment_folders:
        actions.append(f"Confirm equipment folder meaning: {folder_name}")
    return actions
