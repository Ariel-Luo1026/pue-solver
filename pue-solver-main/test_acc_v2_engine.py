import ast
import copy
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import solver
from acc_v2_curve_lookup import ACCOperatingPoint
from acc_v2_engine import (
    ACCV2Engine,
    ACCV2ProductionResult,
    ACCV2ShadowResult,
    create_acc_v2_engine,
    is_acc_v2_enabled,
)
from acc_excel_benchmark import compute_acc_excel_benchmark
from configuration_library_loader import build_solver_input_from_library
from library_solver_adapter import convert_library_input_to_solver_input
from solver import compute_pue_project, get_acc_operating_point, resolve_acc_operating_point, run_acc_v2_shadow
from test_acc_v2_curve_reader import _make_configuration, _replace_pump_with_scenario_curves, _write_xlsx


class ACCV2EngineTest(unittest.TestCase):
    def test_engine_creation(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_valid_configuration(temp_dir)

            engine = create_acc_v2_engine(config)

        self.assertIsInstance(engine, ACCV2Engine)
        self.assertEqual(engine.validation_summary.validation_status, "valid")

    def test_engine_evaluate_operating_point(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_valid_configuration(temp_dir)
            engine = create_acc_v2_engine(config)

            point = engine.evaluate_operating_point(ambient_C=25, load_ratio=0.75)

        self.assertIsInstance(point, ACCOperatingPoint)
        self.assertEqual(point.ambient_C, 25)
        self.assertEqual(point.load_ratio, 0.75)
        self.assertEqual(point.capacity_kW, 1050)

    def test_engine_creation_accepts_chw_pump_scenario_solver_curve_sheets(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_valid_configuration(temp_dir)
            _replace_pump_with_scenario_curves(config)

            engine = create_acc_v2_engine(config)

        self.assertIsInstance(engine, ACCV2Engine)
        self.assertEqual(engine.acc_preview.metadata["selected_solver_curve_sheet"], "Solver_Curve")
        self.assertEqual(
            engine.diagnostic.preview.equipment_curves["pump"].metadata["selected_solver_curve_sheet"],
            "Solver_Curve_Normal",
        )

    def test_engine_creation_does_not_block_acc_lookup_on_non_acc_preview_error(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_valid_configuration(temp_dir)
            pump_folder = Path(config) / "equipment" / "CHW_PUMP_2"
            _write_xlsx(
                pump_folder / "CHW_PUMP_2.xlsx",
                {
                    "Information": [["Parameter", "Value"], ["Equipment", "CHW_PUMP_2"]],
                    "Solver_Curve_Normal": [["flow", "head"], [1, 2]],
                },
            )

            engine = create_acc_v2_engine(config)
            point = engine.evaluate_operating_point(ambient_C=25, load_ratio=0.75)

        self.assertTrue(engine.diagnostic.errors)
        self.assertIsInstance(point, ACCOperatingPoint)
        self.assertEqual(point.capacity_kW, 1050)

    def test_engine_validation_rejects_invalid_configuration(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_configuration(
                temp_dir,
                {
                    "ACC_2": [
                        ["ambient_C", "load_ratio", "capacity_kW", "power_input_kW", "unit_efficiency_kW_per_kW"],
                        [20, 0.5, -1000, 250, 4],
                    ],
                    "RTC_1&2": [["load_ratio", "power_kW"], [0.5, 10]],
                    "CDU_2": [["load_ratio", "power_kW"], [0.5, 13]],
                    "CHW_PUMP_2": [["load_ratio", "power_kW"], [0.5, 20]],
                },
            )

            with self.assertRaisesRegex(ValueError, "ACC V2 diagnostics are invalid"):
                create_acc_v2_engine(config)

    def test_feature_flag_defaults_disabled(self):
        self.assertFalse(is_acc_v2_enabled({}))
        self.assertFalse(is_acc_v2_enabled(None))
        self.assertFalse(is_acc_v2_enabled({"feature_flags": {"acc_v2_enabled": False}}))

    def test_feature_flag_enabled_only_when_explicit_true(self):
        self.assertTrue(is_acc_v2_enabled({"acc_v2_enabled": True}))
        self.assertTrue(is_acc_v2_enabled({"feature_flags": {"acc_v2_enabled": True}}))
        self.assertTrue(is_acc_v2_enabled({"feature_flags": {"acc_v2": True}}))
        self.assertTrue(is_acc_v2_enabled({"acc_v2": {"enabled": True}}))
        self.assertFalse(is_acc_v2_enabled({"acc_v2_enabled": "true"}))

    def test_solver_helper_returns_none_when_disabled(self):
        self.assertIsNone(get_acc_operating_point({}, ambient_C=25, load_ratio=0.75))

    def test_solver_helper_returns_operating_point_when_enabled(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_valid_configuration(temp_dir)

            shadow = get_acc_operating_point(
                {"acc_v2_enabled": True},
                ambient_C=25,
                load_ratio=0.75,
                configuration_path=config,
            )

        self.assertIsInstance(shadow, ACCV2ShadowResult)
        self.assertTrue(shadow.lookup_success)
        self.assertEqual(shadow.capacity_kW, 1050)

    def test_solver_imports_successfully(self):
        self.assertTrue(hasattr(solver, "compute_pue_project"))
        self.assertTrue(hasattr(solver, "get_acc_operating_point"))

    def test_solver_output_unchanged_when_acc_v2_feature_flag_is_disabled(self):
        sample = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        baseline = compute_pue_project(copy.deepcopy(sample))
        disabled = copy.deepcopy(sample)
        disabled["acc_v2_enabled"] = False

        disabled_result = compute_pue_project(disabled)

        self.assertEqual(disabled_result, baseline)

    def test_solver_direct_mode_rejects_acc_v2_enabled_without_configuration(self):
        sample = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        sample["acc_v2_enabled"] = True

        result = compute_pue_project(sample)

        self.assertIn("error", result)
        self.assertIn("ACC Solver_Curve missing or invalid", result["error"])
        self.assertIn("does not allow ACC legacy fallback", result["error"])

    def test_solver_direct_mode_acc_error_includes_workbook_diagnostics(self):
        with TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "ACC_1.5MW_GASENGINE_CDU"
            acc_folder = config / "equipment" / "ACC_2"
            acc_folder.mkdir(parents=True)
            _write_xlsx(acc_folder / "ACC_2.xlsx", {"Information": [["Parameter", "Value"], ["Equipment", "ACC_2"]]})

            sample = convert_library_input_to_solver_input(
                build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
            )
            sample["feature_flags"] = {"acc_v2_enabled": True}
            sample["acc_v2"] = {"enabled": True, "configuration_path": str(config)}

            result = compute_pue_project(sample)

        self.assertIn("error", result)
        self.assertIn("ACC Solver_Curve missing or invalid", result["error"])
        self.assertIn("ACC workbook diagnostics:", result["error"])
        self.assertIn("ACC_2.xlsx", result["error"])
        self.assertIn("file exists=True", result["error"])
        self.assertIn("workbook sheet names=['Information']", result["error"])
        self.assertIn("requested sheet name=Solver_Curve", result["error"])
        self.assertIn("available sheet names=['Information']", result["error"])

    def test_acc_direct_mode_error_recovers_diagnostics_when_result_has_none(self):
        with TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "ACC_1.5MW_GASENGINE_CDU"
            acc_folder = config / "equipment" / "ACC_2"
            acc_folder.mkdir(parents=True)
            _write_xlsx(acc_folder / "ACC_2.xlsx", {"Information": [["Parameter", "Value"], ["Equipment", "ACC_2"]]})

            diagnostics = solver._acc_direct_mode_diagnostics(
                {"acc_v2": {"configuration_path": str(config)}},
                SimpleNamespace(diagnostics=None),
            )

        self.assertIn("ACC workbook diagnostics:", diagnostics)
        self.assertIn("ACC_2.xlsx", diagnostics)
        self.assertIn("workbook sheet names=['Information']", diagnostics)
        self.assertIn("requested sheet name=Solver_Curve", diagnostics)

    def test_run_acc_v2_shadow_returns_none_when_disabled(self):
        self.assertIsNone(run_acc_v2_shadow({}, ambient_C=25, load_ratio=0.75))

    def test_run_acc_v2_shadow_successful_lookup(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_valid_configuration(temp_dir)

            shadow = run_acc_v2_shadow(
                {"acc_v2_enabled": True},
                ambient_C=25,
                load_ratio=0.75,
                configuration_path=config,
            )

        self.assertIsInstance(shadow, ACCV2ShadowResult)
        self.assertTrue(shadow.lookup_success)
        self.assertEqual(shadow.ambient_C, 25)
        self.assertEqual(shadow.load_ratio, 0.75)
        self.assertEqual(shadow.capacity_kW, 1050)
        self.assertEqual(shadow.power_input_kW, 362.5)
        self.assertEqual(shadow.cop, 3.05)

    def test_run_acc_v2_shadow_lookup_failure_is_isolated(self):
        shadow = run_acc_v2_shadow(
            {"acc_v2_enabled": True},
            ambient_C=25,
            load_ratio=0.75,
            configuration_path="missing-configuration",
        )

        self.assertIsInstance(shadow, ACCV2ShadowResult)
        self.assertFalse(shadow.lookup_success)
        self.assertTrue(shadow.validation_errors)

    def test_run_acc_v2_shadow_validation_failure_is_isolated(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_configuration(
                temp_dir,
                {
                    "ACC_2": [
                        ["ambient_C", "load_ratio", "capacity_kW", "power_input_kW", "unit_efficiency_kW_per_kW"],
                        [20, 0.5, -1000, 250, 4],
                    ],
                    "RTC_1&2": [["load_ratio", "power_kW"], [0.5, 10]],
                    "CDU_2": [["load_ratio", "power_kW"], [0.5, 13]],
                    "CHW_PUMP_2": [["load_ratio", "power_kW"], [0.5, 20]],
                },
            )

            shadow = run_acc_v2_shadow(
                {"acc_v2_enabled": True},
                ambient_C=20,
                load_ratio=0.5,
                configuration_path=config,
            )

        self.assertFalse(shadow.lookup_success)
        self.assertTrue(any("diagnostics are invalid" in error for error in shadow.validation_errors))

    def test_run_acc_v2_shadow_exception_isolation(self):
        shadow = run_acc_v2_shadow(
            {"acc_v2_enabled": True},
            ambient_C=None,
            load_ratio=0.5,
            configuration_path="not-used",
        )

        self.assertFalse(shadow.lookup_success)
        self.assertIn("missing configuration_path", shadow.validation_errors[0])

    def test_benchmark_result_unchanged_with_feature_flag_present(self):
        sample = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        baseline = compute_acc_excel_benchmark(copy.deepcopy(sample))
        enabled = copy.deepcopy(sample)
        enabled["acc_v2_enabled"] = True

        result = compute_acc_excel_benchmark(enabled)

        self.assertEqual(result, baseline)

    def test_resolve_acc_operating_point_feature_flag_off_returns_legacy(self):
        result = resolve_acc_operating_point(
            {},
            _legacy_acc_curve(),
            load_ratio=0.75,
            cooling_load_kw=1000,
            active_units=2,
            oat_c=25,
        )

        self.assertIsInstance(result, ACCV2ProductionResult)
        self.assertNotEqual(result.source, "acc_v2")
        self.assertFalse(result.lookup_success)
        self.assertFalse(result.fallback_used)
        self.assertEqual(result.engine_version, "legacy")
        self.assertIsNotNone(result.power_input_kW)

    def test_resolve_acc_operating_point_feature_flag_on_success_uses_acc_v2(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_valid_configuration(temp_dir)

            result = resolve_acc_operating_point(
                {"acc_v2_enabled": True},
                _legacy_acc_curve(),
                load_ratio=0.75,
                cooling_load_kw=1000,
                active_units=2,
                oat_c=25,
                configuration_path=config,
            )

        self.assertTrue(result.lookup_success)
        self.assertFalse(result.fallback_used)
        self.assertEqual(result.source, "acc_v2")
        self.assertEqual(result.capacity_kW, 1050)
        self.assertEqual(result.power_input_kW, 725.0)
        self.assertAlmostEqual(result.cop, 3.05)

    def test_resolve_acc_operating_point_fallback_when_v2_lookup_fails(self):
        result = resolve_acc_operating_point(
            {"acc_v2_enabled": True},
            _legacy_acc_curve(),
            load_ratio=0.75,
            cooling_load_kw=1000,
            active_units=2,
            oat_c=25,
            configuration_path="missing-configuration",
        )

        self.assertFalse(result.lookup_success)
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.engine_version, "legacy")
        self.assertNotEqual(result.source, "acc_v2")
        self.assertIsNotNone(result.power_input_kW)

    def test_solver_execution_successfully_consumes_acc_v2_when_enabled(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_valid_configuration(temp_dir)
            sample = convert_library_input_to_solver_input(
                build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
            )
            sample["acc_v2_enabled"] = True
            sample["acc_v2"] = {"configuration_path": str(config)}

            result = compute_pue_project(sample)

        self.assertNotIn("error", result)
        self.assertEqual(result["hourly_results"][0]["acc_curve_source"], "acc_v2_solver_curve_direct")

    def test_solver_reuses_acc_v2_engine_for_annual_project_run(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_valid_configuration(temp_dir)
            sample = convert_library_input_to_solver_input(
                build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
            )
            sample["acc_v2_enabled"] = True
            sample["acc_v2"] = {"configuration_path": str(config)}

            with patch("acc_v2_engine.create_acc_v2_engine", wraps=create_acc_v2_engine) as mocked_create:
                result = compute_pue_project(sample)

        self.assertNotIn("error", result)
        self.assertEqual(len(result["hourly_results"]), 8760)
        self.assertEqual(mocked_create.call_count, 1)

    def test_solver_does_not_create_acc_v2_engine_when_feature_flag_disabled(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_valid_configuration(temp_dir)
            sample = convert_library_input_to_solver_input(
                build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
            )
            sample["acc_v2"] = {"configuration_path": str(config)}

            with patch("acc_v2_engine.create_acc_v2_engine", wraps=create_acc_v2_engine) as mocked_create:
                result = compute_pue_project(sample)

        self.assertNotIn("error", result)
        self.assertEqual(mocked_create.call_count, 0)

    def test_cached_acc_v2_resolver_matches_uncached_resolver(self):
        with TemporaryDirectory() as temp_dir:
            config = _make_valid_configuration(temp_dir)
            engine = create_acc_v2_engine(config)
            project_input = {"acc_v2_enabled": True}

            uncached = resolve_acc_operating_point(
                project_input,
                _legacy_acc_curve(),
                load_ratio=0.75,
                cooling_load_kw=1000,
                active_units=2,
                oat_c=25,
                configuration_path=config,
            )
            cached = resolve_acc_operating_point(
                project_input,
                _legacy_acc_curve(),
                load_ratio=0.75,
                cooling_load_kw=1000,
                active_units=2,
                oat_c=25,
                configuration_path=config,
                acc_v2_engine=engine,
            )

        self.assertEqual(cached, uncached)

    def test_solver_direct_mode_rejects_invalid_acc_v2_without_legacy_fallback(self):
        sample = convert_library_input_to_solver_input(
            build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal")
        )
        sample["acc_v2_enabled"] = True
        sample["acc_v2"] = {"configuration_path": "missing-configuration"}

        result = compute_pue_project(sample)

        self.assertIn("error", result)
        self.assertIn("ACC Solver_Curve missing or invalid", result["error"])
        self.assertIn("does not allow ACC legacy fallback", result["error"])
        self.assertEqual(result["hourly_results"], [])

    def test_benchmark_path_not_imported_by_engine(self):
        engine_source = Path(__file__).with_name("acc_v2_engine.py").read_text(encoding="utf-8")
        tree = ast.parse(engine_source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)

        self.assertNotIn("acc_excel_benchmark", imports)


def _make_valid_configuration(root):
    return _make_configuration(
        root,
        {
            "ACC_2": [
                ["ambient_C", "load_ratio", "capacity_kW", "power_input_kW", "unit_efficiency_kW_per_kW"],
                [20, 0.5, 1000, 250, 4],
                [20, 1.0, 1200, 400, 3],
                [30, 0.5, 900, 300, 3],
                [30, 1.0, 1100, 500, 2.2],
            ],
            "RTC_1&2": [["load_ratio", "power_kW"], [0.5, 10], [1.0, 20]],
            "CDU_2": [["load_ratio", "power_kW"], [0.5, 13], [1.0, 13]],
            "CHW_PUMP_2": [["load_ratio", "power_kW"], [0.5, 20], [1.0, 60]],
        },
    )


def _legacy_acc_curve():
    return {
        "equipment_id": "ACC_2",
        "source_sheet": "Solver_Curve",
        "data": [
            {"ambient_C": 20, "load_ratio": 0.5, "power_input_kW": 100, "capacity_kW": 1000, "COP": 10},
            {"ambient_C": 30, "load_ratio": 1.0, "power_input_kW": 200, "capacity_kW": 1000, "COP": 5},
        ],
    }


if __name__ == "__main__":
    unittest.main()
