import unittest
from pathlib import Path

from equipment_engines.equipment_engine_dispatcher import (
    EquipmentEngineDispatchError,
    dispatch_equipment_engine,
)
from equipment_metadata import load_equipment_metadata


class EquipmentEngineDispatcherTest(unittest.TestCase):
    def test_acc_dispatch_works(self):
        metadata = load_equipment_metadata(
            Path(__file__).resolve().parent.parent
            / "Configuration Library"
            / "ACC_1.5MW_GASENGINE_CDU"
            / "equipment"
            / "ACC_2"
        )

        engine = dispatch_equipment_engine(metadata, metadata["curve_type"], [{"ambient_C": 35}])

        self.assertEqual(engine["status"], "implemented")
        self.assertEqual(engine["equipment_type"], "ACC")
        self.assertEqual(engine["curve_schema"], "ambient_capacity_power_2D")
        self.assertEqual(engine["engine_type"], "existing_acc_v2_wrapper")

    def test_pump_dispatch_works(self):
        metadata = load_equipment_metadata(
            Path(__file__).resolve().parent.parent
            / "Configuration Library"
            / "ACC_1.5MW_GASENGINE_CDU"
            / "equipment"
            / "CHW_PUMP_2"
        )

        engine = dispatch_equipment_engine(metadata, metadata["curve_type"], [{"load_ratio": 1.0}])

        self.assertEqual(engine["status"], "implemented")
        self.assertEqual(engine["equipment_type"], "CHW_PUMP")
        self.assertEqual(engine["curve_schema"], "load_ratio_power_1D")
        self.assertEqual(engine["engine_type"], "configuration_library_equipment_engine")

    def test_chiller_returns_framework_ready(self):
        metadata = load_equipment_metadata(
            Path(__file__).resolve().parent.parent
            / "Configuration Library"
            / "CHILLER_DRYCOOLER_2MW_GRID"
            / "equipment"
            / "CENTRIFUGALCHILLER_1"
        )

        engine = dispatch_equipment_engine(metadata, metadata["curve_type"], [{"load_ratio": 1.0}])

        self.assertEqual(engine["status"], "framework_ready")
        self.assertEqual(engine["equipment_type"], "CHILLER")
        self.assertEqual(engine["curve_schema"], "cop_map_2D")
        self.assertIsNone(engine["engine_type"])

    def test_unknown_curve_rejected(self):
        metadata = {
            "equipment_id": "ACC_TEST",
            "equipment_type": "ACC",
            "curve_type": "unknown_curve_type",
        }

        with self.assertRaisesRegex(EquipmentEngineDispatchError, "Unsupported curve_type for ACC"):
            dispatch_equipment_engine(metadata, metadata["curve_type"], [])


if __name__ == "__main__":
    unittest.main()
