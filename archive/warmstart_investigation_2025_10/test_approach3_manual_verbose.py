#!/usr/bin/env python3
"""Test Approach 3: Manual Solution Preservation with Detailed Diagnostics

This test manually saves and restores ALL variable values, including
num_products_produced, with detailed logging to verify the warmstart
is actually being passed to the solver.
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


def save_all_variable_values(model):
    """Save ALL variable values to a dictionary."""
    saved = {}
    count = 0

    for var in model.component_data_objects(pyo.Var, active=True):
        val = pyo.value(var)
        if val is not None:
            saved[var.name] = val
            count += 1

    return saved, count


def restore_all_variable_values(model, saved_values):
    """Restore ALL variable values from dictionary."""
    count = 0
    missing = 0

    for var in model.component_data_objects(pyo.Var, active=True):
        if var.name in saved_values:
            var.set_value(saved_values[var.name])
            count += 1
        else:
            missing += 1

    return count, missing


def calculate_num_products_produced(model, products, manufacturing_nodes_list, dates_range):
    """Calculate and set num_products_produced from product_produced."""
    if not hasattr(model, 'num_products_produced'):
        return 0

    count = 0
    for node_id in manufacturing_nodes_list:
        for date_val in dates_range:
            if (node_id, date_val) in model.num_products_produced:
                num_products = sum(
                    1 for product in products
                    if (node_id, product, date_val) in model.product_produced
                    and pyo.value(model.product_produced[node_id, product, date_val]) > 0.5
                )
                model.num_products_produced[node_id, date_val].set_value(num_products)
                count += 1

    return count


def main():
    print("="*80)
    print("APPROACH 3: Manual Solution Preservation (Detailed Diagnostics)")
    print("="*80)
    print("\nStrategy: Save all vars → modify model → restore all vars → solve")
    print("Hypothesis: APPSI should use restored variable values\n")

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
    print("BUILD SINGLE MODEL INSTANCE")
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

    # PHASE 1: Solve with pattern
    print("\n" + "="*80)
    print("PHASE 1: SOLVE WITH PATTERN")
    print("="*80)

    phase1_start = time.time()
    result1 = solver.solve(pattern_model)
    phase1_time = time.time() - phase1_start

    cost1 = pyo.value(pattern_model.obj)
    print(f"\nPhase 1 Results:")
    print(f"  Cost: ${cost1:,.2f}")
    print(f"  Time: {phase1_time:.1f}s")

    # SAVE ALL VARIABLE VALUES
    print("\n" + "="*80)
    print("SAVING ALL VARIABLE VALUES")
    print("="*80)

    saved_values, num_saved = save_all_variable_values(pattern_model)
    print(f"  Saved {num_saved:,} variable values")

    # Calculate num_products_produced
    num_calculated = calculate_num_products_produced(
        pattern_model, products, manufacturing_nodes_list, dates_range
    )
    print(f"  Calculated {num_calculated} num_products_produced values")

    # Save again after calculation
    saved_values, num_saved = save_all_variable_values(pattern_model)
    print(f"  Re-saved {num_saved:,} variable values (including num_products)")

    # MODIFY MODEL
    print("\n" + "="*80)
    print("MODIFYING MODEL STRUCTURE")
    print("="*80)

    print("  Deactivating pattern constraints...")
    pattern_model.weekly_pattern_linking.deactivate()

    print("  Reactivating changeover constraints...")
    if hasattr(pattern_model, 'num_products_counting_con'):
        for idx in pattern_model.num_products_counting_con:
            pattern_model.num_products_counting_con[idx].activate()

    print("  Fixing pattern variables to 0...")
    for idx in pattern_model.product_weekday_pattern:
        pattern_model.product_weekday_pattern[idx].fix(0)

    # RESTORE ALL VARIABLE VALUES
    print("\n" + "="*80)
    print("RESTORING ALL VARIABLE VALUES")
    print("="*80)

    num_restored, num_missing = restore_all_variable_values(pattern_model, saved_values)
    print(f"  Restored {num_restored:,} variable values")
    if num_missing > 0:
        print(f"  Missing {num_missing} variables (not in saved dict)")

    # Verify objective value
    try:
        current_obj = pyo.value(pattern_model.obj)
        print(f"\n  Current objective value: ${current_obj:,.2f}")
        if abs(current_obj - cost1) < 1.0:
            print(f"  ✓  Matches Phase 1 cost (${cost1:,.2f})")
        else:
            print(f"  ⚠️  Differs from Phase 1 cost (${cost1:,.2f})")
            print(f"     Difference: ${abs(current_obj - cost1):,.2f}")
    except Exception as e:
        print(f"  ❌ Cannot evaluate objective: {e}")

    # PHASE 2: Re-solve
    print("\n" + "="*80)
    print("PHASE 2: RE-SOLVE WITH RESTORED VALUES")
    print("="*80)
    print(f"\nExpected: Should find incumbent at ${cost1:,.2f} or better")
    print("Watch solver output for initial incumbent...")

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
    print(f"Total time:  {phase1_time + phase2_time:.1f}s")

    if abs(cost_diff) < 10:
        print(f"\n✅ SUCCESS: Phase 2 matched Phase 1!")
        print(f"   Manual preservation WORKS")
    elif cost_diff < 0:
        print(f"\n✅ GREAT: Phase 2 improved by ${-cost_diff:,.2f}!")
        print(f"   Warmstart helped solver find better solution")
    else:
        print(f"\n❌ FAILURE: Phase 2 worse by ${cost_diff:,.2f}")
        print(f"   APPSI still not using restored values as warmstart")

    print(f"\n{'='*80}")
    print("APPROACH 3 TEST COMPLETE")
    print(f"{'='*80}")

    return 0


if __name__ == "__main__":
    exit(main())
