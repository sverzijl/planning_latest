#!/usr/bin/env python3
"""
Test 4-week optimization with batch tracking using real data.

This test validates whether production spreads naturally across multiple days
WITHOUT an explicit smoothing constraint, relying only on:
1. Labor costs (overtime/weekend premium)
2. Shelf life constraints
3. Transport capacity limits
4. Holding costs
"""

from datetime import date, timedelta
from src.parsers.excel_parser import ExcelParser
from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection

def analyze_production_spread(result):
    """Analyze how production is distributed across days."""

    production_batches = result.metadata.get('production_batch_objects', [])

    if not production_batches:
        print("\n❌ No production batches found in result")
        return False

    # Group by date
    production_by_date = {}
    total_units = 0

    for batch in production_batches:
        prod_date = batch.production_date
        if prod_date not in production_by_date:
            production_by_date[prod_date] = 0
        production_by_date[prod_date] += batch.quantity
        total_units += batch.quantity

    # Sort by date
    sorted_dates = sorted(production_by_date.keys())

    print("\n" + "=" * 70)
    print("PRODUCTION DISTRIBUTION ANALYSIS")
    print("=" * 70)
    print(f"\nTotal production: {total_units:,} units")
    print(f"Production days: {len(sorted_dates)}")
    print(f"Planning horizon: {sorted_dates[0]} to {sorted_dates[-1]}")
    print(f"Span: {(sorted_dates[-1] - sorted_dates[0]).days + 1} days")

    print("\nProduction by date:")
    for d in sorted_dates:
        qty = production_by_date[d]
        pct = (qty / total_units) * 100
        day_name = d.strftime("%A")
        bar = "█" * int(pct / 2)  # Visual bar
        print(f"  {d} ({day_name:9s}): {qty:6,} units ({pct:5.1f}%) {bar}")

    # Analysis
    print("\n" + "-" * 70)
    print("ANALYSIS")
    print("-" * 70)

    # Check concentration
    max_day_qty = max(production_by_date.values())
    max_day_pct = (max_day_qty / total_units) * 100

    if len(sorted_dates) == 1:
        print("\n❌ CONCENTRATED: ALL production on ONE day")
        print("   This indicates natural constraints are INSUFFICIENT.")
        return False
    elif len(sorted_dates) <= 3:
        print(f"\n⚠️  HIGHLY CONCENTRATED: Only {len(sorted_dates)} production days")
        print(f"   Largest day: {max_day_pct:.1f}% of total")
        print("   Natural constraints may be insufficient.")
        return False
    elif max_day_pct > 50:
        print(f"\n⚠️  CONCENTRATED: One day has {max_day_pct:.1f}% of production")
        print(f"   Spread across {len(sorted_dates)} days, but heavily skewed")
        return False
    else:
        print(f"\n✅ WELL DISTRIBUTED: Spread across {len(sorted_dates)} days")
        print(f"   Largest day: {max_day_pct:.1f}% of total")
        print("   Natural constraints are working!")

        # Check for weekday vs weekend pattern
        weekday_total = 0
        weekend_total = 0
        for d in sorted_dates:
            if d.weekday() < 5:  # Monday-Friday
                weekday_total += production_by_date[d]
            else:
                weekend_total += production_by_date[d]

        if weekend_total > 0:
            print(f"\n   Weekday production: {weekday_total:,} ({weekday_total/total_units*100:.1f}%)")
            print(f"   Weekend production: {weekend_total:,} ({weekend_total/total_units*100:.1f}%)")
        else:
            print(f"\n   All production on weekdays (good - avoiding weekend premium)")

        return True

def main():
    """Run 4-week test with real data."""

    print("=" * 70)
    print("4-WEEK BATCH TRACKING TEST - REAL DATA")
    print("=" * 70)
    print("\nTesting: Do natural constraints spread production without smoothing?")
    print("\nConfiguration:")
    print("  - Data: data/examples/Gfree Forecast.xlsm")
    print("  - Planning horizon: 4 weeks (28 days)")
    print("  - Batch tracking: ENABLED")
    print("  - FIFO penalty: DISABLED")
    print("  - Production smoothing: DISABLED")
    print("  - Relying on: Labor costs + shelf life + capacity")

    # Load real data
    print("\n" + "=" * 70)
    print("Loading data...")
    print("=" * 70)

    # Use Network_Config for network/labor/costs
    network_parser = ExcelParser("data/examples/Network_Config.xlsx")
    locations = network_parser.parse_locations()
    routes = network_parser.parse_routes()
    labor_calendar = network_parser.parse_labor_calendar()
    truck_schedules = network_parser.parse_truck_schedules()
    cost_structure = network_parser.parse_cost_structure()

    # Use Gfree Forecast for forecast data (SAP IBP format)
    forecast_parser = ExcelParser("data/examples/Gfree Forecast.xlsm")
    forecast = forecast_parser.parse_forecast(sheet_name="G610_RET")

    # Get manufacturing site from locations
    manufacturing_site = next((loc for loc in locations if loc.type == "manufacturing"), None)
    if not manufacturing_site:
        print("\n❌ No manufacturing location found")
        return

    print(f"\n✅ Data loaded:")
    print(f"   Forecast: {len(forecast.entries)} entries")
    print(f"   Locations: {len(locations)}")
    print(f"   Routes: {len(routes)}")

    # Create data dict
    data = {
        'forecast': forecast,
        'locations': locations,
        'routes': routes,
        'labor_calendar': labor_calendar,
        'truck_schedules': truck_schedules,
        'cost_structure': cost_structure,
        'manufacturing_site': manufacturing_site
    }

    # Set 4-week planning window
    start_date = date(2025, 10, 13)  # Monday
    end_date = start_date + timedelta(days=27)  # 4 weeks

    print(f"\n   Planning window: {start_date} to {end_date}")

    # Build model WITH batch tracking, WITHOUT smoothing
    print("\n" + "=" * 70)
    print("Building optimization model...")
    print("=" * 70)

    model = IntegratedProductionDistributionModel(
        forecast=data['forecast'],
        labor_calendar=data['labor_calendar'],
        manufacturing_site=data['manufacturing_site'],
        cost_structure=data['cost_structure'],
        locations=data['locations'],
        routes=data['routes'],
        truck_schedules=TruckScheduleCollection(schedules=data['truck_schedules']),
        max_routes_per_destination=3,
        allow_shortages=True,  # Allow shortages to ensure feasibility
        enforce_shelf_life=True,
        start_date=start_date,
        end_date=end_date,
        use_batch_tracking=True,           # ✅ Batch tracking
        enable_production_smoothing=False  # ❌ No smoothing
    )

    print(f"\n✅ Model built:")
    print(f"   Batch tracking: {model.use_batch_tracking}")
    print(f"   Production smoothing: {model.enable_production_smoothing}")
    print(f"   Routes enumerated: {len(model.enumerated_routes)}")

    # Solve
    print("\n" + "=" * 70)
    print("Solving optimization...")
    print("=" * 70)
    print("(This may take 2-5 minutes with batch tracking...)")

    result = model.solve(time_limit_seconds=600)

    if not result.is_feasible():
        print(f"\n❌ Solve failed: {result.termination_condition}")
        return

    status_str = "optimal" if result.is_optimal() else "feasible"
    print(f"\n✅ Solve completed: {status_str}")
    print(f"   Total cost: ${result.objective_value:,.2f}")

    # Analyze production distribution
    is_well_distributed = analyze_production_spread(result)

    # Print conclusion
    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)

    if is_well_distributed:
        print("\n✅ SUCCESS: Natural constraints spread production effectively!")
        print("\n   Key findings:")
        print("   - Labor costs (overtime, weekend premium) incentivize weekday spread")
        print("   - Shelf life constraints prevent excessive early production")
        print("   - Transport capacity limits prevent single-day concentration")
        print("\n   RECOMMENDATION: Production smoothing constraint is NOT needed.")
        print("   The model correctly reflects economic reality.")
    else:
        print("\n❌ ISSUE: Production still concentrated despite natural constraints.")
        print("\n   This indicates MISSING COST COMPONENTS:")
        print("   - Holding costs may not be properly modeled")
        print("   - Labor cost structure may not penalize concentration enough")
        print("   - Other economic incentives for spreading may be missing")
        print("\n   RECOMMENDATION: Investigate cost model, not add artificial constraints.")
        print("   Find the missing economic driver for production spreading.")

if __name__ == "__main__":
    main()
