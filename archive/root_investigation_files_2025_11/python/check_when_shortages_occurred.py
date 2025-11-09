"""
Check WHEN shortages occurred vs when end inventory accumulated.

MIP Hypothesis: Products with end inventory on Day 28 had shortages on Days 1-27.
This would mean production timing mismatch - produced too late for early demand.
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
    exit(1)

print("Solved!\n")
model = model_builder.model
solution = model_builder.extract_solution(model)

# Get products with significant end inventory
last_date = max(model.dates)

products_with_end_inv = {}
for (node_id, prod, state, t) in model.inventory:
    if t == last_date:
        try:
            qty = value(model.inventory[node_id, prod, state, t])
            if qty > 50:  # Significant amount
                key = (node_id, prod)
                products_with_end_inv[key] = products_with_end_inv.get(key, 0) + qty
        except:
            pass

print("="*110)
print(f"SHORTAGE TIMING ANALYSIS FOR PRODUCTS WITH END INVENTORY")
print("="*110)

print(f"\nAnalyzing {len(products_with_end_inv)} node/product combinations with end inventory...\n")

# For each, check when shortages occurred
for (node_id, prod), end_inv_qty in sorted(products_with_end_inv.items(), key=lambda x: -x[1])[:10]:
    print(f"\n{node_id} - {prod[:40]}:")
    print(f"  End inventory (Day 28): {end_inv_qty:,.0f} units")

    # Find shortages across horizon
    shortage_days = []
    total_shortage_this_combo = 0

    if hasattr(solution, 'shortages'):
        for (node, p, t), shortage_qty in solution.shortages.items():
            if node == node_id and p == prod and shortage_qty > 0.01:
                shortage_days.append((t, shortage_qty))
                total_shortage_this_combo += shortage_qty

    if len(shortage_days) > 0:
        print(f"  Total shortage (all days): {total_shortage_this_combo:,.0f} units")
        print(f"  Shortage occurred on {len(shortage_days)} days:")

        for t, qty in sorted(shortage_days)[:5]:  # Show first 5
            day_num = (t - list(model.dates)[0]).days + 1
            print(f"    Day {day_num} ({t}): {qty:,.0f} units shortage")

        # Calculate opportunity
        reallocatable = min(end_inv_qty, total_shortage_this_combo)
        savings = reallocatable * 3  # $13 waste - $10 shortage

        print(f"\n  → Could reallocate {reallocatable:,.0f} units to earlier demand")
        print(f"  → Savings: ${savings:,.0f} (avoid waste, serve demand)")
    else:
        print(f"  ✓ No shortage for this combination (end inv is just overproduction)")

# Summary
print(f"\n\n{'='*110}")
print(f"DIAGNOSIS (MIP Theory):")
print(f"{'='*110}")

print(f"\nIf end inventory products HAD shortages on earlier days:")
print(f"  → TIMING MISMATCH: Produced too late for early demand")
print(f"  → Fix: Allow earlier production or better demand matching")
print(f"\nIf end inventory products had NO shortages:")
print(f"  → OVERPRODUCTION: Made too much, no demand for it")
print(f"  → Fix: Tighten production constraints or increase waste penalty")

print(f"\n{'='*110}")
