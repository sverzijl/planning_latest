"""
Test the minimal case WITHOUT batch tracking to see if bug disappears.
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

print("=" * 80)
print("TEST WITHOUT BATCH TRACKING")
print("=" * 80)
print()

# Create model WITHOUT batch tracking
model = UnifiedNodeModel(
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
    use_batch_tracking=False,  # KEY DIFFERENCE
)

# Solve
result = model.solve(solver_name='cbc', time_limit_seconds=120, mip_gap=0.01)

print(f"Status: {result.termination_condition}")
print(f"Solve time: {result.solve_time_seconds:.2f}s")
print(f"Total cost: ${result.objective_value:,.2f}")
print()

# Get solution
solution = model.get_solution()

print("RESULTS:")
print(f"  Production: {sum(solution.get('production_by_date_product', {}).values()):,.0f} units")
print(f"  Demand: 1,000 units")
print()

print("Production by date:")
for (prod_date, product), qty in sorted(solution.get('production_by_date_product', {}).items()):
    if qty > 0.01:
        print(f"  {prod_date}: {qty:,.0f} units")
print()

# Check if bug exists
total_prod = sum(solution.get('production_by_date_product', {}).values())
if total_prod > 1100:
    print("❌ BUG STILL EXISTS without batch tracking!")
    print(f"   Produced {total_prod:,.0f} instead of ~1,000")
else:
    print("✓✓✓ BUG FIXED without batch tracking!")
    print(f"   Production matches demand: {total_prod:,.0f} units")
    print()
    print("   ROOT CAUSE: The bug is related to BATCH TRACKING!")
