import unittest
from copy import deepcopy

from configuration_library_loader import build_solver_input_from_library
from library_solver_adapter import convert_library_input_to_solver_input
from solver import compute_pue_project


class EngineEquipmentCurveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = {}
        cls.outputs = {}
        cls.without_engine_pue = {}
        for scenario in ("Normal", "Failure"):
            adapted = convert_library_input_to_solver_input(
                build_solver_input_from_library("ACC_1.5MW_GASENGINE_CDU", 4.4, scenario)
            )
            cls.inputs[scenario] = adapted
            cls.outputs[scenario] = compute_pue_project(adapted)
            without_engine = deepcopy(adapted)
            without_engine.pop("engine_curve", None)
            without_engine.pop("engine_radiator_curve", None)
            cls.without_engine_pue[scenario] = compute_pue_project(without_engine)["annual_results"]["annual_average_PUE"]

    def test_scenario_specific_engine_curves_are_selected(self):
        self.assertEqual(self.inputs["Normal"]["engine_curve"]["source_sheet"], "Solver_Curve_Normal")
        self.assertEqual(self.inputs["Failure"]["engine_curve"]["source_sheet"], "Solver_Curve_Failure")

    def test_hourly_engine_output_fuel_and_waste_heat(self):
        for scenario in ("Normal", "Failure"):
            hour = self.outputs[scenario]["hourly_results"][0]
            self.assertGreater(hour["engine_output_kW"], 0)
            self.assertGreater(hour["engine_fuel_input_kW"], hour["engine_output_kW"])
            self.assertGreater(hour["engine_waste_heat_kW"], 0)
            self.assertAlmostEqual(hour["engine_efficiency"], 0.40)

    def test_annual_engine_metrics(self):
        for scenario in ("Normal", "Failure"):
            annual = self.outputs[scenario]["annual_results"]
            self.assertGreater(annual["annual_engine_output_kWh"], 0)
            self.assertGreater(annual["annual_engine_fuel_input_kWh"], annual["annual_engine_output_kWh"])
            self.assertGreater(annual["annual_engine_waste_heat_kWh"], 0)
            self.assertAlmostEqual(annual["average_engine_efficiency"], 0.40)
            self.assertAlmostEqual(
                annual["annual_engine_waste_heat_kWh"],
                annual["annual_engine_fuel_input_kWh"] - annual["annual_engine_output_kWh"],
            )

    def test_engine_reporting_without_radiator_does_not_change_pue(self):
        for scenario in ("Normal", "Failure"):
            without_radiator = deepcopy(self.inputs[scenario])
            without_radiator.pop("engine_radiator_curve", None)
            self.assertAlmostEqual(
                compute_pue_project(without_radiator)["annual_results"]["annual_average_PUE"],
                self.without_engine_pue[scenario],
            )


if __name__ == "__main__":
    unittest.main()
