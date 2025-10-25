"""
12-Week @ 2% Gap WITH Shipment Filtering
"""

from datetime import date, timedelta
from pathlib import Path
import time

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from tests.conftest import create_test_products

parser = MultiFileParser(
    forecast_file=Path('data/examples/Gluten Free Forecast - Latest.xlsm'),
    network_file=Path('data/examples/Network_Config.xlsx')
)
forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

manuf_loc = [loc for loc in locations if loc.type == LocationType.MANUFACTURING][0]
manuf_site = ManufacturingSite(
    id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
    production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
    default_changeover_hours=0.5, production_cost_per_unit=cost_structure.production_cost_per_unit
)

start_date = min(e.forecast_date for e in forecast.entries)
end_date = start_date + timedelta(days=83)

converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manuf_site, locations, forecast)
unified_routes = converter.convert_routes(routes)
unified_trucks = converter.convert_truck_schedules(truck_schedules_list, manuf_site.id)
products = create_test_products(sorted(set(e.product_id for e in forecast.entries)))

print("="*80)
print("12-WEEK @ 2% GAP WITH SHIPMENT FILTERING")
print("="*80)

model = UnifiedNodeModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=cost_structure,
    truck_schedules=unified_trucks, products=products,
    start_date=start_date, end_date=end_date,
    use_batch_tracking=True, allow_shortages=True,
    filter_shipments_by_freshness=True,  # ENABLED
)

print("\nSolving...")
start_time = time.time()

result = model.solve(
    solver_name='appsi_highs',
    mip_gap=0.02,
    time_limit_seconds=7200
)

elapsed = time.time() - start_time
shipments = len(model.model.shipment_cohort_index) if hasattr(model.model, 'shipment_cohort_index') else 0

print(f"\nRESULTS:")
print(f"  Time: {elapsed:.1f}s ({elapsed/60:.1f} min)")
print(f"  Objective: ${result.objective_value:,.2f}")
print(f"  Status: {result.termination_condition}")
print(f"  Shipment cohorts: {shipments:,}")
print(f"  Success: {result.success}")
