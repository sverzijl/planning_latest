#!/usr/bin/env python3
"""Check if production is happening at 6122 in the Oct 16/17 scenario"""

from datetime import date, timedelta
from pyomo.environ import value
from src.parsers.excel_parser import ExcelParser
from src.parsers.product_alias_resolver import ProductAliasResolver
from src.parsers.inventory_parser import InventoryParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast
from src.parsers.multi_file_parser import MultiFileParser
from src.models.location import LocationType

INVENTORY_SNAPSHOT = date(2025, 10, 16)
PLANNING_START = date(2025, 10, 17)
PLANNING_END = PLANNING_START + timedelta(days=27)

print("Building and solving model...")

resolver = ProductAliasResolver('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gluten Free Forecast - Latest.xlsm', resolver)
forecast_raw = forecast_parser.parse_forecast()

inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', resolver, INVENTORY_SNAPSHOT)
inv_snapshot = inv_parser.parse()

forecast_filtered = [
    e for e in forecast_raw.entries
    if PLANNING_START <= e.forecast_date <= PLANNING_END
]

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

network_parser = ExcelParser('data/examples/Network_Config.xlsx', resolver)
products_dict = network_parser.parse_products()

inv_dict = {}
for entry in inv_snapshot.entries:
    product_id = resolver.resolve_product_id(entry.product_id) if resolver else entry.product_id
    inv_dict[(entry.location_id, product_id, 'ambient')] = entry.quantity

cost_structure.waste_cost_multiplier = 10.0

model_builder = SlidingWindowModel(
    nodes, unified_routes, forecast_obj, labor_calendar, cost_structure,
    products_dict, PLANNING_START, PLANNING_END, unified_truck_schedules,
    inv_dict, INVENTORY_SNAPSHOT,
    True, True, True
)

result = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05)

if not result.success:
    print(f"Solve failed: {result.termination_condition}")
    exit(1)

model = model_builder.model

print(f"\nObjective: ${result.objective_value:,.0f}\n")

# Check production at 6122
print("="*80)
print("PRODUCTION AT 6122 (Manufacturing)")
print("="*80)

total_production = 0
production_days = set()

for (node_id, prod, t) in model.production:
    if node_id == '6122':
        qty = value(model.production[node_id, prod, t])
        if qty > 0.01:
            total_production += qty
            production_days.add(t)
            print(f"  {t}: {prod[:35]:35s} {qty:>6.0f} units")

if total_production == 0:
    print("  ❌ ZERO PRODUCTION!")
    print("\n  This explains why 6130 has no arrivals!")
    print("  Without production, no goods ship to Lineage → 6130")
else:
    print(f"\n  Total production: {total_production:,.0f} units across {len(production_days)} days")

# Check shipments from 6122 to Lineage
print("\n" + "="*80)
print("SHIPMENTS: 6122 → Lineage")
print("="*80)

total_to_lineage = 0
for (origin, dest, prod, t, state) in model.in_transit:
    if origin == '6122' and dest == 'Lineage':
        qty = value(model.in_transit[origin, dest, prod, t, state])
        if qty > 0.01:
            total_to_lineage += qty
            print(f"  {t}: {prod[:35]:35s} {qty:>6.0f} units ({state})")

if total_to_lineage == 0:
    print("  ❌ NO SHIPMENTS TO LINEAGE!")
else:
    print(f"\n  Total to Lineage: {total_to_lineage:,.0f} units")

# Check shipments from Lineage to 6130
print("\n" + "="*80)
print("SHIPMENTS: Lineage → 6130")
print("="*80)

total_to_6130 = 0
for (origin, dest, prod, t, state) in model.in_transit:
    if origin == 'Lineage' and dest == '6130':
        qty = value(model.in_transit[origin, dest, prod, t, state])
        if qty > 0.01:
            total_to_6130 += qty
            print(f"  {t}: {prod[:35]:35s} {qty:>6.0f} units ({state})")

if total_to_6130 == 0:
    print("  ❌ NO ARRIVALS AT 6130!")
    print("\n  6130 can only use its 937 units ambient init_inv!")
    print("  With 14,154 units demand, model takes 13,217 shortage")
else:
    print(f"\n  Total arrivals at 6130: {total_to_6130:,.0f} units")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)

if total_production == 0:
    print("ROOT CAUSE: No production at 6122!")
    print("  → No shipments to Lineage")
    print("  → No arrivals at 6130")
    print("  → 6130 limited to 937 units init_inv for 14,154 demand")
    print("  → Sliding window rations ambient across 28 days")
    print("  → Day 1 gets 0 consumption (model conserves for later)")
else:
    print("Production exists - bug is elsewhere")
