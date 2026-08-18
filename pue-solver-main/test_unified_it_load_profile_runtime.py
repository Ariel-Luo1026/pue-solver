import unittest
from copy import deepcopy

from configuration_library_loader import build_solver_input_from_library
from topology_dispatcher import dispatch_topology


class UnifiedItLoadProfileRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.design_kw = 4400.0
        cls.profile = [cls.design_kw * (0.72 if hour % 24 < 8 else 0.88) for hour in range(8760)]
        cls.results = {}
        for configuration in ("ACC_1.5MW_GASENGINE_CDU", "CHILLER_DRYCOOLER_2MW_GRID"):
            payload = build_solver_input_from_library(configuration, 4.4, "Normal")
            payload["project"]["it_load"].update({
                "source_type": "user_uploaded", "source_name": "Synthetic Variable 8760", "hours": 8760,
                "hourly_it_load_kW": list(cls.profile),
                "hourly_it_load_percent": [value / cls.design_kw * 100 for value in cls.profile],
                "validation_status": "valid",
            })
            payload["weather"] = {"hourly_data": {
                "hour_index": list(range(1, 8761)), "dry_bulb_C": [25.0] * 8760, "wet_bulb_C": [],
            }}
            override = {"extreme_db_max_C": 44.0, "source": "test_override"}
            payload["peak_design_condition_override"] = override
            payload["project"]["peak_design_condition_override"] = override
            cls.results[configuration] = dispatch_topology(payload["configuration_manifest"], deepcopy(payload))

    def test_identical_variable_profile_reaches_both_topologies(self):
        acc = [row["IT_load_kW"] for row in self.results["ACC_1.5MW_GASENGINE_CDU"]["hourly_results"]]
        chiller = [row["it_load_kW"] for row in self.results["CHILLER_DRYCOOLER_2MW_GRID"]["hourly_results"]]
        self.assertEqual(acc, self.profile)
        self.assertEqual(chiller, self.profile)

    def test_annual_it_energy_matches_across_topologies(self):
        expected = sum(self.profile)
        self.assertEqual(
            [result["annual_results"]["annual_IT_energy_kWh"] for result in self.results.values()],
            [expected, expected],
        )

    def test_peak_design_remains_full_design_capacity(self):
        self.assertLess(max(self.profile), self.design_kw)
        for result in self.results.values():
            self.assertEqual(result["peak_results"]["peak_design_it_load_kW"], self.design_kw)


if __name__ == "__main__":
    unittest.main()
