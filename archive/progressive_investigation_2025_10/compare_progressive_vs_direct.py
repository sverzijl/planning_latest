"""
Compare Progressive vs Direct Solve: Deep Investigation

This script runs BOTH progressive and direct solve on the SAME problem
and compares the solutions in detail to determine if the concerns are:
1. Progressive-specific (algorithm bug)
2. Model-wide (affects both methods)
"""

from datetime import date, timedelta
from pathlib import Path
from collections import defaultdict

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

    parser = MultiFileParser(forecast_file=forecast_file, network_file=network_file)
    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
        production_rate=getattr(manuf_loc, 'production_rate', 1400.0),
        daily_startup_hours=0.5, daily_shutdown_hours=0.25, default_changeover_hours=0.5,
        production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    start_date = min(e.forecast_date for e in forecast.entries)
    end_date = start_date + timedelta(days=83)

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    return {
        'forecast': forecast, 'nodes': nodes, 'routes': unified_routes,
        'labor_calendar': labor_calendar, 'cost_structure': cost_structure,
        'truck_schedules': unified_truck_schedules, 'products': products,
        'start_date': start_date, 'end_date': end_date,
    }


def extract_weekly_production(model, weeks=2):
    """Extract production by week."""
    dates_list = sorted(list(model.model.dates))
    start_date = dates_list[0]
    manuf_node_id = list(model.manufacturing_nodes)[0]

    weekly = {}

    for week in range(1, weeks + 1):
        week_data = {
            'total_production': 0,
            'daily': {},
            'weekend_production': 0,
            'weekday_production': 0,
            'max_daily_hours': 0,
            'total_hours': 0,
        }

        week_start = start_date + timedelta(days=(week - 1) * 7)
        week_dates = [week_start + timedelta(days=i) for i in range(7)]

        for date_val in week_dates:
            if date_val not in model.model.dates:
                continue

            daily_total = 0
            for prod in model.model.products:
                if (manuf_node_id, prod, date_val) in model.model.production:
                    qty = pyo_value(model.model.production[manuf_node_id, prod, date_val])
                    daily_total += qty

            week_data['daily'][date_val] = daily_total
            week_data['total_production'] += daily_total

            # Categorize weekend vs weekday
            if date_val.weekday() >= 5:  # Sat=5, Sun=6
                week_data['weekend_production'] += daily_total
            else:
                week_data['weekday_production'] += daily_total

            # Extract labor hours
            if hasattr(model.model, 'labor_hours_used'):
                if (manuf_node_id, date_val) in model.model.labor_hours_used:
                    hours = pyo_value(model.model.labor_hours_used[manuf_node_id, date_val])
                    week_data['total_hours'] += hours
                    week_data['max_daily_hours'] = max(week_data['max_daily_hours'], hours)

        weekly[week] = week_data

    return weekly


def extract_frozen_inventory(model):
    """Check if frozen inventory exists."""
    if not hasattr(model.model, 'inventory_cohort'):
        return 0

    total_frozen = 0
    for index in model.model.inventory_cohort:
        node_id, prod, prod_date, curr_date, state = index
        if state == 'frozen':
            frozen_qty = pyo_value(model.model.inventory_cohort[index])
            total_frozen += frozen_qty

    return total_frozen


def main():
    print("="*80)
    print("PROGRESSIVE vs DIRECT SOLVE: DEEP COMPARISON")
    print("="*80)

    data = load_data()
    print(f"\nData: {len(data['products'])} products, {(data['end_date'] - data['start_date']).days + 1} days")
    print(f"Planning: {data['start_date']} to {data['end_date']}")

    # SOLVE WITH DIRECT
    print("\n" + "="*80)
    print("METHOD 1: DIRECT SOLVE (1% gap, baseline)")
    print("="*80)

    model_direct = UnifiedNodeModel(
        nodes=data['nodes'], routes=data['routes'], forecast=data['forecast'],
        labor_calendar=data['labor_calendar'], cost_structure=data['cost_structure'],
        products=data['products'], start_date=data['start_date'], end_date=data['end_date'],
        truck_schedules=data['truck_schedules'], use_batch_tracking=True, allow_shortages=True,
    )

    result_direct = model_direct.solve(solver_name='appsi_highs', mip_gap=0.01, time_limit_seconds=600)

    print(f"\nDirect solve complete:")
    print(f"  Objective: ${result_direct.objective_value:,.2f}")
    print(f"  Time: {result_direct.solve_time_seconds:.1f}s")
    print(f"  Status: {result_direct.termination_condition}")

    # SOLVE WITH PROGRESSIVE
    print("\n" + "="*80)
    print("METHOD 2: PROGRESSIVE (4-phase auto)")
    print("="*80)

    model_progressive = UnifiedNodeModel(
        nodes=data['nodes'], routes=data['routes'], forecast=data['forecast'],
        labor_calendar=data['labor_calendar'], cost_structure=data['cost_structure'],
        products=data['products'], start_date=data['start_date'], end_date=data['end_date'],
        truck_schedules=data['truck_schedules'], use_batch_tracking=True, allow_shortages=True,
    )

    result_progressive = model_progressive.solve_progressive(phases='auto')

    print(f"\nProgressive solve complete:")
    print(f"  Objective: ${result_progressive.objective_value:,.2f}")
    print(f"  Time: {result_progressive.solve_time_seconds:.1f}s")
    print(f"  Status: {result_progressive.termination_condition}")

    # EXTRACT AND COMPARE
    direct_weekly = extract_weekly_production(model_direct, weeks=2)
    progressive_weekly = extract_weekly_production(model_progressive, weeks=2)

    direct_frozen = extract_frozen_inventory(model_direct)
    progressive_frozen = extract_frozen_inventory(model_progressive)

    # DETAILED COMPARISON
    print("\n" + "="*80)
    print("DETAILED COMPARISON: Week 1")
    print("="*80)

    print(f"\nDirect Solve - Week 1:")
    print(f"  Total production: {direct_weekly[1]['total_production']:,.0f} units")
    print(f"  Weekday: {direct_weekly[1]['weekday_production']:,.0f} units")
    print(f"  Weekend: {direct_weekly[1]['weekend_production']:,.0f} units")
    print(f"  Weekend %: {direct_weekly[1]['weekend_production']/direct_weekly[1]['total_production']*100 if direct_weekly[1]['total_production'] > 0 else 0:.1f}%")
    print(f"  Max daily hours: {direct_weekly[1]['max_daily_hours']:.1f}h")
    print(f"  Total hours: {direct_weekly[1]['total_hours']:.1f}h")

    print(f"\nProgressive - Week 1:")
    print(f"  Total production: {progressive_weekly[1]['total_production']:,.0f} units")
    print(f"  Weekday: {progressive_weekly[1]['weekday_production']:,.0f} units")
    print(f"  Weekend: {progressive_weekly[1]['weekend_production']:,.0f} units")
    print(f"  Weekend %: {progressive_weekly[1]['weekend_production']/progressive_weekly[1]['total_production']*100 if progressive_weekly[1]['total_production'] > 0 else 0:.1f}%")
    print(f"  Max daily hours: {progressive_weekly[1]['max_daily_hours']:.1f}h")
    print(f"  Total hours: {progressive_weekly[1]['total_hours']:.1f}h")

    print("\n" + "="*80)
    print("DETAILED COMPARISON: Week 2")
    print("="*80)

    print(f"\nDirect Solve - Week 2:")
    print(f"  Total production: {direct_weekly[2]['total_production']:,.0f} units")
    print(f"  Total hours: {direct_weekly[2]['total_hours']:.1f}h")

    print(f"\nProgressive - Week 2:")
    print(f"  Total production: {progressive_weekly[2]['total_production']:,.0f} units")
    print(f"  Total hours: {progressive_weekly[2]['total_hours']:.1f}h")

    print("\n" + "="*80)
    print("FROZEN INVENTORY CHECK")
    print("="*80)

    print(f"\nDirect solve:")
    print(f"  Total frozen inventory: {direct_frozen:,.0f} units")

    print(f"\nProgressive:")
    print(f"  Total frozen inventory: {progressive_frozen:,.0f} units")

    # VERDICT
    print("\n" + "="*80)
    print("VERDICT")
    print("="*80)

    # Check if both methods give similar results
    obj_gap = abs(result_progressive.objective_value - result_direct.objective_value) / result_direct.objective_value

    print(f"\nObjective comparison:")
    print(f"  Gap: {obj_gap*100:.2f}%")

    # Check week 1 production similarity
    week1_prod_gap = abs(progressive_weekly[1]['total_production'] - direct_weekly[1]['total_production']) / direct_weekly[1]['total_production'] if direct_weekly[1]['total_production'] > 0 else 0

    print(f"\nWeek 1 production:")
    print(f"  Gap: {week1_prod_gap*100:.2f}%")

    # Weekend usage comparison
    direct_weekend_pct = direct_weekly[1]['weekend_production'] / direct_weekly[1]['total_production'] * 100 if direct_weekly[1]['total_production'] > 0 else 0
    progressive_weekend_pct = progressive_weekly[1]['weekend_production'] / progressive_weekly[1]['total_production'] * 100 if progressive_weekly[1]['total_production'] > 0 else 0

    print(f"\nWeekend usage:")
    print(f"  Direct: {direct_weekend_pct:.1f}%")
    print(f"  Progressive: {progressive_weekend_pct:.1f}%")

    if abs(direct_weekend_pct - progressive_weekend_pct) < 5:
        print(f"  ✅ BOTH methods use similar weekend %")
        print(f"     → This is a MODEL issue, not progressive bug!")
    else:
        print(f"  ❌ Different weekend usage!")
        print(f"     → This suggests progressive is finding different (worse) solution")

    # Week 2 comparison
    if direct_weekly[2]['total_production'] == 0 and progressive_weekly[2]['total_production'] == 0:
        print(f"\n⚠️  BOTH methods have ZERO week 2 production!")
        print(f"   → This is a MODEL/DATA issue, not progressive-specific")
    elif direct_weekly[2]['total_production'] > 0 and progressive_weekly[2]['total_production'] == 0:
        print(f"\n❌ Progressive has zero week 2, but direct has {direct_weekly[2]['total_production']:,.0f}")
        print(f"   → Progressive is finding wrong solution due to bound tightening!")
    else:
        print(f"\n✅ Week 2 production comparison:")
        print(f"   Direct: {direct_weekly[2]['total_production']:,.0f}")
        print(f"   Progressive: {progressive_weekly[2]['total_production']:,.0f}")

    print("\n" + "="*80)


if __name__ == '__main__':
    main()
