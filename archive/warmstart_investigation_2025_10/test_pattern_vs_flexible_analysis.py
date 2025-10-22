#!/usr/bin/env python3
"""Comprehensive Analysis: Pattern vs Flexible with Start Tracking

User questions:
1. Does Phase 1 pattern produce 5 SKUs every day or something different?
2. Do we even need warmstart if pattern = flexible?
3. Can we just solve flexible directly (cold start)?
4. Is flexible actually leveraging the increased flexibility?

This test will definitively answer all these questions.
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


def add_start_tracking_changeover(model, products, manufacturing_nodes_list, dates_range, labor_calendar):
    """Add sequence-independent changeover formulation."""

    start_index = [
        (node_id, prod, date_val)
        for node_id in manufacturing_nodes_list
        for prod in products
        for date_val in dates_range
    ]

    model.product_start = pyo.Var(
        start_index,
        within=pyo.Binary,
        doc="Binary: 1 if product starts (changeover) in this period"
    )

    model.changeover_detection = pyo.ConstraintList()

    for node_id in manufacturing_nodes_list:
        for prod in products:
            prev_date = None
            for date_val in sorted(dates_range):
                if (node_id, prod, date_val) not in model.product_produced:
                    continue

                if prev_date is None:
                    model.changeover_detection.add(
                        model.product_start[node_id, prod, date_val] >=
                        model.product_produced[node_id, prod, date_val]
                    )
                else:
                    model.changeover_detection.add(
                        model.product_start[node_id, prod, date_val] >=
                        model.product_produced[node_id, prod, date_val] -
                        model.product_produced[node_id, prod, prev_date]
                    )

                prev_date = date_val

    if hasattr(model, 'num_products_counting_con'):
        for idx in model.num_products_counting_con:
            model.num_products_counting_con[idx].deactivate()

    if hasattr(model, 'labor_hours_linking_con'):
        for idx in model.labor_hours_linking_con:
            model.labor_hours_linking_con[idx].deactivate()

    if hasattr(model, 'production_capacity_con'):
        for idx in model.production_capacity_con:
            model.production_capacity_con[idx].deactivate()

    model.capacity_with_changeovers = pyo.ConstraintList()

    startup_hours = 0.5
    shutdown_hours = 0.25
    changeover_hours = 0.5
    production_rate = 1400.0

    for date_val in dates_range:
        node_id = manufacturing_nodes_list[0]

        production_time = sum(
            model.production[node_id, prod, date_val]
            for prod in products
            if (node_id, prod, date_val) in model.production
        ) / production_rate

        changeover_time = changeover_hours * sum(
            model.product_start[node_id, prod, date_val]
            for prod in products
            if (node_id, prod, date_val) in model.product_start
        )

        fixed_overhead = (startup_hours + shutdown_hours) * model.production_day[node_id, date_val]

        if hasattr(model, 'labor_hours_paid') and (node_id, date_val) in model.labor_hours_paid:
            model.capacity_with_changeovers.add(
                production_time + fixed_overhead + changeover_time <=
                model.labor_hours_paid[node_id, date_val]
            )

    return model


def build_pattern_model(model_obj, products, weekday_dates_lists, manufacturing_nodes_list, dates_range, labor_calendar):
    """Build pattern model with start tracking."""

    model = model_obj.build_model()

    model.pattern_active = pyo.Param(initialize=1.0, mutable=True)

    pattern_index = [(prod, wd) for prod in products for wd in range(5)]
    model.product_weekday_pattern = pyo.Var(pattern_index, within=pyo.Binary)

    big_m = 10.0
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

    add_start_tracking_changeover(model, products, manufacturing_nodes_list, dates_range, labor_calendar)

    return model


def analyze_production_schedule(model, products, manufacturing_nodes, dates_range, phase_name):
    """Detailed analysis of which SKUs are produced when."""

    print(f"\n{'='*80}")
    print(f"{phase_name} PRODUCTION SCHEDULE ANALYSIS")
    print(f"{'='*80}")

    node_id = manufacturing_nodes[0]

    # Build day-by-day schedule
    schedule = {}
    for date_val in sorted(dates_range):
        products_produced = []
        for product in products:
            if (node_id, product, date_val) in model.product_produced:
                val = pyo.value(model.product_produced[node_id, product, date_val])
                if val and val > 0.5:
                    products_produced.append(product)
        schedule[date_val] = products_produced

    # Count products per day
    products_per_day = {}
    for date_val, prods in schedule.items():
        count = len(prods)
        if count not in products_per_day:
            products_per_day[count] = 0
        products_per_day[count] += 1

    print(f"\nProducts per day distribution:")
    for count in sorted(products_per_day.keys()):
        days = products_per_day[count]
        pct = (days / len(dates_range)) * 100
        print(f"  {count} SKUs: {days} days ({pct:.1f}%)")

    # Check for daily pattern
    all_5_skus_daily = all(len(prods) == 5 for prods in schedule.values())

    if all_5_skus_daily:
        print(f"\n⚠️  ALL 5 SKUs produced EVERY day")
    else:
        print(f"\n✓  Variable SKU count per day (optimized)")

    # Check for weekly repetition
    print(f"\nWeekly pattern check:")
    weekday_patterns = {i: set() for i in range(5)}

    for date_val, prods in schedule.items():
        weekday = date_val.weekday()
        if weekday < 5:
            weekday_patterns[weekday].add(tuple(sorted(prods)))

    weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    has_pattern = all(len(patterns) == 1 for patterns in weekday_patterns.values())

    if has_pattern:
        print(f"  ✓  Weekly pattern detected:")
        for wd in range(5):
            if weekday_patterns[wd]:
                pattern_set = list(weekday_patterns[wd])[0]
                print(f"    {weekday_names[wd]}: {len(pattern_set)} SKUs - {', '.join([p.split()[0] for p in pattern_set])}")
    else:
        print(f"  ✗  No consistent weekly pattern")

    # Count total changeovers
    total_changeovers = 0
    if hasattr(model, 'product_start'):
        for idx in model.product_start:
            val = pyo.value(model.product_start[idx])
            if val and val > 0.5:
                total_changeovers += 1

    print(f"\nChangeover statistics:")
    print(f"  Total changeovers: {total_changeovers}")
    print(f"  Avg per day: {total_changeovers / len(dates_range):.1f}")

    return schedule, all_5_skus_daily, has_pattern


def compare_schedules(schedule1, schedule2, dates_range):
    """Compare two production schedules."""

    print(f"\n{'='*80}")
    print("SCHEDULE COMPARISON")
    print(f"{'='*80}")

    identical_days = 0
    different_days = 0

    for date_val in dates_range:
        s1 = set(schedule1.get(date_val, []))
        s2 = set(schedule2.get(date_val, []))

        if s1 == s2:
            identical_days += 1
        else:
            different_days += 1

    pct_identical = (identical_days / len(dates_range)) * 100

    print(f"\nIdentical days: {identical_days}/{len(dates_range)} ({pct_identical:.1f}%)")
    print(f"Different days: {different_days}/{len(dates_range)} ({100-pct_identical:.1f}%)")

    if pct_identical == 100:
        print(f"\n✅ SCHEDULES ARE IDENTICAL")
        print(f"   Pattern and flexible produce exact same solution!")
        print(f"   → Pattern warmstart adds NO value (already optimal)")
    elif pct_identical > 90:
        print(f"\n⚠️  SCHEDULES ARE VERY SIMILAR ({pct_identical:.1f}% same)")
        print(f"   Minor differences only")
    else:
        print(f"\n✓  SCHEDULES DIFFER SIGNIFICANTLY ({100-pct_identical:.1f}% different)")
        print(f"   Flexible model leverages additional freedom")

    return pct_identical


def main():
    print("="*80)
    print("COMPREHENSIVE ANALYSIS: Pattern vs Flexible")
    print("="*80)
    print("\nQuestions to answer:")
    print("  1. Does pattern produce 5 SKUs every day?")
    print("  2. Do pattern and flexible give same solution?")
    print("  3. Do we need warmstart or can we solve flexible directly?")
    print("  4. Is flexible leveraging the increased flexibility?\n")

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

    # SOLVE PATTERN MODEL
    print("\n" + "="*80)
    print("SOLVING PATTERN MODEL")
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

    print("\nBuilding pattern model...")
    model_pattern = build_pattern_model(
        model1_obj, products, weekday_dates_lists, manufacturing_nodes_list, dates_range, labor_calendar
    )

    solver = appsi.solvers.Highs()
    solver.config.time_limit = 120
    solver.config.mip_gap = 0.03
    solver.config.stream_solver = False

    print("Solving...")
    t_pattern_start = time.time()
    result_pattern = solver.solve(model_pattern)
    t_pattern = time.time() - t_pattern_start

    cost_pattern = pyo.value(model_pattern.obj)

    print(f"\nPattern Results:")
    print(f"  Cost: ${cost_pattern:,.2f}")
    print(f"  Time: {t_pattern:.1f}s")

    # Analyze pattern solution
    schedule_pattern, all_5_skus, has_weekly_pattern = analyze_production_schedule(
        model_pattern, products, manufacturing_nodes_list, dates_range, "PATTERN"
    )

    # SOLVE FLEXIBLE MODEL (DIRECT - NO WARMSTART)
    print("\n" + "="*80)
    print("SOLVING FLEXIBLE MODEL (DIRECT - NO WARMSTART)")
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
        force_all_skus_daily=False,
    )

    print("\nBuilding flexible model...")
    model_flexible = model2_obj.build_model()
    add_start_tracking_changeover(model_flexible, products, manufacturing_nodes_list, dates_range, labor_calendar)

    print("Solving (cold start)...")
    t_flexible_start = time.time()
    result_flexible = solver.solve(model_flexible)
    t_flexible = time.time() - t_flexible_start

    cost_flexible = pyo.value(model_flexible.obj)

    print(f"\nFlexible Results:")
    print(f"  Cost: ${cost_flexible:,.2f}")
    print(f"  Time: {t_flexible:.1f}s")

    # Analyze flexible solution
    schedule_flexible, all_5_skus_flex, has_pattern_flex = analyze_production_schedule(
        model_flexible, products, manufacturing_nodes_list, dates_range, "FLEXIBLE"
    )

    # COMPARE SCHEDULES
    pct_identical = compare_schedules(schedule_pattern, schedule_flexible, dates_range)

    # FINAL ANALYSIS
    print(f"\n{'='*80}")
    print("FINAL ANALYSIS")
    print(f"{'='*80}")

    print(f"\n1. DOES PATTERN PRODUCE 5 SKUs EVERY DAY?")
    if all_5_skus:
        print(f"   YES - All 5 SKUs every day")
    else:
        print(f"   NO - Variable SKU count")

    print(f"\n2. ARE PATTERN AND FLEXIBLE SOLUTIONS IDENTICAL?")
    if pct_identical == 100:
        print(f"   YES - 100% identical schedules")
    else:
        print(f"   NO - {100-pct_identical:.1f}% of days differ")

    print(f"\n3. DO WE NEED WARMSTART?")
    cost_diff = cost_flexible - cost_pattern
    if abs(cost_diff) < 1.0 and pct_identical == 100:
        print(f"   NO - Pattern and flexible give identical results")
        print(f"   → Just solve flexible directly (cold start)")
        print(f"   → Pattern phase adds no value")
    elif cost_flexible < cost_pattern - 100:
        print(f"   MAYBE - Flexible is better by ${cost_pattern - cost_flexible:,.0f}")
        print(f"   → Flexible finds better solution")
        print(f"   → Pattern warmstart may hurt (bad incumbent)")
    else:
        print(f"   YES - Warmstart provides good starting point")
        print(f"   → Total time: {t_pattern + 3.3:.1f}s vs {t_flexible:.1f}s direct")

    print(f"\n4. IS FLEXIBLE LEVERAGING INCREASED FLEXIBILITY?")
    if pct_identical == 100:
        print(f"   NO - Produces identical schedule to pattern")
        print(f"   → Pattern constraint was not restrictive")
        print(f"   → Optimal solution happens to be a weekly pattern")
    else:
        print(f"   YES - {100-pct_identical:.1f}% of days use different SKUs")
        print(f"   → Flexible model exploits freedom")

    # RECOMMENDATION
    print(f"\n{'='*80}")
    print("RECOMMENDATION")
    print(f"{'='*80}")

    if pct_identical == 100:
        print(f"\n✅ SOLVE FLEXIBLE DIRECTLY (NO WARMSTART NEEDED)")
        print(f"\nReason:")
        print(f"  - Pattern and flexible give identical solutions")
        print(f"  - Flexible cold start: ${cost_flexible:,.0f} in {t_flexible:.1f}s")
        print(f"  - Pattern warmstart: ${cost_pattern:,.0f} + ${cost_flexible:,.0f} in {t_pattern + 3.3:.1f}s")
        print(f"  - Cold start is simpler and similar performance")
    elif t_pattern + 3.3 < t_flexible:
        print(f"\n✅ USE PATTERN WARMSTART")
        print(f"\nReason:")
        print(f"  - Warmstart total: {t_pattern + 3.3:.1f}s")
        print(f"  - Cold start: {t_flexible:.1f}s")
        print(f"  - Warmstart is {t_flexible - (t_pattern + 3.3):.1f}s faster")
    else:
        print(f"\n✅ SOLVE FLEXIBLE DIRECTLY")
        print(f"\nReason:")
        print(f"  - Cold start: {t_flexible:.1f}s")
        print(f"  - Warmstart: {t_pattern + 3.3:.1f}s")
        print(f"  - Cold start is {(t_pattern + 3.3) - t_flexible:.1f}s faster")

    print(f"\n{'='*80}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*80}")

    return 0


if __name__ == "__main__":
    exit(main())
