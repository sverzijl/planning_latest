"""
Trace demand node 6104 material balance day-by-day.

This will show if material balance holds at demand nodes or if phantom supply enters here.
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

# Trace demand node 6104
print("="*120)
print("DEMAND NODE 6104 MATERIAL BALANCE TRACE - ONE PRODUCT")
print("="*120)

node = '6104'
prod = 'HELGAS GFREE MIXED GRAIN 500G'  # Pick first product

# Get initial inventory
init_inv = model_builder.initial_inventory.get((node, prod, 'ambient'), 0)

print(f"\nNode: {node}")
print(f"Product: {prod}")
print(f"Initial inventory: {init_inv:,.0f} units\n")

print(f"{'Date':<12} {'PrevInv':>10} {'Arrivals':>10} {'Departs':>10} {'Consumed':>10} {'EndInv':>10} {'Balance':>10}")
print("-"*120)

dates = sorted(list(model.dates))
cum_arrivals = 0
cum_consumed = 0

for i, t in enumerate(dates):
    # Previous inventory
    if i == 0:
        prev_inv = init_inv
    else:
        prev_date = dates[i-1]
        if (node, prod, 'ambient', prev_date) in model.inventory:
            try:
                prev_inv = value(model.inventory[node, prod, 'ambient', prev_date])
            except:
                prev_inv = 0
        else:
            prev_inv = 0

    # Arrivals: goods that departed (t - transit_days) ago
    arrivals = 0
    for route in model_builder.routes:
        if route.destination_node_id == node:
            departure_date = t - timedelta(days=route.transit_days)
            if departure_date in model.dates:
                # Check all possible origin nodes
                for origin in ['6122', '6104', '6125', 'Lineage']:  # Possible origins
                    for state in ['ambient', 'frozen']:
                        key = (origin, node, prod, departure_date, state)
                        if key in model.in_transit:
                            try:
                                qty = value(model.in_transit[key])
                                if qty > 0.01:
                                    arrivals += qty
                            except:
                                pass

    # Departures: goods leaving TODAY via in_transit
    departures = 0
    for route in model_builder.routes:
        if route.origin_node_id == node:
            for state in ['ambient', 'frozen']:
                key = (node, route.destination_node_id, prod, t, state)
                if key in model.in_transit:
                    try:
                        departures += value(model.in_transit[key])
                    except:
                        pass

    # Consumption
    consumed = 0
    if (node, prod, t) in model.demand_consumed_from_ambient:
        try:
            consumed = value(model.demand_consumed_from_ambient[node, prod, t])
        except:
            pass

    # End inventory
    end_inv = 0
    if (node, prod, 'ambient', t) in model.inventory:
        try:
            end_inv = value(model.inventory[node, prod, 'ambient', t])
        except:
            pass

    # Material balance check
    # Expected: end_inv = prev_inv + arrivals - departures - consumed
    expected_end_inv = prev_inv + arrivals - departures - consumed
    balance = end_inv - expected_end_inv

    cum_arrivals += arrivals
    cum_consumed += consumed

    print(f"{t} {prev_inv:>10,.0f} {arrivals:>10,.0f} {departures:>10,.0f} {consumed:>10,.0f} {end_inv:>10,.0f} {balance:>10,.2f}")

print("-"*120)

# Final summary
print(f"\n\nSUMMARY FOR NODE {node}, PRODUCT {prod}:")
print(f"  Initial inventory:  {init_inv:>10,.0f}")
print(f"  Total arrivals:     {cum_arrivals:>10,.0f}")
print(f"  Total consumed:     {cum_consumed:>10,.0f}")
print(f"  Final inventory:    {end_inv:>10,.0f}")
print(f"  ───────────────────────────────")
print(f"  Material balance:   {init_inv + cum_arrivals - cum_consumed - end_inv:>10,.0f}")

if abs(init_inv + cum_arrivals - cum_consumed - end_inv) < 1:
    print(f"\n✓ Material balance HOLDS (balance ≈ 0)")
else:
    print(f"\n❌ Material balance VIOLATED!")

# Check if any daily balances are non-zero
print(f"\n\n{'='*120}")
print(f"DAILY BALANCE CHECK:")
print(f"{'='*120}")
print(f"\nIf Balance column shows non-zero values, material balance constraint is violated that day.")
print(f"If all Balance values are ≈ 0, constraint holds perfectly.")

# Now check ALL products for this node
print(f"\n\n{'='*120}")
print(f"TOTAL FOR ALL PRODUCTS AT NODE {node}")
print(f"{'='*120}")

total_init = 0
total_arrivals = 0
total_consumed = 0
total_end = 0

for prod in model.products:
    init_inv_prod = model_builder.initial_inventory.get((node, prod, 'ambient'), 0)
    total_init += init_inv_prod

    for t in dates:
        # Arrivals
        for route in model_builder.routes:
            if route.destination_node_id == node:
                departure_date = t - timedelta(days=route.transit_days)
                if departure_date in model.dates:
                    for origin in ['6122', '6104', '6125', 'Lineage']:
                        for state in ['ambient', 'frozen']:
                            key = (origin, node, prod, departure_date, state)
                            if key in model.in_transit:
                                try:
                                    qty = value(model.in_transit[key])
                                    if qty > 0.01:
                                        total_arrivals += qty
                                except:
                                    pass

        # Consumption
        if (node, prod, t) in model.demand_consumed_from_ambient:
            try:
                total_consumed += value(model.demand_consumed_from_ambient[node, prod, t])
            except:
                pass

    # End inventory
    last_date = dates[-1]
    if (node, prod, 'ambient', last_date) in model.inventory:
        try:
            total_end += value(model.inventory[node, prod, 'ambient', last_date])
        except:
            pass

print(f"\nNode {node} - ALL PRODUCTS:")
print(f"  Initial inventory:  {total_init:>12,.0f}")
print(f"  Total arrivals:     {total_arrivals:>12,.0f}")
print(f"  Total consumed:     {total_consumed:>12,.0f}")
print(f"  Final inventory:    {total_end:>12,.0f}")
print(f"  ──────────────────────────────────")
print(f"  Material balance:   {total_init + total_arrivals - total_consumed - total_end:>12,.0f}")

gap = total_consumed - (total_init + total_arrivals)
if gap > 100:
    print(f"\n❌ PHANTOM SUPPLY: {gap:,.0f} units!")
    print(f"   Node consumed {gap:,.0f} more than it received!")
elif abs(total_init + total_arrivals - total_consumed - total_end) < 100:
    print(f"\n✓ Material balance holds")

print(f"\n{'='*120}")
