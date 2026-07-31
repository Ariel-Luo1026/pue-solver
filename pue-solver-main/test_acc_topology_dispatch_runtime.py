import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from acc_v2_curve_reader import (
    ACC_SOLVER_CURVE_COLUMNS,
    find_equipment_workbook,
    read_equipment_solver_curve,
)
from configuration_library_loader import build_solver_input_from_library
from report_dispatcher import dispatch_report
from solver import compute_pue_project
from topology_adapters.acc_gas_engine_cdu import build_acc_solver_input_from_configuration
from topology_dispatcher import dispatch_topology


class AccTopologyDispatchRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library_input = build_solver_input_from_library(
            "ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal"
        )
        cls.manifest = cls.library_input["configuration_manifest"]

    def test_acc_manifest_resolves_topology(self):
        self.assertEqual(self.manifest["solver_topology"], "acc_gas_engine_cdu")

    def test_acc_dispatch_reaches_acc_adapter(self):
        with patch(
            "topology_adapters.acc_gas_engine_cdu.build_solver_input_from_configuration",
            return_value={"status": "adapter_called"},
        ) as adapter:
            result = dispatch_topology(self.manifest, deepcopy(self.library_input))

        adapter.assert_called_once()
        self.assertEqual(result["status"], "adapter_called")

    def test_acc_topology_preserves_explicit_runtime_configuration_path(self):
        browser_path = "Configuration Library/ACC_1.5MW_GASENGINE_CDU"
        library_input = deepcopy(self.library_input)
        library_input["configuration_path"] = browser_path

        solver_input = build_acc_solver_input_from_configuration(
            self.manifest,
            library_input,
        )

        self.assertEqual(solver_input["configuration_path"], browser_path)
        self.assertEqual(solver_input["acc_v2"]["configuration_path"], browser_path)

    def test_acc_topology_can_resolve_acc_workbook_and_solver_curve(self):
        solver_input = build_acc_solver_input_from_configuration(
            self.manifest,
            deepcopy(self.library_input),
        )
        configuration_path = Path(solver_input["acc_v2"]["configuration_path"])
        workbook_path = find_equipment_workbook(configuration_path, "ACC_2")

        self.assertIsNotNone(workbook_path)
        self.assertEqual(workbook_path.name, "ACC_2.xlsx")
        rows = read_equipment_solver_curve(workbook_path, ACC_SOLVER_CURVE_COLUMNS)
        self.assertGreater(len(rows), 0)
        available_columns = set(rows[0])
        for column in ACC_SOLVER_CURVE_COLUMNS:
            self.assertIn(column, available_columns)

    def test_acc_dispatch_returns_runtime_result(self):
        result = dispatch_topology(self.manifest, deepcopy(self.library_input))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["topology_id"], "acc_gas_engine_cdu")
        self.assertEqual(len(result["hourly_results"]), 8760)
        self.assertIn("annual_average_PUE", result["annual_results"])

    def test_annual_pue_unchanged_against_preserved_solver_input(self):
        dispatched = dispatch_topology(self.manifest, deepcopy(self.library_input))
        previous_input = build_acc_solver_input_from_configuration(
            self.manifest,
            deepcopy(self.library_input),
        )
        previous = compute_pue_project(previous_input)

        self.assertLess(
            abs(
                dispatched["annual_results"]["annual_average_PUE"]
                - previous["annual_results"]["annual_average_PUE"]
            ),
            1e-9,
        )

    def test_acc_existing_report_still_works(self):
        result = dispatch_topology(self.manifest, deepcopy(self.library_input))
        report = dispatch_report(result["topology_id"], result)

        self.assertEqual(report["profile_id"], "acc_gas_engine_cdu")
        self.assertEqual(report["dispatch_status"], "matched")
        self.assertIn("report_sections", report)
        self.assertAlmostEqual(
            report["annual_energy_breakdown"]["PUE"],
            result["annual_results"]["annual_average_PUE"],
            places=12,
        )


if __name__ == "__main__":
    unittest.main()
