"""
Test commit 3a71197 to see if it produces ~276k units.
"""

from datetime import datetime, timedelta

from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType


# Load data
print("Loading data...")
coordinator = DataCoordinator(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)
validated = coordinator.load_and_validate()

forecast_entries = [
    ForecastEntry(
        location_id=entry.node_id,
        product_id=entry.product_id,
        forecast_date=entry.demand_date,
        quantity=entry.quantity
    )
    for entry in validated.demand_entries
]
forecast = Forecast(name="Test Forecast", entries=forecast_entries)

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)
_, locations, routes_legacy, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manufacturing_site = manufacturing_locations[0]

converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes_legacy)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

products_dict = {p.id: p for p in validated.products}

# 4-week horizon
horizon_days = 28
start = validated.planning_start_date
end = (datetime.combine(start, datetime.min.time()) + timedelta(days=horizon_days-1)).date()

print(f"Building 4-week model...")
print(f"  Horizon: {start} to {end}")

model_builder = SlidingWindowModel(
    nodes=nodes,
    routes=unified_routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    products=products_dict,
    start_date=start,
    end_date=end,
    truck_schedules=unified_truck_schedules,
    initial_inventory=validated.get_inventory_dict(),
    inventory_snapshot_date=validated.inventory_snapshot_date,
    allow_shortages=True,
    use_pallet_tracking=True,
    use_truck_pallet_tracking=True
)

print(f"\nSolving...")
result = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01)

if not result.success:
    print(f"\n❌ Solve failed: {result.termination_condition}")
    exit(1)

print(f"\n✓ Solve succeeded!")

model = model_builder.model
solution = model_builder.extract_solution(model)

# Check production
print(f"\n{'='*80}")
print(f"PRODUCTION CHECK - COMMIT 3a71197")
print(f"{'='*80}")

total_production = solution.total_production
num_batches = len(solution.production_batches)

print(f"\nTotal production: {total_production:,.0f} units")
print(f"Production batches: {num_batches}")
print(f"Objective: ${solution.total_cost:,.0f}")
print(f"Fill rate: {solution.fill_rate:.1%}")

# Check against expectations
if 250000 < total_production < 320000:
    print(f"\n✅ COMMIT 3a71197 IS WORKING!")
    print(f"   Production {total_production:,.0f} is in expected range [250k, 320k]")
    print(f"\n   Next step: diff this commit vs HEAD to find the bug")
elif 7000 < total_production < 50000:
    print(f"\n❌ COMMIT 3a71197 IS ALSO BROKEN!")
    print(f"   Production {total_production:,.0f} is too low (expected 250k-320k)")
    print(f"\n   Need to check earlier commits")
else:
    print(f"\n⚠️  UNEXPECTED production level: {total_production:,.0f}")

print(f"\n{'='*80}")
