"""
Simple check of shipment_leg index structure after solving.
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

print("Loading and solving...")
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

model_obj = IntegratedProductionDistributionModel(
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

result = model_obj.solve(
    solver_name='cbc',
    time_limit_seconds=600,
    mip_gap=0.01,
    use_aggressive_heuristics=True,
    tee=False
)

if not result.success:
    print("Solve failed")
    sys.exit(1)

print("Solved")

pyomo_model = model_obj.model
first_date = min(pyomo_model.dates)

print(f"\nFirst date: {first_date}")
print("\nChecking shipment_leg index structure:")

# Get first index
first_idx = next(iter(pyomo_model.shipment_leg))
print(f"First index: {first_idx}")
print(f"Type: {type(first_idx)}")

# Unpack it
if isinstance(first_idx, tuple):
    print(f"Length: {len(first_idx)}")
    for i, elem in enumerate(first_idx):
        print(f"  Element {i}: {elem} (type: {type(elem)})")

print("\n" + "=" * 80)
print("CHECKING FOR ARRIVALS BEFORE FIRST DATE")
print("=" * 80)

# Now iterate correctly
arrivals_first_date = []
all_early_arrivals = []

for idx in pyomo_model.shipment_leg:
    qty = value(pyomo_model.shipment_leg[idx])
    if qty > 0.01:
        # Unpack based on actual structure
        if len(idx) == 4:
            # Assume: (origin, dest, prod, delivery_date)
            origin, dest, prod, delivery_date = idx
        elif len(idx) == 3:
            # Assume: ((origin, dest), prod, delivery_date)
            # This is tricky - need to check what's actually a tuple
            if isinstance(idx[0], tuple):
                (origin, dest), prod, delivery_date = idx
            else:
                # Don't know the structure
                print(f"Unknown structure: {idx}")
                continue
        else:
            print(f"Unexpected index length: {len(idx)}")
            continue

        transit_days = model_obj.leg_transit_days.get((origin, dest), 0)
        departure_date = delivery_date - timedelta(days=transit_days)

        if departure_date < first_date:
            all_early_arrivals.append((origin, dest, prod, qty, transit_days, delivery_date, departure_date))
            if delivery_date == first_date:
                arrivals_first_date.append((origin, dest, prod, qty))

print(f"\nTotal shipments with departure before first_date: {len(all_early_arrivals)}")
if all_early_arrivals:
    total_qty = sum(x[3] for x in all_early_arrivals)
    print(f"Total quantity: {total_qty:,.1f} units")

    print(f"\nFirst 20 examples:")
    for origin, dest, prod, qty, transit, deliv_date, dept_date in sorted(all_early_arrivals, key=lambda x: x[3], reverse=True)[:20]:
        print(f"  {origin:15s} -> {dest:10s}  {prod:10s}  {qty:>10,.1f} units")
        print(f"    Delivers: {deliv_date}  Departs: {dept_date} (transit: {transit}d)")

print(f"\nShipments arriving on first date: {len(arrivals_first_date)}")
if arrivals_first_date:
    total_first = sum(x[3] for x in arrivals_first_date)
    print(f"Total quantity on first date: {total_first:,.1f} units")
