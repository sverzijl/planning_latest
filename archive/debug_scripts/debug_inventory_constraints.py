"""
Debug script to write LP file and examine inventory constraints
"""
import sys
from pathlib import Path
from datetime import date, timedelta

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection

print("=" * 80)
print("DEBUG: Writing LP file to examine constraints")
print("=" * 80)

print("\nLoading data...")
network_parser = ExcelParser("data/examples/Network_Config.xlsx")
forecast_parser = ExcelParser("data/examples/Gfree Forecast_Converted.xlsx")

# Parse all data
locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = network_parser.parse_truck_schedules()
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.location_id == '6122'), None)
forecast = forecast_parser.parse_forecast()

# Filter to just 3 days for debugging
start_date = date(2025, 10, 13)  # Monday
end_date = date(2025, 10, 15)     # Wednesday (3 days)
filtered_entries = [e for e in forecast.entries
                   if start_date <= e.forecast_date <= end_date]
forecast.entries = filtered_entries

# Get unique products - just use 2 for simplicity
product_ids = sorted(set(e.product_id for e in forecast.entries))[:2]
forecast.entries = [e for e in forecast.entries if e.product_id in product_ids]

print(f"Filtered to {start_date} - {end_date}: {len(forecast.entries)} forecast entries")
print(f"Products: {product_ids}")

# Create initial inventory at manufacturing site
initial_inv = {}
for pid in product_ids:
    initial_inv[('6122', pid, 'ambient')] = 10000.0

print(f"\nInitial inventory at 6122: {sum(initial_inv.values()):,.0f} units")

print("\nBuilding optimization model...")
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

print(f"Model built successfully")
print(f"  Planning dates: {sorted(model_obj.production_dates)}")
print(f"  Products: {product_ids}")

# Build the Pyomo model but don't solve
print("\nBuilding Pyomo model...")
pyomo_model = model_obj.build_model()
print(f"Pyomo model created: {pyomo_model}")

# Write LP file
lp_file = "/home/sverzijl/planning_latest/debug_inventory_constraints.lp"
print(f"\nWriting LP file to: {lp_file}")
pyomo_model.write(lp_file, io_options={'symbolic_solver_labels': True})
print(f"✅ LP file written successfully")

# Now let's analyze the constraints programmatically
print("\n" + "=" * 80)
print("ANALYZING INVENTORY BALANCE CONSTRAINTS")
print("=" * 80)

# Check first day inventory balance for product 0
first_date = min(model_obj.production_dates)
loc = '6122'
prod = product_ids[0]

print(f"\nFirst date: {first_date}")
print(f"Location: {loc}")
print(f"Product: {prod}")
print(f"Initial inventory: {initial_inv.get((loc, prod, 'ambient'), 0):,.0f}")

# Find all trucks that depart on first day
print("\nTrucks on first day:")
for truck_idx, truck in model_obj.truck_by_index.items():
    # Check for each destination
    for dest in truck.get_destinations(first_date):
        transit_days = model_obj._get_truck_transit_days(truck_idx, dest)
        delivery_date = first_date + timedelta(days=transit_days)

        # Determine when this truck accesses inventory
        if truck.departure_type == 'morning':
            inventory_access_date = first_date - timedelta(days=1)
        else:
            inventory_access_date = first_date

        print(f"  Truck {truck_idx} ({truck.departure_type}): departs {first_date} → {dest} arrives {delivery_date}")
        print(f"    Accesses inventory on: {inventory_access_date}")
        print(f"    In planning horizon: {inventory_access_date in model_obj.production_dates}")

print("\n" + "=" * 80)
print(f"EXAMINE {lp_file} to see the actual constraint formulation")
print("=" * 80)
print("\nLook for constraints named:")
print(f"  - inventory_balance[{loc},{prod},{first_date}]")
print(f"  - truck_inventory_con[...]")
print("\nCheck if morning truck loads on Day 1 are being double-counted.")
