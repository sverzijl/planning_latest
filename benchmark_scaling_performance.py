"""
Benchmark to verify coefficient scaling performance improvement.

Compares solve time with scaled model to baseline of 107 seconds.
"""

import time
from datetime import datetime, timedelta
from pathlib import Path

from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType

print("="*80)
print("COEFFICIENT SCALING PERFORMANCE BENCHMARK")
print("="*80)

# Load data
forecast_file = Path("data/examples/Gluten Free Forecast - Latest.xlsm")
network_file = Path("data/examples/Network_Config.xlsx")
inventory_file = Path("data/examples/inventory_latest.XLSX")

print("\nLoading and validating data...")
coordinator = DataCoordinator(
    forecast_file=str(forecast_file),
    network_file=str(network_file),
    inventory_file=str(inventory_file)
)

validated = coordinator.load_and_validate()

# Use validated planning dates (ensures demand is included)
start = validated.planning_start_date
end = validated.planning_end_date
horizon_days = (end - start).days + 1

print(f"\nHorizon: {start} to {end} ({horizon_days} days)")
print(f"  Nodes: {len(validated.nodes)}")
print(f"  Products: {len(validated.products)}")
print(f"  Demand entries: {len(validated.demand_entries)}")

# Build forecast from validated data
forecast_entries = [
    ForecastEntry(
        location_id=entry.node_id,
        product_id=entry.product_id,
        forecast_date=entry.demand_date,
        quantity=entry.quantity
    )
    for entry in validated.demand_entries
]
forecast = Forecast(name="Validated Forecast", entries=forecast_entries)

# Load network components
print("\nLoading network components...")
parser = MultiFileParser(
    forecast_file=str(forecast_file),
    network_file=str(network_file),
    inventory_file=str(inventory_file)
)
_, locations, routes_legacy, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

# Get manufacturing site
manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manufacturing_site = manufacturing_locations[0]

# Convert to unified format
converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes_legacy)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

# Products dict
products_dict = {p.id: p for p in validated.products}

# Build model
print("\n" + "="*80)
print("BUILDING MODEL")
print("="*80)

build_start = time.time()

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

model = model_builder.build_model()
build_time = time.time() - build_start

print(f"\n✓ Model built in {build_time:.1f}s")

# Run coefficient diagnostics
print("\n" + "="*80)
print("COEFFICIENT DIAGNOSTICS (SCALED MODEL)")
print("="*80)

diagnostics = model_builder.diagnose_scaling(model)

print(f"\nScaling Quality:")
print(f"  Status: {diagnostics['status']}")
print(f"  Coefficient range: [{diagnostics['matrix_min']:.6e}, {diagnostics['matrix_max']:.6e}]")
print(f"  Ratio: {diagnostics['ratio']:,.0f}")
print(f"  Target: < {diagnostics['target_ratio']:.0f}")

if diagnostics['warnings']:
    print(f"\n  ⚠️  Warnings:")
    for w in diagnostics['warnings']:
        print(f"    - {w}")

# Solve model
print("\n" + "="*80)
print("SOLVING MODEL")
print("="*80)

print("\nSolver: APPSI HiGHS")
print("MIP Gap: 1% (0.01)")
print("Time Limit: 300 seconds\n")

solve_start = time.time()

result = model_builder.solve(
    solver_name='appsi_highs',
    time_limit_seconds=300,
    mip_gap=0.01
)

solve_time = time.time() - solve_start

print(f"\n✓ Solve completed in {solve_time:.1f}s")

# Extract solution
solution = model_builder.extract_solution(model)

# Results
print("\n" + "="*80)
print("RESULTS")
print("="*80)

print(f"\nSolution Status: {result.termination_condition}")
print(f"  Total production: {solution.total_production:,.0f} units")
print(f"  Fill rate: {solution.fill_rate:.1%}")
print(f"  Total cost: ${solution.total_cost:,.2f}")

# Performance comparison
print("\n" + "="*80)
print("PERFORMANCE COMPARISON")
print("="*80)

baseline_time = 107.0  # From user's HiGHS output
baseline_ratio = 400_000_000  # Before scaling

actual_improvement = (baseline_time - solve_time) / baseline_time * 100
scaling_improvement = baseline_ratio / diagnostics['ratio']

print(f"\n  BASELINE (Unscaled Model):")
print(f"    Solve time: {baseline_time:.0f} seconds")
print(f"    Coefficient ratio: {baseline_ratio:.2e}")
print(f"    Status: POOR (stuck at 2.06% gap)")
print(f"\n  ACTUAL (Scaled Model):")
print(f"    Solve time: {solve_time:.1f} seconds")
print(f"    Coefficient ratio: {diagnostics['ratio']:.2e}")
print(f"    Status: {diagnostics['status']}")

print(f"\n  IMPROVEMENT:")
print(f"    Solve time: {actual_improvement:+.1f}% ({baseline_time - solve_time:.1f}s faster)")
print(f"    Coefficient scaling: {scaling_improvement:,.0f}× better")

# Verdict
if solve_time < baseline_time * 0.80:
    speedup_pct = (1 - solve_time/baseline_time) * 100
    print(f"\n  ✅ SUCCESS: {speedup_pct:.1f}% speedup achieved (target: 20-40%)")
elif solve_time < baseline_time * 0.95:
    speedup_pct = (1 - solve_time/baseline_time) * 100
    print(f"\n  ✅ MODERATE: {speedup_pct:.1f}% speedup achieved (below 20% target but still improved)")
else:
    print(f"\n  ⚠️  WARNING: Minimal speedup ({actual_improvement:.1f}%)")
    print(f"     Expected 20-40%, got {actual_improvement:.1f}%")
    print(f"     May need further tuning or different problem instance")

print("\n" + "="*80)
