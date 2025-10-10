"""Test boundary condition fix for first-day morning trucks."""

from datetime import date, timedelta
from src.models import (
    TruckSchedule, ManufacturingSite, LaborCalendar, LaborDay,
    Location, Route, Forecast, Product, CostStructure
)
from src.optimization.integrated_model import IntegratedProductionDistributionModel

# Setup minimal data
from src.models import LocationType, StorageMode

# Labor calendar
labor_cal = LaborCalendar(
    name='Test Calendar',
    days=[
        LaborDay(
            date=date(2024, 10, 13),
            fixed_hours=12.0,
            regular_rate=50.0,
            overtime_rate=75.0
        ),
    ]
)

mfg = ManufacturingSite(
    id='6122',
    name='Manufacturing',
    type=LocationType.MANUFACTURING,
    storage_mode=StorageMode.AMBIENT,
    production_rate=1400
)

locations = [
    mfg,
    Location(
        id='6104',
        name='NSW Hub',
        type=LocationType.STORAGE,
        storage_mode=StorageMode.AMBIENT
    ),
]

routes = [
    Route(id='R1', origin_id='6122', destination_id='6104', transit_time_days=1, transport_mode=StorageMode.AMBIENT, cost=0.5),
]

products = [Product(id='P1', name='Product1', ambient_shelf_life_days=17)]

# Morning truck departs Day1 (Oct 13), delivers to 6104 on Day2 (Oct 14)
from src.models import DayOfWeek, DepartureType
trucks = [
    TruckSchedule(
        id='T1',
        day_of_week=DayOfWeek.SUNDAY,  # Oct 13, 2024 is Sunday
        departure_type=DepartureType.MORNING,
        origin_id='6122',
        destination_ids=['6104'],
        capacity_units=14080
    )
]

# Demand at 6104 on Day2
forecasts = [
    Forecast(location_id='6104', product_id='P1', date=date(2024, 10, 14), quantity=1000.0)
]

costs = CostStructure(
    production_cost_per_unit=1.0,
    holding_cost_per_unit_day=0.01,
    shortage_penalty_per_unit=100.0,
    transport_cost_per_unit_km=0.0
)

# Create model with initial inventory = 50,000
model = IntegratedProductionDistributionModel(
    manufacturing_site=mfg,
    locations=locations,
    routes=routes,
    products=products,
    forecasts=forecasts,
    labor_calendar=labor_cal,
    truck_schedules=trucks,
    cost_structure=costs,
    start_date=date(2024, 10, 13),
    end_date=date(2024, 10, 14),
    initial_inventory={('6122', 'P1'): 50000.0}
)

print('Building model...')
pyomo_model = model.build_model()
print(f'Model built successfully!')
print(f'Planning horizon: {model.planning_start_date} to {model.planning_end_date}')
print(f'Initial inventory at 6122: {model.initial_inventory.get(("6122", "P1"), 0)}')
print(f'Dates in model: {sorted(pyomo_model.dates)}')
print(f'\nAttempting solve...')

result = model.solve(solver_name='cbc', time_limit=60)
print(f'\nSolver status: {result.solver.status}')
print(f'Termination condition: {result.solver.termination_condition}')

if str(result.solver.termination_condition) == 'optimal':
    print('\n=== SOLUTION FOUND! ===')
    print(f'Total cost: ${pyomo_model.total_cost():.2f}')

    # Check production
    print('\nProduction:')
    for d in sorted(pyomo_model.dates):
        for prod in pyomo_model.products:
            prod_qty = pyomo_model.production[d, prod].value
            if prod_qty and prod_qty > 0.1:
                print(f'  {d}: {prod_qty:.0f} units of {prod}')

    # Check truck loads
    print('\nTruck loads:')
    for idx in pyomo_model.trucks:
        for dest in pyomo_model.truck_destinations:
            for prod in pyomo_model.products:
                for delivery_date in pyomo_model.dates:
                    load = pyomo_model.truck_load[idx, dest, prod, delivery_date].value
                    if load and load > 0.1:
                        truck = model.truck_by_index[idx]
                        transit_days = model._get_truck_transit_days(idx, dest)
                        departure_date = delivery_date - timedelta(days=transit_days)
                        print(f'  Truck {idx} ({truck.departure_type}): departs {departure_date}, delivers {load:.0f} units of {prod} to {dest} on {delivery_date}')

    # Check inventory
    print('\nInventory at manufacturing site (6122):')
    for d in sorted(pyomo_model.dates):
        for prod in pyomo_model.products:
            inv = pyomo_model.inventory_ambient['6122', prod, d].value
            if inv is not None:
                print(f'  {d}: {inv:.0f} units of {prod}')

    # Check demand satisfaction
    print('\nDemand satisfaction:')
    for d in sorted(pyomo_model.dates):
        for loc in ['6104']:
            for prod in pyomo_model.products:
                if (loc, prod, d) in model.demand:
                    demand = model.demand[(loc, prod, d)]
                    inv = pyomo_model.inventory_ambient[loc, prod, d].value if (loc, prod, d) in model.inventory_ambient_index_set else 0
                    print(f'  {d} at {loc}: demand={demand:.0f}, inventory={inv:.0f}')
else:
    print('\n=== Model is INFEASIBLE or failed to solve ===')

    # Try to diagnose
    print('\nDiagnostic information:')
    print(f'  Initial inventory: {model.initial_inventory.get(("6122", "P1"), 0)}')
    print(f'  Total demand: {sum(f.quantity for f in forecasts)}')
    print(f'  Available production capacity: {mfg.production_rate * 12.0} units')
