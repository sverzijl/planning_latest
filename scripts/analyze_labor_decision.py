"""Analyze labor scheduling decisions from optimization results.

This script helps diagnose why the model prefers weekend production over
weekday overtime, even when overtime is cheaper.
"""

import sys
from pathlib import Path
from datetime import timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.parsers.multi_file_parser import MultiFileParser
from src.models.manufacturing import ManufacturingSite
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.unified_node_model import UnifiedNodeModel


def analyze_labor_decisions():
    """Analyze labor scheduling from real data optimization."""

    print("\n" + "="*80)
    print("LABOR SCHEDULING DECISION ANALYSIS")
    print("="*80)

    # Load data
    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Setup manufacturing site
    manufacturing_site = None
    for loc in locations:
        if loc.type == 'manufacturing':
            manufacturing_site = ManufacturingSite(
                id=loc.id, name=loc.name, type=loc.type,
                storage_mode=loc.storage_mode, capacity=loc.capacity,
                latitude=loc.latitude, longitude=loc.longitude,
                production_rate=1400.0
            )
            break

    # Convert to unified model format
    converter = LegacyToUnifiedConverter()
    nodes, unified_routes, unified_trucks = converter.convert_all(
        manufacturing_site, locations, routes,
        truck_schedules_list, forecast
    )

    # Use 2-week horizon for faster solve
    all_dates = [entry.forecast_date for entry in forecast.entries]
    start_date = min(all_dates)
    end_date = start_date + timedelta(weeks=2)

    print(f"\nPlanning horizon: {start_date} to {end_date} (2 weeks)")
    print(f"Products: {len(set(e.product_id for e in forecast.entries))}")
    print(f"Total demand: {sum(e.quantity for e in forecast.entries if e.forecast_date <= end_date):,.0f} units")

    # Create and solve model
    print("\nBuilding model...")
    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_trucks,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    print("Solving...")
    result = model.solve(time_limit_seconds=120, mip_gap=0.01)

    if not result.success:
        print(f"\n❌ Solve failed: {result.infeasibility_message}")
        return

    print(f"✅ Solved: {result.termination_condition}, Cost: ${result.objective_value:,.2f}")

    # Extract solution
    solution = model.get_solution()

    # Analyze daily labor decisions
    print("\n" + "="*80)
    print("DAILY LABOR ANALYSIS")
    print("="*80)

    production_by_date = solution.get('production_by_date_product', {})
    labor_breakdown = solution.get('labor_cost_breakdown', {})

    # Group by date
    daily_data = {}
    for (date, prod), qty in production_by_date.items():
        if date not in daily_data:
            daily_data[date] = {'products': [], 'total_units': 0}
        if qty > 100:
            daily_data[date]['products'].append((prod, qty))
            daily_data[date]['total_units'] += qty

    # Sort by date
    weekday_overtime_hours = 0
    weekend_hours = 0

    for date in sorted(daily_data.keys()):
        day_info = daily_data[date]
        labor_day = labor_calendar.get_labor_day(date)
        labor_info = labor_breakdown.get(date, {})

        day_name = date.strftime('%A')
        is_weekend = not labor_day.is_fixed_day if labor_day else False

        production_hours = day_info['total_units'] / 1400.0  # Assuming 1400 units/h
        num_products = len(day_info['products'])

        # Calculate overhead
        overhead = 1.0 if num_products == 1 else num_products
        total_hours = production_hours + overhead

        print(f"\n{date} ({day_name:9s}) - {'WEEKEND' if is_weekend else 'WEEKDAY'}:")
        print(f"  Products: {num_products} ({', '.join(p[:20] for p, q in day_info['products'][:3])}...)")
        print(f"  Units: {day_info['total_units']:,.0f}")
        print(f"  Production time: {production_hours:.2f}h")
        print(f"  Overhead time: {overhead:.2f}h")
        print(f"  Total time: {total_hours:.2f}h")

        if labor_info:
            fixed_hrs = labor_info.get('fixed_hours_used', 0)
            ot_hrs = labor_info.get('overtime_hours_used', 0)
            paid_hrs = labor_info.get('hours_paid', 0)
            cost = labor_info.get('total_cost', 0)

            print(f"  Fixed hours: {fixed_hrs:.2f}h")
            print(f"  Overtime hours: {ot_hrs:.2f}h")
            print(f"  Hours paid: {paid_hrs:.2f}h")
            print(f"  Labor cost: ${cost:,.2f}")

            if is_weekend:
                weekend_hours += paid_hrs
            else:
                weekday_overtime_hours += ot_hrs

        # Check capacity vs usage
        if labor_day:
            if labor_day.is_fixed_day:
                max_capacity = labor_day.fixed_hours + (labor_day.overtime_hours if hasattr(labor_day, 'overtime_hours') else 0)
                utilization = (total_hours / max_capacity * 100) if max_capacity > 0 else 0
                print(f"  Capacity: {max_capacity:.1f}h (utilization: {utilization:.1f}%)")

                if total_hours > labor_day.fixed_hours and ot_hrs == 0:
                    print(f"  ⚠️  WARNING: Total time {total_hours:.2f}h > fixed {labor_day.fixed_hours:.1f}h but NO OVERTIME!")
            else:
                print(f"  Capacity: Unlimited (premium rate: ${labor_day.non_fixed_rate:.2f}/h)")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Weekday overtime hours used: {weekday_overtime_hours:.2f}h (max available: 10h)")
    print(f"Weekend hours used: {weekend_hours:.2f}h")
    print()

    # Cost comparison
    weekday_ot_cost = weekday_overtime_hours * 660.0
    weekend_cost = weekend_hours * 1320.0

    print(f"Weekday overtime cost: ${weekday_ot_cost:,.2f}")
    print(f"Weekend cost: ${weekend_cost:,.2f}")
    print()

    if weekend_hours > 0 and weekday_overtime_hours < 10:
        potential_savings = min(weekend_hours, 10 - weekday_overtime_hours) * (1320.0 - 660.0)
        print(f"❌ SUBOPTIMAL: Could save ${potential_savings:,.2f} by shifting {min(weekend_hours, 10 - weekday_overtime_hours):.1f}h from weekend to overtime")
    else:
        print("✅ OPTIMAL: All available overtime used before weekends")

    print("\n" + "="*80)
    print("TOTAL COST BREAKDOWN")
    print("="*80)
    print(f"Labor cost: ${solution.get('total_labor_cost', 0):,.2f}")
    print(f"Production cost: ${solution.get('total_production_cost', 0):,.2f}")
    print(f"Transport cost: ${solution.get('total_transport_cost', 0):,.2f}")
    print(f"Holding cost: ${solution.get('total_holding_cost', 0):,.2f}")
    print(f"Total cost: ${solution.get('total_cost', 0):,.2f}")


if __name__ == "__main__":
    analyze_labor_decisions()
