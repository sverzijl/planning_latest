"""Performance diagnostic suite for D-1/D0 timing constraints.

This script creates progressively more complex test cases to isolate
where solve time becomes problematic.

Test progression:
1. Baseline: 2 destinations (direct routes only), 2 products, 2 weeks
2. Add multi-leg routes (include hub routing)
3. Add more products
4. Add more destinations
5. Extend time horizon
6. Full dataset
"""

import sys
from pathlib import Path
from datetime import date, timedelta
import time

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast, ForecastEntry


# Parse network data (full)
print("Loading network configuration...")
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules_list = network_parser.parse_truck_schedules()
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)

# Parse full forecast
print("Loading full forecast...")
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')
full_forecast = forecast_parser.parse_forecast()

# Get all available products and locations
all_products = sorted(set(entry.product_id for entry in full_forecast.entries))
all_locations = sorted(set(entry.location_id for entry in full_forecast.entries))

print(f"Full dataset: {len(all_products)} products, {len(all_locations)} locations")
print(f"Products: {all_products}")
print(f"Locations: {all_locations}")


def create_test_forecast(start_date, num_days, products, locations):
    """Create filtered forecast for testing."""
    end_date = start_date + timedelta(days=num_days - 1)

    filtered_entries = [
        entry for entry in full_forecast.entries
        if (entry.forecast_date >= start_date and
            entry.forecast_date <= end_date and
            entry.product_id in products and
            entry.location_id in locations)
    ]

    return Forecast(name="Test Forecast", entries=filtered_entries)


def run_test(name, forecast, max_routes=5, time_limit=60):
    """Run optimization test and return diagnostics."""
    print(f"\n{'='*80}")
    print(f"TEST: {name}")
    print(f"{'='*80}")

    num_products = len(set(entry.product_id for entry in forecast.entries))
    num_locations = len(set(entry.location_id for entry in forecast.entries))
    num_dates = len(set(entry.forecast_date for entry in forecast.entries))
    num_entries = len(forecast.entries)

    print(f"Forecast: {num_entries} entries")
    print(f"  Products: {num_products}")
    print(f"  Locations: {num_locations}")
    print(f"  Dates: {num_dates}")

    # Build model
    build_start = time.time()
    model = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing_site,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        truck_schedules=truck_schedules,
        max_routes_per_destination=max_routes,
        allow_shortages=True,
        enforce_shelf_life=True,
    )
    build_time = time.time() - build_start

    print(f"Model built in {build_time:.2f}s")
    print(f"  Routes enumerated: {len(model.enumerated_routes)}")
    print(f"  Production dates: {len(model.production_dates)}")
    print(f"  Trucks: {len(model.truck_indices)}")

    # Solve
    print(f"Solving (timeout={time_limit}s)...")
    result = model.solve(
        solver_name='cbc',
        time_limit_seconds=time_limit,
        mip_gap=0.05,
        tee=False,
    )

    # Results
    print(f"\nRESULTS:")
    print(f"  Status: {result.termination_condition}")
    print(f"  Solve time: {result.solve_time_seconds:.2f}s")
    if result.objective_value:
        print(f"  Objective: ${result.objective_value:,.2f}")

    # Return diagnostics
    return {
        'name': name,
        'num_products': num_products,
        'num_locations': num_locations,
        'num_dates': num_dates,
        'num_entries': num_entries,
        'num_routes': len(model.enumerated_routes),
        'num_trucks': len(model.truck_indices),
        'build_time': build_time,
        'solve_time': result.solve_time_seconds,
        'status': result.termination_condition,
        'objective': result.objective_value,
    }


# Run progressive tests
results = []

# Test 1: Baseline (2 destinations, direct routes only, 2 products, 2 weeks)
# Locations 6104 and 6110 are served directly by trucks from 6122
test1_forecast = create_test_forecast(
    start_date=date(2025, 6, 2),  # Monday
    num_days=14,
    products=['168846', '168847'],  # First 2 products
    locations=['6104', '6110'],  # Direct truck destinations
)
results.append(run_test("Test 1: Baseline (2 dest direct, 2 prod, 14 days)", test1_forecast))

# Test 2: Add multi-leg routes (include 6103 via 6104 hub)
# 6103 is served via 6104: 6122 -> 6104 -> 6103
test2_forecast = create_test_forecast(
    start_date=date(2025, 6, 2),
    num_days=14,
    products=['168846', '168847'],
    locations=['6103', '6104', '6110'],  # Add 6103 (multi-leg via 6104)
)
results.append(run_test("Test 2: Add multi-leg route (3 dest, 2 prod, 14 days)", test2_forecast))

# Test 3: Add more products (5 products)
test3_forecast = create_test_forecast(
    start_date=date(2025, 6, 2),
    num_days=14,
    products=all_products,  # All 5 products
    locations=['6103', '6104', '6110'],
)
results.append(run_test("Test 3: More products (3 dest, 5 prod, 14 days)", test3_forecast))

# Test 4: Add more destinations (6 destinations)
test4_forecast = create_test_forecast(
    start_date=date(2025, 6, 2),
    num_days=14,
    products=all_products,
    locations=['6103', '6104', '6110', '6111', '6128', '6129'],  # 6 destinations
)
results.append(run_test("Test 4: More destinations (6 dest, 5 prod, 14 days)", test4_forecast))

# Test 5: Extend time horizon (4 weeks = 28 days)
test5_forecast = create_test_forecast(
    start_date=date(2025, 6, 2),
    num_days=28,
    products=all_products,
    locations=['6103', '6104', '6110', '6111', '6128', '6129'],
)
results.append(run_test("Test 5: Longer horizon (6 dest, 5 prod, 28 days)", test5_forecast, time_limit=120))

# Test 6: All destinations, 4 weeks
test6_forecast = create_test_forecast(
    start_date=date(2025, 6, 2),
    num_days=28,
    products=all_products,
    locations=all_locations,  # All 9 destinations
)
results.append(run_test("Test 6: All destinations (9 dest, 5 prod, 28 days)", test6_forecast, time_limit=180))

# Test 7: All destinations, 8 weeks
test7_forecast = create_test_forecast(
    start_date=date(2025, 6, 2),
    num_days=56,
    products=all_products,
    locations=all_locations,
)
results.append(run_test("Test 7: Extended horizon (9 dest, 5 prod, 56 days)", test7_forecast, time_limit=300))

# Print summary
print(f"\n{'='*80}")
print("SUMMARY OF RESULTS")
print(f"{'='*80}")
print(f"{'Test':<50} {'Solve Time':<12} {'Status':<15}")
print(f"{'-'*80}")

for r in results:
    status_color = "✓" if r['status'] == 'optimal' else "✗"
    print(f"{r['name']:<50} {r['solve_time']:>10.2f}s  {status_color} {r['status']:<15}")

print(f"\n{'='*80}")
print("DETAILED METRICS")
print(f"{'='*80}")
print(f"{'Test':<30} {'Prod':<6} {'Loc':<5} {'Days':<6} {'Routes':<8} {'Trucks':<8} {'Build':<8} {'Solve':<10}")
print(f"{'-'*80}")

for r in results:
    print(f"{r['name']:<30} {r['num_products']:<6} {r['num_locations']:<5} {r['num_dates']:<6} "
          f"{r['num_routes']:<8} {r['num_trucks']:<8} {r['build_time']:>6.2f}s  {r['solve_time']:>8.2f}s")

# Identify performance threshold
print(f"\n{'='*80}")
print("PERFORMANCE ANALYSIS")
print(f"{'='*80}")

slow_threshold = 10.0  # seconds
for r in results:
    if r['solve_time'] > slow_threshold:
        print(f"⚠️  {r['name']} is SLOW ({r['solve_time']:.2f}s)")
        print(f"    Complexity: {r['num_products']} prod × {r['num_locations']} loc × {r['num_dates']} days")
        print(f"    Model size: {r['num_routes']} routes, {r['num_trucks']} trucks")
        break
else:
    print("✓ All tests completed within acceptable time")
