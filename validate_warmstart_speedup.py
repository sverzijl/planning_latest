"""Quick validation that warmstart provides speedup.

This script runs a minimal test (3 days) to validate warmstart works.
"""

from datetime import date
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.daily_rolling_solver import DailyRollingSolver

print("="*80)
print("WARMSTART SPEEDUP VALIDATION")
print("="*80)

# Load data
print("\n📂 Loading data...")
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX',
)

forecast, locations, routes_list, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()
print("   ✓ Data loaded")

# Create components
print("\n🔨 Creating optimization components...")
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from src.models.truck_schedule import TruckScheduleCollection

manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manuf_loc = manufacturing_locations[0]

manufacturing_site = ManufacturingSite(
    id=manuf_loc.id,
    name=manuf_loc.name,
    storage_mode=manuf_loc.storage_mode,
    production_rate=manuf_loc.production_rate if hasattr(manuf_loc, 'production_rate') and manuf_loc.production_rate else 1400.0,
    daily_startup_hours=0.5,
    daily_shutdown_hours=0.25,
    default_changeover_hours=0.5,
    production_cost_per_unit=cost_structure.production_cost_per_unit,
)

truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

# Convert to unified format
converter = LegacyToUnifiedConverter()
nodes, routes, unified_trucks = converter.convert_all(
    manufacturing_site=manufacturing_site,
    locations=locations,
    routes=routes_list,
    truck_schedules=truck_schedules_list,
    forecast=forecast,
)
print(f"   ✓ {len(nodes)} nodes, {len(routes)} routes")

# Extract products from forecast
product_ids = list(set(entry.product_id for entry in forecast.entries))
from tests.conftest import create_test_products
products_dict = create_test_products(product_ids)  # Already returns dict[str, Product]

# Setup solver with FAST configuration
print("\n⚙️  Configuring solver (fast settings for validation)...")
solver = DailyRollingSolver(
    nodes=nodes,
    routes=routes,
    base_forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    products=products_dict,
    truck_schedules=unified_trucks,
    horizon_days=14,  # 2 weeks (faster than 4 weeks)
    solver_name='appsi_highs',  # Required for warmstart
    time_limit_seconds=180,  # 3 minutes max
    mip_gap=0.03,  # 3% gap (relaxed for speed)
    use_batch_tracking=True,
    allow_shortages=False,
    enforce_shelf_life=True,
)
print("   ✓ Configured: 2-week horizon, 3% gap, 3min limit")

# Get actual forecast date range
forecast_start = min(e.forecast_date for e in forecast.entries)
forecast_end = max(e.forecast_date for e in forecast.entries)
print(f"   Forecast range: {forecast_start} to {forecast_end}")

# Solve 3 days starting from actual forecast start
print("\n🚀 Solving 3 days to validate warmstart...")
print("   Day 1: Cold start (baseline)")
print("   Days 2-3: Warmstart (should be faster)")

results = solver.solve_sequence(
    start_date=forecast_start,
    num_days=3,
    verbose=False  # Quiet for clean output
)

# Analyze results
print("\n" + "="*80)
print("VALIDATION RESULTS")
print("="*80)

if not results.all_successful:
    print("\n❌ FAILED: Not all solves succeeded")
    for r in results.daily_results:
        status = "✓" if r.success else "✗"
        print(f"   Day {r.day_number}: {status} {r.termination_condition}")
    exit(1)

# Check speedup
day1 = results.daily_results[0]
day2 = results.daily_results[1]
day3 = results.daily_results[2]

print(f"\n📊 Solve Times:")
print(f"   Day 1 (cold start): {day1.solve_time:>6.1f}s - ${day1.objective_value:,.0f}")
print(f"   Day 2 (warmstart):  {day2.solve_time:>6.1f}s - ${day2.objective_value:,.0f}")
print(f"   Day 3 (warmstart):  {day3.solve_time:>6.1f}s - ${day3.objective_value:,.0f}")

# Calculate speedup
if day2.warmstart_speedup and day3.warmstart_speedup:
    speedup_day2_pct = (1 - day2.warmstart_speedup) * 100
    speedup_day3_pct = (1 - day3.warmstart_speedup) * 100
    avg_speedup_pct = (speedup_day2_pct + speedup_day3_pct) / 2

    print(f"\n⚡ Warmstart Speedup:")
    print(f"   Day 2: {speedup_day2_pct:+.1f}% faster")
    print(f"   Day 3: {speedup_day3_pct:+.1f}% faster")
    print(f"   Average: {avg_speedup_pct:+.1f}% faster")

    # Validation
    if avg_speedup_pct >= 20:
        print(f"\n✅ SUCCESS: Warmstart achieved {avg_speedup_pct:.1f}% speedup (target: ≥20%)")
        print("   Warmstart is working correctly!")
    elif avg_speedup_pct >= 10:
        print(f"\n⚠️  MARGINAL: Warmstart achieved {avg_speedup_pct:.1f}% speedup (below 20% target)")
        print("   Warmstart is working but performance is lower than expected")
    else:
        print(f"\n❌ FAILED: Warmstart only achieved {avg_speedup_pct:.1f}% speedup (<10%)")
        print("   Warmstart may not be working properly")
        exit(1)
else:
    print("\n⚠️  WARNING: Could not calculate warmstart speedup")
    if day2.used_warmstart:
        print("   Warmstart was used but speedup metric not available")
    else:
        print("   Warmstart was not used!")
        exit(1)

# Cost consistency
costs = [r.objective_value for r in results.daily_results]
cost_var = (max(costs) - min(costs)) / min(costs) * 100
print(f"\n💰 Cost Consistency:")
print(f"   Variation: {cost_var:.2f}%")
if cost_var < 1.0:
    print(f"   ✓ Excellent consistency (<1%)")
elif cost_var < 5.0:
    print(f"   ✓ Good consistency (<5%)")
else:
    print(f"   ⚠️  High variation (>{5}%)")

print("\n" + "="*80)
print("✨ Validation complete!")
print("="*80)
