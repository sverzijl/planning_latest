#!/usr/bin/env python3
"""Test Approach 1: Non-APPSI SolverFactory with warmstart=True

Research indicates that SolverFactory('highs') uses a different interface
than APPSI and may properly generate warmstart files (.mst or similar).

This test uses the standard Pyomo SolverFactory interface.
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


def main():
    print("="*80)
    print("APPROACH 1: Non-APPSI SolverFactory with warmstart=True")
    print("="*80)
    print("\nStrategy: Use standard SolverFactory interface")
    print("Expected: May generate .mst file for warmstart\n")

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

    # Create standard solver (NOT APPSI)
    print("\nCreating SolverFactory('highs') solver...")
    try:
        solver = pyo.SolverFactory('highs')
        print("  ✓  SolverFactory('highs') available")
    except Exception as e:
        print(f"  ❌ SolverFactory('highs') not available: {e}")
        print("\nTrying alternative solver names...")
        for name in ['highs', 'highspy', 'asl:highs']:
            try:
                solver = pyo.SolverFactory(name)
                print(f"  ✓  SolverFactory('{name}') available")
                break
            except:
                print(f"  ❌ SolverFactory('{name}') not available")
                continue
        else:
            print("\n❌ No HiGHS SolverFactory interface available!")
            print("   APPSI is the only interface for HiGHS")
            return 1

    # PHASE 1: Build and solve pattern model
    print("\n" + "="*80)
    print("PHASE 1: SOLVE PATTERN MODEL")
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

    model1 = model1_obj.build_model()
    pattern_model = build_pattern_model(model1_obj, products, weekday_dates_lists, manufacturing_nodes_list)

    print("Solving Phase 1...")
    phase1_start = time.time()

    # Set solver options
    solver.options['time_limit'] = 120
    solver.options['mip_gap'] = 0.03

    result1 = solver.solve(pattern_model, tee=True)
    phase1_time = time.time() - phase1_start

    cost1 = pyo.value(pattern_model.obj)
    print(f"\nPhase 1 Results:")
    print(f"  Cost: ${cost1:,.2f}")
    print(f"  Time: {phase1_time:.1f}s")
    print(f"  Status: {result1.solver.termination_condition}")

    # PHASE 2: Build fresh flexible model
    print("\n" + "="*80)
    print("PHASE 2: BUILD FLEXIBLE MODEL (SEPARATE INSTANCE)")
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
        force_all_skus_daily=False,  # No pattern
    )

    model2 = model2_obj.build_model()

    # Transfer variable values from Phase 1
    print("\nTransferring variable values from Phase 1...")
    transfer_count = 0

    for var_name in dir(pattern_model):
        if var_name.startswith('_'):
            continue
        var1 = getattr(pattern_model, var_name, None)
        var2 = getattr(model2, var_name, None)

        if var1 is None or var2 is None:
            continue

        if isinstance(var1, pyo.Var):
            # Transfer indexed variable values
            for idx in var1:
                if idx in var2:
                    val = pyo.value(var1[idx])
                    if val is not None:
                        var2[idx].value = val
                        transfer_count += 1

    print(f"  Transferred {transfer_count} variable values")

    # SOLVE WITH WARMSTART=TRUE
    print("\n" + "="*80)
    print("PHASE 2: SOLVE WITH warmstart=True")
    print("="*80)
    print("\nDIAGNOSTIC: Watch for warmstart file generation or 'MIP start' message")

    phase2_start = time.time()
    result2 = solver.solve(model2, warmstart=True, tee=True)  # EXPLICIT warmstart flag
    phase2_time = time.time() - phase2_start

    cost2 = pyo.value(model2.obj)
    print(f"\nPhase 2 Results:")
    print(f"  Cost: ${cost2:,.2f}")
    print(f"  Time: {phase2_time:.1f}s")
    print(f"  Status: {result2.solver.termination_condition}")

    # ANALYSIS
    print("\n" + "="*80)
    print("RESULTS ANALYSIS")
    print("="*80)

    cost_diff = cost2 - cost1
    cost_pct = (cost_diff / cost1) * 100 if cost1 > 0 else 0

    print(f"\nPhase 1:     ${cost1:,.2f} in {phase1_time:.1f}s")
    print(f"Phase 2:     ${cost2:,.2f} in {phase2_time:.1f}s")
    print(f"Difference:  ${cost_diff:,.2f} ({cost_pct:+.2f}%)")

    if cost_diff <= 0:
        print(f"\n✅ SUCCESS: Phase 2 equal or better than Phase 1!")
        print(f"   warmstart=True WORKS with SolverFactory")
    else:
        print(f"\n❌ FAILURE: Phase 2 worse than Phase 1")
        print(f"   warmstart=True did NOT work properly")

    print(f"\n{'='*80}")
    print("APPROACH 1 TEST COMPLETE")
    print(f"{'='*80}")

    return 0


if __name__ == "__main__":
    exit(main())
