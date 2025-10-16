"""
Trace 6122_Storage inventory daily to find where the gap occurs.
"""
import sys
from pathlib import Path
from datetime import timedelta

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from pyomo.environ import value

print("=" * 90)
print("DAILY TRACE: 6122_Storage Inventory Balance")
print("=" * 90)

print("\n📊 Loading and solving...")
network_parser = ExcelParser("data/examples/Network_Config.xlsx")
forecast_parser = ExcelParser("data/examples/Gfree Forecast_Converted.xlsx")

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = network_parser.parse_truck_schedules()
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.location_id == '6122'), None)
forecast = forecast_parser.parse_forecast()

product_ids = sorted(set(e.product_id for e in forecast.entries))

initial_inv = {}
for pid in product_ids:
    initial_inv[('6122_Storage', pid, 'ambient')] = 15000.0

model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=TruckScheduleCollection(schedules=truck_schedules),
    max_routes_per_destination=5,
    allow_shortages=True,
    enforce_shelf_life=True,
    initial_inventory=initial_inv
)

result = model.solve(
    solver_name='cbc',
    time_limit_seconds=600,
    mip_gap=0.01,
    use_aggressive_heuristics=True,
    tee=False
)

if not result.success:
    print("\n❌ Solve failed")
    sys.exit(1)

print(f"✅ Solved in {result.solve_time_seconds:.1f}s\n")

pyomo_model = model.model
dates_list = sorted(list(pyomo_model.dates))
products_list = sorted(list(pyomo_model.products))

# Trace daily balance
print("=" * 90)
print("FIRST 30 DAYS: 6122_Storage Daily Balance")
print("=" * 90)

print(f"\n{'Date':<12} {'Production':>12} {'Truck Loads':>12} {'End Inv':>12} {'Calc Inv':>12} {'Diff':>12}")
print("-" * 90)

cumulative_prod = 0
cumulative_loads = 0
total_initial = sum(initial_inv.values())

for i, date in enumerate(dates_list[:30]):
    # Production on this date
    production = sum(value(pyomo_model.production[date, p]) for p in products_list)
    cumulative_prod += production

    # Truck loads departing on this date
    truck_loads_today = 0
    for truck_idx in pyomo_model.trucks:
        for dest in pyomo_model.truck_destinations:
            transit_days = model._get_truck_transit_days(truck_idx, dest)

            for delivery_date in dates_list:
                departure_date = delivery_date - timedelta(days=transit_days)
                if departure_date == date:
                    truck_loads_today += sum(
                        value(pyomo_model.truck_load[truck_idx, dest, p, delivery_date])
                        for p in products_list
                    )

    cumulative_loads += truck_loads_today

    # Inventory at end of this date (from model)
    end_inv = sum(
        value(pyomo_model.inventory_ambient['6122_Storage', p, date])
        for p in products_list
        if ('6122_Storage', p, date) in model.inventory_ambient_index_set
    )

    # Calculated inventory (what it should be)
    calc_inv = total_initial + cumulative_prod - cumulative_loads

    diff = end_inv - calc_inv

    print(f"{date.strftime('%Y-%m-%d'):<12} {production:>12,.0f} {truck_loads_today:>12,.0f} {end_inv:>12,.0f} {calc_inv:>12,.0f} {diff:>12,.0f}")

# Now check the LAST 30 days
print(f"\n{'=' * 90}")
print("LAST 30 DAYS: 6122_Storage Daily Balance")
print("=" * 90)

print(f"\n{'Date':<12} {'Production':>12} {'Truck Loads':>12} {'End Inv':>12} {'Calc Inv':>12} {'Diff':>12}")
print("-" * 90)

# Recalculate cumulative from start for last 30 days
for i, date in enumerate(dates_list[-30:]):
    # Get cumulative up to this date
    dates_up_to = [d for d in dates_list if d <= date]

    cumulative_prod = sum(
        value(pyomo_model.production[d, p])
        for d in dates_up_to
        for p in products_list
    )

    cumulative_loads = 0
    for d in dates_up_to:
        for truck_idx in pyomo_model.trucks:
            for dest in pyomo_model.truck_destinations:
                transit_days = model._get_truck_transit_days(truck_idx, dest)

                for delivery_date in dates_list:
                    departure_date = delivery_date - timedelta(days=transit_days)
                    if departure_date == d:
                        cumulative_loads += sum(
                            value(pyomo_model.truck_load[truck_idx, dest, p, delivery_date])
                            for p in products_list
                        )

    # Production on this date
    production = sum(value(pyomo_model.production[date, p]) for p in products_list)

    # Truck loads departing on this date
    truck_loads_today = 0
    for truck_idx in pyomo_model.trucks:
        for dest in pyomo_model.truck_destinations:
            transit_days = model._get_truck_transit_days(truck_idx, dest)

            for delivery_date in dates_list:
                departure_date = delivery_date - timedelta(days=transit_days)
                if departure_date == date:
                    truck_loads_today += sum(
                        value(pyomo_model.truck_load[truck_idx, dest, p, delivery_date])
                        for p in products_list
                    )

    # Inventory at end of this date (from model)
    end_inv = sum(
        value(pyomo_model.inventory_ambient['6122_Storage', p, date])
        for p in products_list
        if ('6122_Storage', p, date) in model.inventory_ambient_index_set
    )

    # Calculated inventory (what it should be)
    calc_inv = total_initial + cumulative_prod - cumulative_loads

    diff = end_inv - calc_inv

    print(f"{date.strftime('%Y-%m-%d'):<12} {production:>12,.0f} {truck_loads_today:>12,.0f} {end_inv:>12,.0f} {calc_inv:>12,.0f} {diff:>12,.0f}")

# Final summary
final_date = dates_list[-1]
final_inv = sum(
    value(pyomo_model.inventory_ambient['6122_Storage', p, final_date])
    for p in products_list
    if ('6122_Storage', p, final_date) in model.inventory_ambient_index_set
)

total_prod = sum(value(pyomo_model.production[d, p])
                 for d in dates_list for p in products_list)

total_loads = 0
for date in dates_list:
    for truck_idx in pyomo_model.trucks:
        for dest in pyomo_model.truck_destinations:
            transit_days = model._get_truck_transit_days(truck_idx, dest)

            for delivery_date in dates_list:
                departure_date = delivery_date - timedelta(days=transit_days)
                if departure_date == date:
                    total_loads += sum(
                        value(pyomo_model.truck_load[truck_idx, dest, p, delivery_date])
                        for p in products_list
                    )

print(f"\n{'=' * 90}")
print("FINAL SUMMARY")
print("=" * 90)
print(f"\nInitial inventory:  {total_initial:>12,.0f}")
print(f"Total production:   {total_prod:>12,.0f}")
print(f"Total truck loads:  {total_loads:>12,.0f}")
print(f"Final inventory:    {final_inv:>12,.0f}")
print(f"\nCalculated final:   {total_initial + total_prod - total_loads:>12,.0f}")
print(f"Model final:        {final_inv:>12,.0f}")
print(f"Difference:         {final_inv - (total_initial + total_prod - total_loads):>12,.0f}")

if abs(final_inv - (total_initial + total_prod - total_loads)) > 1.0:
    print(f"\n🚨 DISCREPANCY CONFIRMED!")
    print(f"   Model's inventory balance constraint is not working correctly")
    print(f"   The 'Diff' column shows cumulative error over time")
else:
    print(f"\n✅ Balance verified - discrepancy is elsewhere")

print(f"\n{'=' * 90}")
