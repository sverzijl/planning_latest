"""Simple test - Use real data but minimal horizon.

Test waste penalty with:
- Real network (but simplified)
- 2-day horizon (predict outcome easily)
- Strong waste penalty (20×)

Expected: Zero inventory on last day.
"""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from datetime import timedelta, date

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)

forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()
inventory = parser.parse_inventory()

# EXTREME waste penalty
cost_params.waste_cost_multiplier = 100.0  # $130/unit!

mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

start = inventory.snapshot_date
end = start + timedelta(days=2)  # 2 DAYS ONLY

product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

# Get demand
total_demand_2days = sum(
    entry.quantity for entry in forecast.entries
    if start <= entry.forecast_date <= end
)

print("="*80)
print("SIMPLE TEST - 2 days with EXTREME waste penalty")
print("="*80)
print(f"\nSetup:")
print(f"  Horizon: 2 days ({start} to {end})")
print(f"  Total demand: {total_demand_2days:,.0f} units")
print(f"  Waste penalty: $130/unit (100× multiplier!)")
print(f"  Shortage penalty: $10/unit")
print(f"  Ratio: Waste is 13× more expensive than shortage!")

print(f"\nExpected:")
print(f"  Model should prefer shortage over ANY end inventory")
print(f"  End inventory should be ZERO")

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params,
    start_date=start, end_date=end,
    truck_schedules=unified_trucks,
    initial_inventory=None,  # NO initial inventory
    inventory_snapshot_date=start,
    allow_shortages=True,
    use_pallet_tracking=False,
    use_truck_pallet_tracking=False
)

result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, tee=False)

print(f"\nResult: {result.termination_condition}")

if result.is_optimal() or result.is_feasible():
    solution = model.get_solution()

    last_day = end - timedelta(days=1)
    end_inv = sum(qty for (n, p, s, d), qty in solution.inventory_state.items() if d == last_day)

    total_prod = sum(qty for (n, p, d), qty in solution.production_by_date_product.items())
    total_consumed = sum(qty for (n, p, d), qty in solution.demand_consumed.items())

    print(f"\nACTUAL Results:")
    print(f"  Production: {total_prod:,.0f}")
    print(f"  Consumed: {total_consumed:,.0f}")
    print(f"  End inventory: {end_inv:,.0f}")
    print(f"  Shortage: {solution.total_shortage_units:,.0f}")

    if end_inv < 10:
        print(f"\n  ✅ SUCCESS: Waste penalty works! End inventory = {end_inv:.0f}")
        print(f"     Now test with longer horizon...")
    else:
        print(f"\n  ❌ FUNDAMENTAL BUG: Even with $130/unit penalty, {end_inv:.0f} units waste!")
        print(f"     Waste penalty NOT preventing production")

        # Calculate costs
        waste_cost_actual = end_inv * 130
        shortage_cost_actual = solution.total_shortage_units * 10

        print(f"\n  Costs:")
        print(f"    Waste: ${waste_cost_actual:,.2f}")
        print(f"    Shortage: ${shortage_cost_actual:,.2f}")

        if solution.total_shortage_units > 1000:
            print(f"\n  Model chose: High shortage ({solution.total_shortage_units:.0f}) + waste ({end_inv:.0f})")
            print(f"  Should choose: Higher shortage, zero waste")
            print(f"\n  This proves waste penalty is NOT in objective properly!")
else:
    print(f"\n  Infeasible with 2-day horizon")
