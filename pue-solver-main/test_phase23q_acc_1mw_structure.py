import contextlib
import hashlib
import io
import json
import unittest
from pathlib import Path

from acc_v2_curve_lookup import lookup_acc_curve
from acc_v2_curve_reader import read_acc_v2_equipment_curves
from configuration_library_loader import (
    _records,
    build_solver_input_from_library,
    read_xlsx_sheets,
)
from library_solver_adapter import convert_library_input_to_solver_input
from solver import compute_pue_project


LIBRARY = Path(__file__).resolve().parent.parent / "Configuration Library"


class Phase23QAcc1MwStructureTests(unittest.TestCase):
    ACC_HASHES = {
        "ACC_1MW_GRID_CDU": "39511bdb44bf8c35e7e4c845175d18a49bcc3104a27a2db6d7f99ebde8451f56",
        "ACC_1MW_GASENGINE_CDU": "60b2455d157e782c7e82c235496356d6d402b890e8810799736abaeb3c89cab9",
    }

    def test_packages_are_indexed_and_implemented(self):
        index = json.loads((LIBRARY / "configuration_library_index.json").read_text(encoding="utf-8"))
        entries = {item["configuration_id"]: item for item in index["configurations"]}
        for configuration_id in ("ACC_1MW_GRID_CDU", "ACC_1MW_GASENGINE_CDU"):
            self.assertIn(configuration_id, entries)
            manifest = json.loads(
                (LIBRARY / configuration_id / "configuration_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["implementation_status"], "implemented")

    def test_role_applicability_and_user_workbooks(self):
        common = {
            "primary_cooling": "ACC_1",
            "chw_pump": "CHW_PUMP_1",
            "rtc": "RTC_1&2",
            "cdu": "CDU_1",
            "mau": "MAU_1&2",
            "electrical_distribution": "ELECTRICAL_DISTRIBUTION_2",
        }
        gas_only = {"engine": "ENGINE_2", "engine_radiator": "ENGINE_RADIATOR_1"}
        for configuration_id, expected in (
            ("ACC_1MW_GRID_CDU", common),
            ("ACC_1MW_GASENGINE_CDU", {**common, **gas_only}),
        ):
            root = LIBRARY / configuration_id
            manifest = json.loads((root / "configuration_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["equipment_roles"], expected)
            for equipment_id in expected.values():
                metadata = json.loads(
                    (root / "equipment" / equipment_id / "equipment_metadata.json").read_text(encoding="utf-8")
                )
                self.assertEqual(metadata["status"], "implemented")
                self.assertTrue((root / "equipment" / equipment_id / f"{equipment_id}.xlsx").exists())

    def test_package_it_load_workbooks_exist(self):
        for configuration_id in ("ACC_1MW_GRID_CDU", "ACC_1MW_GASENGINE_CDU"):
            self.assertTrue((LIBRARY / configuration_id / "input" / "IT_LOAD_90_PERCENT.xlsx").exists())

    def test_authoritative_acc_curves_are_rectangular_and_immutable(self):
        expected_ambients = {
            -5.0, -3.0, 0.0, 3.0, 6.0, 9.0, 11.0, 14.0, 17.0,
            20.0, 23.0, 25.0, 28.0, 31.0, 34.0, 36.0, 39.0, 42.0, 45.0,
        }
        expected_loads = {0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0}
        for configuration_id, expected_hash in self.ACC_HASHES.items():
            workbook = LIBRARY / configuration_id / "equipment" / "ACC_1" / "ACC_1.xlsx"
            self.assertEqual(hashlib.sha256(workbook.read_bytes()).hexdigest(), expected_hash)
            rows = _records(read_xlsx_sheets(workbook)["Solver_Curve"])
            points = {(float(row["ambient_C"]), float(row["load_ratio"])) for row in rows}
            self.assertEqual(len(rows), 190)
            self.assertEqual({point[0] for point in points}, expected_ambients)
            self.assertEqual({point[1] for point in points}, expected_loads)
            self.assertEqual(len(points), len(expected_ambients) * len(expected_loads))
            self.assertFalse(any(float(row["ambient_C"]) == 46.1 for row in rows))

    def test_acc_upper_ambient_is_clamped_without_fabricated_points(self):
        for configuration_id in self.ACC_HASHES:
            preview = read_acc_v2_equipment_curves(LIBRARY / configuration_id)
            point = lookup_acc_curve(
                preview.equipment_curves["acc_unit"],
                ambient_C=46.1,
                required_capacity_kW=1019.5,
                nominal_unit_capacity_kW=1000,
            )
            self.assertEqual(point.ambient_C, 45.0)
            self.assertAlmostEqual(point.required_capacity_kW, 1019.5)
            self.assertFalse(point.capacity_clamped)

    def test_package_it_load_profiles_are_complete_and_identical(self):
        hashes = set()
        for configuration_id in self.ACC_HASHES:
            workbook = LIBRARY / configuration_id / "input" / "IT_LOAD_90_PERCENT.xlsx"
            hashes.add(hashlib.sha256(workbook.read_bytes()).hexdigest())
            rows = _records(read_xlsx_sheets(workbook)["IT_Load"])
            hours = [int(row["Hour_of_Year"]) for row in rows]
            loads = [float(row["hourly_it_load_percent"]) for row in rows]
            self.assertEqual(hours, list(range(1, 8761)))
            self.assertEqual(set(loads), {90.0})
        self.assertEqual(len(hashes), 1)

    def test_activated_packages_run_all_scenarios_and_preserve_parity(self):
        results = {}
        for configuration_id in self.ACC_HASHES:
            for scenario in ("Normal", "Failure"):
                payload = convert_library_input_to_solver_input(
                    build_solver_input_from_library(configuration_id, 4.0, scenario)
                )
                payload.update({
                    "solar_heat_gain_max_kW": 7,
                    "other_auxiliary_heat_gain_kW": 71,
                    "peak_design_weather_source": "manual",
                    "peak_design_outdoor_dry_bulb_C": 46.1,
                    "acc_v2_enabled": True,
                    "acc_v2": {"configuration_path": str(LIBRARY / configuration_id)},
                })
                with contextlib.redirect_stdout(io.StringIO()):
                    result = compute_pue_project(payload)
                self.assertNotIn("error", result)
                self.assertEqual(len(result["hourly_results"]), 8760)
                peak = result["peak_results"]
                self.assertAlmostEqual(peak["peak_design_cooling_load_kW"], 4078)
                expected_peak_ratio = 0.8 if scenario == "Normal" else 1.0
                self.assertAlmostEqual(peak["peak_design_CHW_pump_load_ratio"], expected_peak_ratio)
                self.assertAlmostEqual(peak["peak_design_CHW_pump_reference_capacity_kW"], 1019.5)
                results[(configuration_id, scenario)] = result

        common_annual = (
            "annual_acc_energy_kWh", "annual_pump_energy_kWh", "annual_cdu_energy_kWh",
            "annual_rtc_energy_kWh", "annual_mau_energy_kWh",
        )
        for scenario in ("Normal", "Failure"):
            grid = results[("ACC_1MW_GRID_CDU", scenario)]
            gas = results[("ACC_1MW_GASENGINE_CDU", scenario)]
            for key in common_annual:
                self.assertAlmostEqual(grid["annual_results"][key], gas["annual_results"][key])
            self.assertEqual(grid["annual_results"]["annual_engine_radiator_energy_kWh"], 0)
            self.assertGreater(gas["annual_results"]["annual_engine_radiator_energy_kWh"], 0)
            self.assertAlmostEqual(
                gas["peak_results"]["peak_design_non_radiator_facility_power_kW"],
                grid["peak_results"]["peak_design_total_facility_power_kW"],
            )

    def test_frontend_and_report_keep_phase23q_f_semantics(self):
        source = (Path(__file__).with_name("ui.js")).read_text(encoding="utf-8")
        for configuration_id, display_name in (
            ("ACC_1MW_GRID_CDU", "ACC 1 MW + Grid + CDU"),
            ("ACC_1MW_GASENGINE_CDU", "ACC 1 MW + Gas Engine + CDU"),
        ):
            manifest = json.loads(
                (LIBRARY / configuration_id / "configuration_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["display_name"], display_name)
        self.assertIn("Failure Peak Design cooling load per active CHW Pump", source)


if __name__ == "__main__":
    unittest.main()
