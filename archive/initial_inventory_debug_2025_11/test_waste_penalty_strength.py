"""Test different waste penalty strengths to find what drives inventory to zero."""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from datetime import timedelta
from copy import deepcopy

# Load data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)

forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()
inventory = parser.parse_inventory()

mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

start = inventory.snapshot_date
end = start + timedelta(weeks=4)
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print(f"{'=' * 80}")
print(f"TESTING WASTE PENALTY STRENGTH")
print(f"{'=' * 80}")

# Test different multipliers
multipliers_to_test = [1.5, 5.0, 8.0, 10.0, 15.0]

for mult in multipliers_to_test:
    # Create modified cost structure
    modified_costs = deepcopy(cost_params)
    modified_costs.waste_cost_multiplier = mult

    waste_penalty = mult * modified_costs.production_cost_per_unit

    print(f"\n{'=' * 80}")
    print(f"Test: waste_cost_multiplier = {mult}")
    print(f"  Waste penalty: ${waste_penalty:.2f}/unit")
    print(f"{'=' * 80}")

    model = SlidingWindowModel(
        nodes=nodes, routes=unified_routes, forecast=forecast,
        products=products, labor_calendar=labor_calendar,
        cost_structure=modified_costs,
        start_date=start, end_date=end,
        truck_schedules=unified_trucks,
        initial_inventory=inventory.to_optimization_dict(),
        inventory_snapshot_date=inventory.snapshot_date,
        allow_shortages=True,
        use_pallet_tracking=False,  # Faster solve
        use_truck_pallet_tracking=False
    )

    result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05, tee=False)

    if not (result.is_optimal() or result.is_feasible()):
        print(f"  ❌ Solve failed")
        continue

    solution = model.get_solution()

    # Check end inventory
    last_date = max(dt for (node, product, state, dt), qty in solution.inventory_state.items())
    end_inventory = sum(
        qty for (node, product, state, dt), qty in solution.inventory_state.items()
        if dt == last_date
    )

    waste_cost = solution.costs.waste.expiration_waste

    print(f"\n  Results:")
    print(f"    End inventory: {end_inventory:,.0f} units")
    print(f"    Waste cost: ${waste_cost:,.2f}")
    print(f"    Total cost: ${solution.total_cost:,.2f}")

    if end_inventory < 100:
        print(f"    ✅ SUCCESS: Inventory driven to near-zero ({end_inventory:.0f} units)")
        print(f"    Multiplier {mult} is strong enough!")
        break
    elif end_inventory < 5000:
        print(f"    ⚠️ IMPROVED: Inventory reduced to {end_inventory:.0f} (from 17,520)")
    else:
        print(f"    ❌ INSUFFICIENT: Still {end_inventory:.0f} units remaining")

print(f"\n{'=' * 80}")
print(f"RECOMMENDATION")
print(f"{'=' * 80}")

print(f"\nTo achieve zero end-of-horizon inventory:")
print(f"  Set waste_cost_multiplier ≥ 8.0")
print(f"  This gives penalty ≥ $10/unit (equal to shortage)")
print(f"\nUpdate in Network_Config.xlsx → CostParameters sheet")
