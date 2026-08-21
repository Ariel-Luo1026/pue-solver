import unittest
from copy import deepcopy

from configuration_library_loader import build_solver_input_from_library
from equipment_engine import ConfigurationLibraryEquipmentEngine, EquipmentEngineConfig
from equipment_role_resolver import resolve_equipment_role_id
from indoor_equipment import evaluate_indoor_equipment, project_it_load_ratio
from topology_adapters.chiller_dry_cooler_runtime import (
    ChillerDryCoolerRuntime,
    ChillerDryCoolerRuntimeError,
)


class IndoorEquipmentCrossTopologyTest(unittest.TestCase):
    def _evaluate_configuration(self, configuration_id, units=3, ratio=0.9):
        payload = build_solver_input_from_library(configuration_id, 4.0, "Normal")
        selected = payload["selected_curves"]
        roles = payload["configuration_manifest"]["equipment_roles"]
        if "indoor_cooling" in roles:
            equipment_ids = resolve_equipment_role_id(payload["configuration_manifest"], "indoor_cooling", selected)
        else:
            equipment_ids = [
                resolve_equipment_role_id(payload["configuration_manifest"], role, selected)
                for role in ("cdu", "rtc", "mau")
            ]
        bindings = {}
        curves = {}
        for equipment_id in equipment_ids:
            role = str((selected[equipment_id].get("equipment_metadata") or {}).get("equipment_type") or equipment_id).lower().split("_")[0]
            bindings[role] = {"equipment_id": equipment_id, "enabled": True}
            curves[equipment_id] = {"points": selected[equipment_id]["curve"]}
        engine = ConfigurationLibraryEquipmentEngine(EquipmentEngineConfig(preloaded_curves=curves))

        def lookup(role, equipment_id, binding, load_ratio):
            result = engine.lookup_power(equipment_id, load_ratio)
            self.assertTrue(result.lookup_success, result.errors)
            return result.power_kW

        return evaluate_indoor_equipment(bindings, ratio, units, lookup)

    def test_acc_and_chiller_use_identical_indoor_curve_results(self):
        acc = self._evaluate_configuration("ACC_1.5MW_GASENGINE_CDU")
        chiller = self._evaluate_configuration("CHILLER_DRYCOOLER_2MW_GRID")
        for field in ("cdu_power_kW", "rtc_power_kW", "mau_power_kW", "white_space_equipment_power_kW"):
            self.assertAlmostEqual(acc[field], chiller[field])
        self.assertAlmostEqual(chiller["white_space_equipment_power_kW"], 91.26)

    def test_project_it_load_ratio_is_shared_and_clamped(self):
        self.assertEqual(project_it_load_ratio(3600, 4000), 0.9)
        self.assertEqual(project_it_load_ratio(5000, 4000), 1.0)
        self.assertEqual(project_it_load_ratio(-1, 4000), 0.0)

    def test_optional_role_absence_does_not_fabricate_equipment(self):
        payload = build_solver_input_from_library("CHILLER_DRYCOOLER_2MW_GRID", 4.0, "Normal")
        manifest = deepcopy(payload["configuration_manifest"])
        manifest["equipment_roles"].pop("indoor_cooling")
        runtime = ChillerDryCoolerRuntime(manifest, payload)
        self.assertEqual(runtime.indoor_equipment_ids, [])
        result = evaluate_indoor_equipment({}, 0.9, 3, lambda *args: self.fail("lookup should not run"))
        self.assertEqual(result["white_space_equipment_power_kW"], 0.0)

    def test_configured_enabled_missing_curve_fails_loudly(self):
        payload = build_solver_input_from_library("CHILLER_DRYCOOLER_2MW_GRID", 4.0, "Normal")
        payload["selected_curves"]["CDU_2"]["curve"] = []
        with self.assertRaisesRegex(ChillerDryCoolerRuntimeError, "CDU_2 Solver_Curve missing or invalid"):
            ChillerDryCoolerRuntime(payload["configuration_manifest"], payload)

    def test_configured_disabled_equipment_is_zero(self):
        result = evaluate_indoor_equipment(
            {"cdu": {"equipment_id": "CDU_2", "enabled": False}},
            0.9,
            3,
            lambda *args: self.fail("disabled equipment lookup should not run"),
        )
        self.assertEqual(result["cdu_power_kW"], 0.0)
        self.assertEqual(result["indoor_equipment_curve_sources"]["cdu"], "configured_disabled")


if __name__ == "__main__":
    unittest.main()
