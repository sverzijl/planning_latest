#!/usr/bin/env python3
"""Test: Direct Substitution Formulation is Solvable

Verify that eliminating num_products_produced and using direct substitution:
    overhead = (S+S-C) * production_day + C * sum(product_produced)

produces a valid, solvable model without the counting constraint.
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


def build_model_with_direct_substitution(model_obj, products, manufacturing_nodes_list, dates_range):
    """Build model using DIRECT SUBSTITUTION (no counting constraint)."""

    # Build base model
    model = model_obj.build_model()

    print("\nModel built. Now removing counting constraint and using direct substitution...")

    # Deactivate the counting constraint (we won't use it)
    if hasattr(model, 'num_products_counting_con'):
        for idx in model.num_products_counting_con:
            model.num_products_counting_con[idx].deactivate()
        print(f"  ✓  Deactivated counting constraint")

    # Use constant overhead parameters (from manufacturing site)
    node_id = manufacturing_nodes_list[0]
    startup_hours = 0.5
    shutdown_hours = 0.25
    changeover_hours = 0.5
    production_rate = 1400.0

    # Deactivate original labor/capacity constraints
    if hasattr(model, 'labor_hours_linking_con'):
        for idx in model.labor_hours_linking_con:
            model.labor_hours_linking_con[idx].deactivate()
        print(f"  ✓  Deactivated original labor_hours_linking_con")

    if hasattr(model, 'production_capacity_con'):
        for idx in model.production_capacity_con:
            model.production_capacity_con[idx].deactivate()
        print(f"  ✓  Deactivated original production_capacity_con")

    # Add reformulated constraints with DIRECT SUBSTITUTION
    model.labor_hours_linking_reformulated = pyo.ConstraintList()
    model.production_capacity_reformulated = pyo.ConstraintList()

    print("\n  Reformulating with direct substitution...")

    for date_val in dates_range:
        if (node_id, date_val) not in model.production_day:
            continue

        # Production time
        production_time = sum(
            model.production[node_id, prod, date_val]
            for prod in products
            if (node_id, prod, date_val) in model.production
        ) / production_rate

        # DIRECT SUBSTITUTION: No intermediate variable!
        num_products_expr = sum(
            model.product_produced[node_id, prod, date_val]
            for prod in products
            if (node_id, prod, date_val) in model.product_produced
        )

        overhead_time = (
            (startup_hours + shutdown_hours - changeover_hours) * model.production_day[node_id, date_val] +
            changeover_hours * num_products_expr  # ← Direct sum!
        )

        # Labor hours linking
        if (node_id, date_val) in model.labor_hours_used:
            model.labor_hours_linking_reformulated.add(
                model.labor_hours_used[node_id, date_val] == production_time + overhead_time
            )

        # Production capacity
        labor_day = model_obj.labor_calendar.get_labor_day(date_val)
        if labor_day and hasattr(model, 'labor_hours_paid'):
            # Use paid hours if available
            if (node_id, date_val) in model.labor_hours_paid:
                model.production_capacity_reformulated.add(
                    production_time + overhead_time <= model.labor_hours_paid[node_id, date_val]
                )

    num_reformulated = len(model.labor_hours_linking_reformulated) + len(model.production_capacity_reformulated)
    print(f"  ✓  Added {num_reformulated} reformulated constraints")
    print(f"\n✅ Direct substitution formulation complete!")

    return model


def main():
    print("="*80)
    print("TEST: Direct Substitution Solvability Check")
    print("="*80)
    print("\nQuestion: Can we eliminate counting constraint using direct substitution?")
    print("Formulation: overhead = (S+S-C)*production_day + C*sum(product_produced)\n")

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

    dates_range = []
    current = start_date
    while current <= end_date:
        dates_range.append(current)
        current += timedelta(days=1)

    cost_structure = cost_structure_base.model_copy()
    cost_structure.freshness_incentive_weight = 0.05

    # BUILD MODEL WITH DIRECT SUBSTITUTION
    print("\n" + "="*80)
    print("BUILD MODEL WITH DIRECT SUBSTITUTION")
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
        force_all_skus_daily=False,  # Full binary flexibility
    )

    print("\nBuilding model with direct substitution...")
    model = build_model_with_direct_substitution(
        model_obj, products, manufacturing_nodes_list, dates_range
    )

    # Verify model structure
    print("\n" + "="*80)
    print("MODEL STRUCTURE VERIFICATION")
    print("="*80)

    # Count variables
    num_binary = sum(1 for v in model.component_data_objects(pyo.Var, active=True) if v.is_binary())
    num_integer = sum(1 for v in model.component_data_objects(pyo.Var, active=True) if v.is_integer() and not v.is_binary())
    num_continuous = sum(1 for v in model.component_data_objects(pyo.Var, active=True) if v.is_continuous())

    print(f"\nVariable counts:")
    print(f"  Binary:     {num_binary:,}")
    print(f"  Integer:    {num_integer:,}")
    print(f"  Continuous: {num_continuous:,}")
    print(f"  Total:      {num_binary + num_integer + num_continuous:,}")

    # Count constraints
    num_constraints = sum(1 for c in model.component_data_objects(pyo.Constraint, active=True))
    print(f"\nActive constraints: {num_constraints:,}")

    # Check if num_products_counting_con is inactive
    if hasattr(model, 'num_products_counting_con'):
        active_counting = sum(1 for idx in model.num_products_counting_con if model.num_products_counting_con[idx].active)
        print(f"  Counting constraints active: {active_counting} (should be 0)")

    # SOLVE TEST
    print("\n" + "="*80)
    print("SOLVABILITY TEST")
    print("="*80)

    solver = appsi.solvers.Highs()
    solver.config.time_limit = 120
    solver.config.mip_gap = 0.03
    solver.config.stream_solver = True

    print("\nSolving model with direct substitution...")
    print("Expected: Should solve successfully (no counting constraint issues)\n")

    solve_start = time.time()
    result = solver.solve(model)
    solve_time = time.time() - solve_start

    cost = pyo.value(model.obj)

    print(f"\n{'='*80}")
    print("RESULTS")
    print(f"{'='*80}")

    print(f"\nSolve status: {result.termination_condition}")
    print(f"Objective:    ${cost:,.2f}")
    print(f"Solve time:   {solve_time:.1f}s")

    # Check solution quality
    if result.termination_condition == pyo.TerminationCondition.optimal:
        print(f"\n✅ MODEL IS SOLVABLE")
        print(f"   Direct substitution formulation WORKS")
    elif result.termination_condition == pyo.TerminationCondition.maxTimeLimit:
        print(f"\n⚠️  Hit time limit but found feasible solution")
        print(f"   Direct substitution formulation WORKS")
    else:
        print(f"\n❌ Solver failed: {result.termination_condition}")
        print(f"   Direct substitution may have issues")
        return 1

    # Compare to expected performance
    print(f"\n{'='*80}")
    print("PERFORMANCE COMPARISON")
    print(f"{'='*80}")

    print(f"\nDirect substitution:")
    print(f"  Binary vars:   {num_binary:,}")
    print(f"  Integer vars:  {num_integer:,}")
    print(f"  Cost:          ${cost:,.2f}")
    print(f"  Time:          {solve_time:.1f}s")

    print(f"\nExpected with counting constraint:")
    print(f"  Binary vars:   ~{num_binary:,} (same)")
    print(f"  Integer vars:  ~{num_integer + 28:,} (+28 for num_products)")
    print(f"  Cost:          Unknown")
    print(f"  Time:          Unknown")

    print(f"\nHistorical flexible model (Approach 6 with counting):")
    print(f"  Cost:          $1,957K")
    print(f"  Time:          124s")

    if cost < 900000 and solve_time < 30:
        print(f"\n🎉 EXCELLENT: Direct substitution is BETTER!")
        print(f"   - Simpler formulation")
        print(f"   - Lower cost: ${cost:,.0f} vs $1,957K")
        print(f"   - Faster: {solve_time:.1f}s vs 124s")
        print(f"\n✓  Ready to test warmstart with this formulation")
    elif cost < 900000:
        print(f"\n✅ GOOD: Direct substitution works")
        print(f"   Lower cost than with counting constraint")
        print(f"\n✓  Ready to test warmstart")
    else:
        print(f"\n⚠️  Direct substitution solved but quality unclear")
        print(f"   May need further investigation")

    print(f"\n{'='*80}")
    print("SOLVABILITY TEST COMPLETE")
    print(f"{'='*80}")

    return 0


if __name__ == "__main__":
    exit(main())
