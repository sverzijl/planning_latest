"""Test if material balance deficit scales with planning horizon length.

Progressive horizon test:
- 1 product, 1 destination (6110 direct), varying weeks: 1, 2, 3, 4
- Isolates if deficit is time-dependent
"""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast, ForecastEntry
from src.optimization import IntegratedProductionDistributionModel

# Parse real network
parser = MultiFileParser(
    forecast_file='data/examples/Gfree Forecast.xlsm',
    network_file='data/examples/Network_Config.xlsx',
)

_, locations, routes, labor, trucks_list, costs = parser.parse_all()

manuf_loc = [loc for loc in locations if loc.type == LocationType.MANUFACTURING][0]
manufacturing_site = ManufacturingSite(
    id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
    production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
    default_changeover_hours=0.5, production_cost_per_unit=costs.production_cost_per_unit,
)

trucks = TruckScheduleCollection(schedules=trucks_list)

product = "HELGAS GFREE WHOLEM 500G"
destination = "6110"  # Direct route

print("="*80)
print("HORIZON LENGTH vs DEFICIT ANALYSIS")
print("="*80)
print(f"Product: {product}")
print(f"Destination: {destination} (direct ambient route)")
print()

for num_weeks in [1, 2, 3, 4]:
    start_date = date(2025, 10, 13)
    end_date = start_date + timedelta(weeks=num_weeks) - timedelta(days=1)

    # Forecast: 100 units/day starting day 2
    forecast_entries = []
    for day_offset in range(2, num_weeks * 7):
        forecast_entries.append(
            ForecastEntry(
                location_id=destination,
                product_id=product,
                forecast_date=start_date + timedelta(days=day_offset),
                quantity=100.0,
            )
        )

    forecast = Forecast(name=f"{num_weeks}w", entries=forecast_entries)
    total_demand = sum(e.quantity for e in forecast_entries)

    # Model and solve
    model = IntegratedProductionDistributionModel(
        forecast=forecast, labor_calendar=labor, manufacturing_site=manufacturing_site,
        cost_structure=costs, locations=locations, routes=routes,
        truck_schedules=trucks, start_date=start_date, end_date=end_date,
        allow_shortages=True, enforce_shelf_life=True, use_batch_tracking=True,
        initial_inventory=None,
    )

    result = model.solve(solver_name='cbc', time_limit_seconds=60, mip_gap=0.01, tee=False)

    if not (result.is_optimal() or result.is_feasible()):
        print(f"{num_weeks}w: INFEASIBLE")
        continue

    solution = model.get_solution()
    production = sum(solution.get('production_by_date_product', {}).values())
    consumption = sum(solution.get('cohort_demand_consumption', {}).values())

    cohort_inv = solution.get('cohort_inventory', {})
    first_day = sum(qty for (loc, prod, pd, cd, state), qty in cohort_inv.items() if cd == start_date)
    last_day = sum(qty for (loc, prod, pd, cd, state), qty in cohort_inv.items() if cd == end_date)

    supply = first_day + production
    usage = consumption + last_day
    balance = supply - usage

    status = "✅" if abs(balance) <= 1 else "❌"
    print(f"{num_weeks}w: Demand={total_demand:>5,.0f} | Prod={production:>5,.0f} | Cons={consumption:>5,.0f} | D1={first_day:>4,.0f} | End={last_day:>5,.0f} | Balance={balance:>6.0f} {status}")

print()
print("If deficit grows with horizon length:")
print("  → Time-based accumulation bug")
print("If deficit appears at specific week threshold:")
print("  → Edge case at that horizon length")
print("If deficit is random:")
print("  → Different bug each time (stochastic issue)")
