"""Diagnose: Why only Mix Grain showing in UI?

Check if model produces multiple products or just one.
"""
from datetime import date, timedelta
from pyomo.core.base import value

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

try:
    initial_inventory = parser.parse_inventory()
    inventory_snapshot_date = initial_inventory.snapshot_date
except:
    initial_inventory = None
    inventory_snapshot_date = min(e.forecast_date for e in forecast.entries)

start = inventory_snapshot_date
end = start + timedelta(weeks=4)
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print("=" * 80)
print("PRODUCT PRODUCTION ANALYSIS")
print("=" * 80)

print(f"\nProducts in forecast: {len(product_ids)}")
for pid in product_ids:
    print(f"  - {pid}")

# Build and solve model
model_wrapper = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks,
    initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
    inventory_snapshot_date=inventory_snapshot_date,
    allow_shortages=True, use_pallet_tracking=True, use_truck_pallet_tracking=True
)

result = model_wrapper.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.02, tee=False)
solution = model_wrapper.get_solution()

print(f"\nSolve complete: {result.termination_condition}")
print(f"Total production: {solution['total_production']:,.0f} units")

# Check production by product
print(f"\n" + "=" * 80)
print("PRODUCTION BY PRODUCT")
print("=" * 80)

production_by_product = {}
for (node_id, prod, date), qty in solution['production_by_date_product'].items():
    production_by_product[prod] = production_by_product.get(prod, 0) + qty

for prod in sorted(production_by_product.keys()):
    qty = production_by_product[prod]
    pct = (qty / solution['total_production']) * 100 if solution['total_production'] > 0 else 0
    print(f"  {prod}: {qty:,.0f} units ({pct:.1f}%)")

# Check demand by product
print(f"\n" + "=" * 80)
print("DEMAND BY PRODUCT")
print("=" * 80)

demand_by_product = {}
for (node, prod, date), qty in model_wrapper.demand.items():
    demand_by_product[prod] = demand_by_product.get(prod, 0) + qty

total_demand = sum(demand_by_product.values())
for prod in sorted(demand_by_product.keys()):
    qty = demand_by_product[prod]
    pct = (qty / total_demand) * 100 if total_demand > 0 else 0
    print(f"  {prod}: {qty:,.0f} units ({pct:.1f}%)")

# Check production_batches
print(f"\n" + "=" * 80)
print("PRODUCTION BATCHES IN SOLUTION")
print("=" * 80)

batches = solution.get('production_batches', [])
print(f"Total batches: {len(batches)}")

products_in_batches = set(b['product'] for b in batches)
print(f"Products in production_batches: {len(products_in_batches)}")
for prod in sorted(products_in_batches):
    print(f"  - {prod}")

# Conclusion
print(f"\n" + "=" * 80)
print("DIAGNOSIS")
print("=" * 80)

if len(production_by_product) == 1:
    print(f"❌ MODEL ISSUE: Only producing 1 product!")
    print(f"   Model should produce all {len(product_ids)} products to meet demand")
elif len(production_by_product) == len(product_ids):
    print(f"✅ MODEL OK: Producing all {len(product_ids)} products")
    if len(products_in_batches) == 1:
        print(f"❌ UI ISSUE: production_batches only has 1 product!")
    else:
        print(f"✅ SOLUTION OK: All products in production_batches")
