import re
import unittest
from pathlib import Path


UI = (Path(__file__).parent / "ui.js").read_text(encoding="utf-8")


def function_source(name):
    match = re.search(rf"function\s+{re.escape(name)}\s*\([^)]*\)\s*{{", UI)
    if not match:
        raise AssertionError(f"Missing function: {name}")
    depth = 0
    quote = None
    escaped = False
    for index in range(match.end() - 1, len(UI)):
        char = UI[index]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif quote:
            if char == quote:
                quote = None
        elif char in "'\"`":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return UI[match.start():index + 1]
    raise AssertionError(f"Unclosed function: {name}")


class MonthlyPueChartAxisTest(unittest.TestCase):
    def test_monthly_pue_chart_uses_explicit_truncated_axis(self):
        report = function_source("buildHtmlReportFromSections")
        monthly_call = report[report.index('"Monthly Average PUE"'):]
        self.assertIn("yMin: 1.00", monthly_call)
        self.assertIn("Math.max(1.25", monthly_call)
        self.assertIn("Math.ceil(Math.max(...monthlyPue.map(row => Number(row.average_pue))) * 20) / 20", monthly_call)
        self.assertIn("yTickStep: 0.05", monthly_call)
        self.assertIn("yTickDigits: 2", monthly_call)

    def test_bar_chart_defaults_remain_zero_based_for_other_charts(self):
        chart = function_source("svgBarChart")
        self.assertIn("Number(opts.yMin) : 0", chart)
        self.assertIn("opts.yTickStep", chart)
        report = function_source("buildHtmlReportFromSections")
        energy_call = report[report.index("const energyChart"):report.index("const annualResultCharts")]
        self.assertNotIn("yMin", energy_call)
        self.assertNotIn("yMax", energy_call)
        self.assertNotIn("yTickStep", energy_call)

    def test_monthly_values_and_aggregation_are_not_transformed(self):
        report = function_source("buildHtmlReportFromSections")
        self.assertIn("value: row.average_pue", report)
        monthly_builder = function_source("buildMonthlyPueData")
        self.assertIn("average_pue: facilityEnergy / itEnergy", monthly_builder)


if __name__ == "__main__":
    unittest.main()
