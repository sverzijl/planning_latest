"""Diagnose why material balance deficit appears at 3-week threshold.

The pattern shows:
- 1-2 weeks: Perfect balance (0 deficit)
- 3+ weeks: Deficit appears (-200 to -900)

This script compares 2-week vs 3-week scenarios to find the difference.
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

product = "TEST_PRODUCT"
destination = "6110"

print("="*80)
print("WEEK 3 THRESHOLD DIAGNOSTIC")
print("="*80)
print()

def run_detailed_test(num_weeks, test_name):
    """Run test with detailed diagnostics."""
    start_date = date(2025, 10, 13)
    end_date = start_date + timedelta(weeks=num_weeks) - timedelta(days=1)

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

    forecast = Forecast(name=test_name, entries=forecast_entries)

    model = IntegratedProductionDistributionModel(
        forecast=forecast, labor_calendar=labor, manufacturing_site=manufacturing_site,
        cost_structure=costs, locations=locations, routes=routes,
        truck_schedules=trucks, start_date=start_date, end_date=end_date,
        allow_shortages=True, enforce_shelf_life=True, use_batch_tracking=True,
        initial_inventory=None,
    )

    result = model.solve(solver_name='cbc', time_limit_seconds=60, mip_gap=0.01, tee=False)

    if not (result.is_optimal() or result.is_feasible()):
        print(f"{test_name}: INFEASIBLE")
        return None

    solution = model.get_solution()

    production_by_date = solution.get('production_by_date_product', {})
    cohort_inv = solution.get('cohort_inventory', {})
    consumption = sum(solution.get('cohort_demand_consumption', {}).values())

    # Track inventory at 6122_Storage by date and state
    storage_inv_by_date = {}
    for (loc, prod, pd, cd, state), qty in cohort_inv.items():
        if loc == '6122_Storage' and qty > 0.01:
            if cd not in storage_inv_by_date:
                storage_inv_by_date[cd] = {'ambient': 0.0, 'frozen': 0.0, 'total': 0.0}
            storage_inv_by_date[cd][state] += qty
            storage_inv_by_date[cd]['total'] += qty

    # Get freeze operations
    freeze_ops = solution.get('freeze_operations', {})
    freeze_by_date = {}
    for (loc, prod, pd, cd), qty in freeze_ops.items():
        if loc == '6122_Storage' and qty > 0.01:
            freeze_by_date[cd] = freeze_by_date.get(cd, 0.0) + qty

    # Calculate totals
    total_production = sum(production_by_date.values())
    first_day = sum(qty for (loc, prod, pd, cd, state), qty in cohort_inv.items() if cd == start_date)
    last_day = sum(qty for (loc, prod, pd, cd, state), qty in cohort_inv.items() if cd == end_date)

    supply = first_day + total_production
    usage = consumption + last_day
    balance = supply - usage

    print(f"{test_name}:")
    print(f"  Production: {total_production:,.0f} units")
    print(f"  Consumption: {consumption:,.0f} units")
    print(f"  Balance: {balance:+.0f} units")
    print()

    print(f"  6122_Storage frozen inventory by date:")
    for d in sorted(storage_inv_by_date.keys())[:10]:
        inv = storage_inv_by_date[d]
        freeze_today = freeze_by_date.get(d, 0)
        print(f"    {d}: frozen={inv['frozen']:>5,.0f}, ambient={inv['ambient']:>5,.0f}, freeze_ops={freeze_today:>5,.0f}")

    # Check for anomalies
    max_frozen_inv = max((inv['frozen'] for inv in storage_inv_by_date.values()), default=0)
    total_freeze = sum(freeze_ops.values())

    print(f"  Max frozen inventory at 6122_Storage: {max_frozen_inv:,.0f}")
    print(f"  Total freeze operations: {total_freeze:,.0f}")

    if max_frozen_inv > total_freeze + 10:
        print(f"  ❌ Frozen inventory ({max_frozen_inv}) > freeze operations ({total_freeze})")
        print(f"     Frozen inventory appearing without freeze operations!")
        print(f"     Phantom frozen inventory: {max_frozen_inv - total_freeze:,.0f} units")

    print()
    return balance

# Run comparisons
print("Comparing 2-week (works) vs 3-week (fails):")
print("="*80)
print()

balance_2w = run_detailed_test(2, "2-week scenario")
balance_3w = run_detailed_test(3, "3-week scenario")

if balance_2w is not None and balance_3w is not None:
    print("="*80)
    print("COMPARISON")
    print("="*80)
    print(f"2-week balance: {balance_2w:+.0f}")
    print(f"3-week balance: {balance_3w:+.0f}")
    print(f"Degradation at week 3: {balance_3w - balance_2w:+.0f} units")
