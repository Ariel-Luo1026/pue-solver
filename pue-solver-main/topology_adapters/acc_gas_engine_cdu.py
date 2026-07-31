"""ACC + gas engine + CDU Configuration Library adapter routing."""


CONFIGURATION_LIBRARY_DIRECT_CALCULATION_MODE = "acc_v2_direct_solver_curve_hourly"
CONFIGURATION_LIBRARY_ACC_ENGINE = "acc_v2_configuration_library"


def build_solver_input_from_configuration(manifest, equipment_roles):
    """Run the existing ACC solver path through topology dispatch.

    The adapter preserves the existing ACC input builder and compute_pue_project
    calculation path. It only owns topology routing and ACC V2 direct-mode
    metadata that the frontend previously injected.
    """
    from library_solver_adapter import _build_acc_gas_engine_cdu_solver_input
    from solver import compute_pue_project

    solver_input = _build_acc_gas_engine_cdu_solver_input(equipment_roles)
    _apply_acc_configuration_library_engine_selection(solver_input, manifest)
    result = compute_pue_project(solver_input)
    if isinstance(result, dict) and "error" not in result:
        _attach_acc_performance_results(result, manifest, solver_input)
        result.setdefault("status", "success")
        result.setdefault("topology_id", "acc_gas_engine_cdu")
        result.setdefault("solver_dispatch_key", "acc_gas_engine_cdu")
        result.setdefault("report_profile", solver_input.get("report_profile"))
        result.setdefault("configuration_id", solver_input.get("configuration_id"))
        result.setdefault("configuration_display_name", solver_input.get("configuration_display_name"))
        result.setdefault("implementation_status", solver_input.get("implementation_status"))
    return result


def build_acc_solver_input_from_configuration(manifest, equipment_roles):
    """Build the preserved ACC solver input for regression comparison tests."""
    from library_solver_adapter import _build_acc_gas_engine_cdu_solver_input

    solver_input = _build_acc_gas_engine_cdu_solver_input(equipment_roles)
    _apply_acc_configuration_library_engine_selection(solver_input, manifest)
    return solver_input


def _apply_acc_configuration_library_engine_selection(solver_input, manifest=None):
    solver_input["run_mode"] = CONFIGURATION_LIBRARY_DIRECT_CALCULATION_MODE
    solver_input["acc_engine"] = CONFIGURATION_LIBRARY_ACC_ENGINE
    feature_flags = solver_input.get("feature_flags")
    if not isinstance(feature_flags, dict):
        feature_flags = {}
    feature_flags["acc_v2_enabled"] = True
    solver_input["feature_flags"] = feature_flags

    acc_v2 = solver_input.get("acc_v2")
    if not isinstance(acc_v2, dict):
        acc_v2 = {}
    acc_v2["enabled"] = True
    configuration_path = _resolve_configuration_path(solver_input, manifest)
    if configuration_path:
        acc_v2["configuration_path"] = str(configuration_path)
    solver_input["acc_v2"] = acc_v2
    return solver_input


def _resolve_configuration_path(solver_input, manifest=None):
    explicit = solver_input.get("configuration_path")
    if explicit:
        return explicit
    configuration_id = (
        (manifest or {}).get("configuration_id")
        or solver_input.get("configuration_id")
        or solver_input.get("configuration_name")
        or (solver_input.get("project") or {}).get("name")
    )
    if not configuration_id:
        return None
    try:
        from configuration_library_loader import DEFAULT_LIBRARY_ROOT

        candidate = DEFAULT_LIBRARY_ROOT / str(configuration_id)
        if candidate.exists():
            return candidate
    except Exception:
        pass
    return configuration_id


def _attach_acc_performance_results(result, manifest=None, solver_input=None):
    """Attach standardized ACC performance payloads from existing hourly output."""
    from copy import deepcopy

    from energy_aggregation import AnnualEnergyAggregationError, aggregate_annual_energy
    from equipment_performance.acc_adapter import performance_result_from_legacy_acc_row

    hourly_results = result.get("hourly_results")
    if not isinstance(hourly_results, list):
        return result

    equipment_id = _acc_equipment_id(manifest, solver_input)
    for row in hourly_results:
        if not isinstance(row, dict) or isinstance(row.get("acc_performance_result"), dict):
            continue
        row["acc_performance_result"] = performance_result_from_legacy_acc_row(
            row,
            equipment_id=equipment_id,
        ).to_dict()

    try:
        result["standard_annual_energy"] = aggregate_annual_energy({"hourly_results": hourly_results})
    except AnnualEnergyAggregationError as exc:
        warnings = result.setdefault("warnings", [])
        if isinstance(warnings, list):
            warnings.append(f"ACC PerformanceResult annual aggregation unavailable: {exc}")

    library_context = result.get("library_context")
    if not isinstance(library_context, dict):
        library_context = {}
    migration = library_context.setdefault("performance_result_migration", {})
    migration.update({
        "acc_performance_result": "attached_from_existing_solver_hourly_output",
        "calculation_formulas_changed": False,
        "equipment_id": equipment_id,
    })
    result["library_context"] = deepcopy(library_context)
    return result


def _acc_equipment_id(manifest=None, solver_input=None):
    roles = (manifest or {}).get("equipment_roles")
    if isinstance(roles, dict):
        equipment_id = roles.get("primary_cooling")
        if equipment_id:
            return equipment_id
    acc_curve = (solver_input or {}).get("acc_curve")
    if isinstance(acc_curve, dict) and acc_curve.get("equipment_id"):
        return acc_curve["equipment_id"]
    return "ACC"
