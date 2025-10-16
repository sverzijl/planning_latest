"""Test if solution loading from CBC works correctly."""

from datetime import date, timedelta
from src.models import (
    Location, LocationType, StorageMode,
    Route, Product, Forecast, ForecastEntry,
    LaborCalendar, LaborDay, ManufacturingSite,
    CostStructure
)
from src.optimization.integrated_model import IntegratedProductionDistributionModel
from pyomo.opt import SolverFactory

# Create simple model
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
    transit_time_days=2.0,
    cost=0.3
)

product = Product(id="PROD_A", name="Product A", sku="SKU_A", ambient_shelf_life_days=17)

forecast_start = date(2025, 1, 15)
forecast = Forecast(
    name="Test Forecast",
    entries=[
        ForecastEntry(location_id="6103", product_id="PROD_A", forecast_date=forecast_start, quantity=500),
    ]
)

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

print("Creating and building model...")
model_obj = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=mfg_site,
    cost_structure=costs,
    locations=[manufacturing, dest],
    routes=[route],
)
pyomo_model = model_obj.build_model()

print(f"Model built with {pyomo_model.nvariables()} variables and {pyomo_model.nconstraints()} constraints")

# Solve with both options
print(f"\n=== Test 1: Solve WITH symbolic_solver_labels=False (current setting) ===")
solver = SolverFactory('cbc')
results1 = solver.solve(pyomo_model, tee=False, symbolic_solver_labels=False, load_solutions=False)

print(f"Solver status: {results1.solver.status}")
print(f"Termination: {results1.solver.termination_condition}")
print(f"Solutions in results: {len(results1.solution) if hasattr(results1, 'solution') else 'N/A'}")

# Try to load solutions
try:
    pyomo_model.solutions.load_from(results1)
    print("Solutions loaded successfully")

    # Check variable values
    sample_var = pyomo_model.production[date(2025, 1, 13), "PROD_A"]
    print(f"Sample variable value: production[2025-01-13, 'PROD_A'] = {sample_var.value}")
except Exception as e:
    print(f"ERROR loading solutions: {e}")

# Reset model
print(f"\n=== Test 2: Solve WITH symbolic_solver_labels=True ===")
pyomo_model2 = model_obj.build_model()  # Rebuild fresh
solver2 = SolverFactory('cbc')
results2 = solver2.solve(pyomo_model2, tee=False, symbolic_solver_labels=True, load_solutions=False)

print(f"Solver status: {results2.solver.status}")
print(f"Termination: {results2.solver.termination_condition}")
print(f"Solutions in results: {len(results2.solution) if hasattr(results2, 'solution') else 'N/A'}")

# Try to load solutions
try:
    pyomo_model2.solutions.load_from(results2)
    print("Solutions loaded successfully")

    # Check variable values
    sample_var2 = pyomo_model2.production[date(2025, 1, 13), "PROD_A"]
    print(f"Sample variable value: production[2025-01-13, 'PROD_A'] = {sample_var2.value}")
except Exception as e:
    print(f"ERROR loading solutions: {e}")

# Test 3: Load solutions automatically
print(f"\n=== Test 3: Solve WITH load_solutions=True ===")
pyomo_model3 = model_obj.build_model()  # Rebuild fresh
solver3 = SolverFactory('cbc')
results3 = solver3.solve(pyomo_model3, tee=False, load_solutions=True)

print(f"Solver status: {results3.solver.status}")
print(f"Termination: {results3.solver.termination_condition}")

# Check variable values
sample_var3 = pyomo_model3.production[date(2025, 1, 13), "PROD_A"]
print(f"Sample variable value: production[2025-01-13, 'PROD_A'] = {sample_var3.value}")
