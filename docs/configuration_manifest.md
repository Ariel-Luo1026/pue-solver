# Configuration Library Manifest

`configuration_manifest.json` describes whether a Configuration Library folder is runnable and which topology/equipment roles it declares. It is architecture metadata only; it must not contain fabricated equipment performance data.

## Location

Each configuration folder can provide:

```text
Configuration Library/<configuration_id>/configuration_manifest.json
```

The browser catalog is listed in:

```text
Configuration Library/configuration_library_index.json
```

## Required Fields

- `schema_version`: manifest schema version, currently `1.0`.
- `configuration_id`: folder/configuration ID.
- `display_name`: user-facing label.
- `cooling_system_type`: registered topology ID, such as `acc_gas_engine_cdu`.
- `implementation_status`: one of the supported status values below.
- `description`: short developer-facing description.
- `equipment_roles`: object mapping topology roles to equipment folder IDs.
- `required_roles`: roles required by the topology/configuration.
- `optional_roles`: roles that may be omitted.
- `solver_topology`: registered topology used for solver dispatch.
- `report_profile`: report profile key.

## Status Values

- `implemented`: full frontend -> library -> solver -> annual result -> report path exists.
- `framework_ready_data_missing`: topology framework exists, but manufacturer `Solver_Curve` data or complete bindings are missing.
- `placeholder`: planning metadata only.
- `disabled`: do not present as runnable.

Only `implemented` configurations may execute.

## Equipment Roles

Roles decouple topology intent from specific equipment folders. For the current ACC path:

- `primary_cooling`: `ACC_2`
- `chw_pump`: `CHW_PUMP_2`
- `cdu`: `CDU_2`
- `rtc`: `RTC_1&2`
- `mau`: `MAU_1&2`
- `engine`: `ENGINE_3`
- `engine_radiator`: `ENGINE_RADIATOR_1`
- `electrical_distribution`: `ELECTRICAL_DISTRIBUTION_2`

Implemented configurations must bind every required role to a non-empty equipment ID that exists in the loaded configuration packages.

## Topology Validation

Manifest loading validates that:

- `implementation_status` is known.
- `cooling_system_type` and `solver_topology` are registered topology IDs.
- implemented manifests reference implemented topologies.
- manifest required roles include the topology-required roles.
- implemented manifests bind every required role.

If a placeholder or data-missing configuration is selected, execution fails with a clear status-specific message.

## Adding Future Configurations

1. Register or update the topology in `topology_registry.py`.
2. Add a `configuration_manifest.json` to the configuration folder.
3. Add the manifest path to `Configuration Library/configuration_library_index.json` if the browser should discover it.
4. Keep `implementation_status` as `placeholder` or `framework_ready_data_missing` until the full annual solver path and real manufacturer `Solver_Curve` data exist.
5. Do not invent manufacturer performance data to make a topology appear implemented.

`framework_ready_data_missing` means the software path is being prepared but cannot yet produce validated manufacturer-data results. `implemented` means the configuration is runnable end to end.
