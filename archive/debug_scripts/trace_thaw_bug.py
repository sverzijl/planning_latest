"""Trace the thaw operation bug to find where inventory disappears.

The diagnostic shows:
- Thaw on 2025-10-31: 100 units (from prod_date=2025-10-13)
- Should create: ambient cohort with prod_date=2025-10-31
- Actual inventory in new cohort: 0 units
- MISSING: 100 units

This script traces the thaw_input term to see if it's being added correctly.
"""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast, ForecastEntry
from src.optimization import IntegratedProductionDistributionModel

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

start_date = date(2025, 10, 13)
end_date = start_date + timedelta(weeks=3) - timedelta(days=1)

forecast_entries = []
for day_offset in range(2, 21):
    forecast_entries.append(
        ForecastEntry(location_id='6110', product_id='TEST', forecast_date=start_date + timedelta(days=day_offset), quantity=100.0)
    )

forecast = Forecast(name='3w', entries=forecast_entries)

model = IntegratedProductionDistributionModel(
    forecast=forecast, labor_calendar=labor, manufacturing_site=manufacturing_site,
    cost_structure=costs, locations=locations, routes=routes,
    truck_schedules=trucks, start_date=start_date, end_date=end_date,
    use_batch_tracking=True, initial_inventory=None,
)

# Build model
pyomo_model = model.build_model()

# Solve
result = model.solve(solver_name='cbc', time_limit_seconds=60, mip_gap=0.01, tee=False)

if result.is_optimal() or result.is_feasible():
    solution = model.get_solution()
    
    thaw_ops = solution.get('thaw_operations', {})
    cohort_inv = solution.get('cohort_inventory', {})
    
    print("="*80)
    print("TRACING THAW OPERATION ON OCT 31")
    print("="*80)
    
    thaw_date = date(2025, 10, 31)
    thaw_qty = thaw_ops.get(('6122_Storage', 'TEST', date(2025, 10, 13), thaw_date), 0)
    
    print(f"\nThaw operation:")
    print(f"  Location: 6122_Storage")
    print(f"  Original prod_date: 2025-10-13")
    print(f"  Thaw date: {thaw_date}")
    print(f"  Quantity: {thaw_qty:,.0f} units")
    print()
    
    # According to line 2063-2073, thaw_input adds to ambient cohort with prod_date=thaw_date
    # Check: inventory_ambient_cohort[6122_Storage, TEST, 2025-10-31, 2025-10-31]
    
    target_cohort = ('6122_Storage', 'TEST', thaw_date, thaw_date, 'ambient')
    target_inv = cohort_inv.get(target_cohort, 0)
    
    print(f"Target ambient cohort (receives thaw_input):")
    print(f"  Cohort: {target_cohort}")
    print(f"  Inventory value: {target_inv:,.0f}")
    print()
    
    if target_inv < thaw_qty - 1:
        print(f"❌ BUG CONFIRMED:")
        print(f"   Thawed {thaw_qty:,.0f} units")
        print(f"   Target cohort has {target_inv:,.0f} units")
        print(f"   Missing: {thaw_qty - target_inv:,.0f} units")
        print()
        
        # Check the ambient balance equation for this cohort
        # According to line 2077, the equation is:
        # inventory_ambient_cohort[loc, prod, prod_date, curr_date] == 
        #     prev_cohort + production_input + ambient_arrivals + thaw_input - 
        #     demand_consumption - ambient_departures - freeze_output
        
        print("Checking terms in ambient balance for this cohort:")
        
        # Previous (should be 0 since prod_date = curr_date)
        prev_date = thaw_date - timedelta(days=1)
        prev_cohort_key = ('6122_Storage', 'TEST', thaw_date, prev_date, 'ambient')
        prev_inv = cohort_inv.get(prev_cohort_key, 0)
        print(f"  prev_cohort: {prev_inv}")
        
        # production_input (should be 0 since prod_date != curr_date for thawed inventory)
        # Actually WAIT - for 6122_Storage, if prod_date == curr_date, production_input is added
        # But thaw creates cohort with prod_date=thaw_date
        # So on thaw_date, prod_date=thaw_date=curr_date
        # Would production ALSO be added? That would double-count!
        
        prod_on_thaw_date = sum(
            qty for (d, p), qty in solution.get('production_by_date_product', {}).items()
            if d == thaw_date and p == 'TEST'
        )
        
        print(f"  production_input: {prod_on_thaw_date} (if loc==6122_Storage and prod_date==curr_date)")
        
        if prod_on_thaw_date > 0:
            print(f"    ⚠️ WARNING: Production on same day as thaw!")
            print(f"       Both production AND thaw_input add to same cohort")
            print(f"       This should be OK (both are inflows)")
        
        # thaw_input (should be 100 from the thaw operation)
        print(f"  thaw_input: {thaw_qty:,.0f} (from thaw operation)")
        
        # demand_consumption
        demand_consumed = sum(
            qty for (loc, prod, pd, cd), qty in solution.get('cohort_demand_consumption', {}).items()
            if loc == '6122_Storage' and pd == thaw_date and cd == thaw_date
        )
        print(f"  demand_consumption: {demand_consumed}")
        
        # ambient_departures (shipments from 6122_Storage on thaw_date)
        shipments_by_leg = solution.get('shipments_by_leg_product_date', {})
        
        departures_from_storage = 0
        for (leg, p, delivery_date), qty in shipments_by_leg.items():
            if leg[0] == '6122_Storage' and p == 'TEST':
                transit = model.leg_transit_days.get(leg, 0)
                depart_date = delivery_date - timedelta(days=transit)
                if depart_date == thaw_date:
                    departures_from_storage += qty
        
        print(f"  ambient_departures: {departures_from_storage}")
        
        # freeze_output
        freeze_on_thaw_date = solution.get('freeze_operations', {}).get(('6122_Storage', 'TEST', thaw_date, thaw_date), 0)
        print(f"  freeze_output: {freeze_on_thaw_date}")
        
        # Calculate expected inventory
        expected = prev_inv + prod_on_thaw_date + thaw_qty - demand_consumed - departures_from_storage - freeze_on_thaw_date
        
        print()
        print(f"Expected inventory: {expected:,.0f}")
        print(f"Actual inventory: {target_inv:,.0f}")
        print(f"Difference: {expected - target_inv:,.0f}")
        
        if abs(expected - target_inv) > 1:
            print()
            print("❌ Constraint equation is violated or incorrectly calculated!")
            print("   This indicates a bug in the constraint implementation")

