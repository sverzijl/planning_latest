"""
Force the optimal solution and see if it's feasible.
"""

from datetime import date, timedelta
from src.optimization.unified_node_model import UnifiedNodeModel
from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure
from pyomo.environ import value

# Setup minimal case
day_1 = date(2025, 1, 1)
day_6 = date(2025, 1, 6)
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

# Create and build model
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

pyomo_model = unified_model.build_model()

# Fix production on day 6 to 1000
pyomo_model.production['MFG', 'PROD1', day_6].fix(1000)

print("=" * 80)
print("FORCING OPTIMAL SOLUTION")
print("=" * 80)
print("Fixed: production(MFG, PROD1, 2025-01-06) = 1,000")
print()

# Solve with this constraint
result = unified_model.solve(solver_name='cbc', time_limit_seconds=120, mip_gap=0.01)

print(f"Status: {result.termination_condition}")
print(f"Solve time: {result.solve_time_seconds:.2f}s")
print()

if result.termination_condition == 'optimal' or result.termination_condition == 'feasible':
    pyomo_model = unified_model.model

    print("✓ OPTIMAL SOLUTION IS FEASIBLE!")
    print()

    # Extract key variables
    prod_day6 = value(pyomo_model.production['MFG', 'PROD1', day_6])
    ship_day6_day7 = value(pyomo_model.shipment_cohort['MFG', 'BR1', 'PROD1', day_6, day_7, 'ambient'])
    inv_br1_day7 = value(pyomo_model.inventory_cohort['BR1', 'PROD1', day_6, day_7, 'ambient'])
    demand_day6_day7 = value(pyomo_model.demand_from_cohort['BR1', 'PROD1', day_6, day_7])

    print("Solution values:")
    print(f"  production(day 6): {prod_day6:,.0f}")
    print(f"  shipment(day 6→7): {ship_day6_day7:,.0f}")
    print(f"  inventory(BR1 day 7): {inv_br1_day7:,.0f}")
    print(f"  demand_from_cohort(day 7): {demand_day6_day7:,.0f}")
    print()

    # Check total cost
    print(f"Total cost: ${value(pyomo_model.obj):,.2f}")
    print(f"Expected: ~$6,022 (1000 × $5.022 + 1000 × $1.00)")
    print()

    # Check all production
    total_prod = sum(value(pyomo_model.production[n, p, d])
                     for (n, p, d) in pyomo_model.production)
    print(f"Total production: {total_prod:,.0f} units")

    # Check end inventory
    end_inv = sum(value(pyomo_model.inventory_cohort[n, p, pd, day_7, s])
                 for (n, p, pd, cd, s) in unified_model.cohort_index_set
                 if cd == day_7)
    print(f"End inventory: {end_inv:,.0f} units")

    if total_prod <= 1100 and end_inv < 100:
        print()
        print("✓✓✓ OPTIMAL SOLUTION CONFIRMED!")
        print("    The solver CAN find the optimal solution when forced.")
        print("    This means there's NO constraint making it infeasible.")
        print("    The bug is in the objective function or solver search!")

elif result.termination_condition == 'infeasible':
    print("❌ OPTIMAL SOLUTION IS INFEASIBLE!")
    print("   There's a hidden constraint blocking the optimal solution.")
else:
    print(f"⚠️  Unexpected result: {result.termination_condition}")
