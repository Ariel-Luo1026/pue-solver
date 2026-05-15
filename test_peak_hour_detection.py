#!/usr/bin/env python3
"""
Test script to verify peak hour detection works correctly.
This test runs PUE calculation without equipment curves to verify
that peak hour is selected based on maximum facility power, not PUE.
"""

import json
import sys
from datetime import datetime, timedelta

# Add the pue-solver-main directory to Python path
sys.path.insert(0, 'pue-solver-main')

from solver import compute_pue_project

def load_json_file(filename):
    """Load JSON data from file."""
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def convert_hour_to_datetime(hour_index):
    """Convert hour index (0-8759) to datetime object."""
    base_date = datetime(2024, 1, 1)  # Assuming year 2024
    return base_date + timedelta(hours=hour_index)

def find_hottest_hour(weather_data):
    """Find the hour with highest dry bulb temperature."""
    dry_bulb_temps = weather_data.get('hourly_data', {}).get('dry_bulb_C', [])
    if not dry_bulb_temps:
        return None

    max_temp = max(dry_bulb_temps)
    max_index = dry_bulb_temps.index(max_temp)

    # Return hour data in the expected format
    return {
        'hour_of_year': max_index + 1,  # 1-based hour of year
        'dry_bulb_temperature_celsius': max_temp
    }

def main():
    print("Testing peak hour detection without equipment curves...")

    # Load data files
    try:
        weather_data = load_json_file('cazaux_france_8760_weather_profile_compact.json')
        it_load_data = load_json_file('ashrae_90_4_compatible_it_load_profile_8760.json')
        curves_data = load_json_file('pue-solver-main/curves.json')
    except FileNotFoundError as e:
        print(f"Error loading data files: {e}")
        return

    # Find the hottest hour in weather data
    hottest_hour = find_hottest_hour(weather_data)
    if hottest_hour:
        hottest_hour_index = hottest_hour.get('hour_of_year', 0)
        hottest_temp = hottest_hour.get('dry_bulb_temperature_celsius', 0)
        hottest_datetime = convert_hour_to_datetime(hottest_hour_index - 1)  # Convert to 0-based
        print(f"Hottest hour: {hottest_datetime} (hour {hottest_hour_index}), Temperature: {hottest_temp}°C")
    else:
        print("Could not find hottest hour in weather data")
        return

    # Prepare project configuration in the expected format
    project_config = {
        "project": {
            "project_mode": True,
            "it_load": {
                "hourly_it_load_kW": [data["IT_load_kW"] for data in it_load_data["hourly_profile"]]
            },
            "equipment_curves": {},  # Empty curves for this test
            "facility_config": curves_data.get("facility_config", {})
        },
        "weather": weather_data,
        "curve_library": {}  # Empty curve library
    }

    # Run PUE calculation
    try:
        result = compute_pue_project(project_config)
    except Exception as e:
        print(f"Error running PUE calculation: {e}")
        return

    # Extract peak hour information
    if "peak_results" in result:
        peak_data = result["peak_results"]
        peak_hour_index = peak_data.get("peak_hour_index", 0)
        peak_datetime = convert_hour_to_datetime(peak_hour_index - 1)  # Convert to 0-based
        peak_pue = peak_data.get("peak_PUE", 0)
        peak_power = peak_data.get("peak_total_facility_power_kW", 0)

        print(f"Detected peak hour: {peak_datetime} (hour {peak_hour_index})")
        print(f"Peak PUE: {peak_pue}")
        print(f"Peak facility power: {peak_power} kW")

        # Check if peak hour has the maximum facility power (this is the correct behavior)
        if "hourly_results" in result:
            hourly_results = result["hourly_results"]
            max_power_hour = max(hourly_results, key=lambda x: x.get("total_facility_power_kW", 0))
            max_power_index = max_power_hour.get("hour_index", 0)
            max_power_value = max_power_hour.get("total_facility_power_kW", 0)

            if peak_hour_index == max_power_index:
                print("✅ SUCCESS: Peak hour correctly matches the hour with maximum facility power!")
                print(f"Both hour {peak_hour_index} and max power hour {max_power_index} have {max_power_value} kW facility power")
            else:
                print("❌ FAILURE: Peak hour does not match the hour with maximum facility power.")
                print(f"Peak hour {peak_hour_index}: {peak_power} kW")
                print(f"Max power hour {max_power_index}: {max_power_value} kW")

        # Additional info about the hottest hour
        print(f"\nFor reference - Hottest hour: {hottest_hour_index} ({hottest_temp}°C)")
        hottest_hour_data = next((h for h in result["hourly_results"] if h.get("hour_index") == hottest_hour_index), None)
        if hottest_hour_data:
            hottest_facility_power = hottest_hour_data.get("total_facility_power_kW", 0)
            print(f"Facility power at hottest hour: {hottest_facility_power} kW")

    else:
        print("No peak results information found in results")
        print("Available keys:", list(result.keys()))

if __name__ == "__main__":
    main()