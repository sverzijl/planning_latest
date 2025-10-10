"""Analyze which routes the unassigned shipments are using.

The unassigned shipments might be from non-manufacturing origin routes
(e.g., hub-to-spoke routes).
"""

import sys
from pathlib import Path
from datetime import date

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast

# Parse data
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules_list = network_parser.parse_truck_schedules()
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)

forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')
full_forecast = forecast_parser.parse_forecast()

# Small test
start_date = date(2025, 6, 2)
end_date = date(2025, 6, 15)
products_to_keep = ['168846', '168847']
locations_to_keep = ['6104', '6110']

test_entries = [
    entry for entry in full_forecast.entries
    if (entry.forecast_date >= start_date and
        entry.forecast_date <= end_date and
        entry.product_id in products_to_keep and
        entry.location_id in locations_to_keep)
]

test_forecast = Forecast(name="Route Structure Analysis", entries=test_entries)

# Build and solve
model = IntegratedProductionDistributionModel(
    forecast=test_forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    max_routes_per_destination=1,
    allow_shortages=True,
    enforce_shelf_life=False,
)

result = model.solve(solver_name='cbc', time_limit_seconds=60, tee=False)

shipments = model.get_shipment_plan()
manufacturing_id = model.manufacturing_site.location_id

print("=" * 80)
print("ROUTE STRUCTURE ANALYSIS")
print("=" * 80)

# Separate shipments by origin
mfg_shipments = [s for s in shipments if s.origin_id == manufacturing_id]
hub_shipments = [s for s in shipments if s.origin_id != manufacturing_id]

print(f"\nTotal shipments: {len(shipments)}")
print(f"  From manufacturing ({manufacturing_id}): {len(mfg_shipments)}")
print(f"  From hubs (non-{manufacturing_id}): {len(hub_shipments)}")

print(f"\n{'=' * 80}")
print(f"MANUFACTURING SHIPMENTS ({len(mfg_shipments)} total)")
print(f"{'=' * 80}")

assigned_count = sum(1 for s in mfg_shipments if s.assigned_truck_id)
print(f"Assigned: {assigned_count}/{len(mfg_shipments)} ({100*assigned_count/len(mfg_shipments):.1f}%)")

print(f"\n{'=' * 80}")
print(f"HUB-TO-SPOKE SHIPMENTS ({len(hub_shipments)} total)")
print(f"{'=' * 80}")

if hub_shipments:
    print(f"\nThese shipments originate from hubs, not manufacturing:")
    for s in sorted(hub_shipments, key=lambda x: (x.origin_id, x.delivery_date))[:10]:
        assigned_status = f"✅ {s.assigned_truck_id}" if s.assigned_truck_id else "❌ NONE"
        print(f"  {s.id}: {s.origin_id}→{s.destination_id}, {s.product_id}, {s.quantity:.0f} units")
        print(f"    Delivery: {s.delivery_date}, Assigned: {assigned_status}")

    hub_assigned = sum(1 for s in hub_shipments if s.assigned_truck_id)
    print(f"\nHub shipments assigned: {hub_assigned}/{len(hub_shipments)} ({100*hub_assigned/len(hub_shipments) if hub_shipments else 0:.1f}%)")
else:
    print("No hub-to-spoke shipments found")

print(f"\n{'=' * 80}")
print("CONCLUSION")
print(f"{'=' * 80}")
print("If hub shipments exist, they don't get truck assignments")
print("because trucks only serve manufacturing-to-hub/spoke routes.")
print("Hub-to-spoke shipments use different trucks (not in truck schedule).")
