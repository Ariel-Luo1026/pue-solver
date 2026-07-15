import unittest
from unittest.mock import patch

from urllib.error import HTTPError

from ashrae_online_lookup import (
    lookup_online_ashrae_design_condition,
    normalize_online_station,
    query_ashrae_online,
)
from ashrae_design_conditions import (
    find_nearest_ashrae_station,
    get_peak_design_condition,
    haversine_distance_km,
    load_design_condition_stations,
)


class AshraeDesignConditionsTest(unittest.TestCase):
    def test_placeholder_station_loads(self):
        stations = load_design_condition_stations()

        self.assertTrue(stations)
        self.assertEqual(stations[0]["station_name"], "WINSTON FIELD, TX, USA")
        self.assertEqual(stations[0]["station_id"], "722122")
        self.assertAlmostEqual(stations[0]["db_max_20yr_C"], 44.0)
        self.assertEqual(
            stations[0]["design_conditions"]["basis"],
            "ASHRAE_20_year_extreme_annual_design_condition",
        )

    def test_nearest_station_calculation(self):
        station = find_nearest_ashrae_station(32.700, -100.950, load_design_condition_stations())

        self.assertEqual(station["station_name"], "WINSTON FIELD, TX, USA")
        self.assertEqual(station["station_id"], "722122")
        self.assertLess(station["distance_km"], 1.0)
        self.assertAlmostEqual(station["extreme_annual_db_max_C"], 44.0)

    def test_distance_calculation(self):
        self.assertAlmostEqual(haversine_distance_km(32.693, -100.951, 32.693, -100.951), 0.0)
        self.assertGreater(haversine_distance_km(32.693, -100.951, 32.8471, -96.8518), 300.0)
        self.assertEqual(haversine_distance_km(32.693, -100.951, None, None), float("inf"))

    def test_peak_design_temperature_retrieval(self):
        condition = get_peak_design_condition(32.693, -100.951)

        self.assertEqual(condition["source"], "ASHRAE_local_cache")
        self.assertEqual(condition["lookup_status"], "failed")
        self.assertEqual(condition["failure_reason"], "Online ASHRAE provider unavailable")
        self.assertEqual(condition["station_name"], "WINSTON FIELD, TX, USA")
        self.assertEqual(condition["station_id"], "722122")
        self.assertAlmostEqual(condition["station_distance_km"], 0.0)
        self.assertAlmostEqual(condition["extreme_db_max_C"], 44.0)
        self.assertEqual(
            condition["temperature_basis"],
            "ASHRAE_20_year_extreme_annual_design_condition",
        )

    def test_no_location_fallback_is_preserved(self):
        condition = get_peak_design_condition(None, None)

        self.assertEqual(condition["source"], "ASHRAE_local_cache")
        self.assertEqual(condition["lookup_status"], "failed")
        self.assertEqual(condition["failure_reason"], "project coordinates missing")
        self.assertEqual(condition["station_name"], "WINSTON FIELD, TX, USA")
        self.assertAlmostEqual(condition["extreme_db_max_C"], 44.0)

    def test_online_endpoint_lookup_matches_albany_for_upstate_new_york_coordinates(self):
        payload = {
            "stations": [
                {
                    "station": "ALBANY INTL, NY, USA",
                    "id": "725180",
                    "station_latitude": 42.747,
                    "station_longitude": -73.799,
                    "design_db_max_C": 44.0,
                }
            ]
        }
        with patch("ashrae_online_lookup._fetch_endpoint", return_value=payload):
            online = query_ashrae_online(42.651, -73.754, endpoint="https://example.test/ashrae")

        self.assertEqual(online["source"], "ASHRAE_online")
        self.assertEqual(online["lookup_status"], "success")
        self.assertEqual(online["failure_reason"], "")
        self.assertEqual(online["lookup_provider"], "ASHRAE_online")
        self.assertEqual(online["station_name"], "ALBANY INTL, NY, USA")
        self.assertEqual(online["station_id"], "725180")
        self.assertLess(online["distance_km"], 20.0)
        self.assertAlmostEqual(online["design_db_max_C"], 44.0)
        self.assertEqual(online["design_condition_basis"], "20-year Extreme Annual Design Condition")

    def test_peak_design_condition_uses_online_result_when_provider_succeeds(self):
        with patch(
            "ashrae_design_conditions.lookup_online_ashrae_design_condition",
            return_value={
                "source": "ASHRAE_online",
                "lookup_provider": "ASHRAE_online",
                "lookup_status": "success",
                "failure_reason": "",
                "station_name": "ALBANY INTL, NY, USA",
                "station_id": "725180",
                "latitude": 42.747,
                "longitude": -73.799,
                "distance_km": 10.8,
                "design_db_max_C": 44.0,
                "extreme_db_max_C": 44.0,
                "temperature_basis": "ASHRAE_20_year_extreme_annual_design_condition",
            },
        ):
            condition = get_peak_design_condition(42.651, -73.754)

        self.assertEqual(condition["source"], "ASHRAE_online")
        self.assertEqual(condition["lookup_provider"], "ASHRAE_online")
        self.assertEqual(condition["lookup_status"], "success")
        self.assertEqual(condition["failure_reason"], "")
        self.assertEqual(condition["station_name"], "ALBANY INTL, NY, USA")
        self.assertEqual(condition["station_id"], "725180")
        self.assertAlmostEqual(condition["design_db_max_C"], 44.0)

    def test_online_failure_uses_local_json_fallback(self):
        with patch("ashrae_design_conditions.lookup_online_ashrae_design_condition", return_value=None):
            condition = get_peak_design_condition(42.651, -73.754)

        self.assertEqual(condition["source"], "ASHRAE_local_cache")
        self.assertEqual(condition["lookup_status"], "failed")
        self.assertEqual(condition["station_name"], "DALLAS LOVE FIELD, TX, USA")
        self.assertEqual(condition["station_id"], "722580")

    def test_no_endpoint_returns_no_online_station(self):
        with patch.dict("ashrae_online_lookup.environ", {}, clear=True):
            condition = lookup_online_ashrae_design_condition(42.651, -73.754, endpoint=None)

        self.assertEqual(condition["lookup_status"], "failed")
        self.assertEqual(condition["failure_reason"], "Online ASHRAE provider unavailable")

    def test_network_failure_returns_explicit_failure_reason(self):
        with patch("ashrae_online_lookup._fetch_endpoint", side_effect=OSError("offline")):
            condition = lookup_online_ashrae_design_condition(42.651, -73.754, endpoint="https://example.test/ashrae")

        self.assertEqual(condition["lookup_status"], "failed")
        self.assertIn("Online ASHRAE provider unavailable", condition["failure_reason"])

    def test_http_error_returns_explicit_failure_reason(self):
        error = HTTPError("https://example.test/ashrae", 503, "Service Unavailable", None, None)
        with patch("ashrae_online_lookup._fetch_endpoint", side_effect=error):
            condition = query_ashrae_online(42.651, -73.754, endpoint="https://example.test/ashrae")

        self.assertEqual(condition["lookup_status"], "failed")
        self.assertEqual(condition["failure_reason"], "ASHRAE online HTTP error: 503")

    def test_timeout_returns_explicit_failure_reason(self):
        with patch("ashrae_online_lookup._fetch_endpoint", side_effect=TimeoutError()):
            condition = query_ashrae_online(42.651, -73.754, endpoint="https://example.test/ashrae")

        self.assertEqual(condition["lookup_status"], "failed")
        self.assertEqual(condition["failure_reason"], "ASHRAE online request timeout")

    def test_invalid_json_returns_explicit_failure_reason(self):
        with patch("ashrae_online_lookup._fetch_endpoint", side_effect=ValueError("bad json")):
            condition = query_ashrae_online(42.651, -73.754, endpoint="https://example.test/ashrae")

        self.assertEqual(condition["lookup_status"], "failed")
        self.assertEqual(condition["failure_reason"], "Invalid ASHRAE response format")

    def test_invalid_design_db_value_returns_explicit_failure_reason(self):
        payload = {"stations": [{"station_name": "BROKEN", "station_id": "BAD", "latitude": 42.7, "longitude": -73.8}]}
        with patch("ashrae_online_lookup._fetch_endpoint", return_value=payload):
            condition = lookup_online_ashrae_design_condition(42.651, -73.754, endpoint="https://example.test/ashrae")

        self.assertEqual(condition["lookup_status"], "failed")
        self.assertEqual(condition["failure_reason"], "ASHRAE online response missing design temperature")

    def test_normalizer_accepts_design_db_max_field(self):
        station = normalize_online_station(
            {
                "name": "ALBANY INTL, NY, USA",
                "wmo": "725180",
                "lat": 42.747,
                "lon": -73.799,
                "design_db_max_C": 44.0,
            },
            42.651,
            -73.754,
        )

        self.assertEqual(station["station_name"], "ALBANY INTL, NY, USA")
        self.assertEqual(station["station_id"], "725180")
        self.assertAlmostEqual(station["design_db_max_C"], 44.0)

    def test_invalid_coordinate_station_is_never_selected(self):
        station = find_nearest_ashrae_station(
            32.700,
            -100.950,
            [
                {
                    "station_name": "INVALID COORDINATE STATION",
                    "station_id": "BAD",
                    "latitude": None,
                    "longitude": None,
                    "design_conditions": {"extreme_annual_db_max_C": 99.0},
                },
                {
                    "station_name": "WINSTON FIELD, TX, USA",
                    "station_id": "722122",
                    "latitude": 32.693,
                    "longitude": -100.951,
                    "design_conditions": {
                        "extreme_annual_db_max_C": 44.0,
                        "basis": "ASHRAE_20_year_extreme_annual_design_condition",
                    },
                },
            ],
        )

        self.assertEqual(station["station_name"], "WINSTON FIELD, TX, USA")


if __name__ == "__main__":
    unittest.main()
