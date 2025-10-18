#!/usr/bin/env python3
"""Extract ALL variable values from minimal case solution."""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure
from src.optimization.unified_node_model import UnifiedNodeModel
from pyomo.environ import value

# Build minimal case
day_1 = date(2025, 1, 1)
day_7 = date(2025, 1, 7)

manufacturing = UnifiedNode(
    id='MFG', name='Manufacturing',
    capabilities=NodeCapabilities(
        can_manufacture=True, has_demand=False, can_store=True,
        requires_trucks=False, storage_mode=StorageMode.AMBIENT,
        production_rate_per_hour=1400.0,
    ),
)

breadroom = UnifiedNode(
    id='BR1', name='Breadroom',
    capabilities=NodeCapabilities(
        can_manufacture=False, has_demand=True, can_store=True,
        requires_trucks=False, storage_mode=StorageMode.AMBIENT,
    ),
)

route = UnifiedRoute(
    id='MFG-BR1', origin_node_id='MFG', destination_node_id='BR1',
    transit_days=1.0, cost_per_unit=1.0, transport_mode=TransportMode.AMBIENT,
)

forecast = Forecast(name='Minimal', entries=[
    ForecastEntry(location_id='BR1', product_id='PROD1', forecast_date=day_7, quantity=1000.0)
])

labor_days = [
    LaborDay(date=day_1+timedelta(days=i), is_fixed_day=True, fixed_hours=12.0,
             overtime_hours=2.0, minimum_hours=4.0, regular_rate=25.0,
             overtime_rate=37.5, non_fixed_rate=50.0)
    for i in range(7)
]

model = UnifiedNodeModel(
    nodes=[manufacturing, breadroom], routes=[route],
    forecast=forecast, labor_calendar=LaborCalendar(name='Test', days=labor_days),
    cost_structure=CostStructure(production_cost_per_unit=5.0, shortage_penalty_per_unit=10000.0),
    start_date=day_1, end_date=day_7, truck_schedules=None, initial_inventory=None,
    use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
)

result = model.solve(solver_name='cbc', time_limit_seconds=60, mip_gap=0.01, tee=False)
pyomo_model = model.model

print("="*80)
print("SOLUTION VARIABLE VALUES")
print("="*80)

# Production
print("\nProduction Variables:")
for date_idx in range(7):
    d = day_1 + timedelta(days=date_idx)
    try:
        val = value(pyomo_model.production['MFG', 'PROD1', d])
        if val > 0.01:
            print(f"  {d}: {val:,.0f} units")
    except:
        pass

# Shipments
print("\nShipment Variables (non-zero):")
for (o, d, p, pd, dd, s) in model.shipment_cohort_index_set:
    try:
        val = value(pyomo_model.shipment_cohort[o, d, p, pd, dd, s])
        if val > 0.01:
            print(f"  {o}→{d} prod:{pd} deliver:{dd}: {val:,.0f} units")
    except:
        pass

# Inventory at BR1 on day 7
print("\nBR1 Inventory on Day 7 (before & after demand):")
for (n, p, pd, cd, s) in model.cohort_index_set:
    if n == 'BR1' and cd == day_7:
        try:
            val = value(pyomo_model.inventory_cohort[n, p, pd, cd, s])
            if val > 0.01:
                print(f"  Cohort prod:{pd}: {val:,.0f} units")
        except:
            pass

# demand_from_cohort
print("\nDemand Allocation (demand_from_cohort):")
total_allocated = 0
for (n, p, pd, dd) in model.demand_cohort_index_set:
    if dd == day_7:
        try:
            val = value(pyomo_model.demand_from_cohort[n, p, pd, dd])
            if val > 0.01:
                print(f"  Cohort prod:{pd}: {val:,.0f} units")
                total_allocated += val
        except:
            pass
print(f"  TOTAL: {total_allocated:,.0f} units (should = 1000)")

# Inventory at MFG on day 7
print("\nMFG Inventory on Day 7:")
for (n, p, pd, cd, s) in model.cohort_index_set:
    if n == 'MFG' and cd == day_7:
        try:
            val = value(pyomo_model.inventory_cohort[n, p, pd, cd, s])
            if val > 0.01:
                print(f"  Cohort prod:{pd}: {val:,.0f} units (WASTE)")
        except:
            pass

print("\n" + "="*80)
print("This shows EXACTLY where the excess 1000 units are located")
print("="*80)
