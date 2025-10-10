"""
Check if outflows near the end of planning horizon are being counted correctly.

The bug hypothesis:
- shipment_leg is indexed by DELIVERY date
- Outflows departing near end of horizon might deliver AFTER horizon ends
- These outflows are NOT counted (if delivery_date not in model.dates)
- This allows inventory to "leak" from the system
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from datetime import timedelta

print("=" * 80)
print("HORIZON LEAK DIAGNOSTIC")
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
    allow_shortages=False,
    enforce_shelf_life=True,
    initial_inventory=initial_inv
)

# Check planning horizon
print(f"\n{'=' * 80}")
print("PLANNING HORIZON")
print("=" * 80)
print(f"\nStart date: {model.start_date}")
print(f"End date: {model.end_date}")
print(f"Days: {len(model.production_dates)}")

# Check hub outbound legs and transit times
print(f"\n{'=' * 80}")
print("HUB OUTBOUND LEGS")
print("=" * 80)

for hub in ['6104', '6125']:
    print(f"\n{hub}:")
    legs = model.legs_from_location.get(hub, [])
    for (origin, dest) in legs:
        transit_days = model.leg_transit_days.get((origin, dest), 0)
        arrival_state = model.leg_arrival_state.get((origin, dest), '')
        print(f"  → {dest}: {transit_days} days transit ({arrival_state})")

# Analyze last N days for potential leaks
N = 5
last_dates = sorted(model.production_dates)[-N:]

print(f"\n{'=' * 80}")
print(f"OUTFLOW ACCOUNTING - LAST {N} DAYS")
print("=" * 80)

for date in last_dates:
    print(f"\n--- Date {date} ({date.strftime('%Y-%m-%d')}) ---")

    for hub in ['6104', '6125']:
        legs = model.legs_from_location.get(hub, [])
        print(f"\n{hub} outflows departing on {date}:")

        for (origin, dest) in legs:
            if model.leg_arrival_state.get((origin, dest)) == 'ambient':
                transit_days = model.leg_transit_days[(origin, dest)]
                delivery_date = date + timedelta(days=transit_days)

                in_horizon = delivery_date in model.production_dates
                status = "✅ IN HORIZON" if in_horizon else "❌ OUTSIDE HORIZON"

                print(f"  → {dest}: delivers {delivery_date} ({status})")

                if not in_horizon:
                    print(f"      ⚠️  This outflow will NOT be counted in inventory balance!")

print(f"\n{'=' * 80}")
print("ANALYSIS")
print("=" * 80)

# Count how many outbound legs would miss horizon
total_potential_leaks = 0
for date in model.production_dates:
    for hub in ['6104', '6125']:
        legs = model.legs_from_location.get(hub, [])
        for (origin, dest) in legs:
            if model.leg_arrival_state.get((origin, dest)) == 'ambient':
                transit_days = model.leg_transit_days[(origin, dest)]
                delivery_date = date + timedelta(days=transit_days)
                if delivery_date not in model.production_dates:
                    total_potential_leaks += 1

print(f"\nTotal (hub, date, dest) combinations where delivery is outside horizon: {total_potential_leaks}")

if total_potential_leaks > 0:
    print(f"\n⚠️  POTENTIAL LEAK DETECTED!")
    print(f"   Shipments departing near end of horizon may not be counted as outflows")
    print(f"   This allows inventory to 'leak' from the system")
else:
    print(f"\n✅ No horizon leak potential detected")
    print(f"   All outflows deliver within planning horizon")

print(f"\n{'=' * 80}")
