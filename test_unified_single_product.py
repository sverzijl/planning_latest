"""Test unified model with real network but only ONE product."""

from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.manufacturing import ManufacturingSite
from src.models.forecast import Forecast
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.unified_node_model import UnifiedNodeModel

parser = MultiFileParser(
    forecast_file='data/examples/Gfree Forecast.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

forecast_full, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

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
    manufacturing_site, locations, routes, truck_schedules_list, forecast_full
)

# Filter forecast to ONE product only
all_products = list(set(e.product_id for e in forecast_full.entries))
single_product = all_products[0]

filtered_entries = [e for e in forecast_full.entries if e.product_id == single_product]

forecast_single = Forecast(
    name=f"Single Product: {single_product}",
    entries=filtered_entries
)

all_dates = [entry.forecast_date for entry in forecast_single.entries]
start_date = min(all_dates)
end_date = start_date + timedelta(days=6)

print("=" * 80)
print(f"TESTING WITH SINGLE PRODUCT: {single_product}")
print("=" * 80)
print(f"  Full network: {len(nodes)} nodes, {len(unified_routes)} routes")
print(f"  Demand entries: {len(forecast_single.entries)}")
print()

model = UnifiedNodeModel(
    nodes=nodes,
    routes=unified_routes,
    forecast=forecast_single,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    start_date=start_date,
    end_date=end_date,
    truck_schedules=[],  # No trucks
    use_batch_tracking=True,
    allow_shortages=True,
    enforce_shelf_life=True,
)

result = model.solve(time_limit_seconds=60, mip_gap=0.05)

print(f"Status: {result.termination_condition}")

if result.is_optimal() or result.is_feasible():
    solution = model.get_solution()

    production = sum(solution.get('production_by_date_product', {}).values())
    shipments = sum(solution.get('shipments_by_route_product_date', {}).values())
    shortages = sum(solution.get('shortages_by_dest_product_date', {}).values())

    print(f"\nResult (Single Product):")
    print(f"  Production: {production:,.0f} units")
    print(f"  Shipments: {shipments:,.0f} units")
    print(f"  Shortages: {shortages:,.0f} units")

    if production > 0:
        print("\n✅ SINGLE PRODUCT WORKS!")
        print("   Bug is likely in MULTI-PRODUCT interactions")
    else:
        print("\n❌ SINGLE PRODUCT FAILS")
        print("   Bug is in NETWORK TOPOLOGY or MULTI-NODE flow")
