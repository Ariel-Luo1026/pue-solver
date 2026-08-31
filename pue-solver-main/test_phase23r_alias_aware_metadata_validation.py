import json
import unittest
from pathlib import Path

from configuration_library_loader import load_configuration_library, select_solver_curve


ROOT = Path(__file__).resolve().parent
LIBRARY = ROOT.parent / "Configuration Library"


class Phase23RAliasAwareMetadataValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = (ROOT / "ui.js").read_text(encoding="utf-8")

    @staticmethod
    def metadata_identity_warning(package_item):
        metadata = package_item.get("equipment_metadata") or {}
        source_equipment_id = (
            package_item.get("source_workbook_equipment_id")
            or package_item.get("equipment_id")
        )
        if metadata.get("equipment_id") and metadata["equipment_id"] != source_equipment_id:
            return "equipment_metadata equipment_id does not match loaded equipment folder"
        return None

    def test_frontend_uses_source_workbook_identity_with_safe_fallback(self):
        self.assertIn(
            "const sourceEquipmentId = packageItem.source_workbook_equipment_id || packageItem.equipment_id;",
            self.ui,
        )
        self.assertIn(
            "metadata.equipment_id !== sourceEquipmentId",
            self.ui,
        )
        self.assertNotIn(
            "metadata.equipment_id !== packageItem.equipment_id",
            self.ui,
        )

    def test_acc_1mw_gas_alias_is_valid_and_curves_remain_scenario_aware(self):
        metadata = json.loads(
            (LIBRARY / "ACC_1MW_GASENGINE_CDU" / "equipment" / "ENGINE_2" / "equipment_metadata.json")
            .read_text(encoding="utf-8")
        )
        frontend_package = {
            "equipment_id": "ENGINE_3",
            "source_workbook_equipment_id": "ENGINE_2",
            "equipment_metadata": metadata,
        }
        self.assertIsNone(self.metadata_identity_warning(frontend_package))

        loaded = load_configuration_library("ACC_1MW_GASENGINE_CDU", LIBRARY)
        engine = loaded["equipment"]["ENGINE_2"]
        self.assertEqual(select_solver_curve(engine, "Normal")["sheet_name"], "Solver_Curve_Normal")
        self.assertEqual(select_solver_curve(engine, "Failure")["sheet_name"], "Solver_Curve_Failure")

    def test_unrelated_metadata_identity_remains_invalid(self):
        frontend_package = {
            "equipment_id": "ENGINE_3",
            "source_workbook_equipment_id": "ENGINE_2",
            "equipment_metadata": {"equipment_id": "UNRELATED_ENGINE"},
        }
        self.assertIsNotNone(self.metadata_identity_warning(frontend_package))

    def test_canonical_engine_and_other_topologies_remain_valid(self):
        canonical = {
            "equipment_id": "ENGINE_3",
            "source_workbook_equipment_id": "ENGINE_3",
            "equipment_metadata": {"equipment_id": "ENGINE_3"},
        }
        self.assertIsNone(self.metadata_identity_warning(canonical))

        for configuration_id in (
            "ACC_1MW_GRID_CDU",
            "ACC_1.5MW_GASENGINE_CDU",
            "CHILLER_DRYCOOLER_2MW_GASENGINE_CDU",
        ):
            loaded = load_configuration_library(configuration_id, LIBRARY)
            manifest = loaded["configuration_manifest"]
            for role in manifest["required_roles"]:
                declared = manifest["equipment_roles"][role]
                declared_ids = declared if isinstance(declared, list) else [declared]
                for declared_id in declared_ids:
                    package = loaded["equipment"].get(declared_id)
                    if package is None:
                        package = next(
                            item for item in loaded["equipment"].values()
                            if item.get("actual_equipment_id") == declared_id
                        )
                    frontend_package = {
                        "equipment_id": package["actual_equipment_id"],
                        "source_workbook_equipment_id": package["actual_equipment_id"],
                        "equipment_metadata": package["equipment_metadata"],
                    }
                    self.assertIsNone(
                        self.metadata_identity_warning(frontend_package),
                        f"{configuration_id}: {role}={declared_id}",
                    )


if __name__ == "__main__":
    unittest.main()
