#!/usr/bin/env python3
"""Quick benchmark to measure model build time improvements.

Focuses on model build time where quicksum() optimization has the most impact.
"""

import time
from datetime import timedelta
from pathlib import Path

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType


def main():
    """Run quick build time benchmark."""
    print("="*70)
    print("PYOMO MODEL BUILD TIME BENCHMARK (OPTIMIZED VERSION)")
    print("="*70)

    data_dir = Path("data/examples")
    forecast_file = data_dir / "Gfree Forecast.xlsm"
    network_file = data_dir / "Network_Config.xlsx"

    print(f"\nLoading data...")
    parser = MultiFileParser(
        forecast_file=str(forecast_file),
        network_file=str(network_file),
        inventory_file=None,
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Get manufacturing site
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
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

    # 4-week horizon
    start_date = min(entry.forecast_date for entry in forecast.entries)
    end_date = start_date + timedelta(days=27)

    print(f"  Planning horizon: {start_date} to {end_date} (28 days)")
    print(f"  Products: {len(set(e.product_id for e in forecast.entries))}")

    # Create model
    print("\nCreating UnifiedNodeModel...")
    model_instance = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_truck_schedules,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    # Run build 3 times and take average
    build_times = []
    pyomo_model = None
    for i in range(3):
        print(f"\nBuild #{i+1}/3...")
        build_start = time.time()
        pyomo_model = model_instance.build_model()
        build_time = time.time() - build_start
        build_times.append(build_time)
        print(f"  Build time: {build_time:.3f}s")

    avg_build_time = sum(build_times) / len(build_times)
    min_build_time = min(build_times)
    max_build_time = max(build_times)

    # Store model in instance for get_model_statistics()
    model_instance.model = pyomo_model

    # Get model statistics using new method
    print("\nGetting model statistics using get_model_statistics()...")
    stats = model_instance.get_model_statistics()

    print(f"\n{'='*70}")
    print("OPTIMIZED MODEL BUILD TIME RESULTS")
    print(f"{'='*70}")
    print(f"\nBuild Time:")
    print(f"  Average: {avg_build_time:.3f}s (over 3 runs)")
    print(f"  Min:     {min_build_time:.3f}s")
    print(f"  Max:     {max_build_time:.3f}s")

    print(f"\nModel Statistics (from get_model_statistics()):")
    print(f"  Total variables:     {stats['num_variables']:,}")
    print(f"    - Binary:          {stats['num_binary_vars']:,}")
    print(f"    - Integer:         {stats['num_integer_vars']:,}")
    print(f"    - Continuous:      {stats['num_continuous_vars']:,}")
    print(f"  Total constraints:   {stats['num_constraints']:,}")

    print(f"\n{'='*70}")
    print("COMPARISON TO BASELINE")
    print(f"{'='*70}")
    baseline_build_time = 4.44  # From interrupted baseline run
    improvement = ((baseline_build_time - avg_build_time) / baseline_build_time) * 100

    print(f"\nBaseline build time:  {baseline_build_time:.3f}s")
    print(f"Optimized build time: {avg_build_time:.3f}s")
    print(f"Improvement:          {improvement:+.1f}% faster")
    print(f"Time saved:           {baseline_build_time - avg_build_time:.3f}s")

    print(f"\n{'='*70}")
    print("OPTIMIZATIONS APPLIED")
    print(f"{'='*70}")
    print("1. quicksum() in objective function (production, transport, shortage costs)")
    print("2. Pre-built route cost lookup dictionary")
    print("3. Added get_model_statistics() method for monitoring")


if __name__ == "__main__":
    main()
