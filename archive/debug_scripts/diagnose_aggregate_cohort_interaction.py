"""Diagnose aggregate vs cohort constraint interaction bug.

Simple tests: Balance = 0 ✅
Full 4-week: Balance = -33k ❌

Both use the SAME constraints (aggregate + cohort), so why the difference?

Key difference to investigate:
- Simple tests: 1 prod, 1-2 dest, 1-2 weeks
- Full 4-week: 5 prods, 8 dests, 4 weeks, real forecast patterns

Hypothesis:
The shipment_cohort_aggregation_con links cohorts to aggregates:
  sum(shipment_leg_cohort[leg, prod, prod_date, dd]) == shipment_leg[leg, prod, dd]

If there's a mismatch in how these sum up, it could create phantom inventory.

This script tests if aggregate = sum(cohorts) in the solution.
"""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from src.models.truck_schedule import TruckScheduleCollection
from src.optimization import IntegratedProductionDistributionModel

# Parse real network
parser = MultiFileParser(
    forecast_file='data/examples/Gfree Forecast.xlsm',
    network_file='data/examples/Network_Config.xlsx',
)

forecast, locations, routes, labor, trucks_list, costs = parser.parse_all()

manuf_loc = [loc for loc in locations if loc.type == LocationType.MANUFACTURING][0]
manufacturing_site = ManufacturingSite(
    id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
    production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
    default_changeover_hours=0.5, production_cost_per_unit=costs.production_cost_per_unit,
)

trucks = TruckScheduleCollection(schedules=trucks_list)

start_date = date(2025, 10, 7)  # Use real forecast start
end_date = start_date + timedelta(weeks=4)

print("="*80)
print("AGGREGATE vs COHORT CONSISTENCY CHECK")
print("="*80)
print()

# Use full real forecast
model = IntegratedProductionDistributionModel(
    forecast=forecast, labor_calendar=labor, manufacturing_site=manufacturing_site,
    cost_structure=costs, locations=locations, routes=routes,
    truck_schedules=trucks, start_date=start_date, end_date=end_date,
    allow_shortages=True, enforce_shelf_life=True, use_batch_tracking=True,
    initial_inventory=None,
)

print(f"Building model with full real forecast...")
print(f"  Planning: {start_date} to {end_date}")
print()

result = model.solve(solver_name='cbc', time_limit_seconds=120, mip_gap=0.05, tee=False)

print(f"✓ Solved in {result.solve_time_seconds:.2f}s")
print()

if result.is_optimal() or result.is_feasible():
    solution = model.get_solution()

    # Get shipments (aggregate level)
    shipments_by_leg = solution.get('shipments_by_leg_product_date', {})

    # Get batch shipments (from cohort aggregation)
    batch_shipments = solution.get('batch_shipments', [])

    print("="*80)
    print("CHECKING AGGREGATE vs COHORT CONSISTENCY")
    print("="*80)
    print()

    # Sum total shipments at aggregate level
    total_aggregate = sum(shipments_by_leg.values())

    # Get cohort shipments and sum them
    # In the solution extraction, batch_shipments contains the cohort-level detail
    total_cohort = 0
    if batch_shipments:
        # batch_shipments is a list of Shipment objects with batch_id
        # Each should correspond to a cohort shipment
        total_cohort = sum(s.quantity for s in batch_shipments)
    else:
        # Calculate from solution dict directly if available
        # The solution should have a way to get cohort shipments
        print("  Warning: batch_shipments not available, checking alternative")

        # Check if we can access the Pyomo model directly
        pyomo_model = model.model if hasattr(model, 'model') else None
        if pyomo_model and hasattr(pyomo_model, 'shipment_leg_cohort'):
            print(f"  Calculating cohort total from Pyomo variables...")
            from pyomo.environ import value
            total_cohort = sum(
                value(var) for var in pyomo_model.shipment_leg_cohort.values()
                if value(var) > 0.001
            )

    print(f"Total aggregate shipments: {total_aggregate:,.0f}")
    print(f"Total cohort shipments: {total_cohort:,.0f}")
    print()

    if abs(total_aggregate - total_cohort) > 100:
        print(f"❌ MISMATCH! Aggregate != Sum(Cohorts)")
        print(f"   Difference: {total_aggregate - total_cohort:+,.0f}")
        print(f"   This could create phantom inventory!")
    else:
        print(f"✓ Aggregate matches cohorts (within rounding)")

    # Check inventory consistency
    print()
    print("="*80)
    print("CHECKING INVENTORY CONSISTENCY")
    print("="*80)
    print()

    # Does total ambient cohort inventory == aggregate ambient inventory?
    cohort_inv = solution.get('cohort_inventory', {})

    # Sample a few locations
    for loc_id in ['6122_Storage', '6104', '6125', 'Lineage']:
        # Sum cohort inventory at this location on final day
        cohort_total = sum(
            qty for (loc, prod, pd, cd, state), qty in cohort_inv.items()
            if loc == loc_id and cd == end_date
        )

        print(f"{loc_id} final day inventory (cohorts): {cohort_total:,.0f}")

    # Check if there's aggregate inventory variables
    inv_frozen_by_loc = solution.get('inventory_frozen_by_loc_product_date', {})
    inv_ambient_by_loc = solution.get('inventory_ambient_by_loc_product_date', {})

    if inv_frozen_by_loc or inv_ambient_by_loc:
        print()
        print("Checking aggregate inventory variables:")

        for loc_id in ['6122_Storage', '6104', '6125', 'Lineage']:
            # Sum aggregate inventory
            agg_frozen = sum(qty for (loc, prod, d), qty in inv_frozen_by_loc.items() if loc == loc_id and d == end_date)
            agg_ambient = sum(qty for (loc, prod, d), qty in inv_ambient_by_loc.items() if loc == loc_id and d == end_date)
            agg_total = agg_frozen + agg_ambient

            cohort_total = sum(
                qty for (loc, prod, pd, cd, state), qty in cohort_inv.items()
                if loc == loc_id and cd == end_date
            )

            if abs(agg_total - cohort_total) > 10:
                print(f"  {loc_id}: Aggregate={agg_total:,.0f}, Cohort={cohort_total:,.0f}, Diff={agg_total - cohort_total:+,.0f} ❌")
            else:
                print(f"  {loc_id}: Aggregate={agg_total:,.0f}, Cohort={cohort_total:,.0f} ✓")
    else:
        print("  (Aggregate inventory not extracted - cohort mode only)")

    # Material balance
    production = sum(solution.get('production_by_date_product', {}).values())
    consumption = sum(solution.get('cohort_demand_consumption', {}).values())
    first_day = sum(qty for (loc, prod, pd, cd, state), qty in cohort_inv.items() if cd == start_date)
    last_day = sum(qty for (loc, prod, pd, cd, state), qty in cohort_inv.items() if cd == end_date)

    supply = first_day + production
    usage = consumption + last_day
    balance = supply - usage

    print()
    print("="*80)
    print("MATERIAL BALANCE")
    print("="*80)
    print(f"Production: {production:,.0f}")
    print(f"Consumption: {consumption:,.0f}")
    print(f"First day: {first_day:,.0f}")
    print(f"Last day: {last_day:,.0f}")
    print(f"Balance: {balance:+,.0f}")

    if abs(balance) > 1000:
        print(f"\n❌ Significant deficit: {balance:,.0f} units")
        print(f"   This is the -33k bug we're investigating")
    else:
        print(f"\n✓ Material balance acceptable")
