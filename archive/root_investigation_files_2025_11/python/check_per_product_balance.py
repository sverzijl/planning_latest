"""
Check material balance PER PRODUCT for manufacturing on Day 1.

Maybe the constraint is satisfied per-product but violates when summed?
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

# Check Day 1 material balance per product
print("="*100)
print("DAY 1 MATERIAL BALANCE CHECK - PER PRODUCT (Manufacturing 6122)")
print("="*100)

mfg_node = '6122'
day1 = min(model.dates)

print(f"\nDate: {day1}\n")
print(f"{'Product':<40} {'InitInv':>10} {'Prod':>10} {'Depart':>10} {'EndInv':>10} {'Balance':>10}")
print("-"*100)

total_init = 0
total_prod = 0
total_depart = 0
total_end = 0

for prod in model.products:
    # Initial inventory for this product
    init_inv = model_builder.initial_inventory.get((mfg_node, prod, 'ambient'), 0)

    # Production
    production = 0
    if (mfg_node, prod, day1) in model.production:
        try:
            production = value(model.production[mfg_node, prod, day1])
        except:
            pass

    # Departures
    departures = 0
    if hasattr(model, 'in_transit'):
        for dest in ['6104', '6110', '6125', 'Lineage']:
            for state in ['ambient', 'frozen']:
                key = (mfg_node, dest, prod, day1, state)
                if key in model.in_transit:
                    try:
                        departures += value(model.in_transit[key])
                    except:
                        pass

    # End inventory
    end_inv = 0
    if (mfg_node, prod, 'ambient', day1) in model.inventory:
        try:
            end_inv = value(model.inventory[mfg_node, prod, 'ambient', day1])
        except:
            pass

    # Balance: init + prod - depart - end (should be ~0)
    balance = init_inv + production - departures - end_inv

    print(f"{prod[:40]:<40} {init_inv:>10,.0f} {production:>10,.0f} {departures:>10,.0f} {end_inv:>10,.0f} {balance:>10,.0f}")

    total_init += init_inv
    total_prod += production
    total_depart += departures
    total_end += end_inv

print("-"*100)
print(f"{'TOTAL':<40} {total_init:>10,.0f} {total_prod:>10,.0f} {total_depart:>10,.0f} {total_end:>10,.0f} {total_init + total_prod - total_depart - total_end:>10,.0f}")

print(f"\n\n{'='*100}")
print(f"INTERPRETATION:")
print(f"{'='*100}")
print(f"\nIf balance = 0 for ALL products: Constraint holds perfectly")
print(f"If balance != 0 for ANY product: That product violates material balance")
print(f"\nFrom constraint formula (line 1683 in sliding_window_model.py):")
print(f"  inventory[t] == prev_inv + production - departures")
print(f"  Rearranged: prev_inv + production - departures - inventory[t] == 0")
print(f"  That's exactly what 'Balance' column shows!")
print(f"\n{'='*100}")
