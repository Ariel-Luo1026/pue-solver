import unittest

from topology_registry import (
    TOPOLOGY_REGISTRY,
    get_topology,
    get_topology_by_cooling_type,
    get_topology_equipment,
    list_topologies,
)
from equipment_registry import equipment_ids_equivalent


class TopologyRegistryTest(unittest.TestCase):
    def test_all_expected_topology_ids_exist(self):
        self.assertEqual(
            set(TOPOLOGY_REGISTRY),
            {
                "acc_gas_engine_cdu",
                "chiller_dry_cooler",
                "water_cooled_chiller",
                "chiller_cooling_tower",
                "liquid_cooling",
                "abs_dry_cooler",
                "abs_cooling_tower",
            },
        )
        self.assertEqual(len(list_topologies()), 7)

    def test_acc_topology_is_implemented(self):
        self.assertEqual(get_topology("acc_gas_engine_cdu")["implementation_status"], "implemented")
        self.assertEqual(get_topology("acc")["implementation_status"], "implemented")

    def test_non_acc_topologies_are_not_implemented(self):
        self.assertEqual(
            get_topology("chiller_dry_cooler")["implementation_status"],
            "framework_ready_data_missing",
        )
        for topology_id in set(TOPOLOGY_REGISTRY) - {"acc_gas_engine_cdu", "chiller_dry_cooler"}:
            self.assertEqual(get_topology(topology_id)["implementation_status"], "placeholder")

    def test_acc_heat_flow_path_contains_required_steps(self):
        heat_flow_path = get_topology("acc")["heat_flow_path"]
        for step in ("IT Load", "CDU", "ACC", "Outdoor Air"):
            self.assertIn(step, heat_flow_path)

    def test_chiller_cooling_tower_environmental_driver_is_wet_bulb_or_cooling_water(self):
        drivers = get_topology("chiller_cooling_tower")["environmental_driver"]
        self.assertTrue(
            any("Wet Bulb" in driver or "Cooling Water Temperature" in driver for driver in drivers)
        )

    def test_abs_topologies_use_absorption_chiller_primary_equipment(self):
        for topology_id in ("abs_dry_cooler", "abs_cooling_tower"):
            self.assertIn(
                "Absorption Chiller",
                get_topology(topology_id)["primary_cooling_equipment"],
            )

    def test_lookup_by_cooling_type(self):
        topology = get_topology_by_cooling_type("Chiller + Cooling Tower")
        self.assertIsNotNone(topology)
        self.assertEqual(topology["topology_id"], "chiller_cooling_tower")
        self.assertEqual(get_topology_by_cooling_type("ACC")["topology_id"], "acc")

    def test_lookup_results_are_copies(self):
        topology = get_topology("acc_gas_engine_cdu")
        topology["heat_flow_path"].append("Mutation")
        self.assertNotIn("Mutation", get_topology("acc")["heat_flow_path"])

    def test_every_topology_has_equipment_ids(self):
        for topology in list_topologies():
            self.assertIn("equipment_ids", topology)
            self.assertTrue(topology["equipment_ids"])

    def test_all_topology_equipment_ids_are_valid(self):
        for topology_id in TOPOLOGY_REGISTRY:
            records = get_topology_equipment(topology_id)
            expected_ids = get_topology(topology_id)["equipment_ids"]
            self.assertEqual(len(records), len(expected_ids))
            for record, expected_id in zip(records, expected_ids):
                self.assertTrue(equipment_ids_equivalent(record["equipment_id"], expected_id))

    def test_acc_topology_includes_current_acc_equipment_references(self):
        equipment_ids = set(get_topology("acc_gas_engine_cdu")["equipment_ids"])
        for equipment_id in ("acc_unit", "cdu", "pump", "gas_engine"):
            self.assertIn(equipment_id, equipment_ids)

    def test_abs_topologies_include_absorption_chiller_and_gas_engine(self):
        for topology_id in ("abs_dry_cooler", "abs_cooling_tower"):
            equipment_ids = set(get_topology(topology_id)["equipment_ids"])
            self.assertIn("absorption_chiller", equipment_ids)
            self.assertIn("gas_engine", equipment_ids)

    def test_chiller_topologies_include_chiller(self):
        for topology_id in ("chiller_dry_cooler", "chiller_cooling_tower"):
            self.assertIn("chiller", get_topology(topology_id)["equipment_ids"])

    def test_cooling_tower_topologies_include_cooling_tower(self):
        for topology_id in ("chiller_cooling_tower", "abs_cooling_tower"):
            self.assertIn("cooling_tower", get_topology(topology_id)["equipment_ids"])

    def test_dry_cooler_topologies_include_dry_cooler(self):
        for topology_id in ("chiller_dry_cooler", "abs_dry_cooler"):
            self.assertIn("dry_cooler", get_topology(topology_id)["equipment_ids"])

    def test_get_topology_equipment_returns_equipment_records(self):
        records = get_topology_equipment("acc")
        self.assertTrue(records)
        self.assertTrue(all(isinstance(record, dict) for record in records))
        self.assertTrue(all("equipment_id" in record for record in records))
        self.assertIn("ACC Unit", {record["display_name"] for record in records})


if __name__ == "__main__":
    unittest.main()
