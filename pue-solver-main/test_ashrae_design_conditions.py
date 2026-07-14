import unittest

from ashrae_design_conditions import get_peak_design_condition, load_design_condition_stations


class AshraeDesignConditionsTest(unittest.TestCase):
    def test_placeholder_station_loads(self):
        stations = load_design_condition_stations()

        self.assertTrue(stations)
        self.assertEqual(stations[0]["station_name"], "WINSTON FIELD, TX, USA")
        self.assertAlmostEqual(stations[0]["db_max_20yr_C"], 44.0)

    def test_peak_design_condition_interface(self):
        condition = get_peak_design_condition(32.693, -100.951)

        self.assertEqual(condition["source"], "ASHRAE_20_year_extreme")
        self.assertEqual(condition["station_name"], "WINSTON FIELD, TX, USA")
        self.assertEqual(condition["station_id"], "ASHRAE_PLACEHOLDER_WINSTON_FIELD_TX")
        self.assertAlmostEqual(condition["extreme_db_max_C"], 44.0)
        self.assertAlmostEqual(condition["extreme_db_min_C"], -16.9)


if __name__ == "__main__":
    unittest.main()
