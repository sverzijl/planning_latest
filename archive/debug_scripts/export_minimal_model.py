#!/usr/bin/env python3
"""Export minimal model to .lp file for manual inspection."""

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

# Create minimal case (same as test)
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
    transit_days=1.0, cost_per_unit=1.0,
    transport_mode=TransportMode.AMBIENT,
)

forecast = Forecast(name='Minimal', entries=[
    ForecastEntry(location_id='BR1', product_id='PROD1', forecast_date=day_7, quantity=1000.0)
])

labor_days = [
    LaborDay(
        date=day_1 + timedelta(days=i),
        is_fixed_day=True,
        fixed_hours=12.0,
        overtime_hours=2.0,
        minimum_hours=4.0,
        regular_rate=25.0,
        overtime_rate=37.5,
        non_fixed_rate=50.0,
    )
    for i in range(7)
]
labor_calendar = LaborCalendar(name='Test', days=labor_days)

cost_structure = CostStructure(
    production_cost_per_unit=5.0,
    shortage_penalty_per_unit=10000.0,
)

print("Building minimal model...")
model = UnifiedNodeModel(
    nodes=[manufacturing, breadroom], routes=[route],
    forecast=forecast, labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    start_date=day_1, end_date=day_7,
    truck_schedules=None, initial_inventory=None,
    use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
)

# Build but don't solve
pyomo_model = model.build_model()

print("Exporting to .lp file...")
pyomo_model.write('minimal_model.lp', io_options={'symbolic_solver_labels': True})

print("\n✓ Model exported to minimal_model.lp")
print("\nYou can now review:")
print("  1. Variables section - see production[], inventory_cohort[], demand_from_cohort[]")
print("  2. Constraints section - see which constraints involve these variables")
print("  3. Objective - verify production cost is applied")
print("\nLook for:")
print("  - Constraints forcing production[MFG,PROD1,2025-01-05] ≥ some_value")
print("  - Coupling between production and other variables")
print("  - Any constraint that would force production = 2×demand")
print("\n" + "="*80)
