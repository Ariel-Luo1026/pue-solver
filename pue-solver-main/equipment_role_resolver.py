"""Manifest role-based equipment binding for Configuration Library inputs."""

from configuration_library_scanner import parse_equipment_folder_name
from equipment_registry import canonicalize_equipment_id


class EquipmentRoleResolutionError(ValueError):
    """Raised when a manifest role cannot be resolved to loaded equipment."""


def resolve_equipment_role(manifest, role_name, loaded_equipment):
    """Return loaded equipment data for a manifest role.

    Role values may be a single equipment ID or a list of equipment IDs. Missing
    optional roles return None and emit a diagnostic; missing required roles fail
    loudly so configuration issues do not fall back to hard-coded equipment IDs.
    """
    resolved_id = resolve_equipment_role_id(manifest, role_name, loaded_equipment)
    if resolved_id is None:
        return None
    if isinstance(resolved_id, list):
        return [loaded_equipment[equipment_id] for equipment_id in resolved_id]
    return loaded_equipment[resolved_id]


def resolve_equipment_role_id(manifest, role_name, loaded_equipment):
    """Return the loaded equipment key for a manifest role."""
    role_value = _declared_role_value(manifest, role_name)
    if role_value is None:
        return None
    if isinstance(role_value, list):
        resolved = [
            _resolve_declared_equipment_id(manifest, role_name, equipment_id, loaded_equipment)
            for equipment_id in role_value
        ]
        return resolved
    return _resolve_declared_equipment_id(manifest, role_name, role_value, loaded_equipment)


def validate_required_equipment_roles(manifest, loaded_equipment):
    """Validate all required manifest roles against loaded equipment packages."""
    for role_name in manifest.get("required_roles", []):
        resolve_equipment_role(manifest, role_name, loaded_equipment)
    return True


def _declared_role_value(manifest, role_name):
    configuration_id = (manifest or {}).get("configuration_id", "<unknown>")
    roles = (manifest or {}).get("equipment_roles") or {}
    required_roles = set((manifest or {}).get("required_roles") or [])
    optional_roles = set((manifest or {}).get("optional_roles") or [])
    if role_name not in roles or roles.get(role_name) in (None, "", []):
        if role_name in optional_roles and role_name not in required_roles:
            print(
                f"Configuration '{configuration_id}' optional equipment role '{role_name}' is not configured."
            )
            return None
        raise EquipmentRoleResolutionError(
            f"Configuration '{configuration_id}' is missing required equipment role '{role_name}'."
        )
    return roles[role_name]


def _resolve_declared_equipment_id(manifest, role_name, declared_equipment_id, loaded_equipment):
    configuration_id = (manifest or {}).get("configuration_id", "<unknown>")
    if not isinstance(loaded_equipment, dict):
        raise EquipmentRoleResolutionError(
            f"Configuration '{configuration_id}' cannot resolve role '{role_name}': loaded_equipment must be a dictionary."
        )
    declared_equipment_id = str(declared_equipment_id)
    if declared_equipment_id in loaded_equipment:
        return declared_equipment_id

    declared_canonical = _canonical_equipment_family(declared_equipment_id)
    matches = [
        equipment_id
        for equipment_id in sorted(loaded_equipment)
        if _canonical_equipment_family(equipment_id) == declared_canonical
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise EquipmentRoleResolutionError(
            f"Configuration '{configuration_id}' role '{role_name}'={declared_equipment_id} is ambiguous; "
            f"matching loaded equipment: {', '.join(matches)}."
        )
    raise EquipmentRoleResolutionError(
        f"Configuration '{configuration_id}' role '{role_name}' references missing equipment '{declared_equipment_id}'."
    )


def _canonical_equipment_family(equipment_id):
    parsed = parse_equipment_folder_name(equipment_id)
    return canonicalize_equipment_id(parsed.get("canonical_equipment_id") or equipment_id)
