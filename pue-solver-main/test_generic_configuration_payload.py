import re
import unittest
from copy import deepcopy
from pathlib import Path

from configuration_library_loader import build_solver_input_from_library
from equipment_role_resolver import resolve_equipment_role_id
from solver import compute_pue_project
from topology_adapters.acc_gas_engine_cdu import build_acc_solver_input_from_configuration
from topology_dispatcher import dispatch_topology


def _generic_payload(library_input):
    manifest = deepcopy(library_input["configuration_manifest"])
    selected_curves = deepcopy(library_input["selected_curves"])
    role_bindings = {}
    equipment_bindings = {}
    for role_name in manifest.get("equipment_roles", {}):
        resolved = resolve_equipment_role_id(manifest, role_name, selected_curves)
        if resolved is None:
            role_bindings[role_name] = None
            continue
        ids = resolved if isinstance(resolved, list) else [resolved]
        bindings = []
        for equipment_id in ids:
            selected = selected_curves[equipment_id]
            binding = {
                "enabled": selected.get("status") != "Missing Solver_Curve",
                "equipment_id": equipment_id,
                "role": role_name,
                "package_path": selected.get("package_path"),
                "selected_curve_sheet": selected.get("sheet_name"),
                "selected_curve_status": selected.get("status"),
                "curve_data": selected.get("curve"),
                "performance_map": selected.get("performance_map"),
                "electrical_path": selected.get("electrical_path"),
                "equipment_metadata": selected.get("equipment_metadata"),
            }
            bindings.append(binding)
            equipment_bindings[equipment_id] = binding
        role_bindings[role_name] = bindings if isinstance(resolved, list) else bindings[0]

    electrical = role_bindings.get("electrical_distribution")
    electrical_path = (electrical[0] if isinstance(electrical, list) else electrical or {}).get("electrical_path")
    payload = {
        key: deepcopy(library_input.get(key))
        for key in (
            "configuration_id",
            "configuration_display_name",
            "configuration_manifest_schema_version",
            "topology_id",
            "implementation_status",
            "solver_dispatch_key",
            "report_profile",
            "configuration_name",
            "configuration_path",
            "cooling_system_type",
            "cooling_unit_capacity_mw",
            "power_source",
            "scenario_name",
            "project",
            "unit_quantity",
            "selected_curves",
            "configuration_manifest",
            "weather",
            "dry_cooler_approach_C",
            "heat_gains",
            "peak_design_weather_source",
            "peak_design_outdoor_dry_bulb_C",
            "ashrae_design_conditions_url",
            "site_location",
            "other_electrical_auxiliary_power_kW",
        )
        if key in library_input
    }
    payload["configuration_manifest"] = manifest
    payload["selected_curves"] = selected_curves
    payload["equipment"] = {
        "role_bindings": role_bindings,
        "equipment_bindings": equipment_bindings,
        "electrical_path": electrical_path,
    }
    payload["electrical_path"] = electrical_path
    return payload


class GenericConfigurationPayloadTest(unittest.TestCase):
    def test_frontend_payload_builder_has_no_topology_specific_equipment_branch(self):
        ui = (Path(__file__).resolve().parent / "ui.js").read_text(encoding="utf-8")
        match = re.search(r"function\s+buildGenericConfigurationLibraryPayload\s*\(", ui)
        self.assertIsNotNone(match)
        start = match.start()
        next_match = re.search(r"\n(?:async\s+)?function\s+\w+\s*\(", ui[start + 1:])
        block = ui[start:start + 1 + next_match.start()]

        self.assertIn("role_bindings: roleBindings", block)
        self.assertIn("equipment_bindings: equipmentBindings", block)
        self.assertNotIn('topologyId === "acc_gas_engine_cdu"', block)
        self.assertNotIn('topologyId === "chiller_dry_cooler"', block)
        self.assertNotIn("ACC:", block)
        self.assertNotIn("chiller: bindingByRole", block)
        self.assertNotIn("dry_cooler: {", block)

    def test_acc_generic_payload_dispatches_and_preserves_pue(self):
        library_input = build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        generic = _generic_payload(library_input)

        dispatched = dispatch_topology(generic["configuration_manifest"], deepcopy(generic))
        previous = build_acc_solver_input_from_configuration(
            library_input["configuration_manifest"],
            deepcopy(library_input),
        )

        self.assertEqual(dispatched["status"], "success")
        self.assertLess(
            abs(
                dispatched["annual_results"]["annual_average_PUE"]
                - compute_pue_project(previous)["annual_results"]["annual_average_PUE"]
            ),
            1e-9,
        )

    def test_chiller_generic_payload_dispatches(self):
        library_input = build_solver_input_from_library("CHILLER_DRYCOOLER_2MW_GRID", 2.0, "Normal")
        generic = _generic_payload(library_input)

        dispatched = dispatch_topology(generic["configuration_manifest"], generic)

        self.assertEqual(dispatched["status"], "success")
        self.assertEqual(dispatched["topology_id"], "chiller_dry_cooler")
        self.assertEqual(len(dispatched["hourly_results"]), 8760)
        self.assertIn("annual_average_PUE", dispatched["annual_results"])


if __name__ == "__main__":
    unittest.main()
