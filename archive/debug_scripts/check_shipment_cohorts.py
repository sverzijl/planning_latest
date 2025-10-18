"""
Check what shipment cohort indices exist.
"""

from datetime import date, timedelta
from src.optimization.unified_node_model import UnifiedNodeModel
from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure

# Setup minimal case
day_1 = date(2025, 1, 1)
day_7 = date(2025, 1, 7)

manufacturing = UnifiedNode(
    id='MFG',
    name='Manufacturing Site',
    capabilities=NodeCapabilities(
        can_manufacture=True,
        has_demand=False,
        can_store=True,
        requires_trucks=False,
        storage_mode=StorageMode.AMBIENT,
        production_rate_per_hour=1400.0,
    ),
)

breadroom = UnifiedNode(
    id='BR1',
    name='Breadroom 1',
    capabilities=NodeCapabilities(
        can_manufacture=False,
        has_demand=True,
        can_store=True,
        requires_trucks=False,
        storage_mode=StorageMode.AMBIENT,
        production_rate_per_hour=None,
    ),
)

route = UnifiedRoute(
    id='MFG-BR1',
    origin_node_id='MFG',
    destination_node_id='BR1',
    transit_days=1.0,
    cost_per_unit=1.0,
    transport_mode=TransportMode.AMBIENT,
)

forecast = Forecast(
    name='Minimal Test',
    entries=[
        ForecastEntry(
            location_id='BR1',
            product_id='PROD1',
            forecast_date=day_7,
            quantity=1000.0
        )
    ]
)

labor_days = []
for day_offset in range(7):
    curr_date = day_1 + timedelta(days=day_offset)
    labor_days.append(LaborDay(
        date=curr_date,
        is_fixed_day=True,
        fixed_hours=12.0,
        overtime_hours=2.0,
        minimum_hours=4.0,
        regular_rate=25.0,
        overtime_rate=37.50,
        non_fixed_rate=50.0,
    ))

labor_calendar = LaborCalendar(name='Test Calendar', days=labor_days)

cost_structure = CostStructure(
    production_cost_per_unit=5.0,
    shortage_penalty_per_unit=10000.0,
)

# Create model (but don't solve yet)
unified_model = UnifiedNodeModel(
    nodes=[manufacturing, breadroom],
    routes=[route],
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    start_date=day_1,
    end_date=day_7,
    truck_schedules=None,
    initial_inventory=None,
    allow_shortages=True,
    enforce_shelf_life=True,
    use_batch_tracking=True,
)

# Build the model (this creates the index sets)
pyomo_model = unified_model.build_model()

print()
print("=" * 80)
print("SHIPMENT COHORT INDEX ANALYSIS")
print("=" * 80)
print(f"Total shipment cohorts: {len(unified_model.shipment_cohort_index_set)}")
print()

# Filter for MFG → BR1, PROD1
mfg_br1_cohorts = [
    (origin, dest, prod, prod_date, delivery_date, state)
    for (origin, dest, prod, prod_date, delivery_date, state) in unified_model.shipment_cohort_index_set
    if origin == 'MFG' and dest == 'BR1' and prod == 'PROD1'
]

print(f"MFG → BR1, PROD1 shipment cohorts: {len(mfg_br1_cohorts)}")
print()

# Group by delivery date
by_delivery_date = {}
for (origin, dest, prod, prod_date, delivery_date, state) in mfg_br1_cohorts:
    if delivery_date not in by_delivery_date:
        by_delivery_date[delivery_date] = []
    by_delivery_date[delivery_date].append((prod_date, state))

print("Shipment cohorts by delivery date:")
for delivery_date in sorted(by_delivery_date.keys()):
    departure_date = delivery_date - timedelta(days=route.transit_days)
    print(f"\n  Delivery {delivery_date} (depart {departure_date}):")
    for (prod_date, state) in sorted(by_delivery_date[delivery_date]):
        print(f"    - From production date {prod_date}, state={state}")

print()
print("=" * 80)
print("CRITICAL CHECK:")
print("=" * 80)

# Check if the optimal shipment exists
optimal_shipment = ('MFG', 'BR1', 'PROD1', date(2025, 1, 6), date(2025, 1, 7), 'ambient')

if optimal_shipment in unified_model.shipment_cohort_index_set:
    print("✓ OPTIMAL SHIPMENT EXISTS:")
    print(f"  {optimal_shipment}")
    print(f"  Produce day 6, ship day 6, arrive day 7")
    print(f"  This should satisfy demand with 0 waste!")
else:
    print("❌ OPTIMAL SHIPMENT MISSING:")
    print(f"  Looking for: {optimal_shipment}")
    print(f"  This shipment cohort was NOT created!")
    print(f"  BUG: Index building logic excluded the optimal solution!")

print()

# Check what constraints the departure date
print("Departure date analysis:")
for day_offset in range(7):
    curr_date = day_1 + timedelta(days=day_offset)
    departure_date = curr_date
    delivery_date = departure_date + timedelta(days=route.transit_days)

    # Check if this departure date is within planning horizon
    if departure_date < unified_model.start_date or departure_date > unified_model.end_date:
        status = "EXCLUDED (departure outside horizon)"
    else:
        status = "INCLUDED"

    print(f"  Depart {departure_date} → Arrive {delivery_date}: {status}")
