"""Test aggregated timing constraints to improve performance.

This script creates a modified version of the timing constraints that
aggregates over products instead of creating per-product constraints.

Expected performance improvement: 5x faster solve times.
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

# We'll need to modify the model inline for testing
from src.optimization.integrated_model import IntegratedProductionDistributionModel
from pyomo.environ import ConcreteModel, Var, Constraint, Objective, NonNegativeReals, Binary, minimize


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

all_locations = sorted(set(entry.location_id for entry in full_forecast.entries))
all_products = sorted(set(entry.product_id for entry in full_forecast.entries))


def create_test_forecast(start_date, num_days, products, location_ids):
    """Create filtered forecast for testing."""
    end_date = start_date + timedelta(days=num_days - 1)

    filtered_entries = [
        entry for entry in full_forecast.entries
        if (entry.forecast_date >= start_date and
            entry.forecast_date <= end_date and
            entry.product_id in products and
            entry.location_id in location_ids)
    ]

    return Forecast(name="Test Forecast", entries=filtered_entries)


# Monkey-patch the IntegratedProductionDistributionModel to use aggregated timing constraints
original_build_model = IntegratedProductionDistributionModel.build_model


def build_model_with_aggregated_timing(self):
    """Build model with aggregated timing constraints instead of per-product."""
    # Call original build_model but we'll replace the timing constraints
    model = original_build_model(self)

    # Remove old per-product timing constraints if they exist
    if hasattr(model, 'truck_morning_timing_con'):
        model.del_component('truck_morning_timing_con')
    if hasattr(model, 'truck_afternoon_timing_con'):
        model.del_component('truck_afternoon_timing_con')

    # Build sparse index set for aggregated constraints
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

    # Aggregated timing constraints (sum over products)
    def truck_morning_timing_agg_rule(model, truck_idx, dest, departure_date):
        """Morning trucks: total load <= total D-1 production (aggregated over products)."""
        truck = self.truck_by_index[truck_idx]
        if truck.departure_type != 'morning':
            return Constraint.Skip

        d_minus_1 = departure_date - timedelta(days=1)
        if d_minus_1 not in model.dates:
            return sum(model.truck_load[truck_idx, dest, p, departure_date] for p in model.products) == 0

        # Aggregate: sum of loads <= sum of D-1 production
        return (sum(model.truck_load[truck_idx, dest, p, departure_date] for p in model.products) <=
                sum(model.production[d_minus_1, p] for p in model.products))

    def truck_afternoon_timing_agg_rule(model, truck_idx, dest, departure_date):
        """Afternoon trucks: total load <= total D-1 + D0 production (aggregated)."""
        truck = self.truck_by_index[truck_idx]
        if truck.departure_type != 'afternoon':
            return Constraint.Skip

        d_minus_1 = departure_date - timedelta(days=1)
        if d_minus_1 not in model.dates:
            return sum(model.truck_load[truck_idx, dest, p, departure_date] for p in model.products) == 0

        # Aggregate: sum of loads <= sum of (D-1 + D0) production
        return (sum(model.truck_load[truck_idx, dest, p, departure_date] for p in model.products) <=
                sum(model.production[d_minus_1, p] + model.production[departure_date, p] for p in model.products))

    # Create new aggregated constraints
    morning_tuples = [(t, d, dt) for (t, d, dt) in valid_truck_dest_date_tuples
                      if self.truck_by_index[t].departure_type == 'morning']
    afternoon_tuples = [(t, d, dt) for (t, d, dt) in valid_truck_dest_date_tuples
                        if self.truck_by_index[t].departure_type == 'afternoon']

    if morning_tuples:
        model.truck_morning_timing_agg_con = Constraint(
            morning_tuples,
            rule=truck_morning_timing_agg_rule,
            doc="Morning trucks load D-1 production (aggregated over products)"
        )
        print(f"  Created {len(morning_tuples)} aggregated morning timing constraints")

    if afternoon_tuples:
        model.truck_afternoon_timing_agg_con = Constraint(
            afternoon_tuples,
            rule=truck_afternoon_timing_agg_rule,
            doc="Afternoon trucks load D-1 or D0 production (aggregated over products)"
        )
        print(f"  Created {len(afternoon_tuples)} aggregated afternoon timing constraints")

    return model


# Apply monkey patch
IntegratedProductionDistributionModel.build_model = build_model_with_aggregated_timing


def run_test(name, num_destinations, num_days=14):
    """Run test with aggregated timing constraints."""
    locations_subset = all_locations[:num_destinations]

    print(f"\n{'='*80}")
    print(f"TEST: {name}")
    print(f"Destinations: {num_destinations}, Days: {num_days}")
    print(f"{'='*80}")

    forecast = create_test_forecast(
        start_date=date(2025, 6, 2),
        num_days=num_days,
        products=all_products,
        location_ids=locations_subset,
    )

    print(f"Building model...")
    build_start = time.time()
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
    build_time = time.time() - build_start

    print(f"Model built in {build_time:.2f}s")

    print("Solving...")
    result = model_obj.solve(
        solver_name='cbc',
        time_limit_seconds=60,
        mip_gap=0.05,
        tee=False,
    )

    print(f"\nRESULTS:")
    print(f"  Status: {result.termination_condition}")
    print(f"  Solve time: {result.solve_time_seconds:.2f}s")
    if result.objective_value:
        print(f"  Objective: ${result.objective_value:,.2f}")

    return {
        'num_destinations': num_destinations,
        'solve_time': result.solve_time_seconds,
        'status': result.termination_condition,
    }


# Run tests
results = []

print("\n" + "="*80)
print("TESTING AGGREGATED TIMING CONSTRAINTS")
print("="*80)

for n_dest in [2, 3, 4, 5, 6, 7, 8, 9]:
    result = run_test(f"Aggregated timing, {n_dest} destinations", n_dest, num_days=14)
    results.append(result)

    if result['solve_time'] and result['solve_time'] > 30:
        print(f"\n⚠️  Still slow at {n_dest} destinations")
        break

# Summary
print(f"\n{'='*80}")
print("COMPARISON: Original vs Aggregated")
print(f"{'='*80}")
print(f"{'Dest':<6} {'Original Time':<15} {'Aggregated Time':<15} {'Speedup':<10}")
print(f"{'-'*80}")

original_times = {
    2: 0.27,
    3: 0.29,
    4: 0.41,
    5: 2.04,
    6: 9.70,
    7: '>60s',
}

for r in results:
    n = r['num_destinations']
    orig = original_times.get(n, 'N/A')
    agg_time = f"{r['solve_time']:.2f}s" if r['solve_time'] else 'N/A'

    if isinstance(orig, float) and r['solve_time']:
        speedup = f"{orig / r['solve_time']:.2f}x"
    else:
        speedup = "N/A"

    print(f"{n:<6} {str(orig):<15} {agg_time:<15} {speedup:<10}")
