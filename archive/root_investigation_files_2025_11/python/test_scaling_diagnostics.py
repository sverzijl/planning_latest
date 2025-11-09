"""Quick test to verify coefficient scaling improvement."""

from datetime import datetime, timedelta
from pathlib import Path

from src.parsers.multi_file_parser import MultiFileParser
from src.validation.data_coordinator import DataCoordinator
from src.optimization.sliding_window_model import SlidingWindowModel

# Load test data
forecast_file = Path("data/examples/Gluten Free Forecast - Latest.xlsm")
network_file = Path("data/examples/Network_Config.xlsx")
inventory_file = Path("data/examples/inventory_latest.XLSX")

print("="*80)
print("COEFFICIENT SCALING DIAGNOSTIC TEST")
print("="*80)

# Use DataCoordinator (handles validation)
coordinator = DataCoordinator(
    forecast_file=str(forecast_file),
    network_file=str(network_file),
    inventory_file=str(inventory_file)
)

validated = coordinator.load_and_validate()

# Short horizon for fast testing (1 week)
start = datetime(2025, 1, 6)
end = start + timedelta(days=6)

print(f"\nBuilding model: {start.date()} to {end.date()} (7 days)...")

# Build model
model_builder = SlidingWindowModel(
    nodes=validated.nodes,
    routes=validated.routes,
    forecast=validated.forecast,
    labor_calendar=validated.labor_calendar,
    cost_structure=validated.cost_structure,
    products=validated.products,
    start_date=start,
    end_date=end,
    truck_schedules=validated.truck_schedules,
    initial_inventory=validated.get_inventory_dict(),
    inventory_snapshot_date=validated.inventory_snapshot_date,
    allow_shortages=True,
    use_pallet_tracking=True,
    use_truck_pallet_tracking=True
)

print("\nBuilding Pyomo model...")
model = model_builder.build_model()

print("\n" + "="*80)
print("RUNNING COEFFICIENT DIAGNOSTICS")
print("="*80)

# Run diagnostics
diagnostics = model_builder.diagnose_scaling(model)

print(f"\nResults:")
print(f"  Status: {diagnostics['status']}")
print(f"  Matrix coefficient range: [{diagnostics['matrix_min']:.6e}, {diagnostics['matrix_max']:.6e}]")
print(f"  Ratio: {diagnostics['ratio']:.2e}")
print(f"  Target: < {diagnostics['target_ratio']:.2e}")
print(f"  Constraints analyzed: {diagnostics['constraint_count']}")

if diagnostics['warnings']:
    print(f"\n  Warnings:")
    for warning in diagnostics['warnings']:
        print(f"    ⚠️  {warning}")

if diagnostics['problem_constraints']:
    print(f"\n  Problem constraints (sample):")
    for constraint in diagnostics['problem_constraints'][:5]:
        print(f"    - {constraint['name'][:80]}")
        print(f"      Range: [{constraint['min']:.2e}, {constraint['max']:.2e}], ratio: {constraint['ratio']:.2e}")

print("\n" + "="*80)
print("EXPECTED vs ACTUAL")
print("="*80)
print(f"\n  BEFORE SCALING:")
print(f"    Matrix range: [5e-05, 2e+04] = 400,000,000 ratio")
print(f"\n  TARGET AFTER SCALING:")
print(f"    Matrix range: [0.32, 1500] = ~4,688 ratio")
print(f"\n  ACTUAL AFTER SCALING:")
print(f"    Matrix range: [{diagnostics['matrix_min']:.6e}, {diagnostics['matrix_max']:.6e}] = {diagnostics['ratio']:.0f} ratio")

if diagnostics['ratio'] < 10000:
    print(f"\n  ✅ SUCCESS: Coefficient ratio improved by ~{400_000_000 / diagnostics['ratio']:.0f}×!")
    print(f"     Status: {diagnostics['status']}")
    print(f"     Expected speedup: 20-40%")
else:
    print(f"\n  ⚠️  NEEDS IMPROVEMENT: Ratio still high ({diagnostics['ratio']:.2e})")
    print(f"     Target: < 10,000")

print("\n" + "="*80)
