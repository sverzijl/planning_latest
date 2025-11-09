"""
Deep MIP Analysis: Solve WITHOUT init_inv in Q and analyze in detail.

This will show EXACTLY what changes and WHY.
"""

from datetime import datetime, timedelta
from pyomo.core.base import value

from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType


print("="*100)
print("MIP ANALYSIS: Solving WITHOUT init_inv in Q")
print("="*100)
print("\nThis will reveal the mechanism causing excessive end inventory...")

# Build and solve
coordinator = DataCoordinator(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)
validated = coordinator.load_and_validate()

forecast_entries = [
    ForecastEntry(location_id=e.node_id, product_id=e.product_id,
                 forecast_date=e.demand_date, quantity=e.quantity)
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
    print(f"\n❌ Solve FAILED without init_inv in Q!")
    print(f"   Termination: {result.termination_condition}")
    print(f"\n   This would mean init_inv in Q is REQUIRED for feasibility")
    exit(1)

print(f"\n✓ Solve succeeded without init_inv in Q")

model = model_builder.model
solution = model_builder.extract_solution(model)

# Extract key metrics
last_date = max(model.dates)

end_inv_total = sum(
    value(model.inventory[n, p, s, last_date])
    for (n, p, s, t) in model.inventory
    if t == last_date and value(model.inventory[n, p, s, last_date]) > 0.01
)

# Check Day 1 init_inv consumption
init_inv_total = sum(validated.get_inventory_dict().values())
day1 = min(model.dates)

consumption_day1 = sum(
    value(model.demand_consumed_from_ambient[n, p, day1])
    for (n, p, t) in model.demand_consumed_from_ambient
    if t == day1
)

inventory_day1 = sum(
    value(model.inventory[n, p, s, day1])
    for (n, p, s, t) in model.inventory
    if t == day1 and value(model.inventory[n, p, s, day1]) > 0.01
)

print(f"\n\n{'='*100}")
print(f"RESULTS WITHOUT init_inv in Q:")
print(f"{'='*100}")

print(f"\nOverall:")
print(f"  Production: {solution.total_production:,.0f} units")
print(f"  End inventory: {end_inv_total:,.0f} units")
print(f"  Shortage: {solution.total_shortage_units:,.0f} units")
print(f"  Objective: ${solution.total_cost:,.0f}")

print(f"\nDay 1 Analysis (init_inv handling):")
print(f"  Initial inventory: {init_inv_total:,.0f} units")
print(f"  Day 1 consumption: {consumption_day1:,.0f} units")
print(f"  Day 1 ending inventory: {inventory_day1:,.0f} units")
print(f"  init_inv consumed on Day 1: {min(consumption_day1, init_inv_total):,.0f} units")
print(f"  init_inv remaining after Day 1: {max(0, inventory_day1 - (solution.total_production * 0)):,.0f} units (approx)")

# Check where end inventory is
end_inv_by_product = {}
for (n, p, s, t) in model.inventory:
    if t == last_date:
        qty = value(model.inventory[n, p, s, t])
        if qty > 0.01:
            end_inv_by_product[p] = end_inv_by_product.get(p, 0) + qty

print(f"\n\nEnd inventory by product:")
for prod, qty in sorted(end_inv_by_product.items(), key=lambda x: -x[1]):
    print(f"  {prod[:40]:<40}: {qty:>10,.0f} units")

# Critical check
print(f"\n\n{'='*100}")
print(f"CRITICAL MIP INSIGHT:")
print(f"{'='*100}")

init_inv_locked = inventory_day1 if inventory_day1 > init_inv_total * 0.9 else 0

if init_inv_locked > init_inv_total * 0.9:
    print(f"\n❌ INIT_INV IS LOCKED AS INVENTORY!")
    print(f"   Day 1 ending inventory ({inventory_day1:,.0f}) ≈ initial inventory ({init_inv_total:,.0f})")
    print(f"\n   WITHOUT init_inv in Q:")
    print(f"   - Sliding window Day 1: consumption[Day1] <= production[Day1]")
    print(f"   - This EXCLUDES init_inv from consumable supply!")
    print(f"   - Material balance: I[1] = init_inv + production - consumption")
    print(f"   - Result: I[1] >= init_inv (can't consume it!)")
    print(f"\n   → Initial inventory becomes LOCKED, can never be consumed")
    print(f"   → Sits as inventory throughout horizon")
    print(f"   → Becomes end inventory waste!")
    print(f"\n   THIS IS WHY removing init_inv from Q makes end inventory WORSE!")
else:
    print(f"\n✓ init_inv consumed normally")
    print(f"   Need to investigate other reasons for high end inventory")

print(f"\n{'='*100}")
