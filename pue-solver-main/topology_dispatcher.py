"""Topology dispatcher for Configuration Library solver adapters."""

from importlib import import_module

from topology_registry import get_topology


NOT_IMPLEMENTED_REASON = "Solver module requires validated equipment curves"


class TopologyDispatchError(ValueError):
    """Raised when a topology cannot be dispatched."""


def dispatch_topology(manifest, solver_input):
    """Dispatch manifest-bound input to the topology-specific solver adapter."""
    topology_id = (manifest or {}).get("solver_topology") or (solver_input or {}).get("topology_id")
    if not topology_id:
        raise TopologyDispatchError("Configuration manifest is missing solver_topology.")

    topology = get_topology(topology_id)
    if topology is None:
        raise TopologyDispatchError(f"Unknown solver_topology: {topology_id}")

    adapter_name = topology.get("adapter")
    if not adapter_name:
        return {
            "status": "not_implemented",
            "topology": topology["topology_id"],
            "reason": NOT_IMPLEMENTED_REASON,
        }

    module = import_module(f"topology_adapters.{adapter_name}")
    return module.build_solver_input_from_configuration(manifest, solver_input)
