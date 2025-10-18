"""
Analyze cohort reachability to find batch management bugs.
Check if shipment cohorts are created for unreachable scenarios.
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
    id='MFG', name='Manufacturing Site',
    capabilities=NodeCapabilities(
        can_manufacture=True, has_demand=False, can_store=True,
        requires_trucks=False, storage_mode=StorageMode.AMBIENT,
        production_rate_per_hour=1400.0,
    ),
)

breadroom = UnifiedNode(
    id='BR1', name='Breadroom 1',
    capabilities=NodeCapabilities(
        can_manufacture=False, has_demand=True, can_store=True,
        requires_trucks=False, storage_mode=StorageMode.AMBIENT,
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

# Create model
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

# Build model
pyomo_model = unified_model.build_model()

print()
print("=" * 80)
print("COHORT REACHABILITY ANALYSIS")
print("=" * 80)
print()

# Check inventory cohorts at MFG
print("INVENTORY COHORTS AT MFG:")
mfg_cohorts = [(n, p, pd, cd, s) for (n, p, pd, cd, s) in unified_model.cohort_index_set
               if n == 'MFG']

# Group by production date and current date
for prod_date in sorted(set(pd for (n, p, pd, cd, s) in mfg_cohorts)):
    cohorts_for_prod = [(cd, s) for (n, p, pd, cd, s) in mfg_cohorts if pd == prod_date]
    print(f"  Production {prod_date}:")
    for curr_date, state in sorted(cohorts_for_prod):
        print(f"    - Can exist at MFG on {curr_date} (state={state})")
print()

# Check shipment cohorts FROM MFG
print("SHIPMENT COHORTS FROM MFG:")
mfg_shipments = [(o, d, p, pd, dd, s) for (o, d, p, pd, dd, s) in unified_model.shipment_cohort_index_set
                 if o == 'MFG']

# Group by production date
for prod_date in sorted(set(pd for (o, d, p, pd, dd, s) in mfg_shipments)):
    shipments_for_prod = [(dd, s) for (o, d, p, pd, dd, s) in mfg_shipments if pd == prod_date]
    departure_dates = [dd - timedelta(days=1) for (dd, s) in shipments_for_prod]

    print(f"  Production {prod_date}:")
    for (delivery_date, state), departure_date in zip(sorted(shipments_for_prod), sorted(departure_dates)):
        # Check if this cohort can exist at MFG on departure date
        can_exist = (('MFG', 'PROD1', prod_date, departure_date, 'ambient') in unified_model.cohort_index_set)

        reachability = "✓ REACHABLE" if can_exist else "❌ UNREACHABLE"
        print(f"    - Ship departing {departure_date} → arriving {delivery_date}: {reachability}")

print()

# CRITICAL CHECK: For day-5 production shipped on day-6
print("=" * 80)
print("CRITICAL REACHABILITY CHECK:")
print("=" * 80)

test_cases = [
    (('MFG', 'PROD1', date(2025, 1, 5), date(2025, 1, 5), 'ambient'),
     "Day-5 cohort at MFG on day 5 (just produced)"),
    (('MFG', 'PROD1', date(2025, 1, 5), date(2025, 1, 6), 'ambient'),
     "Day-5 cohort at MFG on day 6 (held for 1 day)"),
    (('MFG', 'BR1', 'PROD1', date(2025, 1, 5), date(2025, 1, 7), 'ambient'),
     "Shipment: day-5 cohort departs day 6, arrives day 7"),
]

for cohort_key, description in test_cases:
    if len(cohort_key) == 5:  # Inventory cohort
        exists = cohort_key in unified_model.cohort_index_set
    else:  # Shipment cohort
        exists = cohort_key in unified_model.shipment_cohort_index_set

    status = "✓ EXISTS" if exists else "❌ MISSING"
    print(f"{description}:")
    print(f"  {cohort_key}")
    print(f"  {status}")
    print()

print("=" * 80)
print("POTENTIAL BUG:")
print("=" * 80)

# Check if day-5 cohort can persist at MFG to day 6
day5_mfg_day6 = ('MFG', 'PROD1', date(2025, 1, 5), date(2025, 1, 6), 'ambient')
day5_ship_day7 = ('MFG', 'BR1', 'PROD1', date(2025, 1, 5), date(2025, 1, 7), 'ambient')

if day5_mfg_day6 in unified_model.cohort_index_set and day5_ship_day7 in unified_model.shipment_cohort_index_set:
    print("The model allows:")
    print("  1. Day-5 cohort to persist at MFG until day 6")
    print("  2. Day-5 cohort to ship on day 6 (arriving day 7)")
    print()
    print("This means the solver can:")
    print("  - Produce on day 5")
    print("  - Hold at MFG for 1 day (incurring no cost!)")
    print("  - Ship on day 6, arriving day 7")
    print()
    print("BUT ALSO:")
    print("  - Produce on day 5")
    print("  - Ship immediately on day 5, arriving day 6")
    print("  - Hold at BR1 for 1 day (incurring no cost!)")
    print()
    print("⚠️  Both paths have same cost, solver picks arbitrarily!")
    print("   The bug is: NO HOLDING COST to incentivize minimal inventory!")
else:
    print("Cohort configuration doesn't allow both paths.")
