import unittest
from copy import deepcopy
from pathlib import Path

from configuration_library_loader import build_solver_input_from_library
from configuration_library_loader import read_xlsx_sheets, _records
from configuration_manifest import ConfigurationManifestError, discover_configuration_manifests, load_configuration_manifest
from configuration_validator import validate_configuration_library
from equipment_metadata import load_equipment_metadata, validate_equipment_folder
from equipment_role_resolver import resolve_equipment_role_id
from report_dispatcher import dispatch_report
from solver import compute_pue_project
from topology_adapters.acc_gas_engine_cdu import build_acc_solver_input_from_configuration
from topology_dispatcher import dispatch_topology
from topology_registry import get_topology


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LIBRARY_ROOT = PROJECT_ROOT / "Configuration Library"
CONFIGURATION_ID = "CHILLER_DRYCOOLER_2MW_GRID"
CONFIGURATION_PATH = LIBRARY_ROOT / CONFIGURATION_ID


class ChillerDryCoolerFrameworkTest(unittest.TestCase):
    def setUp(self):
        self.manifest = load_configuration_manifest(CONFIGURATION_PATH)
        self.loaded_equipment = {
            equipment_id: {"equipment_id": equipment_id}
            for equipment_id in [
                "CENTRIFUGALCHILLER_1",
                "DRYCOOLER_6",
                "CHW_PUMP_2",
                "CDU_2",
                "RTC_1&2",
                "MAU_1&2",
                "ELECTRICAL_DISTRIBUTION_2",
            ]
        }

    def test_configuration_discovery_finds_chiller_dry_cooler_package(self):
        manifests = discover_configuration_manifests(LIBRARY_ROOT)
        by_id = {item["configuration_id"]: item for item in manifests}

        self.assertIn(CONFIGURATION_ID, by_id)
        self.assertEqual(by_id[CONFIGURATION_ID]["implementation_status"], "implemented")
        self.assertEqual(by_id[CONFIGURATION_ID]["solver_topology"], "chiller_dry_cooler")

    def test_manifest_validation_uses_chiller_dry_cooler_roles(self):
        self.assertEqual(self.manifest["required_roles"], [
            "chiller",
            "dry_cooler",
            "chw_pump",
            "electrical_distribution",
        ])
        self.assertEqual(self.manifest["optional_roles"], ["indoor_cooling"])
        self.assertNotIn("engine", self.manifest["equipment_roles"])
        self.assertNotIn("engine_radiator", self.manifest["equipment_roles"])

    def test_equipment_role_binding_resolves_manifest_ids(self):
        self.assertEqual(resolve_equipment_role_id(self.manifest, "chiller", self.loaded_equipment), "CENTRIFUGALCHILLER_1")
        self.assertEqual(resolve_equipment_role_id(self.manifest, "dry_cooler", self.loaded_equipment), "DRYCOOLER_6")
        self.assertEqual(resolve_equipment_role_id(self.manifest, "chw_pump", self.loaded_equipment), "CHW_PUMP_2")
        self.assertEqual(
            resolve_equipment_role_id(self.manifest, "indoor_cooling", self.loaded_equipment),
            ["CDU_2", "RTC_1&2", "MAU_1&2"],
        )

    def test_configuration_validator_accepts_framework_package_roles(self):
        selected_curves = {}
        for equipment_id in self.loaded_equipment:
            folder = CONFIGURATION_PATH / "equipment" / equipment_id
            workbook = folder / f"{equipment_id}.xlsx"
            sheets = read_xlsx_sheets(workbook)
            sheet_name = "Solver" if equipment_id == "ELECTRICAL_DISTRIBUTION_2" else "Solver_Curve"
            if sheet_name not in sheets:
                sheet_name = "Solver_Curve_Normal"
            selected_curves[equipment_id] = {
                "status": "Electrical Path Found" if equipment_id == "ELECTRICAL_DISTRIBUTION_2" else "Selected",
                "sheet_name": sheet_name,
                "curve": _records(sheets.get(sheet_name, [])),
                "electrical_path": {"it_efficiency": 0.9723, "mep_efficiency": 0.9959}
                if equipment_id == "ELECTRICAL_DISTRIBUTION_2" else None,
                "equipment_metadata": load_equipment_metadata(folder),
            }

        validation = validate_configuration_library({
            "configuration_manifest": self.manifest,
            "configuration_id": CONFIGURATION_ID,
            "topology_id": "chiller_dry_cooler",
            "selected_curves": selected_curves,
            "equipment": {"cooling": {}},
        })

        self.assertEqual(validation["status"], "valid", validation)
        self.assertEqual(validation["missing_roles"], [])
        self.assertEqual(validation["missing_curves"], [])

    def test_equipment_metadata_is_present_and_marks_prototype_support_data(self):
        chiller = validate_equipment_folder(CONFIGURATION_PATH / "equipment" / "CENTRIFUGALCHILLER_1")
        dry_cooler = validate_equipment_folder(CONFIGURATION_PATH / "equipment" / "DRYCOOLER_6")
        pump_metadata = load_equipment_metadata(CONFIGURATION_PATH / "equipment" / "CHW_PUMP_2")

        self.assertEqual(chiller["status"], "valid")
        self.assertEqual(dry_cooler["status"], "valid")
        self.assertEqual(chiller["curve_type"], "cop_curve")
        self.assertEqual(dry_cooler["curve_type"], "ambient_capacity_power")
        self.assertEqual(pump_metadata["status"], "prototype")
        self.assertEqual(pump_metadata["data_status"], "prototype")
        self.assertEqual(pump_metadata["source_configuration"], "ACC_1.5MW_GASENGINE_CDU")

    def test_missing_required_role_fails_manifest_validation(self):
        manifest = deepcopy(self.manifest)
        manifest["equipment_roles"].pop("dry_cooler")

        with self.assertRaisesRegex(ConfigurationManifestError, "missing required equipment role: dry_cooler"):
            from configuration_manifest import validate_configuration_manifest

            validate_configuration_manifest(manifest)

    def test_chiller_dry_cooler_dispatch_returns_annual_result(self):
        library_input = build_solver_input_from_library(CONFIGURATION_ID, 2.0, "Normal")
        result = dispatch_topology(library_input["configuration_manifest"], library_input)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["topology_id"], "chiller_dry_cooler")
        self.assertEqual(len(result["hourly_results"]), 8760)
        self.assertIn("annual_average_PUE", result["annual_results"])

    def test_topology_registry_and_report_profile_are_implemented(self):
        topology = get_topology("chiller_dry_cooler")
        report = dispatch_report("chiller_dry_cooler", {"annual_results": {}})

        self.assertEqual(topology["adapter"], "chiller_dry_cooler")
        self.assertEqual(topology["status"], "implemented")
        self.assertEqual(report["profile_id"], "chiller_dry_cooler")
        self.assertEqual(report["configuration_status"], "Implemented")

    def test_existing_acc_annual_pue_remains_unchanged(self):
        library_input = build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        current = dispatch_topology(library_input["configuration_manifest"], deepcopy(library_input))
        previous = build_acc_solver_input_from_configuration(library_input["configuration_manifest"], deepcopy(library_input))

        current_pue = current["annual_results"]["annual_average_PUE"]
        previous_pue = compute_pue_project(previous)["annual_results"]["annual_average_PUE"]

        self.assertLess(abs(current_pue - previous_pue), 1e-9)


if __name__ == "__main__":
    unittest.main()
