"""Test that state tracking implementation works correctly."""

from datetime import date, timedelta
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route
from src.optimization.integrated_model import IntegratedProductionDistributionModel

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
    storage_mode=StorageMode.FROZEN
)

wa_breadroom = Location(
    id="6130",
    name="WA Breadroom",
    type=LocationType.BREADROOM,
    storage_mode=StorageMode.BOTH  # Can receive frozen, stores ambient
)

locations = [manufacturing, lineage, wa_breadroom]

# Routes
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

print("Creating model with state tracking...")
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=manufacturing_site,
    cost_structure=cost_structure,
    locations=locations,
    routes=routes,
    allow_shortages=False,
    enforce_shelf_life=False,  # Disable to test frozen routes
    validate_feasibility=False  # Skip validation for this test
)

print("Model created successfully!")
print(f"  Destinations: {model.destinations}")
print(f"  Intermediate storage: {model.intermediate_storage}")
print(f"  Inventory locations: {model.inventory_locations}")
print(f"  Locations with frozen storage: {model.locations_frozen_storage}")
print(f"  Locations with ambient storage: {model.locations_ambient_storage}")
print(f"  Number of enumerated routes: {len(model.enumerated_routes)}")

# Check route arrival states
print("\nRoute arrival states:")
for route in model.enumerated_routes:
    arrival_state = model.route_arrival_state.get(route.index, 'unknown')
    print(f"  Route {route.index}: {route.origin_id} -> {route.destination_id} -> arrives as {arrival_state}")

print("\nBuilding Pyomo model...")
pyomo_model = model.build_model()
print("Pyomo model built successfully!")

# Verify state-specific inventory variables exist
print(f"\nInventory variable verification:")
print(f"  inventory_frozen indices: {len(pyomo_model.inventory_frozen_index)}")
print(f"  inventory_ambient indices: {len(pyomo_model.inventory_ambient_index)}")

# Show sample indices
if pyomo_model.inventory_frozen_index:
    print(f"  Sample frozen inventory index: {pyomo_model.inventory_frozen_index[0]}")
if pyomo_model.inventory_ambient_index:
    print(f"  Sample ambient inventory index: {pyomo_model.inventory_ambient_index[0]}")

print("\nState tracking implementation successful!")
