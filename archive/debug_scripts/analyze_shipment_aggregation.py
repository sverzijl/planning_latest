"""Analyze if multiple shipments are aggregated into single truck loads.

This explains why some shipments can't be assigned - they're sharing a truck load.
"""

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

test_forecast = Forecast(name="Aggregation Analysis", entries=test_entries)

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

# Get solution and shipments
solution = model.get_solution()
truck_loads = solution.get('truck_loads_by_truck_dest_product_date', {})
shipments = model.get_shipment_plan()

manufacturing_id = model.manufacturing_site.location_id
mfg_shipments = [s for s in shipments if s.origin_id == manufacturing_id]

print("=" * 80)
print("SHIPMENT AGGREGATION ANALYSIS")
print("=" * 80)

# Group shipments by (first_leg_dest, product, delivery_date)
shipments_by_key = defaultdict(list)
for s in mfg_shipments:
    key = (s.first_leg_destination, s.product_id, s.delivery_date)
    shipments_by_key[key].append(s)

# Group truck loads by (dest, product, date)
truck_loads_by_key = defaultdict(list)
for (truck_idx, dest, prod, date), qty in truck_loads.items():
    key = (dest, prod, date)
    truck_loads_by_key[key].append((truck_idx, qty))

print(f"\nTotal unique (dest, product, date) combinations:")
print(f"  Shipments: {len(shipments_by_key)}")
print(f"  Truck loads: {len(truck_loads_by_key)}")

print(f"\n{'=' * 80}")
print("CASES WHERE MULTIPLE SHIPMENTS SHARE ONE TRUCK LOAD")
print(f"{'=' * 80}")

multi_shipment_count = 0
for key, shipment_list in sorted(shipments_by_key.items()):
    if len(shipment_list) > 1:
        dest, prod, delivery_date = key
        multi_shipment_count += 1

        print(f"\n{dest}, {prod}, {delivery_date.strftime('%Y-%m-%d %a')}:")
        print(f"  {len(shipment_list)} shipments competing for same truck load:")

        total_shipment_qty = sum(s.quantity for s in shipment_list)
        print(f"  Total shipment quantity: {total_shipment_qty:.1f} units")

        for i, s in enumerate(shipment_list, 1):
            assigned_status = f"✅ {s.assigned_truck_id}" if s.assigned_truck_id else "❌ UNASSIGNED"
            print(f"    {i}. {s.id}: {s.quantity:.1f} units → {assigned_status}")

        # Show truck load for this key
        if key in truck_loads_by_key:
            for truck_idx, qty in truck_loads_by_key[key]:
                truck = model.truck_by_index[truck_idx]
                print(f"  Truck load: {truck.truck_name}: {qty:.1f} units")
        else:
            print(f"  ⚠️  No truck load found for this key!")

print(f"\n{'=' * 80}")
print(f"SUMMARY")
print(f"{'=' * 80}")
print(f"Cases with multiple shipments sharing one truck load: {multi_shipment_count}")
print(f"\nThis explains why only the first shipment in each group gets assigned!")
print(f"The current assignment logic assigns on first-come-first-serve basis.")
