"""Test unified model WITHOUT truck constraints to isolate bug."""

from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.manufacturing import ManufacturingSite
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.unified_node_model import UnifiedNodeModel
from pyomo.environ import value

parser = MultiFileParser(
    forecast_file='data/examples/Gfree Forecast.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

manufacturing_site = None
for loc in locations:
    if loc.type == 'manufacturing':
        manufacturing_site = ManufacturingSite(
            id=loc.id, name=loc.name, type=loc.type,
            storage_mode=loc.storage_mode, capacity=loc.capacity,
            latitude=loc.latitude, longitude=loc.longitude,
            production_rate=1400.0
        )
        break

converter = LegacyToUnifiedConverter()
nodes, unified_routes, _ = converter.convert_all(
    manufacturing_site, locations, routes, truck_schedules_list, forecast
)

all_dates = [entry.forecast_date for entry in forecast.entries]
start_date = min(all_dates)
end_date = start_date + timedelta(days=6)

print("=" * 80)
print("TESTING WITHOUT TRUCK CONSTRAINTS")
print("=" * 80)

model = UnifiedNodeModel(
    nodes=nodes,
    routes=unified_routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    start_date=start_date,
    end_date=end_date,
    truck_schedules=[],  # NO TRUCKS - remove truck constraints
    use_batch_tracking=True,
    allow_shortages=True,
    enforce_shelf_life=True,
)

result = model.solve(time_limit_seconds=90, mip_gap=0.05)

print(f"\nStatus: {result.termination_condition}")
print(f"Solve time: {result.solve_time_seconds:.1f}s")

if result.is_optimal() or result.is_feasible():
    solution = model.get_solution()

    production_count = len(solution.get('production_by_date_product', {}))
    shipment_count = len(solution.get('shipments_by_route_product_date', {}))
    shortage_count = len(solution.get('shortages_by_dest_product_date', {}))

    total_production = sum(solution.get('production_by_date_product', {}).values())
    total_shipments = sum(solution.get('shipments_by_route_product_date', {}).values())
    total_shortages = sum(solution.get('shortages_by_dest_product_date', {}).values())

    print(f"\nSOLUTION (No Trucks):")
    print(f"  Production entries: {production_count}")
    print(f"  Total production: {total_production:,.0f} units")
    print(f"  Shipment entries: {shipment_count}")
    print(f"  Total shipments: {total_shipments:,.0f} units")
    print(f"  Shortage entries: {shortage_count}")
    print(f"  Total shortages: {total_shortages:,.0f} units")
    print(f"  Total cost: ${solution['total_cost']:,.2f}")

    print("\n" + "=" * 80)
    if production_count > 0:
        print("✅ SUCCESS: Production happens WITHOUT trucks!")
        print("   BUG IS IN TRUCK CONSTRAINTS")
    else:
        print("❌ FAILURE: Still no production even without trucks")
        print("   BUG IS IN CORE FLOW (inventory balance/demand satisfaction)")
else:
    print(f"\n❌ Model did not solve: {result.termination_condition}")
