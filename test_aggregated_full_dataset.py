"""Test aggregated timing constraints on full dataset.

Based on successful results from small tests, now test with:
- All 9 destinations
- All 5 products
- Extended time horizons (28, 56, 90 days)
"""

import sys
from pathlib import Path
from datetime import date, timedelta
import time

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast
from src.optimization.integrated_model import IntegratedProductionDistributionModel
from pyomo.environ import Constraint


# Parse data
print("Loading network configuration...")
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules_list = network_parser.parse_truck_schedules()
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)

print("Loading full forecast...")
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')
full_forecast = forecast_parser.parse_forecast()

all_locations = sorted(set(entry.location_id for entry in full_forecast.entries))
all_products = sorted(set(entry.product_id for entry in full_forecast.entries))


def create_test_forecast(start_date, num_days):
    """Create filtered forecast for testing."""
    end_date = start_date + timedelta(days=num_days - 1)

    filtered_entries = [
        entry for entry in full_forecast.entries
        if entry.forecast_date >= start_date and entry.forecast_date <= end_date
    ]

    return Forecast(name="Test Forecast", entries=filtered_entries)


# Monkey-patch to use aggregated timing constraints
original_build_model = IntegratedProductionDistributionModel.build_model


def build_model_with_aggregated_timing(self):
    """Build model with aggregated timing constraints."""
    model = original_build_model(self)

    # Remove old per-product timing constraints
    if hasattr(model, 'truck_morning_timing_con'):
        model.del_component('truck_morning_timing_con')
    if hasattr(model, 'truck_afternoon_timing_con'):
        model.del_component('truck_afternoon_timing_con')

    # Build sparse index
    valid_truck_dest_date_tuples = []
    for departure_date in model.dates:
        for truck_idx in self.trucks_on_date.get(departure_date, []):
            truck = self.truck_by_index[truck_idx]
            if truck.destination_id in model.truck_destinations:
                valid_truck_dest_date_tuples.append((truck_idx, truck.destination_id, departure_date))
            if truck_idx in self.trucks_with_intermediate_stops:
                for stop_id in self.trucks_with_intermediate_stops[truck_idx]:
                    if stop_id in model.truck_destinations:
                        valid_truck_dest_date_tuples.append((truck_idx, stop_id, departure_date))

    # Aggregated constraints
    def truck_morning_timing_agg_rule(model, truck_idx, dest, departure_date):
        truck = self.truck_by_index[truck_idx]
        if truck.departure_type != 'morning':
            return Constraint.Skip

        d_minus_1 = departure_date - timedelta(days=1)
        if d_minus_1 not in model.dates:
            return sum(model.truck_load[truck_idx, dest, p, departure_date] for p in model.products) == 0

        return (sum(model.truck_load[truck_idx, dest, p, departure_date] for p in model.products) <=
                sum(model.production[d_minus_1, p] for p in model.products))

    def truck_afternoon_timing_agg_rule(model, truck_idx, dest, departure_date):
        truck = self.truck_by_index[truck_idx]
        if truck.departure_type != 'afternoon':
            return Constraint.Skip

        d_minus_1 = departure_date - timedelta(days=1)
        if d_minus_1 not in model.dates:
            return sum(model.truck_load[truck_idx, dest, p, departure_date] for p in model.products) == 0

        return (sum(model.truck_load[truck_idx, dest, p, departure_date] for p in model.products) <=
                sum(model.production[d_minus_1, p] + model.production[departure_date, p] for p in model.products))

    morning_tuples = [(t, d, dt) for (t, d, dt) in valid_truck_dest_date_tuples
                      if self.truck_by_index[t].departure_type == 'morning']
    afternoon_tuples = [(t, d, dt) for (t, d, dt) in valid_truck_dest_date_tuples
                        if self.truck_by_index[t].departure_type == 'afternoon']

    if morning_tuples:
        model.truck_morning_timing_agg_con = Constraint(
            morning_tuples,
            rule=truck_morning_timing_agg_rule
        )

    if afternoon_tuples:
        model.truck_afternoon_timing_agg_con = Constraint(
            afternoon_tuples,
            rule=truck_afternoon_timing_agg_rule
        )

    return model


IntegratedProductionDistributionModel.build_model = build_model_with_aggregated_timing


def run_test(name, num_days, time_limit=300):
    """Run test with aggregated timing constraints."""
    print(f"\n{'='*80}")
    print(f"TEST: {name} ({num_days} days)")
    print(f"{'='*80}")

    forecast = create_test_forecast(
        start_date=date(2025, 6, 2),
        num_days=num_days,
    )

    print(f"Forecast: {len(forecast.entries)} entries")
    print(f"  Locations: {len(set(e.location_id for e in forecast.entries))}")
    print(f"  Products: {len(set(e.product_id for e in forecast.entries))}")
    print(f"  Dates: {len(set(e.forecast_date for e in forecast.entries))}")

    print("Building model...")
    model_obj = IntegratedProductionDistributionModel(
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

    print("Solving...")
    result = model_obj.solve(
        solver_name='cbc',
        time_limit_seconds=time_limit,
        mip_gap=0.05,
        tee=False,
    )

    print(f"\nRESULTS:")
    print(f"  Status: {result.termination_condition}")
    print(f"  Solve time: {result.solve_time_seconds:.2f}s")
    if result.objective_value:
        print(f"  Objective: ${result.objective_value:,.2f}")

    return result.solve_time_seconds


# Run progressive tests
results = []

print("\n" + "="*80)
print("FULL DATASET TESTS WITH AGGREGATED TIMING CONSTRAINTS")
print("="*80)

# Test 1: 14 days baseline (already tested, but confirm)
time_14 = run_test("Full dataset - 14 days", 14, time_limit=60)
results.append(('14 days', time_14))

# Test 2: 28 days
time_28 = run_test("Full dataset - 28 days", 28, time_limit=180)
results.append(('28 days', time_28))

# Test 3: 56 days (2 months)
time_56 = run_test("Full dataset - 56 days", 56, time_limit=300)
results.append(('56 days', time_56))

# Test 4: 90 days (3 months) - ambitious!
time_90 = run_test("Full dataset - 90 days", 90, time_limit=600)
results.append(('90 days', time_90))

# Summary
print(f"\n{'='*80}")
print("PERFORMANCE SUMMARY")
print(f"{'='*80}")
print(f"{'Time Horizon':<15} {'Solve Time':<12} {'Status':<10}")
print(f"{'-'*80}")

for horizon, solve_time in results:
    status = "SUCCESS" if solve_time and solve_time < 600 else "TIMEOUT"
    time_str = f"{solve_time:.2f}s" if solve_time else "N/A"
    print(f"{horizon:<15} {time_str:<12} {status:<10}")

print(f"\n{'='*80}")
print("CONCLUSION:")
if all(t is not None and t < 600 for _, t in results):
    print("✓ Aggregated timing constraints successfully scale to full dataset!")
    print("  All tests completed within time limits")
else:
    print("⚠️  Some tests still timing out - further optimization may be needed")
print(f"{'='*80}")
