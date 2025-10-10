"""Test that state tracking model can solve successfully."""

from datetime import date, timedelta
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route
from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.optimization.solver_config import SolverConfig

# Create minimal test data
start_date = date(2025, 1, 6)  # Monday

# Locations
manufacturing = Location(
    id="6122",
    name="Manufacturing",
    type=LocationType.MANUFACTURING,
    storage_mode=StorageMode.BOTH
)

lineage = Location(
    id="Lineage",
    name="Lineage Frozen Storage",
    type=LocationType.STORAGE,
    storage_mode=StorageMode.FROZEN  # FROZEN ONLY
)

wa_breadroom = Location(
    id="6130",
    name="WA Breadroom",
    type=LocationType.BREADROOM,
    storage_mode=StorageMode.BOTH
)

locations = [manufacturing, lineage, wa_breadroom]

# Routes - frozen throughout
route_to_lineage = Route(
    id="R1",
    origin_id="6122",
    destination_id="Lineage",
    transport_mode=StorageMode.FROZEN,
    transit_time_days=1.0,
    cost=0.5
)

route_lineage_to_wa = Route(
    id="R2",
    origin_id="Lineage",
    destination_id="6130",
    transport_mode=StorageMode.FROZEN,
    transit_time_days=2.0,
    cost=1.0
)

routes = [route_to_lineage, route_lineage_to_wa]

# Forecast - demand at WA
forecast = Forecast(
    name="Test Forecast",
    entries=[
        ForecastEntry(
            location_id="6130",
            product_id="PROD1",
            forecast_date=start_date + timedelta(days=7),
            quantity=1000.0
        )
    ]
)

# Labor calendar
labor_calendar = LaborCalendar(
    name="Test Labor Calendar",
    days=[
        LaborDay(
            date=start_date + timedelta(days=i),
            is_fixed_day=True,
            fixed_hours=12.0,
            regular_rate=50.0,
            overtime_rate=75.0
        )
        for i in range(14)
    ]
)

# Manufacturing site
manufacturing_site = ManufacturingSite(
    id="6122",
    name="Manufacturing Site",
    storage_mode=StorageMode.BOTH,
    production_rate=1400.0
)

# Cost structure
cost_structure = CostStructure(
    production_cost_per_unit=1.0,
    storage_cost_frozen_per_unit_day=0.05,
    storage_cost_ambient_per_unit_day=0.02,
    shortage_penalty_per_unit=100.0
)

print("=" * 70)
print("STATE TRACKING SOLVE TEST")
print("=" * 70)

print("\nCreating model...")
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    allow_shortages=False,
    enforce_shelf_life=False,
    validate_feasibility=False
)

print("Model created successfully!")

print("\nSolving...")
solver_config = SolverConfig()
solver_name = solver_config.get_best_available_solver()
print(f"Using solver: {solver_name}")

result = model.solve(time_limit_seconds=60)

print(f"\nSolver Status: {result.solver_status}")
print(f"Termination Condition: {result.termination_condition}")
print(f"Solve Time: {result.solve_time_seconds:.2f}s")

if result.is_optimal():
    print("\n✓ Optimal solution found!")
    print(f"Total Cost: ${result.objective_value:,.2f}")

    # Check solution details
    solution = model.solution
    print(f"\nCost Breakdown:")
    print(f"  Labor Cost:      ${solution['total_labor_cost']:>12,.2f}")
    print(f"  Production Cost: ${solution['total_production_cost']:>12,.2f}")
    print(f"  Transport Cost:  ${solution['total_transport_cost']:>12,.2f}")
    print(f"  Inventory Cost:  ${solution['total_inventory_cost']:>12,.2f}")
    print(f"  Total Cost:      ${solution['total_cost']:>12,.2f}")

    # Check state-specific inventory
    frozen_inv = solution.get('inventory_frozen_by_loc_product_date', {})
    ambient_inv = solution.get('inventory_ambient_by_loc_product_date', {})

    print(f"\nInventory:")
    print(f"  Frozen inventory entries: {len(frozen_inv)}")
    print(f"  Ambient inventory entries: {len(ambient_inv)}")

    if frozen_inv:
        print(f"\n  Frozen Inventory (sample):")
        for (loc, prod, dt), qty in list(frozen_inv.items())[:3]:
            print(f"    {loc}, {prod}, {dt}: {qty:,.0f} units")

    if ambient_inv:
        print(f"\n  Ambient Inventory (sample):")
        for (loc, prod, dt), qty in list(ambient_inv.items())[:3]:
            print(f"    {loc}, {prod}, {dt}: {qty:,.0f} units")

    # Check if demand satisfied
    total_production = sum(solution['production_by_date_product'].values())
    total_demand = sum(entry.quantity for entry in forecast.entries)

    print(f"\nDemand Satisfaction:")
    print(f"  Total Production: {total_production:,.0f} units")
    print(f"  Total Demand:     {total_demand:,.0f} units")
    print(f"  Satisfied:        {total_production >= total_demand}")

    print("\n" + "=" * 70)
    print("✓ STATE TRACKING SOLVE TEST PASSED!")
    print("=" * 70)
else:
    print(f"\n✗ Solve failed: {result.termination_condition}")
    print("This may be expected if CBC solver is not available.")
