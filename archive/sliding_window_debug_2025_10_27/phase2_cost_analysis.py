"""Phase 2: Analyze cost structure - is shortage cheaper than production?"""
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
print("PHASE 2: COST STRUCTURE ANALYSIS")
print("=" * 80)

# Check cost parameters
print(f"\nCost Parameters:")
print(f"  Shortage penalty: ${cost_params.shortage_penalty_per_unit:.2f} /unit")
print(f"  Production cost: ${cost_params.production_cost_per_unit:.2f} /unit")

# Solve
result = model_wrapper.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.05, tee=False)
solved_model = model_wrapper.model

# Calculate actual costs from solution
total_demand = sum(model_wrapper.demand.values())
print(f"\nDemand: {total_demand:,.0f} units")

# Check shortage
total_shortage = sum(value(solved_model.shortage[idx]) for idx in solved_model.shortage)
print(f"\nShortage taken: {total_shortage:,.0f} units")
shortage_cost = total_shortage * cost_params.shortage_penalty_per_unit
print(f"Shortage cost: ${shortage_cost:,.2f}")

# Check production
total_production = sum(value(solved_model.production[idx]) for idx in solved_model.production)
print(f"\nProduction: {total_production:,.0f} units")
production_cost = total_production * cost_params.production_cost_per_unit
print(f"Production cost: ${production_cost:,.2f}")

# Check labor
total_labor_hours = sum(value(solved_model.labor_hours_used[idx]) for idx in solved_model.labor_hours_used)
print(f"\nLabor hours: {total_labor_hours:,.1f} hours")

# Get labor rate
first_date = start
labor_day = labor_calendar.get_labor_day(first_date)
labor_cost_rate = labor_day.regular_rate if labor_day else 20.0
print(f"Labor rate: ${labor_cost_rate:.2f} /hour")
labor_cost = total_labor_hours * labor_cost_rate
print(f"Labor cost: ${labor_cost:,.2f}")

# Total cost
total_cost = result.objective_value
print(f"\nTotal objective value: ${total_cost:,.2f}")

# Analysis
print(f"\n" + "=" * 80)
print(f"COST COMPARISON:")
print(f"=" * 80)

if total_production == 0 and total_shortage > 0:
    print(f"\nModel chose SHORTAGE over PRODUCTION")
    print(f"  Shortage cost: ${shortage_cost:,.2f}")

    # What would production cost?
    hypothetical_prod_cost = total_demand * cost_params.production_cost_per_unit
    hypothetical_labor = total_demand / 1400  # Production rate
    hypothetical_labor_cost = hypothetical_labor * labor_cost_rate
    hypothetical_total = hypothetical_prod_cost + hypothetical_labor_cost

    print(f"\n  If we produced {total_demand:,.0f} units:")
    print(f"    Production cost: ${hypothetical_prod_cost:,.2f}")
    print(f"    Labor cost (~{hypothetical_labor:.1f}h): ${hypothetical_labor_cost:,.2f}")
    print(f"    Total: ${hypothetical_total:,.2f}")

    print(f"\n  Comparison:")
    print(f"    Taking shortage: ${shortage_cost:,.2f}")
    print(f"    Producing: ${hypothetical_total:,.2f}")

    if shortage_cost < hypothetical_total:
        print(f"\n  ✅ Shortage IS cheaper - model is CORRECT!")
        print(f"     This is a cost parameter issue, not a model bug.")
    else:
        print(f"\n  ❌ Production would be cheaper - model is WRONG!")
        print(f"     This is a MODEL BUG - production should be chosen.")

elif total_production == 0 and total_shortage == 0:
    print(f"\n❌ NO production and NO shortage - but demand exists!")
    print(f"   This is IMPOSSIBLE - material balance violated!")

else:
    print(f"\nModel is producing to meet demand - normal behavior.")
