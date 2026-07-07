import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from equipment_engine import ConfigurationLibraryEquipmentEngine, EquipmentEngineConfig
from test_acc_v2_curve_reader import _write_xlsx


class EquipmentEngineTest(unittest.TestCase):
    def test_load_equipment_once_and_cache(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_config(temp_dir, {
                "CHW_PUMP_2": [["load_ratio", "power_kW"], [0.5, 20]],
            })
            engine = ConfigurationLibraryEquipmentEngine(str(config))

            first = engine.load_equipment("pump")
            second = engine.load_equipment("pump")

        self.assertIs(first, second)
        self.assertEqual(engine.cache_size, 1)

    def test_lookup_chw_pump(self):
        engine = ConfigurationLibraryEquipmentEngine(
            EquipmentEngineConfig(
                preloaded_curves={
                    "CHW_PUMP_2": {
                        "type": "1d_lookup_table",
                        "x_axis": "load_ratio",
                        "output": "power_kW",
                        "data": [{"load_ratio": 0.0, "power_kW": 10}, {"load_ratio": 1.0, "power_kW": 30}],
                    }
                }
            )
        )

        result = engine.lookup_power("CHW_PUMP_2", 0.5)

        self.assertTrue(result.lookup_success)
        self.assertEqual(result.power_kW, 20)

    def test_lookup_mau_power(self):
        engine = ConfigurationLibraryEquipmentEngine(
            EquipmentEngineConfig(
                preloaded_curves={
                    "MAU_1&2": {
                        "type": "1d_lookup_table",
                        "x_axis": "load_ratio",
                        "output": "power_kW",
                        "data": [{"load_ratio": 0.0, "power_kW": 6}, {"load_ratio": 1.0, "power_kW": 12}],
                    }
                }
            )
        )

        result = engine.lookup_power("MAU_1&2", 0.5)

        self.assertTrue(result.lookup_success)
        self.assertEqual(result.power_kW, 9)

    def test_lookup_rtc_and_cdu_power(self):
        engine = ConfigurationLibraryEquipmentEngine(
            EquipmentEngineConfig(
                preloaded_curves={
                    "RTC_1&2": {
                        "type": "1d_lookup_table",
                        "x_axis": "load_ratio",
                        "output": "power_kW",
                        "data": [{"load_ratio": 0.0, "power_kW": 4}, {"load_ratio": 1.0, "power_kW": 10}],
                    },
                    "CDU_2": {
                        "type": "1d_lookup_table",
                        "x_axis": "load_ratio",
                        "output": "power_kW",
                        "data": [{"load_ratio": 0.0, "power_kW": 11}, {"load_ratio": 1.0, "power_kW": 15}],
                    },
                }
            )
        )

        self.assertEqual(engine.lookup_power("RTC_1&2", 0.5).power_kW, 7)
        self.assertEqual(engine.lookup_power("CDU_2", 0.5).power_kW, 13)

    def test_lookup_engine_and_engine_radiator_power(self):
        engine = ConfigurationLibraryEquipmentEngine(
            EquipmentEngineConfig(
                preloaded_curves={
                    "ENGINE_3": {
                        "type": "1d_lookup_table",
                        "x_axis": "load_ratio",
                        "output": "engine_output_kW",
                        "data": [{"load_ratio": 0.0, "engine_output_kW": 1000}, {"load_ratio": 1.0, "engine_output_kW": 1500}],
                    },
                    "ENGINE_RADIATOR_1": {
                        "type": "1d_lookup_table",
                        "x_axis": "load_ratio",
                        "output": "power_kW",
                        "data": [{"load_ratio": 0.0, "power_kW": 20}, {"load_ratio": 1.0, "power_kW": 40}],
                    },
                }
            )
        )

        self.assertEqual(engine.lookup_power("ENGINE_3", 0.5).power_kW, 1250)
        self.assertEqual(engine.lookup_power("ENGINE_RADIATOR_1", 0.5).power_kW, 30)

    def test_lookup_acc_style_2d_curve(self):
        engine = ConfigurationLibraryEquipmentEngine(
            EquipmentEngineConfig(
                preloaded_curves={
                    "ACC_2": {
                        "type": "2d_lookup_table",
                        "x_axis": "ambient_C",
                        "y_axis": "load_ratio",
                        "output": "power_input_kW",
                        "data": [
                            {"ambient_C": 20, "load_ratio": 0.5, "power_input_kW": 100},
                            {"ambient_C": 20, "load_ratio": 1.0, "power_input_kW": 200},
                            {"ambient_C": 30, "load_ratio": 0.5, "power_input_kW": 150},
                            {"ambient_C": 30, "load_ratio": 1.0, "power_input_kW": 300},
                        ],
                    }
                }
            )
        )

        result = engine.lookup_power("ACC_2", 0.75, ambient_C=25)

        self.assertTrue(result.lookup_success)
        self.assertEqual(result.power_input_kW, 187.5)

    def test_missing_equipment_returns_structured_error(self):
        engine = ConfigurationLibraryEquipmentEngine()

        result = engine.lookup_power("UNKNOWN_EQUIPMENT", 0.5)

        self.assertFalse(result.lookup_success)
        self.assertIn("No Configuration Library path or preloaded curve", result.errors[0])

    def test_invalid_curve_returns_structured_error(self):
        engine = ConfigurationLibraryEquipmentEngine(
            EquipmentEngineConfig(
                preloaded_curves={
                    "CHW_PUMP_2": {
                        "type": "1d_lookup_table",
                        "x_axis": "load_ratio",
                        "output": "power_kW",
                        "data": [{"load_ratio": 0.5, "power_kW": 10}, {"load_ratio": 0.5, "power_kW": 11}],
                    }
                }
            )
        )

        result = engine.lookup_power("CHW_PUMP_2", 0.5)

        self.assertFalse(result.lookup_success)
        self.assertIn("Duplicate CHW_PUMP_2 load_ratio point", result.errors[0])

    def test_lookup_electrical_loss_with_efficiency_loss_fraction_and_loss_kw(self):
        engine = ConfigurationLibraryEquipmentEngine(
            EquipmentEngineConfig(
                preloaded_curves={
                    "ELECTRICAL_DISTRIBUTION_2_eff": {
                        "type": "1d_lookup_table",
                        "x_axis": "load_ratio",
                        "output": "efficiency",
                        "data": [{"load_ratio": 0.0, "efficiency": 0.95}, {"load_ratio": 1.0, "efficiency": 0.99}],
                    },
                    "ELECTRICAL_DISTRIBUTION_2_fraction": {
                        "type": "1d_lookup_table",
                        "x_axis": "load_ratio",
                        "output": "loss_fraction",
                        "data": [{"load_ratio": 0.0, "loss_fraction": 0.05}, {"load_ratio": 1.0, "loss_fraction": 0.01}],
                    },
                    "ELECTRICAL_DISTRIBUTION_2_loss": {
                        "type": "1d_lookup_table",
                        "x_axis": "load_ratio",
                        "output": "loss_kW",
                        "data": [{"load_ratio": 0.0, "loss_kW": 5}, {"load_ratio": 1.0, "loss_kW": 15}],
                    },
                }
            )
        )

        self.assertAlmostEqual(
            engine.lookup_electrical_loss("ELECTRICAL_DISTRIBUTION_2_eff", 0.5, base_power_kW=100).loss_kW,
            100 / 0.97 - 100,
        )
        self.assertAlmostEqual(
            engine.lookup_electrical_loss("ELECTRICAL_DISTRIBUTION_2_fraction", 0.5, base_power_kW=100).loss_kW,
            3,
        )
        self.assertEqual(
            engine.lookup_electrical_loss("ELECTRICAL_DISTRIBUTION_2_loss", 0.5).loss_kW,
            10,
        )


def _make_config(root, equipment_sheets):
    config = Path(root) / "ACC_1.5MW_GASENGINE_CDU"
    for folder_name, solver_curve_rows in equipment_sheets.items():
        folder = config / "equipment" / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        _write_xlsx(
            folder / f"{folder_name}.xlsx",
            {
                "Information": [["Parameter", "Value"], ["Equipment", folder_name]],
                "Solver_Curve": solver_curve_rows,
            },
        )
    return config


if __name__ == "__main__":
    unittest.main()
