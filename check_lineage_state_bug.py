#!/usr/bin/env python3
"""
Check Lineage inventory state bug.

User observation: UI shows ambient and thawed inventory at Lineage on Oct 24-26.
Expected: Lineage should have ONLY frozen inventory (frozen-only facility).
"""

from pyomo.environ import value
from datetime import datetime, timedelta, date
from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType

# Use October 24 start date (matches user's observation)
START_DATE = date(2025, 10, 24)

print("="*80)
print("LINEAGE STATE CONVERSION BUG CHECK")
print("="*80)
print(f"Planning start: {START_DATE}")
print(f"Looking for bug at Lineage on first delivery (Oct 25)")
print()

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

# 4-week horizon starting Oct 24
end = START_DATE + timedelta(days=27)

# Use waste_mult=10 (disposal bug is fixed)
cost_structure.waste_cost_multiplier = 10.0

model_builder = SlidingWindowModel(
    nodes, unified_routes, forecast, labor_calendar, cost_structure,
    products_dict, START_DATE, end, unified_truck_schedules,
    validated.get_inventory_dict(), validated.inventory_snapshot_date,
    True, True, True
)

print("Solving...")
result = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.05)

if not result.success:
    print(f"❌ Solve failed: {result.termination_condition}")
    exit(1)

model = model_builder.model

print("\n" + "="*80)
print("PYOMO MODEL VARIABLES AT LINEAGE (Ground Truth)")
print("="*80)

# Check what inventory variables actually exist for Lineage
first_delivery_date = START_DATE + timedelta(days=1)  # Oct 25 (1 day transit from 6122)

for state in ['frozen', 'ambient', 'thawed']:
    print(f"\n{state.upper()} inventory variables at Lineage:")
    print("-"*80)
    found_any = False

    if hasattr(model, 'inventory'):
        for (node, prod, st, dt) in model.inventory:
            if node == 'Lineage' and st == state and dt == first_delivery_date:
                qty = value(model.inventory[node, prod, st, dt])
                if qty > 0.01:
                    print(f"  {prod[:40]:40s} {qty:>8.0f} units")
                    found_any = True

    if not found_any:
        print("  None")

# Now check solution extraction
print("\n" + "="*80)
print("SOLUTION EXTRACTION (What UI Sees)")
print("="*80)

solution = model_builder.extract_solution(model)

print(f"\nInventory state entries for Lineage on {first_delivery_date}:")
print("-"*80)

lineage_inv_states = [
    inv for inv in solution.inventory_state
    if inv.node_id == 'Lineage' and inv.date == first_delivery_date
]

if lineage_inv_states:
    for inv in lineage_inv_states:
        print(f"  {inv.product_id[:40]:40s} state={inv.state:8s} qty={inv.quantity:>8.0f}")
else:
    print("  No inventory_state entries for Lineage")

print("\n" + "="*80)
print("BUG DIAGNOSIS:")
print("="*80)

# Count by state in Pyomo model
pyomo_frozen = sum(
    value(model.inventory[n, p, s, first_delivery_date])
    for (n, p, s, dt) in model.inventory
    if n == 'Lineage' and s == 'frozen' and dt == first_delivery_date and value(model.inventory[n, p, s, dt]) > 0.01
)

pyomo_ambient = sum(
    value(model.inventory[n, p, s, first_delivery_date])
    for (n, p, s, dt) in model.inventory
    if n == 'Lineage' and s == 'ambient' and dt == first_delivery_date and value(model.inventory[n, p, s, dt]) > 0.01
)

# Count by state in solution extraction
solution_frozen = sum(inv.quantity for inv in lineage_inv_states if inv.state == 'frozen')
solution_ambient = sum(inv.quantity for inv in lineage_inv_states if inv.state == 'ambient')
solution_thawed = sum(inv.quantity for inv in lineage_inv_states if inv.state == 'thawed')

print(f"\nPyomo model variables (ground truth):")
print(f"  Frozen:  {pyomo_frozen:>8.0f} units")
print(f"  Ambient: {pyomo_ambient:>8.0f} units")
print()
print(f"Solution extraction (what UI sees):")
print(f"  Frozen:  {solution_frozen:>8.0f} units")
print(f"  Ambient: {solution_ambient:>8.0f} units")
print(f"  Thawed:  {solution_thawed:>8.0f} units")
print()

if pyomo_frozen > 0 and solution_ambient > 0:
    print("❌ BUG IN SOLUTION EXTRACTION!")
    print("  Pyomo model has FROZEN inventory")
    print("  But solution.inventory_state shows AMBIENT/THAWED")
    print("  → Bug is in extract_solution(), not model formulation")
elif pyomo_ambient > 0:
    print("❌ BUG IN MODEL FORMULATION!")
    print("  Pyomo model has AMBIENT inventory at Lineage")
    print("  But Lineage is frozen-only")
    print("  → State conversion not working in constraints")
else:
    print("✅ Both Pyomo and extraction show frozen only")
    print("  Need to check why UI displays differently")
