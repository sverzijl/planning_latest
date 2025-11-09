"""
Trace manufacturing inventory day-by-day to see cumulative balance.

This will show WHEN the phantom supply appears.
"""

from datetime import datetime, timedelta
from pyomo.core.base import value

from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType


# Load and solve model
print("Building and solving model...")
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

horizon_days = 28
start = validated.planning_start_date
end = (datetime.combine(start, datetime.min.time()) + timedelta(days=horizon_days-1)).date()

model_builder = SlidingWindowModel(
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

result = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01)

if not result.success:
    print(f"Solve failed: {result.termination_condition}")
    exit(1)

print(f"Solved!\n")
model = model_builder.model

# Trace manufacturing day-by-day
print("="*100)
print("MANUFACTURING (6122) DAILY INVENTORY TRACE - ALL PRODUCTS AGGREGATED")
print("="*100)

mfg_node = '6122'

# Get initial inventory
init_inv_total = sum(model_builder.initial_inventory.get((mfg_node, prod, state), 0)
                     for prod in model.products
                     for state in ['ambient', 'frozen'])

print(f"\nInitial inventory: {init_inv_total:,.0f} units\n")

print(f"{'Date':<12} {'Prod':>8} {'Depart':>8} {'EndInv':>8} {'CumProd':>10} {'CumDepart':>10} {'Balance':>10}")
print("-"*100)

cum_production = 0
cum_departures = 0

dates = sorted(list(model.dates))

for t in dates:
    # Production on this date
    prod_today = 0
    if hasattr(model, 'production'):
        for prod in model.products:
            if (mfg_node, prod, t) in model.production:
                try:
                    prod_today += value(model.production[mfg_node, prod, t])
                except:
                    pass

    # Departures on this date
    depart_today = 0
    if hasattr(model, 'in_transit'):
        for (origin, dest, prod, dep_date, state) in model.in_transit:
            if origin == mfg_node and dep_date == t:
                try:
                    depart_today += value(model.in_transit[origin, dest, prod, dep_date, state])
                except:
                    pass

    # End inventory on this date
    end_inv_today = 0
    if hasattr(model, 'inventory'):
        for prod in model.products:
            for state in ['ambient', 'frozen']:
                if (mfg_node, prod, state, t) in model.inventory:
                    try:
                        end_inv_today += value(model.inventory[mfg_node, prod, state, t])
                    except:
                        pass

    # Cumulative
    cum_production += prod_today
    cum_departures += depart_today

    # Balance: init_inv + cum_prod - cum_depart - end_inv
    # Should be ~0 if material balance holds
    balance = init_inv_total + cum_production - cum_departures - end_inv_today

    print(f"{t} {prod_today:>8,.0f} {depart_today:>8,.0f} {end_inv_today:>8,.0f} {cum_production:>10,.0f} {cum_departures:>10,.0f} {balance:>10,.0f}")

print("-"*100)
print(f"{'FINAL':<12} {cum_production:>8,.0f} {cum_departures:>8,.0f} {end_inv_today:>8,.0f}")

print(f"\n\nFINAL BALANCE CHECK:")
print(f"  Init inventory:       {init_inv_total:>10,.0f}")
print(f"  Total production:     {cum_production:>10,.0f}")
print(f"  Total departures:     {cum_departures:>10,.0f}")
print(f"  End inventory:        {end_inv_today:>10,.0f}")
print(f"  ────────────────────────────────")
print(f"  Balance (should be 0): {init_inv_total + cum_production - cum_departures - end_inv_today:>9,.0f}")

if abs(init_inv_total + cum_production - cum_departures - end_inv_today) > 100:
    print(f"\n  ❌ MATERIAL BALANCE VIOLATED!")
else:
    print(f"\n  ✓ Material balance holds")

print("\n" + "="*100)
