"""Analyze constraint interactions to diagnose performance issues.

This script examines:
1. Which variables appear in timing constraints
2. How timing constraints interact with other constraints
3. Potential big-M issues or weak formulations
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
from pyomo.environ import Var, Constraint, value


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


def analyze_constraints(num_destinations, num_days=14):
    """Analyze constraint structure."""
    locations_subset = all_locations[:num_destinations]

    print(f"\n{'='*80}")
    print(f"CONSTRAINT ANALYSIS: {num_destinations} destinations, {num_days} days")
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

    model = model_obj.build_model()

    # Analyze variables
    print("\nVARIABLE ANALYSIS:")

    var_types = {}
    for var_obj in model.component_objects(ctype=Var, active=True):
        var_name = var_obj.name
        count = len([idx for idx in var_obj])
        binary_count = sum(1 for idx in var_obj if var_obj[idx].is_binary())

        var_types[var_name] = {
            'count': count,
            'binary_count': binary_count,
        }

        if count > 0:
            var_type = "binary" if binary_count == count else "continuous" if binary_count == 0 else "mixed"
            print(f"  {var_name:<30} {count:>6} variables ({var_type})")

    # Examine timing constraint structure
    print("\nTIMING CONSTRAINT DETAILS:")

    if hasattr(model, 'truck_morning_timing_con'):
        print(f"\nMorning timing constraints: {len(model.truck_morning_timing_con)}")
        # Show first few constraints to understand structure
        count = 0
        for index in model.truck_morning_timing_con:
            if count < 3:
                con = model.truck_morning_timing_con[index]
                print(f"  Example {count + 1}: {index}")
                print(f"    Constraint: {con.expr}")
                count += 1

    if hasattr(model, 'truck_afternoon_timing_con'):
        print(f"\nAfternoon timing constraints: {len(model.truck_afternoon_timing_con)}")
        count = 0
        for index in model.truck_afternoon_timing_con:
            if count < 3:
                con = model.truck_afternoon_timing_con[index]
                print(f"  Example {count + 1}: {index}")
                print(f"    Constraint: {con.expr}")
                count += 1

    # Examine flow conservation constraint
    print("\nFLOW CONSERVATION CONSTRAINT DETAILS:")
    if hasattr(model, 'flow_conservation_con'):
        print(f"Total flow conservation constraints: {len(model.flow_conservation_con)}")
        count = 0
        for index in model.flow_conservation_con:
            if count < 2:
                con = model.flow_conservation_con[index]
                print(f"  Example {count + 1}: {index}")
                print(f"    Constraint: {con.expr}")
                count += 1

    # Examine truck route linking
    print("\nTRUCK-ROUTE LINKING CONSTRAINT DETAILS:")
    if hasattr(model, 'truck_route_linking_con'):
        print(f"Total truck-route linking constraints: {len(model.truck_route_linking_con)}")
        count = 0
        for index in model.truck_route_linking_con:
            if count < 2:
                con = model.truck_route_linking_con[index]
                print(f"  Example {count + 1}: {index}")
                print(f"    Constraint: {con.expr}")
                count += 1

    # Check for problematic patterns
    print("\n" + "="*80)
    print("POTENTIAL ISSUES:")
    print("="*80)

    # Check if truck_load appears in many constraints
    truck_load_constraints = []
    for con_obj in model.component_objects(ctype=Constraint, active=True):
        con_name = con_obj.name
        has_truck_load = False

        for index in con_obj:
            con_expr = str(con_obj[index].expr)
            if 'truck_load' in con_expr:
                has_truck_load = True
                break

        if has_truck_load:
            truck_load_constraints.append(con_name)

    print(f"\nConstraints involving truck_load variable:")
    for con_name in truck_load_constraints:
        print(f"  - {con_name}")

    # Check if production variable appears in timing constraints
    print(f"\nCritical observation:")
    print(f"  The timing constraints link truck_load ≤ production[d-1] (or d-1+d0)")
    print(f"  This creates indirect coupling between:")
    print(f"    - truck_load (appears in: truck_route_linking, timing, capacity)")
    print(f"    - production (appears in: timing, flow_conservation)")
    print(f"    - shipment (appears in: truck_route_linking, flow_conservation, demand)")
    print(f"  Each destination adds more truck_load variables and timing constraints")
    print(f"  This creates a dense constraint matrix that's hard for MIP solvers")


# Analyze 2, 4, and 6 destinations
for n_dest in [2, 4, 6]:
    analyze_constraints(n_dest, num_days=14)
