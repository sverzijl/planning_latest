#!/usr/bin/env python3
"""
MINIMAL TEST: 6130 Ambient Consumption with Oct 16/17 dates

User scenario (exact):
- Inventory snapshot: Oct 16, 2025
- Planning starts: Oct 17, 2025
- 4-week horizon
- 6130 has 937 units ambient initial inventory
- 6130 has demand starting Oct 17

Expected: Ambient inventory consumed
Observed: Ambient inventory persists unchanged

This test will prove if the bug exists and where.
"""

from datetime import date, timedelta
from pyomo.environ import value, ConcreteModel
from src.parsers.excel_parser import ExcelParser
from src.parsers.product_alias_resolver import ProductAliasResolver
from src.parsers.inventory_parser import InventoryParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.parsers.multi_file_parser import MultiFileParser
from src.models.location import LocationType

# EXACT USER PARAMETERS
INVENTORY_SNAPSHOT = date(2025, 10, 16)
PLANNING_START = date(2025, 10, 17)
PLANNING_END = PLANNING_START + timedelta(days=27)

print("="*100)
print("MINIMAL TEST: 6130 Ambient Consumption (Oct 16/17)")
print("="*100)
print(f"Inventory snapshot: {INVENTORY_SNAPSHOT}")
print(f"Planning start: {PLANNING_START}")
print(f"Horizon: {PLANNING_START} to {PLANNING_END} (28 days)")
print()

# Step 1: Load data the way UI does
resolver = ProductAliasResolver('data/examples/Network_Config.xlsx')

# Parse forecast
forecast_parser = ExcelParser('data/examples/Gluten Free Forecast - Latest.xlsm', resolver)
forecast_raw = forecast_parser.parse_forecast()

# Parse inventory with Oct 16 snapshot
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', resolver, INVENTORY_SNAPSHOT)
inv_snapshot = inv_parser.parse()

print(f"Inventory snapshot from parser: {inv_snapshot.snapshot_date}")
assert inv_snapshot.snapshot_date == INVENTORY_SNAPSHOT, "Snapshot date mismatch!"

# Filter forecast to horizon
forecast_filtered = [
    e for e in forecast_raw.entries
    if PLANNING_START <= e.forecast_date <= PLANNING_END
]

print(f"Forecast entries in horizon: {len(forecast_filtered)}")

# Check 6130 demand on Oct 17
oct17_demand_6130 = [e for e in forecast_filtered if e.location_id == '6130' and e.forecast_date == PLANNING_START]
oct17_total = sum(e.quantity for e in oct17_demand_6130)
print(f"Demand at 6130 on Oct 17: {oct17_total:.0f} units ({len(oct17_demand_6130)} products)")

if oct17_total < 100:
    print("❌ No demand found - this is the problem!")
    exit(1)

# Build model
parser = MultiFileParser(
    'data/examples/Gluten Free Forecast - Latest.xlsm',
    'data/examples/Network_Config.xlsx',
    'data/examples/inventory_latest.XLSX'
)
_, locations, routes_legacy, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manufacturing_site = manufacturing_locations[0]

forecast_obj = Forecast(name="Oct17", entries=forecast_filtered)

converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast_obj)
unified_routes = converter.convert_routes(routes_legacy)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

# Parse products
network_parser = ExcelParser('data/examples/Network_Config.xlsx', resolver)
products_dict = network_parser.parse_products()

# Convert inventory to dict format
inv_dict = {}
for entry in inv_snapshot.entries:
    # InventoryEntry has: location_id, product_id, quantity
    # Resolve product ID
    product_id = resolver.resolve_product_id(entry.product_id) if resolver else entry.product_id
    # Default to ambient state
    inv_dict[(entry.location_id, product_id, 'ambient')] = entry.quantity

print(f"Initial inventory entries: {len(inv_dict)}")

# Check 6130 specifically
inv_6130 = {k: v for k, v in inv_dict.items() if k[0] == '6130'}
print(f"Initial inventory at 6130: {len(inv_6130)} entries")
total_6130 = sum(inv_6130.values())
print(f"  Total: {total_6130:.0f} units (all ambient)")
print()

# Build model
cost_structure.waste_cost_multiplier = 10.0

print("Building model...")
model_builder = SlidingWindowModel(
    nodes, unified_routes, forecast_obj, labor_calendar, cost_structure,
    products_dict, PLANNING_START, PLANNING_END, unified_truck_schedules,
    inv_dict, INVENTORY_SNAPSHOT,
    True, True, True
)

print("Solving (60s limit)...")
result = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05)

if not result.success:
    print(f"❌ Solve failed: {result.termination_condition}")
    exit(1)

print(f"✅ Solved: Objective = ${result.objective_value:,.0f}")

model = model_builder.model

# TEST: Check if 6130 ambient inventory is consumed
print()
print("="*100)
print("6130 AMBIENT CONSUMPTION ANALYSIS")
print("="*100)

# Check inventory on Day 1 vs Day 28
key_first = ('6130', 'HELGAS GFREE MIXED GRAIN 500G', 'ambient', PLANNING_START)
key_last = ('6130', 'HELGAS GFREE MIXED GRAIN 500G', 'ambient', PLANNING_END)

if key_first in model.inventory:
    qty_day1 = value(model.inventory[key_first])
    print(f"\nHELGAS MIXED GRAIN ambient at 6130:")
    print(f"  Day 1  ({PLANNING_START}): {qty_day1:.0f} units")

    if key_last in model.inventory:
        qty_day28 = value(model.inventory[key_last])
        print(f"  Day 28 ({PLANNING_END}): {qty_day28:.0f} units")

        if abs(qty_day1 - qty_day28) < 10:
            print()
            print("  ❌ BUG CONFIRMED: Inventory unchanged!")
            print("  Ambient inventory NOT being consumed")
        else:
            print()
            print("  ✓ Inventory being consumed")

# Check consumption on Oct 17
print(f"\nConsumption from ambient at 6130 on Oct 17:")
total_consumed = 0
if hasattr(model, 'demand_consumed_from_ambient'):
    for (node, prod, t) in model.demand_consumed_from_ambient:
        if node == '6130' and t == PLANNING_START:
            qty = value(model.demand_consumed_from_ambient[node, prod, t])
            if qty > 0.01:
                total_consumed += qty
                print(f"  {prod[:35]:35s} {qty:>6.0f} units")

print(f"\nTotal consumed: {total_consumed:.0f} units")
print(f"Demand on Oct 17: {oct17_total:.0f} units")

if total_consumed < 100:
    print()
    print("="*100)
    print("❌ BUG CONFIRMED: Almost no consumption from ambient at 6130")
    print("="*100)
    print()
    print("Next step: Investigate WHY consumption is zero despite:")
    print("  - Demand exists (615 units)")
    print("  - Inventory exists (937 units)")
    print("  - Variables exist (demand_consumed_from_ambient)")
    print("  - Circular dependency was fixed")
else:
    print()
    print("✅ Consumption working correctly")
