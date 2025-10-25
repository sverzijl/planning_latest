"""
Benchmark: Solve Time Scaling by Horizon Length

Measures actual solve times for different horizon lengths at various gap tolerances.
This provides EVIDENCE for setting realistic progressive phase time limits.

Tests:
- 1 week at 2% gap (baseline)
- 2 weeks at 2% gap
- 4 weeks at 2% gap
- 8 weeks at 2% gap (if time permits)
- 12 weeks at 40% gap (Phase 1 equivalent)

Purpose: Determine if time limits are realistic or need adjustment.
"""

from datetime import date, timedelta
from pathlib import Path
import time

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from tests.conftest import create_test_products


def load_base_data():
    """Load data for benchmarking."""
    forecast_file = Path('data/examples/Gluten Free Forecast - Latest.xlsm')
    network_file = Path('data/examples/Network_Config.xlsx')

    parser = MultiFileParser(forecast_file=forecast_file, network_file=network_file)
    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
        production_rate=getattr(manuf_loc, 'production_rate', 1400.0),
        daily_startup_hours=0.5, daily_shutdown_hours=0.25, default_changeover_hours=0.5,
        production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    start_date = min(e.forecast_date for e in forecast.entries)

    converter = LegacyToUnifiedConverter()

    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    return {
        'forecast': forecast,
        'locations': locations,
        'manufacturing_site': manufacturing_site,
        'routes': routes,
        'labor_calendar': labor_calendar,
        'truck_schedules_list': truck_schedules_list,
        'cost_structure': cost_structure,
        'products': products,
        'start_date': start_date,
        'converter': converter,
    }


def benchmark_horizon(data, weeks, gap, time_limit_seconds):
    """Benchmark solve time for given horizon."""

    start_date = data['start_date']
    end_date = start_date + timedelta(days=weeks * 7 - 1)

    print(f"\n{'='*80}")
    print(f"BENCHMARK: {weeks}-week horizon, {gap*100:.0f}% gap, {time_limit_seconds}s limit")
    print(f"{'='*80}")
    print(f"Date range: {start_date} to {end_date}")

    # Convert to unified
    nodes = data['converter'].convert_nodes(data['manufacturing_site'], data['locations'], data['forecast'])
    unified_routes = data['converter'].convert_routes(data['routes'])
    unified_truck_schedules = data['converter'].convert_truck_schedules(
        data['truck_schedules_list'],
        data['manufacturing_site'].id
    )

    # Build model
    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=data['forecast'],
        labor_calendar=data['labor_calendar'],
        cost_structure=data['cost_structure'],
        products=data['products'],
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_truck_schedules,
        use_batch_tracking=True,
        allow_shortages=True,
    )

    # Solve
    print(f"\nSolving...")
    start_time = time.time()

    result = model.solve(
        solver_name='appsi_highs',
        mip_gap=gap,
        time_limit_seconds=time_limit_seconds
    )

    actual_time = time.time() - start_time

    # Report
    print(f"\nResults:")
    print(f"  Status: {result.termination_condition}")
    print(f"  Objective: ${result.objective_value:,.2f}")
    print(f"  Solve time: {actual_time:.1f}s")
    print(f"  Success: {result.success}")

    if hasattr(result, 'gap') and result.gap:
        print(f"  Final gap: {result.gap*100:.2f}%")

    return {
        'weeks': weeks,
        'gap_target': gap,
        'time_limit': time_limit_seconds,
        'actual_time': actual_time,
        'objective': result.objective_value,
        'status': str(result.termination_condition),
        'success': result.success,
    }


def main():
    """Run scaling benchmark."""

    print("="*80)
    print("SOLVE TIME SCALING BENCHMARK")
    print("="*80)
    print("\nPurpose: Determine realistic time limits for progressive phases")
    print("Weekend capacity: NOW BOUNDED at 14h (to match weekdays)")

    data = load_base_data()

    results = []

    # Benchmark 1: 1 week at 2% gap
    results.append(benchmark_horizon(data, weeks=1, gap=0.02, time_limit_seconds=180))

    # Benchmark 2: 2 weeks at 2% gap
    results.append(benchmark_horizon(data, weeks=2, gap=0.02, time_limit_seconds=300))

    # Benchmark 3: 4 weeks at 2% gap
    results.append(benchmark_horizon(data, weeks=4, gap=0.02, time_limit_seconds=400))

    # Benchmark 4: 8 weeks at 10% gap (looser for longer horizon)
    results.append(benchmark_horizon(data, weeks=8, gap=0.10, time_limit_seconds=500))

    # Benchmark 5: 12 weeks at 40% gap (Phase 1 equivalent)
    results.append(benchmark_horizon(data, weeks=12, gap=0.40, time_limit_seconds=600))

    # Summary
    print("\n" + "="*80)
    print("SCALING SUMMARY")
    print("="*80)

    for r in results:
        status_mark = "✓" if r['success'] else "✗"
        time_mark = "⏱" if "maxTimeLimit" in r['status'] else "✓"

        print(f"\n{r['weeks']:2d} weeks @ {r['gap_target']*100:3.0f}% gap:")
        print(f"  {status_mark} Time: {r['actual_time']:6.1f}s {time_mark}")
        print(f"     Objective: ${r['objective']:,.2f}")
        print(f"     Status: {r['status']}")

    # Calculate recommended time limits
    print("\n" + "="*80)
    print("RECOMMENDED PROGRESSIVE TIME LIMITS")
    print("="*80)

    # Find actual times for each horizon
    time_1w = next((r['actual_time'] for r in results if r['weeks'] == 1), None)
    time_4w = next((r['actual_time'] for r in results if r['weeks'] == 4), None)
    time_8w = next((r['actual_time'] for r in results if r['weeks'] == 8), None)
    time_12w = next((r['actual_time'] for r in results if r['weeks'] == 12), None)

    if time_12w:
        print(f"\nPhase 1 (12w, 40% gap): {int(time_12w * 1.5)}s (actual: {time_12w:.0f}s + 50% buffer)")
    if time_8w:
        print(f"Phase 2 (8w, 15% gap):  {int(time_8w * 1.5)}s (actual: {time_8w:.0f}s + 50% buffer)")
    if time_4w:
        print(f"Phase 3 (4w, 3% gap):   {int(time_4w * 1.5)}s (actual: {time_4w:.0f}s + 50% buffer)")
    if time_1w:
        print(f"Phase 4 (1w, 0.5% gap): {int(time_1w * 1.5)}s (actual: {time_1w:.0f}s + 50% buffer)")

    print("\n" + "="*80)


if __name__ == '__main__':
    main()
