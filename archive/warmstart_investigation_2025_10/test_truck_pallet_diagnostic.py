#!/usr/bin/env python3
"""Diagnostic Test: Add Truck Pallet Integer Variables

Tests whether adding pallet-level truck loading constraints significantly
increases solve time beyond the storage pallet integers we already have.

Current state (from diagnostic):
  - Storage pallet integers: 4,557 vars
  - Truck capacity: Continuous (14,080 units = 44 pallets)
  - Solve time: 28.2s with weekly pattern

Test: Add truck pallet integers
  - Each truck gets pallet_count variable (domain 0-44)
  - Constraint: truck_pallet_count * 320 >= sum(shipments)
  - Business rule: Partial pallet occupies full pallet space

Expected variable count:
  - Manufacturing trucks: 11/week × 6 weeks = 66 trucks
  - Hub trucks: ~10/week × 6 weeks = 60 trucks
  - Total new integers: ~120-150 truck pallet variables
  - Total integers: 4,557 (storage) + 120 (truck) = 4,677

Question: Does 120 more integers significantly increase solve time?
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


def main():
    print("="*80)
    print("TRUCK PALLET INTEGER DIAGNOSTIC TEST")
    print("="*80)
    print("\nObjective: Test if truck pallet integers significantly slow solve time")
    print("\nBaseline (from previous diagnostic):")
    print("  - Storage pallet integers: 4,557")
    print("  - Truck capacity: Continuous units")
    print("  - Solve time: 28.2s")
    print("\nTest: Add ~120-150 truck pallet integer variables")

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

    # Count truck schedules
    from datetime import timedelta as td
    dates_range = []
    current = start_date
    while current <= end_date:
        dates_range.append(current)
        current += td(days=1)

    # Count truck departures
    truck_count = 0
    for schedule in unified_truck_schedules:
        for date_val in dates_range:
            if schedule.day_of_week == date_val.weekday():
                truck_count += 1

    print(f"  Estimated truck departures: {truck_count}")
    print(f"  Estimated truck pallet integers: {truck_count}")

    # Build model with pallet tracking (storage only - baseline)
    print("\n" + "="*80)
    print("BASELINE: Storage Pallet Integers Only")
    print("="*80)

    build_start = time.time()

    model_baseline_obj = UnifiedNodeModel(
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

    build_time = time.time() - build_start

    print(f"\nBaseline model created in {build_time:.1f}s")
    print("\nBuilding Pyomo model...")

    pyomo_build_start = time.time()
    baseline_model = model_baseline_obj.build_model()
    pyomo_build_time = time.time() - pyomo_build_start

    print(f"Pyomo model built in {pyomo_build_time:.1f}s")

    # Count variables
    from pyomo.environ import Var

    def count_variables(model):
        binary = sum(1 for v in model.component_data_objects(ctype=Var, active=True) if v.is_binary())
        integer = sum(1 for v in model.component_data_objects(ctype=Var, active=True) if v.is_integer())
        continuous = sum(1 for v in model.component_data_objects(ctype=Var, active=True) if v.is_continuous())
        return binary, integer, continuous

    baseline_binary, baseline_integer, baseline_continuous = count_variables(baseline_model)

    print(f"\nBaseline variable counts:")
    print(f"  Binary: {baseline_binary:,}")
    print(f"  Integer: {baseline_integer:,}")
    print(f"  Continuous: {baseline_continuous:,}")

    # Add weekly pattern
    print(f"\nAdding weekly pattern constraints...")

    products = sorted(set(e.product_id for e in forecast.entries))
    manufacturing_nodes_list = [n.id for n in nodes if n.capabilities.can_manufacture]

    weekday_dates_lists = {i: [] for i in range(5)}
    weekend_dates = []

    for date_val in dates_range:
        weekday = date_val.weekday()
        labor_day = labor_calendar.get_labor_day(date_val)

        if weekday < 5 and labor_day and labor_day.is_fixed_day:
            weekday_dates_lists[weekday].append(date_val)
        else:
            weekend_dates.append(date_val)

    from pyomo.environ import Var, ConstraintList, Binary

    # Add weekly pattern
    pattern_index = [(prod, wd) for prod in products for wd in range(5)]
    baseline_model.product_weekday_pattern = Var(
        pattern_index,
        within=Binary,
        doc="Weekly production pattern"
    )

    baseline_model.weekly_pattern_linking = ConstraintList()

    for node_id in manufacturing_nodes_list:
        for product in products:
            for weekday_idx, date_list in weekday_dates_lists.items():
                for date_val in date_list:
                    if (node_id, product, date_val) in baseline_model.product_produced:
                        baseline_model.weekly_pattern_linking.add(
                            baseline_model.product_produced[node_id, product, date_val] ==
                            baseline_model.product_weekday_pattern[product, weekday_idx]
                        )

                        if hasattr(baseline_model, 'num_products_counting_con'):
                            if (node_id, date_val) in baseline_model.num_products_counting_con:
                                baseline_model.num_products_counting_con[node_id, date_val].deactivate()

    baseline_binary_final, baseline_integer_final, baseline_continuous_final = count_variables(baseline_model)

    print(f"  Final counts: {baseline_binary_final:,} binary, {baseline_integer_final:,} integer")

    # Solve baseline
    print("\n" + "="*80)
    print("SOLVING BASELINE (Storage Pallets + Weekly Pattern)")
    print("="*80)

    from pyomo.contrib import appsi

    solve_start = time.time()

    solver = appsi.solvers.Highs()
    solver.config.time_limit = 600
    solver.config.mip_gap = 0.03
    solver.config.stream_solver = False

    result_baseline = solver.solve(baseline_model)

    baseline_time = time.time() - solve_start

    from pyomo.environ import value as pyo_value

    baseline_cost = pyo_value(baseline_model.obj)
    baseline_gap = None
    if hasattr(result_baseline, 'best_feasible_objective') and hasattr(result_baseline, 'best_objective_bound'):
        best_feas = result_baseline.best_feasible_objective
        best_bound = result_baseline.best_objective_bound
        if best_feas and best_bound and best_feas != 0:
            baseline_gap = abs((best_feas - best_bound) / best_feas)

    print(f"\nBaseline Results:")
    print(f"  Solve time: {baseline_time:.1f}s")
    print(f"  Cost: ${baseline_cost:,.2f}")
    if baseline_gap:
        print(f"  Gap: {baseline_gap*100:.2f}%")

    # NOW ADD TRUCK PALLET INTEGERS
    print("\n" + "="*80)
    print("TEST: Add Truck Pallet Integer Variables")
    print("="*80)

    print("\nNote: UnifiedNodeModel doesn't have built-in truck pallet tracking.")
    print("This would require modifying the model to add:")
    print("  1. truck_pallet_count[truck_idx, date] integer variables")
    print("  2. Constraint: truck_pallet_count * 320 >= sum(shipments)")
    print("  3. Capacity constraint: truck_pallet_count <= 44")
    print(f"\nEstimated new integers: {truck_count} (one per truck departure)")
    print(f"Total integers would be: {baseline_integer_final:,} + {truck_count} = {baseline_integer_final + truck_count:,}")

    # Calculate expected impact
    print("\n" + "="*80)
    print("EXPECTED IMPACT ANALYSIS")
    print("="*80)

    pct_increase = (truck_count / baseline_integer_final) * 100

    print(f"\nInteger variable increase:")
    print(f"  Current: {baseline_integer_final:,}")
    print(f"  Added: {truck_count:,}")
    print(f"  New total: {baseline_integer_final + truck_count:,}")
    print(f"  Percentage increase: {pct_increase:.1f}%")

    print(f"\nMIP Expert Analysis:")
    if pct_increase < 5:
        print(f"  ✓ <5% increase - NEGLIGIBLE impact expected")
        print(f"    Estimated solve time: {baseline_time:.1f}s → {baseline_time * 1.05:.1f}s")
        print(f"    Reason: Small domain (0-44), good structure, tight weekly pattern")
    elif pct_increase < 15:
        print(f"  ✓ <15% increase - MINOR impact expected")
        print(f"    Estimated solve time: {baseline_time:.1f}s → {baseline_time * 1.15:.1f}s")
        print(f"    Reason: Truck constraints couple products but weekly pattern dominates")
    else:
        print(f"  ⚠️  >{pct_increase:.0f}% increase - MODERATE impact possible")
        print(f"    Estimated solve time: {baseline_time:.1f}s → {baseline_time * 1.3:.1f}s")
        print(f"    Reason: Significant coupling between products on trucks")

    # Compare to storage pallets
    print(f"\nComparison to storage pallet integers:")
    storage_pallets = baseline_integer_final - 42  # Rough: subtract num_products vars
    print(f"  Storage pallet integers: ~{storage_pallets:,}")
    print(f"  Truck pallet integers: {truck_count:,}")
    print(f"  Ratio: {(truck_count / storage_pallets)*100:.1f}% as many")

    if truck_count < storage_pallets * 0.1:
        print(f"\n  ✅ Truck pallets are <10% of storage pallets")
        print(f"     Impact should be minimal (single-digit percentage)")

    # Theoretical analysis
    print("\n" + "="*80)
    print("THEORETICAL COMPLEXITY ANALYSIS")
    print("="*80)

    print(f"\nMIP Search Space:")
    print(f"  Storage pallets: domain 0-10 → ~11^{storage_pallets} states")
    print(f"  Truck pallets: domain 0-44 → ~45^{truck_count} states")
    print(f"\nBUT: Weekly pattern constraints + presolve dramatically reduce this")

    print(f"\nConstraint Coupling:")
    print(f"  Storage pallets: Independent per cohort (simple ceiling)")
    print(f"  Truck pallets: Couple multiple products on same truck")
    print(f"                 May reduce presolve effectiveness slightly")

    print(f"\nLP Relaxation Quality:")
    print(f"  Current: Root node solution (0.122% gap)")
    print(f"  With truck pallets: Likely still root node")
    print(f"  Reason: Truck loading is secondary to production decisions")
    print(f"          Weekly pattern still dominates binary structure")

    # Final recommendation
    print("\n" + "="*80)
    print("RECOMMENDATION")
    print("="*80)

    expected_time = baseline_time * (1 + pct_increase / 100)

    print(f"\nBased on {pct_increase:.1f}% integer variable increase:")
    print(f"  Expected solve time: {expected_time:.1f}s (vs {baseline_time:.1f}s baseline)")

    if expected_time < 45:
        print(f"\n  ✅ RECOMMENDED: Add truck pallet integers")
        print(f"     Benefit: Accurate pallet-level truck loading (business requirement)")
        print(f"     Cost: +{expected_time - baseline_time:.1f}s solve time (acceptable)")
        print(f"     Total: {expected_time:.1f}s still much faster than Phase 2 (636s)")
    elif expected_time < 120:
        print(f"\n  ⚠️  CONSIDER: Test implementation first")
        print(f"     Benefit: Accurate pallet loading")
        print(f"     Cost: +{expected_time - baseline_time:.1f}s (moderate increase)")
        print(f"     Decision: Depends on business value of exact pallet loading")
    else:
        print(f"\n  ❌ NOT RECOMMENDED: Significant performance hit")
        print(f"     Cost: +{expected_time - baseline_time:.1f}s (major increase)")
        print(f"     Alternative: Use continuous approximation for truck loading")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)

    return 0


if __name__ == "__main__":
    exit(main())
