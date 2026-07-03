import csv
import unittest
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from acc_excel_benchmark import compute_acc_excel_benchmark, compute_acc_experimental_hourly_shape, compute_acc_excel_replicated_hourly
from configuration_library_loader import build_solver_input_from_library
from library_solver_adapter import convert_library_input_to_solver_input
from solver import compute_pue_project


class AccExcelBenchmarkTest(unittest.TestCase):
    def _input(self, scenario):
        return convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, scenario)
        )

    @staticmethod
    def _workbook_numeric_cells(sheet_number):
        workbook = Path.home() / "Downloads" / "Annual_PUE_detailed_calculation_JUNO Field.xlsx"
        namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        with ZipFile(workbook) as archive:
            root = ET.fromstring(archive.read(f"xl/worksheets/sheet{sheet_number}.xml"))
        return {
            cell.get("r"): float(value.text)
            for cell in root.findall(f".//{{{namespace}}}c")
            if (value := cell.find(f"{{{namespace}}}v")) is not None
            and value.text not in (None, "")
            and cell.get("t") not in ("s", "str", "inlineStr")
        }

    def test_normal_matches_excel(self):
        output = compute_acc_excel_benchmark(self._input("Normal"))
        self.assertAlmostEqual(output["annual_results"]["annual_average_PUE"], 1.23299755, places=8)
        self.assertEqual(output["annual_results"]["calculation_mode"], "excel_benchmark_compatible")

    def test_failure_matches_excel(self):
        output = compute_acc_excel_benchmark(self._input("Failure"))
        self.assertAlmostEqual(output["annual_results"]["annual_average_PUE"], 1.22622588, places=8)

    def test_auditable_components_and_annual_schema(self):
        output = compute_acc_excel_benchmark(self._input("Normal"))
        annual = output["annual_results"]
        for key in (
            "annual_IT_energy_kWh", "annual_facility_energy_kWh", "annual_acc_energy_kWh",
            "annual_pump_energy_kWh", "annual_indoor_equipment_energy_kWh",
            "annual_engine_radiator_energy_kWh", "annual_it_electrical_loss_kWh",
            "annual_mep_electrical_loss_kWh", "annual_total_cooling_system_energy_kWh",
        ):
            self.assertGreater(annual[key], 0)
        self.assertEqual(len(output["hourly_results"]), 8760)

    def test_dynamic_acc_mode_remains_available(self):
        dynamic = compute_pue_project(self._input("Normal"))
        self.assertNotIn("error", dynamic)
        self.assertNotEqual(dynamic["annual_results"].get("calculation_mode"), "excel_benchmark_compatible")
        self.assertGreater(dynamic["annual_results"]["annual_acc_energy_kWh"], 0)

    def test_hourly_benchmark_uses_weather_and_preserves_annual_acc_energy(self):
        adapted = self._input("Normal")
        adapted["weather"]["hourly_data"]["dry_bulb_C"] = [float(-10 + (hour % 56)) for hour in range(8760)]
        hourly = compute_acc_experimental_hourly_shape(adapted)
        annual_equivalent = compute_acc_excel_benchmark(adapted)
        self.assertNotIn("error", hourly)
        self.assertEqual(len(hourly["hourly_results"]), 8760)
        acc_values = [row["acc_power_kW"] for row in hourly["hourly_results"]]
        self.assertGreater(max(acc_values), min(acc_values))
        target = annual_equivalent["annual_results"]["annual_acc_energy_kWh"]
        actual = hourly["annual_results"]["annual_acc_energy_kWh"]
        self.assertLess(abs(actual - target) / target, 0.005)
        self.assertNotAlmostEqual(
            hourly["annual_results"]["max_hourly_PUE"],
            hourly["annual_results"]["annual_average_PUE"],
            places=6,
        )

    def test_hourly_benchmark_peak_fields_come_from_hourly_results(self):
        adapted = self._input("Failure")
        adapted["weather"]["hourly_data"]["dry_bulb_C"] = [float(-10 + (hour % 56)) for hour in range(8760)]
        output = compute_acc_experimental_hourly_shape(adapted)
        hourly = output["hourly_results"]
        peak_facility = max(hourly, key=lambda row: row["total_facility_power_kW"])
        peak_pue = max(hourly, key=lambda row: row["hourly_PUE"])
        self.assertEqual(output["peak_results"]["peak_hour_index"], peak_facility["hour_index"])
        self.assertEqual(output["peak_results"]["peak_total_facility_power_kW"], peak_facility["total_facility_power_kW"])
        self.assertEqual(output["peak_results"]["peak_PUE_hour_index"], peak_pue["hour_index"])
        self.assertEqual(output["peak_results"]["peak_PUE"], peak_pue["hourly_PUE"])

    def test_experimental_peak_safety_warning(self):
        adapted = self._input("Normal")
        adapted["weather"]["hourly_data"]["dry_bulb_C"] = [float(-10 + (hour % 56)) for hour in range(8760)]
        output = compute_acc_experimental_hourly_shape(adapted)
        annual = output["annual_results"]
        self.assertTrue(annual["acc_peak_power_warning"])
        self.assertGreater(annual["acc_peak_to_scenario_peak_ratio"], 1.10)
        self.assertGreater(annual["max_acc_power_kW"], annual["scenario_peak_acc_power_kW"])
        self.assertTrue(output["warnings"])
        self.assertEqual(output["calculation_mode"], "experimental_acc_hourly_shape")

    def test_albi_normal_triggers_peak_warning_and_preserves_annual_target(self):
        epw = Path(__file__).parent.parent / "input tampelate" / "FRA_LP_Albi-Le.Sequestre.AP.076320_TMYx.2004-2018.epw"
        with epw.open(encoding="utf-8-sig", newline="") as handle:
            dry_bulb = [float(row[6]) for row in list(csv.reader(handle))[8:8768]]
        adapted = self._input("Normal")
        adapted["weather"]["hourly_data"]["dry_bulb_C"] = dry_bulb
        old = compute_acc_excel_benchmark(adapted)
        output = compute_acc_experimental_hourly_shape(adapted)
        annual = output["annual_results"]
        target = old["annual_results"]["annual_acc_energy_kWh"]
        self.assertTrue(annual["acc_peak_power_warning"])
        self.assertAlmostEqual(annual["max_acc_power_kW"], 3615.308717543356, places=6)
        self.assertAlmostEqual(annual["acc_peak_to_scenario_peak_ratio"], 3.3475080717994037, places=9)
        self.assertLess(abs(annual["annual_acc_energy_kWh"] - target) / target, 0.005)

    def test_excel_replicated_hourly_matches_workbook_acc_factor_and_annual_results(self):
        appendix = self._workbook_numeric_cells(5)
        annual_detail = self._workbook_numeric_cells(3)
        electrical = self._workbook_numeric_cells(6)
        dry_bulb = [appendix[f"F{row}"] for row in range(31, 8791)]
        excel_factors = [appendix[f"H{row}"] for row in range(31, 8791)]
        adapted = self._input("Normal")
        adapted["weather"]["hourly_data"]["dry_bulb_C"] = dry_bulb
        output = compute_acc_excel_replicated_hourly(adapted)
        hourly = output["hourly_results"]
        annual = output["annual_results"]
        self.assertEqual(len(hourly), 8760)
        self.assertEqual(hourly[0]["acc_power_kW"], 1080.0 * excel_factors[0])
        self.assertEqual(max(row["acc_power_kW"] for row in hourly), 1080.0 * max(excel_factors))
        self.assertEqual(
            max(abs(row["acc_temperature_power_factor"] - factor) for row, factor in zip(hourly, excel_factors)),
            0.0,
        )
        self.assertAlmostEqual(annual["annual_acc_energy_kWh"], annual_detail["H6"] * 1000.0, places=6)
        self.assertAlmostEqual(annual["annual_facility_energy_kWh"], electrical["S24"] * 1000.0, places=6)
        self.assertAlmostEqual(annual["annual_average_PUE"], electrical["R24"], places=12)

    def test_excel_replicated_peak_is_derived_from_workbook_hourly_factor(self):
        appendix = self._workbook_numeric_cells(5)
        dry_bulb = [appendix[f"F{row}"] for row in range(31, 8791)]
        adapted = self._input("Normal")
        adapted["weather"]["hourly_data"]["dry_bulb_C"] = dry_bulb
        output = compute_acc_excel_replicated_hourly(adapted)
        peak = max(output["hourly_results"], key=lambda row: row["hourly_PUE"])
        self.assertEqual(output["peak_results"]["peak_PUE_hour_index"], peak["hour_index"])
        self.assertEqual(output["peak_results"]["peak_PUE"], peak["hourly_PUE"])
        self.assertAlmostEqual(output["annual_results"]["max_acc_power_kW"], 904.8064204379561, places=9)


if __name__ == "__main__":
    unittest.main()
