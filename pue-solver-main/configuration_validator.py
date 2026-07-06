"""Configuration Library validation summary layer.

Phase 6 validation skeleton. It consumes scanner manifests and produces
human-readable completeness summaries without invoking solver.py.
"""

from configuration_library_scanner import parse_equipment_folder_name, scan_configuration_library


TENTATIVE_FOLDER_PREFIX_MAPPINGS = {
    "ENGINE_RADIATOR": "heat_exchanger",
    "MAU": "terminal_fan",
    "RTC": "auxiliary_load",
}


def validate_configuration_manifest(manifest):
    """Return a validation summary for a scanner manifest."""
    topology_equipment_ids = list(manifest.get("topology_equipment_ids") or [])
    present_equipment_ids = [
        equipment_id
        for equipment_id in manifest.get("detected_equipment_ids", [])
        if equipment_id in topology_equipment_ids
    ]
    missing_equipment_ids = list(manifest.get("missing_expected_equipment_ids") or [])
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


def validate_configuration_library(root_path):
    """Scan and validate all configuration folders under a library root."""
    return [
        validate_configuration_manifest(manifest)
        for manifest in scan_configuration_library(root_path)
    ]


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

