"""Check if in-transit inventory is the missing 50,000 units.

The cohort inventory format (loc, prod, prod_date, curr_date, state) only captures
inventory AT locations, not inventory IN-TRANSIT on trucks.

If shipments departed on day 1 but deliver on day 3, that inventory is
"in transit" on day 2 and won't show up in location inventory.

This could be the source of the 50,000-unit deficit.
"""

from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from src.models.truck_schedule import TruckScheduleCollection

# Parse and create model
parser = MultiFileParser(
    forecast_file='data/examples/Gfree Forecast.xlsm',
    network_file='data/examples/Network_Config.xlsx',
)
forecast, locations, routes, labor, trucks_list, costs = parser.parse_all()
trucks = TruckScheduleCollection(schedules=trucks_list)
manuf = [l for l in locations if l.type == LocationType.MANUFACTURING][0]
msite = ManufacturingSite(
    id=manuf.id, name=manuf.name, storage_mode=manuf.storage_mode,
    production_rate=1400, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
    default_changeover_hours=0.5, production_cost_per_unit=costs.production_cost_per_unit
)

start = min(e.forecast_date for e in forecast.entries)
end = start + timedelta(weeks=4)

print(f"Creating model: {start} to {end}")
model = IntegratedProductionDistributionModel(
    forecast=forecast, labor_calendar=labor, manufacturing_site=msite,
    cost_structure=costs, locations=locations, routes=routes,
    truck_schedules=trucks, start_date=start, end_date=end,
    allow_shortages=True, enforce_shelf_life=True, use_batch_tracking=True,
)

print(f"Solving...")
result = model.solve(solver_name='cbc', time_limit_seconds=90, mip_gap=0.01, tee=False)

if not (result.is_optimal() or result.is_feasible()):
    print(f"❌ Not solved")
    exit(1)

solution = model.get_solution()
cohort_inv = solution.get('cohort_inventory', {})
shipments = model.get_shipment_plan() or []

print(f"\n{'='*80}")
print("IN-TRANSIT INVENTORY ANALYSIS")
print("="*80)

# Calculate in-transit inventory on each day
# A shipment is in-transit if: departure_date < current_date < delivery_date

in_transit_by_date = defaultdict(float)

for shipment in shipments:
    departure_date = shipment.delivery_date - timedelta(days=shipment.total_transit_days)

    # For each day in transit
    current = departure_date + timedelta(days=1)  # Day after departure
    while current < shipment.delivery_date:  # Before delivery
        if model.start_date <= current <= model.end_date:
            in_transit_by_date[current] += shipment.quantity
        current += timedelta(days=1)

print(f"In-transit inventory by date (first 5 days):")
for i, curr_date in enumerate(sorted(in_transit_by_date.keys())[:5]):
    print(f"  {curr_date}: {in_transit_by_date[curr_date]:,.0f} units")

# Check first and last day
first_day_in_transit = in_transit_by_date.get(model.start_date, 0.0)
last_day_in_transit = in_transit_by_date.get(model.end_date, 0.0)

print(f"\nFirst day ({model.start_date}) in-transit: {first_day_in_transit:,.0f} units")
print(f"Last day ({model.end_date}) in-transit: {last_day_in_transit:,.0f} units")

# Now recalculate material balance INCLUDING in-transit
production = sum(solution.get('production_by_date_product', {}).values())

# First day total inventory = at locations + in-transit
first_day_at_locations = sum(
    qty for (loc, prod, pd, cd, state), qty in cohort_inv.items()
    if cd == model.start_date
)
first_day_total = first_day_at_locations + first_day_in_transit

# Last day total inventory  = at locations + in-transit
last_day_at_locations = sum(
    qty for (loc, prod, pd, cd, state), qty in cohort_inv.items()
    if cd == model.end_date
)
last_day_total = last_day_at_locations + last_day_in_transit

print(f"\n{'='*80}")
print("CORRECTED MATERIAL BALANCE")
print("="*80)

print(f"FIRST DAY ({model.start_date}):")
print(f"  At locations: {first_day_at_locations:,.0f}")
print(f"  In-transit: {first_day_in_transit:,.0f}")
print(f"  TOTAL: {first_day_total:,.0f} units")

print(f"\nLAST DAY ({model.end_date}):")
print(f"  At locations: {last_day_at_locations:,.0f}")
print(f"  In-transit: {last_day_in_transit:,.0f}")
print(f"  TOTAL: {last_day_total:,.0f} units")

# Material balance: Initial + Production = Consumption + Final
demand_in_horizon = sum(e.quantity for e in forecast.entries if model.start_date <= e.forecast_date <= model.end_date)
shortage = sum(solution.get('shortages_by_dest_product_date', {}).values())
consumption = demand_in_horizon - shortage

print(f"\nMATERIAL BALANCE EQUATION:")
print(f"  Initial inventory: {first_day_total:,.0f}")
print(f"  + Production: {production:,.0f}")
print(f"  = TOTAL SUPPLY: {first_day_total + production:,.0f} units")
print()
print(f"  Demand satisfied: {consumption:,.0f}")
print(f"  + Final inventory: {last_day_total:,.0f}")
print(f"  = TOTAL USAGE: {consumption + last_day_total:,.0f} units")
print()

balance = (first_day_total + production) - (consumption + last_day_total)
print(f"  BALANCE: {balance:+,.0f} units")

if abs(balance) < 100:
    print(f"\n✓ MATERIAL BALANCE IS CORRECT!")
    print(f"  The 'deficit' was from not accounting for in-transit inventory")
    print(f"  Initial in-transit inventory: {first_day_in_transit:,.0f} units")
else:
    print(f"\n❌ Still have material balance issue: {balance:,.0f} units")
