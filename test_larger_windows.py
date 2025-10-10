"""Test larger window configurations: 28d/21d and 56d/49d."""
import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization import RollingHorizonSolver

print("Loading data...")
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

# Test configurations
configs = [
    ('28d/21d', 28, 21),
    ('56d/49d', 56, 49),
]

plans = {}

for name, window, overlap in configs:
    print(f"\n{'='*70}")
    print(f"{name}: Solving...")
    print(f"{'='*70}")

    solver = RollingHorizonSolver(
        window_size_days=window,
        overlap_days=overlap,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing_site,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        truck_schedules=truck_schedules,
        allow_shortages=True,
        enforce_shelf_life=True,
        time_limit_per_window=120,
    )

    result = solver.solve(
        forecast=full_forecast,
        granularity_config=None,
        solver_name='cbc',
        use_aggressive_heuristics=True,
        verbose=True
    )

    # Extract the complete plan
    production_plan = result.complete_production_plan
    shipment_plan = result.complete_shipment_plan

    # Calculate total production
    total_production = sum(
        sum(products.values())
        for products in production_plan.values()
    )

    # Calculate production days
    production_days = len([
        date for date, products in production_plan.items()
        if sum(products.values()) > 0
    ])

    print(f"\n{'='*70}")
    print(f"RESULTS FOR {name}:")
    print(f"{'='*70}")
    print(f"  Rolling horizon reported cost: ${result.total_cost:,.2f}")
    print(f"  Windows solved: {result.num_windows}")
    print(f"  All feasible: {result.all_feasible}")
    print(f"  Total solve time: {result.total_solve_time:.2f}s")
    print(f"  Avg time/window: {result.average_solve_time_per_window:.2f}s")
    print(f"  Total production: {total_production:,.0f} units")
    print(f"  Production days: {production_days}")
    print(f"  Shipments: {len(shipment_plan)}")

    plans[name] = {
        'production': production_plan,
        'shipments': shipment_plan,
        'reported_cost': result.total_cost,
        'total_production': total_production,
        'production_days': production_days,
        'solve_time': result.total_solve_time,
        'num_windows': result.num_windows,
    }

# Independent cost calculation for comparison
print(f"\n{'='*70}")
print("INDEPENDENT COST CALCULATION")
print(f"{'='*70}")

for name, plan_data in plans.items():
    production_plan = plan_data['production']
    shipment_plan = plan_data['shipments']

    # Calculate labor cost
    labor_cost = 0.0
    for date, products in production_plan.items():
        total_units = sum(products.values())
        if total_units > 0:
            labor_day = labor_calendar.get_labor_day(date)
            if labor_day:
                hours_needed = total_units / 1400  # production rate is 1400 units/hour

                if labor_day.is_fixed_day:
                    fixed_hours = min(hours_needed, labor_day.fixed_hours)
                    overtime_hours = max(0, hours_needed - labor_day.fixed_hours)
                    labor_cost += (labor_day.regular_rate * fixed_hours +
                                 labor_day.overtime_rate * overtime_hours)
                else:
                    # Non-fixed day with minimum hours
                    hours_paid = max(hours_needed, labor_day.minimum_hours or 0)
                    labor_cost += labor_day.non_fixed_rate * hours_paid

    # Calculate production cost
    production_cost = 0.0
    for date, products in production_plan.items():
        total_units = sum(products.values())
        production_cost += cost_structure.production_cost_per_unit * total_units

    # Calculate transport cost (from shipments)
    transport_cost = 0.0
    for shipment in shipment_plan:
        # Look up route cost
        route = next((r for r in routes if r.route_id == shipment.route_id), None)
        if route:
            transport_cost += route.cost_per_unit * shipment.quantity

    total_cost = labor_cost + production_cost + transport_cost

    print(f"\n{name}:")
    print(f"  Labor cost:      ${labor_cost:>12,.2f}")
    print(f"  Production cost: ${production_cost:>12,.2f}")
    print(f"  Transport cost:  ${transport_cost:>12,.2f}")
    print(f"  ------------------------------------------")
    print(f"  ACTUAL TOTAL:    ${total_cost:>12,.2f}")
    print(f"  Reported by RH:  ${plan_data['reported_cost']:>12,.2f}")
    print(f"  Difference:      ${total_cost - plan_data['reported_cost']:>12,.2f}")

# Compare the configurations
print(f"\n{'='*70}")
print("CONFIGURATION COMPARISON")
print(f"{'='*70}")

for name in configs:
    config_name = name[0]
    plan = plans[config_name]
    print(f"\n{config_name}:")
    print(f"  Production:   {plan['total_production']:>10,.0f} units")
    print(f"  Prod days:    {plan['production_days']:>10} days")
    print(f"  Windows:      {plan['num_windows']:>10}")
    print(f"  Solve time:   {plan['solve_time']:>10.1f}s")
    print(f"  Reported cost: ${plan['reported_cost']:>11,.2f}")

print(f"\n{'='*70}")
print("TEST COMPLETE")
print(f"{'='*70}")
