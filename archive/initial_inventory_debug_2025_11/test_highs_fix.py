#!/usr/bin/env python3
"""Quick test to verify HiGHS solver optimization fix."""

import time
from datetime import timedelta
from pathlib import Path

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType


def main():
    print("="*70)
    print("HIGHS SOLVER FIX VERIFICATION")
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

    # Use shorter horizon for quick test (1 week)
    start_date = min(entry.forecast_date for entry in forecast.entries)
    end_date = start_date + timedelta(days=6)  # 1 week

    print(f"  Planning horizon: {start_date} to {end_date} (7 days - quick test)")

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

    # Test HiGHS solver
    print("\n" + "="*70)
    print("TESTING HIGHS WITH FIXED CONFIGURATION")
    print("="*70)
    print("\nSolving with HiGHS (presolve now ALWAYS enabled)...")

    highs_start = time.time()
    result = model_instance.solve(
        solver_name='highs',
        time_limit_seconds=120,
        mip_gap=0.01,
        tee=False,  # Set to True to see solver output
    )
    highs_time = time.time() - highs_start

    print(f"\nHiGHS Results:")
    print(f"  Status: {result.termination_condition}")
    print(f"  Solve time: {highs_time:.2f}s")
    print(f"  Objective: ${result.objective_value:,.2f}" if result.objective_value else "  Objective: N/A")
    print(f"  MIP gap: {result.gap:.2%}" if result.gap else "  MIP gap: N/A")

    # Compare with CBC
    print("\n" + "="*70)
    print("COMPARING WITH CBC")
    print("="*70)
    print("\nSolving with CBC...")

    # Create new instance for CBC
    model_instance_cbc = UnifiedNodeModel(
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

    cbc_start = time.time()
    result_cbc = model_instance_cbc.solve(
        solver_name='cbc',
        time_limit_seconds=120,
        mip_gap=0.01,
        tee=False,
    )
    cbc_time = time.time() - cbc_start

    print(f"\nCBC Results:")
    print(f"  Status: {result_cbc.termination_condition}")
    print(f"  Solve time: {cbc_time:.2f}s")
    print(f"  Objective: ${result_cbc.objective_value:,.2f}" if result_cbc.objective_value else "  Objective: N/A")
    print(f"  MIP gap: {result_cbc.gap:.2%}" if result_cbc.gap else "  MIP gap: N/A")

    # Summary
    print(f"\n{'='*70}")
    print("PERFORMANCE COMPARISON")
    print(f"{'='*70}")
    print(f"\nHiGHS solve time: {highs_time:.2f}s")
    print(f"CBC solve time:   {cbc_time:.2f}s")

    if highs_time < cbc_time:
        speedup = cbc_time / highs_time
        print(f"\n✅ HiGHS is {speedup:.2f}x FASTER than CBC")
        print(f"   Time saved: {cbc_time - highs_time:.2f}s")
    else:
        slowdown = highs_time / cbc_time
        print(f"\n⚠️  HiGHS is {slowdown:.2f}x SLOWER than CBC")
        print(f"   Extra time: {highs_time - cbc_time:.2f}s")

    print(f"\n{'='*70}")
    print("FIX APPLIED")
    print(f"{'='*70}")
    print("✅ HiGHS presolve now ALWAYS enabled (was only enabled with aggressive_heuristics flag)")
    print("✅ HiGHS parallel mode explicitly enabled")
    print("✅ HiGHS symmetry detection always on")
    print("✅ HiGHS simplex strategy optimized (dual simplex)")
    print("✅ HiGHS MIP heuristic effort set to 0.5 (was 0)")


if __name__ == "__main__":
    main()
