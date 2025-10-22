#!/usr/bin/env python3
"""SYSTEMATIC DEBUGGING: Warmstart Paradox

Investigation: Why does pattern solution ($779k, 11.8s) not help flexible model ($1,001k, 905s)?

Theory violation: Flexible has FEWER constraints, so pattern solution should be:
1. Feasible for flexible (subset of constraints)
2. Same cost in both models (same objective)
3. Good warmstart (optimal or near-optimal)

But we observe: Cost increases 28% and solve time increases 77×!

Systematic investigation to find root cause.
"""

import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType

import pyomo.environ as pyo
from pyomo.contrib import appsi


def evaluate_objective(model):
    """Evaluate current objective value with current variable values."""
    return pyo.value(model.obj)


def main():
    print("="*80)
    print("SYSTEMATIC DEBUGGING: WARMSTART PARADOX")
    print("="*80)

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

    # 4-week horizon
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=4*7 - 1)

    products = sorted(set(e.product_id for e in forecast.entries))
    manufacturing_nodes_list = [n.id for n in nodes if n.capabilities.can_manufacture]

    # Configure
    cost_structure = cost_structure_base.model_copy()
    cost_structure.freshness_incentive_weight = 0.05

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

    # ====================================================================================
    # STEP 1: SOLVE PATTERN MODEL
    # ====================================================================================
    print("\n" + "="*80)
    print("STEP 1: SOLVE PATTERN MODEL")
    print("="*80)

    pattern_model_obj = UnifiedNodeModel(
        nodes=nodes, routes=unified_routes, forecast=forecast,
        labor_calendar=labor_calendar, cost_structure=cost_structure,
        start_date=start_date, end_date=end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=initial_inventory,
        inventory_snapshot_date=inventory_date,
        use_batch_tracking=True, allow_shortages=True,
        enforce_shelf_life=True, force_all_skus_daily=False,
    )

    pattern_model = pattern_model_obj.build_model()

    # Add pattern constraints
    pattern_index = [(prod, wd) for prod in products for wd in range(5)]
    pattern_model.product_weekday_pattern = pyo.Var(pattern_index, within=pyo.Binary)
    pattern_model.weekly_pattern_linking = pyo.ConstraintList()

    for node_id in manufacturing_nodes_list:
        for product in products:
            for weekday_idx in range(5):
                for date_val in weekday_dates_lists[weekday_idx]:
                    if (node_id, product, date_val) in pattern_model.product_produced:
                        pattern_model.weekly_pattern_linking.add(
                            pattern_model.product_produced[node_id, product, date_val] ==
                            pattern_model.product_weekday_pattern[product, weekday_idx]
                        )

    if hasattr(pattern_model, 'num_products_counting_con'):
        for idx in pattern_model.num_products_counting_con:
            pattern_model.num_products_counting_con[idx].deactivate()

    # Solve pattern
    print("\nSolving pattern model...")
    pattern_solver = appsi.solvers.Highs()
    pattern_solver.config.time_limit = 300
    pattern_solver.config.mip_gap = 0.03
    pattern_result = pattern_solver.solve(pattern_model)

    pattern_cost = pyo.value(pattern_model.obj)
    print(f"\nPattern solution:")
    print(f"  Cost: ${pattern_cost:,.2f}")
    print(f"  Status: {pattern_result.termination_condition}")

    # ====================================================================================
    # STEP 2: BUILD FLEXIBLE MODEL (SAME SETUP, NO PATTERN CONSTRAINTS)
    # ====================================================================================
    print("\n" + "="*80)
    print("STEP 2: BUILD FLEXIBLE MODEL")
    print("="*80)

    flexible_model_obj = UnifiedNodeModel(
        nodes=nodes, routes=unified_routes, forecast=forecast,
        labor_calendar=labor_calendar, cost_structure=cost_structure,  # SAME cost_structure!
        start_date=start_date, end_date=end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=initial_inventory,
        inventory_snapshot_date=inventory_date,
        use_batch_tracking=True, allow_shortages=True,
        enforce_shelf_life=True, force_all_skus_daily=False,
    )

    flexible_model = flexible_model_obj.build_model()
    print("\nFlexible model built (NO pattern constraints)")

    # ====================================================================================
    # STEP 3: EVALUATE PATTERN SOLUTION ON FLEXIBLE OBJECTIVE (CRITICAL TEST!)
    # ====================================================================================
    print("\n" + "="*80)
    print("STEP 3: EVALUATE PATTERN SOLUTION ON FLEXIBLE MODEL")
    print("="*80)

    print("\nTransferring pattern solution values to flexible model...")

    # Transfer ALL variable values from pattern to flexible
    transferred = 0
    for v in pattern_model.component_data_objects(ctype=pyo.Var, active=True):
        # Get index
        if hasattr(v, 'index'):
            idx = v.index()
        else:
            idx = None

        # Find matching variable in flexible model
        var_name = v.parent_component().name
        if hasattr(flexible_model, var_name):
            flexible_var_component = getattr(flexible_model, var_name)

            if idx is not None:
                if idx in flexible_var_component:
                    flexible_var_component[idx].set_value(pyo.value(v))
                    transferred += 1
            else:
                flexible_var_component.set_value(pyo.value(v))
                transferred += 1

    print(f"Transferred {transferred:,} variable values")

    # CRITICAL: Evaluate flexible objective with pattern solution
    print("\nEvaluating flexible objective with pattern solution...")
    flexible_cost_with_pattern = evaluate_objective(flexible_model)

    print(f"\nCost comparison:")
    print(f"  Pattern model cost:               ${pattern_cost:,.2f}")
    print(f"  Flexible model (pattern solution): ${flexible_cost_with_pattern:,.2f}")

    cost_diff = flexible_cost_with_pattern - pattern_cost
    cost_diff_pct = (cost_diff / pattern_cost) * 100

    print(f"  Difference: ${cost_diff:,.2f} ({cost_diff_pct:+.2f}%)")

    # DIAGNOSIS
    print("\n" + "="*80)
    print("DIAGNOSIS")
    print("="*80)

    if abs(cost_diff) < 100:
        print("\n✅ COSTS MATCH! Objectives are identical.")
        print("   → Warmstart should provide excellent starting point")
        print("   → Problem must be in warmstart loading or solver usage")
    else:
        print(f"\n❌ COSTS DIFFER BY ${abs(cost_diff):,.2f}!")
        print("   → Objectives are NOT identical!")
        print("   → This explains why warmstart doesn't help")
        print("\nPossible causes:")
        print("  1. Different objective expressions")
        print("  2. Pattern solution infeasible for flexible")
        print("  3. Missing constraints in one model")

    # ====================================================================================
    # STEP 4: SOLVE FLEXIBLE WITH WARMSTART
    # ====================================================================================
    print("\n" + "="*80)
    print("STEP 4: SOLVE FLEXIBLE WITH WARMSTART")
    print("="*80)

    print(f"\nBefore solving, flexible objective = ${flexible_cost_with_pattern:,.2f}")
    print("If warmstart is used, solver should start from this cost...")

    flexible_solver = appsi.solvers.Highs()
    flexible_solver.config.time_limit = 120  # Short time for diagnostic
    flexible_solver.config.mip_gap = 0.03
    flexible_solver.config.warmstart = True
    flexible_solver.config.stream_solver = False

    print("\nSolving flexible with 2-minute timeout...")
    flexible_result = flexible_solver.solve(flexible_model)

    flexible_cost_after = pyo.value(flexible_model.obj)

    print(f"\nFlexible solution:")
    print(f"  Cost after solve: ${flexible_cost_after:,.2f}")
    print(f"  Status: {flexible_result.termination_condition}")

    # ====================================================================================
    # FINAL ANALYSIS
    # ====================================================================================
    print("\n" + "="*80)
    print("ROOT CAUSE ANALYSIS")
    print("="*80)

    print(f"\nCost progression:")
    print(f"  Pattern optimal:                  ${pattern_cost:,.2f}")
    print(f"  Flexible (with pattern values):   ${flexible_cost_with_pattern:,.2f}")
    print(f"  Flexible (after warmstart solve): ${flexible_cost_after:,.2f}")

    if abs(flexible_cost_with_pattern - pattern_cost) > 100:
        print("\n🔴 ROOT CAUSE: OBJECTIVES ARE DIFFERENT!")
        print("   Pattern and flexible have different objective expressions")
        print("   → Need to investigate objective formulation differences")
    elif abs(flexible_cost_after - flexible_cost_with_pattern) > 100:
        print("\n🔴 ROOT CAUSE: WARMSTART NOT BEING USED!")
        print("   Solver ignored warmstart values and found different solution")
        print("   → APPSI HiGHS warmstart may not be working")
    else:
        print("\n✅ Warmstart IS working (costs stayed same)")
        print("   → Problem is just that flexible takes longer to prove optimality")

    print("\n" + "="*80)
    print("DIAGNOSTIC COMPLETE")
    print("="*80)

    return 0


if __name__ == "__main__":
    exit(main())
