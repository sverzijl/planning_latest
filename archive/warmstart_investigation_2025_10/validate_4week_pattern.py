#!/usr/bin/env python3
"""Simple Validation: What Pattern Does 4-Week Model Actually Find?

Just solve and report - no complex analysis.
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


def main():
    print("="*80)
    print("4-WEEK PATTERN VALIDATION")
    print("="*80)

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

    # Configure WITH staleness
    cost_structure = cost_structure_base.model_copy()
    cost_structure.freshness_incentive_weight = 0.05

    # Build date lists
    dates_range = []
    current = start_date
    while current <= end_date:
        dates_range.append(current)
        current += timedelta(days=1)

    weekday_dates_lists = {i: [] for i in range(5)}
    for date_val in dates_range:
        weekday = date_val.weekday()
        labor_day = labor_calendar.get_labor_day(date_val)
        if weekday < 5 and labor_day and labor_day.is_fixed_day:
            weekday_dates_lists[weekday].append(date_val)

    # Create model
    print("\nBuilding 4-week pattern model...")
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

    # Add pattern constraints
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

    print("Model built with pattern constraints")

    # Solve
    print("\nSolving...")
    solver = appsi.solvers.Highs()
    solver.config.time_limit = 300
    solver.config.mip_gap = 0.03
    solver.config.stream_solver = False

    result = solver.solve(model)

    print(f"\nSolved in {solver.config.time_limit or 0}s (or less)")
    print(f"Cost: ${pyo.value(model.obj):,.2f}")
    print(f"Status: {result.termination_condition}")

    # Extract pattern
    print("\n" + "="*80)
    print("PATTERN FOUND")
    print("="*80)

    weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']

    print(f"\n{'Product':<45} {'Mon':<6} {'Tue':<6} {'Wed':<6} {'Thu':<6} {'Fri':<6} {'Total':<6}")
    print("-" * 80)

    for product in products:
        row = f"{product:<45}"
        total_days = 0
        for wd in range(5):
            if (product, wd) in model.product_weekday_pattern:
                val = pyo.value(model.product_weekday_pattern[product, wd])
                if val > 0.5:
                    row += f" {'Y':<6}"
                    total_days += 1
                else:
                    row += f" {'N':<6}"
            else:
                row += f" {'-':<6}"
        row += f" {total_days}/5"
        print(row)

    # Summary
    total_slots_used = sum(
        1 for prod in products
        for wd in range(5)
        if (prod, wd) in model.product_weekday_pattern
        and pyo.value(model.product_weekday_pattern[prod, wd]) > 0.5
    )

    print(f"\n{'='*80}")
    print(f"SUMMARY: {total_slots_used}/25 product-weekday slots used ({total_slots_used/25*100:.0f}%)")

    if total_slots_used == 25:
        print("\n❌ ALL 5 products EVERY weekday (100% utilization)")
        print("   This is why warmstart didn't help!")
    elif total_slots_used >= 20:
        print(f"\n⚠️  Very dense pattern ({total_slots_used}/25 used)")
    else:
        print(f"\n✅ Selective pattern ({total_slots_used}/25 used)")

    print("="*80)

    return 0


if __name__ == "__main__":
    exit(main())
