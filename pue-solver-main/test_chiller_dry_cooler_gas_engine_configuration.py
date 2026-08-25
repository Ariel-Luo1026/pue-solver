import json
import unittest
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from configuration_library_loader import build_solver_input_from_library, load_configuration_library
from equipment_role_resolver import EquipmentRoleResolutionError
from topology_adapters.chiller_dry_cooler_runtime import ChillerDryCoolerRuntimeError
from topology_dispatcher import dispatch_topology


ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "Configuration Library"
CONFIGURATION = "CHILLER_DRYCOOLER_2MW_GASENGINE_CDU"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def one_hour_input(scenario="Normal"):
    prepared = build_solver_input_from_library(CONFIGURATION, 4.0, scenario)
    prepared["project"]["it_load"]["hourly_it_load_kW"] = [3600.0]
    prepared["project"]["it_load"]["hourly_it_load_percent"] = [90.0]
    prepared["peak_design_weather_source"] = "manual"
    prepared["peak_design_outdoor_dry_bulb_C"] = 44.0
    prepared["project"]["peak_design_weather_source"] = "manual"
    prepared["project"]["peak_design_outdoor_dry_bulb_C"] = 44.0
    return prepared


class ChillerDryCoolerGasEngineConfigurationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loaded = load_configuration_library(CONFIGURATION, total_it_capacity_mw=4.0)
        cls.inputs = {scenario: one_hour_input(scenario) for scenario in ("Normal", "Failure")}
        cls.results = {
            scenario: dispatch_topology(value["configuration_manifest"], value)
            for scenario, value in cls.inputs.items()
        }

    def test_manifest_and_index_register_canonical_configuration(self):
        manifest = self.loaded["configuration_manifest"]
        self.assertEqual(manifest["configuration_id"], CONFIGURATION)
        self.assertEqual(manifest["solver_topology"], "chiller_dry_cooler")
        self.assertEqual(self.loaded["power_source"], "Gas Engine")
        self.assertEqual(self.loaded["cooling_unit_capacity_mw"], 2.0)
        self.assertEqual([row["scenario"] for row in self.loaded["scenarios"]], ["Normal", "Failure"])
        index = json.loads((LIBRARY / "configuration_library_index.json").read_text(encoding="utf-8"))
        self.assertIn(CONFIGURATION, [row["configuration_id"] for row in index["configurations"]])

    def test_manifest_roles_select_engine_and_radiator_independently(self):
        roles = self.loaded["configuration_manifest"]["equipment_roles"]
        self.assertEqual(roles["engine"], "ENGINE_3")
        self.assertEqual(roles["engine_radiator"], "ENGINE_RADIATOR_1")
        self.assertNotEqual(roles["engine"], roles["engine_radiator"])

    def test_all_runtime_workbooks_match_canonical_sources(self):
        target = LIBRARY / CONFIGURATION / "equipment"
        grid = LIBRARY / "CHILLER_DRYCOOLER_2MW_GRID" / "equipment"
        acc = LIBRARY / "ACC_1.5MW_GASENGINE_CDU" / "equipment"
        for equipment_id in (
            "CENTRIFUGALCHILLER_1", "DRYCOOLER_6", "CHW_PUMP_3", "CW_PUMP_6",
            "CDU_2", "RTC_1&2", "MAU_1&2", "ELECTRICAL_DISTRIBUTION_2",
        ):
            self.assertEqual(
                digest(target / equipment_id / f"{equipment_id}.xlsx"),
                digest(grid / equipment_id / f"{equipment_id}.xlsx"),
            )
        for equipment_id in ("ENGINE_3", "ENGINE_RADIATOR_1"):
            self.assertEqual(
                digest(target / equipment_id / f"{equipment_id}.xlsx"),
                digest(acc / equipment_id / f"{equipment_id}.xlsx"),
            )

    def test_normal_and_failure_unit_policies_reach_runtime(self):
        expected = {"Normal": (3, 3, 3, 3), "Failure": (2, 3, 2, 2)}
        for scenario, counts in expected.items():
            hour = self.results[scenario]["hourly_results"][0]
            self.assertEqual(
                (
                    hour["active_chiller_units"], hour["indoor_active_units"],
                    hour["engine_active_units"], hour["engine_radiator_active_units"],
                ),
                counts,
            )

    def test_engine_is_generation_reference_and_radiator_is_facility_load(self):
        for result in self.results.values():
            hour = result["hourly_results"][0]
            self.assertGreater(hour["engine_output_kW"], 0)
            self.assertGreater(hour["engine_fuel_input_kW"], hour["engine_output_kW"])
            self.assertAlmostEqual(
                hour["engine_waste_heat_kW"],
                hour["engine_fuel_input_kW"] - hour["engine_output_kW"],
            )
            facility_components = (
                hour["it_load_kW"] + hour["chiller_power_kW"] + hour["dry_cooler_power_kW"]
                + hour["pump_power_kW"] + hour["cw_pump_power_total_kW"]
                + hour["white_space_equipment_power_kW"] + hour["engine_radiator_power_kW"]
                + hour["electrical_loss_kW"]
            )
            self.assertAlmostEqual(hour["facility_power_kW"], facility_components)
            self.assertNotAlmostEqual(hour["facility_power_kW"], facility_components + hour["engine_output_kW"])

    def test_radiator_and_electrical_loss_reconcile(self):
        for result in self.results.values():
            hour = result["hourly_results"][0]
            self.assertGreater(hour["engine_radiator_power_kW"], 0)
            self.assertAlmostEqual(
                hour["engine_radiator_load_ratio"],
                hour["non_radiator_facility_power_kW"] / hour["engine_radiator_reference_power_kW"],
            )
            self.assertEqual(hour["engine_radiator_load_ratio_basis"], "non_radiator_facility_demand_ratio")
            self.assertAlmostEqual(
                hour["electrical_loss_kW"],
                hour["it_electrical_loss_kW"] + hour["mep_electrical_loss_kW"],
            )

    def test_peak_design_reconciles_with_radiator_and_excludes_engine_output(self):
        for result in self.results.values():
            peak = result["peak_results"]
            point = peak["peak_design_equipment_result"]
            self.assertGreater(peak["peak_design_engine_radiator_power_kW"], 0)
            self.assertAlmostEqual(
                peak["peak_design_total_facility_power_kW"], point["facility_power_kW"]
            )
            self.assertAlmostEqual(
                peak["peak_PUE"],
                peak["peak_design_total_facility_power_kW"] / peak["peak_design_it_load_kW"],
            )

    def test_alternate_engine_and_radiator_ids_resolve_from_fixture_manifest(self):
        prepared = one_hour_input("Normal")
        manifest = prepared["configuration_manifest"]
        selected = prepared["selected_curves"]
        selected["ENGINE_TEST"] = selected.pop("ENGINE_3")
        selected["ENGINE_RADIATOR_TEST"] = selected.pop("ENGINE_RADIATOR_1")
        manifest["equipment_roles"]["engine"] = "ENGINE_TEST"
        manifest["equipment_roles"]["engine_radiator"] = "ENGINE_RADIATOR_TEST"
        result = dispatch_topology(manifest, prepared)
        self.assertEqual(result["library_context"]["equipment_ids"]["engine"], "ENGINE_TEST")
        self.assertEqual(result["library_context"]["equipment_ids"]["engine_radiator"], "ENGINE_RADIATOR_TEST")

    def test_missing_roles_and_workbook_bindings_fail_explicitly(self):
        for role in ("engine", "engine_radiator"):
            prepared = one_hour_input("Normal")
            prepared["configuration_manifest"]["equipment_roles"].pop(role)
            with self.subTest(role=role), self.assertRaises(EquipmentRoleResolutionError):
                dispatch_topology(prepared["configuration_manifest"], prepared)
        prepared = one_hour_input("Normal")
        prepared["selected_curves"].pop("ENGINE_3")
        with self.assertRaises(EquipmentRoleResolutionError):
            dispatch_topology(prepared["configuration_manifest"], prepared)

    def test_invalid_engine_and_radiator_curves_fail_explicitly(self):
        for equipment_id in ("ENGINE_3", "ENGINE_RADIATOR_1"):
            prepared = one_hour_input("Normal")
            prepared["selected_curves"][equipment_id]["curve"] = []
            with self.subTest(equipment_id=equipment_id), self.assertRaisesRegex(
                ChillerDryCoolerRuntimeError, "Solver_Curve missing or invalid"
            ):
                dispatch_topology(prepared["configuration_manifest"], prepared)


if __name__ == "__main__":
    unittest.main()
