import unittest
from pathlib import Path


class UnifiedItLoadProfileFrontendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = Path(__file__).with_name("ui.js").read_text(encoding="utf-8")
        cls.adapter = Path(__file__).with_name("import_adapter.js").read_text(encoding="utf-8")

    def test_manifest_fallback_matches_python_90_percent_policy(self):
        block = self._function("defaultConfigurationLibraryItLoad")
        self.assertIn("Array(hours).fill(90)", block)
        self.assertIn("Array(hours).fill(0.9)", block)
        self.assertIn("Compatibility Default — 90% Constant", block)

    def test_canonical_profile_rejects_bad_lengths_nan_and_negative_values(self):
        block = self._function("canonicalItLoadProfile")
        self.assertIn("[8760, 8784].includes(kw.length)", block)
        self.assertIn("!Number.isFinite(value)", block)
        self.assertIn("value < 0", block)
        self.assertIn("value > designItKw", block)
        self.assertNotIn("Math.min(designItKw", block)

    def test_user_upload_is_project_level_and_has_highest_precedence(self):
        load = self._function("loadSelectedConfigurationLibrary")
        self.assertLess(load.index("projectItLoadProfileOverride"), load.index(": packagedProfile"))
        upload = self._function("handleStandardFile")
        self.assertIn('sourceType: "user_uploaded"', upload)
        self.assertIn("configurationLibraryData.it_load = projectItLoadProfileOverride", upload)

    def test_percent_profiles_recompute_and_kw_profiles_remain_absolute(self):
        block = self._function("refreshCanonicalItLoadForCapacity")
        self.assertIn('profile.source_basis === "percent"', block)
        self.assertIn("hourlyKw: profile.hourly_it_load_kW", block)

    def test_direct_payload_consumes_only_canonical_kw_array(self):
        block = self._function("buildGenericConfigurationLibraryPayload")
        self.assertIn("resolvedItProfile?.hourly_it_load_kW", block)
        self.assertIn("...resolvedItProfile", block)
        self.assertNotIn("percentages.map(percent => designItLoadKw", block)

    def test_profile_and_weather_must_have_identical_annual_lengths(self):
        block = self._function("getSimulationReadiness")
        self.assertIn("[8760, 8784].includes(itLoadHours)", block)
        self.assertIn("itLoadHours === weatherHours", block)

    def test_supported_engineering_column_aliases(self):
        for alias in ("IT Load (kW)", "IT Load (%)", "IT %", "Load Ratio"):
            self.assertIn(alias, self.adapter)

    def test_peak_design_logic_is_not_profile_average(self):
        self.assertNotIn("peak_design_it_load_kW: resolvedItProfile", self.ui)

    @classmethod
    def _function(cls, name):
        start = cls.ui.index(f"function {name}")
        brace = cls.ui.index("{", cls.ui.index(")", start))
        depth = 0
        for index in range(brace, len(cls.ui)):
            if cls.ui[index] == "{":
                depth += 1
            elif cls.ui[index] == "}":
                depth -= 1
                if depth == 0:
                    return cls.ui[start:index + 1]
        raise AssertionError(name)


if __name__ == "__main__":
    unittest.main()
