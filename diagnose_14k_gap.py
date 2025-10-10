"""
Diagnostic script to identify the exact cause of the 14,080 unit gap.

This is exactly 1 truck capacity (44 pallets × 320 units/pallet = 14,080).

Gap = Total Demand - (Total Production + Initial Inventory)
    = 2,407,299 - (2,318,219 + 75,000)
    = 2,407,299 - 2,393,219
    = 14,080 units

Hypotheses to test:
1. Last day boundary: Demand on final days that can't be fulfilled due to production timing
2. Phantom constraint impact: Specific shipment blocked by the new constraint
3. Shelf life constraint: One truck load prevented by shelf life expiration
4. Route constraint: Specific route/destination with capacity issue
5. First day boundary: Demand on early days that can't be met from initial inventory alone
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
print("DIAGNOSTIC: 14,080 UNIT GAP ANALYSIS")
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

pyomo_model = model.model
dates_list = sorted(list(pyomo_model.dates))
products_list = sorted(list(pyomo_model.products))

# ============================================================================
# 1. CALCULATE OVERALL GAP
# ============================================================================
print(f"\n{'=' * 80}")
print("1. OVERALL GAP CALCULATION")
print("=" * 80)

total_production = sum(value(pyomo_model.production[d, p])
                      for d in pyomo_model.dates
                      for p in pyomo_model.products)
total_initial = sum(initial_inv.values())
total_demand = sum(qty for (dest, prod, d), qty in model.demand.items())

total_shortages = 0
if hasattr(pyomo_model, 'shortage'):
    for (loc, prod, d) in pyomo_model.shortage:
        total_shortages += value(pyomo_model.shortage[loc, prod, d])

print(f"\nSupply Side:")
print(f"  Initial inventory:  {total_initial:>12,.0f} units")
print(f"  Production:         {total_production:>12,.0f} units")
print(f"  Total supply:       {total_initial + total_production:>12,.0f} units")

print(f"\nDemand Side:")
print(f"  Total demand:       {total_demand:>12,.0f} units")
print(f"  Shortages reported: {total_shortages:>12,.0f} units")
print(f"  Demand satisfied:   {total_demand - total_shortages:>12,.0f} units")

gap = total_demand - (total_initial + total_production)
print(f"\nGap: {gap:,.0f} units (exactly {gap / 14080:.2f} truck capacity)")

# ============================================================================
# 2. EXAMINE LAST DAYS OF PLANNING HORIZON
# ============================================================================
print(f"\n{'=' * 80}")
print("2. LAST DAYS ANALYSIS")
print("=" * 80)

last_10_days = dates_list[-10:]

print(f"\nLast 10 Days Demand vs. Arrivals:")
print(f"{'Date':<12} {'Demand':>12} {'Arrivals':>12} {'Shortage':>12} {'Production':>12}")
print("-" * 64)

for d in last_10_days:
    # Demand on this date
    demand_qty = sum(model.demand.get((dest, p, d), 0)
                     for dest in [loc.location_id for loc in locations]
                     for p in products_list)

    # Arrivals on this date (all inbound shipments)
    arrivals = 0
    for leg in pyomo_model.legs:
        for p in products_list:
            if (leg, p, d) in [(l, pr, dt) for l in pyomo_model.legs
                                for pr in pyomo_model.products
                                for dt in pyomo_model.dates]:
                arrivals += value(pyomo_model.shipment_leg[leg, p, d])

    # Shortages
    shortage_qty = sum(
        value(pyomo_model.shortage[dest, p, d])
        if (dest, p, d) in model.demand else 0
        for dest in [loc.location_id for loc in locations]
        for p in products_list
    )

    # Production
    production_qty = sum(value(pyomo_model.production[d, p]) for p in products_list)

    print(f"{d.strftime('%Y-%m-%d'):<12} {demand_qty:>12,.0f} {arrivals:>12,.0f} {shortage_qty:>12,.0f} {production_qty:>12,.0f}")

# ============================================================================
# 3. CHECK FOR CONSTRAINED SHIPMENTS NEAR HORIZON BOUNDARIES
# ============================================================================
print(f"\n{'=' * 80}")
print("3. PHANTOM SHIPMENT CONSTRAINT ANALYSIS")
print("=" * 80)

# Check which shipments are being blocked by the phantom constraint
first_date = dates_list[0]
blocked_shipments = []

print(f"\nChecking for shipments blocked by phantom constraint...")
print(f"Planning horizon starts: {first_date.strftime('%Y-%m-%d')}")

for leg in pyomo_model.legs:
    transit_days = model.leg_transit_days.get(leg, 0)

    # Check first few dates for blocked shipments
    for d in dates_list[:transit_days + 3]:  # Check a few extra days
        departure_date = d - timedelta(days=transit_days)

        if departure_date < first_date:
            # This shipment would be blocked
            demand_on_this_date = sum(
                model.demand.get((leg[1], p, d), 0)  # leg[1] is destination
                for p in products_list
            )

            if demand_on_this_date > 0:
                blocked_shipments.append({
                    'leg': leg,
                    'delivery_date': d,
                    'departure_date': departure_date,
                    'transit_days': transit_days,
                    'demand': demand_on_this_date,
                    'days_before_horizon': (first_date - departure_date).days
                })

if blocked_shipments:
    print(f"\n🔍 Found {len(blocked_shipments)} blocked shipment opportunities:")

    # Group by delivery date
    by_date = {}
    for b in blocked_shipments:
        d = b['delivery_date']
        if d not in by_date:
            by_date[d] = []
        by_date[d].append(b)

    print(f"\n{'Delivery Date':<15} {'Route':<25} {'Transit':>8} {'Demand':>12} {'Days Before':>12}")
    print("-" * 85)

    total_blocked_demand = 0
    for d in sorted(by_date.keys()):
        for b in by_date[d]:
            print(f"{d.strftime('%Y-%m-%d'):<15} {str(b['leg']):<25} {b['transit_days']:>8} {b['demand']:>12,.0f} {b['days_before_horizon']:>12}")
            total_blocked_demand += b['demand']

    print(f"\nTotal demand on dates with blocked shipments: {total_blocked_demand:,.0f} units")
    print(f"(Note: This demand may be satisfied by alternative routes)")

else:
    print("\n✅ No blocked shipments found")

# ============================================================================
# 4. CHECK LAST PRODUCTION CAPACITY
# ============================================================================
print(f"\n{'=' * 80}")
print("4. PRODUCTION CAPACITY UTILIZATION")
print("=" * 80)

# Check if production is maxed out (suggesting capacity constraint)
weekdays = [d for d in dates_list if d.weekday() < 5]
total_weekday_capacity = len(weekdays) * 12 * 1400  # 12 hours * 1400 UPH
total_weekday_production = sum(
    value(pyomo_model.production[d, p])
    for d in weekdays
    for p in products_list
)

print(f"\nWeekday Production Analysis:")
print(f"  Weekdays in horizon:     {len(weekdays)}")
print(f"  Total capacity (12h):    {total_weekday_capacity:,.0f} units")
print(f"  Actual production:       {total_weekday_production:,.0f} units")
print(f"  Utilization:             {total_weekday_production/total_weekday_capacity*100:.1f}%")
print(f"  Unused capacity:         {total_weekday_capacity - total_weekday_production:,.0f} units")

if total_weekday_production >= total_weekday_capacity * 0.99:
    print("\n⚠️  Production is at 99%+ capacity - this may be limiting output")
else:
    print("\n✅ Production has spare capacity available")

# ============================================================================
# 5. EXAMINE SPECIFIC ROUTES WITH LONGEST TRANSIT TIMES
# ============================================================================
print(f"\n{'=' * 80}")
print("5. LONG TRANSIT ROUTE ANALYSIS")
print("=" * 80)

# Find routes with longest transit times
leg_transit_sorted = sorted(model.leg_transit_days.items(), key=lambda x: x[1], reverse=True)

print(f"\nRoutes with longest transit times:")
print(f"{'Route':<30} {'Transit Days':>12} {'Total Shipments':>16}")
print("-" * 60)

for leg, transit_days in leg_transit_sorted[:10]:
    total_shipments = sum(
        value(pyomo_model.shipment_leg[leg, p, d])
        for p in products_list
        for d in dates_list
    )
    print(f"{str(leg):<30} {transit_days:>12} {total_shipments:>16,.0f}")

# ============================================================================
# 6. CHECK FOR SHELF LIFE CONSTRAINTS
# ============================================================================
print(f"\n{'=' * 80}")
print("6. SHELF LIFE CONSTRAINT ANALYSIS")
print("=" * 80)

# Check if any routes are filtered out by shelf life
max_transit_in_use = max(model.leg_transit_days.values())
print(f"\nMaximum transit days in network: {max_transit_in_use} days")
print(f"Shelf life limit (if enforced): 10 days")

if max_transit_in_use > 10:
    print(f"\n⚠️  Some routes have transit > 10 days and may be filtered out")
else:
    print(f"\n✅ All routes within shelf life limit")

# ============================================================================
# 7. DIAGNOSIS SUMMARY
# ============================================================================
print(f"\n{'=' * 80}")
print("DIAGNOSIS SUMMARY")
print("=" * 80)

print(f"\nGap: {gap:,.0f} units = {gap / 14080:.3f} truck capacity")

if abs(gap - 14080) < 1.0:
    print(f"\n🎯 Gap is EXACTLY 1 truck capacity!")
    print(f"\nMost likely causes:")
    print(f"  1. Final day boundary: Last day demand can't be fully satisfied")
    print(f"  2. Transit constraint: Long transit route preventing final delivery")
    print(f"  3. Production timing: Last production batch can't be loaded in time")
    print(f"  4. Phantom constraint: First days blocking one truck load")

    # Check if we have production on last days
    last_5_days_prod = sum(
        value(pyomo_model.production[d, p])
        for d in dates_list[-5:]
        for p in products_list
    )

    if last_5_days_prod < 1000:
        print(f"\n  ⚠️  Very low production in last 5 days ({last_5_days_prod:,.0f} units)")
        print(f"      This suggests end-of-horizon constraint")

print(f"\n{'=' * 80}")
