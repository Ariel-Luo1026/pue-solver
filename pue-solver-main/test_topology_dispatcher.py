import unittest
from copy import deepcopy

from configuration_library_loader import build_solver_input_from_library
from library_solver_adapter import _build_acc_gas_engine_cdu_solver_input
from solver import compute_pue_project
from topology_adapters.chiller_dry_cooler import FRAMEWORK_REASON
from topology_dispatcher import (
    NOT_IMPLEMENTED_REASON,
    TopologyDispatchError,
    dispatch_topology,
)


class TopologyDispatcherTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library_input = build_solver_input_from_library(
            "ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal"
        )
        cls.manifest = cls.library_input["configuration_manifest"]

    def test_acc_topology_dispatches_to_solver_adapter(self):
        dispatched = dispatch_topology(self.manifest, deepcopy(self.library_input))

        self.assertIn("project", dispatched)
        self.assertEqual(dispatched["topology_id"], "acc_gas_engine_cdu")
        self.assertEqual(dispatched["acc_curve"]["equipment_id"], "ACC_2")

    def test_unknown_topology_fails(self):
        manifest = deepcopy(self.manifest)
        manifest["solver_topology"] = "unknown_topology"

        with self.assertRaisesRegex(TopologyDispatchError, "Unknown solver_topology"):
            dispatch_topology(manifest, deepcopy(self.library_input))

    def test_chiller_dry_cooler_topology_returns_framework_status(self):
        manifest = deepcopy(self.manifest)
        manifest["solver_topology"] = "chiller_dry_cooler"

        result = dispatch_topology(manifest, deepcopy(self.library_input))

        self.assertEqual(result["status"], "framework_ready_data_missing")
        self.assertEqual(result["topology"], "chiller_dry_cooler")
        self.assertEqual(result["reason"], FRAMEWORK_REASON)

    def test_framework_only_topology_without_adapter_returns_not_implemented_error(self):
        manifest = deepcopy(self.manifest)
        manifest["solver_topology"] = "water_cooled_chiller"

        result = dispatch_topology(manifest, deepcopy(self.library_input))

        self.assertEqual(result["status"], "not_implemented")
        self.assertEqual(result["topology"], "water_cooled_chiller")
        self.assertEqual(result["reason"], NOT_IMPLEMENTED_REASON)

    def test_acc_annual_pue_output_remains_unchanged(self):
        dispatched = dispatch_topology(self.manifest, deepcopy(self.library_input))
        previous = _build_acc_gas_engine_cdu_solver_input(deepcopy(self.library_input))

        dispatched_pue = compute_pue_project(dispatched)["annual_results"]["annual_average_PUE"]
        previous_pue = compute_pue_project(previous)["annual_results"]["annual_average_PUE"]

        self.assertLess(abs(dispatched_pue - previous_pue), 1e-9)


if __name__ == "__main__":
    unittest.main()
