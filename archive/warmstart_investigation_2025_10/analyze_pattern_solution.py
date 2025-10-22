#!/usr/bin/env python3
"""Analyze Pattern Solution to Understand Why It's a Poor Warmstart

Solves 4-week full pattern and inspects the actual pattern found.
Question: Is the pattern realistic (selective) or unrealistic (all products daily)?
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
    print("PATTERN SOLUTION ANALYSIS")
    print("="*80)
    print("\nObjective: Inspect what pattern the solver actually finds")
    print("Question: Is it realistic or does it force all products daily?\n")

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

    # Configure with staleness
    cost_structure = cost_structure_base.model_copy()
    cost_structure.freshness_incentive_weight = 0.05

    # Solve using the weekly pattern warmstart function (built-in)
    from src.optimization.unified_node_model import solve_weekly_pattern_warmstart

    print("Solving 4-week with weekly pattern constraint...")

    result = solve_weekly_pattern_warmstart(
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
        solver_name='appsi_highs',
        time_limit_phase1=120,
        time_limit_phase2=300,
        mip_gap=0.03,
        tee=False,
    )

    print(f"\nPattern solution found!")
    print(f"  Status: {result.status}")
    print(f"  Solve time: {result.solve_time:.1f}s")
    print(f"  Total cost: ${result.total_cost:,.2f}")

    # Extract and analyze the pattern
    print(f"\n{'='*80}")
    print("PATTERN ANALYSIS")
    print(f"{'='*80}")

    # Get production schedule from result
    if hasattr(result, 'production_schedule') and result.production_schedule:
        schedule = result.production_schedule

        # Analyze pattern by weekday
        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        pattern_by_weekday = {wd: {prod: [] for prod in products} for wd in range(5)}

        for batch in schedule.batches:
            if batch.quantity > 0:
                weekday = batch.production_date.weekday()
                if weekday < 5:
                    pattern_by_weekday[weekday][batch.product_id].append(batch.quantity)

        print("\nPattern Found (Products Produced Per Weekday):")
        print(f"\n{'Product':<40} {'Mon':<8} {'Tue':<8} {'Wed':<8} {'Thu':<8} {'Fri':<8}")
        print("-" * 80)

        for product in products:
            row = f"{product:<40}"
            for wd in range(5):
                if pattern_by_weekday[wd][product]:
                    row += f" {'YES':<8}"
                else:
                    row += f" {'NO':<8}"
            print(row)

        # Count how many products per weekday
        print(f"\n{'='*80}")
        print("PRODUCTS PER WEEKDAY")
        print(f"{'='*80}")

        for wd in range(5):
            products_on_day = sum(1 for prod in products if pattern_by_weekday[wd][prod])
            print(f"  {weekday_names[wd]}: {products_on_day}/5 products")

        total_prods = sum(
            1 for wd in range(5)
            for prod in products
            if pattern_by_weekday[wd][prod]
        )
        max_possible = 5 * 5  # 5 weekdays × 5 products
        pct = (total_prods / max_possible) * 100

        print(f"\n  Total: {total_prods}/{max_possible} product-weekday slots ({pct:.0f}%)")

        # DIAGNOSIS
        print(f"\n{'='*80}")
        print("DIAGNOSIS")
        print(f"{'='*80}")

        if total_prods == max_possible:
            print(f"\n❌ PROBLEM: Pattern forces ALL products EVERY weekday!")
            print(f"\nThis is unrealistic because:")
            print(f"  - No selectivity (defeats purpose of pattern)")
            print(f"  - Maximum changeovers")
            print(f"  - Poor warmstart quality for flexible model")
            print(f"\nWhy this happens:")
            print(f"  - Solver finds it's cheapest to spread demand across all days")
            print(f"  - No explicit cost for changeov ers")
            print(f"  - Pattern constraint doesn't prevent this")
        elif total_prods >= 20:  # 80%+
            print(f"\n⚠️  Pattern is DENSE: {total_prods}/25 slots used ({pct:.0f}%)")
            print(f"\nLimited selectivity - most products produced most days")
        else:
            print(f"\n✅ Pattern is SELECTIVE: {total_prods}/25 slots used ({pct:.0f}%)")
            print(f"\nGood pattern - clear production schedule")

        # Calculate average products per day
        avg_per_day = total_prods / 5
        print(f"\nAverage products per day: {avg_per_day:.1f}")

        if avg_per_day >= 4.5:
            print(f"  → Essentially producing everything (4.5-5 products/day)")
        elif avg_per_day >= 3:
            print(f"  → Moderate schedule (3-4 products/day)")
        else:
            print(f"  → Selective schedule (<3 products/day)")

    else:
        print("\n⚠️  Could not extract production schedule from result")

    print(f"\n{'='*80}")
    print("CONCLUSION")
    print(f"{'='*80}")

    print(f"\nPattern warmstart failed because:")
    print(f"  1. Pattern solver finds 'produce everything' is optimal")
    print(f"  2. This provides no guidance for flexible model")
    print(f"  3. Flexible model wants selective production")
    print(f"  4. Warmstart value = minimal")

    print(f"\nRecommendation:")
    print(f"  - Don't use pattern warmstart for full flexible")
    print(f"  - Use 1-week flexible directly (433s, proven)")
    print(f"  - OR use full pattern (21.5s, fastest)")

    return 0


if __name__ == "__main__":
    exit(main())
