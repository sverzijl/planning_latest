"""
Check actual inventory values at hubs to see if any are negative or problematic.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from pyomo.environ import value

print("=" * 80)
print("HUB INVENTORY VALUE CHECK")
print("=" * 80)

print("\nLoading data and building model...")
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

pyomo_model = model.model

print(f"\n{'=' * 80}")
print("HUB 6104 INVENTORY VALUES")
print("=" * 80)

hub = '6104'
print(f"\nChecking inventory at {hub} (first 10 dates, first product):")

# Get first product
first_product = sorted(pyomo_model.products)[0]
dates = sorted([d for d in pyomo_model.dates])[:10]

for d in dates:
    if (hub, first_product, d) in pyomo_model.inventory_ambient:
        inv_val = value(pyomo_model.inventory_ambient[hub, first_product, d])
        print(f"  {d}: inventory = {inv_val:>10.2f}")
    else:
        print(f"  {d}: NO INVENTORY VARIABLE")

# Check for negative values across ALL products and dates
print(f"\n{hub} Inventory Statistics:")
negative_count = 0
zero_count = 0
positive_count = 0
min_val = float('inf')
max_val = float('-inf')

for (loc, p, d) in pyomo_model.inventory_ambient:
    if loc == hub:
        val = value(pyomo_model.inventory_ambient[loc, p, d])
        if val < -0.01:  # Allow small numerical errors
            negative_count += 1
        elif val < 0.01:
            zero_count += 1
        else:
            positive_count += 1
        min_val = min(min_val, val)
        max_val = max(max_val, val)

print(f"  Negative values: {negative_count}")
print(f"  Zero values: {zero_count}")
print(f"  Positive values: {positive_count}")
if min_val != float('inf'):
    print(f"  Min value: {min_val:.2f}")
    print(f"  Max value: {max_val:.2f}")

print(f"\n{'=' * 80}")
print("HUB 6125 INVENTORY VALUES")
print("=" * 80)

hub = '6125'
print(f"\nChecking inventory at {hub} (first 10 dates, first product):")

for d in dates:
    if (hub, first_product, d) in pyomo_model.inventory_ambient:
        inv_val = value(pyomo_model.inventory_ambient[hub, first_product, d])
        print(f"  {d}: inventory = {inv_val:>10.2f}")
    else:
        print(f"  {d}: NO INVENTORY VARIABLE")

# Check for negative values across ALL products and dates
print(f"\n{hub} Inventory Statistics:")
negative_count = 0
zero_count = 0
positive_count = 0
min_val = float('inf')
max_val = float('-inf')

for (loc, p, d) in pyomo_model.inventory_ambient:
    if loc == hub:
        val = value(pyomo_model.inventory_ambient[loc, p, d])
        if val < -0.01:
            negative_count += 1
        elif val < 0.01:
            zero_count += 1
        else:
            positive_count += 1
        min_val = min(min_val, val)
        max_val = max(max_val, val)

print(f"  Negative values: {negative_count}")
print(f"  Zero values: {zero_count}")
print(f"  Positive values: {positive_count}")
if min_val != float('inf'):
    print(f"  Min value: {min_val:.2f}")
    print(f"  Max value: {max_val:.2f}")

print(f"\n{'=' * 80}")
