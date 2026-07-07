import ast
import copy
import unittest
from pathlib import Path

from calculators.legacy_result_mapper import (
    map_legacy_annual_result,
    map_legacy_hourly_result,
    map_legacy_result,
)
from calculators.models import AnnualResult, CalculationResult, HourlyResult


class LegacyResultMapperTests(unittest.TestCase):
    def test_hourly_result_mapping_works(self):
        row = {
            "hour_index": 7,
            "IT_load_kW": 4400.0,
            "dry_bulb_C": 32.0,
            "wet_bulb_C": 24.0,
            "cooling_power_kW": 900.0,
            "pump_power_kW": 50.0,
            "airflow_power_kW": 12.0,
            "electrical_loss_kW": 8.0,
            "auxiliary_power_kW": 4.0,
            "total_facility_power_kW": 5374.0,
            "hourly_PUE": 1.22136,
            "equipment_results": {"acc_unit": {"power_kw": 900.0}},
            "warnings": ["sample warning"],
        }

        mapped = map_legacy_hourly_result(row)

        self.assertIsInstance(mapped, HourlyResult)
        self.assertEqual(mapped.hour_index, 7)
        self.assertEqual(mapped.it_load_kw, 4400.0)
        self.assertEqual(mapped.outdoor_dry_bulb_c, 32.0)
        self.assertEqual(mapped.outdoor_wet_bulb_c, 24.0)
        self.assertEqual(mapped.cooling_power_kw, 900.0)
        self.assertEqual(mapped.pump_power_kw, 50.0)
        self.assertEqual(mapped.fan_power_kw, 12.0)
        self.assertEqual(mapped.electrical_loss_kw, 8.0)
        self.assertEqual(mapped.auxiliary_power_kw, 4.0)
        self.assertEqual(mapped.total_facility_power_kw, 5374.0)
        self.assertEqual(mapped.hourly_pue, 1.22136)
        self.assertEqual(mapped.equipment_results["acc_unit"]["power_kw"], 900.0)
        self.assertEqual(mapped.warnings, ["sample warning"])
        self.assertEqual(mapped.metadata["source"], "legacy_solver")

    def test_annual_result_mapping_works(self):
        annual = {
            "annual_average_PUE": 1.23,
            "annual_IT_energy_kWh": 34690.0,
            "annual_facility_energy_kWh": 42772.0,
            "annual_cooling_energy_kWh": 5016.0,
            "annual_chiller_energy_kWh": 0.0,
            "annual_acc_energy_kWh": 1009.0,
            "annual_pump_energy_kWh": 54.0,
            "annual_terminal_fan_energy_kWh": 72.0,
            "annual_electrical_loss_kWh": 108.0,
            "annual_auxiliary_energy_kWh": 12.0,
            "peak_total_facility_power_kW": 5900.0,
            "min_hourly_PUE": 1.1,
            "max_hourly_PUE": 1.4,
            "monthly_average_PUE": [1.2] * 12,
        }

        mapped = map_legacy_annual_result(annual)

        self.assertIsInstance(mapped, AnnualResult)
        self.assertEqual(mapped.annual_average_pue, 1.23)
        self.assertEqual(mapped.annual_it_energy_kwh, 34690.0)
        self.assertEqual(mapped.annual_facility_energy_kwh, 42772.0)
        self.assertEqual(mapped.annual_cooling_energy_kwh, 5016.0)
        self.assertEqual(mapped.annual_chiller_energy_kwh, 0.0)
        self.assertEqual(mapped.annual_heat_rejection_energy_kwh, 1009.0)
        self.assertEqual(mapped.annual_pump_energy_kwh, 54.0)
        self.assertEqual(mapped.annual_fan_energy_kwh, 72.0)
        self.assertEqual(mapped.annual_electrical_loss_kwh, 108.0)
        self.assertEqual(mapped.annual_auxiliary_energy_kwh, 12.0)
        self.assertEqual(mapped.peak_total_facility_power_kw, 5900.0)
        self.assertEqual(mapped.min_hourly_pue, 1.1)
        self.assertEqual(mapped.max_hourly_pue, 1.4)
        self.assertEqual(mapped.monthly_average_pue, [1.2] * 12)
        self.assertEqual(mapped.equipment_energy_breakdown["acc_unit"], 1009.0)
        self.assertEqual(mapped.equipment_energy_breakdown["pump"], 54.0)
        self.assertEqual(mapped.equipment_energy_breakdown["fan"], 72.0)

    def test_full_result_mapping_returns_calculation_result(self):
        result = {
            "annual_results": {
                "annual_average_PUE": 1.23,
                "annual_IT_energy_kWh": 34690.0,
            },
            "hourly_results": [
                {"hour": 1, "IT_load_kW": 4000.0, "hourly_PUE": 1.2},
                {"hour": 2, "IT_load_kW": 4100.0, "hourly_PUE": 1.21},
            ],
            "report_context": {"project": "JUNO"},
            "warnings": ["legacy warning"],
            "errors": [],
            "solver_version": "legacy-test",
        }

        mapped = map_legacy_result(result, calculator_id="acc_calculator")

        self.assertIsInstance(mapped, CalculationResult)
        self.assertIsInstance(mapped.annual_results, AnnualResult)
        self.assertTrue(all(isinstance(row, HourlyResult) for row in mapped.hourly_results))
        self.assertEqual(len(mapped.hourly_results), 2)
        self.assertEqual(mapped.report_context, {"project": "JUNO"})
        self.assertEqual(mapped.warnings, ["legacy warning"])
        self.assertEqual(mapped.execution_metadata["source"], "legacy_solver")
        self.assertEqual(mapped.solver_version, "legacy-test")
        self.assertEqual(mapped.calculator_id, "acc_calculator")

    def test_missing_fields_use_defaults(self):
        hourly = map_legacy_hourly_result({})
        annual = map_legacy_annual_result({})
        full = map_legacy_result({})

        self.assertIsNone(hourly.hour_index)
        self.assertIsNone(hourly.hourly_pue)
        self.assertEqual(hourly.equipment_results, {})
        self.assertIsNone(annual.annual_average_pue)
        self.assertEqual(annual.monthly_average_pue, [])
        self.assertEqual(full.hourly_results, [])
        self.assertIsInstance(full.annual_results, AnnualResult)

    def test_input_dictionaries_are_not_modified(self):
        result = {
            "annual_results": {
                "annual_average_PUE": 1.23,
                "monthly_average_PUE": [1.2] * 12,
            },
            "hourly_results": [
                {
                    "hour": 1,
                    "equipment_results": {"acc_unit": {"power_kw": 900.0}},
                }
            ],
            "report_context": {"nested": {"value": 1}},
        }
        original = copy.deepcopy(result)

        mapped = map_legacy_result(result)
        mapped.report_context["nested"]["value"] = 99
        mapped.hourly_results[0].equipment_results["acc_unit"]["power_kw"] = 0.0

        self.assertEqual(result, original)

    def test_mapper_does_not_import_solver(self):
        mapper_path = Path(__file__).with_name("calculators") / "legacy_result_mapper.py"
        parsed = ast.parse(mapper_path.read_text(encoding="utf-8"))
        imported_modules = set()
        for node in ast.walk(parsed):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

        self.assertNotIn("solver", imported_modules)


if __name__ == "__main__":
    unittest.main()
