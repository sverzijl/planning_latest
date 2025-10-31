"""Smoke test for pipeline inventory tracking refactor.

Verifies that the refactored model can build and solve.
"""
from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

print("=" * 80)
print("PIPELINE REFACTOR SMOKE TEST")
print("=" * 80)

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

# Simple 7-day test
start = min(e.forecast_date for e in forecast.entries)
end = start + timedelta(days=6)  # 1 week
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print(f"\nTest configuration:")
print(f"  Horizon: {start} to {end} ({(end - start).days + 1} days)")
print(f"  Products: {len(products)}")
print(f"  Routes: {len(unified_routes)}")

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

# Build model
print("\n" + "=" * 80)
print("Building model...")
print("=" * 80)
pyomo_model = model.build_model()

# Verify in_transit variables exist
if hasattr(pyomo_model, 'in_transit'):
    print(f"\n✅ in_transit variables created: {len(list(pyomo_model.in_transit))}")

    # Check date range
    departure_dates = set()
    for (origin, dest, prod, departure_date, state) in pyomo_model.in_transit:
        departure_dates.add(departure_date)

    min_departure = min(departure_dates)
    max_departure = max(departure_dates)
    print(f"  Departure date range: {min_departure} to {max_departure}")
    print(f"  Planning horizon: {start} to {end}")

    if max_departure <= end:
        print(f"  ✅ All in_transit variables within planning horizon")
    else:
        print(f"  ❌ FAIL: in_transit variables extend beyond horizon by {(max_departure - end).days} days")
else:
    print(f"\n❌ FAIL: in_transit variables not found")

# Verify shipment variables don't exist
if hasattr(pyomo_model, 'shipment'):
    print(f"\n❌ FAIL: shipment variables still exist (should be removed)")
else:
    print(f"\n✅ shipment variables removed (replaced with in_transit)")

# Solve
print("\n" + "=" * 80)
print("Solving model...")
print("=" * 80)
result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.01, tee=False)

print(f"\nSolve status: {result.termination_condition}, optimal={result.is_optimal()}")

if result.is_optimal():
    print(f"Objective value: ${result.objective_value:,.2f}")

    # Extract solution
    solution = model.extract_solution(pyomo_model)

    # Verify shipments_by_route extracted
    if hasattr(solution, 'shipments_by_route_product_date') or 'shipments_by_route_product_date' in solution:
        shipments = solution.get('shipments_by_route_product_date', {}) if isinstance(solution, dict) else getattr(solution, 'shipments_by_route_product_date', {})
        print(f"\n✅ Shipments extracted: {len(shipments)} routes")
    else:
        print(f"\n⚠️  Shipments not found in solution (may be OK if no flows)")

    print(f"\n" + "=" * 80)
    print("✅ SMOKE TEST PASSED")
    print("=" * 80)
else:
    print(f"\n" + "=" * 80)
    print(f"❌ SMOKE TEST FAILED: Solve not optimal")
    print(f"=" * 80)
