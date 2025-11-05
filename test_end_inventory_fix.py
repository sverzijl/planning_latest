"""
VERIFICATION TEST: End-Inventory Fix

This script ACTUALLY SOLVES the model and verifies:
1. No post-horizon shipments in solution
2. End inventory significantly reduced
3. Material balance correct

This is what I SHOULD have done before claiming the fix worked.
"""

from datetime import datetime, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from src.models.location import LocationType

print("="*80)
print("END-INVENTORY FIX VERIFICATION (WITH ACTUAL SOLVE)")
print("="*80)

# Load data
print("\n1. Loading data...")
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

forecast, locations, routes, labor_cal, trucks, costs = parser.parse_all()

# Use 1-week horizon for faster testing
planning_start = datetime(2025, 10, 17).date()
planning_end = planning_start + timedelta(weeks=1)

# Build model
mfg = [loc for loc in locations if loc.type == LocationType.MANUFACTURING][0]
converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(mfg, locations, forecast)
unified_routes = converter.convert_routes(routes)
unified_trucks = converter.convert_truck_schedules(trucks, mfg.id)

products = create_test_products(
    sorted(set(e.product_id for e in forecast.entries
              if planning_start <= e.forecast_date <= planning_end))
)

print(f"\n2. Building model...")
print(f"   Horizon: {planning_start} to {planning_end}")

model = SlidingWindowModel(
    nodes=nodes,
    routes=unified_routes,
    forecast=forecast,
    products=products,
    labor_calendar=labor_cal,
    cost_structure=costs,
    start_date=planning_start,
    end_date=planning_end,
    truck_schedules=unified_trucks,
    allow_shortages=True,
    use_pallet_tracking=False  # Faster
)

print(f"\n3. SOLVING model...")
result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.02)

if not result.success:
    print(f"❌ SOLVE FAILED: {result.termination_condition}")
    exit(1)

print(f"✅ Solve succeeded: {result.termination_condition}")
print(f"   Objective: ${result.objective_value:,.2f}")
print(f"   Time: {result.solve_time_seconds:.1f}s")

# Extract solution
print(f"\n4. Extracting solution...")
solution = model.get_solution()

# VERIFICATION 1: Check post-horizon shipments
print(f"\n5. VERIFICATION: Post-Horizon Shipments")
print("-"*80)

post_horizon_count = 0
for shipment in solution.shipments:
    if shipment.delivery_date > planning_end:
        post_horizon_count += 1
        if post_horizon_count <= 3:
            print(f"   ❌ {shipment.origin} → {shipment.destination}: delivers {shipment.delivery_date}")

if post_horizon_count == 0:
    print("   ✅ NO post-horizon shipments")
else:
    print(f"   ❌ FOUND {post_horizon_count} post-horizon shipments - FIX FAILED!")

# VERIFICATION 2: Check end inventory
print(f"\n6. VERIFICATION: End-of-Horizon Inventory")
print("-"*80)

end_inventory_total = 0
if solution.inventory_state:
    for (node, prod, state, date), qty in solution.inventory_state.items():
        if date == planning_end:
            end_inventory_total += qty

print(f"   End inventory: {end_inventory_total:,.0f} units")

if end_inventory_total < 10000:
    print(f"   ✅ Reduced to acceptable level")
elif end_inventory_total < 20000:
    print(f"   ⚠️  Improved but still high")
else:
    print(f"   ❌ Still excessive (>{end_inventory_total:,.0f})")

# VERIFICATION 3: Material balance
print(f"\n7. VERIFICATION: Material Balance")
print("-"*80)

total_production = solution.total_production
total_consumed = sum(solution.demand_consumed.values()) if solution.demand_consumed else 0
total_shortage = solution.total_shortage_units

print(f"   Production: {total_production:,.0f}")
print(f"   Consumed: {total_consumed:,.0f}")
print(f"   Shortage: {total_shortage:,.0f}")
print(f"   End inventory: {end_inventory_total:,.0f}")

balance = total_production - (total_consumed + total_shortage) - end_inventory_total
print(f"   Balance (prod - demand - end_inv): {balance:,.0f}")

if abs(balance) < 1000:
    print(f"   ✅ Material balance correct")
else:
    print(f"   ⚠️  Unaccounted: {abs(balance):,.0f} (likely in-transit)")

# FINAL VERDICT
print(f"\n" + "="*80)
print("FINAL VERDICT")
print("="*80)

if post_horizon_count == 0 and end_inventory_total < 10000:
    print("\n✅ FIX VERIFIED:")
    print(f"   - No post-horizon shipments")
    print(f"   - End inventory reduced to {end_inventory_total:,.0f} units")
    print(f"\n→ SAFE TO COMMIT")
else:
    print("\n❌ FIX INCOMPLETE:")
    if post_horizon_count > 0:
        print(f"   - Still {post_horizon_count} post-horizon shipments")
    if end_inventory_total >= 10000:
        print(f"   - End inventory still {end_inventory_total:,.0f} units")
    print(f"\n→ DO NOT COMMIT - MORE INVESTIGATION NEEDED")
