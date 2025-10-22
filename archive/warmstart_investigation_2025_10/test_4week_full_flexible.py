#!/usr/bin/env python3
"""Test: 4 Weeks Completely Flexible with Staleness Penalty

Tests if 4-week horizon with FULL flexibility is solvable with staleness penalty.

Binary Decisions:
- 4 weeks × 5 weekdays × 5 products = ~100 binary decisions
- vs 1-week flexible (50 decisions): 460s
- vs 6-week flexible (150 decisions): 636s timeout

Search Space: 2^100 ≈ 1.3×10^30
- 10^15 times larger than 1-week flexible (2^50)
- 10^54 times smaller than 6-week flexible (2^150)

With staleness penalty, expected: 500-900s (8-15 minutes)
Without staleness penalty, expected: Likely timeout
"""

import sys
from pathlib import Path
from datetime import date, timedelta
import time

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType

import pyomo.environ as pyo
from pyomo.contrib import appsi


def main():
    print("="*80)
    print("4-WEEK FULL FLEXIBILITY TEST")
    print("="*80)
    print("\nConfiguration: 4 weeks, NO pattern constraints, WITH staleness penalty")
    print("Binary decisions: ~100 (vs 50 for 1-week flex, 150 for 6-week flex)")
    print("Expected: 500-900s with staleness (vs 460s for 1-week flex)\n")

    # Load data
    print("="*80)
    print("LOADING DATA")
    print("="*80)

    parser = MultiFileParser(
        forecast_file="data/examples/Gluten Free Forecast - Latest.xlsm",
        network_file="data/examples/Network_Config.xlsx",
        inventory_file="data/examples/inventory.XLSX",
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure_base = parser.parse_all()

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
        default_changeover_hours=0.5, production_cost_per_unit=cost_structure_base.production_cost_per_unit,
    )

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    inventory_snapshot = parser.parse_inventory(snapshot_date=None)
    initial_inventory = inventory_snapshot.to_optimization_dict() if inventory_snapshot else None
    inventory_date = inventory_snapshot.snapshot_date if inventory_snapshot else None

    # 4-week horizon (not 6!)
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=4*7 - 1)  # 4 weeks

    print(f"\nConfiguration:")
    print(f"  Horizon: 4 weeks ({(end_date - start_date).days + 1} days)")
    print(f"  Flexibility: 100% (no pattern constraints)")
    print(f"  Staleness penalty: $0.05/unit/day")

    products = sorted(set(e.product_id for e in forecast.entries))
    manufacturing_nodes_list = [n.id for n in nodes if n.capabilities.can_manufacture]

    # Count production days
    dates_range = []
    current = start_date
    while current <= end_date:
        dates_range.append(current)
        current += timedelta(days=1)

    prod_days = sum(1 for d in dates_range if d.weekday() < 5)
    print(f"  Production days: {prod_days}")
    print(f"  Products: {len(products)}")
    print(f"  Binary decisions: ~{prod_days * len(products)}")

    # Configure with staleness penalty
    cost_structure = cost_structure_base.model_copy()
    cost_structure.freshness_incentive_weight = 0.05  # $0.05 staleness penalty

    # Create model (NO pattern - full flexibility)
    print("\n" + "="*80)
    print("CREATING MODEL (FULL FLEXIBILITY)")
    print("="*80)

    model_obj = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=initial_inventory,
        inventory_snapshot_date=inventory_date,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
        force_all_skus_daily=False,  # CRITICAL: Allow binary SKU selection
    )

    # Build model (no additional pattern constraints - pure binary flexibility!)
    print("\nBuilding model...")
    build_start = time.time()
    model = model_obj.build_model()
    build_time = time.time() - build_start
    print(f"Model built in {build_time:.1f}s")

    # Count variables
    def count_variables(m):
        binary = sum(1 for v in m.component_data_objects(ctype=pyo.Var, active=True) if v.is_binary())
        integer = sum(1 for v in m.component_data_objects(ctype=pyo.Var, active=True) if v.is_integer())
        continuous = sum(1 for v in m.component_data_objects(ctype=pyo.Var, active=True) if v.is_continuous())
        return binary, integer, continuous

    binary_count, integer_count, continuous_count = count_variables(model)

    print(f"\nVariable counts:")
    print(f"  Binary: {binary_count:,}")
    print(f"  Integer: {integer_count:,}")
    print(f"  Continuous: {continuous_count:,}")
    print(f"\nNote: No pattern constraints - ALL binary decisions are free")

    # Solve
    print("\n" + "="*80)
    print("SOLVING")
    print("="*80)

    solver = appsi.solvers.Highs()
    solver.config.time_limit = 900  # 15 minutes (give it more time)
    solver.config.mip_gap = 0.03
    solver.config.stream_solver = False

    print(f"\nSolver configuration:")
    print(f"  Solver: HiGHS")
    print(f"  Time limit: 900s (15 minutes)")
    print(f"  MIP gap: 3%")
    print(f"  Staleness: $0.05/unit/day")

    print("\nSolving...")
    solve_start = time.time()

    result = solver.solve(model)

    solve_time = time.time() - solve_start

    # Extract results
    cost = pyo.value(model.obj)
    gap = None
    if hasattr(result, 'best_feasible_objective') and hasattr(result, 'best_objective_bound'):
        best_feas = result.best_feasible_objective
        best_bound = result.best_objective_bound
        if best_feas and best_bound and best_feas != 0:
            gap = abs((best_feas - best_bound) / best_feas)

    print(f"\n{'='*80}")
    print("RESULTS")
    print(f"{'='*80}")

    print(f"\n4-Week Full Flexibility:")
    print(f"  Solve time: {solve_time:.1f}s ({solve_time/60:.1f} minutes)")
    print(f"  Cost: ${cost:,.2f}")
    if gap is not None:
        print(f"  Gap: {gap*100:.3f}%")
    print(f"  Status: {result.termination_condition}")

    # Compare to baselines
    print(f"\n{'='*80}")
    print("COMPARISON TO OTHER APPROACHES")
    print(f"{'='*80}")

    print(f"\n4-week horizon options:")
    print(f"  Full flexibility (this test): {solve_time:.0f}s")

    print(f"\n6-week horizon options (for reference):")
    print(f"  Full pattern: 21.5s")
    print(f"  1-week flexible + $0.20: 433.5s")
    print(f"  2-week flexible: 609s (timeout)")

    # Recommendation
    print(f"\n{'='*80}")
    print("RECOMMENDATION")
    print(f"{'='*80}")

    if solve_time < 300:  # 5 minutes
        print(f"\n🎉 EXCELLENT: 4-week full flexibility is PRACTICAL!")
        print(f"\nBenefits:")
        print(f"  - Solve time: {solve_time:.0f}s ({solve_time/60:.1f} minutes)")
        print(f"  - 100% flexibility across entire horizon")
        print(f"  - Staleness penalty ensures FIFO behavior")
        print(f"\n✅ RECOMMENDED: Use 4-week full flexible for medium-term planning")
    elif solve_time < 600:  # 10 minutes
        print(f"\n✓  ACCEPTABLE: 4-week full flexibility is feasible")
        print(f"\nPerformance:")
        print(f"  - Solve time: {solve_time:.0f}s ({solve_time/60:.1f} minutes)")
        print(f"  - May be acceptable depending on planning cadence")
        print(f"\nDecision: Use if full flexibility is valuable")
    else:
        print(f"\n⚠️  TOO SLOW: 4-week full flexibility still challenging")
        print(f"\nResults:")
        print(f"  - Solve time: {solve_time:.0f}s (exceeded 10 minutes)")
        print(f"\nOptions:")
        print(f"  1. Use 4-week horizon with 1-week flexible pattern")
        print(f"  2. Use 6-week full pattern (21.5s)")
        print(f"  3. Use 6-week with 1-week flexible (433s)")

    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}")

    return 0


if __name__ == "__main__":
    exit(main())
