"""Debug unified model infeasibility by writing LP file."""

from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.manufacturing import ManufacturingSite
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.unified_node_model import UnifiedNodeModel


parser = MultiFileParser(
    forecast_file="data/examples/Gfree Forecast.xlsm",
    network_file="data/examples/Network_Config.xlsx"
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
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site, locations, routes,
    truck_schedules_list, forecast
)

all_dates = [entry.forecast_date for entry in forecast.entries]
start_date = min(all_dates)
end_date = start_date + timedelta(days=6)

print("Creating unified model...")
model = UnifiedNodeModel(
    nodes=nodes,
    routes=unified_routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    start_date=start_date,
    end_date=end_date,
    truck_schedules=unified_trucks,
    use_batch_tracking=True,
    allow_shortages=False,  # No shortages - forces production
    enforce_shelf_life=True,
)

print("\nSolving...")
result = model.solve(time_limit_seconds=60, mip_gap=0.05)

print(f"Status: {result.termination_condition}")

if not result.is_feasible():
    print("\n❌ MODEL IS INFEASIBLE")
    print("Writing LP file for inspection...")
    model.model.write('unified_model_infeasible.lp')
    print("✅ LP file written to: unified_model_infeasible.lp")
    print()
    print("Inspect the file to find:")
    print("  - Disconnected variable groups")
    print("  - Over-constrained flows")
    print("  - Missing linking constraints")
    print()
    print("Key things to check:")
    print("  1. Are production variables linked to inventory_cohort?")
    print("  2. Are inventory_cohort linked to shipment_cohort?")
    print("  3. Are shipment_cohort linked to demand_from_cohort?")
    print("  4. Are there any constraints forcing everything to zero?")
else:
    print("\n✅ MODEL IS FEASIBLE/OPTIMAL!")
    solution = model.get_solution()
    if solution:
        print(f"  Production: {sum(solution.get('production_by_date_product', {}).values()):,.0f} units")
        print(f"  Shipments: {sum(solution.get('shipments_by_route_product_date', {}).values()):,.0f} units")
