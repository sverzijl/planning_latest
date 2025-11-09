"""
Find which specific node/product combinations have end inventory on Day 28
that could have been consumed instead of taking shortage.
"""

from datetime import datetime, timedelta
from pyomo.core.base import value

from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType


# Solve
print("Solving...")
coordinator = DataCoordinator(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)
validated = coordinator.load_and_validate()

forecast_entries = [
    ForecastEntry(
        location_id=e.node_id,
        product_id=e.product_id,
        forecast_date=e.demand_date,
        quantity=e.quantity
    )
    for e in validated.demand_entries
]
forecast = Forecast(name="Test", entries=forecast_entries)

parser = MultiFileParser(
    'data/examples/Gluten Free Forecast - Latest.xlsm',
    'data/examples/Network_Config.xlsx',
    'data/examples/inventory_latest.XLSX'
)
_, locations, routes_legacy, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manufacturing_site = manufacturing_locations[0]

converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes_legacy)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)
products_dict = {p.id: p for p in validated.products}

start = validated.planning_start_date
end = (datetime.combine(start, datetime.min.time()) + timedelta(days=27)).date()

model_builder = SlidingWindowModel(
    nodes, unified_routes, forecast, labor_calendar, cost_structure,
    products_dict, start, end, unified_truck_schedules,
    validated.get_inventory_dict(), validated.inventory_snapshot_date,
    True, True, True
)

result = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01)
if not result.success:
    exit(1)

print("Solved!\n")
model = model_builder.model

# Find wasted inventory on Day 28
print("="*110)
print("WASTED INVENTORY ON DAY 28 (End-of-Horizon)")
print("="*110)

last_date = max(model.dates)

# For each node/product, check if has end inventory AND shortage on Day 28
waste_opportunities = []

for node_id in model.nodes:
    for prod in model.products:
        # Get end inventory
        end_inv = 0
        if (node_id, prod, 'ambient', last_date) in model.inventory:
            try:
                end_inv = value(model.inventory[node_id, prod, 'ambient', last_date])
            except:
                pass

        # Get shortage on Day 28
        shortage = 0
        if hasattr(model, 'shortage') and (node_id, prod, last_date) in model.shortage:
            try:
                shortage = value(model.shortage[node_id, prod, last_date])
            except:
                pass

        # Get consumption
        consumption = 0
        if (node_id, prod, last_date) in model.demand_consumed_from_ambient:
            try:
                consumption = value(model.demand_consumed_from_ambient[node_id, prod, last_date])
            except:
                pass

        # Get demand
        demand = model_builder.demand.get((node_id, prod, last_date), 0)

        # If has BOTH inventory and shortage → waste opportunity
        if end_inv > 10 and shortage > 10:
            waste_opportunities.append({
                'node': node_id,
                'product': prod,
                'inventory': end_inv,
                'shortage': shortage,
                'consumption': consumption,
                'demand': demand
            })

print(f"\nFound {len(waste_opportunities)} cases of inventory + shortage on same day:")
print(f"\n{'Node':<10} {'Product':<40} {'Inventory':>10} {'Shortage':>10} {'Demand':>10} {'Consumed':>10}")
print("-"*110)

for item in sorted(waste_opportunities, key=lambda x: -(x['inventory'] + x['shortage']))[:15]:
    print(f"{item['node']:<10} {item['product'][:40]:<40} {item['inventory']:>10,.0f} {item['shortage']:>10,.0f} {item['demand']:>10,.0f} {item['consumption']:>10,.0f}")

total_waste_opp = sum(min(item['inventory'], item['shortage']) for item in waste_opportunities)
print("-"*110)
print(f"Potential savings (reallocate min(inv, shortage)): ${total_waste_opp * 3:,.0f}")

# Analysis
print(f"\n\n{'='*110}")
print(f"MIP ANALYSIS:")
print(f"{'='*110}")

if len(waste_opportunities) > 0:
    print(f"\n❌ Found {len(waste_opportunities)} node/product combinations with BOTH inventory and shortage on Day 28!")
    print(f"\nThis is economically irrational. For each case:")
    print(f"  - Inventory exists at the node")
    print(f"  - Demand exists at the SAME node")
    print(f"  - Yet model takes shortage instead of consuming inventory!")
    print(f"\nWHICH CONSTRAINT prevents consumption?")

    # Check one specific case
    worst_case = max(waste_opportunities, key=lambda x: min(x['inventory'], x['shortage']))
    print(f"\n\nWorst case: {worst_case['node']}, {worst_case['product'][:35]}")
    print(f"  Inventory: {worst_case['inventory']:,.0f}")
    print(f"  Shortage: {worst_case['shortage']:,.0f}")
    print(f"  Demand: {worst_case['demand']:,.0f}")
    print(f"  Consumed: {worst_case['consumption']:,.0f}")

    unconsumable = worst_case['inventory'] - worst_case['consumption']
    if unconsumable > 10:
        print(f"\n  → {unconsumable:,.0f} units are UNCONSUMABLE despite being at demand node!")
        print(f"  Why? Check:")
        print(f"    1. Is inventory too old? (shelf life constraint)")
        print(f"    2. Is sliding window blocking consumption?")
        print(f"    3. Is there a constraint bug?")

else:
    print(f"\n✓ No waste opportunities on Day 28")
    print(f"  End inventory must be from EARLIER days (expired/unusable)")

print(f"\n{'='*110}")
