"""Simplified warmstart validation using existing test infrastructure.

This uses the same approach as test_integration_ui_workflow.py to ensure
compatibility and validate warmstart speedup.
"""

from datetime import date, timedelta
from pathlib import Path
import time

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.warmstart_utils import extract_solution_for_warmstart, shift_warmstart_hints
from tests.conftest import create_test_products


print("="*80)
print("WARMSTART SPEEDUP VALIDATION (SIMPLIFIED)")
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

# Get product IDs from forecast
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

# Convert to unified format
converter = LegacyToUnifiedConverter()
nodes, routes, unified_trucks = converter.convert_all(
    manufacturing_site=manufacturing_site,
    locations=locations,
    routes=routes_list,
    truck_schedules=truck_schedules_list,
    forecast=forecast,
)

print(f"   ✓ {len(nodes)} nodes, {len(routes)} routes, {len(products)} products")

# Get forecast date range
forecast_start = min(e.forecast_date for e in forecast.entries)
forecast_end = max(e.forecast_date for e in forecast.entries)
print(f"   ✓ Forecast: {forecast_start} to {forecast_end}")

# Define test window (2 weeks for speed)
test_start = forecast_start
test_end = test_start + timedelta(days=13)  # 2 weeks

print(f"\n{'='*80}")
print(f"DAY 1: COLD START (Baseline)")
print(f"{'='*80}")
print(f"Planning horizon: {test_start} to {test_end}")

# Day 1: Cold start
model_day1 = UnifiedNodeModel(
    nodes=nodes,
    routes=routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    products=products,
    start_date=test_start,
    end_date=test_end,
    truck_schedules=unified_trucks,
    use_batch_tracking=True,
    allow_shortages=True,  # Allow shortages to ensure feasibility
    enforce_shelf_life=True,
)

start_time = time.time()
result_day1 = model_day1.solve(
    solver_name='appsi_highs',
    time_limit_seconds=180,
    mip_gap=0.03,
    tee=False,
    use_warmstart=False,  # Cold start
)
day1_time = time.time() - start_time

if not result_day1.success:
    print(f"\n❌ Day 1 FAILED: {result_day1.termination_condition}")
    print("Cannot validate warmstart without successful Day 1 solve")
    exit(1)

print(f"\n✅ Day 1 solved successfully!")
print(f"   Time: {day1_time:.1f}s")
print(f"   Cost: ${result_day1.objective_value:,.0f}")
print(f"   Gap: {result_day1.gap:.2%}" if result_day1.gap else "")

# Extract warmstart
print(f"\n📦 Extracting warmstart from Day 1 solution...")
warmstart_day1 = extract_solution_for_warmstart(model_day1, verbose=True)

# Day 2: Shift forward by 1 day
print(f"\n{'='*80}")
print(f"DAY 2: WITH WARMSTART")
print(f"{'='*80}")

day2_start = test_start + timedelta(days=1)
day2_end = test_end + timedelta(days=1)
print(f"Planning horizon: {day2_start} to {day2_end} (shifted +1 day)")

# Shift warmstart hints
warmstart_day2 = shift_warmstart_hints(
    warmstart_hints=warmstart_day1,
    shift_days=1,
    new_start_date=day2_start,
    new_end_date=day2_end,
    verbose=True
)

# Build and solve Day 2 with warmstart
model_day2 = UnifiedNodeModel(
    nodes=nodes,
    routes=routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    products=products,
    start_date=day2_start,
    end_date=day2_end,
    truck_schedules=unified_trucks,
    use_batch_tracking=True,
    allow_shortages=True,  # Allow shortages to ensure feasibility
    enforce_shelf_life=True,
)

start_time = time.time()
result_day2 = model_day2.solve(
    solver_name='appsi_highs',
    time_limit_seconds=180,
    mip_gap=0.03,
    tee=False,
    use_warmstart=True,  # WITH WARMSTART
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
print(f"SPEEDUP VALIDATION")
print(f"{'='*80}")
print(f"Day 1 (cold start): {day1_time:>6.1f}s - ${result_day1.objective_value:,.0f}")
print(f"Day 2 (warmstart):  {day2_time:>6.1f}s - ${result_day2.objective_value:,.0f}")
print(f"Speedup:            {speedup_pct:>5.1f}% faster")

# Validation
if speedup_pct >= 20:
    print(f"\n✅ SUCCESS: Warmstart achieved {speedup_pct:.1f}% speedup (target: ≥20%)")
    print("   Warmstart is working correctly!")
elif speedup_pct >= 10:
    print(f"\n⚠️  MARGINAL: Warmstart achieved {speedup_pct:.1f}% speedup (below 20% target)")
    print("   Warmstart is working but performance is lower than expected")
else:
    print(f"\n❌ FAILED: Warmstart only achieved {speedup_pct:.1f}% speedup (<10%)")
    print("   Warmstart may not be working properly")
    exit(1)

# Cost consistency
cost_diff = abs(result_day2.objective_value - result_day1.objective_value)
cost_diff_pct = cost_diff / result_day1.objective_value * 100

print(f"\n💰 Cost Consistency:")
print(f"   Difference: ${cost_diff:,.0f} ({cost_diff_pct:.2f}%)")
if cost_diff_pct < 1.0:
    print(f"   ✓ Excellent consistency (<1%)")
elif cost_diff_pct < 5.0:
    print(f"   ✓ Good consistency (<5%)")
else:
    print(f"   ⚠️  High variation (>{5}%)")

print(f"\n{'='*80}")
print(f"✨ Warmstart validation complete!")
print(f"{'='*80}")
