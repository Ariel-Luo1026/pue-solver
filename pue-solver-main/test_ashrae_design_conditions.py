import unittest
from unittest.mock import patch

from urllib.error import HTTPError

from ashrae_online_lookup import (
    ASHRAE_METEO_PLACES_ENDPOINT,
    ASHRAE_METEO_PARAMETERS_ENDPOINT,
    lookup_online_ashrae_design_condition,
    normalize_online_station,
    normalize_ashrae_url,
    query_ashrae_online,
)
from ashrae_design_conditions import (
    find_nearest_ashrae_station,
    get_peak_design_condition,
    haversine_distance_km,
    load_design_condition_stations,
)
from ashrae_proxy import query_ashrae_design_condition


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
        with patch.dict("ashrae_online_lookup.environ", {"ASHRAE_ONLINE_LOOKUP_DISABLED": "1"}, clear=True):
            condition = get_peak_design_condition(32.693, -100.951)

        self.assertEqual(condition["source"], "ASHRAE_local_cache")
        self.assertEqual(condition["lookup_status"], "failed")
        self.assertEqual(condition["failure_reason"], "online lookup disabled")
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

    def test_custom_online_endpoint_lookup_matches_albany_for_upstate_new_york_coordinates(self):
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
        self.assertEqual(online["lookup_method"], "ASHRAE_API")
        self.assertEqual(online["station_name"], "ALBANY INTL, NY, USA")
        self.assertEqual(online["station_id"], "725180")
        self.assertLess(online["distance_km"], 20.0)
        self.assertAlmostEqual(online["design_db_max_C"], 44.0)
        self.assertEqual(online["design_condition_basis"], "20-year Extreme Annual Design Condition")

    def test_ashrae_meteo_workflow_matches_albany_for_upstate_new_york_coordinates(self):
        places_payload = {
            "meteo_stations": [
                {
                    "wmo": "725180",
                    "place": "ALBANY INTL, NY, USA",
                    "lat": "42.747",
                    "long": "-73.799",
                    "elev": "85",
                    "tt": "0.0018258372235745843",
                }
            ]
        }
        parameters_payload = {
            "meteo_stations": [
                {
                    "place": "ALBANY INTL, NY, USA",
                    "wmo": "725180",
                    "lat": "42.747",
                    "long": "-73.799",
                    "n-year_return_period_values_of_extreme_DB_20_max": "37.1",
                    "n-year_return_period_values_of_extreme_DB_20_min": "-27.0",
                }
            ]
        }
        with patch("ashrae_online_lookup._fetch_ashrae_meteo_places", return_value=places_payload), patch(
            "ashrae_online_lookup._fetch_ashrae_meteo_parameters",
            return_value=parameters_payload,
        ):
            online = query_ashrae_online(42.651, -73.754)

        self.assertEqual(online["source"], "ASHRAE_online")
        self.assertEqual(online["lookup_status"], "success")
        self.assertEqual(online["lookup_method"], "ASHRAE_web")
        self.assertEqual(online["lookup_endpoint"], ASHRAE_METEO_PARAMETERS_ENDPOINT)
        self.assertEqual(online["station_name"], "ALBANY INTL, NY, USA")
        self.assertEqual(online["station_id"], "725180")
        self.assertLess(online["distance_km"], 20.0)
        self.assertAlmostEqual(online["design_db_max_C"], 37.1)
        self.assertEqual(online["design_condition_basis"], "20-year Extreme Annual Design Condition")
        diagnostics = online["ashrae_raw_diagnostics"]
        self.assertEqual(diagnostics["request_places"]["keys"], ["meteo_stations"])
        self.assertIn("wmo", diagnostics["request_places"]["first_meteo_station_keys"])
        self.assertEqual(diagnostics["request_meteo_parametres"]["keys"], ["meteo_stations"])
        self.assertIn(
            "n-year_return_period_values_of_extreme_DB_20_max",
            diagnostics["request_meteo_parametres"]["first_meteo_station_keys"],
        )

    def test_peak_design_condition_uses_online_result_when_provider_succeeds(self):
        with patch(
            "ashrae_design_conditions.lookup_online_ashrae_design_condition",
            return_value={
                "source": "ASHRAE_online",
                "lookup_provider": "ASHRAE_online",
                "lookup_status": "success",
                "failure_reason": "",
                "lookup_method": "ASHRAE_web",
                "lookup_endpoint": ASHRAE_METEO_PARAMETERS_ENDPOINT,
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
        self.assertEqual(condition["lookup_method"], "ASHRAE_web")
        self.assertEqual(condition["lookup_endpoint"], ASHRAE_METEO_PARAMETERS_ENDPOINT)
        self.assertEqual(condition["station_name"], "ALBANY INTL, NY, USA")
        self.assertEqual(condition["station_id"], "725180")
        self.assertAlmostEqual(condition["design_db_max_C"], 44.0)

    def test_online_failure_rejects_distant_local_json_fallback(self):
        with patch(
            "ashrae_design_conditions.lookup_online_ashrae_design_condition",
            return_value={
                "lookup_status": "failed",
                "failure_reason": "network request failed",
                "source": "ASHRAE_online",
                "lookup_method": "ASHRAE_web",
            },
        ):
            condition = get_peak_design_condition(42.651, -73.754)

        self.assertEqual(condition["source"], "ASHRAE_online")
        self.assertEqual(condition["lookup_status"], "failed")
        self.assertEqual(condition["failure_reason"], "network request failed")
        self.assertEqual(condition["online_status"], "failed")
        self.assertEqual(condition["fallback_status"], "no_valid_nearby_ASHRAE_cache_station")
        self.assertEqual(condition["station_name"], "No valid nearby ASHRAE cache station")
        self.assertEqual(condition["station_id"], "")
        self.assertIsNone(condition["extreme_db_max_C"])

    def test_online_failure_allows_nearby_local_json_fallback(self):
        with patch(
            "ashrae_design_conditions.lookup_online_ashrae_design_condition",
            return_value={
                "lookup_status": "failed",
                "failure_reason": "network request failed",
                "source": "ASHRAE_online",
                "lookup_method": "ASHRAE_web",
            },
        ):
            condition = get_peak_design_condition(32.693, -100.951)

        self.assertEqual(condition["source"], "ASHRAE_local_cache")
        self.assertEqual(condition["lookup_status"], "failed")
        self.assertEqual(condition["failure_reason"], "network request failed")
        self.assertEqual(condition["fallback_status"], "ASHRAE_local_cache")
        self.assertEqual(condition["station_name"], "WINSTON FIELD, TX, USA")
        self.assertEqual(condition["station_id"], "722122")
        self.assertLess(condition["station_distance_km"], 1.0)

    def test_malformed_endpoint_is_normalized_to_https(self):
        self.assertEqual(
            normalize_ashrae_url("ashrae-meteo.info/v3.0/request_places.php"),
            ASHRAE_METEO_PLACES_ENDPOINT,
        )
        self.assertEqual(
            normalize_ashrae_url("v3.0/request_places.php"),
            ASHRAE_METEO_PLACES_ENDPOINT,
        )
        self.assertEqual(
            normalize_ashrae_url(None),
            ASHRAE_METEO_PLACES_ENDPOINT,
        )

    def test_custom_endpoint_is_normalized_before_fetch(self):
        payload = {
            "stations": [
                {
                    "station": "ALBANY INTL, NY, USA",
                    "id": "725180",
                    "station_latitude": 42.747,
                    "station_longitude": -73.799,
                    "design_db_max_C": 37.1,
                }
            ]
        }
        with patch("ashrae_online_lookup._fetch_endpoint", return_value=payload) as fetch:
            online = query_ashrae_online(42.651, -73.754, endpoint="ashrae-meteo.info/v3.0/request_places.php")

        self.assertEqual(fetch.call_args.args[2], ASHRAE_METEO_PLACES_ENDPOINT)
        self.assertEqual(online["lookup_status"], "success")

    def test_local_proxy_endpoint_is_identified_as_proxy_method(self):
        payload = {
            "station_name": "ALBANY INTL, NY, USA",
            "station_id": "725180",
            "latitude": 42.747,
            "longitude": -73.799,
            "distance_km": 10.8,
            "design_db_max_C": 37.1,
            "source": "ASHRAE_online_proxy",
            "lookup_provider": "ASHRAE_online_proxy",
            "lookup_method": "ASHRAE_proxy",
        }
        with patch("ashrae_online_lookup._fetch_endpoint", return_value=payload):
            online = query_ashrae_online(
                42.651,
                -73.754,
                endpoint="http://127.0.0.1:8011/api/ashrae_design_condition",
            )

        self.assertEqual(online["lookup_status"], "success")
        self.assertEqual(online["lookup_method"], "ASHRAE_proxy")
        self.assertEqual(online["lookup_provider"], "ASHRAE_online_proxy")
        self.assertEqual(online["station_name"], "ALBANY INTL, NY, USA")
        self.assertEqual(online["station_id"], "725180")
        self.assertLess(online["distance_km"], 20.0)
        self.assertAlmostEqual(online["design_db_max_C"], 37.1)

    def test_proxy_query_normalizes_albany_online_result(self):
        with patch(
            "ashrae_proxy.query_ashrae_online",
            return_value={
                "source": "ASHRAE_online",
                "lookup_status": "success",
                "failure_reason": "",
                "station_name": "ALBANY INTL, NY, USA",
                "station_id": "725180",
                "station_latitude": 42.747,
                "station_longitude": -73.799,
                "distance_km": 10.8,
                "design_db_max_C": 37.1,
                "extreme_db_max_C": 37.1,
                "temperature_basis": "ASHRAE_20_year_extreme_annual_design_condition",
            },
        ):
            condition = query_ashrae_design_condition(42.651, -73.754)

        self.assertEqual(condition["source"], "ASHRAE_online_proxy")
        self.assertEqual(condition["lookup_provider"], "ASHRAE_online_proxy")
        self.assertEqual(condition["lookup_method"], "ASHRAE_proxy")
        self.assertEqual(condition["lookup_status"], "success")
        self.assertEqual(condition["online_status"], "success")
        self.assertEqual(condition["fallback_status"], "not_used")
        self.assertEqual(condition["station_name"], "ALBANY INTL, NY, USA")
        self.assertEqual(condition["station_id"], "725180")
        self.assertLess(condition["distance_km"], 20.0)
        self.assertAlmostEqual(condition["design_db_max_C"], 37.1)

    def test_disabled_online_lookup_returns_no_online_station(self):
        with patch.dict("ashrae_online_lookup.environ", {"ASHRAE_ONLINE_LOOKUP_DISABLED": "1"}, clear=True):
            condition = lookup_online_ashrae_design_condition(42.651, -73.754, endpoint=None)

        self.assertEqual(condition["lookup_status"], "failed")
        self.assertEqual(condition["failure_reason"], "online lookup disabled")
        self.assertEqual(condition["lookup_method"], "ASHRAE_web")

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

    def test_normalizer_accepts_raw_ashrae_meteo_field_names(self):
        station = normalize_online_station(
            {
                "place": "ALBANY INTL, NY, USA",
                "wmo": "725180",
                "lat": "42.747",
                "long": "-73.799",
                "n-year_return_period_values_of_extreme_DB_20_max": "37.1",
            },
            42.651,
            -73.754,
        )

        self.assertEqual(station["station_name"], "ALBANY INTL, NY, USA")
        self.assertEqual(station["station_id"], "725180")
        self.assertLess(station["distance_km"], 20.0)
        self.assertAlmostEqual(station["design_db_max_C"], 37.1)

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
