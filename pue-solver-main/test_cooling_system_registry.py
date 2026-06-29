import unittest

from cooling_system_registry import COOLING_SYSTEM_REGISTRY, resolve_configuration_equipment
from equipment_catalog import EQUIPMENT_CATALOG, get_equipment_item, resolve_equipment_list


GAS_ONLY_PREFIXES = ("ENGINE_", "ENGINE_RADIATOR_", "SMOKE_WATER_HX_")


class CoolingSystemRegistrySmokeTest(unittest.TestCase):
    def test_catalog_and_distinct_model_items_exist(self):
        self.assertTrue(EQUIPMENT_CATALOG)
        for equipment_id in (
            "ACC_1", "ACC_2", "CHW_PUMP_1", "CHW_PUMP_2", "CHW_PUMP_3",
            "ENGINE_2", "ENGINE_3", "ENGINE_RADIATOR_1",
        ):
            self.assertEqual(get_equipment_item(equipment_id)["id"], equipment_id)
        self.assertIsNot(EQUIPMENT_CATALOG["ACC_1"], EQUIPMENT_CATALOG["ACC_2"])
        self.assertEqual(
            len({id(EQUIPMENT_CATALOG[f"CHW_PUMP_{n}"]) for n in (1, 2, 3)}), 3
        )

    def test_all_registry_ids_resolve_and_gas_equipment_is_isolated(self):
        for system in COOLING_SYSTEM_REGISTRY.values():
            for unit in system["cooling_unit_capacities"].values():
                for source_name, config in unit["power_sources"].items():
                    equipment_ids = config["white_space_equipment"] + config["gray_space_equipment"]
                    self.assertTrue(all(item is not None for item in resolve_equipment_list(equipment_ids)))
                    gas_ids = [item for item in config["gray_space_equipment"] if item.startswith(GAS_ONLY_PREFIXES)]
                    if source_name == "Gas Engine":
                        self.assertTrue(any(item.startswith("ENGINE_") for item in gas_ids))
                        self.assertTrue(any(item.startswith("ENGINE_RADIATOR_") for item in gas_ids))
                    else:
                        self.assertEqual(gas_ids, [])

    def test_acc_one_mw_paths_match_model_level_source_table_example(self):
        sources = COOLING_SYSTEM_REGISTRY["ACC"]["cooling_unit_capacities"]["1"]["power_sources"]
        expected_white = ["CDU_1", "RTC_1", "RTC_2", "MAU_1", "MAU_2"]
        self.assertEqual(sources["Grid"]["white_space_equipment"], expected_white)
        self.assertEqual(sources["Grid"]["gray_space_equipment"], ["ACC_1", "CHW_PUMP_1"])
        self.assertEqual(sources["Gas Engine"]["white_space_equipment"], expected_white)
        self.assertEqual(
            sources["Gas Engine"]["gray_space_equipment"],
            ["ACC_1", "CHW_PUMP_1", "ENGINE_RADIATOR_1", "ENGINE_2"],
        )

    def test_existing_grid_chiller_dry_cooler_path_is_valid(self):
        system = COOLING_SYSTEM_REGISTRY["Chiller + Dry Cooler"]
        self.assertTrue(system["calculation_implemented"])
        grid = system["cooling_unit_capacities"]["2"]["power_sources"]["Grid"]
        self.assertTrue(grid["white_space_equipment"])
        self.assertTrue(grid["gray_space_equipment"])
        resolved = resolve_configuration_equipment("Chiller + Dry Cooler", 2, "Grid")
        self.assertTrue(all(resolved.values()))


if __name__ == "__main__":
    unittest.main()
