"""Debug inventory variable initialization issue."""

from datetime import date, timedelta
from src.models import (
    Location, LocationType, StorageMode,
    Route, Product, Forecast, ForecastEntry,
    LaborCalendar, LaborDay, ManufacturingSite,
    CostStructure
)
from src.optimization.integrated_model import IntegratedProductionDistributionModel
from pyomo.environ import value

# Replicate test setup
manufacturing = Location(
    id="6122",
    name="Manufacturing Site",
    type=LocationType.MANUFACTURING,
    storage_mode=StorageMode.AMBIENT,
)

hub = Location(
    id="6125",
    name="VIC Hub",
    type=LocationType.STORAGE,
    storage_mode=StorageMode.AMBIENT,
)

dest1 = Location(
    id="6103",
    name="Breadroom 1",
    type=LocationType.BREADROOM,
    storage_mode=StorageMode.AMBIENT,
)

dest2 = Location(
    id="6105",
    name="Breadroom 2",
    type=LocationType.BREADROOM,
    storage_mode=StorageMode.AMBIENT,
)

routes = [
    Route(id="R1", origin_id="6122", destination_id="6125", transport_mode=StorageMode.AMBIENT, transit_time_days=1.0, cost=0.1),
    Route(id="R2", origin_id="6125", destination_id="6103", transport_mode=StorageMode.AMBIENT, transit_time_days=1.0, cost=0.2),
    Route(id="R3", origin_id="6125", destination_id="6105", transport_mode=StorageMode.AMBIENT, transit_time_days=1.0, cost=0.2),
    Route(id="R4", origin_id="6122", destination_id="6103", transport_mode=StorageMode.AMBIENT, transit_time_days=2.0, cost=0.3),
]

products = [
    Product(id="PROD_A", name="Product A", sku="SKU_A", ambient_shelf_life_days=17),
    Product(id="PROD_B", name="Product B", sku="SKU_B", ambient_shelf_life_days=17),
]

# Demand on Jan 15-16
forecast_start = date(2025, 1, 15)
forecast = Forecast(
    name="Test Forecast",
    entries=[
        ForecastEntry(location_id="6103", product_id="PROD_A", forecast_date=forecast_start, quantity=500),
        ForecastEntry(location_id="6103", product_id="PROD_A", forecast_date=forecast_start + timedelta(days=1), quantity=500),
        ForecastEntry(location_id="6105", product_id="PROD_A", forecast_date=forecast_start, quantity=300),
        ForecastEntry(location_id="6105", product_id="PROD_A", forecast_date=forecast_start + timedelta(days=1), quantity=300),
        ForecastEntry(location_id="6103", product_id="PROD_B", forecast_date=forecast_start, quantity=400),
        ForecastEntry(location_id="6103", product_id="PROD_B", forecast_date=forecast_start + timedelta(days=1), quantity=400),
    ]
)

# Labor calendar starts Jan 12
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
    locations=[manufacturing, hub, dest1, dest2],
    routes=routes,
)

print(f"\nPlanning horizon: {model.start_date} to {model.end_date}")
print(f"Production dates: {sorted(model.production_dates)}")

print(f"\nBuilding Pyomo model...")
pyomo_model = model.build_model()

print(f"Pyomo dates: {sorted(pyomo_model.dates)}")
print(f"Inventory ambient index entries: {len(model.inventory_ambient_index_set)}")
print(f"Pyomo model ID: {id(pyomo_model)}")

# Check specific entries
print(f"\nChecking inventory index for location 6103, product PROD_A:")
for test_date in [date(2025, 1, 12), date(2025, 1, 13), date(2025, 1, 14), date(2025, 1, 15), date(2025, 1, 16)]:
    key = ("6103", "PROD_A", test_date)
    in_index = key in model.inventory_ambient_index_set
    print(f"  {test_date}: in_index={in_index}")

print(f"\nSolving...")
result = model.solve(solver_name='cbc')

print(f"After solve, model.model ID: {id(model.model) if hasattr(model, 'model') else 'N/A'}")
print(f"Are they the same object? {id(pyomo_model) == id(model.model) if hasattr(model, 'model') else 'N/A'}")

print(f"\nTermination: {result.termination_condition}")
print(f"Solver status: {result.solver_status}")
print(f"Success: {result.success}")

if not result.success:
    print(f"Infeasibility message: {result.infeasibility_message}")

# Try to access variables from the CORRECT model (the one used in solve())
solved_model = model.model

print(f"\nTrying to access inventory variables for breadroom 6103 (from SOLVED model):")
for test_date in [date(2025, 1, 12), date(2025, 1, 13), date(2025, 1, 14), date(2025, 1, 15)]:
    try:
        var = solved_model.inventory_ambient["6103", "PROD_A", test_date]
        has_value = var.value is not None
        val = var.value if has_value else "None"
        print(f"  inventory_ambient['6103', 'PROD_A', {test_date}] = {val} (has_value={has_value})")
    except KeyError:
        print(f"  inventory_ambient['6103', 'PROD_A', {test_date}] - KEY ERROR")
    except Exception as e:
        print(f"  inventory_ambient['6103', 'PROD_A', {test_date}] - ERROR: {e}")

print(f"\nTrying to access inventory variables for manufacturing 6122 (from SOLVED model):")
for test_date in [date(2025, 1, 12), date(2025, 1, 13), date(2025, 1, 14), date(2025, 1, 15)]:
    try:
        var = solved_model.inventory_ambient["6122", "PROD_A", test_date]
        has_value = var.value is not None
        val = var.value if has_value else "None"
        print(f"  inventory_ambient['6122', 'PROD_A', {test_date}] = {val} (has_value={has_value})")
    except KeyError:
        print(f"  inventory_ambient['6122', 'PROD_A', {test_date}] - KEY ERROR")
    except Exception as e:
        print(f"  inventory_ambient['6122', 'PROD_A', {test_date}] - ERROR: {e}")

print(f"\nTrying to access production variables (from SOLVED model):")
for test_date in [date(2025, 1, 12), date(2025, 1, 13), date(2025, 1, 14), date(2025, 1, 15)]:
    try:
        var = solved_model.production[test_date, "PROD_A"]
        has_value = var.value is not None
        val = var.value if has_value else "None"
        print(f"  production[{test_date}, 'PROD_A'] = {val} (has_value={has_value})")
    except KeyError:
        print(f"  production[{test_date}, 'PROD_A'] - KEY ERROR")
    except Exception as e:
        print(f"  production[{test_date}, 'PROD_A'] - ERROR: {e}")

# Check if constraints exist
print(f"\nChecking constraints:")
print(f"  Has inventory_ambient_balance_con: {hasattr(pyomo_model, 'inventory_ambient_balance_con')}")
if hasattr(pyomo_model, 'inventory_ambient_balance_con'):
    con = pyomo_model.inventory_ambient_balance_con
    print(f"  Number of constraints: {len(list(con))}")
    # Check specific constraint
    key = ("6103", "PROD_A", date(2025, 1, 13))
    if key in model.inventory_ambient_index_set:
        try:
            idx = model.inventory_ambient_index.index(key)
            constraint = con[key]
            print(f"  Constraint for {key} exists: {constraint is not None}")
        except:
            print(f"  Could not access constraint for {key}")
