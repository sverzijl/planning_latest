"""
Detailed MIP Analysis: Compare WITH vs WITHOUT init_inv in Q

User insight: Model sees all 28 days at once. If it produces waste when shortage
is cheaper, something is FORCING it. Need to identify WHAT.

This script will:
1. Solve WITH init_inv in Q (current)
2. Solve WITHOUT init_inv in Q (modified)
3. Compare in detail: production timing, end inventory, where differences occur
"""

from datetime import datetime, timedelta
from pyomo.core.base import value

from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType


def build_model():
    """Build model components."""
    coordinator = DataCoordinator(
        forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
        network_file='data/examples/Network_Config.xlsx',
        inventory_file='data/examples/inventory_latest.XLSX'
    )
    validated = coordinator.load_and_validate()

    forecast_entries = [
        ForecastEntry(location_id=e.node_id, product_id=e.product_id,
                     forecast_date=e.demand_date, quantity=e.quantity)
        for e in validated.demand_entries
    ]
    forecast = Forecast(name="Test", entries=forecast_entries)

    parser = MultiFileParser(
        'data/examples/Gluten Free Forecast - Latest.xlsm',
        'data/examples/Network_Config.xlsx',
        'data/examples/inventory_latest.XLSX'
    )
    _, locations, routes_legacy, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manufacturing_site = manufacturing_locations[0]

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes_legacy)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)
    products_dict = {p.id: p for p in validated.products}

    start = validated.planning_start_date
    end = (datetime.combine(start, datetime.min.time()) + timedelta(days=27)).date()

    return (validated, forecast, nodes, unified_routes, labor_calendar,
            truck_schedules_list, cost_structure, products_dict, start, end,
            unified_truck_schedules)


# Build once
components = build_model()
(validated, forecast, nodes, unified_routes, labor_calendar,
 truck_schedules_list, cost_structure, products_dict, start, end,
 unified_truck_schedules) = components

print("="*100)
print("SOLVING WITH init_inv IN Q (Current Formulation)")
print("="*100)

model_with = SlidingWindowModel(
    nodes, unified_routes, forecast, labor_calendar, cost_structure,
    products_dict, start, end, unified_truck_schedules,
    validated.get_inventory_dict(), validated.inventory_snapshot_date,
    True, True, True
)

result_with = model_with.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01)

if not result_with.success:
    print("Solve failed WITH init_inv!")
    exit(1)

print(f"\nSolved WITH init_inv in Q!")

model_pyomo_with = model_with.model
solution_with = model_with.extract_solution(model_pyomo_with)

# Extract key metrics WITH
production_with = solution_with.total_production
objective_with = solution_with.total_cost
shortage_with = solution_with.total_shortage_units

# End inventory WITH
last_date = max(model_pyomo_with.dates)
end_inv_with = sum(
    value(model_pyomo_with.inventory[n, p, s, last_date])
    for (n, p, s, t) in model_pyomo_with.inventory
    if t == last_date and value(model_pyomo_with.inventory[n, p, s, last_date]) > 0.01
)

# Production by date WITH
prod_by_date_with = {}
for t in model_pyomo_with.dates:
    prod_today = sum(
        value(model_pyomo_with.production[n, p, date])
        for (n, p, date) in model_pyomo_with.production
        if date == t
    )
    if prod_today > 1:
        prod_by_date_with[t] = prod_today

print(f"\nResults WITH init_inv in Q:")
print(f"  Production: {production_with:,.0f} units")
print(f"  End inventory: {end_inv_with:,.0f} units")
print(f"  Shortage: {shortage_with:,.0f} units")
print(f"  Objective: ${objective_with:,.0f}")
print(f"  Production days: {len(prod_by_date_with)}")

print(f"\n\n{'='*100}")
print(f"Now I need to manually edit the code to remove init_inv from Q and re-run...")
print(f"{'='*100}")
print(f"""
TO COMPLETE THIS ANALYSIS:

1. Edit src/optimization/sliding_window_model.py
   - Lines 1227-1234: Comment out init_inv addition to Q_ambient
   - Lines 1340-1346: Comment out init_inv addition to Q_frozen
   - Lines 1427-1431: Comment out init_inv addition to Q_thawed

2. Run this script again to solve WITHOUT init_inv in Q

3. Compare the results to understand the mechanism

KEY QUESTIONS TO ANSWER:
a) WHERE does end inventory increase? (which nodes/products?)
b) WHEN does production shift? (earlier/later/same days?)
c) HOW does init_inv behave? (consumed Day 1 or locked as inventory?)
d) WHICH constraint becomes tight/infeasible?

This will reveal if there's a CORRECT way to fix the formulation.
""")
