"""Annual runtime for Chiller + Dry Cooler Configuration Library topologies."""

from copy import deepcopy

from cooling_load_model import calculate_annual_cooling_load, calculate_peak_design_condition
from capacity_validation import validate_peak_capacity
from energy_aggregation import aggregate_annual_energy
from equipment_engine import ConfigurationLibraryEquipmentEngine, EquipmentEngineConfig
from equipment_performance import dispatch_performance_adapter
from equipment_role_resolver import resolve_equipment_role_id, validate_required_equipment_roles
from unit_scenario_manager import resolve_unit_scenario


class ChillerDryCoolerRuntimeError(ValueError):
    """Raised when the chiller + dry cooler runtime cannot evaluate input."""


class ChillerDryCoolerRuntime:
    """Run an independent annual 8760 simulation for chiller + dry cooler packages."""

    DEFAULT_DRY_COOLER_APPROACH_C = 5.0

    def __init__(self, manifest, configuration_context):
        self.manifest = manifest or {}
        self.context = configuration_context or {}
        self.selected_curves = self.context.get("selected_curves") or {}
        validate_required_equipment_roles(self.manifest, self.selected_curves)

        self.chiller_id = resolve_equipment_role_id(self.manifest, "chiller", self.selected_curves)
        self.dry_cooler_id = resolve_equipment_role_id(self.manifest, "dry_cooler", self.selected_curves)
        self.pump_id = resolve_equipment_role_id(self.manifest, "chw_pump", self.selected_curves)
        self.electrical_id = resolve_equipment_role_id(
            self.manifest, "electrical_distribution", self.selected_curves
        )

        self.chiller_adapter = dispatch_performance_adapter(
            self._equipment_metadata(self.chiller_id, "chiller", "CHILLER", "cop_curve"),
            curve_data=self._curve_rows(self.chiller_id),
        )
        self.dry_cooler_adapter = dispatch_performance_adapter(
            self._equipment_metadata(self.dry_cooler_id, "dry_cooler", "DRY_COOLER", "ambient_capacity_power"),
            curve_data=self._curve_rows(self.dry_cooler_id),
        )
        self.generic_engine = ConfigurationLibraryEquipmentEngine(
            EquipmentEngineConfig(preloaded_curves=self._generic_preloaded_curves())
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
        roles = unit_scenario.get("role_quantities") or {}
        active_chiller_units = self._active_role_units(roles, "chiller_units", unit_scenario["active_units"])
        active_dry_cooler_units = self._active_role_units(roles, "dry_cooler_units", unit_scenario["active_units"])
        active_pump_units = self._active_role_units(roles, "pump_units", unit_scenario["active_units"])
        dry_cooler_approach_c = self._dry_cooler_approach_c()

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
            "electrical_loss": 0.0,
        }

        for index, load_row in enumerate(cooling_rows):
            row = self._evaluate_operating_point(
                load_row,
                design_it,
                chiller_unit_capacity_kw,
                active_chiller_units,
                active_dry_cooler_units,
                active_pump_units,
                dry_cooler_approach_c,
                hour=index + 1,
            )
            hourly_results.append(row)
            totals["it"] += row["it_load_kW"]
            totals["cooling_load"] += row["cooling_load_kW"]
            totals["solar_heat_gain"] += load_row["solar_heat_gain_kW"]
            totals["other_auxiliary_heat_gain"] += load_row["other_auxiliary_heat_gain_kW"]
            totals["facility"] += row["facility_power_kW"]
            totals["chiller"] += row["chiller_power_kW"]
            totals["dry_cooler"] += row["dry_cooler_power_kW"]
            totals["pump"] += row["pump_power_kW"]
            totals["electrical_loss"] += row["electrical_loss_kW"]

        annual_average_pue = totals["facility"] / totals["it"] if totals["it"] > 0 else 0.0
        annual_results = {
            "annual_average_PUE": annual_average_pue,
            "annual_IT_energy_kWh": totals["it"],
            "annual_facility_energy_kWh": totals["facility"],
            "annual_chiller_energy_kWh": totals["chiller"],
            "annual_dry_cooler_energy_kWh": totals["dry_cooler"],
            "annual_pump_energy_kWh": totals["pump"],
            "annual_electrical_loss_kWh": totals["electrical_loss"],
            "annual_solar_heat_gain_kWh": totals["solar_heat_gain"],
            "annual_other_auxiliary_heat_gain_kWh": totals["other_auxiliary_heat_gain"],
            "annual_cooling_load_kWh": totals["cooling_load"],
            "annual_total_cooling_system_energy_kWh": totals["chiller"] + totals["dry_cooler"] + totals["pump"],
        }
        standard_annual_energy = aggregate_annual_energy({"hourly_results": hourly_results})
        peak_results = self._peak_design_results(
            design_it,
            chiller_unit_capacity_kw,
            active_chiller_units,
            active_dry_cooler_units,
            active_pump_units,
            dry_cooler_approach_c,
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
                    "electrical_distribution": self.electrical_id,
                },
                "selected_curves": deepcopy(self.selected_curves),
                "runtime_assumptions": {
                    "dry_cooler_approach_C": dry_cooler_approach_c,
                    "cooling_load_model": "shared_cooling_load_model",
                    "unit_scenario": deepcopy(unit_scenario),
                    "facility_power_formula": "IT + chiller + dry_cooler + pump + electrical_loss",
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
        dry_cooler_approach_c,
        hour=None,
    ):
        """Evaluate annual and peak-design points through one equipment path."""
        it_kw = float(load_row["it_load_kW"])
        ambient_c = float(load_row["ambient_dry_bulb_C"])
        cooling_load_kw = float(load_row["cooling_load_kW"])
        load_ratio = cooling_load_kw / design_it if design_it else 0.0
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
        dry_cooler_power_kw = dry_cooler_perf["power_kW"] * active_dry_cooler_units
        pump_power_kw = self._pump_power(load_ratio, active_pump_units)
        electrical_loss_kw = self._electrical_loss(
            load_ratio,
            it_kw=it_kw,
            mep_kw=chiller_power_kw + dry_cooler_power_kw + pump_power_kw,
        )
        facility_power_kw = (
            it_kw
            + chiller_power_kw
            + dry_cooler_power_kw
            + pump_power_kw
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
            "dry_cooler_capacity_per_unit_kW": dry_cooler_perf["capacity_kW"],
            "dry_cooler_capacity_kW": dry_cooler_perf["capacity_kW"] * active_dry_cooler_units,
            "dry_cooler_capacity_ratio": dry_cooler_perf["capacity_ratio"],
            "pump_power_per_unit_kW": pump_power_kw / active_pump_units,
            "pump_power_kW": pump_power_kw,
            "electrical_loss_kW": electrical_loss_kw,
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
        dry_cooler_approach_c,
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
            dry_cooler_approach_c,
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
            "peak_design_CHW_pump_power_kW": point["pump_power_kW"],
            "peak_design_electrical_loss_kW": point["electrical_loss_kW"],
            "peak_design_equipment_result": point,
        })
        return peak

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

    def _pump_power(self, load_ratio, active_units):
        result = self.generic_engine.lookup_power(self.pump_id, load_ratio)
        if not result.lookup_success or result.power_kW is None:
            raise ChillerDryCoolerRuntimeError(
                f"{self.pump_id} pump lookup failed: {'; '.join(result.errors)}"
            )
        return float(result.power_kW) * active_units

    def _electrical_loss(self, load_ratio, it_kw, mep_kw):
        electrical_path = self._electrical_path()
        if not electrical_path:
            return 0.0
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
        return float(it_loss.loss_kW or 0.0) + float(mep_loss.loss_kW or 0.0)

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
