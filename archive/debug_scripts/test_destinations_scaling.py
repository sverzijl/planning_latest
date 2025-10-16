"""Test scaling with number of destinations to find performance cliff.

Previous diagnostic showed:
- 3 destinations: 0.47s (28 days)
- 9 destinations: >180s timeout (28 days)

This test progressively adds destinations to find the threshold.
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


# Parse network data
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

# Get all locations ordered by demand volume
all_locations = sorted(set(entry.location_id for entry in full_forecast.entries))
all_products = sorted(set(entry.product_id for entry in full_forecast.entries))

print(f"All locations: {all_locations}")
print(f"All products: {all_products}")


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


def run_test(num_destinations, num_days=14, time_limit=60):
    """Run test with specified number of destinations."""
    locations_subset = all_locations[:num_destinations]

    print(f"\n{'='*80}")
    print(f"Testing {num_destinations} destinations, {num_days} days")
    print(f"Locations: {locations_subset}")
    print(f"{'='*80}")

    forecast = create_test_forecast(
        start_date=date(2025, 6, 2),
        num_days=num_days,
        products=all_products,
        locations=locations_subset,
    )

    print(f"Forecast entries: {len(forecast.entries)}")

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
        max_routes_per_destination=5,
        allow_shortages=True,
        enforce_shelf_life=True,
    )
    build_time = time.time() - build_start

    print(f"Model built in {build_time:.2f}s")
    print(f"  Routes: {len(model.enumerated_routes)}")
    print(f"  Trucks: {len(model.truck_indices)}")

    # Solve
    print(f"Solving (timeout={time_limit}s)...")
    solve_start = time.time()
    result = model.solve(
        solver_name='cbc',
        time_limit_seconds=time_limit,
        mip_gap=0.05,
        tee=False,
    )
    solve_time = time.time() - solve_start

    print(f"Status: {result.termination_condition}")
    print(f"Solve time: {solve_time:.2f}s")

    return {
        'num_destinations': num_destinations,
        'num_days': num_days,
        'num_routes': len(model.enumerated_routes),
        'build_time': build_time,
        'solve_time': solve_time,
        'status': result.termination_condition,
    }


# Run tests with increasing destinations
results = []

# Short horizon (14 days) tests
print("\n" + "="*80)
print("SHORT HORIZON TESTS (14 days)")
print("="*80)

for n_dest in [2, 3, 4, 5, 6, 7, 8, 9]:
    result = run_test(n_dest, num_days=14, time_limit=60)
    results.append(result)

    # Stop if solve time exceeds 30s
    if result['solve_time'] > 30:
        print(f"\n⚠️  Performance degraded at {n_dest} destinations")
        print(f"    Solve time: {result['solve_time']:.2f}s")
        break

# Summary
print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}")
print(f"{'Destinations':<15} {'Routes':<10} {'Build':<10} {'Solve':<10} {'Status':<15}")
print(f"{'-'*80}")

for r in results:
    print(f"{r['num_destinations']:<15} {r['num_routes']:<10} {r['build_time']:>8.2f}s  {r['solve_time']:>8.2f}s  {r['status']:<15}")

# Identify scaling
if len(results) > 1:
    print(f"\n{'='*80}")
    print("SCALING ANALYSIS")
    print(f"{'='*80}")

    for i in range(1, len(results)):
        prev = results[i-1]
        curr = results[i]

        dest_ratio = curr['num_destinations'] / prev['num_destinations']
        route_ratio = curr['num_routes'] / prev['num_routes']
        time_ratio = curr['solve_time'] / prev['solve_time'] if prev['solve_time'] > 0 else float('inf')

        print(f"{prev['num_destinations']} → {curr['num_destinations']} destinations:")
        print(f"  Routes: {prev['num_routes']} → {curr['num_routes']} ({route_ratio:.2f}x)")
        print(f"  Solve time: {prev['solve_time']:.2f}s → {curr['solve_time']:.2f}s ({time_ratio:.2f}x)")
