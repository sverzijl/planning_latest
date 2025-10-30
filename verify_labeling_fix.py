"""Verify labeling report shows destinations (not Unknown)."""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from src.analysis.production_labeling_report import ProductionLabelingReportGenerator
from datetime import timedelta

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)

forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()
inventory = parser.parse_inventory()

mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

start = inventory.snapshot_date
end = start + timedelta(weeks=1)
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks,
    initial_inventory=inventory.to_optimization_dict(),
    inventory_snapshot_date=inventory.snapshot_date,
    allow_shortages=True
)

print("Solving model...")
result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, tee=False)
solution = model.get_solution()

# Test labeling report
generator = ProductionLabelingReportGenerator(solution)
generator.set_leg_states(model.route_arrival_state)

requirements = generator.generate_labeling_requirements()

print(f"\n{'=' * 80}")
print("LABELING FIX VERIFICATION")
print(f"{'=' * 80}")

print(f"\n✅ Total labeling requirements: {len(requirements)}")

# Check for Unknown destinations
has_unknown = sum(1 for req in requirements
                  if 'Unknown' in req.ambient_destinations or 'Unknown' in req.frozen_destinations)

if has_unknown > 0:
    print(f"\n❌ FAIL: {has_unknown} requirements show 'Unknown' destinations")
else:
    print(f"\n✅ PASS: No 'Unknown' destinations found")

# Show sample requirements
print(f"\nSample requirements (first 3):")
for req in requirements[:3]:
    print(f"\n  {req.production_date} - {req.product_id}")
    print(f"    Total: {req.total_quantity:.0f} units")
    if req.frozen_quantity > 0:
        print(f"    Frozen: {req.frozen_quantity:.0f} units → {req.frozen_destinations}")
    if req.ambient_quantity > 0:
        print(f"    Ambient: {req.ambient_quantity:.0f} units → {req.ambient_destinations}")

# Verify we have actual destinations
all_frozen_dests = set()
all_ambient_dests = set()
for req in requirements:
    all_frozen_dests.update(req.frozen_destinations)
    all_ambient_dests.update(req.ambient_destinations)

print(f"\n✅ All frozen destinations: {sorted(all_frozen_dests)}")
print(f"✅ All ambient destinations: {sorted(all_ambient_dests)}")

print(f"\n{'=' * 80}")
print("VERIFICATION COMPLETE")
print(f"{'=' * 80}")
