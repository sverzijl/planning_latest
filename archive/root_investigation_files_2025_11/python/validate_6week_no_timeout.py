"""Validate 6-week rolling window with extended time limit (no timeout).

This allows both Day 1 and Day 2 to solve to completion (within MIP gap)
so we can measure the actual warmstart speedup.

Configuration:
- Time limit: 1800s (30 minutes) - enough to solve to optimality
- MIP gap: 2% (practical tolerance)
- Full problem: 42 days, 5 products, 9 destinations
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
from pyomo.environ import value as pyo_value


print("="*80)
print("6-WEEK ROLLING WINDOW - NO TIMEOUT")
print("Extended time limit to measure true warmstart speedup")
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

product_ids = list(set(entry.product_id for entry in forecast.entries))
products_dict = create_test_products(product_ids)

converter = LegacyToUnifiedConverter()
nodes, routes, unified_trucks = converter.convert_all(
    manufacturing_site=manufacturing_site,
    locations=locations,
    routes=routes_list,
    truck_schedules=truck_schedules_list,
    forecast=forecast,
)

print(f"   ✓ {len(nodes)} nodes, {len(routes)} routes, {len(products_dict)} products")

forecast_start = min(e.forecast_date for e in forecast.entries)
print(f"   ✓ Forecast starts: {forecast_start}")

# Configuration - EXTENDED TIME LIMIT
HORIZON_DAYS = 42
SOLVER_CONFIG = {
    'solver_name': 'appsi_highs',
    'time_limit_seconds': 1800,  # 30 minutes - should be enough
    'mip_gap': 0.02,
    'tee': True,  # Show solver output to monitor progress
}

print(f"\n⚙️  Configuration:")
print(f"   Horizon: {HORIZON_DAYS} days (6 weeks)")
print(f"   Time limit: {SOLVER_CONFIG['time_limit_seconds']}s (30 minutes)")
print(f"   MIP gap: {SOLVER_CONFIG['mip_gap']:.1%}")
print(f"   Solver: {SOLVER_CONFIG['solver_name']}")

# DAY 1
print(f"\n{'='*80}")
print(f"DAY 1: COLD START")
print(f"{'='*80}")

day1_start = forecast_start
day1_end = day1_start + timedelta(days=HORIZON_DAYS - 1)
print(f"Horizon: {day1_start} to {day1_end}")

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
    initial_inventory=None,
)

print(f"\n🚀 Solving Day 1 (up to 30 minutes)...")
print(f"   (Solver output shown below)\n")

start_time = time.time()
result_day1 = model_day1.solve(**SOLVER_CONFIG)
day1_time = time.time() - start_time

print(f"\n" + "="*80)
if not result_day1.success:
    print(f"❌ Day 1 FAILED: {result_day1.termination_condition}")
    exit(1)

print(f"✅ Day 1 COMPLETE!")
print(f"   Time: {day1_time:.1f}s ({day1_time/60:.1f} minutes)")
print(f"   Cost: ${result_day1.objective_value:,.0f}")
print(f"   Gap: {result_day1.gap:.2%}" if result_day1.gap else "")
hit_limit_day1 = day1_time >= SOLVER_CONFIG['time_limit_seconds'] * 0.99
if hit_limit_day1:
    print(f"   ⚠️  Hit time limit")
print(f"="*80)

# Extract actuals and warmstart
print(f"\n📦 Extracting Day 1 solution...")
warmstart_full = extract_solution_for_warmstart(model_day1, verbose=False)

# Extract ending inventory
day1_ending_inventory = {}
pyomo_model = model_day1.model
if hasattr(pyomo_model, 'inventory_cohort'):
    for key in pyomo_model.inventory_cohort:
        node_id, product_id, state, prod_date, inv_date = key
        if inv_date == day1_start:
            try:
                qty = pyo_value(pyomo_model.inventory_cohort[key])
                if qty is not None and qty > 0.01:
                    inv_key = (node_id, product_id, state, prod_date)
                    day1_ending_inventory[inv_key] = day1_ending_inventory.get(inv_key, 0) + qty
            except:
                pass

print(f"   ✓ Warmstart: {len(warmstart_full):,} variables")
print(f"   ✓ Actuals: {len(day1_ending_inventory)} inventory cohorts")

# DAY 2
print(f"\n{'='*80}")
print(f"DAY 2: WITH WARMSTART + ACTUALS")
print(f"{'='*80}")

day2_start = day1_start + timedelta(days=1)
day2_end = day1_end + timedelta(days=1)
print(f"Horizon: {day2_start} to {day2_end}")

# Filter warmstart for rolling window
warmstart_day2 = extract_warmstart_for_rolling_window(
    warmstart_hints=warmstart_full,
    new_start_date=day2_start,
    new_end_date=day2_end,
    verbose=False
)

print(f"   Warmstart: {len(warmstart_day2):,} variables ({len(warmstart_day2)/len(warmstart_full)*100:.1f}% coverage)")
print(f"   Actuals: {len(day1_ending_inventory)} inventory cohorts")

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
    initial_inventory=day1_ending_inventory if day1_ending_inventory else None,
    inventory_snapshot_date=day1_start if day1_ending_inventory else None,
)

print(f"\n🚀 Solving Day 2 (up to 30 minutes)...")
print(f"   (Solver output shown below)\n")

start_time = time.time()
result_day2 = model_day2.solve(
    **SOLVER_CONFIG,
    use_warmstart=True,
    warmstart_hints=warmstart_day2,
)
day2_time = time.time() - start_time

print(f"\n" + "="*80)
if not result_day2.success:
    print(f"❌ Day 2 FAILED: {result_day2.termination_condition}")
    exit(1)

print(f"✅ Day 2 COMPLETE!")
print(f"   Time: {day2_time:.1f}s ({day2_time/60:.1f} minutes)")
print(f"   Cost: ${result_day2.objective_value:,.0f}")
print(f"   Gap: {result_day2.gap:.2%}" if result_day2.gap else "")
hit_limit_day2 = day2_time >= SOLVER_CONFIG['time_limit_seconds'] * 0.99
if hit_limit_day2:
    print(f"   ⚠️  Hit time limit")
print(f"="*80)

# Results
speedup_pct = (1 - day2_time / day1_time) * 100 if day1_time > 0 else 0

print(f"\n{'='*80}")
print(f"FINAL RESULTS")
print(f"{'='*80}")
print(f"\nDay 1 (cold start):        {day1_time:>7.1f}s ({day1_time/60:>5.1f} min) - ${result_day1.objective_value:,.0f} - {result_day1.gap:.2%} gap")
print(f"Day 2 (warmstart+actuals): {day2_time:>7.1f}s ({day2_time/60:>5.1f} min) - ${result_day2.objective_value:,.0f} - {result_day2.gap:.2%} gap")
print(f"\nSpeedup: {speedup_pct:>6.1f}% faster")

if hit_limit_day1 and hit_limit_day2:
    gap_improvement = (result_day1.gap - result_day2.gap) if result_day1.gap and result_day2.gap else 0
    print(f"\n⚠️  Both solves hit time limit - can't measure pure speedup")
    print(f"   However, warmstart improved gap: {result_day1.gap:.2%} → {result_day2.gap:.2%}")

    if gap_improvement > 0:
        print(f"   ✅ Warmstart helped: {gap_improvement:+.2%} better gap in same time")

    print(f"\n💡 To measure speedup: increase time_limit to 3600s (1 hour)")
elif hit_limit_day1 and not hit_limit_day2:
    print(f"\n✅ SUCCESS! Day 2 solved before time limit")
    print(f"   Warmstart enabled solution within time limit")
    print(f"   Speedup: {speedup_pct:.1f}% faster")
elif not hit_limit_day1 and not hit_limit_day2:
    if speedup_pct >= 30:
        print(f"\n✅ SUCCESS: {speedup_pct:.1f}% speedup (target: ≥30%)")
    elif speedup_pct >= 15:
        print(f"\n⚠️  MARGINAL: {speedup_pct:.1f}% speedup (below target)")
    else:
        print(f"\n❌ MINIMAL: {speedup_pct:.1f}% speedup")

print(f"\n{'='*80}")
print(f"Validation complete!")
print(f"{'='*80}")
