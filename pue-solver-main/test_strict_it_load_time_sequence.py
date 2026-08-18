import unittest
from pathlib import Path


ROOT = Path(__file__).parent


def javascript_function(source, name):
    start = source.index(f"function {name}")
    brace = source.index("{", source.index(")", start))
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError(name)


class StrictItLoadTimeSequenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = (ROOT / "ui.js").read_text(encoding="utf-8")
        cls.adapter = (ROOT / "import_adapter.js").read_text(encoding="utf-8")
        cls.validator = javascript_function(cls.ui, "validateItLoadHourSequence")
        cls.canonical = javascript_function(cls.ui, "canonicalItLoadProfile")

    def test_validator_requires_exact_row_order_sequence(self):
        for token in (
            "Number.isInteger(found)", "found !== expected", "index + 1",
            "firstDuplicate", "firstMissing", "duplicate Hour_of_Year",
            "missing Hour_of_Year", "Expected Hour ${expected} but found Hour ${found}",
        ):
            self.assertIn(token, self.validator)
        self.assertNotIn(".sort(", self.validator)

    def test_valid_explicit_8760_and_8784_are_supported(self):
        self.assertIn("Array.from({ length: hours }", self.validator)
        self.assertIn("hour_sequence_valid: !error", self.validator)
        self.assertIn("[8760, 8784].includes(kw.length)", self.canonical)

    def test_invalid_boundaries_blank_text_and_noninteger_are_rejected(self):
        self.assertIn('String(value).trim() === ""', self.validator)
        self.assertIn("Number.isFinite(number)", self.validator)
        self.assertIn("hour identifiers must be integers", self.validator)
        self.assertIn("errors.push(sequence.hour_sequence_error)", self.canonical)

    def test_row_order_mode_is_valid_with_warning(self):
        self.assertIn('time_basis: "row_order_only"', self.validator)
        self.assertIn("chronological alignment relies on file row order", self.validator)
        self.assertIn("has_explicit_hour_ids: false", self.validator)

    def test_canonical_metadata_and_percent_conversion_are_preserved(self):
        for field in ("hour_ids", "has_explicit_hour_ids", "time_basis", "hour_sequence_valid", "hour_sequence_error"):
            self.assertIn(field, self.canonical)
        percent = javascript_function(self.ui, "canonicalItLoadFromPercent")
        self.assertIn("designItKw * value / 100", percent)
        self.assertIn("...timeOptions", percent)

    def test_aliases_csv_and_calendar_extension_preserve_hour_aliases(self):
        for alias in ("Hour_of_Year", "Hour of Year", '"Hour"', "hour_index"):
            self.assertIn(alias, self.adapter)
        self.assertIn('ext === ".csv"', self.adapter)
        adapter = javascript_function(self.adapter, "adaptItExcelRows")
        for calendar_field in ('"Date"', '"Time"', '"Timestamp"', '"Month"', '"Day"'):
            self.assertIn(calendar_field, adapter)

    def test_adapter_preserves_rows_instead_of_filtering_columns(self):
        adapter = javascript_function(self.adapter, "adaptItExcelRows")
        self.assertIn("rowsRawColumnWithKey", adapter)
        self.assertNotIn(".filter(", adapter)
        self.assertNotIn(".sort(", adapter)

    def test_readiness_requires_valid_profile_and_matching_weather(self):
        block = javascript_function(self.ui, "getSimulationReadiness")
        self.assertIn("profileValid", block)
        self.assertIn("itLoadHours === weatherHours", block)

    def test_fallback_gets_generated_hour_basis(self):
        load = javascript_function(self.ui, "loadSelectedConfigurationLibrary")
        self.assertIn('timeBasis: "generated_hour_of_year"', load)
        self.assertIn("packagedHourIds", load)


if __name__ == "__main__":
    unittest.main()
