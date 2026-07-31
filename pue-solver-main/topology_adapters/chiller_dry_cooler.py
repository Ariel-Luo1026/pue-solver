"""Topology adapter for Chiller + Dry Cooler Configuration Library packages."""


def build_solver_input_from_configuration(manifest, solver_input):
    from topology_adapters.chiller_dry_cooler_runtime import ChillerDryCoolerRuntime

    return ChillerDryCoolerRuntime(manifest, solver_input).run_annual()
