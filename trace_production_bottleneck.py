"""
Diagnostic script to trace production bottleneck and identify why production
is limited to 1.70M units instead of meeting 2.41M demand.
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

print("=" * 80)
print("PRODUCTION BOTTLENECK DIAGNOSTIC")
print("=" * 80)

print("\n📊 Loading data and solving model...")
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

print(f"✅ Solved in {result.solve_time_seconds:.1f}s")
print(f"   Objective: ${result.objective_value:,.2f}")

pyomo_model = model.model

# ============================================================================
# 1. PRODUCTION ANALYSIS
# ============================================================================
print(f"\n{'=' * 80}")
print("1. PRODUCTION ANALYSIS")
print("=" * 80)

dates_list = sorted(list(pyomo_model.dates))
products_list = sorted(list(pyomo_model.products))

# Calculate daily production
daily_production = {}
for d in dates_list:
    daily_total = sum(value(pyomo_model.production[d, p]) for p in products_list)
    daily_production[d] = daily_total

total_production = sum(daily_production.values())
print(f"\nTotal Production: {total_production:,.0f} units")

# Show first 30 days
print(f"\nFirst 30 Days Production:")
for i, d in enumerate(dates_list[:30]):
    prod = daily_production[d]
    print(f"  {d.strftime('%Y-%m-%d')} ({d.strftime('%a')}): {prod:>10,.0f} units")

# Find when production drops significantly
print(f"\nProduction Pattern Analysis:")
high_days = [d for d, p in daily_production.items() if p > 10000]
low_days = [d for d, p in daily_production.items() if p < 5000]
zero_days = [d for d, p in daily_production.items() if p < 1.0]

print(f"  Days with production > 10K: {len(high_days)}")
print(f"  Days with production < 5K:  {len(low_days)}")
print(f"  Days with zero production:  {len(zero_days)}")

# ============================================================================
# 2. 6122_STORAGE INVENTORY FLOW
# ============================================================================
print(f"\n{'=' * 80}")
print("2. 6122_STORAGE INVENTORY FLOW")
print("=" * 80)

print(f"\nFirst 30 Days Inventory Balance:")
print(f"{'Date':<12} {'Day':>4} {'Prev Inv':>12} {'Production':>12} {'Truck Load':>12} {'End Inv':>12}")
print("-" * 68)

for i, d in enumerate(dates_list[:30]):
    # Get inventory at end of this date
    end_inv = sum(
        value(pyomo_model.inventory_ambient['6122_Storage', p, d])
        if ('6122_Storage', p, d) in model.inventory_ambient_index_set else 0
        for p in products_list
    )

    # Get production on this date
    production = daily_production[d]

    # Get previous inventory
    if i == 0:
        prev_inv = sum(initial_inv.values())
    else:
        prev_d = dates_list[i-1]
        prev_inv = sum(
            value(pyomo_model.inventory_ambient['6122_Storage', p, prev_d])
            if ('6122_Storage', p, prev_d) in model.inventory_ambient_index_set else 0
            for p in products_list
        )

    # Calculate truck load (should be prev_inv + production - end_inv)
    truck_load = prev_inv + production - end_inv

    print(f"{d.strftime('%Y-%m-%d'):<12} {d.strftime('%a'):>4} {prev_inv:>12,.0f} {production:>12,.0f} {truck_load:>12,.0f} {end_inv:>12,.0f}")

# Check final inventory
final_date = max(dates_list)
final_storage_inv = sum(
    value(pyomo_model.inventory_ambient['6122_Storage', p, final_date])
    if ('6122_Storage', p, final_date) in model.inventory_ambient_index_set else 0
    for p in products_list
)

print(f"\nFinal 6122_Storage Inventory: {final_storage_inv:,.0f} units")

# ============================================================================
# 3. TRUCK LOADING ANALYSIS
# ============================================================================
print(f"\n{'=' * 80}")
print("3. TRUCK LOADING ANALYSIS")
print("=" * 80)

# Calculate truck loads by departure date
from datetime import timedelta

truck_loads_by_departure = {}
for truck_idx in pyomo_model.trucks:
    for dest in pyomo_model.truck_destinations:
        # Get transit days
        transit_days = model._get_truck_transit_days(truck_idx, dest)

        for delivery_date in pyomo_model.dates:
            departure_date = delivery_date - timedelta(days=transit_days)
            if departure_date in pyomo_model.dates:
                load = sum(
                    value(pyomo_model.truck_load[truck_idx, dest, p, delivery_date])
                    for p in products_list
                )

                if departure_date not in truck_loads_by_departure:
                    truck_loads_by_departure[departure_date] = 0
                truck_loads_by_departure[departure_date] += load

print(f"\nFirst 30 Days Truck Loads (by departure date):")
for d in dates_list[:30]:
    load = truck_loads_by_departure.get(d, 0)
    print(f"  {d.strftime('%Y-%m-%d')} ({d.strftime('%a')}): {load:>10,.0f} units")

total_truck_loads = sum(truck_loads_by_departure.values())
print(f"\nTotal Truck Loads: {total_truck_loads:,.0f} units")

# ============================================================================
# 4. MASS BALANCE CHECK
# ============================================================================
print(f"\n{'=' * 80}")
print("4. MASS BALANCE CHECK")
print("=" * 80)

total_initial = sum(initial_inv.values())
total_demand = sum(qty for (dest, prod, d), qty in model.demand.items())

# Calculate total shortages
total_shortages = 0
if hasattr(pyomo_model, 'shortage'):
    for (loc, prod, d) in pyomo_model.shortage:
        total_shortages += value(pyomo_model.shortage[loc, prod, d])

# Calculate total final inventory (all locations)
total_final_inv = 0
for loc in model.inventory_locations:
    for p in products_list:
        if (loc, p, final_date) in model.inventory_ambient_index_set:
            total_final_inv += value(pyomo_model.inventory_ambient[loc, p, final_date])

print(f"\nInputs:")
print(f"  Initial Inventory:  {total_initial:>12,.0f} units")
print(f"  Production:         {total_production:>12,.0f} units")
print(f"  Total Supply:       {total_initial + total_production:>12,.0f} units")

print(f"\nOutputs:")
print(f"  Demand:             {total_demand:>12,.0f} units")
print(f"  Shortages:          {total_shortages:>12,.0f} units")
print(f"  Demand Satisfied:   {total_demand - total_shortages:>12,.0f} units")
print(f"  Final Inventory:    {total_final_inv:>12,.0f} units")
print(f"  Total Usage:        {(total_demand - total_shortages) + total_final_inv:>12,.0f} units")

balance_gap = (total_initial + total_production) - ((total_demand - total_shortages) + total_final_inv)
print(f"\nMass Balance Gap:     {balance_gap:>12,.0f} units")

if abs(balance_gap) < 1.0:
    print("✅ Mass balance verified!")
else:
    print(f"⚠️  Mass balance error!")

# ============================================================================
# 5. BOTTLENECK IDENTIFICATION
# ============================================================================
print(f"\n{'=' * 80}")
print("5. BOTTLENECK IDENTIFICATION")
print("=" * 80)

# Check labor capacity
weekdays = [d for d in dates_list if d.weekday() < 5]  # Mon-Fri
labor_capacity_regular = len(weekdays) * 12 * 1400  # 12 hours * 1400 UPH
labor_capacity_with_ot = len(weekdays) * 14 * 1400  # With 2h overtime

print(f"\nCapacity Analysis:")
print(f"  Weekdays in horizon:        {len(weekdays)}")
print(f"  Labor capacity (regular):   {labor_capacity_regular:,.0f} units (12h/day)")
print(f"  Labor capacity (with OT):   {labor_capacity_with_ot:,.0f} units (14h/day)")
print(f"  Actual production:          {total_production:,.0f} units")
print(f"  Utilization (regular):      {total_production/labor_capacity_regular*100:.1f}%")

# Check truck capacity
num_truck_departures = sum(1 for d in dates_list if d.weekday() < 5) * 11  # 11 trucks/week
truck_capacity = num_truck_departures * 14080  # 14,080 units/truck

print(f"\nTruck Capacity:")
print(f"  Truck departures (estimate): {num_truck_departures}")
print(f"  Truck capacity (total):      {truck_capacity:,.0f} units")
print(f"  Actual truck loads:          {total_truck_loads:,.0f} units")
print(f"  Utilization:                 {total_truck_loads/truck_capacity*100:.1f}%")

# Identify the binding constraint
print(f"\n{'=' * 80}")
print("DIAGNOSIS")
print("=" * 80)

production_deficit = total_demand - total_production
print(f"\nProduction Deficit: {production_deficit:,.0f} units ({production_deficit/total_demand*100:.1f}% of demand)")

if total_shortages > 0:
    print(f"Shortages: {total_shortages:,.0f} units (model reports unmet demand)")
else:
    print(f"Shortages: ZERO (despite {production_deficit:,.0f} unit deficit!)")
    print(f"⚠️  This suggests units are being produced but not reaching demand locations")

# Check if inventory is accumulating
if final_storage_inv > 50000:
    print(f"\n⚠️  BOTTLENECK: 6122_Storage inventory accumulating ({final_storage_inv:,.0f} units)")
    print(f"   Trucks are not loading enough inventory from storage")
    print(f"   Check truck loading constraints (lines 1595-1655 in integrated_model.py)")
elif total_final_inv > 200000:
    print(f"\n⚠️  BOTTLENECK: Excess inventory at network locations ({total_final_inv:,.0f} units)")
    print(f"   Units are reaching network but not being consumed")
else:
    print(f"\n⚠️  BOTTLENECK: Production artificially limited")
    print(f"   Production capacity available but not being utilized")
    print(f"   Check production or truck loading constraints")

print(f"\n{'=' * 80}")
