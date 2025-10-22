#!/usr/bin/env python3
"""Test: 4-Week Pattern Warmstart for 4-Week Full Flexible

Strategy:
1. Solve 4-week FULL PATTERN (~20s) - get good feasible solution
2. Extract solution (production decisions, inventory, etc.)
3. Use as warmstart for 4-week FULL FLEXIBLE
4. Compare: Cold start (905s) vs Warmstart (hopefully <600s)

MIP Theory: Good warmstart provides incumbent solution that prunes branch-and-bound
tree, reducing nodes explored and improving convergence.
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


def build_4week_pattern_model(model_obj, products, weekday_dates_lists, manufacturing_nodes_list):
    """Build 4-week full pattern model."""
    model = model_obj.build_model()

    # Create pattern variables for ALL 4 weeks
    pattern_index = [(prod, wd) for prod in products for wd in range(5)]
    model.product_weekday_pattern = pyo.Var(pattern_index, within=pyo.Binary)

    # Link ALL production dates to pattern
    model.weekly_pattern_linking = pyo.ConstraintList()
    for node_id in manufacturing_nodes_list:
        for product in products:
            for weekday_idx in range(5):
                for date_val in weekday_dates_lists[weekday_idx]:
                    if (node_id, product, date_val) in model.product_produced:
                        model.weekly_pattern_linking.add(
                            model.product_produced[node_id, product, date_val] ==
                            model.product_weekday_pattern[product, weekday_idx]
                        )

    # Deactivate all changeover constraints (pattern handles it)
    if hasattr(model, 'num_products_counting_con'):
        for idx in model.num_products_counting_con:
            model.num_products_counting_con[idx].deactivate()

    return model


def extract_warmstart(pattern_model, flexible_model):
    """Extract warmstart values from pattern solution for flexible model.

    Maps variables from pattern model to flexible model:
    - Binary product_produced values
    - Continuous production quantities
    - Inventory levels
    """
    count = 0

    # Extract binary production decisions
    if hasattr(pattern_model, 'product_produced'):
        for idx in pattern_model.product_produced:
            val = pyo.value(pattern_model.product_produced[idx])
            if val is not None and idx in flexible_model.product_produced:
                # Set value directly on variable
                flexible_model.product_produced[idx].set_value(round(val))
                count += 1

    # Extract production quantities
    if hasattr(pattern_model, 'production'):
        for idx in pattern_model.production:
            val = pyo.value(pattern_model.production[idx])
            if val is not None and idx in flexible_model.production:
                flexible_model.production[idx].set_value(val)
                count += 1

    # Extract inventory cohorts
    if hasattr(pattern_model, 'inventory_cohort'):
        for idx in pattern_model.inventory_cohort:
            val = pyo.value(pattern_model.inventory_cohort[idx])
            if val is not None and idx in flexible_model.inventory_cohort:
                flexible_model.inventory_cohort[idx].set_value(val)
                count += 1

    # Extract shipments
    if hasattr(pattern_model, 'shipment_cohort'):
        for idx in pattern_model.shipment_cohort:
            val = pyo.value(pattern_model.shipment_cohort[idx])
            if val is not None and idx in flexible_model.shipment_cohort:
                flexible_model.shipment_cohort[idx].set_value(val)
                count += 1

    return count


def main():
    print("="*80)
    print("4-WEEK PATTERN WARMSTART TEST")
    print("="*80)
    print("\nStrategy: Solve pattern fast → Use as warmstart for full flexible")
    print("Expected: 905s cold start → 360-540s with warmstart (30-40% faster)\n")

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

    # 4-week horizon
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=4*7 - 1)

    products = sorted(set(e.product_id for e in forecast.entries))
    manufacturing_nodes_list = [n.id for n in nodes if n.capabilities.can_manufacture]

    # Build date lists
    dates_range = []
    current = start_date
    while current <= end_date:
        dates_range.append(current)
        current += timedelta(days=1)

    weekday_dates_lists = {i: [] for i in range(5)}
    for date_val in dates_range:
        weekday = date_val.weekday()
        labor_day = labor_calendar.get_labor_day(date_val)
        if weekday < 5 and labor_day and labor_day.is_fixed_day:
            weekday_dates_lists[weekday].append(date_val)

    # Configure with staleness penalty
    cost_structure = cost_structure_base.model_copy()
    cost_structure.freshness_incentive_weight = 0.05

    # PHASE 1: Solve 4-week pattern
    print("\n" + "="*80)
    print("PHASE 1: SOLVE 4-WEEK FULL PATTERN")
    print("="*80)

    print("\nCreating pattern model...")
    pattern_model_obj = UnifiedNodeModel(
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
        force_all_skus_daily=False,
    )

    print("\nBuilding pattern model...")
    pattern_build_start = time.time()
    pattern_model = build_4week_pattern_model(pattern_model_obj, products, weekday_dates_lists, manufacturing_nodes_list)
    pattern_build_time = time.time() - pattern_build_start
    print(f"Pattern model built in {pattern_build_time:.1f}s")

    print("\nSolving pattern model...")
    pattern_solver = appsi.solvers.Highs()
    pattern_solver.config.time_limit = 300  # 5 minutes should be plenty
    pattern_solver.config.mip_gap = 0.03
    pattern_solver.config.stream_solver = False

    pattern_solve_start = time.time()
    pattern_result = pattern_solver.solve(pattern_model)
    pattern_solve_time = time.time() - pattern_solve_start

    pattern_cost = pyo.value(pattern_model.obj)
    print(f"\nPattern solution:")
    print(f"  Solve time: {pattern_solve_time:.1f}s")
    print(f"  Cost: ${pattern_cost:,.2f}")
    print(f"  Status: {pattern_result.termination_condition}")

    # PHASE 2: Build 4-week full flexible model
    print("\n" + "="*80)
    print("PHASE 2: BUILD 4-WEEK FULL FLEXIBLE MODEL")
    print("="*80)

    print("\nCreating full flexible model...")
    flexible_model_obj = UnifiedNodeModel(
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
        force_all_skus_daily=False,  # No pattern - full flexibility
    )

    print("\nBuilding flexible model...")
    flexible_build_start = time.time()
    flexible_model = flexible_model_obj.build_model()
    flexible_build_time = time.time() - flexible_build_start
    print(f"Flexible model built in {flexible_build_time:.1f}s")

    # Extract warmstart from pattern solution
    print("\nExtracting warmstart from pattern solution...")
    warmstart_start = time.time()
    warmstart_count = extract_warmstart(pattern_model, flexible_model)
    warmstart_time = time.time() - warmstart_start
    print(f"Warmstart applied to {warmstart_count:,} variables in {warmstart_time:.1f}s")

    # PHASE 3: Solve with warmstart
    print("\n" + "="*80)
    print("PHASE 3: SOLVE 4-WEEK FLEXIBLE WITH WARMSTART")
    print("="*80)

    print("\nSolving with warmstart...")
    flexible_solver = appsi.solvers.Highs()
    flexible_solver.config.time_limit = 900  # 15 minutes
    flexible_solver.config.mip_gap = 0.03
    flexible_solver.config.stream_solver = False
    flexible_solver.config.warmstart = True  # CRITICAL: Enable warmstart

    print("Warmstart enabled in solver config")

    flexible_solve_start = time.time()
    flexible_result = flexible_solver.solve(flexible_model)
    flexible_solve_time = time.time() - flexible_solve_start

    flexible_cost = pyo.value(flexible_model.obj)
    flexible_gap = None
    if hasattr(flexible_result, 'best_feasible_objective') and hasattr(flexible_result, 'best_objective_bound'):
        best_feas = flexible_result.best_feasible_objective
        best_bound = flexible_result.best_objective_bound
        if best_feas and best_bound and best_feas != 0:
            flexible_gap = abs((best_feas - best_bound) / best_feas)

    print(f"\nFlexible solution (with warmstart):")
    print(f"  Solve time: {flexible_solve_time:.1f}s")
    print(f"  Cost: ${flexible_cost:,.2f}")
    if flexible_gap is not None:
        print(f"  Gap: {flexible_gap*100:.3f}%")
    print(f"  Status: {flexible_result.termination_condition}")

    # RESULTS COMPARISON
    print(f"\n{'='*80}")
    print("RESULTS COMPARISON")
    print(f"{'='*80}")

    cold_start_time = 905.4  # From previous test
    total_time = pattern_solve_time + flexible_solve_time

    print(f"\n4-Week Full Flexible Performance:")
    print(f"  Cold start (no warmstart): 905.4s (timeout)")
    print(f"  With warmstart:")
    print(f"    - Pattern solve: {pattern_solve_time:.1f}s")
    print(f"    - Flexible solve: {flexible_solve_time:.1f}s")
    print(f"    - Total time: {total_time:.1f}s")

    if total_time < cold_start_time:
        speedup = cold_start_time / total_time
        improvement = cold_start_time - total_time
        print(f"\n  ✅ Warmstart FASTER: {improvement:.0f}s improvement ({speedup:.2f}× speedup)")
    else:
        slowdown = total_time / cold_start_time
        print(f"\n  ⚠️  Warmstart slower: {slowdown:.2f}× (warmstart overhead > benefit)")

    # Compare to other approaches
    print(f"\n{'='*80}")
    print("COMPARISON TO ALL APPROACHES")
    print(f"{'='*80}")

    print(f"\n6-week horizon options:")
    print(f"  Full pattern: 21.5s")
    print(f"  1-week flexible + $0.20: 433.5s")

    print(f"\n4-week horizon options:")
    print(f"  Full pattern: {pattern_solve_time:.1f}s")
    print(f"  Full flexible (cold): 905s (timeout)")
    print(f"  Full flexible (warmstart): {total_time:.1f}s")

    # Final recommendation
    print(f"\n{'='*80}")
    print("RECOMMENDATION")
    print(f"{'='*80}")

    if total_time < 300:  # 5 minutes
        print(f"\n🎉 SUCCESS: 4-week flexible with warmstart is PRACTICAL!")
        print(f"\nConfiguration:")
        print(f"  - Horizon: 4 weeks")
        print(f"  - Flexibility: 100%")
        print(f"  - Warmstart: Pattern solution")
        print(f"  - Total time: {total_time:.0f}s ({total_time/60:.1f} minutes)")
        print(f"\n✅ RECOMMENDED for 4-week planning cycle")
    elif total_time < 600:  # 10 minutes
        print(f"\n✓  ACCEPTABLE: Warmstart helps but still slow")
        print(f"\nPerformance:")
        print(f"  - Total time: {total_time:.0f}s ({total_time/60:.1f} minutes)")
        print(f"  - Improvement over cold: {cold_start_time - total_time:.0f}s")
        print(f"\nDecision: Use if 4-week full flexibility is critical")
    else:
        print(f"\n❌ Warmstart not sufficient")
        print(f"\nResults:")
        print(f"  - Still slow: {total_time:.0f}s ({total_time/60:.1f} minutes)")
        print(f"\nRecommendation:")
        print(f"  For 6-week: Use 1-week flexible (433s)")
        print(f"  For 4-week: Use 1-week flexible (~250-300s estimated)")

    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}")

    return 0


if __name__ == "__main__":
    exit(main())
