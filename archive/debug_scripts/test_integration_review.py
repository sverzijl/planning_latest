"""Integration test to review optimization results on example data."""

import sys
from pathlib import Path
from datetime import date, timedelta
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection

def main():
    print("="*80)
    print("OPTIMIZATION INTEGRATION TEST - EXAMPLE DATA REVIEW")
    print("="*80)
    print()

    # Parse example data
    print("📂 Loading example data...")

    # Parse network config
    network_path = "data/examples/Network_Config.xlsx"
    network_parser = ExcelParser(network_path)

    locations = network_parser.parse_locations()
    routes = network_parser.parse_routes()
    labor_calendar = network_parser.parse_labor_calendar()
    truck_schedules_list = network_parser.parse_truck_schedules()
    truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)
    cost_structure = network_parser.parse_cost_structure()

    # Find manufacturing site
    manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
    if not manufacturing_site:
        print("❌ No manufacturing site found in locations!")
        return

    # Parse forecast
    forecast_path = "data/examples/Gfree Forecast_Converted.xlsx"
    forecast_parser = ExcelParser(forecast_path)
    forecast = forecast_parser.parse_forecast()

    parsed_data = {
        'locations': locations,
        'routes': routes,
        'labor_calendar': labor_calendar,
        'truck_schedules': truck_schedules,
        'cost_structure': cost_structure,
        'manufacturing_site': manufacturing_site,
        'forecast': forecast,
    }

    print(f"✓ Loaded {len(parsed_data['locations'])} locations")
    print(f"✓ Loaded {len(parsed_data['routes'])} routes")
    print(f"✓ Loaded {len(forecast.entries)} forecast entries")

    # Calculate date range from entries
    dates = [entry.forecast_date for entry in forecast.entries]
    start_date = min(dates)
    end_date = max(dates)
    days = (end_date - start_date).days + 1

    print(f"✓ Planning horizon: {start_date} to {end_date} ({days} days)")
    print()

    # Calculate total demand
    total_demand = sum(entry.quantity for entry in forecast.entries)
    print(f"📊 Total demand: {total_demand:,.0f} units over {days} days")
    print(f"📊 Average daily demand: {total_demand/days:,.0f} units/day")
    print()

    # Labor calendar summary
    labor_cal = parsed_data['labor_calendar']
    weekdays = sum(1 for day in labor_cal.days if day.is_fixed_day)
    weekends = sum(1 for day in labor_cal.days if not day.is_fixed_day)
    print(f"📅 Labor calendar: {weekdays} weekdays, {weekends} weekend days")

    # Get a sample weekend and weekday for rate comparison
    sample_weekday = next((day for day in labor_cal.days if day.is_fixed_day), None)
    sample_weekend = next((day for day in labor_cal.days if not day.is_fixed_day), None)

    if sample_weekday:
        print(f"   Weekday rates: ${sample_weekday.regular_rate}/h regular, ${sample_weekday.overtime_rate}/h OT")
    if sample_weekend:
        print(f"   Weekend rates: ${sample_weekend.non_fixed_rate}/h (4h minimum)")
    print()

    # Create optimization model
    print("🔧 Building optimization model...")
    model = IntegratedProductionDistributionModel(
        forecast=parsed_data['forecast'],
        labor_calendar=parsed_data['labor_calendar'],
        manufacturing_site=parsed_data['manufacturing_site'],
        cost_structure=parsed_data['cost_structure'],
        locations=parsed_data['locations'],
        routes=parsed_data['routes'],
        truck_schedules=parsed_data['truck_schedules'],
        max_routes_per_destination=5,
        allow_shortages=True,  # Allow shortages to identify infeasibility
        enforce_shelf_life=True,
    )

    print(f"✓ Model built: {len(model.enumerated_routes)} routes, {len(model.production_dates)} production days")
    print()

    # Solve
    print("⚡ Solving optimization model with CBC...")
    print("   (This may take 1-2 minutes)")
    result = model.solve(
        solver_name='cbc',
        time_limit_seconds=300,
        mip_gap=0.01,
        tee=False,
    )

    print()
    print("="*80)
    print("OPTIMIZATION RESULTS")
    print("="*80)
    print()

    if not (result.is_optimal() or result.is_feasible()):
        print(f"❌ Solver status: {result.termination_condition}")
        if result.infeasibility_message:
            print(f"   {result.infeasibility_message}")
        return

    # Extract solution from model
    solution = model.get_solution()

    # High-level metrics
    print("📈 SOLUTION SUMMARY:")
    print(f"   Status: {'Optimal' if result.is_optimal() else 'Feasible'}")
    print(f"   Total cost: ${result.objective_value:,.2f}")
    print(f"   Solve time: {result.solve_time_seconds:.1f}s")
    if result.gap:
        print(f"   Optimality gap: {result.gap*100:.2f}%")
    print()

    # Production analysis
    production = solution.get('production_by_date_product', {})
    total_production = sum(production.values())
    production_days = len(set(d for d, p in production.keys()))

    print("🏭 PRODUCTION ANALYSIS:")
    print(f"   Total production: {total_production:,.0f} units")
    print(f"   Production days used: {production_days} days")
    print(f"   Average per production day: {total_production/production_days:,.0f} units/day")
    print()

    # Labor analysis by day type
    labor_hours = solution.get('labor_hours_by_date', {})
    labor_costs = solution.get('labor_cost_by_date', {})

    weekday_hours = 0.0
    weekday_cost = 0.0
    weekend_hours = 0.0
    weekend_cost = 0.0
    weekday_production = 0.0
    weekend_production = 0.0

    weekday_dates = []
    weekend_dates = []

    for d, hours in labor_hours.items():
        if hours > 0.01:
            labor_day = labor_cal.get_labor_day(d)
            prod = sum(qty for (prod_date, p), qty in production.items() if prod_date == d)

            if labor_day and labor_day.is_fixed_day:
                weekday_hours += hours
                weekday_cost += labor_costs.get(d, 0.0)
                weekday_production += prod
                if hours > 0:
                    weekday_dates.append((d, hours, prod))
            else:
                weekend_hours += hours
                weekend_cost += labor_costs.get(d, 0.0)
                weekend_production += prod
                if hours > 0:
                    weekend_dates.append((d, hours, prod))

    print("⏰ LABOR HOURS BREAKDOWN:")
    print(f"   Weekday hours: {weekday_hours:,.1f}h (${weekday_cost:,.2f})")
    print(f"   Weekend hours: {weekend_hours:,.1f}h (${weekend_cost:,.2f})")
    print(f"   Total labor cost: ${weekday_cost + weekend_cost:,.2f}")
    print()

    print("📦 PRODUCTION BY DAY TYPE:")
    print(f"   Weekday production: {weekday_production:,.0f} units ({weekday_production/total_production*100:.1f}%)")
    print(f"   Weekend production: {weekend_production:,.0f} units ({weekend_production/total_production*100:.1f}%)")
    print()

    # Weekend production details
    if weekend_dates:
        print("⚠️  WEEKEND PRODUCTION DETAILS:")
        print(f"   {len(weekend_dates)} weekend days with production")
        print()
        for d, hours, prod in sorted(weekend_dates)[:10]:  # Show first 10
            day_name = d.strftime("%A, %Y-%m-%d")
            cost_per_unit = labor_costs.get(d, 0) / prod if prod > 0 else 0
            print(f"   {day_name}: {prod:,.0f} units in {hours:.1f}h (${cost_per_unit:.4f}/unit labor)")

        if len(weekend_dates) > 10:
            print(f"   ... and {len(weekend_dates) - 10} more weekend days")
        print()

    # Cost breakdown
    total_cost = result.objective_value
    labor_cost = solution.get('total_labor_cost', 0.0)
    production_cost = solution.get('total_production_cost', 0.0)
    transport_cost = solution.get('total_transport_cost', 0.0)

    print("💰 COST BREAKDOWN:")
    print(f"   Labor cost:      ${labor_cost:>12,.2f} ({labor_cost/total_cost*100:>5.1f}%)")
    print(f"   Production cost: ${production_cost:>12,.2f} ({production_cost/total_cost*100:>5.1f}%)")
    print(f"   Transport cost:  ${transport_cost:>12,.2f} ({transport_cost/total_cost*100:>5.1f}%)")
    print(f"   {'─'*45}")
    print(f"   Total cost:      ${total_cost:>12,.2f} (100.0%)")
    print()

    # Cost per unit
    print("📊 UNIT ECONOMICS:")
    print(f"   Total cost per unit: ${total_cost/total_production:.4f}")
    print(f"   Labor cost per unit: ${labor_cost/total_production:.4f}")
    print(f"   Weekday labor cost per unit: ${weekday_cost/weekday_production:.4f}" if weekday_production > 0 else "   (no weekday production)")
    print(f"   Weekend labor cost per unit: ${weekend_cost/weekend_production:.4f}" if weekend_production > 0 else "   (no weekend production)")
    print()

    # Capacity utilization
    production_rate = 1400  # units/hour (from CLAUDE.md)
    weekday_capacity = weekdays * 12 * production_rate  # Regular hours only
    total_capacity = weekday_capacity + weekends * 14 * production_rate

    print("🏭 CAPACITY UTILIZATION:")
    print(f"   Weekday capacity (12h/day): {weekday_capacity:,.0f} units")
    print(f"   Total capacity available: {total_capacity:,.0f} units")
    print(f"   Production: {total_production:,.0f} units")
    print(f"   Utilization: {total_production/weekday_capacity*100:.1f}% of weekday capacity")
    print()

    # Save results to CSV for detailed review
    print("💾 Saving detailed results to CSV...")

    # Production schedule
    prod_df = pd.DataFrame([
        {
            'date': d,
            'day_of_week': d.strftime('%A'),
            'product': p,
            'quantity': qty,
            'is_weekend': not labor_cal.get_labor_day(d).is_fixed_day if labor_cal.get_labor_day(d) else False,
        }
        for (d, p), qty in production.items()
    ])
    prod_df = prod_df.sort_values(['date', 'product'])
    prod_df.to_csv('integration_test_production.csv', index=False)
    print("   ✓ integration_test_production.csv")

    # Labor summary
    labor_df = pd.DataFrame([
        {
            'date': d,
            'day_of_week': d.strftime('%A'),
            'is_weekend': not labor_cal.get_labor_day(d).is_fixed_day if labor_cal.get_labor_day(d) else False,
            'hours': hours,
            'cost': labor_costs.get(d, 0.0),
            'production': sum(qty for (prod_date, p), qty in production.items() if prod_date == d),
        }
        for d, hours in labor_hours.items() if hours > 0.01
    ])
    labor_df = labor_df.sort_values('date')
    labor_df.to_csv('integration_test_labor.csv', index=False)
    print("   ✓ integration_test_labor.csv")

    print()
    print("="*80)
    print("✅ INTEGRATION TEST COMPLETE")
    print("="*80)

if __name__ == "__main__":
    main()
