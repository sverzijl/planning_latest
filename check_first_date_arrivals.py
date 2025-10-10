"""
Check what shipments are arriving on the first date.
These should be IMPOSSIBLE because they would require departures before the planning horizon.
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
print("FIRST DATE ARRIVAL DIAGNOSTIC")
print("=" * 80)

print("\nLoading data...")
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

# Create initial inventory
initial_inv = {}
for pid in product_ids:
    initial_inv[('6122_Storage', pid, 'ambient')] = 15000.0

print("\nBuilding model with allow_shortages=True...")
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

print("\nSolving...")
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

print(f"✅ Solved")

pyomo_model = model.model

# Get first date
first_date = min(pyomo_model.dates)
print(f"\nFirst date in planning horizon: {first_date}")

print(f"\n{'=' * 80}")
print("SHIPMENTS ARRIVING ON FIRST DATE")
print("=" * 80)

# Check all shipment_leg variables for arrivals on first date
arrivals_first_date = []

for idx in pyomo_model.shipment_leg:
    (origin, dest), prod, delivery_date = idx
    if delivery_date == first_date:
        qty = value(pyomo_model.shipment_leg[idx])
        if qty > 0.01:
            arrivals_first_date.append((origin, dest, prod, qty))

if not arrivals_first_date:
    print("\n✅ No shipments arriving on first date (expected)")
else:
    print(f"\n❌ Found {len(arrivals_first_date)} shipments arriving on first date:")
    print(f"\nThese are IMPOSSIBLE because they require departures before planning horizon!")

    for origin, dest, prod, qty in sorted(arrivals_first_date, key=lambda x: x[3], reverse=True)[:20]:
        # Calculate when this shipment would have departed
        transit_days = model.leg_transit_days.get((origin, dest), 0)
        departure_date = first_date - timedelta(days=transit_days)

        print(f"\n  Origin: {origin:15s} -> Dest: {dest:10s}")
        print(f"  Product: {prod:10s}")
        print(f"  Quantity: {qty:>10,.1f} units")
        print(f"  Transit days: {transit_days}")
        print(f"  Departure would be: {departure_date} (BEFORE planning horizon!)")

print(f"\n{'=' * 80}")
print("ANALYSIS")
print("=" * 80)

if arrivals_first_date:
    print(f"""
The model is allowing shipments to arrive on the first date of the planning horizon.
This is physically impossible because:

1. shipment_leg[(origin, dest), prod, delivery_date] represents a shipment
   that ARRIVES on delivery_date

2. For a shipment to arrive on delivery_date, it must have DEPARTED on:
   departure_date = delivery_date - transit_days

3. If delivery_date == first_date, then departure_date is BEFORE the planning horizon

4. There's no constraint preventing this!

THE BUG:
The model needs a constraint that prevents shipment_leg from being non-zero
if the departure date is outside the planning horizon.

Alternatively, shipment_leg should be indexed by DEPARTURE date, not delivery date.
But that would require refactoring the entire model.

IMMEDIATE FIX:
Add a constraint:
  shipment_leg[(o, d), p, delivery_date] == 0
  if (delivery_date - transit_days) < first_date

Or equivalently:
  shipment_leg[(o, d), p, delivery_date] == 0
  if delivery_date < (first_date + transit_days)
""")
else:
    print("\nNo arrivals on first date - checking if the bug exists elsewhere...")

print(f"\n{'=' * 80}")
print("CHECKING FIRST FEW DATES")
print("=" * 80)

dates_list = sorted(pyomo_model.dates)[:5]

for check_date in dates_list:
    arrivals = []
    for idx in pyomo_model.shipment_leg:
        (origin, dest), prod, delivery_date = idx
        if delivery_date == check_date:
            qty = value(pyomo_model.shipment_leg[idx])
            if qty > 0.01:
                transit_days = model.leg_transit_days.get((origin, dest), 0)
                departure_date = check_date - timedelta(days=transit_days)
                arrivals.append((origin, dest, prod, qty, transit_days, departure_date))

    if arrivals:
        print(f"\nDate {check_date}:")
        print(f"  {len(arrivals)} shipments arriving")

        # Check how many have departure before first_date
        invalid = [a for a in arrivals if a[5] < first_date]
        if invalid:
            total_invalid_qty = sum(a[3] for a in invalid)
            print(f"  ❌ {len(invalid)} shipments with departure before first_date!")
            print(f"     Total quantity: {total_invalid_qty:,.1f} units")
