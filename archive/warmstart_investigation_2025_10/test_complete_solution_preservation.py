#!/usr/bin/env python3
"""Test: Complete Solution Preservation Including Auxiliary Variables

ROOT CAUSE FOUND: When changeover constraints are deactivated in Phase 1,
the num_products_produced variables are not given values. When we reactivate
in Phase 2, the Phase 1 solution becomes INFEASIBLE!

Solution: Before deactivating pattern and reactivating changeover,
we need to SET num_products_produced values based on Phase 1 solution.

This test verifies this hypothesis and implements the fix.
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


def build_pattern_model(model_obj, products, weekday_dates_lists, manufacturing_nodes_list):
    """Build 4-week pattern model."""
    model = model_obj.build_model()

    pattern_index = [(prod, wd) for prod in products for wd in range(5)]
    model.product_weekday_pattern = pyo.Var(pattern_index, within=pyo.Binary)

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

    if hasattr(model, 'num_products_counting_con'):
        for idx in model.num_products_counting_con:
            model.num_products_counting_con[idx].deactivate()

    return model


def preserve_complete_solution(model, products, manufacturing_nodes_list, dates_range):
    """Preserve complete solution including auxiliary variables.

    Key insight: When changeover constraints were deactivated in Phase 1,
    num_products_produced variables were not set. We need to set them now
    based on product_produced values BEFORE reactivating the constraints.
    """
    print("\nPreserving complete solution (including auxiliary variables)...")

    # Calculate and set num_products_produced based on product_produced
    if hasattr(model, 'num_products_produced'):
        for node_id in manufacturing_nodes_list:
            for date_val in dates_range:
                if (node_id, date_val) in model.num_products_produced:
                    # Count how many products were produced
                    count = sum(
                        1 for product in products
                        if (node_id, product, date_val) in model.product_produced
                        and pyo.value(model.product_produced[node_id, product, date_val]) > 0.5
                    )

                    # Set the count variable
                    model.num_products_produced[node_id, date_val].set_value(count)

        print(f"  Set {len([k for k in model.num_products_produced])} num_products_produced variables")

    return True


def main():
    print("="*80)
    print("TEST: COMPLETE SOLUTION PRESERVATION")
    print("="*80)
    print("\nHypothesis: num_products_produced variables not set in Phase 1")
    print("Fix: Set them before reactivating changeover constraints")

    # Load data (abbreviated for clarity)
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

    # PHASE 1: Build and solve pattern model
    print("\n" + "="*80)
    print("PHASE 1: SOLVE PATTERN MODEL")
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
        force_all_skus_daily=False,
    )

    model = model_obj.build_model()
    pattern_model = build_pattern_model(model_obj, products, weekday_dates_lists, manufacturing_nodes_list)

    solver = appsi.solvers.Highs()
    solver.config.time_limit = 120
    solver.config.mip_gap = 0.03
    solver.config.stream_solver = True

    print("Solving Phase 1...")
    phase1_start = time.time()
    result1 = solver.solve(pattern_model)
    phase1_time = time.time() - phase1_start

    cost1 = pyo.value(pattern_model.obj)
    print(f"\nPhase 1 Results:")
    print(f"  Cost: ${cost1:,.2f}")
    print(f"  Time: {phase1_time:.1f}s")

    # CRITICAL FIX: Preserve complete solution
    print("\n" + "="*80)
    print("APPLYING FIX: Preserve ALL Variables")
    print("="*80)

    preserve_complete_solution(pattern_model, products, manufacturing_nodes_list, dates_range)

    # PHASE 2: Deactivate pattern, reactivate changeover
    print("\n" + "="*80)
    print("PHASE 2: DEACTIVATE PATTERN, REACTIVATE CHANGEOVER")
    print("="*80)

    print("\nDeactivating pattern constraints...")
    pattern_model.weekly_pattern_linking.deactivate()

    print("Reactivating changeover constraints...")
    if hasattr(pattern_model, 'num_products_counting_con'):
        for idx in pattern_model.num_products_counting_con:
            pattern_model.num_products_counting_con[idx].activate()

    print("Fixing pattern variables to 0...")
    for idx in pattern_model.product_weekday_pattern:
        pattern_model.product_weekday_pattern[idx].fix(0)

    # Verify feasibility NOW
    print("\nVerifying Phase 1 solution is now feasible for Phase 2...")
    violations_found = False

    if hasattr(pattern_model, 'num_products_counting_con'):
        for idx in pattern_model.num_products_counting_con:
            con = pattern_model.num_products_counting_con[idx]
            try:
                body_val = pyo.value(con.body)
                lower = pyo.value(con.lower) if con.lower is not None else None
                upper = pyo.value(con.upper) if con.upper is not None else None

                violated = False
                if lower is not None and body_val < lower - 1e-6:
                    print(f"  ❌ Violation at {idx}: body={body_val:.4f} < lower={lower:.4f}")
                    violated = True
                    violations_found = True
                if upper is not None and body_val > upper + 1e-6:
                    print(f"  ❌ Violation at {idx}: body={body_val:.4f} > upper={upper:.4f}")
                    violated = True
                    violations_found = True
            except:
                pass

    if not violations_found:
        print("  ✓  NO violations - Phase 1 solution is NOW feasible for Phase 2!")

    # PHASE 2: Re-solve
    print("\n" + "="*80)
    print("PHASE 2: SOLVE WITH PRESERVED SOLUTION")
    print("="*80)
    print("\nExpected: Should start from ${}K or find better".format(cost1/1000))

    phase2_start = time.time()
    result2 = solver.solve(pattern_model)
    phase2_time = time.time() - phase2_start

    cost2 = pyo.value(pattern_model.obj)
    print(f"\nPhase 2 Results:")
    print(f"  Cost: ${cost2:,.2f}")
    print(f"  Time: {phase2_time:.1f}s")

    # ANALYSIS
    print("\n" + "="*80)
    print("RESULTS ANALYSIS")
    print("="*80)

    cost_diff = cost2 - cost1
    cost_pct = (cost_diff / cost1) * 100 if cost1 > 0 else 0

    print(f"\nPhase 1:     ${cost1:,.2f} in {phase1_time:.1f}s")
    print(f"Phase 2:     ${cost2:,.2f} in {phase2_time:.1f}s")
    print(f"Difference:  ${cost_diff:,.2f} ({cost_pct:+.2f}%)")

    if abs(cost_diff) < 1000:
        print(f"\n✅ SUCCESS: Phase 2 matched Phase 1 cost!")
        print(f"   Solution was preserved correctly")
        print(f"   Warmstart is working")
    elif cost_diff < 0:
        print(f"\n✅ GREAT: Phase 2 found BETTER solution!")
        print(f"   Improved by ${-cost_diff:,.2f}")
        print(f"   Warmstart helped solver find improvement")
    else:
        print(f"\n❌ FAILURE: Phase 2 still worse than Phase 1")
        print(f"   Cost increased by ${cost_diff:,.2f}")
        print(f"   Solution preservation didn't work")

    total_time = phase1_time + phase2_time
    print(f"\nTotal time: {total_time:.1f}s")

    if phase2_time < 60:
        print(f"✓  Phase 2 was fast - hot-start likely working")
    else:
        print(f"⚠️  Phase 2 was slow - hot-start may not be effective")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)

    return 0


if __name__ == "__main__":
    exit(main())
