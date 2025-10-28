"""Check if balance constraints are being violated."""
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

result = model_wrapper.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05, tee=False)
solved_model = model_wrapper.model

print("=" * 80)
print("CHECK CONSTRAINT SLACK (Are constraints violated?)")
print("=" * 80)

# Check manufacturing balance constraint slack
mfg_id = '6122'
first_product = product_ids[0]
first_date = start

if (mfg_id, first_product, first_date) in solved_model.ambient_balance_con:
    con = solved_model.ambient_balance_con[mfg_id, first_product, first_date]

    # Evaluate constraint expression
    try:
        # LHS - RHS should = 0 for equality constraint
        lhs = value(con.body)  # Left side of ==
        rhs = value(con.lower)  # Right side (for equality, lower == upper)

        slack = abs(lhs - rhs)

        print(f"\nManufacturing balance for {first_product[:30]}, {first_date}:")
        print(f"  LHS (inventory): {lhs:.2f}")
        print(f"  RHS (production + arrivals - departures): {rhs:.2f}")
        print(f"  Slack (|LHS - RHS|): {slack:.6f}")

        if slack > 0.01:
            print(f"  ❌ CONSTRAINT VIOLATED! (slack > 0.01)")
        else:
            print(f"  ✅ Constraint satisfied")

    except Exception as e:
        print(f"  ERROR evaluating constraint: {e}")

# Check a few more manufacturing balance constraints
print(f"\nChecking multiple manufacturing balance constraints:")
checked = 0
violated = 0
for idx in solved_model.ambient_balance_con:
    node_id, prod, date_val = idx
    if node_id == '6122' and checked < 5:
        con = solved_model.ambient_balance_con[idx]
        try:
            lhs = value(con.body)
            rhs = value(con.lower) if con.lower is not None else value(con.upper)
            slack = abs(lhs - rhs)

            if slack > 0.01:
                print(f"  ❌ VIOLATED [{prod[:20]}, {date_val}]: slack = {slack:.4f}")
                violated += 1
            else:
                print(f"  ✅ OK [{prod[:20]}, {date_val}]: slack = {slack:.6f}")
            checked += 1
        except:
            pass

print(f"\nSummary: {violated}/{checked} constraints violated")

if violated > 0:
    print(f"\n⚠️  CONSTRAINTS ARE BEING VIOLATED!")
    print(f"   This means the model formulation has a bug.")
