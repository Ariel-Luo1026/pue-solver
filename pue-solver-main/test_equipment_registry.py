import unittest

from equipment_registry import (
    EQUIPMENT_REGISTRY,
    get_equipment,
    list_equipment,
    list_equipment_by_category,
    list_equipment_by_status,
)


class EquipmentRegistryTest(unittest.TestCase):
    def test_all_expected_equipment_ids_exist(self):
        self.assertEqual(
            set(EQUIPMENT_REGISTRY),
            {
                "acc_unit",
                "cdu",
                "pump",
                "terminal_fan",
                "electrical_distribution",
                "auxiliary_load",
                "chiller",
                "dry_cooler",
                "cooling_tower",
                "absorption_chiller",
                "gas_engine",
                "heat_exchanger",
            },
        )
        self.assertEqual(len(list_equipment()), 12)

    def test_current_acc_support_equipment_statuses(self):
        self.assertEqual(get_equipment("acc_unit")["implementation_status"], "implemented")
        self.assertIn(
            get_equipment("pump")["implementation_status"],
            {"implemented", "existing-supported"},
        )

    def test_future_cooling_equipment_is_placeholder(self):
        for equipment_id in ("chiller", "absorption_chiller", "cooling_tower"):
            self.assertEqual(get_equipment(equipment_id)["implementation_status"], "placeholder")

    def test_gas_engine_exists(self):
        gas_engine = get_equipment("gas_engine")
        self.assertIsNotNone(gas_engine)
        self.assertEqual(gas_engine["display_name"], "Gas Engine")

    def test_heat_rejection_category_contains_expected_equipment(self):
        heat_rejection_names = {
            equipment["display_name"]
            for equipment in list_equipment_by_category("heat_rejection")
        }
        self.assertIn("ACC Unit", heat_rejection_names)
        self.assertIn("Dry Cooler", heat_rejection_names)
        self.assertIn("Cooling Tower", heat_rejection_names)

    def test_placeholder_status_returns_future_equipment(self):
        placeholder_ids = {
            equipment["equipment_id"]
            for equipment in list_equipment_by_status("placeholder")
        }
        self.assertIn("chiller", placeholder_ids)
        self.assertIn("dry_cooler", placeholder_ids)
        self.assertIn("cooling_tower", placeholder_ids)
        self.assertIn("absorption_chiller", placeholder_ids)
        self.assertIn("heat_exchanger", placeholder_ids)

    def test_lookup_results_are_copies(self):
        equipment = get_equipment("acc_unit")
        equipment["typical_inputs"].append("Mutation")
        self.assertNotIn("Mutation", get_equipment("acc_unit")["typical_inputs"])


if __name__ == "__main__":
    unittest.main()
