"""Simple test to diagnose boundary condition bug."""

from datetime import date, timedelta
from src.models import (
    Location, LocationType, StorageMode,
    Route, Product, Forecast, ForecastEntry,
    LaborCalendar, LaborDay, ManufacturingSite,
    CostStructure
)
from src.optimization.integrated_model import IntegratedProductionDistributionModel

# Create simple network
manufacturing = Location(
    id="6122",
    name="Manufacturing Site",
    type=LocationType.MANUFACTURING,
    storage_mode=StorageMode.AMBIENT,
)

dest = Location(
    id="6103",
    name="Destination",
    type=LocationType.BREADROOM,
    storage_mode=StorageMode.AMBIENT,
)

route = Route(
    id="R1",
    origin_id="6122",
    destination_id="6103",
    transport_mode=StorageMode.AMBIENT,
    transit_time_days=2.0,  # 2-day transit
    cost=0.3
)

product = Product(id="PROD_A", name="Product A", sku="SKU_A", ambient_shelf_life_days=17)

# Demand on Jan 15
forecast_start = date(2025, 1, 15)
forecast = Forecast(
    name="Test Forecast",
    entries=[
        ForecastEntry(location_id="6103", product_id="PROD_A", forecast_date=forecast_start, quantity=500),
    ]
)

# Labor calendar starts Jan 12 (3 days before demand)
labor_start = date(2025, 1, 12)
labor_calendar = LaborCalendar(
    name="Test Calendar",
    days=[
        LaborDay(date=labor_start + timedelta(days=i), fixed_hours=12.0, regular_rate=50.0, overtime_rate=75.0)
        for i in range(10)
    ]
)

mfg_site = ManufacturingSite(
    id="6122",
    name="Manufacturing",
    type=LocationType.MANUFACTURING,
    storage_mode=StorageMode.AMBIENT,
    production_rate=1400.0
)

costs = CostStructure(
    production_cost_per_unit=0.8,
    holding_cost_frozen_per_unit_day=0.05,
    storage_cost_ambient_per_unit_day=0.02,
    shortage_penalty_per_unit=1.5
)

print("Creating model...")
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=mfg_site,
    cost_structure=costs,
    locations=[manufacturing, dest],
    routes=[route],
)

print(f"\n=== Model Setup ===")
print(f"Forecast start: {forecast_start}")
print(f"Labor calendar start: {labor_start}")
print(f"Planning start: {model.start_date}")
print(f"Planning end: {model.end_date}")
print(f"Production dates: {sorted(model.production_dates)}")

print(f"\n=== Building Pyomo Model ===")
pyomo_model = model.build_model()

print(f"Pyomo dates: {sorted(pyomo_model.dates)}")
print(f"Inventory ambient index count: {len(model.inventory_ambient_index_set)}")

# Check if Jan 13 is in the index
for loc_id in ['6122']:
    for prod_id in ['PROD_A']:
        for test_date in [date(2025, 1, 12), date(2025, 1, 13), date(2025, 1, 14), date(2025, 1, 15)]:
            in_index = (loc_id, prod_id, test_date) in model.inventory_ambient_index_set
            print(f"  ({loc_id}, {prod_id}, {test_date}): in index = {in_index}")

print(f"\n=== Attempting Solve ===")
try:
    result = model.solve(solver_name='cbc')
    print(f"Termination: {result.termination_condition}")
    print(f"Success: {result.success}")
    if not result.success and result.infeasibility_message:
        print(f"Infeasibility message: {result.infeasibility_message}")
    else:
        print(f"Objective value: {result.objective_value}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
