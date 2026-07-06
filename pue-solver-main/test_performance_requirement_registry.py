import unittest

from performance_requirement_registry import (
    PERFORMANCE_REQUIREMENT_REGISTRY,
    get_performance_requirement,
    get_topology_performance_requirements,
    list_performance_requirements,
    list_requirements_by_equipment,
    list_requirements_by_status,
)


class PerformanceRequirementRegistryTest(unittest.TestCase):
    def test_all_expected_requirement_ids_exist(self):
        self.assertEqual(
            set(PERFORMANCE_REQUIREMENT_REGISTRY),
            {
                "it_load_profile",
                "weather_profile",
                "acc_performance_curve",
                "cdu_performance_curve",
                "pump_power_curve",
                "terminal_fan_curve",
                "electrical_efficiency_curve",
                "auxiliary_fixed_load",
                "gas_engine_curve",
                "chiller_cop_surface",
                "dry_cooler_fan_curve",
                "cooling_tower_performance_curve",
                "absorption_chiller_performance_curve",
                "heat_exchanger_curve",
            },
        )
        self.assertEqual(len(list_performance_requirements()), 14)

    def test_acc_topology_performance_requirements_include_current_acc_stack(self):
        requirement_ids = {
            requirement["requirement_id"]
            for requirement in get_topology_performance_requirements("acc")
        }
        for requirement_id in (
            "it_load_profile",
            "weather_profile",
            "acc_performance_curve",
            "pump_power_curve",
            "terminal_fan_curve",
            "electrical_efficiency_curve",
            "auxiliary_fixed_load",
            "gas_engine_curve",
        ):
            self.assertIn(requirement_id, requirement_ids)

    def test_chiller_dry_cooler_topology_requirements_include_future_curves(self):
        requirement_ids = {
            requirement["requirement_id"]
            for requirement in get_topology_performance_requirements("chiller_dry_cooler")
        }
        self.assertIn("chiller_cop_surface", requirement_ids)
        self.assertIn("dry_cooler_fan_curve", requirement_ids)

    def test_abs_cooling_tower_requirements_include_abs_tower_and_engine_curves(self):
        requirement_ids = {
            requirement["requirement_id"]
            for requirement in get_topology_performance_requirements("abs_cooling_tower")
        }
        self.assertIn("absorption_chiller_performance_curve", requirement_ids)
        self.assertIn("cooling_tower_performance_curve", requirement_ids)
        self.assertIn("gas_engine_curve", requirement_ids)

    def test_placeholder_systems_return_placeholder_future_requirements(self):
        requirement_ids = {
            requirement["requirement_id"]
            for requirement in list_requirements_by_status("placeholder")
        }
        self.assertIn("chiller_cop_surface", requirement_ids)
        self.assertIn("dry_cooler_fan_curve", requirement_ids)
        self.assertIn("cooling_tower_performance_curve", requirement_ids)
        self.assertIn("absorption_chiller_performance_curve", requirement_ids)
        self.assertIn("heat_exchanger_curve", requirement_ids)

    def test_equipment_requirement_lookup(self):
        requirement_ids = {
            requirement["requirement_id"]
            for requirement in list_requirements_by_equipment("acc_unit")
        }
        self.assertIn("acc_performance_curve", requirement_ids)
        self.assertIn("it_load_profile", requirement_ids)
        self.assertIn("weather_profile", requirement_ids)

    def test_lookup_results_are_copies(self):
        requirement = get_performance_requirement("acc_performance_curve")
        requirement["typical_independent_variables"].append("Mutation")
        self.assertNotIn(
            "Mutation",
            get_performance_requirement("acc_performance_curve")[
                "typical_independent_variables"
            ],
        )


if __name__ == "__main__":
    unittest.main()
