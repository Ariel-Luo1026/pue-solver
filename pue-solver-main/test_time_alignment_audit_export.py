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


class TimeAlignmentAuditExportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = (ROOT / "ui.js").read_text(encoding="utf-8")
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.builder = function(cls.ui, "buildTimeAlignmentAudit")

    def test_one_audit_record_is_created_per_canonical_kw_value(self):
        self.assertIn("profile.hourly_it_load_kW.map((loadKw, index)", self.builder)
        self.assertNotIn(".sort(", self.builder)
        self.assertNotIn("validateItLoadCalendar", self.builder)

    def test_display_row_and_internal_index_mapping(self):
        self.assertIn("annual_row: index + 1", self.builder)
        self.assertIn("internal_index: index", self.builder)
        lookup = function(self.ui, "inspectTimeAlignmentAuditRow")
        self.assertIn("audit.rows[annualRow - 1]", lookup)

    def test_uploaded_generated_and_row_order_hour_provenance(self):
        self.assertIn("profile.has_explicit_hour_ids === true", self.builder)
        self.assertIn('profile.time_basis === "generated_hour_of_year"', self.builder)
        self.assertIn('"GENERATED"', self.builder)
        self.assertIn('"NOT PROVIDED"', self.builder)
        self.assertIn('"WARNING — ROW ORDER ONLY"', self.builder)

    def test_calendar_and_epw_source_values_are_exposed(self):
        for token in (
            "profile.calendar_ids?.[index]", "calendar?.month", "calendar?.day", "calendar?.hour_of_day",
            "weather.month", "weather.day", "weather.epw_hour", '"1_24_epw_hour"',
        ):
            self.assertIn(token, self.builder)

    def test_existing_hour_convention_is_reported_not_revalidated(self):
        display = function(self.ui, "alignmentTimestampDisplay")
        self.assertIn('convention === "0_23_clock_hour"', display)
        self.assertIn("calendar.hour_of_day", display)
        self.assertNotIn("validate", display)

    def test_original_input_and_canonical_solver_kw_are_both_exposed(self):
        self.assertIn('profile.source_basis === "percent"', self.builder)
        self.assertIn("profile.hourly_it_load_percent?.[index]", self.builder)
        self.assertIn("it_load_kW: Number(loadKw)", self.builder)
        self.assertNotIn("design_it_load_kW *", self.builder)

    def test_alignment_status_modes_follow_existing_metadata(self):
        for status in (
            "PASS — HOUR ID ONLY", "PASS — CALENDAR", "PASS — GENERATED HOUR ID",
            "WARNING — ROW ORDER ONLY", "NOT CHECKED", "ERROR",
        ):
            self.assertIn(status, self.builder)

    def test_audit_is_cached_by_profile_weather_and_canonical_arrays(self):
        cache = function(self.ui, "getTimeAlignmentAudit")
        self.assertIn("timeAlignmentAuditCache", cache)
        self.assertIn("resolvedProfile?.hourly_it_load_kW", cache)
        self.assertIn("weatherData.epw_hour", cache)

    def test_csv_has_deterministic_required_columns(self):
        for column in (
            "Annual_Row", "Internal_Index", "IT_Hour_ID", "IT_Time_Basis", "IT_Calendar_Time_Basis",
            "IT_Timestamp", "IT_Month", "IT_Day", "IT_Hour", "IT_Hour_Convention", "EPW_Month",
            "EPW_Day", "EPW_Hour", "EPW_Hour_Convention", "IT_Load_Input", "IT_Load_Input_Unit",
            "IT_Load_kW", "Hour_ID_Status", "Calendar_Status", "Weather_Alignment_Status",
            "Overall_Alignment_Status",
        ):
            self.assertIn(f'"{column}"', self.ui)
        serializer = function(self.ui, "timeAlignmentAuditCsv")
        self.assertIn("TIME_ALIGNMENT_CSV_COLUMNS", serializer)
        self.assertIn('join("\\r\\n")', serializer)

    def test_csv_safety_and_filename(self):
        safety = function(self.ui, "csvSafeCell")
        self.assertIn("/^[=+\\-@]/", safety)
        self.assertIn("replace(/\"/g", safety)
        exporter = function(self.ui, "exportTimeAlignmentAuditCsv")
        self.assertIn("IT_Weather_Time_Alignment_Audit.csv", exporter)
        self.assertIn('text/csv;charset=utf-8', exporter)

    def test_viewer_is_compact_first_and_last_five(self):
        render = function(self.ui, "renderTimeAlignmentAudit")
        self.assertIn("audit.rows.slice(0, 5)", render)
        self.assertIn("audit.rows.slice(-5)", render)
        self.assertNotIn("audit.rows.map", render)
        self.assertIn('id="timeAlignmentAuditPanel"', self.html)
        self.assertIn('id="timeAlignmentAuditRowInput"', self.html)
        self.assertIn('id="btnExportTimeAlignmentCsv"', self.html)

    def test_html_report_contains_summary_not_full_rows(self):
        report = function(self.ui, "buildHtmlReportFromSections")
        self.assertIn("Annual Data Alignment", report)
        self.assertIn("Appendix C — IT / Weather Alignment", report)
        self.assertIn("Full CSV Audit", report)
        self.assertIn("alignmentFirst", report)
        self.assertIn("alignmentLast", report)
        self.assertNotIn("alignmentAudit.rows.map", report)


if __name__ == "__main__":
    unittest.main()
