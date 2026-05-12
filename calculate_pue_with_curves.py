#!/usr/bin/env python3
"""
Complete PUE Calculation with Equipment Curves
Integrates mechanical, electrical, and cooling system curves
"""
import json
import sys
import os

# Add the nested folder to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'pue-solver-main'))

from solver import compute_pue_project

def load_json_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    base_path = os.path.dirname(__file__)
    
    # Load all data files
    print("Loading data files...")
    weather_data = load_json_file(os.path.join(base_path, 'cazaux_france_8760_weather_profile_compact.json'))
    it_load_data = load_json_file(os.path.join(base_path, 'ashrae_90_4_compatible_it_load_profile_8760.json'))
    mechanical_curves = load_json_file(os.path.join(base_path, 'mechanical_equipment_load_curves_default.json'))
    electrical_curves = load_json_file(os.path.join(base_path, 'electrical_system_efficiency_curves_default.json'))
    cooling_curves = load_json_file(os.path.join(base_path, 'cooling_system_chiller_cop_vs_load.json'))
    
    print("✓ Weather data loaded")
    print("✓ IT load profile loaded")
    print("✓ Mechanical curves loaded")
    print("✓ Electrical curves loaded")
    print("✓ Cooling curves loaded")
    
    # Build equipment_curves dictionary from the three curve packages
    equipment_curves = {}
    
    # Add electrical curves
    if "curves" in electrical_curves:
        for curve_id, curve_data in electrical_curves["curves"].items():
            equipment_curves[curve_id] = curve_data
    
    # Add mechanical curves
    if "curves" in mechanical_curves:
        for curve_id, curve_data in mechanical_curves["curves"].items():
            equipment_curves[curve_id] = curve_data
    
    # Add cooling curves
    if "curve" in cooling_curves:
        curve_id = cooling_curves["curve"].get("curve_id", "chiller_COP_H_vs_load")
        equipment_curves[curve_id] = cooling_curves["curve"]
    
    print(f"\n✓ Consolidated {len(equipment_curves)} equipment curves")
    print(f"  Curves: {', '.join(list(equipment_curves.keys())[:5])}{'...' if len(equipment_curves) > 5 else ''}")
    
    # Extract weather and IT load arrays
    hourly_weather = weather_data.get("hourly_data", [])
    hourly_it_load = it_load_data.get("hourly_data", [])
    
    dry_bulb = [h.get("dry_bulb_C") for h in hourly_weather]
    wet_bulb = [h.get("wet_bulb_C") for h in hourly_weather]
    rel_humidity = [h.get("relative_humidity_percent") for h in hourly_weather]
    it_load = [h.get("load_kW") for h in hourly_it_load]
    
    print(f"\n✓ Extracted 8760 hourly weather records")
    print(f"✓ Extracted 8760 hourly IT load records")
    print(f"  Dry bulb range: {min([x for x in dry_bulb if x is not None]):.1f}°C to {max([x for x in dry_bulb if x is not None]):.1f}°C")
    print(f"  IT load range: {min([x for x in it_load if x is not None]):.1f} kW to {max([x for x in it_load if x is not None]):.1f} kW")
    
    # Build complete project input
    project_input = {
        "project": {
            "name": "Cazaux France PUE Analysis with Equipment Curves",
            "description": "8760-hour annual calculation with mechanical, electrical, and cooling system curves",
            "location": "Cazaux, France",
            "calculation_mode": "project_8760"
        },
        "facility_config": {
            "design_it_load_kW": 1000,
            "selected_cooling_mode": "active_cooling",
            "selected_it_cooling_mode": "crac_precision_cooling"
        },
        "curve_library": {
            "equipment_curves": equipment_curves
        },
        "weather_data": {
            "dry_bulb_C": dry_bulb,
            "wet_bulb_C": wet_bulb,
            "relative_humidity_percent": rel_humidity
        },
        "hourly_it_load": {
            "load_kW": it_load
        }
    }
    
    print("\n" + "="*70)
    print("STARTING PUE CALCULATION WITH EQUIPMENT CURVES")
    print("="*70)
    
    # Execute calculation
    result = compute_pue_project(project_input)
    
    # Save results
    output_path = os.path.join(base_path, 'pue_project_8760_calculated_with_curves.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    
    print(f"\n{'='*70}")
    print("CALCULATION COMPLETE")
    print(f"{'='*70}")
    
    # Display summary
    annual = result.get("annual_results", {})
    peak = result.get("peak_results", {})
    
    print(f"\n📊 ANNUAL RESULTS:")
    print(f"   Annual Average PUE:      {annual.get('annual_average_PUE', 'N/A'):.3f}")
    print(f"   IT Energy:               {annual.get('annual_IT_energy_kWh', 0):,.0f} kWh")
    print(f"   Facility Energy:         {annual.get('annual_facility_energy_kWh', 0):,.0f} kWh")
    print(f"   Cooling Energy:          {annual.get('annual_cooling_energy_kWh', 0):,.0f} kWh")
    print(f"   Electrical Loss:         {annual.get('annual_electrical_loss_kWh', 0):,.0f} kWh")
    print(f"   Auxiliary Energy:        {annual.get('annual_auxiliary_energy_kWh', 0):,.0f} kWh")
    
    print(f"\n🔥 PEAK HOUR RESULTS:")
    print(f"   Peak PUE:                {peak.get('peak_PUE', 'N/A'):.3f}")
    print(f"   Peak Hour Index:         {peak.get('peak_hour_index', 'N/A')}")
    print(f"   Peak Outdoor Temp:       {peak.get('peak_outdoor_dry_bulb_C', 'N/A'):.1f}°C")
    print(f"   Peak Outdoor Wet Bulb:   {peak.get('peak_outdoor_wet_bulb_C', 'N/A'):.1f}°C")
    print(f"   Peak IT Load:            {peak.get('peak_IT_load_kW', 0):.1f} kW")
    print(f"   Peak Total Facility Power: {peak.get('peak_total_facility_power_kW', 0):.1f} kW")
    
    validation = result.get("validation", {}).get("checks", {})
    print(f"\n✓ VALIDATION CHECKS:")
    for check, status in validation.items():
        symbol = "✓" if status else "✗"
        print(f"   {symbol} {check}")
    
    print(f"\n📁 Results saved to: {output_path}")
    
if __name__ == "__main__":
    main()
