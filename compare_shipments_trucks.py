"""Compare all shipments vs all truck loads to find the mismatch."""

import sys
from pathlib import Path
from datetime import date
from collections import defaultdict

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast

# Parse and build model (same as before)
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

test_forecast = Forecast(name="Compare Test", entries=test_entries)

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

solution = model.get_solution()
truck_loads = solution.get('truck_loads_by_truck_dest_product_date', {})
shipments_by_route = solution.get('shipments_by_route_product_date', {})

print("="*80)
print("TRUCK LOADS (from optimization variables)")
print("="*80)
truck_totals = defaultdict(float)
for (truck_idx, dest, prod, date), qty in sorted(truck_loads.items()):
    truck = model.truck_by_index[truck_idx]
    print(f"  {date.strftime('%Y-%m-%d %a')}: Truck {truck.truck_name} → {dest}, {prod}: {qty:.0f} units")
    truck_totals[(dest, prod, date)] += qty

print(f"\n{'='*80}")
print("SHIPMENTS (from optimization variables)")
print("="*80)
shipment_totals = defaultdict(float)
for (route_idx, prod, date), qty in sorted(shipments_by_route.items()):
    route = model.route_enumerator.get_route(route_idx)
    origin = route.origin_id
    dest = route.destination_id
    first_leg = route.path[1] if len(route.path) >= 2 else dest
    print(f"  {date.strftime('%Y-%m-%d %a')}: Route {origin}→{dest} (via {first_leg}), {prod}: {qty:.0f} units")
    shipment_totals[(first_leg, prod, date)] += qty

print(f"\n{'='*80}")
print("COMPARISON: Truck loads vs Shipments (by first-leg dest)")
print("="*80)

all_keys = set(truck_totals.keys()) | set(shipment_totals.keys())
for (dest, prod, date) in sorted(all_keys):
    truck_qty = truck_totals.get((dest, prod, date), 0)
    ship_qty = shipment_totals.get((dest, prod, date), 0)
    match = "✅" if abs(truck_qty - ship_qty) < 0.1 else "❌"
    print(f"{match} {date.strftime('%Y-%m-%d %a')}, {dest}, {prod}:")
    print(f"     Truck: {truck_qty:7.0f} units")
    print(f"     Ship:  {ship_qty:7.0f} units")
    if abs(truck_qty - ship_qty) > 0.1:
        print(f"     MISMATCH: {abs(truck_qty - ship_qty):.0f} units difference")
