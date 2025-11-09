"""Validate rolling window warmstart on 6-week (42 day) horizon.

This tests the CORRECT production planning workflow:
- Day 1: Solve Days 1-42 (6 weeks)
- Planner executes Day 1, records actuals
- Day 2: Solve Days 2-43 with warmstart from Day 1 for Days 2-42 (EXACT match)

Expected: 50-70% speedup on Day 2 vs Day 1
"""

from datetime import date, timedelta
import time

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.warmstart_utils import (
    extract_solution_for_warmstart,
    extract_warmstart_for_rolling_window,
)
from tests.conftest import create_test_products


print("="*80)
print("6-WEEK ROLLING WINDOW WARMSTART VALIDATION")
print("="*80)

# Parse data
print("\n📂 Loading data...")
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file=None,
)

forecast, locations, routes_list, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from src.models.truck_schedule import TruckScheduleCollection

manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manuf_loc = manufacturing_locations[0]

manufacturing_site = ManufacturingSite(
    id=manuf_loc.id,
    name=manuf_loc.name,
    storage_mode=manuf_loc.storage_mode,
    production_rate=getattr(manuf_loc, 'production_rate', 1400.0),
    daily_startup_hours=0.5,
    daily_shutdown_hours=0.25,
    default_changeover_hours=0.5,
    production_cost_per_unit=cost_structure.production_cost_per_unit,
)

truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

# Get products
product_ids = list(set(entry.product_id for entry in forecast.entries))
products_dict = create_test_products(product_ids)

# Convert to unified format
converter = LegacyToUnifiedConverter()
nodes, routes, unified_trucks = converter.convert_all(
    manufacturing_site=manufacturing_site,
    locations=locations,
    routes=routes_list,
    truck_schedules=truck_schedules_list,
    forecast=forecast,
)

print(f"   ✓ {len(nodes)} nodes, {len(routes)} routes, {len(products_dict)} products")

# Get forecast date range
forecast_start = min(e.forecast_date for e in forecast.entries)
forecast_end = max(e.forecast_date for e in forecast.entries)
print(f"   ✓ Forecast: {forecast_start} to {forecast_end}")

# Configuration
HORIZON_DAYS = 42  # 6 weeks
SOLVER_CONFIG = {
    'solver_name': 'appsi_highs',
    'time_limit_seconds': 600,  # 10 minutes for 6-week
    'mip_gap': 0.02,  # 2% gap (practical for large problems)
    'tee': False,
}

# Day 1: Full 6-week solve
print(f"\n{'='*80}")
print(f"DAY 1: COLD START (6-week horizon)")
print(f"{'='*80}")

day1_start = forecast_start
day1_end = day1_start + timedelta(days=HORIZON_DAYS - 1)
print(f"Planning horizon: {day1_start} to {day1_end} ({HORIZON_DAYS} days)")

model_day1 = UnifiedNodeModel(
    nodes=nodes,
    routes=routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    products=products_dict,
    start_date=day1_start,
    end_date=day1_end,
    truck_schedules=unified_trucks,
    use_batch_tracking=True,
    allow_shortages=True,
    enforce_shelf_life=True,
)

print(f"\n🚀 Solving Day 1 (cold start)...")
start_time = time.time()

result_day1 = model_day1.solve(**SOLVER_CONFIG)

day1_time = time.time() - start_time

if not result_day1.success:
    print(f"\n❌ Day 1 FAILED: {result_day1.termination_condition}")
    print("Cannot validate warmstart without successful Day 1 solve")
    exit(1)

print(f"\n✅ Day 1 solved successfully!")
print(f"   Time: {day1_time:.1f}s")
print(f"   Cost: ${result_day1.objective_value:,.0f}")
print(f"   Gap: {result_day1.gap:.2%}" if result_day1.gap else "")
print(f"   Variables: {result_day1.num_variables:,}")

# Extract complete solution
print(f"\n📦 Extracting Day 1 solution for warmstart...")
warmstart_full = extract_solution_for_warmstart(model_day1, verbose=True)

# Day 2: Rolling window (Days 2-43)
print(f"\n{'='*80}")
print(f"DAY 2: ROLLING WINDOW WITH WARMSTART")
print(f"{'='*80}")

day2_start = day1_start + timedelta(days=1)  # Oct 17
day2_end = day1_end + timedelta(days=1)      # Nov 27
print(f"Planning horizon: {day2_start} to {day2_end} ({HORIZON_DAYS} days)")

# Extract warmstart for overlapping window
# Day 1 was Oct 16-Nov 26
# Day 2 is  Oct 17-Nov 27
# Overlap:  Oct 17-Nov 26 (41 days - EXACT from Day 1!)
# New:      Nov 27 (1 day - solver decides)

print(f"\n🔄 Extracting warmstart for rolling window...")
print(f"   Day 1 window: {day1_start} to {day1_end}")
print(f"   Day 2 window: {day2_start} to {day2_end}")
print(f"   Overlap: {day2_start} to {day1_end} ({(day1_end - day2_start).days + 1} days)")
print(f"   New dates: {day2_end} (1 day)")

warmstart_day2 = extract_warmstart_for_rolling_window(
    warmstart_hints=warmstart_full,
    new_start_date=day2_start,
    new_end_date=day2_end,
    verbose=True
)

# Build Day 2 model
model_day2 = UnifiedNodeModel(
    nodes=nodes,
    routes=routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    products=products_dict,
    start_date=day2_start,
    end_date=day2_end,
    truck_schedules=unified_trucks,
    use_batch_tracking=True,
    allow_shortages=True,
    enforce_shelf_life=True,
)

print(f"\n🚀 Solving Day 2 (with warmstart)...")
start_time = time.time()

result_day2 = model_day2.solve(
    **SOLVER_CONFIG,
    use_warmstart=True,
    warmstart_hints=warmstart_day2,
)

day2_time = time.time() - start_time

if not result_day2.success:
    print(f"\n❌ Day 2 FAILED: {result_day2.termination_condition}")
    print("Warmstart may not be working properly")
    exit(1)

print(f"\n✅ Day 2 solved successfully!")
print(f"   Time: {day2_time:.1f}s")
print(f"   Cost: ${result_day2.objective_value:,.0f}")
print(f"   Gap: {result_day2.gap:.2%}" if result_day2.gap else "")

# Calculate speedup
speedup_pct = (1 - day2_time / day1_time) * 100 if day1_time > 0 else 0

print(f"\n{'='*80}")
print(f"SPEEDUP VALIDATION (6-WEEK HORIZON)")
print(f"{'='*80}")
print(f"Day 1 (cold start): {day1_time:>7.1f}s - ${result_day1.objective_value:,.0f}")
print(f"Day 2 (warmstart):  {day2_time:>7.1f}s - ${result_day2.objective_value:,.0f}")
print(f"Speedup:            {speedup_pct:>6.1f}% faster")

# Validation
if speedup_pct >= 30:
    print(f"\n✅ SUCCESS: Warmstart achieved {speedup_pct:.1f}% speedup (target: ≥30%)")
    print("   Rolling window warmstart is working correctly!")
elif speedup_pct >= 15:
    print(f"\n⚠️  MARGINAL: Warmstart achieved {speedup_pct:.1f}% speedup (below 30% target)")
    print("   Warmstart is working but performance is lower than expected")
else:
    print(f"\n❌ FAILED: Warmstart only achieved {speedup_pct:.1f}% speedup (<15%)")
    print("   Warmstart may not be working properly")
    exit(1)

# Cost consistency
cost_diff = abs(result_day2.objective_value - result_day1.objective_value)
cost_diff_pct = cost_diff / result_day1.objective_value * 100

print(f"\n💰 Cost Consistency:")
print(f"   Difference: ${cost_diff:,.0f} ({cost_diff_pct:.2f}%)")
if cost_diff_pct < 2.0:
    print(f"   ✓ Excellent consistency (<2%)")
elif cost_diff_pct < 5.0:
    print(f"   ✓ Good consistency (<5%)")
else:
    print(f"   ⚠️  Variation >5% (expected for different planning windows)")

# Warmstart quality metrics
overlap_days = (day1_end - day2_start).days + 1
overlap_pct = overlap_days / HORIZON_DAYS * 100

print(f"\n📊 Warmstart Quality:")
print(f"   Horizon: {HORIZON_DAYS} days")
print(f"   Overlap: {overlap_days} days ({overlap_pct:.1f}%)")
print(f"   New dates: 1 day (Day {HORIZON_DAYS})")
print(f"   Warmstart variables: {len(warmstart_day2):,}")

print(f"\n{'='*80}")
print(f"✨ 6-week rolling window validation complete!")
print(f"{'='*80}")
