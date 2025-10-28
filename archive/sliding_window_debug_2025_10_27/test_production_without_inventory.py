"""Test that model produces when no initial inventory (SHOULD FAIL before fix)."""
from datetime import date, timedelta
from pyomo.core.base import value
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

print("=" * 80)
print("TEST: Production Without Initial Inventory (FAILING TEST)")
print("=" * 80)

# Parse
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

# 2-day test
start = min(e.forecast_date for e in forecast.entries)
end = start + timedelta(days=1)
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

model_wrapper = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,  # NO inventory!
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

# Solve
result = model_wrapper.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05, tee=False)
solved_model = model_wrapper.model

# Extract values from SOLVED model using get_solution() method
solution = model_wrapper.get_solution()
total_prod = solution.get('total_production', 0)
total_shortage = solution.get('total_shortage_units', 0)
fill_rate = solution.get('fill_rate', 0)
total_demand = sum(model_wrapper.demand.values())

print(f"\nResults:")
print(f"  Demand: {total_demand:,.0f} units")
print(f"  Production: {total_prod:,.0f} units")
print(f"  Shortage: {total_shortage:,.0f} units")
print(f"  Fill rate: {fill_rate*100:.1f}%")

# TEST ASSERTIONS
print(f"\n" + "=" * 80)
print(f"TEST RESULTS:")
print(f"=" * 80)

# Without initial inventory, must either produce or take shortage
test_passed = True

if total_prod == 0 and total_shortage == 0:
    print(f"\n❌ FAIL: Material balance violated!")
    print(f"   Cannot satisfy demand without production or shortage!")
    test_passed = False

if total_prod > 0:
    print(f"\n✅ PASS: Model is producing ({total_prod:,.0f} units)")

if total_shortage > 0 and total_prod == 0:
    print(f"\n⚠️  CONDITIONAL PASS: Taking shortage instead of producing")
    print(f"   (This is valid if shortage penalty < production cost)")

# Check material balance via fill rate (more reliable)
if fill_rate < 0.85:
    print(f"\n❌ FAIL: Fill rate {fill_rate*100:.1f}% < 85%!")
    test_passed = False
else:
    print(f"\n✅ PASS: Fill rate {fill_rate*100:.1f}% >= 85%")

if test_passed:
    print(f"\n✅ TEST PASSED")
else:
    print(f"\n❌ TEST FAILED")
    print(f"\nThis test should FAIL before the fix is applied.")
    print(f"After fixing the departure date loop bug, it should PASS.")
