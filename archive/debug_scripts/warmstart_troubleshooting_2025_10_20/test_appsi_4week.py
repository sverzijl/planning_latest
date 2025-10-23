#!/usr/bin/env python3
"""Test APPSI HiGHS vs legacy HiGHS on 4-week problem."""

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
    print("APPSI HIGHS vs LEGACY HIGHS - 4 WEEK COMPARISON")
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

    print(f"  Planning: {start_date} to {end_date} (28 days)")

    # Test APPSI HiGHS
    print("\n" + "="*70)
    print("TEST 1: APPSI HIGHS (New Interface)")
    print("="*70)

    model_appsi = UnifiedNodeModel(
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

    print("\nSolving with APPSI HiGHS...")
    appsi_start = time.time()
    result_appsi = model_appsi.solve(
        solver_name='appsi_highs',
        time_limit_seconds=120,
        mip_gap=0.01,
        use_warmstart=False,  # Test without warmstart first
        tee=False,
    )
    appsi_time = time.time() - appsi_start

    print(f"\nAPPSI HiGHS Results:")
    print(f"  Status: {result_appsi.termination_condition}")
    print(f"  Time: {appsi_time:.2f}s")
    if result_appsi.objective_value:
        print(f"  Objective: ${result_appsi.objective_value:,.2f}")

    # Test Legacy HiGHS
    print("\n" + "="*70)
    print("TEST 2: LEGACY HIGHS (Old Interface)")
    print("="*70)

    model_legacy = UnifiedNodeModel(
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

    print("\nSolving with Legacy HiGHS...")
    legacy_start = time.time()
    result_legacy = model_legacy.solve(
        solver_name='highs',  # Legacy interface
        time_limit_seconds=120,
        mip_gap=0.01,
        tee=False,
    )
    legacy_time = time.time() - legacy_start

    print(f"\nLegacy HiGHS Results:")
    print(f"  Status: {result_legacy.termination_condition}")
    print(f"  Time: {legacy_time:.2f}s")
    if result_legacy.objective_value:
        print(f"  Objective: ${result_legacy.objective_value:,.2f}")

    # Compare
    print(f"\n{'='*70}")
    print("PERFORMANCE COMPARISON - 4 WEEK HORIZON")
    print(f"{'='*70}")
    print(f"\nAPPSI HiGHS: {appsi_time:.2f}s")
    print(f"Legacy HiGHS: {legacy_time:.2f}s")

    if appsi_time < legacy_time:
        speedup = legacy_time / appsi_time
        print(f"\n🚀 APPSI is {speedup:.2f}x FASTER!")
        print(f"   Time saved: {legacy_time - appsi_time:.2f}s")
    else:
        print(f"\n⚠️  APPSI is {appsi_time / legacy_time:.2f}x slower")

    print(f"\n{'='*70}")
    print("CONCLUSION")
    print(f"{'='*70}")
    print("APPSI HiGHS uses newer, more efficient interface")
    print("Expected benefits:")
    print("  - Better integration with Pyomo")
    print("  - Persistent solver (model updates faster)")
    print("  - Native warmstart support")
    print("  - Generally faster than legacy interface")


if __name__ == "__main__":
    main()
