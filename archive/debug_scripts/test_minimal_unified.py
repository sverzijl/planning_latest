"""Minimal test case: 1 mfg node → 1 demand node, should be trivially feasible."""

from datetime import date, timedelta
from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure
from src.optimization.unified_node_model import UnifiedNodeModel
from pyomo.environ import value

print("=" * 80)
print("MINIMAL TEST CASE: 1 MFG → 1 DEMAND")
print("=" * 80)

# Create minimal data
# Node 1: Manufacturing
mfg_node = UnifiedNode(
    id="MFG",
    name="Manufacturing",
    capabilities=NodeCapabilities(
        can_manufacture=True,
        production_rate_per_hour=1000.0,
        can_store=True,
        storage_mode=StorageMode.AMBIENT,
    )
)

# Node 2: Demand
demand_node = UnifiedNode(
    id="DEMAND",
    name="Demand Location",
    capabilities=NodeCapabilities(
        can_manufacture=False,
        can_store=True,
        storage_mode=StorageMode.AMBIENT,
        has_demand=True,
    )
)

# Route: MFG → DEMAND (1 day transit)
route = UnifiedRoute(
    id="R1",
    origin_node_id="MFG",
    destination_node_id="DEMAND",
    transit_days=1.0,
    transport_mode=TransportMode.AMBIENT,
    cost_per_unit=1.0,
)

# Forecast: 100 units demand on day 2
start_date = date(2025, 10, 1)
forecast = Forecast(
    name="Minimal Test",
    entries=[
        ForecastEntry(
            location_id="DEMAND",
            product_id="PRODUCT_A",
            forecast_date=start_date + timedelta(days=1),  # Day 2
            quantity=100.0
        )
    ]
)

# Labor: 2 days with capacity
labor_calendar = LaborCalendar(
    name="Minimal",
    days=[
        LaborDay(date=start_date, fixed_hours=12.0, regular_rate=25.0, overtime_rate=37.5, is_fixed_day=True),
        LaborDay(date=start_date + timedelta(days=1), fixed_hours=12.0, regular_rate=25.0, overtime_rate=37.5, is_fixed_day=True),
    ]
)

# Costs
cost_structure = CostStructure(
    production_cost_per_unit=5.0,
    shortage_penalty_per_unit=10000.0,
)

print("\nTest Setup:")
print(f"  Day 1: Produce 100 units at MFG")
print(f"  Day 1→2: Ship 100 units (1-day transit)")
print(f"  Day 2: Deliver to DEMAND (satisfy 100 units demand)")
print()

# Create model
model = UnifiedNodeModel(
    nodes=[mfg_node, demand_node],
    routes=[route],
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    start_date=start_date,
    end_date=start_date + timedelta(days=1),  # 2 days
    truck_schedules=[],
    use_batch_tracking=True,
    allow_shortages=True,
    enforce_shelf_life=True,
)

result = model.solve(time_limit_seconds=30, mip_gap=0.05)

print(f"Status: {result.termination_condition}")

if result.is_optimal() or result.is_feasible():
    solution = model.get_solution()

    production = sum(solution.get('production_by_date_product', {}).values())
    shipments = sum(solution.get('shipments_by_route_product_date', {}).values())
    shortages = sum(solution.get('shortages_by_dest_product_date', {}).values())

    print(f"\nResult:")
    print(f"  Production: {production:.0f} units")
    print(f"  Shipments: {shipments:.0f} units")
    print(f"  Shortages: {shortages:.0f} units")
    print(f"  Cost: ${solution['total_cost']:,.2f}")

    if production > 0:
        print("\n✅ MINIMAL CASE WORKS - Production happens!")
        print("   Bug must be in complexity (multi-node/multi-product interaction)")
    else:
        print("\n❌ MINIMAL CASE FAILS - No production even in simplest scenario")
        print("   Bug is in FUNDAMENTAL constraints")
        print("\n   Writing LP file...")
        model.model.write('minimal_infeasible.lp')
        print("   Check minimal_infeasible.lp to find the blocking constraint")
else:
    print(f"❌ Infeasible: {result.termination_condition}")
    model.model.write('minimal_infeasible.lp')
    print("LP file: minimal_infeasible.lp")
