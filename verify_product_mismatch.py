"""Verify the product mismatch hypothesis.

Check if shipments and truck loads match by (dest, date) in total,
but NOT by (dest, product, date) individually.
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
from pyomo.environ import value

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

test_forecast = Forecast(name="Product Mismatch Test", entries=test_entries)

# Build and solve
model_obj = IntegratedProductionDistributionModel(
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

result = model_obj.solve(solver_name='cbc', time_limit_seconds=60, tee=False)

m = model_obj.model
mfg_id = model_obj.manufacturing_site.location_id

print("=" * 80)
print("PRODUCT-LEVEL MISMATCH ANALYSIS")
print("=" * 80)

for dest in ['6104', '6110']:
    print(f"\n{'=' * 80}")
    print(f"Destination: {dest}")
    print(f"{'=' * 80}")

    for date in sorted(model_obj.production_dates):
        # Get shipments by product
        shipments_by_product = {}
        direct_routes = []
        for route_idx in model_obj.route_indices:
            route = model_obj.route_enumerator.get_route(route_idx)
            if route and route.origin_id == mfg_id:
                first_leg_dest = route.path[1] if len(route.path) >= 2 else route.destination_id
                if first_leg_dest == dest:
                    direct_routes.append(route_idx)

        for p in m.products:
            total = sum(value(m.shipment[r, p, date]) for r in direct_routes)
            shipments_by_product[p] = total

        # Get truck loads by product
        trucks_by_product = {}
        trucks_to_dest = model_obj.trucks_to_destination.get(dest, [])
        for p in m.products:
            total = sum(value(m.truck_load[t, dest, p, date]) for t in trucks_to_dest)
            trucks_by_product[p] = total

        # Compare
        shipment_total = sum(shipments_by_product.values())
        truck_total = sum(trucks_by_product.values())

        if shipment_total > 0.01 or truck_total > 0.01:
            print(f"\n{date.strftime('%Y-%m-%d %a')}:")
            print(f"  Total: Shipments={shipment_total:.1f}, Trucks={truck_total:.1f}, Diff={abs(shipment_total-truck_total):.1f}")

            # Check each product
            for p in m.products:
                ship_qty = shipments_by_product[p]
                truck_qty = trucks_by_product[p]
                if ship_qty > 0.01 or truck_qty > 0.01:
                    diff = abs(ship_qty - truck_qty)
                    status = "✅" if diff < 0.1 else "❌ MISMATCH"
                    print(f"    {p}: Ship={ship_qty:7.1f}, Truck={truck_qty:7.1f} {status}")

print(f"\n{'=' * 80}")
print("CONCLUSION")
print(f"{'=' * 80}")
print("If you see MISMATCH above, the constraint needs to be per-product!")
print("The constraint should be indexed by (dest, PRODUCT, date), not just (dest, date)")
