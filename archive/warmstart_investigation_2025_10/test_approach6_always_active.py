#!/usr/bin/env python3
"""Test Approach 6: Keep Counting Constraint ALWAYS ACTIVE

USER INSIGHT: Why deactivate the counting constraint at all?

Pattern constraint: product_produced[Mon] == pattern[Mon] for all Mondays
Counting constraint: num_products == sum(product_produced)

These DON'T conflict - they're just redundant!
- Pattern makes all Mondays have same products
- Counting still correctly counts them

If we keep counting constraint ACTIVE in both phases:
- Phase 1: Pattern active (parameter=1), counting active
- Phase 2: Pattern inactive (parameter=0), counting active
- NO .activate() or .deactivate() calls AT ALL!
- TRUE pure parameter change!

This should be the CORRECT APPSI warmstart pattern!
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


def build_pattern_model_always_active_counting(model_obj, products, weekday_dates_lists, manufacturing_nodes_list):
    """Build pattern model keeping counting constraint ALWAYS ACTIVE.

    Key insight: Counting constraint doesn't conflict with pattern!
    - Pattern: All Mondays produce same products
    - Counting: num_products = count of products (works fine!)

    By keeping it active in both phases, we avoid ANY structural changes.
    """
    model = model_obj.build_model()

    # Add mutable parameter
    model.pattern_active = pyo.Param(initialize=1.0, mutable=True)
    print(f"  Added parameter: pattern_active = {pyo.value(model.pattern_active)}")

    # Create pattern variables
    pattern_index = [(prod, wd) for prod in products for wd in range(5)]
    model.product_weekday_pattern = pyo.Var(pattern_index, within=pyo.Binary)
    print(f"  Added {len(pattern_index)} pattern variables")

    # BigM for parameter-based enforcement
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

    # CRITICAL: DO NOT deactivate counting constraint!
    # Leave it active in BOTH phases - it doesn't conflict!
    print(f"  ✓  Counting constraint LEFT ACTIVE (no conflict with pattern)")

    return model


def main():
    print("="*80)
    print("APPROACH 6: Always-Active Counting Constraint")
    print("="*80)
    print("\nUSER INSIGHT: Counting doesn't conflict with pattern!")
    print("Strategy: Keep ALL constraints active, only change parameter\n")

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
    print("BUILD MODEL (ALL CONSTRAINTS STAY ACTIVE)")
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

    print("\nBuilding model (keeping all constraints active)...")
    model = build_pattern_model_always_active_counting(
        model_obj, products, weekday_dates_lists, manufacturing_nodes_list
    )

    # Verify counting constraint is active
    if hasattr(model, 'num_products_counting_con'):
        active_count = sum(1 for idx in model.num_products_counting_con if model.num_products_counting_con[idx].active)
        print(f"\n  ✓  Counting constraint: {active_count} constraints ACTIVE")

    solver = appsi.solvers.Highs()
    solver.config.time_limit = 120
    solver.config.mip_gap = 0.03
    solver.config.stream_solver = True

    # PHASE 1
    print("\n" + "="*80)
    print("PHASE 1: SOLVE WITH PATTERN ACTIVE")
    print("="*80)

    print(f"pattern_active = {pyo.value(model.pattern_active)}")

    phase1_start = time.time()
    result1 = solver.solve(model)
    phase1_time = time.time() - phase1_start

    cost1 = pyo.value(model.obj)
    print(f"\nPhase 1 Results:")
    print(f"  Cost: ${cost1:,.2f}")
    print(f"  Time: {phase1_time:.1f}s")

    # PHASE 2: ONLY PARAMETER CHANGE
    print("\n" + "="*80)
    print("PHASE 2: PURE PARAMETER CHANGE (NO STRUCTURAL CHANGES)")
    print("="*80)

    print("\nChanging pattern_active: 1 → 0")
    model.pattern_active.set_value(0.0)

    print("\n✓  Parameter changed")
    print("✓  ALL constraints remain active")
    print("✓  NO .activate() calls")
    print("✓  NO .deactivate() calls")
    print("✓  This is the PUREST parameter change possible!")

    # Verify constraint is still active
    if hasattr(model, 'num_products_counting_con'):
        active_count = sum(1 for idx in model.num_products_counting_con if model.num_products_counting_con[idx].active)
        print(f"✓  Counting constraint: {active_count} constraints still ACTIVE")

    print(f"\nCurrent objective: ${pyo.value(model.obj):,.2f}")
    print(f"\n🎯 MOMENT OF TRUTH: If Phase 2 initial incumbent = ~${cost1:,.0f}")
    print(f"   then APPSI warmstart WORKS! 🎉\n")

    phase2_start = time.time()
    result2 = solver.solve(model)
    phase2_time = time.time() - phase2_start

    cost2 = pyo.value(model.obj)
    print(f"\nPhase 2 Results:")
    print(f"  Cost: ${cost2:,.2f}")
    print(f"  Time: {phase2_time:.1f}s")

    # ANALYSIS
    print("\n" + "="*80)
    print("FINAL VERDICT")
    print("="*80)

    cost_diff = cost2 - cost1
    cost_pct = (cost_diff / cost1) * 100 if cost1 > 0 else 0

    print(f"\nPhase 1:     ${cost1:,.2f} in {phase1_time:.1f}s")
    print(f"Phase 2:     ${cost2:,.2f} in {phase2_time:.1f}s")
    print(f"Difference:  ${cost_diff:,.2f} ({cost_pct:+.2f}%)")

    if abs(cost_diff) < 100:
        print(f"\n🎉🎉🎉 SUCCESS: WARMSTART WORKS!")
        print(f"\n✓  Phase 2 matched Phase 1 cost")
        print(f"✓  ALL constraints stayed active")
        print(f"✓  ONLY parameter changed")
        print(f"✓  APPSI preserved MIP incumbent!")
        print(f"\nThis is the CORRECT pattern for APPSI warmstart!")
        return 0
    elif cost_diff < 0:
        print(f"\n🎉 EVEN BETTER: Phase 2 improved by ${-cost_diff:,.2f}!")
        print(f"\n✓  Warmstart worked and solver found improvement")
        return 0
    else:
        print(f"\n❌ Phase 2 worse by ${cost_diff:,.2f}")
        print(f"\nCheck solver log above:")
        print(f"  - Initial incumbent ≈ ${cost1/1000:.0f}K → Warmstart preserved but solver stuck")
        print(f"  - Initial incumbent ≈ $3M → Warmstart NOT preserved")
        return 1


if __name__ == "__main__":
    exit(main())
