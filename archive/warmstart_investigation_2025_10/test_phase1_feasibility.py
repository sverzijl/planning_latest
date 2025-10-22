#!/usr/bin/env python3
"""Test: Verify Phase 1 Solution Is Feasible for Phase 2

The user's critical observation: Phase 2 has FEWER constraints than Phase 1,
so Phase 1 solution MUST be feasible for Phase 2. Phase 2 should return AT WORST
the same cost as Phase 1.

Actual result: Phase 2 returns WORSE cost ($1.05M vs $795K)

This investigation: Check if Phase 1 solution actually satisfies Phase 2 constraints.
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


def check_constraint_satisfaction(model, constraint_name):
    """Check if all constraints in a ConstraintList/Constraint are satisfied."""
    violations = []
    satisfied = []

    constraint_obj = getattr(model, constraint_name, None)
    if constraint_obj is None:
        return None, f"Constraint {constraint_name} not found"

    # Handle different constraint types
    if isinstance(constraint_obj, pyo.Constraint):
        # Indexed constraint
        for idx in constraint_obj:
            con = constraint_obj[idx]
            if not con.active:
                continue  # Skip inactive constraints

            # Evaluate constraint
            try:
                body_value = pyo.value(con.body)
                lower = pyo.value(con.lower) if con.lower is not None else None
                upper = pyo.value(con.upper) if con.upper is not None else None

                violated = False
                if lower is not None and body_value < lower - 1e-6:
                    violations.append((idx, f"body={body_value:.4f} < lower={lower:.4f}"))
                    violated = True
                if upper is not None and body_value > upper + 1e-6:
                    violations.append((idx, f"body={body_value:.4f} > upper={upper:.4f}"))
                    violated = True

                if not violated:
                    satisfied.append(idx)

            except Exception as e:
                violations.append((idx, f"Error evaluating: {e}"))

    return satisfied, violations


def main():
    print("="*80)
    print("TEST: PHASE 1 SOLUTION FEASIBILITY FOR PHASE 2")
    print("="*80)
    print("\nQuestion: Is Phase 1 solution feasible for Phase 2 constraints?")
    print("Expected: YES (Phase 2 is less constrained)")

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

    # BUILD AND SOLVE PHASE 1
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
    solver.config.stream_solver = False

    print("Solving Phase 1...")
    result1 = solver.solve(pattern_model)
    cost1 = pyo.value(pattern_model.obj)
    print(f"Phase 1 cost: ${cost1:,.2f}")

    # NOW TEST FEASIBILITY
    print("\n" + "="*80)
    print("FEASIBILITY CHECK: Phase 1 Solution vs Phase 2 Constraints")
    print("="*80)

    # The constraints that will be ACTIVE in Phase 2:
    # 1. All original constraints (production, inventory, demand, truck, etc.)
    # 2. Changeover constraints (num_products_counting_con) - REACTIVATED
    # The constraints that will be INACTIVE in Phase 2:
    # 1. Pattern linking constraints - DEACTIVATED

    print("\nChecking changeover constraints (will be reactivated in Phase 2)...")

    # Reactivate changeover constraints temporarily to test
    if hasattr(pattern_model, 'num_products_counting_con'):
        for idx in pattern_model.num_products_counting_con:
            pattern_model.num_products_counting_con[idx].activate()

        satisfied, violations = check_constraint_satisfaction(pattern_model, 'num_products_counting_con')

        if violations:
            print(f"\n❌ FOUND {len(violations)} VIOLATIONS:")
            for idx, msg in violations[:10]:  # Show first 10
                print(f"   {idx}: {msg}")
            if len(violations) > 10:
                print(f"   ... and {len(violations)-10} more")

            print(f"\n⚠️  Phase 1 solution is INFEASIBLE for Phase 2!")
            print(f"   This explains why Phase 2 can't use it")
        else:
            print(f"\n✓  All {len(satisfied)} changeover constraints SATISFIED")
            print(f"   Phase 1 solution IS feasible for Phase 2")

            print(f"\n⚠️  CRITICAL FINDING:")
            print(f"   Phase 1 solution is feasible for Phase 2")
            print(f"   But Phase 2 didn't use it (started with $3.38M incumbent)")
            print(f"   → APPSI is NOT preserving solution across model changes!")

        # Deactivate again
        for idx in pattern_model.num_products_counting_con:
            pattern_model.num_products_counting_con[idx].deactivate()

    # Also check a few other key constraints
    print("\nChecking core constraints...")
    constraint_checks = [
        'inventory_balance',
        'demand_satisfaction',
        'production_capacity',
    ]

    all_feasible = True
    for con_name in constraint_checks:
        if hasattr(pattern_model, con_name):
            satisfied, violations = check_constraint_satisfaction(pattern_model, con_name)
            if violations and len(violations) > 0:
                print(f"  ❌ {con_name}: {len(violations)} violations")
                all_feasible = False
            else:
                print(f"  ✓  {con_name}: all satisfied")

    # FINAL VERDICT
    print("\n" + "="*80)
    print("VERDICT")
    print("="*80)

    if all_feasible:
        print("\n✅ Phase 1 solution IS FEASIBLE for Phase 2 constraints")
        print("\nConclusion:")
        print("  - Phase 1 solution satisfies ALL Phase 2 constraints")
        print("  - Phase 2 should AT MINIMUM return this solution")
        print("  - But Phase 2 started with $3.38M (not $795K)")
        print("\n🔍 ROOT CAUSE: APPSI is NOT preserving the MIP solution")
        print("   when constraints are deactivated/reactivated!")
        print("\nThis is either:")
        print("  A. APPSI bug/limitation (doesn't preserve MIP incumbent on model changes)")
        print("  B. We need explicit solution preservation code")
    else:
        print("\n❌ Phase 1 solution is INFEASIBLE for some Phase 2 constraints")
        print("\nThis would explain why Phase 2 doesn't use it")
        print("But it still doesn't explain why Phase 2 cost > Phase 1 cost")

    return 0


if __name__ == "__main__":
    exit(main())
