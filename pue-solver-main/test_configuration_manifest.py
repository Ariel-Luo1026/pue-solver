import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from configuration_manifest import (
    ConfigurationManifestError,
    UnsupportedConfigurationStatusError,
    assert_manifest_executable,
    discover_configuration_manifests,
    load_configuration_manifest,
    validate_configuration_manifest,
)


def valid_acc_manifest(**overrides):
    manifest = {
        "schema_version": "1.0",
        "configuration_id": "ACC_1.5MW_GASENGINE_CDU",
        "display_name": "ACC 1.5 MW + Gas Engine + CDU",
        "cooling_system_type": "acc_gas_engine_cdu",
        "implementation_status": "implemented",
        "description": "test manifest",
        "equipment_roles": {
            "primary_cooling": "ACC_2",
            "chw_pump": "CHW_PUMP_2",
            "rtc": "RTC_1&2",
            "cdu": "CDU_2",
            "mau": "MAU_1&2",
            "engine": "ENGINE_3",
            "engine_radiator": "ENGINE_RADIATOR_1",
            "electrical_distribution": "ELECTRICAL_DISTRIBUTION_2",
        },
        "required_roles": [
            "primary_cooling",
            "chw_pump",
            "rtc",
            "cdu",
            "mau",
            "engine",
            "engine_radiator",
            "electrical_distribution",
        ],
        "optional_roles": [],
        "solver_topology": "acc_gas_engine_cdu",
        "report_profile": "acc_gas_engine_cdu",
    }
    manifest.update(overrides)
    return manifest


class ConfigurationManifestTest(unittest.TestCase):
    def write_manifest(self, root, configuration_id, manifest):
        config_dir = Path(root) / configuration_id
        config_dir.mkdir(parents=True)
        (config_dir / "configuration_manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        return config_dir

    def test_valid_acc_manifest_loads(self):
        manifest = validate_configuration_manifest(valid_acc_manifest())
        self.assertEqual(manifest["configuration_id"], "ACC_1.5MW_GASENGINE_CDU")
        self.assertEqual(manifest["implementation_status"], "implemented")
        self.assertEqual(manifest["solver_topology"], "acc_gas_engine_cdu")
        self.assertTrue(assert_manifest_executable(manifest))

    def test_missing_required_field_fails(self):
        manifest = valid_acc_manifest()
        del manifest["configuration_id"]
        with self.assertRaisesRegex(ConfigurationManifestError, "missing required field: configuration_id"):
            validate_configuration_manifest(manifest)

    def test_invalid_status_fails(self):
        with self.assertRaisesRegex(ConfigurationManifestError, "invalid implementation_status"):
            validate_configuration_manifest(valid_acc_manifest(implementation_status="ready-ish"))

    def test_invalid_topology_fails(self):
        with self.assertRaisesRegex(ConfigurationManifestError, "unknown topology"):
            validate_configuration_manifest(valid_acc_manifest(cooling_system_type="not_a_topology"))

    def test_missing_required_equipment_role_fails_for_implemented_manifest(self):
        manifest = valid_acc_manifest()
        manifest["equipment_roles"]["engine"] = ""
        with self.assertRaisesRegex(ConfigurationManifestError, "missing required equipment role: engine"):
            validate_configuration_manifest(manifest)

    def test_placeholder_topology_cannot_execute(self):
        manifest = valid_acc_manifest(
            configuration_id="CHILLER_COOLINGTOWER_2MW_GRID_CDU",
            cooling_system_type="chiller_cooling_tower",
            implementation_status="placeholder",
            solver_topology="chiller_cooling_tower",
            required_roles=["primary_cooling", "cooling_tower", "chw_pump", "cdu"],
            equipment_roles={
                "primary_cooling": "CENTRIFUGALCHILLER_1",
                "cooling_tower": "COOLING_TOWER_2",
                "chw_pump": "CHW_PUMP_2",
                "cdu": "CDU_2",
            },
        )
        validated = validate_configuration_manifest(manifest)
        with self.assertRaisesRegex(UnsupportedConfigurationStatusError, "placeholder"):
            assert_manifest_executable(validated)

    def test_mismatched_solver_topology_rejected(self):
        with self.assertRaisesRegex(ConfigurationManifestError, "different registered topologies"):
            validate_configuration_manifest(valid_acc_manifest(solver_topology="chiller_cooling_tower"))

    def test_required_role_mismatch_rejected(self):
        manifest = valid_acc_manifest(required_roles=["primary_cooling"])
        with self.assertRaisesRegex(ConfigurationManifestError, "required_roles missing"):
            validate_configuration_manifest(manifest)

    def test_discovery_finds_only_manifest_folders(self):
        with TemporaryDirectory() as temp_dir:
            self.write_manifest(temp_dir, "ACC_1.5MW_GASENGINE_CDU", valid_acc_manifest())
            (Path(temp_dir) / "unrelated").mkdir()
            manifests = discover_configuration_manifests(temp_dir)
        self.assertEqual([item["configuration_id"] for item in manifests], ["ACC_1.5MW_GASENGINE_CDU"])

    def test_repository_acc_manifest_loads(self):
        config_dir = Path(__file__).resolve().parent.parent / "Configuration Library" / "ACC_1.5MW_GASENGINE_CDU"
        manifest = load_configuration_manifest(config_dir)
        self.assertEqual(manifest["configuration_id"], "ACC_1.5MW_GASENGINE_CDU")
        self.assertEqual(manifest["implementation_status"], "implemented")


if __name__ == "__main__":
    unittest.main()
