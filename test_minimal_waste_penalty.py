"""Minimal test case - Can I predict the outcome?

Simplest possible scenario:
- 1 location (manufacturing)
- 1 product
- 2 days planning horizon
- Day 0: Demand = 1000 units
- Day 1: Demand = 0 units (last day)

Expected with waste penalty:
- Produce 1000 on day 0
- Consume 1000 on day 0
- End inventory day 1: 0 units

If this doesn't work, I've found the fundamental bug.
"""

from src.models.location import Location
from src.models.unified_node import UnifiedNode
from src.models.unified_route import UnifiedRoute
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure
from src.models.product import Product
from src.optimization.sliding_window_model import SlidingWindowModel
from datetime import date, timedelta

print("="*80)
print("MINIMAL TEST - Can waste penalty drive inventory to zero?")
print("="*80)

# Create minimal data
start_date = date(2025, 11, 1)
end_date = start_date + timedelta(days=1)  # 2 days total

# Single location (manufacturing with demand capability)
from src.models.unified_node import NodeCapabilities, StorageMode

mfg_node = UnifiedNode(
    id='MFG',
    name='Manufacturing',
    capabilities=NodeCapabilities(
        can_manufacture=True,
        has_demand=True,  # Can consume its own production
        can_store=True,
        requires_trucks=False,
        production_rate_per_hour=1400.0,
        storage_capacity=50000.0,
        storage_mode=StorageMode.AMBIENT
    )
)

# Single product
product = Product(id='PROD_A', name='Product A', units_per_mix=100)
products = {'PROD_A': product}

# Demand: 1000 on day 0, 0 on day 1
forecast = Forecast(name='Minimal', entries=[
    ForecastEntry(
        location_id='MFG',
        product_id='PROD_A',
        forecast_date=start_date,
        quantity=1000.0
    )
])

# Labor calendar (simple)
labor_cal = LaborCalendar(days=[
    LaborDay(date=start_date, fixed_hours=12, regular_rate=20, overtime_rate=30, non_fixed_rate=40),
    LaborDay(date=end_date, fixed_hours=12, regular_rate=20, overtime_rate=30, non_fixed_rate=40),
])

# Cost structure with STRONG waste penalty
costs = CostStructure(
    production_cost_per_unit=1.0,
    shortage_penalty_per_unit=10.0,
    waste_cost_multiplier=20.0,  # Very strong: $20/unit waste penalty!
    storage_cost_ambient_per_unit_day=0.0,
    storage_cost_frozen_per_unit_day=0.0
)

# No routes (single location)
routes = []

# No initial inventory
initial_inventory = None

print(f"\nScenario:")
print(f"  Location: MFG (manufacturing + demand)")
print(f"  Product: PROD_A")
print(f"  Horizon: {start_date} to {end_date} (2 days)")
print(f"  Demand day 0: 1,000 units")
print(f"  Demand day 1: 0 units")
print(f"  Waste penalty: $20/unit (2× shortage!)")

print(f"\nExpected Optimal Solution:")
print(f"  Day 0: Produce 1,000, consume 1,000, inventory = 0")
print(f"  Day 1: Produce 0, consume 0, inventory = 0")
print(f"  Total cost: 0 (no shortage, no waste)")

print(f"\nBuilding model...")

model = SlidingWindowModel(
    nodes=[mfg_node],
    routes=routes,
    forecast=forecast,
    products=products,
    labor_calendar=labor_cal,
    cost_structure=costs,
    start_date=start_date,
    end_date=end_date,
    truck_schedules=[],
    initial_inventory=initial_inventory,
    inventory_snapshot_date=start_date,
    allow_shortages=True,
    use_pallet_tracking=False,
    use_truck_pallet_tracking=False
)

print(f"\nSolving...")
result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, tee=False)

print(f"\nResult: {result.termination_condition}")

if result.is_optimal() or result.is_feasible():
    solution = model.get_solution()

    # Check production
    prod_day0 = sum(qty for (n, p, d), qty in solution.production_by_date_product.items() if d == start_date)
    prod_day1 = sum(qty for (n, p, d), qty in solution.production_by_date_product.items() if d == end_date)

    # Check inventory
    inv_day0 = sum(qty for (n, p, s, d), qty in solution.inventory_state.items() if d == start_date)
    inv_day1 = sum(qty for (n, p, s, d), qty in solution.inventory_state.items() if d == end_date)

    # Check consumption
    consumed_day0 = sum(qty for (n, p, d), qty in solution.demand_consumed.items() if d == start_date)
    consumed_day1 = sum(qty for (n, p, d), qty in solution.demand_consumed.items() if d == end_date)

    print(f"\nACTUAL Solution:")
    print(f"  Day 0: Produce {prod_day0:.0f}, consume {consumed_day0:.0f}, inventory = {inv_day0:.0f}")
    print(f"  Day 1: Produce {prod_day1:.0f}, consume {consumed_day1:.0f}, inventory = {inv_day1:.0f}")

    print(f"\nComparison:")
    print(f"  Expected day 1 inventory: 0")
    print(f"  Actual day 1 inventory: {inv_day1:.0f}")

    if inv_day1 < 1:
        print(f"\n  ✅ SUCCESS: Waste penalty works in minimal case!")
        print(f"     Now add complexity step by step")
    else:
        print(f"\n  ❌ BUG IN MINIMAL CASE: {inv_day1:.0f} units waste!")
        print(f"     Waste penalty not working even in simplest scenario")
        print(f"     This is the FUNDAMENTAL BUG")

        # Diagnostic
        print(f"\n  Diagnostics:")
        print(f"    Total cost: ${solution.total_cost:.2f}")
        print(f"    Waste cost: ${solution.costs.waste.expiration_waste:.2f}")
        print(f"    Expected waste: ${inv_day1 * 20:.2f}")

else:
    print(f"\n  Model infeasible - even minimal case fails")
