"""
Check why there's no production on the last 2 days of horizon.

From MIP theory: Model should produce on Day 27-28 to serve Day 28 demand.
If it doesn't, something is preventing it.
"""

from datetime import datetime, timedelta
from pyomo.core.base import value

from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType


# Load data
coordinator = DataCoordinator(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)
validated = coordinator.load_and_validate()

forecast_entries = [
    ForecastEntry(
        location_id=entry.node_id,
        product_id=entry.product_id,
        forecast_date=entry.demand_date,
        quantity=entry.quantity
    )
    for entry in validated.demand_entries
]
forecast = Forecast(name="Test Forecast", entries=forecast_entries)

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)
_, locations, routes_legacy, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manufacturing_site = manufacturing_locations[0]

converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes_legacy)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

products_dict = {p.id: p for p in validated.products}

# Build with EXTENDED horizon to test
horizon_days = 28
start = validated.planning_start_date
end = (datetime.combine(start, datetime.min.time()) + timedelta(days=horizon_days-1)).date()

print("="*100)
print(f"CHECKING PRODUCTION VARIABLES ON LAST DAYS")
print("="*100)

print(f"\nPlanning dates: {start} to {end}")
print(f"Horizon: {horizon_days} days\n")

# Check what the last few dates are
dates_list = []
current = start
for i in range(horizon_days):
    dates_list.append(current)
    current = (datetime.combine(current, datetime.min.time()) + timedelta(days=1)).date()

print(f"Last 5 days of horizon:")
for i, d in enumerate(dates_list[-5:], start=len(dates_list)-4):
    day_name = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][d.weekday()]
    print(f"  Day {i}: {d} ({day_name})")

# Check demand on last days
print(f"\nDemand on last 3 days:")
for d in dates_list[-3:]:
    demand_today = sum(
        qty for (node, prod, date), qty in model_builder.demand.items()
        if date == d
    )
    print(f"  {d}: {demand_today:,.0f} units")

# Check if production variables even EXIST for last days
model_builder_test = SlidingWindowModel(
    nodes=nodes,
    routes=unified_routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    products=products_dict,
    start_date=start,
    end_date=end,
    truck_schedules=unified_truck_schedules,
    initial_inventory=validated.get_inventory_dict(),
    inventory_snapshot_date=validated.inventory_snapshot_date,
    allow_shortages=True,
    use_pallet_tracking=True,
    use_truck_pallet_tracking=True
)

result = model_builder_test.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01)
model = model_builder_test.model

print(f"\n\nProduction variables on last 3 days:")
last_3_dates = dates_list[-3:]

for d in last_3_dates:
    prod_vars_exist = []
    if hasattr(model, 'production'):
        for (node_id, prod, date) in model.production:
            if date == d:
                prod_vars_exist.append(prod)

    print(f"\n{d}:")
    if len(prod_vars_exist) > 0:
        print(f"  Production variables exist: {len(prod_vars_exist)} products")

        # Check values
        for prod in prod_vars_exist[:3]:  # Show first 3
            key = ('6122', prod, d)  # Manufacturing node
            if key in model.production:
                try:
                    val = value(model.production[key])
                    print(f"    {prod[:35]}: {val:,.0f} units")
                except:
                    print(f"    {prod[:35]}: (uninitialized)")
    else:
        print(f"  ❌ NO PRODUCTION VARIABLES!")
        print(f"     Model can't produce on this day - variables don't exist!")

print(f"\n\n{'='*100}")
print(f"DIAGNOSIS:")
print(f"{'='*100}")

print(f"\nIf production variables don't exist for last days:")
print(f"  → Model CAN'T produce on those days")
print(f"  → Must produce earlier")
print(f"  → Early production sits as end inventory")
print(f"\nThis would explain the forced end inventory!")

print(f"\n{'='*100}")
