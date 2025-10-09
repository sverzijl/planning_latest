#!/usr/bin/env python
"""
Quick verification script for integration tests.
Runs the 3 previously failing tests to verify labor calendar extension fix.
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    print("="*80)
    print("PHASE 2A: Integration Test Verification")
    print("="*80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("Objective: Verify that labor calendar extension (May 26, 2025 - Dec 31, 2026)")
    print("           fixed the 3 previously failing integration tests.")
    print()

    # Check if example files exist
    forecast_file = Path("data/examples/Gfree Forecast.xlsm")
    network_file = Path("data/examples/Network_Config.xlsx")

    print("Checking for required data files:")
    print(f"  Forecast file: {forecast_file} ... {'✓' if forecast_file.exists() else '✗ MISSING'}")
    print(f"  Network config: {network_file} ... {'✓' if network_file.exists() else '✗ MISSING'}")
    print()

    if not forecast_file.exists() or not network_file.exists():
        print("ERROR: Required data files not found. Cannot run tests.")
        return 1

    # Import test module
    try:
        from tests.test_labor_validation_integration import (
            test_example_data_with_normal_horizon,
            test_example_data_with_extended_horizon,
            test_labor_validation_distinguishes_weekdays_vs_weekends,
        )
        print("✓ Test module imported successfully")
        print()
    except ImportError as e:
        print(f"✗ Failed to import test module: {e}")
        return 1

    # Load test fixtures manually
    print("Loading test data...")
    try:
        from src.parsers.excel_parser import ExcelParser
        from src.models.truck_schedule import TruckScheduleCollection

        # Parse forecast data
        forecast_parser = ExcelParser(forecast_file)
        forecast = forecast_parser.parse_forecast()
        print(f"  ✓ Loaded forecast: {len(forecast.entries)} entries")

        # Parse network configuration
        network_parser = ExcelParser(network_file)
        locations = network_parser.parse_locations()
        routes = network_parser.parse_routes()
        labor_calendar = network_parser.parse_labor_calendar()
        truck_schedules_list = network_parser.parse_truck_schedules()
        cost_structure = network_parser.parse_cost_structure()
        print(f"  ✓ Loaded network config: {len(locations)} locations, {len(routes)} routes")

        # Check labor calendar coverage
        labor_dates = sorted([d.date for d in labor_calendar.days])
        print(f"  ✓ Labor calendar: {labor_dates[0]} to {labor_dates[-1]} ({len(labor_dates)} days)")

        # Check forecast coverage
        forecast_dates = sorted(set([e.forecast_date for e in forecast.entries]))
        print(f"  ✓ Forecast dates: {forecast_dates[0]} to {forecast_dates[-1]} ({len(forecast_dates)} days)")

        # Verify labor calendar covers forecast
        missing_dates = [d for d in forecast_dates if d not in labor_dates and d.weekday() < 5]
        if missing_dates:
            print(f"  ⚠ Warning: {len(missing_dates)} forecast weekdays not in labor calendar")
            print(f"    First few: {missing_dates[:5]}")
        else:
            print(f"  ✓ All forecast weekdays covered by labor calendar")

        # Wrap truck schedules
        truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

        # Find manufacturing site
        mfg_sites = [loc for loc in locations if loc.type == 'manufacturing']
        if not mfg_sites:
            print("  ✗ No manufacturing site found")
            return 1
        manufacturing_site = mfg_sites[0]
        print(f"  ✓ Manufacturing site: {manufacturing_site.location_id}")
        print()

    except Exception as e:
        print(f"✗ Failed to load test data: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Create fixture data tuple
    load_example_data = (forecast, locations, routes, labor_calendar, truck_schedules, cost_structure)

    # Run tests manually
    tests_run = []
    tests_passed = []
    tests_failed = []

    print("="*80)
    print("Running Tests")
    print("="*80)
    print()

    # Test 1: Normal horizon
    test_name = "test_example_data_with_normal_horizon"
    print(f"Test 1: {test_name}")
    print("-" * 80)
    try:
        test_example_data_with_normal_horizon(load_example_data, manufacturing_site)
        print(f"✓ PASS: {test_name}")
        tests_passed.append(test_name)
    except Exception as e:
        print(f"✗ FAIL: {test_name}")
        print(f"  Error: {e}")
        tests_failed.append((test_name, str(e)))
    finally:
        tests_run.append(test_name)
    print()

    # Test 2: Extended horizon
    test_name = "test_example_data_with_extended_horizon"
    print(f"Test 2: {test_name}")
    print("-" * 80)
    try:
        test_example_data_with_extended_horizon(load_example_data, manufacturing_site)
        print(f"✓ PASS: {test_name}")
        tests_passed.append(test_name)
    except Exception as e:
        print(f"✗ FAIL: {test_name}")
        print(f"  Error: {e}")
        tests_failed.append((test_name, str(e)))
    finally:
        tests_run.append(test_name)
    print()

    # Test 3: Weekday vs weekend distinction
    test_name = "test_labor_validation_distinguishes_weekdays_vs_weekends"
    print(f"Test 3: {test_name}")
    print("-" * 80)
    try:
        test_labor_validation_distinguishes_weekdays_vs_weekends(load_example_data, manufacturing_site)
        print(f"✓ PASS: {test_name}")
        tests_passed.append(test_name)
    except Exception as e:
        print(f"✗ FAIL: {test_name}")
        print(f"  Error: {e}")
        tests_failed.append((test_name, str(e)))
    finally:
        tests_run.append(test_name)
    print()

    # Summary
    print("="*80)
    print("Test Results Summary")
    print("="*80)
    print(f"Tests run:    {len(tests_run)}")
    print(f"Tests passed: {len(tests_passed)}")
    print(f"Tests failed: {len(tests_failed)}")
    print()

    if tests_failed:
        print("Failed tests:")
        for test_name, error in tests_failed:
            print(f"  ✗ {test_name}")
            print(f"    {error[:200]}...")
        print()

    # Final verdict
    print("="*80)
    print("Final Verdict:")
    print("="*80)

    if len(tests_passed) == 3:
        print("SUCCESS: All 3 previously failing tests now pass! ✓")
        print()
        print("The labor calendar extension (May 26, 2025 - Dec 31, 2026) successfully")
        print("resolved the integration test failures. Tests are now stable.")
        return 0
    else:
        print(f"FAILURE: {len(tests_failed)} of 3 tests still failing ✗")
        print()
        print("Further investigation required.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
