#!/usr/bin/env python3
"""Diagnostic Test: Isolate Pallet Integers vs Binary SKU Selectors

This test helps determine which variable type causes the performance bottleneck:
- 4,515 pallet integer variables (from pallet tracking), OR
- 210 binary SKU selector variables (from daily product_produced decisions)

Test Design:
-----------
Run Phase 1 with:
  - Weekly repeating pattern (reduces binary count: 210 → ~110)
  - Pallet-based costs (creates 4,515 integer pallet variables)

Expected Outcomes:
------------------
- If solves in <60s: Binary selectors are the bottleneck (pallet integers are OK)
- If timeout >300s: Pallet integers are the bottleneck (not binary selectors)

Comparison Matrix:
------------------
| Configuration        | Binary Vars | Integer Vars | Solve Time | Bottleneck? |
|----------------------|-------------|--------------|------------|-------------|
| Phase 1 current      | ~110        | 0            | ~70s       | N/A         |
| Phase 1 diagnostic   | ~110        | ~4,515       | ???s       | TEST THIS   |
| Phase 2 full binary  | ~280        | ~4,515       | ~636s      | N/A         |
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


def count_variables(model):
    """Count binary, integer, and continuous variables in a Pyomo model."""
    from pyomo.environ import Var

    binary_count = 0
    integer_count = 0
    continuous_count = 0

    for v in model.component_data_objects(ctype=Var, active=True):
        if v.is_binary():
            binary_count += 1
        elif v.is_integer():
            integer_count += 1
        elif v.is_continuous():
            continuous_count += 1

    return binary_count, integer_count, continuous_count


def main():
    print("="*80)
    print("PALLET INTEGER DIAGNOSTIC TEST")
    print("="*80)
    print("\nObjective: Isolate whether pallet integers or binary selectors cause")
    print("          the performance bottleneck in 6-week optimization")
    print("\nTest: Phase 1 with weekly pattern + pallet integers")
    print("      (110 binary vars + 4,515 integer vars)")

    # Load data
    print("\n" + "="*80)
    print("LOADING DATA")
    print("="*80)

    parser = MultiFileParser(
        forecast_file="data/examples/Gluten Free Forecast - Latest.xlsm",
        network_file="data/examples/Network_Config.xlsx",
        inventory_file="data/examples/inventory.XLSX",
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
        default_changeover_hours=0.5, production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    inventory_snapshot = parser.parse_inventory(snapshot_date=None)
    initial_inventory = inventory_snapshot.to_optimization_dict() if inventory_snapshot else None
    inventory_date = inventory_snapshot.snapshot_date if inventory_snapshot else None

    # Test 6-week horizon
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=6*7 - 1)

    print(f"\nConfiguration:")
    print(f"  Horizon: 6 weeks ({(end_date - start_date).days + 1} days)")
    print(f"  Timeout: 600s (10 minutes)")
    print(f"  Solver: appsi_highs")
    print(f"  Gap tolerance: 3%")

    # Verify pallet costs are configured
    print(f"\nCost Structure Verification:")
    print(f"  Frozen pallet fixed: ${cost_structure.storage_cost_fixed_per_pallet_frozen:.2f}")
    print(f"  Frozen pallet daily: ${cost_structure.storage_cost_per_pallet_day_frozen:.4f}")

    if cost_structure.storage_cost_fixed_per_pallet_frozen == 0.0 and \
       cost_structure.storage_cost_per_pallet_day_frozen == 0.0:
        print("\n  ❌ ERROR: No pallet costs configured!")
        print("  Cannot run diagnostic test without pallet tracking.")
        return 1

    print(f"  ✓ Pallet costs configured - Phase 1 will create pallet variables")

    # Build Phase 1 model with DIAGNOSTIC FLAG ENABLED
    print("\n" + "="*80)
    print("BUILDING PHASE 1 MODEL WITH PALLET TRACKING (DIAGNOSTIC MODE)")
    print("="*80)

    # Get manufacturing info for weekly pattern
    from datetime import timedelta as td
    products = sorted(set(e.product_id for e in forecast.entries))
    manufacturing_nodes = [n.id for n in nodes if n.capabilities.can_manufacture]

    # Build date range and categorize weekdays vs weekends
    dates_range = []
    current = start_date
    while current <= end_date:
        dates_range.append(current)
        current += td(days=1)

    weekday_dates_lists = {i: [] for i in range(5)}  # 0=Mon, 4=Fri
    weekend_dates = []

    for date_val in dates_range:
        weekday = date_val.weekday()
        labor_day = labor_calendar.get_labor_day(date_val)

        if weekday < 5 and labor_day and labor_day.is_fixed_day:
            weekday_dates_lists[weekday].append(date_val)
        else:
            weekend_dates.append(date_val)

    weekday_count = sum(len(dates) for dates in weekday_dates_lists.values())
    pattern_binary_vars = 25  # 5 products × 5 weekdays
    weekend_binary_vars = 5 * len(weekend_dates)
    total_phase1_binary = pattern_binary_vars + weekend_binary_vars

    print(f"\nExpected variable counts:")
    print(f"  Binary (weekly pattern): {total_phase1_binary} ({pattern_binary_vars} pattern + {weekend_binary_vars} weekends)")
    print(f"  Integer (pallet tracking): ~4,515 (estimated)")
    print(f"  Continuous: ~100,000 (estimated)")

    # Build model with pallet tracking
    print(f"\nBuilding UnifiedNodeModel with pallet-based costs...")

    build_start = time.time()

    model_phase1_obj = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,  # CRITICAL: Using ORIGINAL pallet-based costs
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

    build_time = time.time() - build_start

    print(f"\nUnifiedNodeModel object created in {build_time:.1f}s")

    # Build the Pyomo model
    print(f"\nBuilding Pyomo model...")
    pyomo_build_start = time.time()
    pyomo_model = model_phase1_obj.build_model()
    pyomo_build_time = time.time() - pyomo_build_start
    print(f"Pyomo model built in {pyomo_build_time:.1f}s")

    # Count variables in model BEFORE adding weekly pattern
    print(f"\nCounting variables in base model...")
    binary_before, integer_before, continuous_before = count_variables(pyomo_model)

    print(f"\n  Base model variable counts:")
    print(f"    Binary: {binary_before:,}")
    print(f"    Integer: {integer_before:,}")
    print(f"    Continuous: {continuous_before:,}")

    # Now add weekly pattern constraints
    print(f"\nAdding weekly pattern constraints...")

    from pyomo.environ import Var, ConstraintList, Binary, Constraint

    model = pyomo_model

    # Add weekly pattern binary variables
    model.product_weekday_pattern = Var(
        products,
        range(5),  # 0=Mon, 1=Tue, ..., 4=Fri
        domain=Binary,
        doc="Weekly production pattern: 1 if product produced on this weekday"
    )

    # Create linking constraints
    model.weekly_pattern_linking = ConstraintList()

    linked_count = 0
    for node_id in manufacturing_nodes:
        for product in products:
            for weekday_idx, date_list in weekday_dates_lists.items():
                for date_val in date_list:
                    if (node_id, product, date_val) in model.product_produced:
                        # Link this date's decision to the weekly pattern
                        model.weekly_pattern_linking.add(
                            model.product_produced[node_id, product, date_val] ==
                            model.product_weekday_pattern[product, weekday_idx]
                        )
                        linked_count += 1

                        # CRITICAL: Deactivate counting constraint for linked dates
                        # (conflicts with weekly pattern constraint)
                        if hasattr(model, 'num_products_counting_con'):
                            if (node_id, date_val) in model.num_products_counting_con:
                                model.num_products_counting_con[node_id, date_val].deactivate()

    print(f"  Added {linked_count} linking constraints")
    print(f"  Added {len(products) * 5} weekly pattern binary variables")

    # Count variables AFTER adding weekly pattern
    binary_after, integer_after, continuous_after = count_variables(pyomo_model)

    print(f"\n  Final model variable counts:")
    print(f"    Binary: {binary_after:,} (+{binary_after - binary_before:,})")
    print(f"    Integer: {integer_after:,} (no change)")
    print(f"    Continuous: {continuous_after:,} (+{continuous_after - continuous_before:,})")

    # Validate expectations
    print(f"\n" + "="*80)
    print("VALIDATION")
    print("="*80)

    validation_passed = True

    # Check pallet integer variables
    if integer_after < 1000:
        print(f"\n  ❌ FAILED: Expected ~4,515 integer variables, got {integer_after:,}")
        print(f"  Pallet tracking may not be enabled correctly")
        validation_passed = False
    else:
        print(f"\n  ✓ Pallet integer variables: {integer_after:,} (expected ~4,500)")

    # Check binary variable reduction
    if binary_after > 200:
        print(f"  ⚠️  WARNING: Binary count {binary_after:,} higher than expected (~110)")
    else:
        print(f"  ✓ Binary variables: {binary_after:,} (weekly pattern active)")

    if not validation_passed:
        print("\n  ❌ Validation failed - aborting test")
        return 1

    # Solve Phase 1
    print("\n" + "="*80)
    print("SOLVING PHASE 1 WITH PALLET TRACKING")
    print("="*80)
    print(f"\nConfiguration:")
    print(f"  Binary vars: {binary_after:,}")
    print(f"  Integer vars: {integer_after:,}")
    print(f"  Continuous vars: {continuous_after:,}")
    print(f"  Time limit: 600s (10 minutes)")
    print(f"  Gap tolerance: 3%")
    print(f"\nSolving...")

    solve_start = time.time()

    # Solve manually built model directly
    from pyomo.contrib import appsi
    solver = appsi.solvers.Highs()
    solver.config.time_limit = 600  # 10 minutes
    solver.config.mip_gap = 0.03  # 3%
    solver.config.stream_solver = True  # Show solver output (tee=True)

    solver_result = solver.solve(model)

    solve_time = time.time() - solve_start

    # Extract results
    from pyomo.environ import value as pyo_value, TerminationCondition

    status = str(solver_result.termination_condition)
    objective_value = pyo_value(model.obj)

    # Calculate gap if available
    gap = None
    if hasattr(solver_result, 'best_feasible_objective') and hasattr(solver_result, 'best_objective_bound'):
        best_feas = solver_result.best_feasible_objective
        best_bound = solver_result.best_objective_bound
        if best_feas is not None and best_bound is not None and best_feas != 0:
            gap = abs((best_feas - best_bound) / best_feas)

    # Results
    print("\n" + "="*80)
    print("DIAGNOSTIC RESULTS")
    print("="*80)

    print(f"\nPhase 1 with Weekly Pattern + Pallet Integers:")
    print(f"  Solve time: {solve_time:.1f}s")
    print(f"  Status: {status}")
    print(f"  Cost: ${objective_value:,.2f}")
    if gap:
        print(f"  Gap: {gap*100:.2f}%")

    # Comparison matrix
    print("\n" + "="*80)
    print("COMPARISON MATRIX")
    print("="*80)
    print(f"\n{'Configuration':<25} | {'Binary':<8} | {'Integer':<8} | {'Time':<8} | {'Gap':<6} | {'Cost':<12}")
    print("-" * 90)
    print(f"{'Phase 1 current':<25} | {110:<8,} | {0:<8,} | {'~70s':<8} | {'N/A':<6} | {'~$800k':<12}")
    print(f"{'Phase 1 diagnostic':<25} | {binary_after:<8,} | {integer_after:<8,} | {f'{solve_time:.0f}s':<8} | {f'{gap*100:.1f}%' if gap else 'N/A':<6} | {f'${objective_value/1000:.0f}k':<12}")
    print(f"{'Phase 2 full binary':<25} | {'~280':<8} | {'~4,515':<8} | {'~636s':<8} | {'~60%':<6} | {'~$1.9M':<12}")

    # Analysis
    print("\n" + "="*80)
    print("ANALYSIS")
    print("="*80)

    if solve_time < 60:
        print(f"\n✅ RESULT: Pallet integers are NOT the bottleneck!")
        print(f"\nPhase 1 with 4,515 pallet integer variables solved in {solve_time:.1f}s (<60s).")
        print(f"This indicates that integer variables perform well with the weekly pattern.")
        print(f"\n🔍 CONCLUSION: Binary SKU selectors are the performance bottleneck.")
        print(f"\nPhase 2's slow performance (~636s) is likely due to:")
        print(f"  - 280 binary product_produced variables (vs 110 in Phase 1)")
        print(f"  - Full combinatorial search space without weekly pattern constraint")
        print(f"\nRecommendation: Focus optimization efforts on reducing binary variable count")
        print(f"                or improving binary variable branching strategy.")
    elif solve_time < 300:
        print(f"\n⚠️  RESULT: Pallet integers have MODERATE impact")
        print(f"\nPhase 1 with 4,515 pallet integer variables solved in {solve_time:.1f}s.")
        print(f"This is slower than baseline (~70s) but faster than Phase 2 (~636s).")
        print(f"\n🔍 CONCLUSION: Both pallet integers AND binary selectors contribute to slowdown.")
        print(f"\nPhase 2's performance is affected by:")
        print(f"  - 4,515 pallet integer variables (adds {solve_time - 70:.0f}s)")
        print(f"  - Additional binary product_produced variables (adds ~{636 - solve_time:.0f}s)")
        print(f"\nRecommendation: Consider both pallet tracking optimization AND binary reduction.")
    else:
        print(f"\n✅ RESULT: Pallet integers ARE the bottleneck!")
        print(f"\nPhase 1 with 4,515 pallet integer variables took {solve_time:.1f}s (>{300}s).")
        print(f"This indicates that integer variables dominate the solve time.")
        print(f"\n🔍 CONCLUSION: Pallet integer variables are the primary performance bottleneck.")
        print(f"\nPhase 2's slow performance (~636s) is primarily due to:")
        print(f"  - 4,515 pallet_count integer variables")
        print(f"  - Binary variables have minimal additional impact")
        print(f"\nRecommendation: Focus on pallet tracking optimization:")
        print(f"  1. Aggregate pallet tracking (fewer nodes)")
        print(f"  2. Tighten pallet count bounds")
        print(f"  3. Alternative formulation (continuous + rounding)")
        print(f"  4. Consider if pallet-level precision is necessary")

    print("\n" + "="*80)
    print("DIAGNOSTIC TEST COMPLETE")
    print("="*80)

    return 0


if __name__ == "__main__":
    exit(main())
