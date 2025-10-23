#!/usr/bin/env python3
"""Test: Sequence-Independent Changeover Formulation (Start Tracking)

User's proposed formulation:
- b[i,t] ∈ {0,1}: Product i running in period t
- y[i,t] ∈ {0,1}: Product i STARTS in period t (changeover trigger)
- y[i,t] ≥ b[i,t] - b[i,t-1]  (captures 0→1 transitions)

Benefits over counting constraint:
- No equality constraints (just inequalities)
- No integer variables (just binary)
- Weaker coupling (inequality vs equality)
- Directly tracks changeovers (what we care about)

This test compares three scenarios:
1. Pattern model with start tracking
2. Flexible model with start tracking
3. Pattern warmstart → Flexible (if start tracking enables it)
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


def add_start_tracking_changeover(model, products, manufacturing_nodes_list, dates_range, labor_calendar):
    """Add sequence-independent changeover formulation.

    Variables:
    - product_produced[i,t] (already exists): b[i,t] - is product running
    - product_start[i,t] (new): y[i,t] - does product START

    Constraints:
    - y[i,t] ≥ b[i,t] - b[i,t-1]  (captures 0→1 transitions)

    Capacity:
    - production_time + setup_time * sum(y[i,t]) ≤ capacity
    """

    # Add start/changeover indicator variables
    start_index = [
        (node_id, prod, date_val)
        for node_id in manufacturing_nodes_list
        for prod in products
        for date_val in dates_range
    ]

    model.product_start = pyo.Var(
        start_index,
        within=pyo.Binary,
        doc="Binary: 1 if product starts (changeover) in this period"
    )

    print(f"  Added {len(start_index)} product_start variables")

    # Add changeover detection constraints
    model.changeover_detection = pyo.ConstraintList()

    for node_id in manufacturing_nodes_list:
        for prod in products:
            prev_date = None
            for date_val in sorted(dates_range):
                if (node_id, prod, date_val) not in model.product_produced:
                    continue

                if prev_date is None:
                    # First period - start if producing
                    # Assume no prior production (b[i,0] = 0)
                    model.changeover_detection.add(
                        model.product_start[node_id, prod, date_val] >=
                        model.product_produced[node_id, prod, date_val]
                    )
                else:
                    # y[i,t] ≥ b[i,t] - b[i,t-1]
                    model.changeover_detection.add(
                        model.product_start[node_id, prod, date_val] >=
                        model.product_produced[node_id, prod, date_val] -
                        model.product_produced[node_id, prod, prev_date]
                    )

                prev_date = date_val

    print(f"  Added {len(model.changeover_detection)} changeover detection constraints")

    # Deactivate counting constraint (not needed)
    if hasattr(model, 'num_products_counting_con'):
        for idx in model.num_products_counting_con:
            model.num_products_counting_con[idx].deactivate()
        print(f"  Deactivated counting constraint (using start tracking instead)")

    # Deactivate original labor/capacity constraints
    if hasattr(model, 'labor_hours_linking_con'):
        for idx in model.labor_hours_linking_con:
            model.labor_hours_linking_con[idx].deactivate()

    if hasattr(model, 'production_capacity_con'):
        for idx in model.production_capacity_con:
            model.production_capacity_con[idx].deactivate()

    # Add reformulated capacity with changeover time
    model.capacity_with_changeovers = pyo.ConstraintList()

    startup_hours = 0.5
    shutdown_hours = 0.25
    changeover_hours = 0.5
    production_rate = 1400.0

    for date_val in dates_range:
        node_id = manufacturing_nodes_list[0]

        # Production time
        production_time = sum(
            model.production[node_id, prod, date_val]
            for prod in products
            if (node_id, prod, date_val) in model.production
        ) / production_rate

        # Changeover time = changeover_hours * number of starts
        changeover_time = changeover_hours * sum(
            model.product_start[node_id, prod, date_val]
            for prod in products
            if (node_id, prod, date_val) in model.product_start
        )

        # Fixed overhead (startup + shutdown) if any production
        fixed_overhead = (startup_hours + shutdown_hours) * model.production_day[node_id, date_val]

        # Use paid hours for capacity limit
        if hasattr(model, 'labor_hours_paid') and (node_id, date_val) in model.labor_hours_paid:
            model.capacity_with_changeovers.add(
                production_time + fixed_overhead + changeover_time <=
                model.labor_hours_paid[node_id, date_val]
            )

    print(f"  Added {len(model.capacity_with_changeovers)} capacity constraints with start tracking")

    return model


def build_pattern_model_with_start_tracking(model_obj, products, weekday_dates_lists, manufacturing_nodes_list, dates_range, labor_calendar):
    """Build pattern model using start tracking changeover formulation."""

    model = model_obj.build_model()

    # Add parameter for pattern control
    model.pattern_active = pyo.Param(initialize=1.0, mutable=True)

    # Pattern variables
    pattern_index = [(prod, wd) for prod in products for wd in range(5)]
    model.product_weekday_pattern = pyo.Var(pattern_index, within=pyo.Binary)

    # Pattern linking (parameter-controlled)
    big_m = 10.0
    model.pattern_linking_upper = pyo.ConstraintList()
    model.pattern_linking_lower = pyo.ConstraintList()

    for node_id in manufacturing_nodes_list:
        for product in products:
            for weekday_idx in range(5):
                for date_val in weekday_dates_lists[weekday_idx]:
                    if (node_id, product, date_val) in model.product_produced:
                        model.pattern_linking_upper.add(
                            model.product_produced[node_id, product, date_val] -
                            model.product_weekday_pattern[product, weekday_idx]
                            <= big_m * (1 - model.pattern_active)
                        )
                        model.pattern_linking_lower.add(
                            model.product_produced[node_id, product, date_val] -
                            model.product_weekday_pattern[product, weekday_idx]
                            >= -big_m * (1 - model.pattern_active)
                        )

    print(f"  Added pattern constraints (parameter-controlled)")

    # Add start tracking changeover formulation
    add_start_tracking_changeover(model, products, manufacturing_nodes_list, dates_range, labor_calendar)

    return model


def main():
    print("="*80)
    print("TEST: Sequence-Independent Changeover Formulation (Start Tracking)")
    print("="*80)
    print("\nUser's proposed formulation:")
    print("  y[i,t] ≥ b[i,t] - b[i,t-1]  (captures 0→1 transitions)")
    print("  Capacity: production_time + setup_time * sum(y[i,t]) ≤ C")
    print("\nTests:")
    print("  1. Pattern model with start tracking")
    print("  2. Flexible model with start tracking")
    print("  3. Pattern warmstart → Flexible\n")

    # Load data
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

    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=4*7 - 1)

    products = sorted(set(e.product_id for e in forecast.entries))
    manufacturing_nodes_list = [n.id for n in nodes if n.capabilities.can_manufacture]

    weekday_dates_lists = {i: [] for i in range(5)}
    dates_range = []
    current = start_date
    while current <= end_date:
        dates_range.append(current)
        if current.weekday() < 5:
            labor_day = labor_calendar.get_labor_day(current)
            if labor_day and labor_day.is_fixed_day:
                weekday_dates_lists[current.weekday()].append(current)
        current += timedelta(days=1)

    cost_structure = cost_structure_base.model_copy()
    cost_structure.freshness_incentive_weight = 0.05

    # TEST 1: Pattern model with start tracking
    print("\n" + "="*80)
    print("TEST 1: PATTERN MODEL WITH START TRACKING")
    print("="*80)

    model1_obj = UnifiedNodeModel(
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

    print("\nBuilding pattern model with start tracking...")
    model_pattern = build_pattern_model_with_start_tracking(
        model1_obj, products, weekday_dates_lists, manufacturing_nodes_list, dates_range, labor_calendar
    )

    # Count variables
    num_binary_pattern = sum(1 for v in model_pattern.component_data_objects(pyo.Var, active=True) if v.is_binary())
    num_int_pattern = sum(1 for v in model_pattern.component_data_objects(pyo.Var, active=True) if v.is_integer() and not v.is_binary())

    print(f"\nPattern model structure:")
    print(f"  Binary vars:   {num_binary_pattern:,}")
    print(f"  Integer vars:  {num_int_pattern:,}")

    solver = appsi.solvers.Highs()
    solver.config.time_limit = 120
    solver.config.mip_gap = 0.03
    solver.config.stream_solver = False

    print("\nSolving pattern model...")
    t1_start = time.time()
    result1 = solver.solve(model_pattern)
    t1_time = time.time() - t1_start

    cost1 = pyo.value(model_pattern.obj)

    print(f"\nTest 1 Results:")
    print(f"  Cost:   ${cost1:,.2f}")
    print(f"  Time:   {t1_time:.1f}s")
    print(f"  Status: {result1.termination_condition}")

    # TEST 2: Flexible model with start tracking
    print("\n" + "="*80)
    print("TEST 2: FLEXIBLE MODEL WITH START TRACKING")
    print("="*80)

    model2_obj = UnifiedNodeModel(
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

    print("\nBuilding flexible model with start tracking...")
    model_flexible = model2_obj.build_model()

    # Add start tracking (no pattern constraints)
    add_start_tracking_changeover(model_flexible, products, manufacturing_nodes_list, dates_range, labor_calendar)

    num_binary_flex = sum(1 for v in model_flexible.component_data_objects(pyo.Var, active=True) if v.is_binary())
    num_int_flex = sum(1 for v in model_flexible.component_data_objects(pyo.Var, active=True) if v.is_integer() and not v.is_binary())

    print(f"\nFlexible model structure:")
    print(f"  Binary vars:   {num_binary_flex:,}")
    print(f"  Integer vars:  {num_int_flex:,}")

    print("\nSolving flexible model...")
    t2_start = time.time()
    result2 = solver.solve(model_flexible)
    t2_time = time.time() - t2_start

    cost2 = pyo.value(model_flexible.obj)

    print(f"\nTest 2 Results:")
    print(f"  Cost:   ${cost2:,.2f}")
    print(f"  Time:   {t2_time:.1f}s")
    print(f"  Status: {result2.termination_condition}")

    # TEST 3: Pattern warmstart for flexible
    print("\n" + "="*80)
    print("TEST 3: PATTERN WARMSTART → FLEXIBLE (START TRACKING)")
    print("="*80)

    # Build fresh model for warmstart test
    model3_obj = UnifiedNodeModel(
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

    print("\nBuilding pattern model for warmstart...")
    model_warmstart = build_pattern_model_with_start_tracking(
        model3_obj, products, weekday_dates_lists, manufacturing_nodes_list, dates_range, labor_calendar
    )

    solver_warmstart = appsi.solvers.Highs()
    solver_warmstart.config.time_limit = 120
    solver_warmstart.config.mip_gap = 0.03
    solver_warmstart.config.stream_solver = False

    # Phase 1: Solve pattern
    print("\nPhase 1: Solving pattern...")
    t3a_start = time.time()
    result3a = solver_warmstart.solve(model_warmstart)
    t3a_time = time.time() - t3a_start

    cost3a = pyo.value(model_warmstart.obj)
    print(f"  Phase 1: ${cost3a:,.2f} in {t3a_time:.1f}s")

    # Phase 2: Change parameter (pure parameter change - no structural changes!)
    print("\nPhase 2: Changing pattern_active: 1 → 0")
    model_warmstart.pattern_active.set_value(0.0)
    print("  ✓  NO structural changes (start tracking stays active)")

    print("\nPhase 2: Re-solving...")
    print(f"Expected initial incumbent: ~${cost3a:,.0f}\n")

    t3b_start = time.time()
    result3b = solver_warmstart.solve(model_warmstart)
    t3b_time = time.time() - t3b_start

    cost3b = pyo.value(model_warmstart.obj)
    print(f"  Phase 2: ${cost3b:,.2f} in {t3b_time:.1f}s")

    # COMPREHENSIVE COMPARISON
    print("\n" + "="*80)
    print("COMPREHENSIVE COMPARISON")
    print("="*80)

    print(f"\n1. PATTERN MODEL (Start Tracking):")
    print(f"   Cost: ${cost1:,.2f}")
    print(f"   Time: {t1_time:.1f}s")
    print(f"   Binary vars: {num_binary_pattern:,}")

    print(f"\n2. FLEXIBLE MODEL (Start Tracking):")
    print(f"   Cost: ${cost2:,.2f}")
    print(f"   Time: {t2_time:.1f}s")
    print(f"   Binary vars: {num_binary_flex:,}")

    print(f"\n3. WARMSTART (Pattern → Flexible with Start Tracking):")
    print(f"   Phase 1: ${cost3a:,.2f} in {t3a_time:.1f}s")
    print(f"   Phase 2: ${cost3b:,.2f} in {t3b_time:.1f}s")
    print(f"   Total:   ${cost3b:,.2f} in {t3a_time + t3b_time:.1f}s")

    cost_diff = cost3b - cost3a
    cost_pct = (cost_diff / cost3a) * 100 if cost3a > 0 else 0
    print(f"   Change:  ${cost_diff:,.2f} ({cost_pct:+.2f}%)")

    # HISTORICAL COMPARISON
    print(f"\n{'='*80}")
    print("COMPARISON TO HISTORICAL RESULTS (Counting Constraint)")
    print(f"{'='*80}")

    print(f"\nCounting constraint approach:")
    print(f"  Pattern:  $779K in 8s   (counting deactivated)")
    print(f"  Flexible: Unknown (not tested alone)")
    print(f"  Warmstart Phase 2: $1,928K in 301s (warmstart failed)")

    print(f"\nStart tracking approach:")
    print(f"  Pattern:  ${cost1/1000:.0f}K in {t1_time:.0f}s")
    print(f"  Flexible: ${cost2/1000:.0f}K in {t2_time:.0f}s")
    print(f"  Warmstart Phase 2: ${cost3b/1000:.0f}K in {t3b_time:.0f}s")

    # WARMSTART EVALUATION
    print(f"\n{'='*80}")
    print("WARMSTART EVALUATION")
    print(f"{'='*80}")

    if abs(cost_diff) < 100:
        print(f"\n🎉 SUCCESS: Warmstart preserved incumbent!")
        print(f"   Start tracking formulation enables APPSI warmstart!")
    elif cost_diff < 0:
        print(f"\n✅ IMPROVED: Phase 2 better by ${-cost_diff:,.2f}")
        print(f"   Warmstart worked!")
    elif cost_diff < cost3a * 0.10:
        print(f"\n⚠️  PARTIAL: Phase 2 slightly worse (+{cost_pct:.1f}%)")
        print(f"   May indicate warmstart partially working")
    else:
        print(f"\n❌ FAILED: Phase 2 much worse (+{cost_pct:.1f}%)")
        print(f"   Warmstart likely not preserved")

    # FINAL RECOMMENDATION
    print(f"\n{'='*80}")
    print("FINAL RECOMMENDATION")
    print(f"{'='*80}")

    if cost1 < 850000 and t1_time < 30:
        print(f"\n✅ Start tracking formulation WORKS for pattern model")
        print(f"   - Good cost: ${cost1:,.0f}")
        print(f"   - Fast solve: {t1_time:.1f}s")

    if cost2 < 850000 and t2_time < 120:
        print(f"\n✅ Start tracking formulation WORKS for flexible model")
        print(f"   - Good cost: ${cost2:,.0f}")
        print(f"   - Reasonable time: {t2_time:.1f}s")

    if abs(cost_diff) < 1000:
        print(f"\n✅ Start tracking ENABLES APPSI warmstart!")
        print(f"   - This is the SOLUTION to the warmstart problem!")

    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}")

    return 0


if __name__ == "__main__":
    exit(main())
