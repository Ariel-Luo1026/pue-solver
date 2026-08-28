import json
import unittest
from hashlib import sha256
from pathlib import Path

from configuration_library_loader import _records, build_solver_input_from_library, read_xlsx_sheets
from equipment_engine import ConfigurationLibraryEquipmentEngine, EquipmentEngineConfig
from library_solver_adapter import convert_library_input_to_solver_input
from solver import compute_pue_project


ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "Configuration Library"
GRID_ID = "ACC_1.5MW_GRID_CDU"
GAS_ID = "ACC_1.5MW_GASENGINE_CDU"
COMMON_EQUIPMENT = (
    "ACC_2",
    "CHW_PUMP_2",
    "CDU_2",
    "RTC_1&2",
    "MAU_1&2",
    "ELECTRICAL_DISTRIBUTION_2",
)
CONFIGURATION_OWNED_SEMANTIC_EQUIPMENT = {"CDU_2"}


def file_hash(path):
    return sha256(path.read_bytes()).hexdigest()


def executable_input(configuration_id, scenario, hours=1):
    payload = convert_library_input_to_solver_input(
        build_solver_input_from_library(configuration_id, 4.0, scenario)
    )
    payload["project"]["it_load"]["hourly_it_load_kW"] = [3600.0] * hours
    payload["weather"]["hourly_data"] = {
        "hour_index": list(range(1, hours + 1)),
        "dry_bulb_C": [35.0] * hours,
        "wet_bulb_C": [],
    }
    payload["peak_design_weather_source"] = "manual"
    payload["peak_design_outdoor_dry_bulb_C"] = 44.0
    payload["project"]["peak_design_weather_source"] = "manual"
    payload["project"]["peak_design_outdoor_dry_bulb_C"] = 44.0
    payload["acc_v2_enabled"] = True
    payload["acc_v2"] = {
        "configuration_path": str(LIBRARY / configuration_id),
    }
    return payload


class AccGridConfigurationActivationTest(unittest.TestCase):
    def assert_configuration_owned_workbooks_semantically_equal(
        self, grid_workbook, gas_workbook, equipment_id, representative_load_ratio
    ):
        grid_sheets = read_xlsx_sheets(grid_workbook)
        gas_sheets = read_xlsx_sheets(gas_workbook)
        self.assertEqual(list(grid_sheets), list(gas_sheets))
        self.assertEqual(grid_sheets["Solver_Curve"][0], gas_sheets["Solver_Curve"][0])
        for sheet_name in ("Metadata", "Performance_Map", "Solver_Curve", "Validation"):
            self.assertEqual(_records(grid_sheets[sheet_name]), _records(gas_sheets[sheet_name]))

        grid_information = {row["Parameter"]: row["Value"] for row in _records(grid_sheets["Information"])}
        gas_information = {row["Parameter"]: row["Value"] for row in _records(gas_sheets["Information"])}
        for parameter in ("Equipment Type", "Model ID", "Maximum Power", "Base Power", "Primary Read Sheet"):
            self.assertEqual(grid_information[parameter], gas_information[parameter])

        curves = {
            "grid": {"points": _records(grid_sheets["Solver_Curve"])},
            "gas": {"points": _records(gas_sheets["Solver_Curve"])},
        }
        engine = ConfigurationLibraryEquipmentEngine(EquipmentEngineConfig(preloaded_curves=curves))
        grid_point = engine.lookup_power("grid", representative_load_ratio)
        gas_point = engine.lookup_power("gas", representative_load_ratio)
        self.assertTrue(grid_point.lookup_success, grid_point.errors)
        self.assertTrue(gas_point.lookup_success, gas_point.errors)
        self.assertAlmostEqual(grid_point.power_kW, gas_point.power_kW)
        return grid_point.power_kW

    def test_manifest_and_index_activate_grid_configuration(self):
        manifest = json.loads((LIBRARY / GRID_ID / "configuration_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["configuration_id"], GRID_ID)
        self.assertEqual(manifest["display_name"], "ACC 1.5 MW + Grid + CDU")
        self.assertEqual(manifest["power_source"], "Grid")
        self.assertEqual(manifest["cooling_technology"], "ACC")
        self.assertEqual(manifest["cooling_unit_capacity_mw"], 1.5)
        self.assertEqual(manifest["solver_topology"], "acc_gas_engine_cdu")
        self.assertEqual(manifest["report_profile"], "acc_gas_engine_cdu")
        self.assertNotIn("engine", manifest["equipment_roles"])
        self.assertNotIn("engine_radiator", manifest["equipment_roles"])
        index = json.loads((LIBRARY / "configuration_library_index.json").read_text(encoding="utf-8"))
        ids = [item["configuration_id"] for item in index["configurations"]]
        self.assertIn(GRID_ID, ids)
        self.assertLess(ids.index(GAS_ID), ids.index(GRID_ID))

    def test_common_runtime_packages_are_byte_identical_and_generation_packages_absent(self):
        for equipment_id in COMMON_EQUIPMENT:
            with self.subTest(equipment_id=equipment_id):
                grid_dir = LIBRARY / GRID_ID / "equipment" / equipment_id
                gas_dir = LIBRARY / GAS_ID / "equipment" / equipment_id
                grid_files = sorted(path.name for path in grid_dir.iterdir() if path.is_file() and not path.name.startswith("~$"))
                gas_files = sorted(path.name for path in gas_dir.iterdir() if path.is_file() and not path.name.startswith("~$"))
                self.assertEqual(grid_files, gas_files)
                for filename in grid_files:
                    if equipment_id in CONFIGURATION_OWNED_SEMANTIC_EQUIPMENT and filename.endswith(".xlsx"):
                        power_per_unit = self.assert_configuration_owned_workbooks_semantically_equal(
                            grid_dir / filename, gas_dir / filename, equipment_id, 0.9
                        )
                        self.assertAlmostEqual(power_per_unit, 18.87)
                        self.assertAlmostEqual(power_per_unit * 3, 56.61)
                    else:
                        self.assertEqual(file_hash(grid_dir / filename), file_hash(gas_dir / filename))
        self.assertFalse((LIBRARY / GRID_ID / "equipment" / "ENGINE_3").exists())
        self.assertFalse((LIBRARY / GRID_ID / "equipment" / "ENGINE_RADIATOR_1").exists())

    def test_distinct_reserved_acc_workbook_is_preserved_as_provenance(self):
        archived = LIBRARY / GRID_ID / "source" / "legacy_YVAM1500_ACC_2.xlsx"
        self.assertEqual(
            file_hash(archived),
            "06fc19a3965162fc17938c56e5b710d2271a37db1fc1f15e9bc2a25149ffc516",
        )
        self.assertNotEqual(
            file_hash(archived),
            file_hash(LIBRARY / GRID_ID / "equipment" / "ACC_2" / "ACC_2.xlsx"),
        )

    def test_normal_and_failure_unit_policy(self):
        normal = build_solver_input_from_library(GRID_ID, 4.0, "Normal")
        failure = build_solver_input_from_library(GRID_ID, 4.0, "Failure")
        self.assertEqual(
            (normal["project"]["required_units"], normal["project"]["installed_units"], normal["project"]["active_units"], normal["project"]["indoor_active_units"]),
            (3, 4, 4, 4),
        )
        self.assertEqual(
            (failure["project"]["required_units"], failure["project"]["installed_units"], failure["project"]["active_units"], failure["project"]["indoor_active_units"]),
            (3, 4, 3, 4),
        )

    def test_grid_and_gas_share_facility_side_results(self):
        for scenario in ("Normal", "Failure"):
            with self.subTest(scenario=scenario):
                grid = compute_pue_project(executable_input(GRID_ID, scenario))
                gas = compute_pue_project(executable_input(GAS_ID, scenario))
                self.assertNotIn("error", grid)
                self.assertNotIn("error", gas)
                grid_hour = grid["hourly_results"][0]
                gas_hour = gas["hourly_results"][0]
                for field in (
                    "cooling_power_kW",
                    "pump_power_kW",
                    "cdu_power_kW",
                    "rtc_power_kW",
                    "mau_power_kW",
                    "white_space_equipment_power_kW",
                ):
                    with self.subTest(field=field):
                        self.assertAlmostEqual(grid_hour[field], gas_hour[field], places=9)
                self.assertIsNone(grid_hour["engine_output_kW"])
                self.assertEqual(grid_hour["engine_radiator_power_kW"], 0.0)
                self.assertGreater(gas_hour["engine_output_kW"], 0.0)
                self.assertGreater(gas_hour["engine_radiator_power_kW"], 0.0)
                expected_facility_delta = gas_hour["engine_radiator_power_kW"] + (
                    gas_hour["mep_electrical_loss_kW"] - grid_hour["mep_electrical_loss_kW"]
                )
                self.assertAlmostEqual(
                    gas_hour["total_facility_power_kW"] - grid_hour["total_facility_power_kW"],
                    expected_facility_delta,
                    places=9,
                )

    def test_grid_normal_and_failure_run_full_8760_and_reconcile(self):
        for scenario in ("Normal", "Failure"):
            with self.subTest(scenario=scenario):
                result = compute_pue_project(executable_input(GRID_ID, scenario, hours=8760))
                self.assertNotIn("error", result)
                self.assertEqual(len(result["hourly_results"]), 8760)
                annual = result["annual_results"]
                self.assertEqual(annual["annual_engine_output_kWh"], 0.0)
                self.assertEqual(annual["annual_engine_radiator_energy_kWh"], 0.0)
                self.assertAlmostEqual(
                    annual["annual_facility_energy_kWh"],
                    sum(row["total_facility_power_kW"] for row in result["hourly_results"]),
                    places=6,
                )
                peak = result["peak_results"]
                self.assertEqual(peak.get("peak_design_engine_radiator_power_kW"), 0.0)
                self.assertGreater(annual["annual_average_PUE"], 1.0)


if __name__ == "__main__":
    unittest.main()
