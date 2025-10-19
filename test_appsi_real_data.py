#!/usr/bin/env python3
"""Test APPSI HiGHS with user's real data."""

import time
from datetime import timedelta
from pathlib import Path

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType


def main():
    print("="*80)
    print("APPSI HIGHS vs CBC - REAL USER DATA (4-WEEK)")
    print("="*80)

    data_dir = Path("data/examples")
    forecast_file = data_dir / "Gfree Forecast.xlsm"
    network_file = data_dir / "Network_Config.xlsx"
    inventory_file = data_dir / "inventory_latest.XLSX"

    print(f"\nLoading data...")
    parser = MultiFileParser(
        forecast_file=str(forecast_file),
        network_file=str(network_file),
        inventory_file=str(inventory_file),
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()
    inventory_snapshot = parser.parse_inventory(snapshot_date=None)

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
        production_rate=getattr(manuf_loc, 'production_rate', 1400.0),
        daily_startup_hours=0.5, daily_shutdown_hours=0.25,
        default_changeover_hours=0.5,
        production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    start_date = inventory_snapshot.snapshot_date
    end_date = start_date + timedelta(days=27)
    inv_dict = inventory_snapshot.to_optimization_dict()

    print(f"  Planning: {start_date} to {end_date}")

    # Test APPSI HiGHS
    print("\n" + "="*80)
    print("TEST: APPSI HIGHS")
    print("="*80)

    model_appsi = UnifiedNodeModel(
        nodes=nodes, routes=unified_routes, forecast=forecast,
        labor_calendar=labor_calendar, cost_structure=cost_structure,
        start_date=start_date, end_date=end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=inv_dict,
        inventory_snapshot_date=inventory_snapshot.snapshot_date,
        use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
    )

    print("\nSolving with APPSI HiGHS (5% gap, 120s limit)...")
    appsi_start = time.time()
    result_appsi = model_appsi.solve(
        solver_name='appsi_highs',
        time_limit_seconds=120,
        mip_gap=0.05,
        use_warmstart=False,
        tee=False,
    )
    appsi_time = time.time() - appsi_start

    print(f"\nAPPSI HiGHS Results:")
    print(f"  Status: {result_appsi.termination_condition}")
    print(f"  Time: {appsi_time:.2f}s")
    if result_appsi.objective_value:
        print(f"  Objective: ${result_appsi.objective_value:,.2f}")

    # Compare
    print(f"\n{'='*80}")
    print("SOLVER COMPARISON - REAL DATA, 4-WEEK HORIZON")
    print(f"{'='*80}")
    print(f"CBC (from previous test):  64.54s")
    print(f"APPSI HiGHS:               {appsi_time:.2f}s")

    if appsi_time < 64.54:
        speedup = 64.54 / appsi_time
        print(f"\n✅ APPSI HiGHS is {speedup:.2f}x FASTER than CBC")
        print(f"   Time saved: {64.54 - appsi_time:.2f}s")
    else:
        slowdown = appsi_time / 64.54
        print(f"\n⚠️  APPSI HiGHS is {slowdown:.2f}x slower than CBC")
        print(f"   Extra time: {appsi_time - 64.54:.2f}s")

if __name__ == "__main__":
    main()
