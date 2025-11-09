"""
MIP Experiment: Increase waste cost dramatically.

If end inventory drops → Cost coefficient issue
If end inventory stays high → Constraint forces it
"""

from datetime import datetime, timedelta
from pyomo.core.base import value

from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType


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

# Test different waste multipliers
for mult in [10.0, 50.0, 100.0, 500.0]:
    print(f"\n{'='*100}")
    print(f"Testing waste_multiplier = {mult}")
    print(f"{'='*100}")

    # Modify cost structure
    cost_structure_test = cost_structure.copy(update={'waste_cost_multiplier': mult})

    model_builder = SlidingWindowModel(
        nodes, unified_routes, forecast, labor_calendar, cost_structure_test,
        products_dict, start, end, unified_truck_schedules,
        validated.get_inventory_dict(), validated.inventory_snapshot_date,
        True, True, True
    )

    result = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01)

    if not result.success:
        print(f"  Solve failed!")
        continue

    model = model_builder.model
    solution = model_builder.extract_solution(model)

    # Get end inventory
    last_date = max(model.dates)
    end_inv = sum(
        value(model.inventory[n, p, s, last_date])
        for (n, p, s, t) in model.inventory
        if t == last_date and value(model.inventory[n, p, s, last_date]) > 0.01
    )

    waste_cost_per_unit = mult * cost_structure.production_cost_per_unit
    actual_waste_cost = end_inv * waste_cost_per_unit

    print(f"  Waste cost: ${waste_cost_per_unit:.2f}/unit")
    print(f"  End inventory: {end_inv:,.0f} units")
    print(f"  Total waste cost: ${actual_waste_cost:,.0f}")
    print(f"  Production: {solution.total_production:,.0f} units")
    print(f"  Shortage: {solution.total_shortage_units:,.0f} units")
    print(f"  Objective: ${solution.total_cost:,.0f}")

print(f"\n\n{'='*100}")
print(f"MIP DIAGNOSIS:")
print(f"{'='*100}")

print(f"""
If end inventory DROPS as waste penalty increases:
  → Cost coefficient issue (waste penalty too low)
  → Increase waste_multiplier in production model

If end inventory STAYS HIGH despite extreme penalties:
  → Constraint forces it (not cost issue)
  → Need to identify and relax forcing constraint

If end inventory drops to ~0 at high penalty:
  → Proves low end inventory IS feasible
  → Current formulation just needs higher waste cost
""")
