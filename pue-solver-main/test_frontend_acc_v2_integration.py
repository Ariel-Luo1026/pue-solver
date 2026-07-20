import copy
import re
import unittest
from pathlib import Path

from configuration_library_loader import build_solver_input_from_library
from library_solver_adapter import convert_library_input_to_solver_input
from solver import compute_pue_project


class FrontendACCV2IntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent
        cls.index = (root / "index.html").read_text(encoding="utf-8")
        cls.ui = (root / "ui.js").read_text(encoding="utf-8")

    def test_acc_engine_selector_is_removed_and_direct_engine_is_fixed(self):
        self.assertNotIn('id="accCalculationEngine"', self.index)
        self.assertNotIn("Legacy ACC Engine", self.index)
        self.assertIn("ACC V2 Configuration Library Engine", self.index)

    def test_run_mode_selector_is_removed_and_direct_mode_is_fixed(self):
        self.assertNotIn('id="configurationCalculationMode"', self.index)
        self.assertNotIn("Dynamic Hourly Simulation", self.index)
        self.assertNotIn("Excel Benchmark Annual Equivalent Mode", self.index)
        self.assertNotIn("Excel Replicated Hourly Mode", self.index)
        self.assertNotIn("ACC V2 Direct Solver_Curve Hourly Mode", self.index)
        self.assertIn("Using Configuration Library Direct Solver_Curve hourly simulation.", self.index)
        self.assertIn("Configuration Library Direct Solver_Curve Hourly Simulation", self.index)

    def test_frontend_always_maps_direct_mode_to_acc_v2_feature_flag(self):
        self.assertIn("function applyAccCalculationEngineSelection", self.ui)
        self.assertIn('CONFIGURATION_LIBRARY_DIRECT_CALCULATION_MODE = "acc_v2_direct_solver_curve_hourly"', self.ui)
        self.assertIn('CONFIGURATION_LIBRARY_ACC_ENGINE = "acc_v2_configuration_library"', self.ui)
        self.assertIn("inputObj.run_mode = calculationMode || CONFIGURATION_LIBRARY_DIRECT_CALCULATION_MODE", self.ui)
        self.assertIn("inputObj.acc_engine = CONFIGURATION_LIBRARY_ACC_ENGINE", self.ui)
        self.assertIn("feature_flags.acc_v2_enabled = true", self.ui)
        self.assertIn("inputObj.acc_v2.enabled = true", self.ui)
        self.assertIn("inputObj.acc_v2.configuration_path = activeConfigurationPath", self.ui)
        self.assertNotIn("feature_flags.acc_v2_enabled = false", self.ui)

    def test_configuration_library_run_path_no_longer_branches_to_benchmark_modes(self):
        run_block = self._function_source("runUsingConfigurationLibrary")
        self.assertIn("CONFIGURATION_LIBRARY_DIRECT_CALCULATION_MODE", run_block)
        self.assertIn("applyAccCalculationEngineSelection(adaptedInput, calculationMode, libraryInput.configuration_path)", run_block)
        self.assertIn("Configuration Library path is missing. Please click Load Configuration Library before running.", run_block)
        self.assertIn("await run({ libraryRun: true, libraryInput: adaptedInput });", run_block)
        self.assertNotIn("compute_acc_excel_benchmark", run_block)
        self.assertNotIn("compute_acc_excel_replicated_hourly", run_block)
        self.assertNotIn("compute_acc_experimental_hourly_shape", run_block)

    def test_frontend_rejects_empty_hourly_project_output(self):
        run_block = self._function_source("run")
        self.assertIn("const hourlyRows = Array.isArray(outObj.hourly_results) ? outObj.hourly_results : []", run_block)
        self.assertIn("const isProjectResult = outObj.annual_results && hourlyRows.length > 0", run_block)
        self.assertIn("Solver returned zero hourly rows. No annual results were rendered.", run_block)
        empty_guard = run_block[
            run_block.index("if (outObj.annual_results && Array.isArray(outObj.hourly_results) && hourlyRows.length === 0)"):
            run_block.index("if (isProjectResult)")
        ]
        self.assertNotIn("showProjectVisualization(outObj)", empty_guard)

    def test_frontend_error_output_logs_full_solver_message(self):
        run_block = self._function_source("run")
        self.assertIn("if (outObj.error)", run_block)
        error_block = run_block[
            run_block.index("if (outObj.error)"):
            run_block.index("if (outObj.annual_results && Array.isArray(outObj.hourly_results) && hourlyRows.length === 0)")
        ]
        self.assertIn("const message = String(outObj.error)", error_block)
        self.assertIn("console.error(outObj)", error_block)
        self.assertIn("showRuntimeErrorDetails(message)", error_block)
        self.assertIn("libraryStatus.textContent = message", error_block)
        self.assertIn("Error: ${message}", error_block)
        self.assertIn("log(`Solver error\\n${message}`)", error_block)
        self.assertNotIn("showProjectVisualization(outObj)", error_block)
        self.assertNotIn("showSinglePointVisualization(outObj)", error_block)

    def test_frontend_visible_error_pre_preserves_multiline_diagnostics(self):
        self.assertIn('id="runtimeErrorDetails"', self.index)
        self.assertIn("white-space:pre-wrap", self.index)
        self.assertIn("const elRuntimeErrorDetails = document.getElementById(\"runtimeErrorDetails\")", self.ui)
        self.assertIn("function showRuntimeErrorDetails", self.ui)
        details_block = self._function_source("showRuntimeErrorDetails")
        self.assertIn("textContent = String(message || \"\")", details_block)
        self.assertIn('style.display = "block"', details_block)
        sample = "ACC Solver_Curve missing\\nworkbook path=Configuration Library/ACC_2.xlsx\\nsheet names=['Information']"
        self.assertIn("workbook path", sample)
        self.assertIn("sheet names", sample)

    def test_frontend_pyodide_exception_displays_message_and_stack(self):
        self.assertIn("function formatRuntimeException", self.ui)
        formatter_block = self._function_source("formatRuntimeException")
        self.assertIn("error.stack", formatter_block)
        self.assertIn("`${message}\\n${stack}`", formatter_block)
        run_block = self._function_source("run")
        catch_block = run_block[run_block.index("} catch (e) {"):]
        self.assertIn("const message = formatRuntimeException(e)", catch_block)
        self.assertIn("showRuntimeErrorDetails(message)", catch_block)
        self.assertIn("log(\"❌ Run 失败：\\n\" + message)", catch_block)

    def test_pyodide_loads_direct_mode_python_modules_before_solver(self):
        self.assertIn("function loadPythonModuleIntoPyodide", self.ui)
        self.assertIn("pyodide.FS.writeFile(fileName, text)", self.ui)
        ensure_block = self._function_source("ensurePyodideReady")
        for module_name in (
            "equipment_curve_lookup.py",
            "equipment_curve_reader.py",
            "equipment_engine.py",
            "configuration_manifest.py",
            "configuration_library_loader.py",
            "equipment_registry.py",
            "acc_v2_curve_lookup.py",
            "acc_v2_curve_reader.py",
            "acc_v2_diagnostics.py",
            "acc_v2_engine.py",
            "unit_quantity.py",
        ):
            self.assertIn(f'"{module_name}"', self.ui)
        self.assertLess(ensure_block.index("DIRECT_MODE_PYTHON_MODULES"), ensure_block.index('fetch("./solver.py", { cache: "no-store" })'))
        self.assertLess(ensure_block.index("await loadPythonModuleIntoPyodide(moduleName)"), ensure_block.index("await pyodide.runPythonAsync(pyText)"))

    def test_pyodide_loads_configuration_manifest_before_configuration_library_loader(self):
        module_block = self.ui[
            self.ui.index("const DIRECT_MODE_PYTHON_MODULES"):
            self.ui.index("function log")
        ]
        self.assertIn('"configuration_manifest.py"', module_block)
        self.assertIn('"configuration_library_loader.py"', module_block)
        self.assertLess(
            module_block.index('"configuration_manifest.py"'),
            module_block.index('"configuration_library_loader.py"'),
        )

    def test_frontend_result_area_reports_acc_engine_used(self):
        self.assertIn("function getAccEngineUsedLabel", self.ui)
        self.assertIn("ACC Engine Used:", self.ui)
        self.assertIn("ACC V2 Configuration Library Engine", self.ui)
        self.assertNotIn("ACC V2 unavailable", self.ui)

    def test_solver_rejects_acc_v2_enabled_and_missing_configuration_in_direct_mode(self):
        sample = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        sample["feature_flags"] = {"acc_v2_enabled": True}
        sample["acc_v2"] = {"enabled": True, "configuration_path": "missing-configuration"}

        result = compute_pue_project(sample)

        self.assertIn("error", result)
        self.assertIn("ACC Solver_Curve missing or invalid", result["error"])
        self.assertIn("does not allow ACC legacy fallback", result["error"])

    def _function_source(self, function_name):
        match = re.search(rf"(?:async\s+)?function\s+{re.escape(function_name)}\s*\(", self.ui)
        if not match:
            raise AssertionError(f"function {function_name} not found")
        start = match.start()
        next_match = re.search(r"\n(?:async\s+)?function\s+\w+\s*\(", self.ui[start + 1:])
        end = start + 1 + next_match.start() if next_match else len(self.ui)
        return self.ui[start:end]


if __name__ == "__main__":
    unittest.main()
