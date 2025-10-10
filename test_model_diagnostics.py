"""Detailed model diagnostics to understand constraint growth.

This script builds models with different sizes and reports:
- Number of variables (continuous, binary, integer)
- Number of constraints (by type)
- LP relaxation quality
- Model structure insights
"""

import sys
from pathlib import Path
from datetime import date, timedelta

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast
from pyomo.environ import value, Var, Constraint


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


def analyze_model(num_destinations, num_days=14):
    """Build model and analyze structure."""
    locations_subset = all_locations[:num_destinations]

    print(f"\n{'='*80}")
    print(f"MODEL ANALYSIS: {num_destinations} destinations, {num_days} days")
    print(f"{'='*80}")

    forecast = create_test_forecast(
        start_date=date(2025, 6, 2),
        num_days=num_days,
        products=all_products,
        locations=locations_subset,
    )

    # Build model
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

    # Build the Pyomo model by calling build_model directly
    model = model_obj.build_model()

    # Count variables
    num_vars = 0
    num_continuous = 0
    num_binary = 0
    num_integer = 0

    for var in model.component_objects(ctype=Var, active=True):
        for index in var:
            num_vars += 1
            if var[index].is_binary():
                num_binary += 1
            elif var[index].is_integer():
                num_integer += 1
            else:
                num_continuous += 1

    # Count constraints
    constraint_counts = {}
    total_constraints = 0

    for con in model.component_objects(ctype=Constraint, active=True):
        con_name = con.name
        con_count = len([index for index in con])
        constraint_counts[con_name] = con_count
        total_constraints += con_count

    print(f"\nVARIABLES:")
    print(f"  Total: {num_vars:,}")
    print(f"  Continuous: {num_continuous:,}")
    print(f"  Binary: {num_binary:,}")
    print(f"  Integer: {num_integer:,}")

    print(f"\nCONSTRAINTS:")
    print(f"  Total: {total_constraints:,}")
    for con_name, count in sorted(constraint_counts.items(), key=lambda x: -x[1]):
        pct = 100.0 * count / total_constraints if total_constraints > 0 else 0
        print(f"  {con_name:<40} {count:>8,} ({pct:>5.1f}%)")

    print(f"\nMODEL DIMENSIONS:")
    print(f"  Products: {len(model.products)}")
    print(f"  Destinations: {len(model_obj.destinations)}")
    print(f"  Dates: {len(model.dates)}")
    print(f"  Routes: {len(model.routes)}")
    print(f"  Trucks: {len(model.trucks)}")
    print(f"  Truck destinations: {len(model.truck_destinations)}")

    return {
        'num_destinations': num_destinations,
        'num_vars': num_vars,
        'num_continuous': num_continuous,
        'num_binary': num_binary,
        'num_integer': num_integer,
        'num_constraints': total_constraints,
        'constraint_counts': constraint_counts,
    }


# Analyze models with different sizes
results = []

for n_dest in [2, 3, 4, 5, 6, 7]:
    result = analyze_model(n_dest, num_days=14)
    results.append(result)

# Summary comparison
print(f"\n{'='*80}")
print("SCALING SUMMARY")
print(f"{'='*80}")
print(f"{'Dest':<6} {'Total Vars':<12} {'Binary':<10} {'Constraints':<12} {'Vars Growth':<12} {'Cons Growth':<12}")
print(f"{'-'*80}")

prev_result = None
for r in results:
    var_growth = ""
    con_growth = ""

    if prev_result:
        var_ratio = r['num_vars'] / prev_result['num_vars']
        con_ratio = r['num_constraints'] / prev_result['num_constraints']
        var_growth = f"{var_ratio:.2f}x"
        con_growth = f"{con_ratio:.2f}x"

    print(f"{r['num_destinations']:<6} {r['num_vars']:<12,} {r['num_binary']:<10,} {r['num_constraints']:<12,} {var_growth:<12} {con_growth:<12}")

    prev_result = r

# Identify which constraints are growing fastest
print(f"\n{'='*80}")
print("CONSTRAINT GROWTH ANALYSIS")
print(f"{'='*80}")

if len(results) >= 2:
    r1 = results[0]  # 2 destinations
    r2 = results[-1]  # Last destination count

    print(f"Comparing {r1['num_destinations']} vs {r2['num_destinations']} destinations:")
    col1_header = f"Count @{r1['num_destinations']}"
    col2_header = f"Count @{r2['num_destinations']}"
    print(f"{'Constraint Type':<40} {col1_header:<15} {col2_header:<15} {'Growth':<10}")
    print(f"{'-'*80}")

    for con_name in r1['constraint_counts']:
        count1 = r1['constraint_counts'][con_name]
        count2 = r2['constraint_counts'].get(con_name, 0)
        growth = count2 / count1 if count1 > 0 else 0

        print(f"{con_name:<40} {count1:>13,} {count2:>13,} {growth:>8.2f}x")
