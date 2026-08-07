import ast
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class FrontendPumpFrameworkLoadingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = (ROOT / "ui.js").read_text(encoding="utf-8")
        match = re.search(
            r"const DIRECT_MODE_PYTHON_MODULES = Object\.freeze\(\[(.*?)\]\);",
            cls.ui,
            re.DOTALL,
        )
        if not match:
            raise AssertionError("DIRECT_MODE_PYTHON_MODULES was not found.")
        cls.modules = re.findall(r'"([^"]+)"', match.group(1))

    def test_pump_framework_is_preloaded_once_before_chiller_runtime(self):
        self.assertEqual(self.modules.count("pump_load_framework.py"), 1)
        self.assertLess(
            self.modules.index("pump_load_framework.py"),
            self.modules.index("topology_adapters/chiller_dry_cooler_runtime.py"),
        )

    def test_pump_framework_has_no_unlisted_local_dependencies(self):
        tree = ast.parse((ROOT / "pump_load_framework.py").read_text(encoding="utf-8"))
        imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertEqual(imports, [])

    def test_chiller_import_chain_and_pump_equipment_remain_available(self):
        required = {
            "pump_load_framework.py",
            "equipment_engine.py",
            "equipment_performance/__init__.py",
            "topology_adapters/__init__.py",
            "topology_adapters/chiller_dry_cooler_runtime.py",
            "topology_adapters/chiller_dry_cooler.py",
            "topology_registry.py",
            "topology_dispatcher.py",
        }
        self.assertTrue(required.issubset(self.modules))
        runtime = (ROOT / "topology_adapters" / "chiller_dry_cooler_runtime.py").read_text(encoding="utf-8")
        self.assertIn("from pump_load_framework import", runtime)
        self.assertIn("CHW_PUMP", runtime)
        self.assertIn("CW_PUMP", runtime)

    def test_acc_frontend_modules_are_preserved(self):
        for module in (
            "acc_v2_curve_lookup.py",
            "acc_v2_curve_reader.py",
            "acc_v2_diagnostics.py",
            "acc_v2_engine.py",
            "topology_adapters/acc_gas_engine_cdu.py",
        ):
            self.assertIn(module, self.modules)

    def test_loader_writes_matching_relative_module_path(self):
        self.assertIn("for (const moduleName of DIRECT_MODE_PYTHON_MODULES)", self.ui)
        self.assertIn("await loadPythonModuleIntoPyodide(moduleName)", self.ui)
        self.assertIn("pyodide.FS.writeFile(fileName, text)", self.ui)


if __name__ == "__main__":
    unittest.main()
