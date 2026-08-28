"""Annual runtime for Chiller + Dry Cooler Configuration Library topologies."""

from copy import deepcopy

from cooling_load_model import calculate_annual_cooling_load, calculate_peak_design_condition
from capacity_validation import validate_peak_capacity
from energy_aggregation import aggregate_annual_energy
from equipment_engine import ConfigurationLibraryEquipmentEngine, EquipmentEngineConfig
from equipment_performance import dispatch_performance_adapter
from equipment_role_resolver import resolve_equipment_role_id, validate_required_equipment_roles
from indoor_equipment import evaluate_indoor_equipment, project_it_load_ratio
from unit_scenario_manager import resolve_unit_scenario
from pump_load_framework import (
    calculate_failure_peak_pump_reference,
    evaluate_pump_power,
    resolve_pump_reference_capacity,
)
from generation_side_equipment import (
    evaluate_engine_generation,
    evaluate_engine_radiator,
    gas_engine_roles_for_power_source,
    linear_curve_value,
)


class ChillerDryCoolerRuntimeError(ValueError):
    """Raised when the chiller + dry cooler runtime cannot evaluate input."""


CHW_PUMP_ROLE = "chw_pump"
CW_PUMP_ROLE = "cw_pump"


class ChillerDryCoolerRuntime:
    """Run an independent annual 8760 simulation for chiller + dry cooler packages."""

    DEFAULT_DRY_COOLER_APPROACH_C = 5.0

    def __init__(self, manifest, configuration_context):
        self.manifest = manifest or {}
        self.context = configuration_context or {}
        self.selected_curves = self.context.get("selected_curves") or {}
        validate_required_equipment_roles(self.manifest, self.selected_curves)
        self.power_source = self.context.get("power_source") or self.manifest.get("power_source") or "Grid"
        generation_roles = gas_engine_roles_for_power_source(
            self.manifest, self.selected_curves, self.power_source
        )
        self.engine_id = generation_roles.engine if generation_roles else None
        self.engine_radiator_id = generation_roles.engine_radiator if generation_roles else None
        self.gas_engine_enabled = generation_roles is not None
        self.engine_radiator_reference_kw = None

        self.chiller_id = resolve_equipment_role_id(self.manifest, "chiller", self.selected_curves)
        self.dry_cooler_id = resolve_equipment_role_id(self.manifest, "dry_cooler", self.selected_curves)
        self.pump_id = resolve_equipment_role_id(self.manifest, "chw_pump", self.selected_curves)
        self.cw_pump_id = resolve_equipment_role_id(self.manifest, "cw_pump", self.selected_curves)
        self.electrical_id = resolve_equipment_role_id(
            self.manifest, "electrical_distribution", self.selected_curves
        )
        self.indoor_equipment_ids = (
            resolve_equipment_role_id(self.manifest, "indoor_cooling", self.selected_curves)
            if "indoor_cooling" in (self.manifest.get("equipment_roles") or {})
            else []
        ) or []
        if not isinstance(self.indoor_equipment_ids, list):
            self.indoor_equipment_ids = [self.indoor_equipment_ids]
        self.indoor_bindings = {
            self._indoor_role(equipment_id): self._equipment_binding(equipment_id)
            for equipment_id in self.indoor_equipment_ids
        }

        self.chiller_adapter = dispatch_performance_adapter(
            self._equipment_metadata(self.chiller_id, "chiller", "CHILLER", "cop_curve"),
            curve_data=self._curve_rows(self.chiller_id),
        )
        self.dry_cooler_adapter = dispatch_performance_adapter(
            self._equipment_metadata(self.dry_cooler_id, "dry_cooler", "DRY_COOLER", "outdoor_temperature_power"),
            curve_data=self._curve_rows(self.dry_cooler_id),
            capacity_curve_data=self._equipment_binding(self.dry_cooler_id).get("performance_map"),
        )
        self.generic_engine = ConfigurationLibraryEquipmentEngine(
            EquipmentEngineConfig(preloaded_curves=self._generic_preloaded_curves())
        )
        self.pump_reference_capacity_kw = None
        self.pump_reference_capacity_source = None
        self.pump_reference_diagnostics = None
        dry_cooler_information = self._equipment_binding(self.dry_cooler_id).get("information") or {}
        dry_cooler_metadata = self._equipment_metadata(self.dry_cooler_id, "dry_cooler", "DRY_COOLER", "ambient_capacity_power")
        self.cw_pump_reference_capacity_kw, self.cw_pump_reference_capacity_source = resolve_pump_reference_capacity(
            role_metadata=(self.context.get("role_bindings") or {}).get("cw_pump")
            or (self.manifest.get("role_metadata") or {}).get("cw_pump"),
            equipment_metadata=self._equipment_metadata(self.cw_pump_id, "cw_pump", "CW_PUMP", "load_ratio_power"),
            associated_equipment_capacity_kW=dry_cooler_information.get("Design Capacity") or dry_cooler_metadata.get("rated_capacity_kW"),
        )

    def run_annual(self):
        project = self.context.get("project") or {}
        cooling_model = calculate_annual_cooling_load(self.context)
        cooling_rows = cooling_model["hourly_cooling_load"]
        hours = len(cooling_rows)

        design_it = float(
            project.get("design_it_load_kW")
            or max((row["it_load_kW"] for row in cooling_rows), default=0.0)
            or 0.0
        )
        if design_it <= 0:
            raise ChillerDryCoolerRuntimeError("project.design_it_load_kW must be greater than 0.")
        chiller_unit_capacity_kw = float(project.get("cooling_unit_capacity_kW") or 0.0)
        if chiller_unit_capacity_kw <= 0:
            raise ChillerDryCoolerRuntimeError("project.cooling_unit_capacity_kW must be greater than 0.")
        unit_scenario = self._unit_scenario(design_it, chiller_unit_capacity_kw)
        failure_scenario = resolve_unit_scenario(
            design_it,
            chiller_unit_capacity_kw,
            scenario_name="Failure",
            scenario_formula="required_units",
        )
        failure_roles = failure_scenario.get("role_quantities") or {}
        failure_active_pump_units = self._active_role_units(
            failure_roles,
            "chw_pump_units",
            self._active_role_units(
                failure_roles, "pump_units", failure_scenario["active_units"]
            ),
        )
        peak_design = calculate_peak_design_condition(self.context)
        self.pump_reference_diagnostics = calculate_failure_peak_pump_reference(
            design_it,
            peak_design["peak_design_solar_heat_gain_kW"],
            peak_design["peak_design_other_auxiliary_heat_gain_kW"],
            failure_active_pump_units,
        )
        self.pump_reference_capacity_kw = self.pump_reference_diagnostics[
            "pump_reference_capacity_kW"
        ]
        self.pump_reference_capacity_source = self.pump_reference_diagnostics[
            "pump_reference_basis"
        ]
        roles = unit_scenario.get("role_quantities") or {}
        active_chiller_units = self._active_role_units(roles, "chiller_units", unit_scenario["active_units"])
        active_dry_cooler_units = self._active_role_units(roles, "dry_cooler_units", unit_scenario["active_units"])
        active_pump_units = self._active_role_units(roles, "chw_pump_units", self._active_role_units(roles, "pump_units", unit_scenario["active_units"]))
        cw_pump_role = roles.get("cw_pump_units") or {}
        active_cw_pump_units = self._non_negative_role_units(cw_pump_role, unit_scenario["active_units"])
        indoor_role = roles.get("indoor_units") or {}
        indoor_active_units = self._non_negative_role_units(indoor_role, unit_scenario["installed_units"])
        engine_role = roles.get("engine_units") or {}
        engine_active_units = self._non_negative_role_units(engine_role, unit_scenario["active_units"])
        project_engine_units = project.get("engine_active_units")
        if project_engine_units is not None:
            engine_active_units = self._non_negative_role_units(
                {"active_units": project_engine_units}, engine_active_units
            )
        engine_radiator_active_units = engine_active_units
        project_radiator_units = project.get("engine_radiator_active_units")
        if project_radiator_units is not None:
            engine_radiator_active_units = self._non_negative_role_units(
                {"active_units": project_radiator_units}, engine_active_units
            )
        dry_cooler_approach_c = self._dry_cooler_approach_c()
        if self.gas_engine_enabled:
            self.engine_radiator_reference_kw = self._failure_peak_non_radiator_reference(
                design_it,
                chiller_unit_capacity_kw,
                dry_cooler_approach_c,
            )

        hourly_results = []
        totals = {
            "it": 0.0,
            "cooling_load": 0.0,
            "solar_heat_gain": 0.0,
            "other_auxiliary_heat_gain": 0.0,
            "facility": 0.0,
            "chiller": 0.0,
            "dry_cooler": 0.0,
            "pump": 0.0,
            "cw_pump": 0.0,
            "cdu": 0.0,
            "rtc": 0.0,
            "mau": 0.0,
            "white_space": 0.0,
            "electrical_loss": 0.0,
            "it_electrical_loss": 0.0,
            "mep_electrical_loss": 0.0,
            "engine_output": 0.0,
            "engine_fuel": 0.0,
            "engine_waste_heat": 0.0,
            "engine_radiator": 0.0,
        }

        for index, load_row in enumerate(cooling_rows):
            row = self._evaluate_operating_point(
                load_row,
                design_it,
                chiller_unit_capacity_kw,
                active_chiller_units,
                active_dry_cooler_units,
                active_pump_units,
                active_cw_pump_units,
                indoor_active_units,
                dry_cooler_approach_c,
                engine_active_units,
                engine_radiator_active_units,
                self.engine_radiator_reference_kw,
                hour=index + 1,
            )
            hourly_results.append(row)
            row.update({
                "installed_cw_pumps": int(cw_pump_role.get("installed_units", active_cw_pump_units)),
                "active_cw_pumps": active_cw_pump_units,
                "standby_cw_pumps": int(cw_pump_role.get("standby_units", 0)),
                "failed_cw_pumps": int(unit_scenario.get("failed_units", 0)),
            })
            totals["it"] += row["it_load_kW"]
            totals["cooling_load"] += row["cooling_load_kW"]
            totals["solar_heat_gain"] += load_row["solar_heat_gain_kW"]
            totals["other_auxiliary_heat_gain"] += load_row["other_auxiliary_heat_gain_kW"]
            totals["facility"] += row["facility_power_kW"]
            totals["chiller"] += row["chiller_power_kW"]
            totals["dry_cooler"] += row["dry_cooler_power_kW"]
            totals["pump"] += row["pump_power_kW"]
            totals["cw_pump"] += row["cw_pump_power_total_kW"]
            totals["cdu"] += row["cdu_power_kW"]
            totals["rtc"] += row["rtc_power_kW"]
            totals["mau"] += row["mau_power_kW"]
            totals["white_space"] += row["white_space_equipment_power_kW"]
            totals["electrical_loss"] += row["electrical_loss_kW"]
            totals["it_electrical_loss"] += row["it_electrical_loss_kW"]
            totals["mep_electrical_loss"] += row["mep_electrical_loss_kW"]
            totals["engine_output"] += row["engine_output_kW"]
            totals["engine_fuel"] += row["engine_fuel_input_kW"]
            totals["engine_waste_heat"] += row["engine_waste_heat_kW"]
            totals["engine_radiator"] += row["engine_radiator_power_kW"]

        annual_average_pue = totals["facility"] / totals["it"] if totals["it"] > 0 else 0.0
        dry_cooler_curve_rows = self._curve_rows(self.dry_cooler_id)
        dry_cooler_curve_powers = [float(row["power_kW"]) for row in dry_cooler_curve_rows if isinstance(row, dict) and isinstance(row.get("power_kW"), (int, float))]
        annual_results = {
            "annual_average_PUE": annual_average_pue,
            "annual_IT_energy_kWh": totals["it"],
            "annual_facility_energy_kWh": totals["facility"],
            "annual_chiller_energy_kWh": totals["chiller"],
            "annual_dry_cooler_energy_kWh": totals["dry_cooler"],
            "max_dry_cooler_total_power_kW": max((row["dry_cooler_power_total_kW"] for row in hourly_results), default=0.0),
            "dry_cooler_temperature_clamp_hours": sum(1 for row in hourly_results if row["dry_cooler_temperature_clamped_low"] or row["dry_cooler_temperature_clamped_high"]),
            "dry_cooler_curve_min_temperature_C": hourly_results[0]["dry_cooler_curve_min_temperature_C"] if hourly_results else None,
            "dry_cooler_curve_max_temperature_C": hourly_results[0]["dry_cooler_curve_max_temperature_C"] if hourly_results else None,
            "dry_cooler_curve_min_power_kW": min(dry_cooler_curve_powers) if dry_cooler_curve_powers else None,
            "dry_cooler_rated_power_cap_kW": max(dry_cooler_curve_powers) if dry_cooler_curve_powers else None,
            "annual_pump_energy_kWh": totals["pump"],
            "annual_chw_pump_energy_kWh": totals["pump"],
            "annual_cw_pump_energy_kWh": totals["cw_pump"],
            "annual_cdu_energy_kWh": totals["cdu"],
            "annual_rtc_energy_kWh": totals["rtc"],
            "annual_mau_energy_kWh": totals["mau"],
            "annual_white_space_equipment_energy_kWh": totals["white_space"],
            "annual_electrical_loss_kWh": totals["electrical_loss"],
            "annual_it_electrical_loss_kWh": totals["it_electrical_loss"],
            "annual_mep_electrical_loss_kWh": totals["mep_electrical_loss"],
            "annual_engine_output_kWh": totals["engine_output"],
            "annual_engine_energy_kWh": totals["engine_output"],
            "annual_engine_fuel_input_kWh": totals["engine_fuel"],
            "annual_engine_waste_heat_kWh": totals["engine_waste_heat"],
            "average_engine_efficiency": (
                totals["engine_output"] / totals["engine_fuel"]
                if totals["engine_fuel"] > 0 else None
            ),
            "annual_engine_radiator_energy_kWh": totals["engine_radiator"],
            "max_engine_radiator_power_kW": max(
                (row["engine_radiator_power_kW"] for row in hourly_results), default=0.0
            ),
            "annual_solar_heat_gain_kWh": totals["solar_heat_gain"],
            "annual_other_auxiliary_heat_gain_kWh": totals["other_auxiliary_heat_gain"],
            "annual_cooling_load_kWh": totals["cooling_load"],
            "annual_total_cooling_system_energy_kWh": totals["chiller"] + totals["dry_cooler"] + totals["pump"] + totals["cw_pump"] + totals["white_space"] + totals["engine_radiator"],
        }
        standard_annual_energy = aggregate_annual_energy({"hourly_results": hourly_results})
        peak_results = self._peak_design_results(
            design_it,
            chiller_unit_capacity_kw,
            active_chiller_units,
            active_dry_cooler_units,
            active_pump_units,
            active_cw_pump_units,
            indoor_active_units,
            dry_cooler_approach_c,
            engine_active_units,
            engine_radiator_active_units,
            self.engine_radiator_reference_kw,
        )
        capacity_validation = self._capacity_validation(
            peak_results,
            unit_scenario,
            chiller_unit_capacity_kw,
            active_chiller_units,
            active_dry_cooler_units,
        )
        return {
            "status": "success",
            "configuration_id": self.context.get("configuration_id") or self.manifest.get("configuration_id"),
            "configuration_display_name": self.context.get("configuration_display_name")
            or self.manifest.get("display_name"),
            "cooling_system_type": self.context.get("cooling_system_type") or self.manifest.get("cooling_system_type"),
            "power_source": self.power_source,
            "topology_id": "chiller_dry_cooler",
            "solver_dispatch_key": "chiller_dry_cooler",
            "report_profile": self.context.get("report_profile") or self.manifest.get("report_profile"),
            "implementation_status": self.context.get("implementation_status") or "implemented",
            "scenario_name": self.context.get("scenario_name"),
            "annual_results": annual_results,
            "standard_annual_energy": standard_annual_energy,
            "peak_results": peak_results,
            "capacity_validation": capacity_validation,
            "hourly_results": hourly_results,
            "library_context": {
                "configuration_manifest": deepcopy(self.manifest),
                "equipment_ids": {
                    "chiller": self.chiller_id,
                    "dry_cooler": self.dry_cooler_id,
                    "chw_pump": self.pump_id,
                    "cw_pump": self.cw_pump_id,
                    "indoor_cooling": deepcopy(self.indoor_equipment_ids),
                    "engine": self.engine_id,
                    "engine_radiator": self.engine_radiator_id,
                    "electrical_distribution": self.electrical_id,
                },
                "selected_curves": deepcopy(self.selected_curves),
                "runtime_assumptions": {
                    "dry_cooler_approach_C": dry_cooler_approach_c,
                    "cooling_load_model": "shared_cooling_load_model",
                    "unit_scenario": deepcopy(unit_scenario),
                    "facility_power_formula": "IT + chiller + dry_cooler + CHW pump + CW pump + indoor equipment + Engine Radiator + electrical loss",
                    "engine_output_boundary": "generation_side_excluded_from_facility_power",
                    "engine_radiator_reference_power_kW": self.engine_radiator_reference_kw,
                },
            },
        }

    def _evaluate_operating_point(
        self,
        load_row,
        design_it,
        chiller_unit_capacity_kw,
        active_chiller_units,
        active_dry_cooler_units,
        active_pump_units,
        active_cw_pump_units,
        indoor_active_units,
        dry_cooler_approach_c,
        engine_active_units=0,
        engine_radiator_active_units=0,
        engine_radiator_reference_kw=None,
        include_generation=True,
        hour=None,
    ):
        """Evaluate annual and peak-design points through one equipment path."""
        it_kw = float(load_row["it_load_kW"])
        ambient_c = float(load_row["ambient_dry_bulb_C"])
        cooling_load_kw = float(load_row["cooling_load_kW"])
        load_ratio = cooling_load_kw / design_it if design_it else 0.0
        indoor_load_ratio = project_it_load_ratio(it_kw, design_it)
        ceft_c = ambient_c + dry_cooler_approach_c
        required_capacity_per_chiller_unit_kw = cooling_load_kw / active_chiller_units
        chiller_per_unit = self._chiller_performance(
            required_capacity_per_chiller_unit_kw,
            chiller_unit_capacity_kw,
            ceft_c,
        )
        chiller_perf = chiller_per_unit.performance
        chiller_power_kw = chiller_perf["power_kW"] * active_chiller_units
        heat_rejection_kw = cooling_load_kw + chiller_power_kw
        heat_rejection_per_dry_cooler_unit_kw = heat_rejection_kw / active_dry_cooler_units
        dry_cooler_per_unit = self._dry_cooler_performance(
            heat_rejection_per_dry_cooler_unit_kw,
            ambient_c,
        )
        dry_cooler_perf = dry_cooler_per_unit.performance
        dry_cooler_power_lookup = dry_cooler_per_unit.diagnostics.get("power_lookup") or {}
        dry_cooler_power_kw = dry_cooler_perf["power_kW"] * active_dry_cooler_units
        pump = self._pump_power(cooling_load_kw, active_pump_units)
        pump_power_kw = pump["pump_power_total_kW"]
        cw_pump = self._cw_pump_power(heat_rejection_kw, active_cw_pump_units)
        cw_pump_power_kw = cw_pump["pump_power_total_kW"]
        indoor_power = evaluate_indoor_equipment(
            self.indoor_bindings,
            indoor_load_ratio,
            indoor_active_units,
            self._lookup_indoor_power_per_unit,
        )
        white_space_power_kw = indoor_power["white_space_equipment_power_kW"]
        non_radiator_mep_kw = (
            chiller_power_kw + dry_cooler_power_kw + pump_power_kw
            + cw_pump_power_kw + white_space_power_kw
        )
        non_radiator_electrical_loss_kw = self._electrical_loss(
            load_ratio,
            it_kw=it_kw,
            mep_kw=non_radiator_mep_kw,
        )
        non_radiator_facility_power_kw = (
            it_kw + non_radiator_mep_kw + non_radiator_electrical_loss_kw
        )
        engine_result = {
            "output_kW": 0.0,
            "efficiency": None,
            "fuel_input_kW": 0.0,
            "waste_heat_kW": 0.0,
        }
        radiator_result = {
            "load_ratio": 0.0,
            "lookup_load_ratio": 0.0,
            "power_per_unit_kW": 0.0,
            "total_power_kW": 0.0,
        }
        if self.gas_engine_enabled and include_generation:
            engine_curve = {
                "equipment_id": self.engine_id,
                "data": self._curve_rows(self.engine_id),
                "default_efficiency": 0.40,
            }
            engine_result = evaluate_engine_generation(
                engine_curve,
                indoor_load_ratio,
                engine_active_units,
                self._lookup_generation_power_per_unit,
                linear_curve_value,
            )
            radiator_result = evaluate_engine_radiator(
                {
                    "equipment_id": self.engine_radiator_id,
                    "data": self._curve_rows(self.engine_radiator_id),
                },
                non_radiator_facility_power_kw,
                engine_radiator_reference_kw,
                engine_radiator_active_units,
                self._lookup_radiator_power_per_unit,
            )
        engine_radiator_power_kw = radiator_result["total_power_kW"]
        it_electrical_loss_kw, mep_electrical_loss_kw = self._electrical_loss_components(
            load_ratio,
            it_kw=it_kw,
            mep_kw=non_radiator_mep_kw + engine_radiator_power_kw,
        )
        electrical_loss_kw = it_electrical_loss_kw + mep_electrical_loss_kw
        facility_power_kw = (
            it_kw
            + chiller_power_kw
            + dry_cooler_power_kw
            + pump_power_kw
            + cw_pump_power_kw
            + white_space_power_kw
            + engine_radiator_power_kw
            + electrical_loss_kw
        )
        return {
            "hour": hour,
            "it_load_kW": it_kw,
            "ambient_dry_bulb_C": ambient_c,
            "solar_heat_gain_kW": float(load_row["solar_heat_gain_kW"]),
            "other_auxiliary_heat_gain_kW": float(load_row["other_auxiliary_heat_gain_kW"]),
            "cooling_load_kW": cooling_load_kw,
            "CEFT_C": ceft_c,
            "dry_cooler_approach_C": dry_cooler_approach_c,
            "required_capacity_per_chiller_unit_kW": required_capacity_per_chiller_unit_kw,
            "active_chiller_units": active_chiller_units,
            "active_dry_cooler_units": active_dry_cooler_units,
            "active_pump_units": active_pump_units,
            "active_cw_pump_units": active_cw_pump_units,
            **indoor_power,
            "chiller_performance_result": chiller_per_unit.to_dict(),
            "dry_cooler_performance_result": dry_cooler_per_unit.to_dict(),
            "chiller_power_per_unit_kW": chiller_perf["power_kW"],
            "chiller_power_kW": chiller_power_kw,
            "chiller_COP": chiller_perf["COP"],
            "chiller_load_ratio": chiller_perf["load_ratio"],
            "chiller_unit_capacity_kW": chiller_unit_capacity_kw,
            "heat_rejection_kW": heat_rejection_kw,
            "heat_rejection_per_dry_cooler_unit_kW": heat_rejection_per_dry_cooler_unit_kw,
            "dry_cooler_power_per_unit_kW": dry_cooler_perf["power_kW"],
            "dry_cooler_power_kW": dry_cooler_power_kw,
            "dry_cooler_power_total_kW": dry_cooler_power_kw,
            "dry_cooler_active_unit_count": active_dry_cooler_units,
            "dry_cooler_outdoor_temperature_raw_C": dry_cooler_power_lookup.get("dry_cooler_outdoor_temperature_raw_C"),
            "dry_cooler_lookup_temperature_C": dry_cooler_power_lookup.get("dry_cooler_lookup_temperature_C"),
            "dry_cooler_curve_min_temperature_C": dry_cooler_power_lookup.get("dry_cooler_curve_min_temperature_C"),
            "dry_cooler_curve_max_temperature_C": dry_cooler_power_lookup.get("dry_cooler_curve_max_temperature_C"),
            "dry_cooler_temperature_clamped_low": dry_cooler_power_lookup.get("dry_cooler_temperature_clamped_low", False),
            "dry_cooler_temperature_clamped_high": dry_cooler_power_lookup.get("dry_cooler_temperature_clamped_high", False),
            "dry_cooler_power_curve_source": f"{self.dry_cooler_id}/Solver_Curve",
            "dry_cooler_power_lookup_basis": "outdoor_dry_bulb_temperature_only",
            "dry_cooler_capacity_per_unit_kW": dry_cooler_perf["capacity_kW"],
            "dry_cooler_capacity_kW": dry_cooler_perf["capacity_kW"] * active_dry_cooler_units,
            "dry_cooler_capacity_ratio": dry_cooler_perf["capacity_ratio"],
            **pump,
            "pump_reference_capacity_source": self.pump_reference_capacity_source,
            "pump_load_ratio": pump["pump_load_ratio_lookup"],
            "pump_power_per_unit_kW": pump["pump_power_per_unit_kW"],
            "pump_power_kW": pump_power_kw,
            "chw_pump_reference_capacity_kW": self.pump_reference_capacity_kw,
            "chw_pump_reference_capacity_source": self.pump_reference_capacity_source,
            "chw_pump_reference_capacity_basis": "Failure Peak Design cooling load per active CHW Pump",
            "chw_pump_reference_peak_cooling_load_kW": self.pump_reference_diagnostics[
                "pump_reference_peak_cooling_load_kW"
            ],
            "chw_pump_reference_failure_active_units": self.pump_reference_diagnostics[
                "pump_reference_failure_active_units"
            ],
            "chw_pump_current_load_per_unit_kW": pump["pump_required_load_per_unit_kW"],
            "chw_pump_load_ratio_raw": pump["pump_load_ratio_raw"],
            "chw_pump_load_ratio": pump["pump_load_ratio_lookup"],
            "chw_pump_load_ratio_basis": self.pump_reference_capacity_source,
            "chw_pump_load_ratio_warning": (
                "CHW Pump load ratio exceeds the Failure Peak Design reference."
                if pump["pump_overload"] else None
            ),
            "cw_pump_reference_capacity_per_unit_kW": cw_pump["pump_reference_capacity_per_unit_kW"],
            "cw_pump_reference_capacity_source": self.cw_pump_reference_capacity_source,
            "cw_pump_active_unit_count": cw_pump["pump_active_unit_count"],
            "cw_pump_required_load_per_unit_kW": cw_pump["pump_required_load_per_unit_kW"],
            "cw_pump_heat_rejection_load_kW": heat_rejection_kw,
            "cw_pump_load_ratio_raw": cw_pump["pump_load_ratio_raw"],
            "cw_pump_load_ratio_lookup": cw_pump["pump_load_ratio_lookup"],
            "cw_pump_curve_min_load_ratio": cw_pump["pump_curve_min_load_ratio"],
            "cw_pump_curve_max_load_ratio": cw_pump["pump_curve_max_load_ratio"],
            "cw_pump_power_per_unit_kW": cw_pump["pump_power_per_unit_kW"],
            "cw_pump_power_total_kW": cw_pump_power_kw,
            "cw_pump_load_ratio_clamped_low": cw_pump["pump_clamped_low"],
            "cw_pump_load_ratio_clamped_high": cw_pump["pump_clamped_high"],
            "cw_pump_overload": cw_pump["pump_overload"],
            "cw_pump_curve_source": cw_pump["pump_curve_source"],
            "cw_pump_load_ratio_basis": "heat_rejection_per_active_cw_pump_over_fixed_single_pump_reference_capacity",
            "electrical_loss_kW": electrical_loss_kw,
            "it_electrical_loss_kW": it_electrical_loss_kw,
            "mep_electrical_loss_kW": mep_electrical_loss_kw,
            "non_radiator_electrical_loss_kW": non_radiator_electrical_loss_kw,
            "non_radiator_facility_power_kW": non_radiator_facility_power_kw,
            "engine_output_kW": engine_result["output_kW"],
            "engine_power_kW": engine_result["output_kW"],
            "engine_efficiency": engine_result["efficiency"],
            "engine_fuel_input_kW": engine_result["fuel_input_kW"],
            "engine_waste_heat_kW": engine_result["waste_heat_kW"],
            "engine_active_units": engine_active_units if self.gas_engine_enabled else 0,
            "engine_3_power_boundary": "generation_side_excluded_from_facility_power",
            "engine_radiator_power_kW": engine_radiator_power_kw,
            "engine_radiator_power_per_unit_kW": radiator_result["power_per_unit_kW"],
            "engine_radiator_load_ratio": radiator_result["load_ratio"],
            "engine_radiator_load_ratio_lookup": radiator_result["lookup_load_ratio"],
            "engine_radiator_load_ratio_basis": "non_radiator_facility_demand_ratio",
            "engine_radiator_reference_power_kW": engine_radiator_reference_kw,
            "engine_radiator_reference_basis": "failure_scenario_peak_non_radiator_facility_demand",
            "engine_radiator_active_units": engine_radiator_active_units if self.gas_engine_enabled else 0,
            "engine_radiator_power_boundary": "facility_auxiliary_electrical_load",
            "facility_power_kW": facility_power_kw,
            "PUE": facility_power_kw / it_kw if it_kw > 0 else 0.0,
        }

    def _peak_design_results(
        self,
        design_it,
        chiller_unit_capacity_kw,
        active_chiller_units,
        active_dry_cooler_units,
        active_pump_units,
        active_cw_pump_units,
        indoor_active_units,
        dry_cooler_approach_c,
        engine_active_units,
        engine_radiator_active_units,
        engine_radiator_reference_kw,
    ):
        """Resolve and evaluate the independent design condition."""
        from solver import _peak_design_weather_condition

        condition = _peak_design_weather_condition(self.context)
        peak = calculate_peak_design_condition(self.context, condition)
        ambient_c = peak.get("peak_design_outdoor_dry_bulb_C")
        if ambient_c is None or design_it <= 0:
            peak["peak_PUE_definition"] = "unavailable"
            peak["peak_PUE"] = None
            peak["peak_design_total_facility_power_kW"] = None
            peak["peak_design_facility_electrical_demand_kW"] = None
            return peak

        point = self._evaluate_operating_point(
            {
                "it_load_kW": peak["peak_design_it_load_kW"],
                "ambient_dry_bulb_C": ambient_c,
                "solar_heat_gain_kW": peak["peak_design_solar_heat_gain_kW"],
                "other_auxiliary_heat_gain_kW": peak["peak_design_other_auxiliary_heat_gain_kW"],
                "cooling_load_kW": peak["peak_design_cooling_load_kW"],
            },
            design_it,
            chiller_unit_capacity_kw,
            active_chiller_units,
            active_dry_cooler_units,
            active_pump_units,
            active_cw_pump_units,
            indoor_active_units,
            dry_cooler_approach_c,
            engine_active_units,
            engine_radiator_active_units,
            engine_radiator_reference_kw,
        )
        facility_kw = point["facility_power_kW"]
        peak.update({
            "peak_PUE": facility_kw / peak["peak_design_it_load_kW"],
            "peak_PUE_definition": "peak_design",
            "peak_design_total_facility_power_kW": facility_kw,
            "peak_design_facility_electrical_demand_kW": facility_kw,
            "peak_design_chiller_power_kW": point["chiller_power_kW"],
            "peak_design_chiller_COP": point["chiller_COP"],
            "peak_design_dry_cooler_power_kW": point["dry_cooler_power_kW"],
            "peak_design_dry_cooler_power_per_unit_kW": point["dry_cooler_power_per_unit_kW"],
            "peak_design_CHW_pump_power_kW": point["pump_power_kW"],
            "peak_design_CW_pump_power_kW": point["cw_pump_power_total_kW"],
            "peak_design_CDU_power_kW": point["cdu_power_kW"],
            "peak_design_RTC_power_kW": point["rtc_power_kW"],
            "peak_design_MAU_power_kW": point["mau_power_kW"],
            "peak_design_white_space_equipment_power_kW": point["white_space_equipment_power_kW"],
            "peak_design_indoor_active_units": point["indoor_active_units"],
            "peak_design_project_load_ratio": point["indoor_equipment_load_ratio"],
            "peak_design_heat_rejection_kW": point["heat_rejection_kW"],
            "peak_design_electrical_loss_kW": point["electrical_loss_kW"],
            "peak_design_it_electrical_loss_kW": point["it_electrical_loss_kW"],
            "peak_design_mep_electrical_loss_kW": point["mep_electrical_loss_kW"],
            "peak_design_engine_output_kW": point["engine_output_kW"],
            "peak_design_engine_efficiency": point["engine_efficiency"],
            "peak_design_engine_fuel_input_kW": point["engine_fuel_input_kW"],
            "peak_design_engine_waste_heat_kW": point["engine_waste_heat_kW"],
            "peak_design_engine_radiator_power_kW": point["engine_radiator_power_kW"],
            "peak_design_engine_active_units": point["engine_active_units"],
            "peak_design_engine_radiator_active_units": point["engine_radiator_active_units"],
            "peak_design_equipment_result": point,
        })
        return peak

    def _failure_peak_non_radiator_reference(
        self,
        design_it,
        chiller_unit_capacity_kw,
        dry_cooler_approach_c,
    ):
        """Evaluate the canonical Failure Peak Design demand before radiator power."""
        from solver import _peak_design_weather_condition

        condition = _peak_design_weather_condition(self.context)
        peak = calculate_peak_design_condition(self.context, condition)
        ambient_c = peak.get("peak_design_outdoor_dry_bulb_C")
        if ambient_c is None:
            raise ChillerDryCoolerRuntimeError(
                "Gas Engine configuration requires a valid Peak Design outdoor dry-bulb condition "
                "for Engine Radiator normalization."
            )
        failure = resolve_unit_scenario(
            design_it,
            chiller_unit_capacity_kw,
            scenario_name="Failure",
            scenario_formula="required_units",
        )
        roles = failure["role_quantities"]
        point = self._evaluate_operating_point(
            {
                "it_load_kW": peak["peak_design_it_load_kW"],
                "ambient_dry_bulb_C": ambient_c,
                "solar_heat_gain_kW": peak["peak_design_solar_heat_gain_kW"],
                "other_auxiliary_heat_gain_kW": peak["peak_design_other_auxiliary_heat_gain_kW"],
                "cooling_load_kW": peak["peak_design_cooling_load_kW"],
            },
            design_it,
            chiller_unit_capacity_kw,
            roles["chiller_units"]["active_units"],
            roles["dry_cooler_units"]["active_units"],
            roles["chw_pump_units"]["active_units"],
            roles["cw_pump_units"]["active_units"],
            roles["indoor_units"]["active_units"],
            dry_cooler_approach_c,
            roles["engine_units"]["active_units"],
            roles["engine_units"]["active_units"],
            None,
            include_generation=False,
        )
        return point["non_radiator_facility_power_kW"]

    def _curve_rows(self, equipment_id):
        selected = self.selected_curves.get(equipment_id) or {}
        rows = selected.get("curve")
        if not isinstance(rows, list) or not rows:
            raise ChillerDryCoolerRuntimeError(f"{equipment_id} Solver_Curve missing or invalid.")
        return rows

    def _source_sheet(self, equipment_id):
        return (self.selected_curves.get(equipment_id) or {}).get("sheet_name") or "Solver_Curve"

    def _equipment_metadata(self, equipment_id, role_name, equipment_type, curve_type):
        selected = self.selected_curves.get(equipment_id) or {}
        metadata = selected.get("equipment_metadata")
        if isinstance(metadata, dict):
            return metadata
        binding_metadata = self._equipment_binding(equipment_id).get("equipment_metadata")
        if isinstance(binding_metadata, dict):
            return binding_metadata
        equipment = self.context.get("equipment") if isinstance(self.context.get("equipment"), dict) else {}
        cooling = equipment.get("cooling") if isinstance(equipment.get("cooling"), dict) else {}
        binding = cooling.get(role_name) if isinstance(cooling.get(role_name), dict) else {}
        metadata = binding.get("equipment_metadata") if isinstance(binding.get("equipment_metadata"), dict) else None
        if isinstance(metadata, dict):
            return metadata
        role_bindings = equipment.get("role_bindings") if isinstance(equipment.get("role_bindings"), dict) else {}
        role_binding = role_bindings.get(role_name)
        if isinstance(role_binding, list):
            role_binding = next((item for item in role_binding if isinstance(item, dict)), {})
        if isinstance(role_binding, dict):
            metadata = role_binding.get("equipment_metadata")
            if isinstance(metadata, dict):
                return metadata
        return {
            "equipment_id": equipment_id,
            "equipment_type": equipment_type,
            "curve_type": curve_type,
        }

    def _generic_preloaded_curves(self):
        preloaded = {
            self.pump_id: {"points": self._curve_rows(self.pump_id)},
        }
        for equipment_id in self.indoor_equipment_ids:
            binding = self._equipment_binding(equipment_id)
            if binding.get("enabled") is False:
                continue
            preloaded[equipment_id] = {"points": self._curve_rows(equipment_id)}
        for equipment_id in (self.engine_id, self.engine_radiator_id):
            if equipment_id:
                preloaded[equipment_id] = {"points": self._curve_rows(equipment_id)}
        electrical_path = self._electrical_path()
        if electrical_path:
            preloaded[f"{self.electrical_id}:IT"] = {
                "points": _flat_efficiency_points(electrical_path.get("it_efficiency"))
            }
            preloaded[f"{self.electrical_id}:MEP"] = {
                "points": _flat_efficiency_points(electrical_path.get("mep_efficiency"))
            }
        return preloaded

    def _hourly_it_loads(self, project):
        it_load = project.get("it_load") if isinstance(project.get("it_load"), dict) else {}
        hourly_it = it_load.get("hourly_it_load_kW")
        if not isinstance(hourly_it, list) or not hourly_it:
            raise ChillerDryCoolerRuntimeError("project.it_load.hourly_it_load_kW is required.")
        return [float(value) for value in hourly_it]

    def _dry_bulb(self, hours):
        weather = self.context.get("weather") if isinstance(self.context.get("weather"), dict) else {}
        hourly_data = weather.get("hourly_data") if isinstance(weather.get("hourly_data"), dict) else {}
        dry_bulb = hourly_data.get("dry_bulb_C")
        if isinstance(dry_bulb, list) and len(dry_bulb) == hours:
            return [float(value) for value in dry_bulb]
        return [25.0] * hours

    def _dry_cooler_approach_c(self):
        project = self.context.get("project") if isinstance(self.context.get("project"), dict) else {}
        equipment = self.context.get("equipment") if isinstance(self.context.get("equipment"), dict) else {}
        cooling = equipment.get("cooling") if isinstance(equipment.get("cooling"), dict) else {}
        dry_cooler = cooling.get("dry_cooler") if isinstance(cooling.get("dry_cooler"), dict) else {}
        candidates = [
            self.context.get("dry_cooler_approach_C"),
            self.context.get("dry_cooler_approach_c"),
            project.get("dry_cooler_approach_C"),
            project.get("dry_cooler_approach_c"),
            dry_cooler.get("approach_C"),
            dry_cooler.get("approach_c"),
        ]
        for value in candidates:
            try:
                if value is not None and value != "":
                    return float(value)
            except (TypeError, ValueError):
                continue
        return self.DEFAULT_DRY_COOLER_APPROACH_C

    def _unit_scenario(self, design_it_kw, unit_capacity_kw):
        project = self.context.get("project") if isinstance(self.context.get("project"), dict) else {}
        scenario_name = (
            self.context.get("scenario_name")
            or project.get("scenario_name")
            or "Normal"
        )
        scenario_formula = (
            self.context.get("scenario_formula")
            or project.get("scenario_formula")
            or (project.get("unit_scenario") or {}).get("scenario_formula")
        )
        role_quantities = (
            self.context.get("role_quantities")
            or project.get("role_quantities")
            or (project.get("unit_scenario") or {}).get("role_quantities")
        )
        return resolve_unit_scenario(
            design_it_kw,
            unit_capacity_kw,
            scenario_name=scenario_name,
            scenario_formula=scenario_formula,
            role_quantities=role_quantities,
        )

    def _active_role_units(self, roles, role_name, default):
        role = roles.get(role_name) if isinstance(roles, dict) else None
        value = role.get("active_units") if isinstance(role, dict) else default
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return max(1, int(default))

    def _non_negative_role_units(self, role, default):
        value = role.get("active_units") if isinstance(role, dict) else default
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return max(0, int(default))

    def _chiller_performance(self, required_capacity_kw, unit_capacity_kw, ceft_c):
        return self.chiller_adapter.calculate({
            "required_cooling_capacity_kW": required_capacity_kw,
            "rated_chiller_capacity_kW": unit_capacity_kw,
            "CEFT_C": ceft_c,
        })

    def _dry_cooler_performance(self, heat_rejection_kw, ambient_c):
        return self.dry_cooler_adapter.calculate({
            "required_heat_rejection_kW": heat_rejection_kw,
            "ambient_dry_bulb_C": ambient_c,
        })

    def _pump_power(self, cooling_load_kw, active_units):
        return evaluate_pump_power(
            cooling_load_kw,
            active_units,
            self.pump_reference_capacity_kw,
            self._curve_rows(self.pump_id),
            curve_source=f"{self.pump_id}/Solver_Curve",
        )

    def _cw_pump_power(self, heat_rejection_kw, active_units):
        return evaluate_pump_power(
            heat_rejection_kw,
            active_units,
            self.cw_pump_reference_capacity_kw,
            self._curve_rows(self.cw_pump_id),
            curve_source=f"{self.cw_pump_id}/Solver_Curve",
        )

    def _lookup_indoor_power_per_unit(self, role, equipment_id, binding, load_ratio):
        result = self.generic_engine.lookup_power(equipment_id, load_ratio)
        if not result.lookup_success or result.power_kW is None:
            raise ChillerDryCoolerRuntimeError(
                f"{equipment_id} Solver_Curve lookup failed: {'; '.join(result.errors)}"
            )
        return float(result.power_kW)

    def _lookup_generation_power_per_unit(self, equipment_id, rows, load_ratio):
        result = self.generic_engine.lookup_power(equipment_id, load_ratio)
        if not result.lookup_success or result.power_kW is None:
            raise ChillerDryCoolerRuntimeError(
                f"{equipment_id} Solver_Curve lookup failed: {'; '.join(result.errors)}"
            )
        return float(result.power_kW)

    def _lookup_radiator_power_per_unit(self, equipment_id, rows, load_ratio):
        result = self.generic_engine.lookup_power(equipment_id, load_ratio)
        if not result.lookup_success or result.power_kW is None:
            raise ChillerDryCoolerRuntimeError(
                f"{equipment_id} Solver_Curve lookup failed: {'; '.join(result.errors)}"
            )
        return {"power_kW": float(result.power_kW), "load_ratio": result.load_ratio}

    def _indoor_role(self, equipment_id):
        equipment_type = str(
            ((self.selected_curves.get(equipment_id) or {}).get("equipment_metadata") or {}).get("equipment_type")
            or equipment_id
        ).upper()
        for role in ("cdu", "rtc", "mau"):
            if equipment_type.startswith(role.upper()):
                return role
        raise ChillerDryCoolerRuntimeError(
            f"Unsupported indoor_cooling equipment {equipment_id!r}; expected CDU, RTC, or MAU."
        )

    def _equipment_binding(self, equipment_id):
        equipment = self.context.get("equipment") if isinstance(self.context.get("equipment"), dict) else {}
        equipment_bindings = equipment.get("equipment_bindings") if isinstance(equipment.get("equipment_bindings"), dict) else {}
        direct_binding = equipment_bindings.get(equipment_id)
        if isinstance(direct_binding, dict):
            return direct_binding
        role_bindings = equipment.get("role_bindings") if isinstance(equipment.get("role_bindings"), dict) else {}
        for value in role_bindings.values():
            bindings = value if isinstance(value, list) else [value]
            for binding in bindings:
                if isinstance(binding, dict) and binding.get("equipment_id") == equipment_id:
                    return binding
        cooling = equipment.get("cooling") if isinstance(equipment.get("cooling"), dict) else {}
        for value in cooling.values():
            if isinstance(value, dict) and value.get("equipment_id") == equipment_id:
                return value
            if isinstance(value, dict) and isinstance(value.get(equipment_id), dict):
                return value[equipment_id]
        auxiliary = equipment.get("auxiliary") if isinstance(equipment.get("auxiliary"), dict) else {}
        direct_auxiliary = auxiliary.get(equipment_id)
        if isinstance(direct_auxiliary, dict):
            return direct_auxiliary
        return {}

    def _electrical_loss(self, load_ratio, it_kw, mep_kw):
        return sum(self._electrical_loss_components(load_ratio, it_kw, mep_kw))

    def _electrical_loss_components(self, load_ratio, it_kw, mep_kw):
        electrical_path = self._electrical_path()
        if not electrical_path:
            return 0.0, 0.0
        it_loss = self.generic_engine.lookup_electrical_loss(
            f"{self.electrical_id}:IT",
            load_ratio,
            base_power_kW=it_kw,
        )
        mep_loss = self.generic_engine.lookup_electrical_loss(
            f"{self.electrical_id}:MEP",
            load_ratio,
            base_power_kW=mep_kw,
        )
        errors = []
        if not it_loss.lookup_success:
            errors.extend(it_loss.errors)
        if not mep_loss.lookup_success:
            errors.extend(mep_loss.errors)
        if errors:
            raise ChillerDryCoolerRuntimeError(
                f"{self.electrical_id} electrical lookup failed: {'; '.join(errors)}"
            )
        return float(it_loss.loss_kW or 0.0), float(mep_loss.loss_kW or 0.0)

    def _electrical_path(self):
        selected = self.selected_curves.get(self.electrical_id) or {}
        return (
            selected.get("electrical_path")
            or self.context.get("electrical_path")
            or (self.context.get("equipment") or {}).get("electrical_path")
        )

    def _capacity_validation(
        self,
        peak_results,
        unit_scenario,
        chiller_unit_capacity_kw,
        active_chiller_units,
        active_dry_cooler_units,
    ):
        roles = unit_scenario.get("role_quantities") or {}
        chiller_role = roles.get("chiller_units") or {}
        dry_cooler_role = roles.get("dry_cooler_units") or {}
        peak_load = peak_results.get("peak_design_cooling_load_kW")
        peak_dry_bulb = peak_results.get("peak_design_outdoor_dry_bulb_C")
        role_capacities = {
            "chiller": {
                "installed_units": chiller_role.get("installed_units", unit_scenario.get("installed_units")),
                "required_units": chiller_role.get("required_units", unit_scenario.get("required_units")),
                "active_units": active_chiller_units,
                "unit_capacity_kW": chiller_unit_capacity_kw,
                "peak_load_kW": peak_load,
            }
        }
        dry_cooler_warnings = []
        dry_cooler_capacity_per_unit = None
        dry_cooler_peak_load = None
        if peak_dry_bulb is None:
            dry_cooler_warnings.append(
                "Dry cooler peak ambient capacity cannot be calculated because peak design dry bulb is unavailable."
            )
        elif peak_load is None:
            dry_cooler_warnings.append(
                "Dry cooler peak heat rejection cannot be calculated because peak design cooling load is unavailable."
            )
        else:
            try:
                peak_ceft = float(peak_dry_bulb) + self._dry_cooler_approach_c()
                chiller_peak_per_unit = self._chiller_performance(
                    float(peak_load) / max(1, int(active_chiller_units)),
                    chiller_unit_capacity_kw,
                    peak_ceft,
                )
                dry_cooler_peak_load = float(peak_load) + (
                    chiller_peak_per_unit.performance["power_kW"] * max(1, int(active_chiller_units))
                )
                dry_cooler_peak = self._dry_cooler_performance(
                    0,
                    peak_dry_bulb,
                )
                dry_cooler_capacity_per_unit = dry_cooler_peak.performance["capacity_kW"]
            except Exception as exc:
                dry_cooler_warnings.append(
                    f"Dry cooler peak ambient capacity could not be calculated: {exc}"
                )
        role_capacities["dry_cooler"] = {
            "installed_units": dry_cooler_role.get("installed_units", unit_scenario.get("installed_units")),
            "required_units": dry_cooler_role.get("required_units", unit_scenario.get("required_units")),
            "active_units": active_dry_cooler_units,
            "unit_capacity_kW": dry_cooler_capacity_per_unit,
            "peak_load_kW": dry_cooler_peak_load,
            "warnings": dry_cooler_warnings,
        }
        return validate_peak_capacity(
            "chiller_dry_cooler",
            peak_results=peak_results,
            unit_scenario=unit_scenario,
            role_capacities=role_capacities,
        )


def _flat_efficiency_points(efficiency):
    if efficiency is None:
        raise ChillerDryCoolerRuntimeError("Electrical distribution efficiency is missing.")
    value = float(efficiency)
    return [{"load_ratio": 0.0, "efficiency": value}, {"load_ratio": 1.0, "efficiency": value}]
