#!/usr/bin/env python3
"""Test APPSI HiGHS with warmstart on production planning model."""

import time
from datetime import timedelta
from pathlib import Path

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType


def load_data():
    """Load test data."""
    data_dir = Path("data/examples")
    forecast_file = data_dir / "Gfree Forecast.xlsm"
    network_file = data_dir / "Network_Config.xlsx"

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

    return {
        'nodes': nodes,
        'routes': unified_routes,
        'forecast': forecast,
        'labor_calendar': labor_calendar,
        'truck_schedules': unified_truck_schedules,
        'cost_structure': cost_structure,
    }


def test_horizon(data, horizon_days, label):
    """Test a specific horizon."""
    start_date = min(entry.forecast_date for entry in data['forecast'].entries)
    end_date = start_date + timedelta(days=horizon_days - 1)

    print(f"\n{'='*70}")
    print(f"{label} ({horizon_days} days): {start_date} to {end_date}")
    print(f"{'='*70}")

    # Test WITHOUT warmstart
    print("\nTest 1: APPSI HiGHS WITHOUT warmstart")
    model1 = UnifiedNodeModel(
        nodes=data['nodes'],
        routes=data['routes'],
        forecast=data['forecast'],
        labor_calendar=data['labor_calendar'],
        cost_structure=data['cost_structure'],
        start_date=start_date,
        end_date=end_date,
        truck_schedules=data['truck_schedules'],
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    start = time.time()
    result1 = model1.solve(
        solver_name='appsi_highs',
        time_limit_seconds=120,
        mip_gap=0.01,
        use_warmstart=False,  # NO WARMSTART
        tee=False,
    )
    time1 = time.time() - start

    print(f"  Status: {result1.termination_condition}")
    print(f"  Time: {time1:.2f}s")
    if result1.objective_value:
        print(f"  Objective: ${result1.objective_value:,.2f}")

    # Test WITH warmstart
    print("\nTest 2: APPSI HiGHS WITH warmstart")
    model2 = UnifiedNodeModel(
        nodes=data['nodes'],
        routes=data['routes'],
        forecast=data['forecast'],
        labor_calendar=data['labor_calendar'],
        cost_structure=data['cost_structure'],
        start_date=start_date,
        end_date=end_date,
        truck_schedules=data['truck_schedules'],
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    start = time.time()
    result2 = model2.solve(
        solver_name='appsi_highs',
        time_limit_seconds=120,
        mip_gap=0.01,
        use_warmstart=True,  # WITH WARMSTART!
        tee=False,
    )
    time2 = time.time() - start

    print(f"  Status: {result2.termination_condition}")
    print(f"  Time: {time2:.2f}s")
    if result2.objective_value:
        print(f"  Objective: ${result2.objective_value:,.2f}")

    # Compare
    if time1 > 0 and time2 > 0:
        speedup = time1 / time2
        improvement = ((time1 - time2) / time1) * 100
        print(f"\n🚀 Warmstart Result:")
        if speedup > 1.0:
            print(f"  {improvement:.1f}% FASTER ({speedup:.2f}x speedup)")
            print(f"  Time saved: {time1 - time2:.2f}s")
        else:
            print(f"  {-improvement:.1f}% slower (warmstart didn't help)")

    return time1, time2, result1, result2


def main():
    print("="*70)
    print("APPSI HIGHS WARMSTART TEST - PRODUCTION PLANNING MODEL")
    print("="*70)
    print("\nThis tests the new APPSI HiGHS interface (Pyomo 6.9.1+)")
    print("which supports warmstart for MASSIVE performance gains!")

    data = load_data()

    results = []

    # Test on 1-week first (fast)
    print("\n" + "="*70)
    print("QUICK TEST: 1-WEEK HORIZON")
    print("="*70)
    try:
        time_no_ws, time_ws, r1, r2 = test_horizon(data, 7, "1-week")
        results.append(('1-week', time_no_ws, time_ws))
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    # Summary
    if results:
        print(f"\n{'='*70}")
        print("WARMSTART PERFORMANCE SUMMARY")
        print(f"{'='*70}")
        for label, t_no, t_yes in results:
            speedup = t_no / t_yes if t_yes > 0 else 0
            saved = t_no - t_yes
            print(f"{label:8s}: {t_no:6.2f}s → {t_yes:6.2f}s  ({speedup:.2f}x speedup, {saved:.2f}s saved)")


if __name__ == "__main__":
    main()
