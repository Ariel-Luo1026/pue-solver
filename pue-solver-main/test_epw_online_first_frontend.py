import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
UI = (ROOT / "ui.js").read_text(encoding="utf-8")


def function_source(name):
    match = re.search(rf"(?:async\s+)?function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", UI)
    if not match:
        raise AssertionError(f"function not found: {name}")
    depth = 0
    for index in range(match.end() - 1, len(UI)):
        if UI[index] == "{":
            depth += 1
        elif UI[index] == "}":
            depth -= 1
            if depth == 0:
                return UI[match.start():index + 1]
    raise AssertionError(f"unterminated function: {name}")


class EpwOnlineFirstFrontendContractTest(unittest.TestCase):
    def test_online_lookup_precedes_any_local_index_search(self):
        source = function_source("autoMatchLocalEpw")
        self.assertLess(source.index("fetchOnlineEpw("), source.index("findNearestLocalEpwByCoordinates("))
        self.assertIn("coordinates.latitude, coordinates.longitude, locationText", source)

    def test_online_result_uses_exact_returned_file_not_generic_nearest_match(self):
        source = function_source("autoMatchLocalEpw")
        self.assertIn("findLocalEpwByFile(onlineResult.epw_file, epwIndex)", source)
        online_branch = source[:source.index("Searching local EPW fallback")]
        self.assertNotIn("findNearestLocalEpwByCoordinates", online_branch)

    def test_online_download_cache_hit_and_fallback_provenance_are_distinct(self):
        source = function_source("autoMatchLocalEpw")
        for value in ("ONLINE_DOWNLOADED", "ONLINE_CACHE_HIT", "LOCAL_FALLBACK"):
            self.assertIn(f"EPW_SELECTION_PROVENANCE.{value}", source)
        apply_source = function_source("applyMatchedEpw")
        self.assertIn("selection_provenance: provenance", apply_source)
        self.assertIn("fallback_reason: fallbackReason", apply_source)
        self.assertIn("Weather Source:", apply_source)
        self.assertIn("Match Distance:", apply_source)
        self.assertIn("hourly weather loaded", apply_source)

    def test_local_cache_only_runs_after_online_failure(self):
        source = function_source("autoMatchLocalEpw")
        fallback = source.index("Searching local EPW fallback")
        local_match = source.index("findNearestLocalEpwByCoordinates")
        self.assertGreater(local_match, fallback)
        self.assertIn("fallbackReason: onlineFailureReason", source)

    def test_annual_weather_length_contract_is_unchanged(self):
        source = function_source("applyMatchedEpw")
        self.assertIn("weatherHours === 8760 || weatherHours === 8784", source)

    def test_manual_weather_upload_has_distinct_provenance(self):
        source = function_source("handleStandardFile")
        self.assertIn("selection_provenance: EPW_SELECTION_PROVENANCE.MANUAL", source)

    def test_chicago_and_dallas_cached_files_cannot_short_circuit_online(self):
        source = function_source("autoMatchLocalEpw")
        online_call = source.index("fetchOnlineEpw(coordinates.latitude, coordinates.longitude, locationText)")
        local_index = source.index("findNearestLocalEpwByCoordinates")
        self.assertLess(online_call, local_index)
        self.assertNotIn("Columbus", source)
        self.assertNotIn("Dallas", source)


if __name__ == "__main__":
    unittest.main()
