#!/usr/bin/env python3
"""
Test for labor constraint violations.

Issue found: 12-week solve shows a day with 35 labor hours!
Maximum should be ~14 hours (12 fixed + 2 overtime on weekdays).

This test will find which day(s) violate labor constraints.
"""

import sys
from pathlib import Path
from datetime import timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.parsers.inventory_parser import InventoryParser
from tests.conftest import create_test_products


def main():
    print("="*80)
    print("LABOR CONSTRAINT VIOLATION TEST")
    print("="*80)

    # Load data
    parser = MultiFileParser(
        forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
        network_file='data/examples/Network_Config.xlsx',
        inventory_file='data/examples/inventory_latest.XLSX'
    )

    forecast, locations, routes, labor_calendar, truck_schedules, cost_structure = parser.parse_all()

    inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
    inventory_snapshot = inv_parser.parse()

    # Test with 12-week horizon
    planning_start = inventory_snapshot.snapshot_date
    planning_end = planning_start + timedelta(weeks=12)

    print(f"\nPlanning: {planning_start} to {planning_end} (12 weeks)")

    # Convert
    from src.models.location import LocationType
    mfg = [loc for loc in locations if loc.type == LocationType.MANUFACTURING][0]

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(mfg, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_trucks = converter.convert_truck_schedules(truck_schedules, mfg.id)

    products = create_test_products(
        sorted(set(e.product_id for e in forecast.entries
                  if planning_start <= e.forecast_date <= planning_end))
    )

    # Build model
    print(f"\nBuilding model...")
    model = SlidingWindowModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=planning_start,
        end_date=planning_end,
        truck_schedules=unified_trucks,
        initial_inventory=inventory_snapshot.to_optimization_dict(),
        inventory_snapshot_date=inventory_snapshot.snapshot_date,
        allow_shortages=True,
        use_pallet_tracking=True,
        use_truck_pallet_tracking=True
    )

    # Solve
    print(f"\nSolving...")
    result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.02)
    solution = model.get_solution()

    # Validate labor hours
    print(f"\n" + "="*80)
    print(f"LABOR HOURS VALIDATION")
    print(f"="*80)

    violations = []
    max_hours_seen = 0

    for date, labor_breakdown in solution.labor_hours_by_date.items():
        total_hours = labor_breakdown.used

        # Get expected max for this day
        labor_day = labor_calendar.get_labor_day(date)
        if labor_day:
            if labor_day.is_fixed_day:
                # Weekday: 12 fixed + 2 overtime = 14 max
                max_allowed = labor_day.fixed_hours + labor_day.overtime_hours
            else:
                # Weekend: 8 overtime max
                max_allowed = labor_day.overtime_hours
        else:
            max_allowed = 14  # Default

        if total_hours > max_hours_seen:
            max_hours_seen = total_hours

        # Check for violation
        if total_hours > max_allowed + 0.1:  # Allow small numerical tolerance
            violations.append({
                'date': date,
                'hours': total_hours,
                'max_allowed': max_allowed,
                'excess': total_hours - max_allowed,
                'is_weekend': not labor_day.is_fixed_day if labor_day else False
            })

    print(f"\nLabor hours statistics:")
    print(f"  Days with labor: {len(solution.labor_hours_by_date)}")
    print(f"  Max hours seen: {max_hours_seen:.1f}")
    print(f"  Violations found: {len(violations)}")

    if violations:
        print(f"\n❌ LABOR CONSTRAINT VIOLATIONS:")
        for v in violations[:10]:
            day_type = "Weekend" if v['is_weekend'] else "Weekday"
            print(f"  {v['date']} ({day_type}): {v['hours']:.1f} hours (max={v['max_allowed']:.1f}, excess={v['excess']:.1f})")

        print(f"\n🔍 BUG FOUND:")
        print(f"   Production capacity constraint is not limiting labor hours correctly!")
        print(f"   Model is using MORE hours than available on some days.")

        return violations
    else:
        print(f"\n✅ All days respect labor constraints")
        return []


if __name__ == "__main__":
    violations = main()

    if violations:
        print(f"\n" + "="*80)
        print(f"FAIL: Found {len(violations)} labor constraint violations")
        print(f"="*80)
        sys.exit(1)
    else:
        print(f"\n" + "="*80)
        print(f"PASS: All labor constraints respected")
        print(f"="*80)
        sys.exit(0)
