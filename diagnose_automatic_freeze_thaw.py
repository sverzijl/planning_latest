"""Diagnose if freeze/thaw operations are automatic or optional.

Business Logic (from user):
- Freezing at Lineage is AUTOMATIC (not optional) when ambient stock arrives
- Thawing at 6130 is AUTOMATIC (not optional) when frozen stock arrives
- General rule: Storage mode mismatch triggers automatic state transition

Current Model Behavior:
- model.freeze and model.thaw are decision variables (NonNegativeReals)
- Model can CHOOSE to freeze/thaw or not
- This is WRONG - should be FORCED based on arrivals

This script checks:
1. Are freeze/thaw operations linked to shipment arrivals?
2. Is there a constraint forcing freeze when ambient arrives at frozen storage?
3. Is there a constraint forcing thaw when frozen arrives at ambient storage?
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

print("="*80)
print("AUTOMATIC FREEZE/THAW DIAGNOSTIC")
print("="*80)
print()

# Check Lineage configuration
lineage_loc = [loc for loc in locations if loc.id == 'Lineage'][0]
wa_loc = [loc for loc in locations if loc.id == '6130'][0]

print(f"Lineage configuration:")
print(f"  storage_mode: {lineage_loc.storage_mode}")
print(f"  Receives: Ambient shipments from 6122")
print(f"  Should: AUTOMATICALLY freeze all arriving ambient stock")
print()

print(f"6130 (WA) configuration:")
print(f"  storage_mode: {wa_loc.storage_mode}")
print(f"  Receives: Frozen shipments from Lineage")
print(f"  Should: AUTOMATICALLY thaw all arriving frozen stock")
print()

# Check routes
route_to_lineage = [r for r in routes if r.destination_id == 'Lineage']
route_from_lineage = [r for r in routes if r.origin_id == 'Lineage']

print("Routes:")
if route_to_lineage:
    for r in route_to_lineage:
        print(f"  {r.id}: {r.origin_id} → Lineage, mode={r.transport_mode}")
if route_from_lineage:
    for r in route_from_lineage:
        print(f"  {r.id}: Lineage → {r.destination_id}, mode={r.transport_mode}")

print()

# Create simple test scenario
start_date = date(2025, 10, 13)
end_date = start_date + timedelta(days=6)

# Demand at WA (forces Lineage route)
forecast_entries = []
for day_offset in range(5, 7):  # Days 5-6 (allows 4-day transit)
    forecast_entries.append(
        ForecastEntry(
            location_id="6130",
            product_id="TEST",
            forecast_date=start_date + timedelta(days=day_offset),
            quantity=100.0,
        )
    )

forecast = Forecast(name="Lineage Auto Test", entries=forecast_entries)

model = IntegratedProductionDistributionModel(
    forecast=forecast, labor_calendar=labor, manufacturing_site=manufacturing_site,
    cost_structure=costs, locations=locations, routes=routes,
    truck_schedules=trucks, start_date=start_date, end_date=end_date,
    use_batch_tracking=True, initial_inventory=None,
)

# Check leg states
print("Leg state analysis:")
print("="*80)

leg_to_lineage = [leg for leg in model.leg_keys if leg[1] == 'Lineage']
leg_from_lineage = [leg for leg in model.leg_keys if leg[0] == 'Lineage']

print(f"\\nLegs TO Lineage:")
for leg in leg_to_lineage:
    transport = model.leg_transport_mode.get(leg)
    arrival_state = model.leg_arrival_state.get(leg)
    print(f"  {leg}: transport={transport}, arrival_state={arrival_state}")

    # Check storage mode mismatch
    if arrival_state == 'ambient' and lineage_loc.storage_mode == 'frozen':
        print(f"    ⚠️ MISMATCH: Ambient arrives at frozen storage")
        print(f"       Should trigger: AUTOMATIC FREEZE")
    elif arrival_state == 'frozen' and lineage_loc.storage_mode == 'frozen':
        print(f"    ✓ Match: Frozen arrives at frozen storage (no state change needed)")

print(f"\\nLegs FROM Lineage:")
for leg in leg_from_lineage:
    transport = model.leg_transport_mode.get(leg)
    arrival_state = model.leg_arrival_state.get(leg)
    dest_id = leg[1]
    dest_loc = model.location_by_id.get(dest_id)

    print(f"  {leg}: transport={transport}, arrival_state={arrival_state}")

    if dest_loc:
        if arrival_state == 'frozen' and dest_loc.storage_mode == 'ambient':
            print(f"    ⚠️ MISMATCH: Frozen arrives at ambient storage ({dest_id})")
            print(f"       Should trigger: AUTOMATIC THAW")
        elif arrival_state == 'ambient' and dest_loc.storage_mode == 'ambient':
            print(f"    ✓ Match: Ambient arrives at ambient storage")

print()
print("="*80)
print("CHECKING IF FREEZE/THAW ARE FORCED")
print("="*80)

# Build model
pyomo_model = model.build_model()

print(f"\\nmodel.freeze variables: {len(pyomo_model.freeze) if hasattr(pyomo_model, 'freeze') else 0}")
print(f"model.thaw variables: {len(pyomo_model.thaw) if hasattr(pyomo_model, 'thaw') else 0}")

# Check if there are constraints forcing freeze/thaw
if hasattr(pyomo_model, 'component_map'):
    constraint_names = [name for name in pyomo_model.component_map()]
    freeze_constraints = [name for name in constraint_names if 'freeze' in name.lower() and 'force' in name.lower()]
    thaw_constraints = [name for name in constraint_names if 'thaw' in name.lower() and 'force' in name.lower()]

    print(f"\\nConstraints forcing freeze: {len(freeze_constraints)}")
    for name in freeze_constraints:
        print(f"  - {name}")

    print(f"Constraints forcing thaw: {len(thaw_constraints)}")
    for name in thaw_constraints:
        print(f"  - {name}")

    if not freeze_constraints and not thaw_constraints:
        print(f"\\n❌ NO CONSTRAINTS forcing automatic freeze/thaw!")
        print(f"   Freeze/thaw are OPTIONAL decision variables")
        print(f"   Should be: FORCED based on arrival_state vs storage_mode mismatch")

print()
print("="*80)
print("EXPECTED BEHAVIOR")
print("="*80)
print()
print("For Lineage route (6122 → Lineage → 6130):")
print("  1. Ambient ships from 6122 → arrives at Lineage (frozen storage)")
print("     → AUTOMATIC FREEZE: ambient_arrival[t] = freeze[t]")
print()
print("  2. Frozen ships from Lineage → arrives at 6130 (ambient storage)")
print("     → AUTOMATIC THAW: frozen_arrival[t] = thaw[t]")
print()
print("Missing constraints:")
print("  - freeze[Lineage, prod, pd, t] == ambient_arrivals[Lineage, prod, pd, t]")
print("  - thaw[6130, prod, pd, t] == frozen_arrivals[6130, prod, pd, t]")
