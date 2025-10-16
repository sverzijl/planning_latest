"""Diagnose why model can't meet demand on weekdays."""

import sys
from pathlib import Path
from datetime import date

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
end_date = date(2025, 6, 8)
products_to_keep = ['168846']
locations_to_keep = ['6104']

test_entries = [
    entry for entry in full_forecast.entries
    if (entry.forecast_date >= start_date and
        entry.forecast_date <= end_date and
        entry.product_id in products_to_keep and
        entry.location_id in locations_to_keep)
]

# Scale down
total_demand = sum(e.quantity for e in test_entries)
scale_factor = 20000 / total_demand if total_demand > 0 else 1.0
for entry in test_entries:
    entry.quantity = entry.quantity * scale_factor

test_forecast = Forecast(name="Shortfall Diagnosis", entries=test_entries)

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

print("=" * 80)
print("SHORTFALL DIAGNOSIS")
print("=" * 80)

# Show demand by delivery date
print("\n📦 DEMAND BY DELIVERY DATE:")
demand_by_date = {}
for (dest, prod, deliv_date), qty in model_obj.demand.items():
    if deliv_date not in demand_by_date:
        demand_by_date[deliv_date] = 0
    demand_by_date[deliv_date] += qty

for d in sorted(demand_by_date.keys()):
    demand = demand_by_date[d]
    shortage = value(m.shortage[('6104', '168846', d)]) if ('6104', '168846', d) in m.shortage else 0
    delivered = demand - shortage
    print(f"  {d.strftime('%Y-%m-%d %a')}: Demand={demand:7.0f}, Delivered={delivered:7.0f}, Shortage={shortage:7.0f}")

# Show truck schedule
print("\n🚚 TRUCK SCHEDULE TO 6104:")
for truck in truck_schedules_list:
    if truck.destination_id == '6104':
        for day, runs in truck.schedule.items():
            if runs:
                departure_date = date(2025, 6, 1) + (day - 0) * (date(2025, 6, 2) - date(2025, 6, 1))
                # Find actual dates when this truck runs
                for prod_date in model_obj.production_dates:
                    if prod_date.weekday() == day:
                        # Calculate delivery date
                        route = next((r for r in model_obj.route_enumerator.routes
                                    if r.origin_id == '6122' and r.destination_id == '6104'), None)
                        if route:
                            transit_days = route.transit_days
                            delivery_date = prod_date + timedelta(days=transit_days)
                            if start_date <= delivery_date <= end_date:
                                print(f"  Truck {truck.truck_name}: Departure {prod_date.strftime('%a')}, "
                                      f"Delivery {delivery_date.strftime('%a %Y-%m-%d')}")
                                break

# Show production dates vs delivery dates
print("\n🏭 PRODUCTION TIMING:")
print("  (production_date + transit_days = delivery_date)")
from datetime import timedelta
route_transit = 1  # 6122→6104 is 1 day transit

for prod_date in sorted(model_obj.production_dates):
    total_prod = sum(value(m.production[prod_date, p]) for p in m.products)
    if total_prod < 0.01:
        continue

    delivery_date = prod_date + timedelta(days=route_transit)
    is_weekend = prod_date.weekday() >= 5
    marker = "🔴" if is_weekend else "✅"

    print(f"{marker} Produce {prod_date.strftime('%a %Y-%m-%d')}: {total_prod:7.0f} units → "
          f"Deliver {delivery_date.strftime('%a %Y-%m-%d')}")

    # Check if there's demand on delivery date
    demand = demand_by_date.get(delivery_date, 0)
    if demand > 0.01:
        print(f"     Demand on {delivery_date.strftime('%a')}: {demand:.0f} units")
    else:
        print(f"     ⚠️  NO DEMAND on {delivery_date.strftime('%a')}")

print("\n💡 HYPOTHESIS:")
print("If production on weekends is for dates with no trucks or outside demand period,")
print("that would explain why model accepts shortage + weekend instead of weekday production.")
