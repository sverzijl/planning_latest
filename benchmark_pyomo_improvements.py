#!/usr/bin/env python3
"""Benchmark script to measure Pyomo model performance improvements.

Measures:
- Model build time
- Solve time
- Total time
- Model statistics (variables, constraints)

Run before and after implementing optimization recommendations.
"""

import time
from datetime import date, timedelta
from pathlib import Path

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType


def load_test_data():
    """Load test data using MultiFileParser (matches UI workflow)."""
    data_dir = Path("data/examples")
    forecast_file = data_dir / "Gfree Forecast.xlsm"
    network_file = data_dir / "Network_Config.xlsx"

    if not forecast_file.exists():
        raise FileNotFoundError(f"Forecast file not found: {forecast_file}")
    if not network_file.exists():
        raise FileNotFoundError(f"Network file not found: {network_file}")

    print(f"Loading data...")
    print(f"  Forecast: {forecast_file.name}")
    print(f"  Network: {network_file.name}")

    # Parse using MultiFileParser
    parser = MultiFileParser(
        forecast_file=str(forecast_file),
        network_file=str(network_file),
        inventory_file=None,  # No initial inventory for benchmark
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Get manufacturing site
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    if not manufacturing_locations:
        raise ValueError("No manufacturing site found")

    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id,
        name=manuf_loc.name,
        storage_mode=manuf_loc.storage_mode,
        production_rate=getattr(manuf_loc, 'production_rate', 1400.0),
        daily_startup_hours=0.5,
        daily_shutdown_hours=0.25,
        default_changeover_hours=0.5,
        production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    # Convert to unified format
    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    # Use forecast start date
    start_date = min(entry.forecast_date for entry in forecast.entries)
    # 4-week horizon for realistic benchmark
    end_date = start_date + timedelta(days=27)

    print(f"  Nodes: {len(nodes)}")
    print(f"  Routes: {len(unified_routes)}")
    print(f"  Forecast entries: {len(forecast.entries)}")
    print(f"  Planning horizon: {start_date} to {end_date} ({(end_date - start_date).days + 1} days)")

    return {
        'nodes': nodes,
        'routes': unified_routes,
        'forecast': forecast,
        'labor_calendar': labor_calendar,
        'truck_schedules': unified_truck_schedules,
        'cost_structure': cost_structure,
        'start_date': start_date,
        'end_date': end_date,
    }


def count_model_components(model):
    """Count variables and constraints in the model."""
    from pyomo.environ import Var, Constraint

    num_vars = 0
    num_binary = 0
    num_integer = 0
    num_continuous = 0

    for v in model.component_data_objects(Var, active=True):
        num_vars += 1
        if v.is_binary():
            num_binary += 1
        elif v.is_integer():
            num_integer += 1
        elif v.is_continuous():
            num_continuous += 1

    num_constraints = sum(1 for _ in model.component_data_objects(Constraint, active=True))

    return {
        'total_vars': num_vars,
        'binary_vars': num_binary,
        'integer_vars': num_integer,
        'continuous_vars': num_continuous,
        'constraints': num_constraints,
    }


def benchmark_model(data, solver_name='cbc', use_warmstart=False):
    """Run benchmark on UnifiedNodeModel."""

    print(f"\n{'='*70}")
    print(f"BENCHMARK: solver={solver_name}, warmstart={use_warmstart}")
    print(f"{'='*70}")

    # Create model
    print("\nCreating UnifiedNodeModel...")
    model_instance = UnifiedNodeModel(
        nodes=data['nodes'],
        routes=data['routes'],
        forecast=data['forecast'],
        labor_calendar=data['labor_calendar'],
        cost_structure=data['cost_structure'],
        start_date=data['start_date'],
        end_date=data['end_date'],
        truck_schedules=data['truck_schedules'],
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    # Measure model build time
    print("\nBuilding Pyomo model...")
    build_start = time.time()
    pyomo_model = model_instance.build_model()
    build_time = time.time() - build_start

    print(f"  Model build time: {build_time:.2f}s")

    # Count model components
    stats = count_model_components(pyomo_model)
    print(f"\nModel Statistics:")
    print(f"  Total variables: {stats['total_vars']:,}")
    print(f"    - Binary: {stats['binary_vars']:,}")
    print(f"    - Integer: {stats['integer_vars']:,}")
    print(f"    - Continuous: {stats['continuous_vars']:,}")
    print(f"  Constraints: {stats['constraints']:,}")

    # Solve
    print(f"\nSolving with {solver_name.upper()}...")
    solve_start = time.time()
    result = model_instance.solve(
        solver_name=solver_name,
        time_limit_seconds=120,
        mip_gap=0.01,
        tee=False,
        use_warmstart=use_warmstart,
    )
    solve_time = time.time() - solve_start

    total_time = build_time + solve_time

    # Results
    print(f"\n{'='*70}")
    print(f"RESULTS")
    print(f"{'='*70}")
    print(f"  Status: {result.status}")
    print(f"  Build time: {build_time:.2f}s")
    print(f"  Solve time: {solve_time:.2f}s")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Objective value: ${result.objective_value:,.2f}")
    print(f"  MIP gap: {result.mip_gap:.2%}")

    return {
        'build_time': build_time,
        'solve_time': solve_time,
        'total_time': total_time,
        'status': result.status,
        'objective_value': result.objective_value,
        'mip_gap': result.mip_gap,
        'stats': stats,
    }


def main():
    """Run benchmarks."""
    print("="*70)
    print("PYOMO MODEL PERFORMANCE BENCHMARK")
    print("="*70)

    # Load data once
    data = load_test_data()

    # Run benchmark with CBC solver (baseline)
    cbc_results = benchmark_model(data, solver_name='cbc', use_warmstart=False)

    # Try HiGHS if available
    try:
        print("\n")
        highs_results = benchmark_model(data, solver_name='highs', use_warmstart=False)
    except Exception as e:
        print(f"\nHiGHS benchmark skipped: {e}")
        highs_results = None

    # Summary
    print(f"\n{'='*70}")
    print(f"BENCHMARK SUMMARY")
    print(f"{'='*70}")
    print(f"\nCBC Solver:")
    print(f"  Build: {cbc_results['build_time']:.2f}s")
    print(f"  Solve: {cbc_results['solve_time']:.2f}s")
    print(f"  Total: {cbc_results['total_time']:.2f}s")

    if highs_results:
        print(f"\nHiGHS Solver:")
        print(f"  Build: {highs_results['build_time']:.2f}s")
        print(f"  Solve: {highs_results['solve_time']:.2f}s")
        print(f"  Total: {highs_results['total_time']:.2f}s")
        print(f"\nHiGHS Speedup: {cbc_results['total_time'] / highs_results['total_time']:.2f}x")


if __name__ == "__main__":
    main()
