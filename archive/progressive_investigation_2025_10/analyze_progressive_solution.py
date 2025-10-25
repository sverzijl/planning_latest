"""
Diagnostic Script: Analyze Progressive Solution from Manufacturing Perspective

This script runs the progressive optimizer and extracts detailed production
data to evaluate whether decisions make manufacturing sense.

Analysis includes:
- Week 1-2 production schedule (daily breakdown)
- Labor utilization (regular vs overtime)
- Changeover patterns (SKU switches)
- Frozen inventory strategy
- Truck loading patterns
- Comparison with direct solve
"""

from datetime import date, timedelta
from pathlib import Path
from collections import defaultdict
import json

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from tests.conftest import create_test_products

from pyomo.environ import value as pyo_value


def load_data():
    """Load 12-week production planning data."""
    forecast_file = Path('data/examples/Gluten Free Forecast - Latest.xlsm')
    network_file = Path('data/examples/Network_Config.xlsx')

    parser = MultiFileParser(
        forecast_file=forecast_file,
        network_file=network_file,
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Get manufacturing site
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id,
        name=manuf_loc.name,
        storage_mode=manuf_loc.storage_mode,
        production_rate=getattr(manuf_loc, 'production_rate', 1400.0),
        daily_startup_hours=0.5,
        daily_shutdown_hours=0.25,
        default_changeover_hours=0.5,
        production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    # Get 12-week horizon
    start_date = min(e.forecast_date for e in forecast.entries)
    end_date = start_date + timedelta(days=83)

    # Convert to unified format
    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    # Create products
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    return {
        'forecast': forecast,
        'nodes': nodes,
        'routes': unified_routes,
        'labor_calendar': labor_calendar,
        'cost_structure': cost_structure,
        'truck_schedules': unified_truck_schedules,
        'products': products,
        'start_date': start_date,
        'end_date': end_date,
        'manufacturing_site': manufacturing_site,
    }


def analyze_production_schedule(model, solution, weeks_to_analyze=2):
    """Analyze production schedule for specified weeks.

    Args:
        model: Solved UnifiedNodeModel
        solution: Solution dictionary
        weeks_to_analyze: Number of weeks to analyze in detail

    Returns:
        Dictionary with detailed analysis
    """
    analysis = {
        'daily_production': defaultdict(lambda: defaultdict(float)),
        'daily_labor_hours': {},
        'daily_changeovers': {},
        'daily_total_production': {},
        'weekly_summary': {},
    }

    dates_list = sorted(list(model.model.dates))
    start_date = dates_list[0]

    # Get manufacturing node ID
    manuf_node_id = list(model.manufacturing_nodes)[0]

    # Extract daily production
    for date_idx, date_val in enumerate(dates_list):
        week_num = (date_val - start_date).days // 7 + 1

        if week_num > weeks_to_analyze:
            continue

        daily_total = 0
        products_produced_today = []

        for prod in model.model.products:
            if (manuf_node_id, prod, date_val) in model.model.production:
                qty = pyo_value(model.model.production[manuf_node_id, prod, date_val])

                if qty > 0.01:
                    analysis['daily_production'][date_val][prod] = qty
                    daily_total += qty
                    products_produced_today.append(prod)

        analysis['daily_total_production'][date_val] = daily_total

        # Count changeovers (number of different SKUs produced)
        analysis['daily_changeovers'][date_val] = len(products_produced_today)

        # Extract labor hours
        if hasattr(model.model, 'labor_hours_used'):
            if (manuf_node_id, date_val) in model.model.labor_hours_used:
                hours = pyo_value(model.model.labor_hours_used[manuf_node_id, date_val])
                analysis['daily_labor_hours'][date_val] = hours

    # Calculate weekly summaries
    for week in range(1, weeks_to_analyze + 1):
        week_start = start_date + timedelta(days=(week - 1) * 7)
        week_dates = [week_start + timedelta(days=i) for i in range(7)]

        total_production = sum(
            analysis['daily_total_production'].get(d, 0)
            for d in week_dates
        )

        total_hours = sum(
            analysis['daily_labor_hours'].get(d, 0)
            for d in week_dates
        )

        total_changeovers = sum(
            analysis['daily_changeovers'].get(d, 0)
            for d in week_dates
        )

        analysis['weekly_summary'][week] = {
            'total_production': total_production,
            'total_labor_hours': total_hours,
            'total_changeovers': total_changeovers,
            'avg_daily_production': total_production / 7,
            'production_days': sum(1 for d in week_dates if analysis['daily_total_production'].get(d, 0) > 0),
        }

    return analysis


def extract_frozen_inventory_strategy(model, weeks=12):
    """Extract frozen inventory levels by week."""
    if not hasattr(model.model, 'inventory_cohort'):
        return {}

    dates_list = sorted(list(model.model.dates))
    start_date = dates_list[0]

    frozen_by_week = defaultdict(float)

    for index in model.model.inventory_cohort:
        node_id, prod, prod_date, curr_date, state = index

        if state == 'frozen':
            week_num = (curr_date - start_date).days // 7 + 1
            frozen_qty = pyo_value(model.model.inventory_cohort[index])
            frozen_by_week[week_num] += frozen_qty

    # Average by number of dates in each week
    avg_frozen = {}
    for week in range(1, weeks + 1):
        if week in frozen_by_week:
            avg_frozen[week] = frozen_by_week[week] / 7  # Average over 7 days

    return avg_frozen


def print_manufacturing_analysis(analysis, frozen_strategy):
    """Print detailed manufacturing analysis."""

    print("\n" + "="*80)
    print("MANUFACTURING ANALYSIS: Progressive Solution")
    print("="*80)

    # Week-by-week summary
    for week, summary in sorted(analysis['weekly_summary'].items()):
        print(f"\nWeek {week}:")
        print(f"  Total production: {summary['total_production']:,.0f} units")
        print(f"  Production days: {summary['production_days']}/7")
        print(f"  Avg daily production: {summary['avg_daily_production']:,.0f} units/day")
        print(f"  Total labor hours: {summary['total_labor_hours']:.1f} hours")
        print(f"  Total changeovers: {summary['total_changeovers']} SKU switches")

        if week in frozen_strategy:
            print(f"  Frozen inventory (avg): {frozen_strategy[week]:,.0f} units")

    # Daily breakdown for week 1
    print("\n" + "="*80)
    print("WEEK 1 DAILY BREAKDOWN")
    print("="*80)

    dates_list = sorted(analysis['daily_production'].keys())
    week_1_dates = [d for d in dates_list if (d - dates_list[0]).days < 7]

    for date_val in week_1_dates:
        day_name = date_val.strftime("%A")
        total = analysis['daily_total_production'].get(date_val, 0)
        hours = analysis['daily_labor_hours'].get(date_val, 0)
        changeovers = analysis['daily_changeovers'].get(date_val, 0)

        print(f"\n{date_val} ({day_name}):")
        print(f"  Total: {total:,.0f} units, Labor: {hours:.1f}h, Changeovers: {changeovers}")

        if date_val in analysis['daily_production']:
            print(f"  Products:")
            for prod, qty in sorted(analysis['daily_production'][date_val].items()):
                print(f"    {prod}: {qty:,.0f} units")

    # Week 2 daily breakdown
    print("\n" + "="*80)
    print("WEEK 2 DAILY BREAKDOWN")
    print("="*80)

    week_2_dates = [d for d in dates_list if 7 <= (d - dates_list[0]).days < 14]

    for date_val in week_2_dates:
        day_name = date_val.strftime("%A")
        total = analysis['daily_total_production'].get(date_val, 0)
        hours = analysis['daily_labor_hours'].get(date_val, 0)
        changeovers = analysis['daily_changeovers'].get(date_val, 0)

        print(f"\n{date_val} ({day_name}):")
        print(f"  Total: {total:,.0f} units, Labor: {hours:.1f}h, Changeovers: {changeovers}")

        if date_val in analysis['daily_production']:
            print(f"  Products:")
            for prod, qty in sorted(analysis['daily_production'][date_val].items()):
                print(f"    {prod}: {qty:,.0f} units")


def manufacturing_sensibility_checks(analysis):
    """Perform manufacturing sensibility checks."""

    print("\n" + "="*80)
    print("MANUFACTURING SENSIBILITY CHECKS")
    print("="*80)

    checks_passed = []
    checks_failed = []
    warnings = []

    # Check 1: Production smoothness (coefficient of variation)
    week_1_daily = []
    for i in range(7):
        dates = sorted(analysis['daily_production'].keys())
        if i < len(dates):
            week_1_daily.append(analysis['daily_total_production'].get(dates[i], 0))

    if week_1_daily:
        avg = sum(week_1_daily) / len(week_1_daily)
        if avg > 0:
            variance = sum((x - avg)**2 for x in week_1_daily) / len(week_1_daily)
            std_dev = variance ** 0.5
            cv = std_dev / avg if avg > 0 else 0

            print(f"\n✓ Production Smoothness:")
            print(f"    Coefficient of variation: {cv:.2f}")
            if cv < 0.5:
                checks_passed.append("Production is smooth (low variance)")
                print(f"    ✅ PASS: Production is reasonably smooth")
            elif cv < 1.0:
                warnings.append("Production has moderate variance")
                print(f"    ⚠️  WARNING: Moderate production variance")
            else:
                checks_failed.append("Production is highly variable")
                print(f"    ❌ FAIL: Production is very erratic")

    # Check 2: Weekend usage
    weekend_production = 0
    weekday_production = 0

    dates = sorted(analysis['daily_production'].keys())
    for date_val in dates[:14]:  # First 2 weeks
        qty = analysis['daily_total_production'].get(date_val, 0)
        if date_val.weekday() >= 5:  # Saturday=5, Sunday=6
            weekend_production += qty
        else:
            weekday_production += qty

    print(f"\n✓ Weekend Production:")
    print(f"    Weekday: {weekday_production:,.0f} units")
    print(f"    Weekend: {weekend_production:,.0f} units")

    if weekend_production == 0:
        checks_passed.append("No weekend production (cost-optimal)")
        print(f"    ✅ PASS: No weekend production (expected - high labor cost)")
    elif weekend_production < weekday_production * 0.1:
        warnings.append("Minimal weekend production")
        print(f"    ⚠️  WARNING: Some weekend production (check if justified by demand)")
    else:
        checks_failed.append("Excessive weekend production")
        print(f"    ❌ CONCERN: Significant weekend production (expensive!)")

    # Check 3: Changeovers per day
    avg_changeovers = sum(analysis['daily_changeovers'].values()) / max(len(analysis['daily_changeovers']), 1)

    print(f"\n✓ Daily Changeovers:")
    print(f"    Average: {avg_changeovers:.1f} SKU switches/day")

    if avg_changeovers <= 3:
        checks_passed.append("Reasonable changeovers (<= 3/day)")
        print(f"    ✅ PASS: Reasonable changeover frequency")
    elif avg_changeovers <= 5:
        warnings.append("Moderate changeovers (3-5/day)")
        print(f"    ⚠️  WARNING: Moderate changeover frequency")
    else:
        checks_failed.append("Excessive changeovers (>5/day)")
        print(f"    ❌ CONCERN: High changeover frequency (inefficient!)")

    # Check 4: Capacity utilization
    week_1_summary = analysis['weekly_summary'].get(1, {})
    weekly_capacity = 84000  # 5 days × 12h × 1400 units/h = 84,000 units

    if 'total_production' in week_1_summary:
        utilization = week_1_summary['total_production'] / weekly_capacity

        print(f"\n✓ Capacity Utilization (Week 1):")
        print(f"    Production: {week_1_summary['total_production']:,.0f} units")
        print(f"    Capacity: {weekly_capacity:,.0f} units/week (regular hours)")
        print(f"    Utilization: {utilization*100:.1f}%")

        if 0.6 <= utilization <= 0.95:
            checks_passed.append("Healthy capacity utilization (60-95%)")
            print(f"    ✅ PASS: Healthy utilization")
        elif utilization < 0.6:
            warnings.append("Low capacity utilization (<60%)")
            print(f"    ⚠️  WARNING: Low utilization (demand might be low)")
        else:
            warnings.append("High capacity utilization (>95%)")
            print(f"    ⚠️  WARNING: High utilization (tight capacity)")

    # Summary
    print("\n" + "="*80)
    print("SENSIBILITY SUMMARY")
    print("="*80)
    print(f"✅ Checks passed: {len(checks_passed)}")
    for check in checks_passed:
        print(f"   - {check}")

    if warnings:
        print(f"\n⚠️  Warnings: {len(warnings)}")
        for warning in warnings:
            print(f"   - {warning}")

    if checks_failed:
        print(f"\n❌ Concerns: {len(checks_failed)}")
        for fail in checks_failed:
            print(f"   - {fail}")

    overall_sensible = len(checks_failed) == 0 and len(warnings) <= 2

    if overall_sensible:
        print(f"\n🎯 OVERALL: Solution appears SENSIBLE from manufacturing perspective")
    else:
        print(f"\n⚠️  OVERALL: Solution has concerns - review details above")

    return overall_sensible


def compare_progressive_vs_direct(progressive_analysis, direct_analysis):
    """Compare progressive vs direct solve decisions."""

    print("\n" + "="*80)
    print("PROGRESSIVE vs DIRECT SOLVE COMPARISON")
    print("="*80)

    # Compare week 1 production
    week_1_prog = progressive_analysis['weekly_summary'].get(1, {})
    week_1_direct = direct_analysis['weekly_summary'].get(1, {})

    if week_1_prog and week_1_direct:
        prod_diff = week_1_prog['total_production'] - week_1_direct['total_production']
        prod_diff_pct = (prod_diff / week_1_direct['total_production']) * 100 if week_1_direct['total_production'] > 0 else 0

        print(f"\nWeek 1 Production:")
        print(f"  Direct: {week_1_direct['total_production']:,.0f} units")
        print(f"  Progressive: {week_1_prog['total_production']:,.0f} units")
        print(f"  Difference: {prod_diff:+,.0f} units ({prod_diff_pct:+.1f}%)")

        if abs(prod_diff_pct) < 5:
            print(f"  ✅ Very similar production quantities")
        elif abs(prod_diff_pct) < 10:
            print(f"  ⚠️  Moderate difference in production")
        else:
            print(f"  ❌ Significant difference in production strategy")


def main():
    """Main analysis workflow."""

    print("="*80)
    print("PROGRESSIVE SOLUTION ANALYSIS")
    print("="*80)

    # Load data
    print("\nLoading data...")
    data = load_data()

    print(f"Data loaded: {len(data['products'])} products, "
          f"{(data['end_date'] - data['start_date']).days + 1} days")

    # Build and solve with PROGRESSIVE
    print("\n" + "="*80)
    print("SOLVING WITH PROGRESSIVE OPTIMIZATION")
    print("="*80)

    model_progressive = UnifiedNodeModel(
        nodes=data['nodes'],
        routes=data['routes'],
        forecast=data['forecast'],
        labor_calendar=data['labor_calendar'],
        cost_structure=data['cost_structure'],
        products=data['products'],
        start_date=data['start_date'],
        end_date=data['end_date'],
        truck_schedules=data['truck_schedules'],
        use_batch_tracking=True,
        allow_shortages=True,
    )

    result_progressive = model_progressive.solve_progressive(phases='auto', tee=False)

    print(f"\nProgressive solve complete:")
    print(f"  Objective: ${result_progressive.objective_value:,.2f}")
    print(f"  Time: {result_progressive.solve_time_seconds:.1f}s")
    print(f"  Status: {result_progressive.termination_condition}")

    # Extract solution
    solution_progressive = model_progressive.get_solution()

    # Analyze progressive solution
    print("\n" + "="*80)
    print("ANALYZING PROGRESSIVE SOLUTION")
    print("="*80)

    progressive_analysis = analyze_production_schedule(
        model_progressive,
        solution_progressive,
        weeks_to_analyze=2
    )

    # Extract frozen strategy
    frozen_strategy = extract_frozen_inventory_strategy(model_progressive, weeks=12)

    # Print detailed analysis
    print_manufacturing_analysis(progressive_analysis, frozen_strategy)

    # Perform sensibility checks
    is_sensible = manufacturing_sensibility_checks(progressive_analysis)

    # Save results to JSON
    output = {
        'progressive': {
            'objective': result_progressive.objective_value,
            'solve_time': result_progressive.solve_time_seconds,
            'weekly_summary': {k: v for k, v in progressive_analysis['weekly_summary'].items()},
            'frozen_strategy': {k: v for k, v in frozen_strategy.items()},
            'is_sensible': is_sensible,
        }
    }

    with open('progressive_analysis_results.json', 'w') as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n📊 Results saved to: progressive_analysis_results.json")

    return is_sensible


if __name__ == '__main__':
    is_sensible = main()

    if is_sensible:
        print("\n✅ CONCLUSION: Progressive solution makes manufacturing sense!")
        exit(0)
    else:
        print("\n⚠️  CONCLUSION: Review concerns before proceeding")
        exit(1)
