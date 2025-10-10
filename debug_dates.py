"""Check planning horizon and date coverage."""

from datetime import date, timedelta
from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection

# Parse data
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules_list = network_parser.parse_truck_schedules()
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
forecast = forecast_parser.parse_forecast()

# Get forecast date range
forecast_dates = [e.forecast_date for e in forecast.entries]
min_forecast = min(forecast_dates)
max_forecast = max(forecast_dates)

print(f"Forecast date range:")
print(f"  First: {min_forecast}")
print(f"  Last: {max_forecast}")
print(f"  Days: {(max_forecast - min_forecast).days + 1}")

# Build model
print(f"\nBuilding model...")
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    max_routes_per_destination=5,
    allow_shortages=True,
    enforce_shelf_life=True,
)

print(f"\nModel planning horizon:")
print(f"  Production dates: {len(model.production_dates)} days")
print(f"  First: {min(model.production_dates)}")
print(f"  Last: {max(model.production_dates)}")

# Build Pyomo model to get dates
pyomo_model = model.build_model()

print(f"\nModel dates (includes extension for transit):")
all_dates = list(pyomo_model.dates)
print(f"  All dates: {len(all_dates)} days")
print(f"  First: {min(all_dates)}")
print(f"  Last: {max(all_dates)}")

# Check if planning horizon extends beyond forecast
extension_days = (max(all_dates) - max_forecast).days
print(f"\nPlanning extension: {extension_days} days beyond last forecast date")

# Check max transit time
max_transit = max(model.route_transit_days.values())
print(f"Max route transit time: {max_transit:.1f} days")

if extension_days < max_transit:
    print(f"❌ PROBLEM: Extension ({extension_days}d) < max transit ({max_transit}d)")
    print(f"   Shipments for late forecast dates can't arrive!")

# Check if there are demands late in the horizon that can't be satisfied
late_demands = [e for e in forecast.entries if e.forecast_date > max_forecast - timedelta(days=int(max_transit))]
if late_demands:
    print(f"\n⚠️  {len(late_demands)} demand entries in last {int(max_transit)} days of forecast")
    print(f"   These require production {int(max_transit)}+ days before delivery")

    # Check if production dates cover this
    earliest_needed = min(e.forecast_date for e in late_demands) - timedelta(days=int(max_transit))
    if earliest_needed < min(model.production_dates):
        print(f"   ❌ Need production starting {earliest_needed}, but model starts {min(model.production_dates)}")
    else:
        print(f"   ✅ Production starts early enough ({min(model.production_dates)})")

# Check if all demand dates are in the shipment date range
demands_outside_horizon = []
for entry in forecast.entries:
    if entry.forecast_date not in all_dates:
        demands_outside_horizon.append(entry)

if demands_outside_horizon:
    print(f"\n❌ PROBLEM: {len(demands_outside_horizon)} demand dates outside planning horizon!")
    for e in demands_outside_horizon[:5]:
        print(f"   {e.location_id}, {e.product_id}, {e.forecast_date}: {e.quantity} units")
