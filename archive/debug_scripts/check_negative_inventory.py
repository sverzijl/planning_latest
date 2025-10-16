"""
Check for negative inventory values in the solved model.
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
print("NEGATIVE INVENTORY CHECK")
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

print(f"✅ Solved in {result.solve_time_seconds:.1f}s\n")

pyomo_model = model.model

# Check ALL inventory variables for negative values
negative_inventory = []

print("Checking ambient inventory variables...")
for (loc, prod, date) in model.inventory_ambient_index_set:
    inv_value = value(pyomo_model.inventory_ambient[loc, prod, date])
    if inv_value < -0.01:  # Allow tiny numerical errors
        negative_inventory.append((loc, prod, date, inv_value, 'ambient'))

# Check frozen inventory if it exists
if hasattr(pyomo_model, 'inventory_frozen'):
    print("Checking frozen inventory variables...")
    for (loc, prod, date) in pyomo_model.inventory_frozen:
        inv_value = value(pyomo_model.inventory_frozen[loc, prod, date])
        if inv_value < -0.01:
            negative_inventory.append((loc, prod, date, inv_value, 'frozen'))

print(f"\n{'=' * 80}")
print("RESULTS")
print("=" * 80)

if negative_inventory:
    print(f"\n🚨 FOUND {len(negative_inventory)} NEGATIVE INVENTORY VALUES!\n")

    # Group by location
    by_location = {}
    for (loc, prod, date, value, inv_type) in negative_inventory:
        if loc not in by_location:
            by_location[loc] = []
        by_location[loc].append((prod, date, value, inv_type))

    # Show summary by location
    print("Summary by Location:")
    print(f"{'Location':<20} {'Count':>8} {'Total Negative':>18}")
    print("-" * 50)
    for loc in sorted(by_location.keys()):
        entries = by_location[loc]
        total_neg = sum(v for (p, d, v, t) in entries)
        print(f"{loc:<20} {len(entries):>8} {total_neg:>18,.0f}")

    # Show worst offenders
    print(f"\nTop 20 Most Negative Inventory Values:")
    sorted_neg = sorted(negative_inventory, key=lambda x: x[3])
    print(f"{'Location':<20} {'Product':<10} {'Date':<12} {'Type':<8} {'Value':>15}")
    print("-" * 70)
    for (loc, prod, date, val, inv_type) in sorted_neg[:20]:
        print(f"{loc:<20} {prod:<10} {date.strftime('%Y-%m-%d'):<12} {inv_type:<8} {val:>15,.2f}")

    # Calculate total negative inventory
    total_negative = sum(v for (l, p, d, v, t) in negative_inventory)
    print(f"\n{'=' * 80}")
    print(f"TOTAL NEGATIVE INVENTORY: {total_negative:,.0f} units")
    print(f"Mass Balance Gap (from previous diagnostic): -630,807 units")
    print(f"Match: {abs(total_negative + 630807) < 1000}")
    print(f"={'=' * 80}")

    print(f"\n💡 ROOT CAUSE IDENTIFIED:")
    print(f"   Inventory variables are not properly constrained to be non-negative")
    print(f"   The model allows {total_negative:,.0f} units of negative inventory")
    print(f"   This creates phantom supply to meet demand")
    print(f"\n🔧 FIX REQUIRED:")
    print(f"   Add domain=NonNegativeReals to inventory variable definitions")
    print(f"   Check lines where inventory_ambient and inventory_frozen are defined")

else:
    print(f"\n✅ NO NEGATIVE INVENTORY FOUND")
    print(f"   All inventory values are non-negative")
    print(f"   The mass balance issue must be elsewhere")

print(f"\n{'=' * 80}")
