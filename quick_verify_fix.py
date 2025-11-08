#!/usr/bin/env python3
"""Quick verification that circular dependency fix works."""

from datetime import datetime, timedelta
from pyomo.environ import value
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

# Set waste_mult=10
cost_structure.waste_cost_multiplier = 10.0

print("="*80)
print("DISPOSAL BUG FIX - QUICK VERIFICATION")
print("="*80)
print(f"waste_multiplier: {cost_structure.waste_cost_multiplier}")
print()

# Solve
model_builder = SlidingWindowModel(
    nodes, unified_routes, forecast, labor_calendar, cost_structure,
    products_dict, start, end, unified_truck_schedules,
    validated.get_inventory_dict(), validated.inventory_snapshot_date,
    True, True, True
)

result = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=300, mip_gap=0.01)

if not result.success:
    print(f"❌ FAILED: {result.termination_condition}")
    exit(1)

# Extract disposal from model
model = model_builder.model
disposal_total = 0
if hasattr(model, 'disposal'):
    for (node, prod, state, t) in model.disposal:
        disp_val = value(model.disposal[node, prod, state, t])
        if disp_val > 0.01:
            disposal_total += disp_val

# Extract end inventory
last_date = max(model.dates)
end_inv_total = 0
for (node, prod, state, t) in model.inventory:
    if t == last_date:
        inv_val = value(model.inventory[node, prod, state, t])
        if inv_val > 0.01:
            end_inv_total += inv_val

# Extract production
prod_total = 0
if hasattr(model, 'production'):
    for (node, prod, t) in model.production:
        prod_val = value(model.production[node, prod, t])
        if prod_val > 0.01:
            prod_total += prod_val

# Extract shortage
shortage_total = 0
if hasattr(model, 'shortage'):
    for (node, prod, t) in model.shortage:
        short_val = value(model.shortage[node, prod, t])
        if short_val > 0.01:
            shortage_total += short_val

print("\nRESULTS:")
print("="*80)
print(f"Objective: ${result.objective_value:,.0f}")
print(f"Production: {prod_total:,.0f} units")
print(f"Shortage: {shortage_total:,.0f} units")
print(f"End inventory: {end_inv_total:,.0f} units")
print(f"Disposal: {disposal_total:,.0f} units")
print()

print("EVALUATION:")
print("="*80)

# Compare to baseline
print("Baseline (with circular bug):")
print("  Objective: $1,052,000")
print("  Disposal: 7,434 units")
print("  Shortage: 48,848 units")
print()

print("With fix:")
print(f"  Objective: ${result.objective_value:,.0f}  ({'✅ BETTER' if result.objective_value < 950_000 else '❌ STILL HIGH'})")
print(f"  Disposal: {disposal_total:,.0f} units  ({'✅ ELIMINATED' if disposal_total < 100 else '❌ STILL PRESENT'})")
print(f"  Shortage: {shortage_total:,.0f} units  ({'✅ REDUCED' if shortage_total < 40_000 else '⚠️ STILL HIGH'})")
print(f"  End inventory: {end_inv_total:,.0f} units  ({'✅ REASONABLE' if end_inv_total < 20_000 else '⚠️ HIGH'})")
print()

if disposal_total < 100 and result.objective_value < 950_000:
    print("="*80)
    print("✅ DISPOSAL BUG IS FIXED!")
    print("="*80)
    print(f"\nSavings: ${1_052_000 - result.objective_value:,.0f} (vs broken formulation)")
else:
    print("="*80)
    print("⚠️  Partial improvement but not fully fixed")
    print("="*80)
