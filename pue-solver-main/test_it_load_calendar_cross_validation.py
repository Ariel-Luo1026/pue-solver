import unittest
from pathlib import Path


ROOT = Path(__file__).parent


def function(source, name):
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


class ItLoadCalendarCrossValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = (ROOT / "ui.js").read_text(encoding="utf-8")
        cls.adapter = (ROOT / "import_adapter.js").read_text(encoding="utf-8")

    def test_parser_priority_and_unambiguous_clock_aliases(self):
        block = function(self.adapter, "adaptItExcelRows")
        self.assertLess(block.index("if (timestampColumn)"), block.index("else if (dateColumn || timeColumn)"))
        self.assertLess(block.index("else if (dateColumn || timeColumn)"), block.index("else if (monthColumn"))
        for alias in ("Hour_of_Day", "Hour of Day", "Clock_Hour", "clock_hour"):
            self.assertIn(alias, block)
        self.assertIn('["Hour_of_Year", "Hour of Year", "Hour", "hour_index"]', block)

    def test_raw_columns_remain_paired_for_all_file_types(self):
        block = function(self.adapter, "adaptItExcelRows")
        self.assertIn("rowsRawColumnWithKey", block)
        self.assertNotIn(".filter(", block)
        self.assertIn('ext === ".csv"', self.adapter)

    def test_calendar_metadata_is_canonical(self):
        block = function(self.ui, "validateItLoadCalendar")
        for field in (
            "calendar_ids", "has_explicit_calendar_ids", "calendar_time_basis",
            "calendar_sequence_valid", "calendar_sequence_error", "calendar_validation_warning",
            "calendar_epw_match_valid", "calendar_epw_match_error", "calendar_hour_convention",
        ):
            self.assertIn(field, block)

    def test_8760_8784_and_leap_shape_are_distinguished(self):
        expected = function(self.ui, "expectedAnnualCalendar")
        self.assertIn("hours === 8784", expected)
        self.assertIn("calendarDaysInMonth(month, leap)", expected)
        validator = function(self.ui, "validateItLoadCalendar")
        self.assertIn("isLeapCalendarYear(year) !== (hours === 8784)", validator)
        self.assertIn("calendar chronology mismatch", validator)

    def test_timestamp_date_time_and_component_modes(self):
        block = function(self.ui, "validateItLoadCalendar")
        for basis in ('"timestamp"', '"date_time"', '"month_day_hour"'):
            self.assertIn(basis, block)
        self.assertIn("Date and Time columns must both be supplied", block)
        self.assertIn("Month, Day, and explicit Hour-of-Day columns must all be supplied", block)

    def test_invalid_dates_hours_counts_and_order_are_errors(self):
        block = function(self.ui, "validateItLoadCalendar")
        for text in (
            "Invalid calendar timestamp", "Invalid calendar date", "Calendar timestamp count",
            "ambiguous or inconsistent", "calendar chronology mismatch", "exactly 8760 or 8784",
        ):
            self.assertIn(text, block)
        self.assertNotIn(".sort(", block)

    def test_complete_hour_convention_is_deterministic(self):
        block = function(self.ui, "validateItLoadCalendar")
        self.assertIn('"0_23_clock_hour"', block)
        self.assertIn('"1_24_epw_hour"', block)
        self.assertIn("hasZero && !has24", block)
        self.assertIn("has24 && !hasZero", block)

    def test_epw_comparison_uses_native_calendar_arrays_without_shift(self):
        block = function(self.ui, "validateItCalendarAgainstEpw")
        for field in ("weather.month", "weather.day", "weather.epw_hour"):
            self.assertIn(field, block)
        self.assertIn("calendar alignment mismatch at annual row", block)
        self.assertNotIn(".sort(", block)
        epw = function(self.adapter, "adaptEpw")
        self.assertIn("pushIfNumber(epwHour, num(cols[3]))", epw)

    def test_readiness_blocks_calendar_errors_and_length_mismatch(self):
        block = function(self.ui, "getSimulationReadiness")
        self.assertIn("validateItCalendarAgainstEpw", block)
        self.assertIn("calendar_epw_match_valid !== false", block)
        self.assertIn("itLoadHours === weatherHours", block)

    def test_hour_of_year_and_calendar_validation_both_feed_profile_errors(self):
        block = function(self.ui, "canonicalItLoadProfile")
        self.assertIn("validateItLoadHourSequence", block)
        self.assertIn("validateItLoadCalendar", block)
        self.assertIn("errors.push(sequence.hour_sequence_error)", block)
        self.assertIn("errors.push(calendar.calendar_sequence_error)", block)

    def test_no_calendar_remains_backward_compatible(self):
        block = function(self.ui, "validateItLoadCalendar")
        self.assertIn('calendar_time_basis: "none"', block)
        self.assertIn("calendar_sequence_valid: null", block)
        self.assertIn("Calendar timestamps were not supplied", block)

    def test_ui_and_report_expose_calendar_diagnostics(self):
        for label in (
            "IT Calendar Time Basis", "Calendar Sequence Validation",
            "IT / Weather Calendar Alignment", "Calendar Hour Convention",
        ):
            self.assertIn(label, self.ui)


if __name__ == "__main__":
    unittest.main()
