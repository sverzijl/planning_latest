#!/usr/bin/env python3
"""Warmstart Performance Benchmark Script.

This standalone script compares solve performance between:
1. BASELINE: Binary product_produced variables WITHOUT warmstart
2. WARMSTART: Binary product_produced variables WITH warmstart hints

Purpose:
- Measure warmstart effectiveness on real production data
- Quantify speedup from campaign-based production patterns
- Validate warmstart doesn't degrade solution quality

Usage:
    python scripts/benchmark_warmstart_performance.py

Output:
- Console: Formatted comparison table
- File: benchmark_results.txt with detailed metrics
"""

import sys
import time
from datetime import date, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from src.models.truck_schedule import TruckScheduleCollection


def load_data():
    """Load real data files for benchmarking."""
    data_dir = project_root / "data" / "examples"

    forecast_file = data_dir / "Gfree Forecast.xlsm"
    network_file = data_dir / "Network_Config.xlsx"
    inventory_file = data_dir / "inventory.xlsx"

    # Verify files exist
    if not forecast_file.exists():
        raise FileNotFoundError(f"Forecast file not found: {forecast_file}")
    if not network_file.exists():
        raise FileNotFoundError(f"Network file not found: {network_file}")

    # Parse data
    parser = MultiFileParser(
        forecast_file=str(forecast_file),
        network_file=str(network_file),
        inventory_file=str(inventory_file) if inventory_file.exists() else None,
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Extract manufacturing site
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    if not manufacturing_locations:
        raise ValueError("No manufacturing site found in locations")

    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id,
        name=manuf_loc.name,
        storage_mode=manuf_loc.storage_mode,
        production_rate=manuf_loc.production_rate if hasattr(manuf_loc, 'production_rate') and manuf_loc.production_rate else 1400.0,
        daily_startup_hours=0.5,
        daily_shutdown_hours=0.25,
        default_changeover_hours=0.5,
        production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    # Parse initial inventory
    initial_inventory = None
    inventory_snapshot_date = None
    if inventory_file.exists():
        inventory_snapshot = parser.parse_inventory(snapshot_date=None)
        initial_inventory = inventory_snapshot
        inventory_snapshot_date = inventory_snapshot.snapshot_date

    # Convert to unified format
    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    return {
        'forecast': forecast,
        'nodes': nodes,
        'unified_routes': unified_routes,
        'unified_truck_schedules': unified_truck_schedules,
        'labor_calendar': labor_calendar,
        'cost_structure': cost_structure,
        'initial_inventory': initial_inventory,
        'inventory_snapshot_date': inventory_snapshot_date,
    }


def run_baseline_test(data, start_date, end_date):
    """Run baseline test WITHOUT warmstart."""
    print("\n" + "=" * 80)
    print("TEST 1: BASELINE (Binary product_produced WITHOUT warmstart)")
    print("=" * 80)

    model = UnifiedNodeModel(
        nodes=data['nodes'],
        routes=data['unified_routes'],
        forecast=data['forecast'],
        labor_calendar=data['labor_calendar'],
        cost_structure=data['cost_structure'],
        start_date=start_date,
        end_date=end_date,
        truck_schedules=data['unified_truck_schedules'],
        initial_inventory=data['initial_inventory'].to_optimization_dict() if data['initial_inventory'] else None,
        inventory_snapshot_date=data['inventory_snapshot_date'],
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    start = time.time()
    result = model.solve(
        solver_name='cbc',
        use_warmstart=False,  # NO WARMSTART
        time_limit_seconds=300,
        mip_gap=0.01,
        tee=False,
    )
    solve_time = time.time() - start

    solution = model.get_solution()

    print(f"Status:         {result.termination_condition}")
    print(f"Solve time:     {solve_time:.1f}s")
    print(f"Objective:      ${result.objective_value:,.2f}")
    print(f"MIP gap:        {result.gap * 100:.2f}%" if result.gap else "N/A")

    # Extract metrics
    production_by_date_product = solution.get('production_by_date_product', {})
    total_production = sum(production_by_date_product.values())
    total_shortage = solution.get('total_shortage_units', 0)

    demand_in_horizon = sum(
        e.quantity for e in data['forecast'].entries
        if start_date <= e.forecast_date <= end_date
    )
    fill_rate = 100 * (1 - total_shortage / demand_in_horizon) if demand_in_horizon > 0 else 100

    print(f"Production:     {total_production:,.0f} units")
    print(f"Demand:         {demand_in_horizon:,.0f} units")
    print(f"Fill rate:      {fill_rate:.1f}%")

    return {
        'status': result.termination_condition,
        'solve_time': solve_time,
        'objective': result.objective_value,
        'gap': result.gap,
        'production': total_production,
        'demand': demand_in_horizon,
        'shortage': total_shortage,
        'fill_rate': fill_rate,
    }


def run_warmstart_test(data, start_date, end_date):
    """Run warmstart test WITH campaign hints."""
    print("\n" + "=" * 80)
    print("TEST 2: WARMSTART (Binary product_produced WITH campaign hints)")
    print("=" * 80)

    model = UnifiedNodeModel(
        nodes=data['nodes'],
        routes=data['unified_routes'],
        forecast=data['forecast'],
        labor_calendar=data['labor_calendar'],
        cost_structure=data['cost_structure'],
        start_date=start_date,
        end_date=end_date,
        truck_schedules=data['unified_truck_schedules'],
        initial_inventory=data['initial_inventory'].to_optimization_dict() if data['initial_inventory'] else None,
        inventory_snapshot_date=data['inventory_snapshot_date'],
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    start = time.time()
    result = model.solve(
        solver_name='cbc',
        use_warmstart=True,  # ENABLE WARMSTART
        time_limit_seconds=300,
        mip_gap=0.01,
        tee=False,
    )
    solve_time = time.time() - start

    solution = model.get_solution()

    print(f"Status:         {result.termination_condition}")
    print(f"Solve time:     {solve_time:.1f}s")
    print(f"Objective:      ${result.objective_value:,.2f}")
    print(f"MIP gap:        {result.gap * 100:.2f}%" if result.gap else "N/A")

    # Extract metrics
    production_by_date_product = solution.get('production_by_date_product', {})
    total_production = sum(production_by_date_product.values())
    total_shortage = solution.get('total_shortage_units', 0)

    demand_in_horizon = sum(
        e.quantity for e in data['forecast'].entries
        if start_date <= e.forecast_date <= end_date
    )
    fill_rate = 100 * (1 - total_shortage / demand_in_horizon) if demand_in_horizon > 0 else 100

    print(f"Production:     {total_production:,.0f} units")
    print(f"Demand:         {demand_in_horizon:,.0f} units")
    print(f"Fill rate:      {fill_rate:.1f}%")

    return {
        'status': result.termination_condition,
        'solve_time': solve_time,
        'objective': result.objective_value,
        'gap': result.gap,
        'production': total_production,
        'demand': demand_in_horizon,
        'shortage': total_shortage,
        'fill_rate': fill_rate,
    }


def print_comparison(baseline, warmstart):
    """Print formatted comparison table."""
    print("\n" + "=" * 80)
    print("PERFORMANCE COMPARISON")
    print("=" * 80)
    print(f"{'Metric':<25} {'Baseline':>15} {'Warmstart':>15} {'Difference':>20}")
    print("-" * 80)

    # Solve time
    time_diff = warmstart['solve_time'] - baseline['solve_time']
    time_diff_pct = (time_diff / baseline['solve_time']) * 100 if baseline['solve_time'] > 0 else 0
    print(f"{'Solve time (s)':<25} {baseline['solve_time']:>15.1f} {warmstart['solve_time']:>15.1f} {time_diff:>15.1f}s ({time_diff_pct:+.1f}%)")

    # Objective
    obj_diff = warmstart['objective'] - baseline['objective']
    obj_diff_pct = (obj_diff / baseline['objective']) * 100 if baseline['objective'] > 0 else 0
    print(f"{'Objective ($)':<25} {baseline['objective']:>15,.2f} {warmstart['objective']:>15,.2f} ${obj_diff:>15,.2f} ({obj_diff_pct:+.1f}%)")

    # Gap
    baseline_gap_pct = baseline['gap'] * 100 if baseline['gap'] else 0
    warmstart_gap_pct = warmstart['gap'] * 100 if warmstart['gap'] else 0
    gap_diff = warmstart_gap_pct - baseline_gap_pct
    print(f"{'MIP gap (%)':<25} {baseline_gap_pct:>15.2f} {warmstart_gap_pct:>15.2f} {gap_diff:>20.2f}%")

    # Fill rate
    fill_diff = warmstart['fill_rate'] - baseline['fill_rate']
    print(f"{'Fill rate (%)':<25} {baseline['fill_rate']:>15.1f} {warmstart['fill_rate']:>15.1f} {fill_diff:>20.1f}%")

    print("-" * 80)

    # Speedup summary
    if warmstart['solve_time'] < baseline['solve_time']:
        speedup_pct = ((baseline['solve_time'] - warmstart['solve_time']) / baseline['solve_time']) * 100
        print(f"\nWARMSTART SPEEDUP: {speedup_pct:.1f}%")
        print(f"Time saved: {baseline['solve_time'] - warmstart['solve_time']:.1f}s")
        print("✅ WARMSTART EFFECTIVE")
    else:
        slowdown_pct = ((warmstart['solve_time'] - baseline['solve_time']) / baseline['solve_time']) * 100
        print(f"\nWARMSTART SLOWDOWN: {slowdown_pct:.1f}%")
        print(f"Time penalty: {warmstart['solve_time'] - baseline['solve_time']:.1f}s")
        print("⚠️  WARMSTART INEFFECTIVE")

    print("=" * 80)


def save_results(baseline, warmstart, output_file):
    """Save benchmark results to file."""
    with open(output_file, 'w') as f:
        f.write("WARMSTART PERFORMANCE BENCHMARK RESULTS\n")
        f.write("=" * 80 + "\n")
        f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Planning horizon: 4 weeks (28 days)\n")
        f.write(f"Solver: CBC\n")
        f.write(f"MIP gap tolerance: 1%\n")
        f.write(f"Time limit: 300s\n\n")

        f.write("BASELINE TEST (WITHOUT warmstart)\n")
        f.write("-" * 80 + "\n")
        f.write(f"Status:         {baseline['status']}\n")
        f.write(f"Solve time:     {baseline['solve_time']:.1f}s\n")
        f.write(f"Objective:      ${baseline['objective']:,.2f}\n")
        f.write(f"MIP gap:        {baseline['gap']*100:.2f}%\n" if baseline['gap'] else "MIP gap:        N/A\n")
        f.write(f"Production:     {baseline['production']:,.0f} units\n")
        f.write(f"Demand:         {baseline['demand']:,.0f} units\n")
        f.write(f"Fill rate:      {baseline['fill_rate']:.1f}%\n\n")

        f.write("WARMSTART TEST (WITH campaign hints)\n")
        f.write("-" * 80 + "\n")
        f.write(f"Status:         {warmstart['status']}\n")
        f.write(f"Solve time:     {warmstart['solve_time']:.1f}s\n")
        f.write(f"Objective:      ${warmstart['objective']:,.2f}\n")
        f.write(f"MIP gap:        {warmstart['gap']*100:.2f}%\n" if warmstart['gap'] else "MIP gap:        N/A\n")
        f.write(f"Production:     {warmstart['production']:,.0f} units\n")
        f.write(f"Demand:         {warmstart['demand']:,.0f} units\n")
        f.write(f"Fill rate:      {warmstart['fill_rate']:.1f}%\n\n")

        f.write("COMPARISON\n")
        f.write("=" * 80 + "\n")

        time_diff = warmstart['solve_time'] - baseline['solve_time']
        time_diff_pct = (time_diff / baseline['solve_time']) * 100 if baseline['solve_time'] > 0 else 0
        f.write(f"Solve time difference:     {time_diff:+.1f}s ({time_diff_pct:+.1f}%)\n")

        obj_diff = warmstart['objective'] - baseline['objective']
        obj_diff_pct = (obj_diff / baseline['objective']) * 100 if baseline['objective'] > 0 else 0
        f.write(f"Objective difference:      ${obj_diff:+,.2f} ({obj_diff_pct:+.1f}%)\n")

        fill_diff = warmstart['fill_rate'] - baseline['fill_rate']
        f.write(f"Fill rate difference:      {fill_diff:+.1f}%\n\n")

        if warmstart['solve_time'] < baseline['solve_time']:
            speedup_pct = ((baseline['solve_time'] - warmstart['solve_time']) / baseline['solve_time']) * 100
            f.write(f"WARMSTART SPEEDUP: {speedup_pct:.1f}%\n")
            f.write(f"Time saved: {baseline['solve_time'] - warmstart['solve_time']:.1f}s\n")
            f.write("✅ WARMSTART EFFECTIVE\n")
        else:
            slowdown_pct = ((warmstart['solve_time'] - baseline['solve_time']) / baseline['solve_time']) * 100
            f.write(f"WARMSTART SLOWDOWN: {slowdown_pct:.1f}%\n")
            f.write(f"Time penalty: {warmstart['solve_time'] - baseline['solve_time']:.1f}s\n")
            f.write("⚠️  WARMSTART INEFFECTIVE\n")

    print(f"\n✓ Results saved to: {output_file}")


def main():
    """Run warmstart performance benchmark."""
    print("=" * 80)
    print("WARMSTART PERFORMANCE BENCHMARK")
    print("=" * 80)
    print("Comparing solve performance with and without warmstart hints")
    print("Configuration: 4-week horizon, CBC solver, 1% MIP gap, 300s time limit")
    print("=" * 80)

    # Load data
    print("\nLoading data files...")
    data = load_data()
    print(f"✓ Data loaded successfully")
    print(f"  Forecast entries: {len(data['forecast'].entries)}")
    print(f"  Nodes: {len(data['nodes'])}")
    print(f"  Routes: {len(data['unified_routes'])}")

    # Set planning horizon
    if data['inventory_snapshot_date']:
        start_date = data['inventory_snapshot_date']
    else:
        start_date = min(e.forecast_date for e in data['forecast'].entries)
    end_date = start_date + timedelta(weeks=4)

    print(f"\nPlanning horizon: {start_date} to {end_date} (28 days)")

    # Run baseline test
    baseline_results = run_baseline_test(data, start_date, end_date)

    # Run warmstart test
    warmstart_results = run_warmstart_test(data, start_date, end_date)

    # Print comparison
    print_comparison(baseline_results, warmstart_results)

    # Save results
    output_file = project_root / "benchmark_results.txt"
    save_results(baseline_results, warmstart_results, output_file)

    print("\n✓ Benchmark complete")


if __name__ == "__main__":
    main()
