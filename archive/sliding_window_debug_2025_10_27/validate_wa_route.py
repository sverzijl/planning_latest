"""Validate WA route: Manufacturing → Lineage (frozen) → 6130 (thawed)."""
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

model_wrapper = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks,
    initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
    inventory_snapshot_date=inventory_snapshot_date,
    allow_shortages=True, use_pallet_tracking=True, use_truck_pallet_tracking=True
)

print("=" * 80)
print("WA ROUTE VALIDATION")
print("=" * 80)

result = model_wrapper.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.02, tee=False)
solution = model_wrapper.get_solution()

print(f"\nSolve complete:")
print(f"  Status: {result.termination_condition}")
print(f"  Solve time: {result.solve_time_seconds:.1f}s")
print(f"  Fill rate: {solution['fill_rate']*100:.1f}%")

# Check WA route flows
print(f"\n" + "=" * 80)
print(f"WA ROUTE ANALYSIS")
print(f"=" * 80)

# Extract flows
freeze_flows = solution.get('freeze_flows', {})
thaw_flows = solution.get('thaw_flows', {})

# Freeze at Lineage
freeze_at_lineage = sum(qty for (node, prod, date_val), qty in freeze_flows.items() if node == 'Lineage')
print(f"\nFreeze flows at Lineage: {freeze_at_lineage:,.0f} units")

# Thaw at 6130 (WA)
thaw_at_6130 = sum(qty for (node, prod, date_val), qty in thaw_flows.items() if node == '6130')
print(f"Thaw flows at 6130 (WA): {thaw_at_6130:,.0f} units")

# Check demand at 6130
demand_at_6130 = sum(qty for (node, prod, date_val), qty in model_wrapper.demand.items() if node == '6130')
print(f"Demand at 6130: {demand_at_6130:,.0f} units")

# Check if shortage at 6130
if 'shortages' in solution:
    shortage_at_6130 = sum(qty for (node, prod, date_val), qty in solution['shortages'].items() if node == '6130')
    print(f"Shortage at 6130: {shortage_at_6130:,.0f} units")
    fill_rate_6130 = (1 - shortage_at_6130/demand_at_6130)*100 if demand_at_6130 > 0 else 100
    print(f"Fill rate at 6130: {fill_rate_6130:.1f}%")

# Validation
print(f"\n" + "=" * 80)
print(f"WA ROUTE VALIDATION:")
print(f"=" * 80)

if thaw_at_6130 > 0:
    print(f"✅ PASS: 6130 receives thawed product ({thaw_at_6130:,.0f} units)")
else:
    print(f"⚠️  WARNING: No thaw flows at 6130")

if freeze_at_lineage > 0:
    print(f"✅ PASS: Lineage frozen buffer is used ({freeze_at_lineage:,.0f} units)")
else:
    print(f"⚠️  INFO: Lineage frozen buffer not used (may use direct ambient route)")

if demand_at_6130 > 0 and shortage_at_6130 / demand_at_6130 < 0.15:
    print(f"✅ PASS: WA demand satisfied (fill rate: {fill_rate_6130:.1f}%)")
else:
    print(f"❌ FAIL: WA demand not satisfied adequately")

print(f"\n✅ WA route validation complete!")
