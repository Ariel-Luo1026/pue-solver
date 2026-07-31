import unittest
from copy import deepcopy

from configuration_library_loader import build_solver_input_from_library
from cooling_load_model import calculate_annual_cooling_load, calculate_peak_design_condition
from solver import compute_pue_project
from topology_adapters.acc_gas_engine_cdu import build_acc_solver_input_from_configuration
from topology_dispatcher import dispatch_topology


def _weather(hours):
    dry_bulb = [15.0 + float(index % 24) for index in range(hours)]
    return {
        "hourly_data": {
            "hour_index": list(range(1, hours + 1)),
            "dry_bulb_C": dry_bulb,
            "wet_bulb_C": [],
        },
        "metadata": {"source": "unit_test_epw", "weather_hours": hours},
    }


def _heat_gains(solar_kw=7.0, auxiliary_kw=71.0):
    return {
        "solar_heat_gain_max_kW": solar_kw,
        "solar_daytime_start_hour": 6,
        "solar_daytime_end_hour": 18,
        "other_auxiliary_heat_gain_kW": auxiliary_kw,
    }


def _attach_common_inputs(input_obj, solar_kw=7.0, auxiliary_kw=71.0):
    hours = len(input_obj["project"]["it_load"]["hourly_it_load_kW"])
    gains = _heat_gains(solar_kw, auxiliary_kw)
    input_obj["weather"] = _weather(hours)
    input_obj["heat_gains"] = deepcopy(gains)
    input_obj.update(gains)
    input_obj["peak_design_weather_source"] = "manual"
    input_obj["peak_design_outdoor_dry_bulb_C"] = 44.0
    input_obj["project"]["heat_gains"] = deepcopy(gains)
    input_obj["project"]["peak_design_weather_source"] = "manual"
    input_obj["project"]["peak_design_outdoor_dry_bulb_C"] = 44.0
    input_obj["peak_design_condition_override"] = {
        "source": "manual",
        "extreme_db_max_C": 44.0,
        "temperature_basis": "ASHRAE_20_year_extreme_annual_design_condition",
    }
    return input_obj


class CoolingLoadModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.acc_library_input = build_solver_input_from_library(
            "ACC_1.5MW_GASENGINE_CDU", 4.4, "Normal"
        )
        cls.chiller_library_input = build_solver_input_from_library(
            "CHILLER_DRYCOOLER_2MW_GRID", 4.4, "Normal"
        )

    def test_acc_solver_cooling_load_matches_common_model(self):
        acc_solver_input = build_acc_solver_input_from_configuration(
            self.acc_library_input["configuration_manifest"],
            deepcopy(self.acc_library_input),
        )
        _attach_common_inputs(acc_solver_input)

        common = calculate_annual_cooling_load(acc_solver_input)
        acc_result = compute_pue_project(acc_solver_input)

        self.assertLess(
            abs(
                acc_result["annual_results"]["annual_cooling_load_kWh"]
                - common["totals"]["annual_cooling_load_kWh"]
            ),
            1e-9,
        )

    def test_acc_and_chiller_receive_same_weather_and_peak_design_condition(self):
        acc_solver_input = build_acc_solver_input_from_configuration(
            self.acc_library_input["configuration_manifest"],
            deepcopy(self.acc_library_input),
        )
        chiller_input = deepcopy(self.chiller_library_input)
        _attach_common_inputs(acc_solver_input)
        _attach_common_inputs(chiller_input)

        chiller_result = dispatch_topology(chiller_input["configuration_manifest"], chiller_input)
        acc_peak = calculate_peak_design_condition(
            acc_solver_input,
            acc_solver_input["peak_design_condition_override"],
        )

        self.assertEqual(
            acc_solver_input["weather"]["hourly_data"]["dry_bulb_C"],
            chiller_input["weather"]["hourly_data"]["dry_bulb_C"],
        )
        self.assertEqual(
            acc_peak["peak_design_outdoor_dry_bulb_C"],
            chiller_result["peak_results"]["peak_design_outdoor_dry_bulb_C"],
        )
        self.assertEqual(
            acc_peak["peak_design_cooling_load_kW"],
            chiller_result["peak_results"]["peak_design_cooling_load_kW"],
        )

    def test_solar_and_auxiliary_heat_gain_increase_cooling_load_for_both_topologies(self):
        acc_base = build_acc_solver_input_from_configuration(
            self.acc_library_input["configuration_manifest"],
            deepcopy(self.acc_library_input),
        )
        chiller_base = deepcopy(self.chiller_library_input)
        _attach_common_inputs(acc_base, solar_kw=7.0, auxiliary_kw=71.0)
        _attach_common_inputs(chiller_base, solar_kw=7.0, auxiliary_kw=71.0)

        acc_high = build_acc_solver_input_from_configuration(
            self.acc_library_input["configuration_manifest"],
            deepcopy(self.acc_library_input),
        )
        chiller_high = deepcopy(self.chiller_library_input)
        _attach_common_inputs(acc_high, solar_kw=20.0, auxiliary_kw=100.0)
        _attach_common_inputs(chiller_high, solar_kw=20.0, auxiliary_kw=100.0)

        acc_base_load = compute_pue_project(acc_base)["annual_results"]["annual_cooling_load_kWh"]
        acc_high_load = compute_pue_project(acc_high)["annual_results"]["annual_cooling_load_kWh"]
        chiller_base_load = dispatch_topology(
            chiller_base["configuration_manifest"], chiller_base
        )["annual_results"]["annual_cooling_load_kWh"]
        chiller_high_load = dispatch_topology(
            chiller_high["configuration_manifest"], chiller_high
        )["annual_results"]["annual_cooling_load_kWh"]

        self.assertGreater(acc_high_load, acc_base_load)
        self.assertGreater(chiller_high_load, chiller_base_load)

    def test_dry_cooler_approach_changes_ceft_cop_and_chiller_power(self):
        input_5c = deepcopy(self.chiller_library_input)
        input_8c = deepcopy(self.chiller_library_input)
        _attach_common_inputs(input_5c)
        _attach_common_inputs(input_8c)
        input_5c["dry_cooler_approach_C"] = 5.0
        input_8c["dry_cooler_approach_C"] = 8.0

        row_5c = dispatch_topology(input_5c["configuration_manifest"], input_5c)["hourly_results"][23]
        row_8c = dispatch_topology(input_8c["configuration_manifest"], input_8c)["hourly_results"][23]

        self.assertEqual(row_8c["CEFT_C"] - row_5c["CEFT_C"], 3.0)
        self.assertLess(row_8c["chiller_COP"], row_5c["chiller_COP"])
        self.assertGreater(row_8c["chiller_power_kW"], row_5c["chiller_power_kW"])


if __name__ == "__main__":
    unittest.main()
