#!/usr/bin/env python3
"""
Investigate Weekend Production Splitting Issue

Analyzes whether the optimizer is incorrectly splitting production across
consecutive weekend days when consolidation would save labor costs.

Expected: Consolidate to one weekend day to save 4-hour minimum payment
Observed: Splitting across both days, paying 8 hours for 2.6 hours of work
"""

from datetime import date, timedelta
from pathlib import Path
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from src.models.truck_schedule import TruckScheduleCollection

def analyze_weekend_labor_cost():
    """Analyze the weekend production splitting issue."""

    print("=" * 80)
    print("WEEKEND PRODUCTION SPLITTING INVESTIGATION")
    print("=" * 80)

    # Load data (same as integration test)
    data_dir = Path("data/examples")
    forecast_path = data_dir / "Gluten Free Forecast - Latest.xlsm"
    network_path = data_dir / "Network_Config.xlsx"
    inventory_path = data_dir / "inventory_latest.XLSX"

    print(f"\nLoading data from:")
    print(f"  Forecast:  {forecast_path}")
    print(f"  Network:   {network_path}")
    print(f"  Inventory: {inventory_path if inventory_path.exists() else 'None (optional)'}")

    # Parse using MultiFileParser
    parser = MultiFileParser(
        forecast_file=forecast_path,
        network_file=network_path,
        inventory_file=inventory_path if inventory_path.exists() else None,
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Get manufacturing site
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    if not manufacturing_locations:
        raise ValueError("No manufacturing site found")

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

    # Parse inventory if available
    initial_inventory = None
    inventory_snapshot_date = None
    if inventory_path.exists():
        inventory_snapshot = parser.parse_inventory(snapshot_date=None)
        initial_inventory = inventory_snapshot
        inventory_snapshot_date = inventory_snapshot.snapshot_date

    # Convert to unified format
    truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)
    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    print(f"\n✓ Loaded {len(nodes)} nodes")
    print(f"✓ Loaded {len(unified_routes)} routes")
    print(f"✓ Loaded labor calendar")
    print(f"✓ Loaded {len(unified_truck_schedules)} truck schedules")

    # Set up model parameters
    if inventory_snapshot_date:
        start_date = inventory_snapshot_date
    else:
        # Use earliest forecast date
        start_date = min(e.forecast_date for e in forecast.entries)

    horizon_weeks = 4
    end_date = start_date + timedelta(weeks=horizon_weeks)
    horizon_days = (end_date - start_date).days

    print(f"\n{'Planning Horizon':.<40} {start_date} to {end_date}")
    print(f"{'Horizon Days':.<40} {horizon_days}")

    # Identify weekend days in horizon
    weekend_days = []
    for i in range(horizon_days):
        check_date = start_date + timedelta(days=i)
        labor_day = labor_calendar.get_labor_day(check_date)
        if labor_day and not labor_day.is_fixed_day:
            weekend_days.append({
                'date': check_date,
                'day_name': check_date.strftime('%A'),
                'minimum_hours': labor_day.minimum_hours,
                'non_fixed_rate': labor_day.non_fixed_rate or labor_day.overtime_rate
            })

    print(f"\n{'Non-Fixed Days (Weekends/Holidays)':.<40} {len(weekend_days)}")
    for wd in weekend_days[:5]:  # Show first 5
        print(f"  {wd['date']} ({wd['day_name']}): {wd['minimum_hours']}h min @ ${wd['non_fixed_rate']:.2f}/h")
    if len(weekend_days) > 5:
        print(f"  ... and {len(weekend_days) - 5} more")

    # Calculate 4-hour minimum cost
    if weekend_days:
        sample_rate = weekend_days[0]['non_fixed_rate']
        min_hours = weekend_days[0]['minimum_hours']
        min_cost = sample_rate * min_hours
        print(f"\n{'Weekend Minimum Payment':.<40} {min_hours}h × ${sample_rate:.2f}/h = ${min_cost:,.2f}")
        print(f"{'Penalty for Splitting Across 2 Days':.<40} ${min_cost:,.2f} (pays 2× minimum)")

    # Create and solve optimization model
    print("\n" + "=" * 80)
    print("BUILDING OPTIMIZATION MODEL")
    print("=" * 80)

    # Create products for model (extract unique product IDs from forecast)
    from tests.conftest import create_test_products
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        truck_schedules=unified_truck_schedules,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
        inventory_snapshot_date=inventory_snapshot_date,
        use_batch_tracking=True,
        allow_shortages=True,  # Same as your observation
        enforce_shelf_life=True,
    )

    print("\n✓ Model built successfully")
    print(f"  Manufacturing nodes: {len(model.manufacturing_nodes)}")
    print(f"  Products: {len(model.products)}")
    print(f"  Date range: {start_date} to {end_date}")

    # Solve
    print("\n" + "=" * 80)
    print("SOLVING OPTIMIZATION MODEL")
    print("=" * 80)

    result = model.solve(
        solver_name='appsi_highs',
        mip_gap=0.01,  # 1% optimality gap
        time_limit_seconds=300.0,   # 5 minutes
    )

    # Check result status
    from pyomo.opt import TerminationCondition
    acceptable_statuses = [TerminationCondition.optimal, TerminationCondition.feasible,
                          TerminationCondition.maxTimeLimit, TerminationCondition.intermediateNonInteger]
    is_acceptable = (result.termination_condition in acceptable_statuses or
                    (hasattr(result.termination_condition, 'name') and
                     any(status.name == result.termination_condition.name
                         for status in acceptable_statuses)))

    if not is_acceptable:
        print(f"\n✗ Solve failed with status: {result.termination_condition}")
        return

    print(f"\n✓ Solve completed with status: {result.termination_condition}")
    print(f"  Solve time: {result.solve_time_seconds:.2f}s")
    print(f"  Objective value: ${result.objective_value:,.2f}")

    # Extract and analyze weekend production
    print("\n" + "=" * 80)
    print("WEEKEND PRODUCTION ANALYSIS")
    print("=" * 80)

    # Get solution details
    solution = model.get_solution()
    production_schedule = solution.get('production_by_date_product', {})

    # Group production by weekend pairs
    weekend_production = []
    for (prod_date, product), quantity in production_schedule.items():
        if quantity > 0:
            labor_day = labor_calendar.get_labor_day(prod_date)

            if labor_day and not labor_day.is_fixed_day:
                # This is weekend/holiday production
                production_rate = 1400  # units/hour
                hours_used = quantity / production_rate
                hours_paid = max(hours_used, labor_day.minimum_hours)

                labor_cost = hours_paid * (labor_day.non_fixed_rate or labor_day.overtime_rate)

                weekend_production.append({
                    'date': prod_date,
                    'day_name': prod_date.strftime('%A'),
                    'product': product,
                    'quantity': quantity,
                    'hours_used': hours_used,
                    'hours_paid': hours_paid,
                    'labor_cost': labor_cost,
                    'wasted_hours': hours_paid - hours_used
                })

    # Sort by date
    weekend_production.sort(key=lambda x: x['date'])

    if not weekend_production:
        print("\n✓ No weekend production scheduled (optimal!)")
    else:
        print(f"\n{'Weekend Production Days':.<40} {len(weekend_production)}")
        print("\nDetailed Breakdown:")
        print("-" * 120)
        print(f"{'Date':<12} {'Day':<10} {'Product':<25} {'Qty':>8} {'Hours Used':>10} {'Hours Paid':>10} {'Wasted':>8} {'Cost':>12}")
        print("-" * 120)

        total_weekend_cost = 0
        total_wasted_hours = 0

        for wp in weekend_production:
            print(f"{wp['date']} {wp['day_name']:<10} {wp['product']:<25} "
                  f"{wp['quantity']:>8.0f} {wp['hours_used']:>10.2f} {wp['hours_paid']:>10.2f} "
                  f"{wp['wasted_hours']:>8.2f} ${wp['labor_cost']:>11,.2f}")
            total_weekend_cost += wp['labor_cost']
            total_wasted_hours += wp['wasted_hours']

        print("-" * 120)
        print(f"{'TOTAL':>37} {'':<25} {'':<8} {'':<10} {'':<10} "
              f"{total_wasted_hours:>8.2f} ${total_weekend_cost:>11,.2f}")
        print("-" * 120)

        # Identify consecutive weekend pairs with same product
        print("\n" + "=" * 80)
        print("CONSOLIDATION OPPORTUNITIES")
        print("=" * 80)

        consolidation_savings = 0
        for i in range(len(weekend_production) - 1):
            curr = weekend_production[i]
            next_wp = weekend_production[i + 1]

            # Check if consecutive days with same product
            if (next_wp['date'] - curr['date']).days == 1 and curr['product'] == next_wp['product']:
                # Calculate potential savings
                combined_qty = curr['quantity'] + next_wp['quantity']
                combined_hours_used = combined_qty / 1400
                combined_hours_paid = max(combined_hours_used, labor_calendar.get_labor_day(curr['date']).minimum_hours)

                rate = labor_calendar.get_labor_day(curr['date']).non_fixed_rate or labor_calendar.get_labor_day(curr['date']).overtime_rate
                combined_cost = combined_hours_paid * rate

                current_cost = curr['labor_cost'] + next_wp['labor_cost']
                savings = current_cost - combined_cost

                print(f"\n🔴 INEFFICIENCY DETECTED:")
                print(f"   Product: {curr['product']}")
                print(f"   Current: {curr['date']} ({curr['quantity']:.0f} units) + {next_wp['date']} ({next_wp['quantity']:.0f} units)")
                print(f"   Current Cost: ${curr['labor_cost']:,.2f} + ${next_wp['labor_cost']:,.2f} = ${current_cost:,.2f}")
                print(f"   Consolidated Cost: ${combined_cost:,.2f} (one {combined_hours_paid:.2f}h shift)")
                print(f"   POTENTIAL SAVINGS: ${savings:,.2f} ({savings/current_cost*100:.1f}%)")

                consolidation_savings += savings

        if consolidation_savings > 0:
            print(f"\n{'='*80}")
            print(f"TOTAL CONSOLIDATION OPPORTUNITY: ${consolidation_savings:,.2f}")
            print(f"{'='*80}")
            print("\n⚠️  MODEL BUG CONFIRMED: Optimizer is splitting weekend production inefficiently")
            print("   Root cause: 4-hour minimum cost constraint not preventing consecutive day splits")
        else:
            print("\n✓ No obvious consolidation opportunities found")
            print("   Weekend production appears optimal")

    # Print cost breakdown
    print("\n" + "=" * 80)
    print("COST BREAKDOWN")
    print("=" * 80)

    labor_cost = solution.get('total_labor_cost', 0)
    production_cost = solution.get('total_production_cost', 0)
    transport_cost = solution.get('total_transport_cost', 0)
    holding_cost = solution.get('total_holding_cost', 0)
    shortage_cost = solution.get('total_shortage_cost', 0)
    total_cost = labor_cost + production_cost + transport_cost + holding_cost + shortage_cost

    cost_items = [
        ('Labor Cost', labor_cost),
        ('Production Cost', production_cost),
        ('Transport Cost', transport_cost),
        ('Holding Cost', holding_cost),
        ('Shortage Cost', shortage_cost),
    ]

    for name, cost in sorted(cost_items, key=lambda x: x[1], reverse=True):
        if cost > 0:
            pct = (cost / total_cost) * 100 if total_cost > 0 else 0
            print(f"{name:.<40} ${cost:>12,.2f} ({pct:>5.1f}%)")

    print("-" * 80)
    print(f"{'TOTAL':.<40} ${total_cost:>12,.2f}")

    # Print demand satisfaction
    print("\n" + "=" * 80)
    print("DEMAND SATISFACTION")
    print("=" * 80)

    # Calculate total demand from forecast
    total_demand = sum(e.quantity for e in forecast.entries)
    total_shortage = solution.get('total_shortage', 0)
    fill_rate = ((total_demand - total_shortage) / total_demand * 100) if total_demand > 0 else 0

    print(f"{'Total Demand':.<40} {total_demand:>12,.0f} units")
    print(f"{'Shortages':.<40} {total_shortage:>12,.0f} units")
    print(f"{'Fill Rate':.<40} {fill_rate:>12.1f}%")


if __name__ == '__main__':
    analyze_weekend_labor_cost()
