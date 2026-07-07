import ast
import unittest
from pathlib import Path

from calculators.models import AnnualResult, make_annual_result


class AnnualResultModelTest(unittest.TestCase):
    def test_annual_result_instantiates(self):
        result = AnnualResult(
            annual_average_pue=1.23,
            annual_it_energy_kwh=34690.0,
            annual_facility_energy_kwh=42772.0,
        )
        self.assertEqual(result.annual_average_pue, 1.23)
        self.assertEqual(result.annual_it_energy_kwh, 34690.0)
        self.assertEqual(result.equipment_energy_breakdown, {})
        self.assertEqual(result.monthly_average_pue, [])

    def test_make_annual_result_returns_annual_result(self):
        result = make_annual_result(annual_cooling_energy_kwh=5016.0)
        self.assertIsInstance(result, AnnualResult)
        self.assertEqual(result.annual_cooling_energy_kwh, 5016.0)

    def test_safe_defaults_work(self):
        result = make_annual_result()
        self.assertIsNone(result.annual_average_pue)
        self.assertIsNone(result.peak_total_facility_power_kw)
        self.assertEqual(result.equipment_energy_breakdown, {})
        self.assertEqual(result.monthly_average_pue, [])
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.metadata, {})

    def test_equipment_energy_breakdown_supports_per_equipment_energy(self):
        result = make_annual_result(
            equipment_energy_breakdown={
                "acc_unit": 1009.0,
                "pump": 54.0,
                "electrical_distribution": 108.0,
            }
        )
        self.assertEqual(result.equipment_energy_breakdown["acc_unit"], 1009.0)
        self.assertEqual(result.equipment_energy_breakdown["pump"], 54.0)

    def test_monthly_average_pue_supports_12_values(self):
        monthly = [1.2 + index * 0.001 for index in range(12)]
        result = make_annual_result(monthly_average_pue=monthly)
        self.assertEqual(len(result.monthly_average_pue), 12)
        self.assertEqual(result.monthly_average_pue, monthly)

    def test_models_do_not_import_solver(self):
        source = (Path(__file__).resolve().parent / "calculators" / "models.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.append(node.module)
        self.assertNotIn("solver", imported_modules)


if __name__ == "__main__":
    unittest.main()
