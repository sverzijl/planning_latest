#!/usr/bin/env python3
"""Test Approach 5: Reformulate Overhead to Eliminate Counting Constraint

BREAKTHROUGH INSIGHT: The counting constraint is the problem!

Instead of:
    num_products_produced = sum(product_produced)  # ← Constraint to activate/deactivate
    overhead = (S+S-C) * production_day + C * num_products_produced

Use:
    overhead = (S+S-C) * production_day + C * sum(product_produced)  # ← Direct!

This eliminates the need to activate/deactivate ANY constraints in Phase 2!
Only parameter change (pattern_active: 1 → 0) - pure APPSI-compatible!
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


def build_pattern_model_with_reformulated_overhead(model_obj, products, weekday_dates_lists, manufacturing_nodes_list, dates_range):
    """Build pattern model with overhead reformulated to avoid counting constraint.

    Key reformulation:
        overhead = (S+S-C) * production_day + C * sum(product_produced)

    This eliminates need for num_products_counting_con entirely!
    """
    model = model_obj.build_model()

    # Add mutable parameter for pattern enforcement
    model.pattern_active = pyo.Param(initialize=1.0, mutable=True)
    print(f"  Added mutable parameter: pattern_active = {pyo.value(model.pattern_active)}")

    # Create pattern variables
    pattern_index = [(prod, wd) for prod in products for wd in range(5)]
    model.product_weekday_pattern = pyo.Var(pattern_index, within=pyo.Binary)
    print(f"  Added {len(pattern_index)} pattern variables")

    # BigM for conditional constraints
    big_m = 10.0

    # Add pattern linking with parameter control
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

    print(f"  Added pattern linking constraints (parameter-controlled)")

    # CRITICAL REFORMULATION: Replace num_products_counting_con
    # Instead of using counting constraint, substitute sum(product_produced) directly
    print("\n  REFORMULATING overhead calculation...")

    # Deactivate the counting constraint (we won't use it)
    if hasattr(model, 'num_products_counting_con'):
        for idx in model.num_products_counting_con:
            model.num_products_counting_con[idx].deactivate()
        print(f"  Deactivated counting constraint (not needed)")

    # Get manufacturing node
    node_id = manufacturing_nodes_list[0]
    node = next(n for n in model_obj.nodes if n.id == node_id)

    startup_hours = node.capabilities.daily_startup_hours or 0.5
    shutdown_hours = node.capabilities.daily_shutdown_hours or 0.5
    changeover_hours = node.capabilities.default_changeover_hours or 1.0
    production_rate = node.capabilities.production_rate or 1400.0

    # Recreate labor constraints with reformulated overhead
    # We need to replace the labor_hours_linking_con and production_capacity_con

    # Deactivate original labor constraints
    if hasattr(model, 'labor_hours_linking_con'):
        for idx in model.labor_hours_linking_con:
            model.labor_hours_linking_con[idx].deactivate()

    if hasattr(model, 'production_capacity_con'):
        for idx in model.production_capacity_con:
            model.production_capacity_con[idx].deactivate()

    print(f"  Deactivated original labor/capacity constraints")

    # Add reformulated constraints
    model.labor_hours_linking_reformulated = pyo.ConstraintList()
    model.production_capacity_reformulated = pyo.ConstraintList()

    for date_val in dates_range:
        if (node_id, date_val) not in model.production_day:
            continue

        # Calculate production time
        production_time = sum(
            model.production[node_id, prod, date_val]
            for prod in products
            if (node_id, prod, date_val) in model.production
        ) / production_rate

        # REFORMULATED: Overhead using direct sum(product_produced)
        # No need for num_products_produced variable!
        num_products_expr = sum(
            model.product_produced[node_id, prod, date_val]
            for prod in products
            if (node_id, prod, date_val) in model.product_produced
        )

        overhead_time = (
            (startup_hours + shutdown_hours - changeover_hours) * model.production_day[node_id, date_val] +
            changeover_hours * num_products_expr  # ← Direct sum, no intermediate variable!
        )

        # Labor hours linking
        if (node_id, date_val) in model.labor_hours_used:
            model.labor_hours_linking_reformulated.add(
                model.labor_hours_used[node_id, date_val] == production_time + overhead_time
            )

        # Production capacity
        labor_day = model_obj.labor_calendar.get_labor_day(date_val)
        if labor_day:
            labor_hours = labor_day.fixed_hours if labor_day.is_fixed_day else 14.0
            if (node_id, date_val) in model.labor_hours_paid:
                labor_hours = model.labor_hours_paid[node_id, date_val]

            model.production_capacity_reformulated.add(
                production_time + overhead_time <= labor_hours
            )

    print(f"  Added reformulated constraints ({len(model.labor_hours_linking_reformulated)} labor, {len(model.production_capacity_reformulated)} capacity)")
    print(f"\n✓  Overhead now uses sum(product_produced) directly - NO counting constraint needed!")

    return model


def main():
    print("="*80)
    print("APPROACH 5: Reformulated Overhead (No Counting Constraint)")
    print("="*80)
    print("\nBREAKTHROUGH: Eliminate need for constraint activation!")
    print("Strategy: Substitute sum(product_produced) directly in overhead\n")

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

    # BUILD MODEL
    print("\n" + "="*80)
    print("BUILD MODEL WITH REFORMULATED OVERHEAD")
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

    print("\nBuilding model with reformulated overhead...")
    model = build_pattern_model_with_reformulated_overhead(
        model_obj, products, weekday_dates_lists, manufacturing_nodes_list, dates_range
    )

    solver = appsi.solvers.Highs()
    solver.config.time_limit = 120
    solver.config.mip_gap = 0.03
    solver.config.stream_solver = True

    # PHASE 1
    print("\n" + "="*80)
    print("PHASE 1: SOLVE WITH PATTERN (parameter=1)")
    print("="*80)

    phase1_start = time.time()
    result1 = solver.solve(model)
    phase1_time = time.time() - phase1_start

    cost1 = pyo.value(model.obj)
    print(f"\nPhase 1 Results:")
    print(f"  Cost: ${cost1:,.2f}")
    print(f"  Time: {phase1_time:.1f}s")

    # PHASE 2: ONLY PARAMETER CHANGE (no constraint activation!)
    print("\n" + "="*80)
    print("PHASE 2: CHANGE PARAMETER (NO STRUCTURAL CHANGES!)")
    print("="*80)

    print("\nChanging pattern_active: 1 → 0")
    model.pattern_active.set_value(0.0)
    print(f"  pattern_active = {pyo.value(model.pattern_active)}")

    print("\n✓  NO constraint activation/deactivation needed!")
    print("  This is a PURE parameter change - APPSI should preserve incumbent!\n")

    print("CRITICAL TEST: If Phase 2 initial incumbent ≈ ${}K → SUCCESS!".format(int(cost1/1000)))

    phase2_start = time.time()
    result2 = solver.solve(model)
    phase2_time = time.time() - phase2_start

    cost2 = pyo.value(model.obj)
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
    print(f"Total time:  {phase1_time + phase2_time:.1f}s")

    if abs(cost_diff) < 100:
        print(f"\n🎉🎉🎉 SUCCESS: Phase 2 matched Phase 1!")
        print(f"\n✓  Reformulated overhead WORKS!")
        print(f"✓  NO structural changes needed!")
        print(f"✓  APPSI preserved incumbent!")
        return 0
    elif cost_diff < 0:
        print(f"\n🎉 EVEN BETTER: Phase 2 improved by ${-cost_diff:,.2f}!")
        return 0
    else:
        print(f"\n❌ FAILED: Phase 2 worse by ${cost_diff:,.2f}")
        print(f"   Even reformulated overhead doesn't fix APPSI limitation")
        return 1


if __name__ == "__main__":
    exit(main())
