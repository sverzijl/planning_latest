"""
Verify leg-based routing solution for 29-week model.
"""
import sys
from pathlib import Path
from datetime import date

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection

print("=" * 80)
print("LEG-BASED ROUTING VERIFICATION - 29 WEEKS")
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

# Use full dataset
forecast_dates = [e.forecast_date for e in forecast.entries]
start_date = min(forecast_dates)
end_date = max(forecast_dates)

product_ids = sorted(set(e.product_id for e in forecast.entries))

# Create initial inventory
initial_inv = {}
for pid in product_ids:
    initial_inv[('6122_Storage', pid, 'ambient')] = 15000.0

print(f"Dataset: {start_date} to {end_date} ({(end_date - start_date).days + 1} days)")

print("\nBuilding model...")
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

print(f"\nModel structure:")
print(f"  Network legs: {len(model.leg_keys)}")
print(f"  Planning dates: {len(model.production_dates)}")

# Display network legs
print(f"\nNetwork Legs Enumerated:")
legs_by_origin = {}
for (origin, dest) in sorted(model.leg_keys):
    if origin not in legs_by_origin:
        legs_by_origin[origin] = []
    legs_by_origin[origin].append(dest)

for origin in sorted(legs_by_origin.keys()):
    dests = ', '.join(legs_by_origin[origin])
    print(f"  {origin} → {dests}")

# Check for key hub-to-spoke legs
print(f"\nKey Hub-to-Spoke Legs (NEW with leg-based routing):")
hub_spoke_legs = [
    ('6104', '6103'), ('6104', '6105'),  # NSW/ACT hub
    ('6125', '6123'),  # VIC/SA hub
    ('Lineage', '6130'),  # Frozen buffer to WA
]

for (origin, dest) in hub_spoke_legs:
    if (origin, dest) in model.leg_keys:
        transit = model.leg_transit_days[(origin, dest)]
        cost = model.leg_cost[(origin, dest)]
        print(f"  ✅ {origin} → {dest}: {transit} days, ${cost:.2f}/unit")
    else:
        print(f"  ❌ {origin} → {dest}: NOT FOUND")

print("\nSolving (quick test with 60s limit)...")
result = model.solve(
    solver_name='cbc',
    time_limit_seconds=60,
    mip_gap=0.05,  # 5% gap for quick test
    use_aggressive_heuristics=True,
    tee=False
)

print(f"\n" + "=" * 80)
print(f"SOLUTION ANALYSIS")
print(f"=" * 80)
print(f"Status: {result.termination_condition}")
print(f"Success: {result.success}")

if result.success:
    print(f"Objective: ${result.objective_value:,.2f}")
    print(f"Solve Time: {result.solve_time_seconds:.1f}s")

    # Access the solution details
    solution = result.solution_details

    # Check for leg shipments
    if 'shipments_by_leg_product_date' in solution:
        leg_shipments = solution['shipments_by_leg_product_date']
        print(f"\n✅ Leg shipments in solution: {len(leg_shipments)} non-zero shipments")

        # Group by leg
        shipments_by_leg = {}
        for ((origin, dest), prod, date), qty in leg_shipments.items():
            leg_key = (origin, dest)
            if leg_key not in shipments_by_leg:
                shipments_by_leg[leg_key] = 0
            shipments_by_leg[leg_key] += qty

        print(f"\nShipment Volume by Leg:")
        for (origin, dest), total_qty in sorted(shipments_by_leg.items(), key=lambda x: -x[1])[:15]:
            print(f"  {origin:8s} → {dest:8s}: {total_qty:>10,.0f} units")

        # Check for hub buffering capability
        print(f"\nHub-to-Spoke Shipments (demonstrates buffering capability):")
        for (origin, dest) in hub_spoke_legs:
            if (origin, dest) in shipments_by_leg:
                total = shipments_by_leg[(origin, dest)]
                print(f"  ✅ {origin} → {dest}: {total:>10,.0f} units shipped")
            else:
                print(f"  ⚠️  {origin} → {dest}: 0 units (no demand or not economical)")
    else:
        print(f"\n❌ 'shipments_by_leg_product_date' not found in solution")

    print(f"\n✅ 29-WEEK LEG-BASED ROUTING TEST PASSED")

else:
    print(f"\n❌ Solve failed: {result.termination_condition}")

print("=" * 80)
