"""
Test if .stale attribute properly identifies uninitialized variables.

Hypothesis: .stale doesn't work with APPSI solver, so extraction
includes uninitialized variables with garbage/zero values.
"""

from datetime import datetime, timedelta
from pathlib import Path

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

forecast_entries = [ForecastEntry(location_id=e.node_id, product_id=e.product_id, forecast_date=e.demand_date, quantity=e.quantity) for e in validated.demand_entries]
forecast = Forecast(name='Test', entries=forecast_entries)

parser = MultiFileParser(forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm', network_file='data/examples/Network_Config.xlsx', inventory_file='data/examples/inventory_latest.XLSX')
_, locations, routes_legacy, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manufacturing_site = manufacturing_locations[0]

converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes_legacy)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

products_dict = {p.id: p for p in validated.products}

start = validated.planning_start_date
end = (datetime.combine(start, datetime.min.time()) + timedelta(days=6)).date()

model_builder = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=cost_structure,
    products=products_dict, start_date=start, end_date=end,
    truck_schedules=unified_truck_schedules,
    initial_inventory=validated.get_inventory_dict(),
    inventory_snapshot_date=validated.inventory_snapshot_date,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

result = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.01)
model = model_builder.model

print("="*80)
print("TESTING .stale ATTRIBUTE ON in_transit VARIABLES")
print("="*80)

# Sample 20 in_transit variables
sample_keys = list(model.in_transit.keys())[:20]

print(f"\nChecking {len(sample_keys)} sample variables:")
print(f"{'Index':<6} {'has_stale':<10} {'stale_val':<12} {'has_value':<12} {'value_val':<15} {'Can Extract?':<15}")
print("-"*90)

for i, key in enumerate(sample_keys):
    var = model.in_transit[key]

    has_stale = hasattr(var, 'stale')
    stale_val = var.stale if has_stale else "N/A"
    has_value_attr = hasattr(var, 'value')
    value_val = var.value if has_value_attr else "N/A"

    # What extraction code would do
    would_skip_stale = has_stale and var.stale
    would_skip_value = not has_value_attr or var.value is None
    can_extract = not would_skip_stale and not would_skip_value

    print(f"{i:<6} {str(has_stale):<10} {str(stale_val):<12} {str(has_value_attr):<12} {str(value_val):<15} {str(can_extract):<15}")

print("\n" + "="*80)
print("DIAGNOSIS:")
print("="*80)

# Count how extraction behaves
extraction_would_include = 0
actually_have_values = 0

for key in model.in_transit:
    var = model.in_transit[key]

    # What extraction does
    would_skip_stale = hasattr(var, 'stale') and var.stale
    would_skip_value = not hasattr(var, 'value') or var.value is None

    if not would_skip_stale and not would_skip_value:
        extraction_would_include += 1
        if var.value > 0.01:
            actually_have_values += 1

print(f"\nExtraction behavior:")
print(f"  Variables extraction WOULD include: {extraction_would_include}")
print(f"  Variables that ACTUALLY have value > 0.01: {actually_have_values}")
print(f"  Variables with value = 0 but not skipped: {extraction_would_include - actually_have_values}")

if extraction_would_include - actually_have_values > 500:
    print(f"\n❌ BUG CONFIRMED: Extraction includes {extraction_would_include - actually_have_values} zero-valued variables!")
    print(f"   These add to shipment totals even though solver set them to 0")
    print(f"   This inflates shipment counts")
else:
    print(f"\n✅ Extraction properly filters")

print("\n" + "="*80)
