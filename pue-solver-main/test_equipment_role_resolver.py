import unittest
from copy import deepcopy

from configuration_library_loader import load_configuration_library
from equipment_role_resolver import (
    EquipmentRoleResolutionError,
    resolve_equipment_role,
    resolve_equipment_role_id,
    validate_required_equipment_roles,
)


class EquipmentRoleResolverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loaded = load_configuration_library("ACC_1.5MW_GASENGINE_CDU")
        cls.manifest = cls.loaded["configuration_manifest"]
        cls.equipment = cls.loaded["equipment"]

    def test_existing_acc_manifest_resolves_expected_roles(self):
        self.assertEqual(resolve_equipment_role_id(self.manifest, "primary_cooling", self.equipment), "ACC_2")
        self.assertEqual(resolve_equipment_role_id(self.manifest, "chw_pump", self.equipment), "CHW_PUMP_2")
        self.assertEqual(resolve_equipment_role_id(self.manifest, "engine", self.equipment), "ENGINE_2")
        self.assertIs(resolve_equipment_role(self.manifest, "primary_cooling", self.equipment), self.equipment["ACC_2"])
        self.assertTrue(validate_required_equipment_roles(self.manifest, self.equipment))

    def test_changed_manifest_role_resolves_changed_equipment_id(self):
        manifest = deepcopy(self.manifest)
        equipment = deepcopy(self.equipment)
        manifest["equipment_roles"]["chw_pump"] = "TEST_PUMP"
        equipment["TEST_PUMP"] = deepcopy(equipment["CHW_PUMP_2"])
        equipment["TEST_PUMP"]["equipment_id"] = "TEST_PUMP"

        self.assertEqual(resolve_equipment_role_id(manifest, "chw_pump", equipment), "TEST_PUMP")
        self.assertEqual(resolve_equipment_role(manifest, "chw_pump", equipment)["equipment_id"], "TEST_PUMP")

    def test_missing_required_role_raises_clear_configuration_error(self):
        manifest = deepcopy(self.manifest)
        del manifest["equipment_roles"]["chw_pump"]

        with self.assertRaisesRegex(EquipmentRoleResolutionError, "missing required equipment role 'chw_pump'"):
            resolve_equipment_role(manifest, "chw_pump", self.equipment)

    def test_missing_optional_role_returns_none(self):
        manifest = deepcopy(self.manifest)
        manifest["optional_roles"] = ["water_treatment"]

        self.assertIsNone(resolve_equipment_role(manifest, "water_treatment", self.equipment))


if __name__ == "__main__":
    unittest.main()
