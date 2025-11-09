#!/usr/bin/env python3
"""Check if production variable keys are created correctly."""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

# Convert
mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

# 1 day
start = date(2025, 10, 17)
end = start

product_ids = ['HELGAS GFREE MIXED GRAIN 500G']
products = create_test_products(product_ids)

print("="*80)
print("PRODUCTION VARIABLE KEY CHECK")
print("="*80)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

m = model.build_model()

print(f"\nProduction variables created:")
print(f"  Total: {len(list(m.production))}")

# Check specific key
node_id = '6122'
prod_id = 'HELGAS GFREE MIXED GRAIN 500G'
date_val = start

key = (node_id, prod_id, date_val)
print(f"\nChecking key: {key}")
print(f"  Exists in m.production: {key in m.production}")

if key in m.production:
    var = m.production[key]
    print(f"  Variable: {var}")
    print(f"  Domain: {var.domain}")
    print(f"  Bounds: [{var.lb}, {var.ub}]")

# Now check if this key would pass the conditional in material balance
nodes_dict = {n.id: n for n in nodes} if isinstance(nodes, list) else nodes
node = nodes_dict.get(node_id)

if node:
    can_produce = node.can_produce()
    prod_state = node.get_production_state() if can_produce else None

    print(f"\nNode {node_id} production capability:")
    print(f"  can_produce(): {can_produce}")
    print(f"  get_production_state(): {prod_state}")

    # Check the exact conditional
    check1 = node.can_produce()
    check2 = (node_id, prod_id, date_val) in m.production
    check3 = (node.get_production_state() == 'ambient') if can_produce else False

    print(f"\nConditional checks for material balance:")
    print(f"  node.can_produce(): {check1}")
    print(f"  (node_id, prod, t) in model.production: {check2}")
    print(f"  node.get_production_state() == 'ambient': {check3}")
    print(f"  ALL TRUE (should include in balance): {check1 and check2 and check3}")

    if check1 and check2 and check3:
        print(f"\n  ✓ Production SHOULD be included in material balance")
    else:
        print(f"\n  ✗ One of the checks failed - production won't be in balance")

print("="*80)
