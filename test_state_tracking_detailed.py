"""Detailed test of state tracking with explicit checks."""

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
    storage_mode=StorageMode.FROZEN  # FROZEN ONLY
)

wa_breadroom = Location(
    id="6130",
    name="WA Breadroom",
    type=LocationType.BREADROOM,
    storage_mode=StorageMode.BOTH  # Can receive frozen, stores ambient
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

# Forecast - demand at both Lineage and WA to test state tracking
forecast = Forecast(
    name="Test Forecast",
    entries=[
        ForecastEntry(
            location_id="Lineage",
            product_id="PROD1",
            forecast_date=start_date + timedelta(days=5),
            quantity=500.0
        ),
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
print("DETAILED STATE TRACKING TEST")
print("=" * 70)

print("\nCreating model with state tracking...")
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

print("\n" + "=" * 70)
print("MODEL DATA EXTRACTION")
print("=" * 70)

print(f"\nDestinations: {model.destinations}")
print(f"Intermediate storage: {model.intermediate_storage}")
print(f"Inventory locations: {model.inventory_locations}")
print(f"\nLocations with FROZEN storage: {model.locations_frozen_storage}")
print(f"Locations with AMBIENT storage: {model.locations_ambient_storage}")

print(f"\n" + "-" * 70)
print("ROUTE ENUMERATION")
print("-" * 70)
print(f"Number of enumerated routes: {len(model.enumerated_routes)}")

for route in model.enumerated_routes:
    arrival_state = model.route_arrival_state.get(route.index, 'unknown')
    is_frozen = model._is_frozen_route(route)
    dest_loc = model.location_by_id.get(route.destination_id)
    dest_mode = dest_loc.storage_mode if dest_loc else "unknown"

    print(f"\nRoute {route.index}:")
    print(f"  Path: {' -> '.join(route.path)}")
    print(f"  Destination: {route.destination_id} (storage mode: {dest_mode})")
    print(f"  Is frozen route: {is_frozen}")
    print(f"  Arrival state: {arrival_state}")
    print(f"  Transit days: {route.total_transit_days}")

    # Expected behavior:
    # - Route to Lineage (FROZEN storage only) → should arrive FROZEN
    # - Route to 6130 (BOTH storage) → should arrive AMBIENT (thaws)
    if route.destination_id == "Lineage":
        expected = "frozen"
    else:
        expected = "ambient"

    status = "✓" if arrival_state == expected else "✗"
    print(f"  {status} Expected: {expected}, Got: {arrival_state}")

print(f"\n" + "-" * 70)
print("PYOMO MODEL BUILD")
print("-" * 70)
pyomo_model = model.build_model()
print("Pyomo model built successfully!")

print(f"\n" + "-" * 70)
print("INVENTORY VARIABLES")
print("-" * 70)
print(f"Frozen inventory indices: {len(model.inventory_frozen_index_set)}")
print(f"Ambient inventory indices: {len(model.inventory_ambient_index_set)}")

# Group by location
frozen_by_loc = {}
ambient_by_loc = {}

for (loc, prod, date) in model.inventory_frozen_index_set:
    if loc not in frozen_by_loc:
        frozen_by_loc[loc] = 0
    frozen_by_loc[loc] += 1

for (loc, prod, date) in model.inventory_ambient_index_set:
    if loc not in ambient_by_loc:
        ambient_by_loc[loc] = 0
    ambient_by_loc[loc] += 1

print("\nFrozen inventory variables by location:")
for loc, count in frozen_by_loc.items():
    print(f"  {loc}: {count} variables")

print("\nAmbient inventory variables by location:")
for loc, count in ambient_by_loc.items():
    print(f"  {loc}: {count} variables")

print(f"\n" + "=" * 70)
print("STATE TRACKING IMPLEMENTATION VERIFICATION")
print("=" * 70)

# Verify expected behavior
checks_passed = 0
checks_total = 0

# Check 1: Lineage should have frozen inventory variables (FROZEN only storage)
checks_total += 1
if "Lineage" in frozen_by_loc and frozen_by_loc["Lineage"] > 0:
    print("✓ Check 1 PASSED: Lineage has frozen inventory variables")
    checks_passed += 1
else:
    print("✗ Check 1 FAILED: Lineage should have frozen inventory variables")

# Check 2: Lineage should NOT have ambient inventory variables (FROZEN only)
checks_total += 1
if "Lineage" not in ambient_by_loc or ambient_by_loc.get("Lineage", 0) == 0:
    print("✓ Check 2 PASSED: Lineage has no ambient inventory variables (FROZEN only)")
    checks_passed += 1
else:
    print("✗ Check 2 FAILED: Lineage should not have ambient inventory (FROZEN only storage)")

# Check 3: 6130 should have both frozen and ambient inventory variables (BOTH storage)
checks_total += 1
if "6130" in frozen_by_loc and "6130" in ambient_by_loc:
    print("✓ Check 3 PASSED: 6130 has both frozen and ambient inventory variables")
    checks_passed += 1
else:
    print("✗ Check 3 FAILED: 6130 should have both types (BOTH storage mode)")

# Check 4: Route to Lineage should arrive as frozen
checks_total += 1
lineage_routes = [r for r in model.enumerated_routes if r.destination_id == "Lineage"]
if lineage_routes:
    route_idx = lineage_routes[0].index
    arrival_state = model.route_arrival_state.get(route_idx)
    if arrival_state == "frozen":
        print("✓ Check 4 PASSED: Route to Lineage arrives as frozen")
        checks_passed += 1
    else:
        print(f"✗ Check 4 FAILED: Route to Lineage should arrive frozen, got {arrival_state}")
else:
    print("⚠ Check 4 SKIPPED: No routes to Lineage found")

# Check 5: Route to 6130 should arrive as ambient (thaws from frozen)
checks_total += 1
wa_routes = [r for r in model.enumerated_routes if r.destination_id == "6130"]
if wa_routes:
    route_idx = wa_routes[0].index
    arrival_state = model.route_arrival_state.get(route_idx)
    if arrival_state == "ambient":
        print("✓ Check 5 PASSED: Route to 6130 arrives as ambient (thaws)")
        checks_passed += 1
    else:
        print(f"✗ Check 5 FAILED: Route to 6130 should arrive ambient, got {arrival_state}")
else:
    print("⚠ Check 5 SKIPPED: No routes to 6130 found")

print(f"\n" + "=" * 70)
print(f"RESULTS: {checks_passed}/{checks_total} checks passed")
print("=" * 70)

if checks_passed == checks_total:
    print("\n✓ STATE TRACKING IMPLEMENTATION SUCCESSFUL!")
else:
    print(f"\n✗ {checks_total - checks_passed} check(s) failed")
