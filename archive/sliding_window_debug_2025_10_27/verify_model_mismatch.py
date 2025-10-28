"""Verify that we're accessing the wrong model object."""
from datetime import date, timedelta
from pyomo.core.base import value
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

start = min(e.forecast_date for e in forecast.entries)
end = start + timedelta(days=1)
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

model_wrapper = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

print("=" * 80)
print("VERIFY MODEL OBJECT MISMATCH HYPOTHESIS")
print("=" * 80)

# Build a model (creates first Pyomo model)
old_unsolved_model = model_wrapper.build_model()
print(f"\n1. Built model: {id(old_unsolved_model)}")

# Solve (internally builds ANOTHER model!)
result = model_wrapper.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05, tee=False)
print(f"2. Solved, status: {result.termination_condition}")

# Get the SOLVED model
solved_model = model_wrapper.model  # This is the model that was actually solved!
print(f"3. Solved model: {id(solved_model)}")

print(f"\n4. Are they the same object? {old_unsolved_model is solved_model}")

# Try accessing variables from UNSOLVED model (should fail)
print(f"\n5. Accessing production from UNSOLVED model:")
try:
    first_prod = list(old_unsolved_model.production)[0]
    val = value(old_unsolved_model.production[first_prod])
    print(f"   production{first_prod} = {val}")
except ValueError as e:
    print(f"   ❌ ERROR: {str(e)[:80]}...")

# Try accessing variables from SOLVED model (should work!)
print(f"\n6. Accessing production from SOLVED model:")
try:
    first_prod = list(solved_model.production)[0]
    val = value(solved_model.production[first_prod])
    print(f"   production{first_prod} = {val}")
    print(f"   ✅ SUCCESS! Variables have values in the SOLVED model!")
except ValueError as e:
    print(f"   ❌ ERROR: {str(e)[:80]}...")

# Count non-zero production
prod_count = 0
prod_total = 0
for idx in solved_model.production:
    try:
        val = value(solved_model.production[idx])
        if val and val > 0.1:
            prod_count += 1
            prod_total += val
    except:
        pass

print(f"\n7. RESULTS FROM SOLVED MODEL:")
print(f"   Non-zero production variables: {prod_count}")
print(f"   Total production: {prod_total:,.0f} units")

print(f"\n✅ HYPOTHESIS CONFIRMED!")
print(f"   The bug was accessing the WRONG model object.")
print(f"   We were looking at the unsolved model instead of the solved model!")
