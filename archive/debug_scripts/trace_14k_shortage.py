"""
Detailed trace of the 14,080 unit shortage.

Find exactly which locations and dates have unmet demand.
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
print("TRACE: FINDING THE 14,080 UNIT SHORTAGE")
print("=" * 80)

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

# ============================================================================
# 1. INVENTORY BALANCE BY LOCATION AND DATE
# ============================================================================
print("=" * 80)
print("1. FINAL DAYS INVENTORY BALANCE BY LOCATION")
print("=" * 80)

last_7_days = dates_list[-7:]
demand_locations = [loc for loc in locations if loc.location_type in ['breadroom', 'distribution_hub']]

print(f"\nLast 7 Days Balance (Demand - Satisfied):")
print(f"{'Location':<12} {'Type':<12} ", end='')
for d in last_7_days:
    print(f"{d.strftime('%m-%d'):>10}", end='')
print(f"{'Total':>12}")
print("-" * (24 + 10 * len(last_7_days) + 12))

total_by_date = {d: 0 for d in last_7_days}
total_by_location = {}

for loc in demand_locations:
    loc_id = loc.location_id
    row_data = []

    for d in last_7_days:
        # Demand at this location on this date
        demand_qty = sum(model.demand.get((loc_id, p, d), 0) for p in products_list)

        # Inventory at this location
        inv_qty = 0
        if (loc_id, products_list[0], d) in model.inventory_ambient_index_set:
            inv_qty = sum(
                value(pyomo_model.inventory_ambient[loc_id, p, d])
                for p in products_list
                if (loc_id, p, d) in model.inventory_ambient_index_set
            )

        # Net (negative means shortage)
        net = inv_qty - demand_qty
        row_data.append((demand_qty, inv_qty, net))

        if demand_qty > 0:
            if loc_id not in total_by_location:
                total_by_location[loc_id] = 0
            total_by_location[loc_id] += demand_qty
            total_by_date[d] += demand_qty

    # Only print if location has demand in these days
    if any(d > 0 for d, i, n in row_data):
        loc_total = sum(d for d, i, n in row_data)
        print(f"{loc_id:<12} {loc.location_type:<12} ", end='')
        for demand_qty, inv_qty, net in row_data:
            if demand_qty > 0:
                print(f"{demand_qty:>10,.0f}", end='')
            else:
                print(f"{'':>10}", end='')
        print(f"{loc_total:>12,.0f}")

print("-" * (24 + 10 * len(last_7_days) + 12))
print(f"{'TOTAL':<24} ", end='')
for d in last_7_days:
    if total_by_date[d] > 0:
        print(f"{total_by_date[d]:>10,.0f}", end='')
    else:
        print(f"{'':>10}", end='')
print(f"{sum(total_by_date.values()):>12,.0f}")

# ============================================================================
# 2. TRACK WHERE THE 14K SHORTAGE OCCURS
# ============================================================================
print(f"\n{'=' * 80}")
print("2. MASS BALANCE FOR ENTIRE HORIZON")
print("=" * 80)

# For each location, calculate: initial + arrivals - demand - outflows = final inventory
print(f"\n{'Location':<12} {'Initial':>12} {'Arrivals':>12} {'Demand':>12} {'Outflows':>12} {'Final':>12} {'Gap':>12}")
print("-" * 86)

total_gap = 0
location_gaps = []

for loc in locations:
    loc_id = loc.location_id

    # Initial inventory
    initial = sum(initial_inv.get((loc_id, p, 'ambient'), 0) for p in products_list)

    # Total arrivals
    arrivals = 0
    for leg in pyomo_model.legs:
        if leg[1] == loc_id:  # Destination is this location
            for p in products_list:
                for d in dates_list:
                    arrivals += value(pyomo_model.shipment_leg[leg, p, d])

    # Production (if manufacturing site)
    if loc_id == '6122':
        production = sum(value(pyomo_model.production[d, p])
                        for d in dates_list for p in products_list)
        arrivals += production

    # Total demand
    demand = sum(model.demand.get((loc_id, p, d), 0)
                 for p in products_list for d in dates_list)

    # Total outflows
    outflows = 0
    for leg in pyomo_model.legs:
        if leg[0] == loc_id:  # Origin is this location
            for p in products_list:
                for d in dates_list:
                    outflows += value(pyomo_model.shipment_leg[leg, p, d])

    # Final inventory
    final_date = dates_list[-1]
    final = 0
    if (loc_id, products_list[0], final_date) in model.inventory_ambient_index_set:
        final = sum(
            value(pyomo_model.inventory_ambient[loc_id, p, final_date])
            for p in products_list
            if (loc_id, p, final_date) in model.inventory_ambient_index_set
        )

    # Gap: (initial + arrivals) - (demand + outflows + final)
    gap = (initial + arrivals) - (demand + outflows + final)

    if abs(gap) > 1.0:
        total_gap += gap
        location_gaps.append((loc_id, gap, demand))

    if demand > 0 or abs(gap) > 1.0:
        print(f"{loc_id:<12} {initial:>12,.0f} {arrivals:>12,.0f} {demand:>12,.0f} {outflows:>12,.0f} {final:>12,.0f} {gap:>12,.0f}")

print(f"\nTotal mass balance gap across all locations: {total_gap:,.0f} units")

# ============================================================================
# 3. FIND EXACT SHORTAGE LOCATIONS
# ============================================================================
print(f"\n{'=' * 80}")
print("3. LOCATIONS WITH MASS BALANCE GAP")
print("=" * 80)

if location_gaps:
    print(f"\n{'Location':<12} {'Gap':>12} {'Total Demand':>15}")
    print("-" * 42)

    location_gaps_sorted = sorted(location_gaps, key=lambda x: x[1])
    for loc_id, gap, demand in location_gaps_sorted:
        if abs(gap) > 1.0:
            print(f"{loc_id:<12} {gap:>12,.0f} {demand:>15,.0f}")

    print(f"\nTotal gap: {sum(g for l, g, d in location_gaps):,.0f} units")

# ============================================================================
# 4. CHECK IF THIS IS DUE TO PLANNING HORIZON EXTENSION
# ============================================================================
print(f"\n{'=' * 80}")
print("4. PLANNING HORIZON ANALYSIS")
print("=" * 80)

# Check what dates the forecast ends vs what dates are in the model
forecast_end = max(e.date for e in forecast.entries)
model_end = dates_list[-1]

print(f"\nForecast end date:     {forecast_end.strftime('%Y-%m-%d')}")
print(f"Model horizon end:     {model_end.strftime('%Y-%m-%d')}")
print(f"Horizon extension:     {(model_end - forecast_end).days} days")

if model_end > forecast_end:
    print(f"\n⚠️  Model horizon is {(model_end - forecast_end).days} days beyond forecast")
    print(f"    This is expected due to transit time extension")

    # Check demand on extended days
    extended_days = [d for d in dates_list if d > forecast_end]
    extended_demand = sum(
        model.demand.get((loc, p, d), 0)
        for loc in [l.location_id for l in locations]
        for p in products_list
        for d in extended_days
    )

    print(f"    Demand on extended days: {extended_demand:,.0f} units")

    if extended_demand > 0:
        print(f"\n💡 EXPLANATION:")
        print(f"   The model extends the horizon by {(model_end - forecast_end).days} days to allow")
        print(f"   shipments in-transit to arrive. However, there may still be")
        print(f"   {extended_demand:,.0f} units of demand on these extended days")
        print(f"   that can't be fully satisfied due to the original horizon boundary.")

# ============================================================================
# 5. FINAL PRODUCTION DAYS
# ============================================================================
print(f"\n{'=' * 80}")
print("5. FINAL PRODUCTION DAYS")
print("=" * 80)

last_14_days = dates_list[-14:]

print(f"\nLast 14 Days Production:")
print(f"{'Date':<12} {'Weekday':<10} {'Production':>12}")
print("-" * 38)

total_last_14 = 0
for d in last_14_days:
    prod = sum(value(pyomo_model.production[d, p]) for p in products_list)
    total_last_14 += prod
    weekday = d.strftime('%A')
    print(f"{d.strftime('%Y-%m-%d'):<12} {weekday:<10} {prod:>12,.0f}")

print(f"\nTotal production in last 14 days: {total_last_14:,.0f} units")

# Check last production date
last_prod_date = None
for d in reversed(dates_list):
    prod = sum(value(pyomo_model.production[d, p]) for p in products_list)
    if prod > 100:
        last_prod_date = d
        break

if last_prod_date:
    print(f"\nLast significant production date: {last_prod_date.strftime('%Y-%m-%d')}")
    print(f"Days before horizon end: {(model_end - last_prod_date).days} days")

print(f"\n{'=' * 80}")
print("CONCLUSION")
print("=" * 80)

print(f"\nThe 14,080 unit gap (1 truck capacity) is likely due to:")
print(f"  1. End-of-horizon boundary effect")
print(f"  2. Demand in final days that can't be satisfied due to:")
print(f"     - Production timing constraints")
print(f"     - Transit time preventing delivery within horizon")
print(f"     - Optimal cost minimization leaving small shortage")

print(f"\nThis may be an acceptable tolerance in a finite-horizon model.")
print(f"In practice, this would be covered by:")
print(f"  - Rolling horizon planning (next period covers the gap)")
print(f"  - Safety stock at distribution locations")
print(f"  - Demand on extended days beyond original forecast")

print(f"\n{'=' * 80}")
