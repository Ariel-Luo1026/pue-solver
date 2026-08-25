"""Configuration Library manifest parsing and topology validation."""

from copy import deepcopy
import json
from pathlib import Path

from topology_registry import get_topology


MANIFEST_FILENAME = "configuration_manifest.json"
VALID_IMPLEMENTATION_STATUSES = {
    "implemented",
    "framework_ready_data_missing",
    "placeholder",
    "disabled",
    "test_only",
}
REQUIRED_FIELDS = (
    "schema_version",
    "configuration_id",
    "display_name",
    "cooling_system_type",
    "implementation_status",
    "equipment_roles",
    "required_roles",
    "optional_roles",
    "solver_topology",
    "report_profile",
)


class ConfigurationManifestError(ValueError):
    """Raised when a Configuration Library manifest is missing or invalid."""


class UnsupportedConfigurationStatusError(ConfigurationManifestError):
    """Raised when a valid manifest is not executable."""


def manifest_path_for_configuration(configuration_dir):
    return Path(configuration_dir) / MANIFEST_FILENAME


def load_configuration_manifest(configuration_dir):
    """Read and validate a configuration manifest from a configuration folder."""
    manifest_path = manifest_path_for_configuration(configuration_dir)
    configuration_id = Path(configuration_dir).name
    if not manifest_path.is_file():
        raise ConfigurationManifestError(
            f"Configuration '{configuration_id}' is missing manifest: {manifest_path}"
        )
    try:
        with manifest_path.open(encoding="utf-8") as handle:
            raw = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ConfigurationManifestError(
            f"Configuration '{configuration_id}' has invalid JSON manifest at {manifest_path}: {exc}"
        ) from exc
    except OSError as exc:
        raise ConfigurationManifestError(
            f"Configuration '{configuration_id}' manifest could not be read at {manifest_path}: {exc}"
        ) from exc
    return validate_configuration_manifest(raw, manifest_path)


def validate_configuration_manifest(raw_manifest, manifest_path=None):
    """Return a normalized manifest dict or raise a clear validation error."""
    manifest_path = Path(manifest_path) if manifest_path else None
    if not isinstance(raw_manifest, dict):
        raise _error(None, manifest_path, "manifest must be a JSON object")
    configuration_id = raw_manifest.get("configuration_id")
    for field in REQUIRED_FIELDS:
        if field not in raw_manifest or raw_manifest.get(field) in (None, ""):
            raise _error(configuration_id, manifest_path, f"missing required field: {field}")

    manifest = deepcopy(raw_manifest)
    configuration_id = str(manifest["configuration_id"])
    manifest["configuration_id"] = configuration_id
    manifest["schema_version"] = str(manifest["schema_version"])
    manifest["display_name"] = str(manifest["display_name"])
    manifest["cooling_system_type"] = str(manifest["cooling_system_type"])
    manifest["implementation_status"] = str(manifest["implementation_status"])
    manifest["solver_topology"] = str(manifest["solver_topology"])
    manifest["report_profile"] = str(manifest["report_profile"])

    status = manifest["implementation_status"]
    if status not in VALID_IMPLEMENTATION_STATUSES:
        raise _error(configuration_id, manifest_path, f"invalid implementation_status: {status}")
    if not isinstance(manifest.get("equipment_roles"), dict):
        raise _error(configuration_id, manifest_path, "equipment_roles must be an object")
    if not isinstance(manifest.get("required_roles"), list):
        raise _error(configuration_id, manifest_path, "required_roles must be a list")
    if not isinstance(manifest.get("optional_roles"), list):
        raise _error(configuration_id, manifest_path, "optional_roles must be a list")

    manifest["equipment_roles"] = {
        str(role): _normalize_equipment_role_value(configuration_id, manifest_path, role, equipment_id)
        for role, equipment_id in manifest["equipment_roles"].items()
    }
    manifest["required_roles"] = [str(role) for role in manifest["required_roles"]]
    manifest["optional_roles"] = [str(role) for role in manifest["optional_roles"]]
    _validate_topology_compatibility(manifest, manifest_path)
    topology = get_topology(manifest["solver_topology"]) or {}
    required_inputs = manifest.get("required_inputs", topology.get("required_inputs", []))
    if required_inputs is None:
        required_inputs = []
    if not isinstance(required_inputs, list):
        raise _error(configuration_id, manifest_path, "required_inputs must be a list")
    manifest["required_inputs"] = [str(item) for item in required_inputs]

    for role in manifest["required_roles"]:
        equipment_id = manifest["equipment_roles"].get(role)
        if not equipment_id:
            raise _error(
                configuration_id,
                manifest_path,
                f"missing required equipment role: {role}",
            )

    power_source = manifest.get("power_source")
    normalized_power_source = "".join(character for character in str(power_source or "").lower() if character.isalnum())
    if normalized_power_source == "gasengine":
        for role in ("engine", "engine_radiator"):
            if not manifest["equipment_roles"].get(role) or role not in manifest["required_roles"]:
                raise _error(
                    configuration_id,
                    manifest_path,
                    f"Gas Engine configuration requires generation role: {role}",
                )
    if manifest_path:
        manifest["manifest_path"] = str(manifest_path)
    return manifest


def _normalize_equipment_role_value(configuration_id, manifest_path, role, equipment_id):
    if equipment_id is None:
        return None
    if isinstance(equipment_id, list):
        normalized = []
        for item in equipment_id:
            if item in (None, ""):
                raise _error(
                    configuration_id,
                    manifest_path,
                    f"equipment role '{role}' contains an empty equipment ID",
                )
            normalized.append(str(item))
        return normalized
    if isinstance(equipment_id, (str, int, float)):
        return str(equipment_id)
    raise _error(
        configuration_id,
        manifest_path,
        f"equipment role '{role}' must be an equipment ID or list of equipment IDs",
    )


def discover_configuration_manifests(library_root, include_invalid=False):
    """Discover configuration folders that contain a valid manifest."""
    root = Path(library_root)
    manifests = []
    if not root.is_dir():
        return manifests
    for configuration_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        manifest_path = manifest_path_for_configuration(configuration_dir)
        if not manifest_path.is_file():
            if include_invalid:
                manifests.append({
                    "configuration_id": configuration_dir.name,
                    "implementation_status": "disabled",
                    "error": f"missing manifest: {manifest_path}",
                })
            continue
        try:
            manifests.append(load_configuration_manifest(configuration_dir))
        except ConfigurationManifestError as exc:
            if include_invalid:
                manifests.append({
                    "configuration_id": configuration_dir.name,
                    "implementation_status": "disabled",
                    "manifest_path": str(manifest_path),
                    "error": str(exc),
                })
    return manifests


def assert_manifest_executable(manifest):
    """Raise a status-specific error if a manifest is not runnable."""
    status = (manifest or {}).get("implementation_status")
    configuration_id = (manifest or {}).get("configuration_id", "<unknown>")
    topology_id = (manifest or {}).get("solver_topology") or (manifest or {}).get("cooling_system_type")
    if status == "implemented":
        topology = get_topology(topology_id)
        if not topology or topology.get("implementation_status") != "implemented":
            topology_status = topology.get("implementation_status") if topology else "unknown"
            raise UnsupportedConfigurationStatusError(
                f"Configuration '{configuration_id}' declares topology '{topology_id}', "
                f"but that topology is currently '{topology_status}' and cannot be executed."
            )
        return True
    if status == "framework_ready_data_missing":
        raise UnsupportedConfigurationStatusError(
            f"Configuration '{configuration_id}' is framework-ready, but required manufacturer Solver_Curve data is missing."
        )
    if status == "placeholder":
        raise UnsupportedConfigurationStatusError(
            f"Configuration '{configuration_id}' is a placeholder and cannot be executed."
        )
    if status == "disabled":
        raise UnsupportedConfigurationStatusError(
            f"Configuration '{configuration_id}' is disabled and cannot be executed."
        )
    if status == "test_only":
        raise UnsupportedConfigurationStatusError(
            f"Configuration '{configuration_id}' is test-only and cannot be executed."
        )
    raise UnsupportedConfigurationStatusError(
        f"Configuration '{configuration_id}' has invalid implementation_status: {status}"
    )


def _validate_topology_compatibility(manifest, manifest_path):
    configuration_id = manifest["configuration_id"]
    cooling_topology = get_topology(manifest["cooling_system_type"])
    if cooling_topology is None:
        raise _error(
            configuration_id,
            manifest_path,
            f"unknown topology in cooling_system_type: {manifest['cooling_system_type']}",
        )
    solver_topology = get_topology(manifest["solver_topology"])
    if solver_topology is None:
        raise _error(
            configuration_id,
            manifest_path,
            f"unknown solver_topology: {manifest['solver_topology']}",
        )
    if manifest["implementation_status"] == "test_only":
        return
    if solver_topology["topology_id"] != cooling_topology["topology_id"]:
        raise _error(
            configuration_id,
            manifest_path,
            "cooling_system_type and solver_topology refer to different registered topologies",
        )
    topology_status = solver_topology.get("implementation_status")
    manifest_status = manifest["implementation_status"]
    if manifest_status == "implemented" and topology_status != "implemented":
        raise _error(
            configuration_id,
            manifest_path,
            f"declares topology '{solver_topology['topology_id']}', but that topology is currently '{topology_status}' and cannot be executed",
        )
    topology_required_roles = set(solver_topology.get("required_roles", []))
    manifest_required_roles = set(manifest["required_roles"])
    missing_roles = sorted(topology_required_roles - manifest_required_roles)
    if missing_roles:
        raise _error(
            configuration_id,
            manifest_path,
            f"required_roles missing topology-required roles: {', '.join(missing_roles)}",
        )


def _error(configuration_id, manifest_path, message):
    label = configuration_id or "<unknown>"
    location = f" at {manifest_path}" if manifest_path else ""
    return ConfigurationManifestError(f"Configuration '{label}' manifest{location}: {message}")
