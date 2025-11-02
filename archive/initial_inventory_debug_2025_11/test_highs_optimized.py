#!/usr/bin/env python3
"""Test optimized HiGHS configuration with corrected simplex_strategy."""

import time
from datetime import timedelta
from pathlib import Path

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType


def run_test(horizon_days, label):
    """Run HiGHS test with given horizon."""

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

    # Set horizon
    start_date = min(entry.forecast_date for entry in forecast.entries)
    end_date = start_date + timedelta(days=horizon_days - 1)

    print(f"\n{'='*70}")
    print(f"{label}: {horizon_days} days")
    print(f"{'='*70}")
    print(f"Planning: {start_date} to {end_date}")

    # Create and solve with HiGHS
    model = UnifiedNodeModel(
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

    start_time = time.time()
    result = model.solve(
        solver_name='highs',
        time_limit_seconds=120,
        mip_gap=0.01,
        tee=False,
    )
    total_time = time.time() - start_time

    print(f"\nResults:")
    print(f"  Status: {result.termination_condition}")
    print(f"  Total time: {total_time:.2f}s")
    if result.objective_value:
        print(f"  Objective: ${result.objective_value:,.2f}")
    if result.gap:
        print(f"  MIP gap: {result.gap:.2%}")

    return total_time, result


def main():
    print("="*70)
    print("HIGHS OPTIMIZED CONFIGURATION TEST")
    print("="*70)
    print("\nFixes Applied:")
    print("  1. simplex_strategy = 2 (was 4) - Dual SIP parallel simplex")
    print("  2. mip_lp_age_limit = 10 (was 20) - HiGHS default")
    print("  3. Additional heuristics: zi_round, shifting (aggressive mode)")
    print("  4. Aggressive mode: age_limit = 5 (faster cut removal)")

    # Test on increasing horizons
    results = []

    for days, label in [(7, "1-week"), (14, "2-week"), (28, "4-week")]:
        try:
            solve_time, result = run_test(days, label)
            results.append((label, days, solve_time, result))
        except KeyboardInterrupt:
            print("\n\nTest interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            continue

    # Summary
    print(f"\n{'='*70}")
    print("PERFORMANCE SUMMARY")
    print(f"{'='*70}")

    for label, days, solve_time, result in results:
        gap_str = f"{result.gap:.2%}" if result.gap else "N/A"
        status_str = "✅" if result.is_optimal() else "⚠️"
        print(f"{status_str} {label:8s}: {solve_time:6.2f}s  (gap: {gap_str})")

    # Expected performance
    print(f"\n{'='*70}")
    print("EXPECTED PERFORMANCE (with fixes)")
    print(f"{'='*70}")
    print("  1-week:  < 5s   (was ~2.2s with wrong config)")
    print("  2-week:  < 20s  (should be faster now)")
    print("  4-week:  < 60s  (should be MUCH faster than 190s)")


if __name__ == "__main__":
    main()
