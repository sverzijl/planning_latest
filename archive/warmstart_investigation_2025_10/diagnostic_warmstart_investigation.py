#!/usr/bin/env python3
"""DIAGNOSTIC: Investigate why pattern warmstart produces worse solutions.

Phase 1 Investigation:
- Enable tee=True to capture solver output
- Compare costs: Pattern vs Flexible-cold vs Flexible-warm
- Verify warmstart acceptance by HiGHS
- Analyze pattern solution structure
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
    """Extract warmstart values from pattern solution for flexible model."""
    count = 0

    # Extract binary production decisions
    if hasattr(pattern_model, 'product_produced'):
        for idx in pattern_model.product_produced:
            val = pyo.value(pattern_model.product_produced[idx])
            if val is not None and idx in flexible_model.product_produced:
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


def analyze_pattern_solution(pattern_model, products, dates_range, manufacturing_nodes_list):
    """Analyze the pattern solution to see which SKUs are produced when."""
    print("\n" + "="*80)
    print("PATTERN SOLUTION ANALYSIS")
    print("="*80)

    # Count production days per product
    production_days = {prod: 0 for prod in products}

    for node_id in manufacturing_nodes_list:
        for product in products:
            for date_val in dates_range:
                if (node_id, product, date_val) in pattern_model.product_produced:
                    val = pyo.value(pattern_model.product_produced[node_id, product, date_val])
                    if val and val > 0.5:  # Binary variable close to 1
                        production_days[product] += 1

    print(f"\nProduction days per product (out of {len(dates_range)} days):")
    for product, days in sorted(production_days.items()):
        pct = (days / len(dates_range)) * 100
        print(f"  {product}: {days} days ({pct:.1f}%)")

    # Check if all products produced every day
    all_products_daily = all(days == len(dates_range) for days in production_days.values())

    if all_products_daily:
        print("\n⚠️  FINDING: All 5 products produced every day (100% coverage)")
        print("   This is likely SUBOPTIMAL for flexible model")
    else:
        print("\n✓  Pattern allows some products to skip days")

    return production_days, all_products_daily


def main():
    print("="*80)
    print("DIAGNOSTIC: PATTERN WARMSTART INVESTIGATION")
    print("="*80)
    print("\nGoal: Understand why pattern warmstart produces worse solutions")
    print("Method: Evidence gathering with detailed solver logs")

    # Load data
    print("\n" + "="*80)
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
    print("PHASE 1: SOLVE 4-WEEK PATTERN MODEL")
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

    print("\n" + "="*80)
    print("SOLVING PATTERN MODEL (with tee=True for diagnostics)")
    print("="*80)

    pattern_solver = appsi.solvers.Highs()
    pattern_solver.config.time_limit = 300  # 5 minutes
    pattern_solver.config.mip_gap = 0.03
    pattern_solver.config.stream_solver = True  # DIAGNOSTIC: Enable output

    pattern_solve_start = time.time()
    pattern_result = pattern_solver.solve(pattern_model)  # stream_solver=True already set in config
    pattern_solve_time = time.time() - pattern_solve_start

    pattern_cost = pyo.value(pattern_model.obj)
    print(f"\n{'='*80}")
    print(f"PATTERN SOLUTION:")
    print(f"  Solve time: {pattern_solve_time:.1f}s")
    print(f"  Objective cost: ${pattern_cost:,.2f}")
    print(f"  Termination: {pattern_result.termination_condition}")
    print(f"{'='*80}")

    # DIAGNOSTIC: Analyze pattern solution
    production_days, all_products_daily = analyze_pattern_solution(
        pattern_model, products, dates_range, manufacturing_nodes_list
    )

    # PHASE 2: Build 4-week flexible model
    print("\n" + "="*80)
    print("PHASE 2: BUILD 4-WEEK FLEXIBLE MODEL")
    print("="*80)

    print("\nCreating flexible model (no pattern constraints)...")
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
    print("\n" + "="*80)
    print("EXTRACTING WARMSTART FROM PATTERN SOLUTION")
    print("="*80)

    warmstart_start = time.time()
    warmstart_count = extract_warmstart(pattern_model, flexible_model)
    warmstart_time = time.time() - warmstart_start
    print(f"\nWarmstart extraction:")
    print(f"  Variables set: {warmstart_count:,}")
    print(f"  Time: {warmstart_time:.1f}s")

    # PHASE 3: Solve with warmstart
    print("\n" + "="*80)
    print("PHASE 3: SOLVE FLEXIBLE MODEL WITH WARMSTART")
    print("="*80)
    print("\nDIAGNOSTIC: Watch for 'Using MIP start' or 'Initial incumbent' messages")
    print("           If absent → warmstart was REJECTED or IGNORED")

    flexible_solver = appsi.solvers.Highs()
    flexible_solver.config.time_limit = 900  # 15 minutes
    flexible_solver.config.mip_gap = 0.03
    flexible_solver.config.stream_solver = True  # DIAGNOSTIC: Enable output
    flexible_solver.config.warmstart = True  # Enable warmstart

    print(f"\nSolver config:")
    print(f"  warmstart: {flexible_solver.config.warmstart}")
    print(f"  time_limit: {flexible_solver.config.time_limit}s")
    print(f"  mip_gap: {flexible_solver.config.mip_gap}")

    print("\n" + "="*80)
    print("SOLVING FLEXIBLE MODEL (with warmstart + tee=True)")
    print("="*80)

    flexible_solve_start = time.time()
    flexible_result = flexible_solver.solve(flexible_model)  # stream_solver=True already set in config
    flexible_solve_time = time.time() - flexible_solve_start

    flexible_cost = pyo.value(flexible_model.obj)
    flexible_gap = None
    if hasattr(flexible_result, 'best_feasible_objective') and hasattr(flexible_result, 'best_objective_bound'):
        best_feas = flexible_result.best_feasible_objective
        best_bound = flexible_result.best_objective_bound
        if best_feas and best_bound and best_feas != 0:
            flexible_gap = abs((best_feas - best_bound) / best_feas)

    print(f"\n{'='*80}")
    print(f"FLEXIBLE SOLUTION (WITH WARMSTART):")
    print(f"  Solve time: {flexible_solve_time:.1f}s")
    print(f"  Objective cost: ${flexible_cost:,.2f}")
    if flexible_gap is not None:
        print(f"  MIP gap: {flexible_gap*100:.3f}%")
    print(f"  Termination: {flexible_result.termination_condition}")
    print(f"{'='*80}")

    # DIAGNOSTIC ANALYSIS
    print("\n" + "="*80)
    print("DIAGNOSTIC ANALYSIS")
    print("="*80)

    total_time = pattern_solve_time + flexible_solve_time

    print(f"\n1. COST COMPARISON:")
    print(f"   Pattern model:        ${pattern_cost:,.2f}")
    print(f"   Flexible (warmstart): ${flexible_cost:,.2f}")

    cost_diff = flexible_cost - pattern_cost
    cost_pct = (cost_diff / pattern_cost) * 100 if pattern_cost > 0 else 0

    if cost_diff > 0:
        print(f"   → Flexible is WORSE by ${cost_diff:,.2f} ({cost_pct:+.1f}%)")
        print(f"   ⚠️  ANOMALY: Flexible should be better (less constrained)")
    else:
        print(f"   → Flexible is BETTER by ${-cost_diff:,.2f} ({cost_pct:+.1f}%)")
        print(f"   ✓  Expected: Flexible improved on pattern")

    print(f"\n2. PATTERN STRUCTURE:")
    if all_products_daily:
        print(f"   ⚠️  Pattern forces ALL 5 SKUs every day")
        print(f"   → This is likely SUBOPTIMAL")
        print(f"   → Warmstart may be POOR QUALITY")
    else:
        print(f"   ✓  Pattern allows selective production")

    print(f"\n3. TIME PERFORMANCE:")
    print(f"   Pattern solve:  {pattern_solve_time:.1f}s")
    print(f"   Flexible solve: {flexible_solve_time:.1f}s")
    print(f"   Total:          {total_time:.1f}s")

    print(f"\n4. WARMSTART ACCEPTANCE:")
    print(f"   → Review solver output above for:")
    print(f"      - 'Using MIP start' message")
    print(f"      - Initial primal bound matching pattern cost")
    print(f"      - Number of nodes explored")
    print(f"   → If no mention of warmstart → IT WAS REJECTED")

    # HYPOTHESIS
    print("\n" + "="*80)
    print("HYPOTHESIS")
    print("="*80)

    print("\nBased on evidence:")
    if all_products_daily and cost_diff > 0:
        print("\n✓  Hypothesis 1: POOR QUALITY WARMSTART")
        print("   - Pattern forces all SKUs daily (high cost)")
        print("   - Flexible with warmstart is worse than pattern")
        print("   - Warmstart is misleading the solver")
        print("\n   Next step: Verify warmstart was ACCEPTED (check logs above)")
        print("   If accepted → bad incumbent prunes good solutions")
        print("   If rejected → warmstart mechanism not working")
    elif not all_products_daily and cost_diff > 0:
        print("\n?  Hypothesis 2: WARMSTART NOT ACCEPTED")
        print("   - Pattern doesn't force all SKUs")
        print("   - But flexible still worse")
        print("   - Warmstart may not be working at all")
        print("\n   Next step: Check logs for warmstart acceptance")
    else:
        print("\n?  Unexpected result - flexible improved on pattern")
        print("   - May indicate warmstart is working correctly")
        print("   - Or warmstart rejected and cold start found better solution")

    print("\n" + "="*80)
    print("INVESTIGATION COMPLETE - Review logs above")
    print("="*80)

    return 0


if __name__ == "__main__":
    exit(main())
