#!/usr/bin/env python3
"""
Benchmark script with correct date alignment to forecast data.

Tests 1-week, 2-week, and 4-week horizons starting from the actual forecast start date.
Verifies that solutions are realistic with actual demand.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from tests.conftest import create_test_products


def format_time(seconds):
    """Format seconds as human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    else:
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins}m {secs:.1f}s"


def analyze_solution(model):
    """Analyze the solution to verify it's realistic."""
    # Get objective value
    import pyomo.environ as pyo
    obj_value = 0
    for obj in model.model.component_data_objects(ctype=pyo.Objective, active=True):
        obj_value = pyo.value(obj)
        break

    analysis = {
        'total_production': 0,
        'total_mixes': 0,
        'total_changeovers': 0,
        'production_days': 0,
        'products_produced': set(),
        'objective_value': obj_value,
    }

    # Count production
    import pyomo.environ as pyo
    for var in model.model.component_data_objects(ctype=pyo.Var):
        if not var.is_indexed():
            name = var.name
            value = pyo.value(var)

            if value and value > 0.01:
                if 'production[' in name:
                    analysis['total_production'] += value
                elif 'mix_count[' in name:
                    analysis['total_mixes'] += value
                    # Extract product from variable name
                    # Format: mix_count[node,date,product]
                    parts = name.split('[')[1].rstrip(']').split(',')
                    if len(parts) >= 3:
                        product = parts[2]
                        analysis['products_produced'].add(product)
                elif 'product_produced[' in name:
                    # Binary variable indicating production on a day
                    analysis['production_days'] += value
                elif 'start_production[' in name:
                    # Tracks product startups (0→1 transitions)
                    analysis['total_changeovers'] += value

    return analysis


def run_benchmark(horizon_name, start_date, end_date):
    """Run a single benchmark test."""
    print(f"\n{'='*80}")
    print(f"BENCHMARK: {horizon_name}")
    print(f"Date Range: {start_date} to {end_date}")
    print(f"{'='*80}\n")

    # Load data
    print("Loading data...")
    forecast_file = Path(__file__).parent / "data" / "examples" / "Gfree Forecast.xlsm"
    network_file = Path(__file__).parent / "data" / "examples" / "Network_Config.xlsx"

    parser = MultiFileParser(
        forecast_file=str(forecast_file),
        network_file=str(network_file)
    )

    # Parse data
    forecast, locations, routes, labor_calendar, truck_schedules, cost_structure = parser.parse_all()

    # Count demand entries
    demand_count = 0
    total_demand = 0
    for entry in forecast.entries:
        entry_date = entry.forecast_date
        if hasattr(entry_date, 'date'):
            entry_date = entry_date.date()
        if start_date <= entry_date <= end_date:
            demand_count += 1
            total_demand += entry.quantity

    print(f"Demand entries in range: {demand_count}")
    print(f"Total demand: {total_demand:,.0f} units\n")

    if demand_count == 0:
        print("WARNING: No demand in date range!")
        return None

    # Find manufacturing site and create ManufacturingSite object
    manufacturing_site = None
    for loc in locations:
        if loc.type == 'manufacturing':
            manufacturing_site = ManufacturingSite(
                id=loc.id,
                name=loc.name,
                type=loc.type,
                storage_mode=loc.storage_mode,
                capacity=loc.capacity,
                latitude=loc.latitude,
                longitude=loc.longitude,
                production_rate=1400.0
            )
            break

    if not manufacturing_site:
        print("ERROR: No manufacturing site found!")
        return None

    # Convert legacy data to unified format
    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules, manufacturing_site.id)

    # Create products for model (extract unique product IDs from forecast)
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    # Create and solve model
    print("Building optimization model...")
    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_truck_schedules,
        use_batch_tracking=True,
        allow_shortages=True,  # Allow shortages to debug infeasibility
        enforce_shelf_life=True,
    )

    # Solve
    print("\nSolving with APPSI HiGHS...")
    print(f"Start time: {datetime.now().strftime('%H:%M:%S')}\n")

    start_time = time.time()
    results = model.solve(
        solver_name='appsi_highs',
        time_limit_seconds=300,
        mip_gap=0.01,
        tee=True  # Show solver output
    )
    solve_time = time.time() - start_time

    # Now count variables from the built model
    import pyomo.environ as pyo
    continuous_vars = 0
    integer_vars = 0
    binary_vars = 0

    for var in model.model.component_data_objects(ctype=pyo.Var):
        if var.is_binary():
            binary_vars += 1
        elif var.is_integer():
            integer_vars += 1
        else:
            continuous_vars += 1

    constraints = sum(1 for _ in model.model.component_data_objects(ctype=pyo.Constraint))

    print(f"\nSolve completed in {format_time(solve_time)}")
    print(f"Termination condition: {results.termination_condition}\n")

    # Analyze solution
    if results.is_optimal() or results.is_feasible():
        print("Analyzing solution...")
        analysis = analyze_solution(model)

        print(f"\nSOLUTION ANALYSIS:")
        print(f"  Objective value (total cost): ${analysis['objective_value']:,.2f}")
        print(f"  Total production: {analysis['total_production']:,.0f} units")
        print(f"  Total mixes: {analysis['total_mixes']:.1f}")
        print(f"  Products produced: {len(analysis['products_produced'])}")
        print(f"  Production days: {analysis['production_days']:.1f}")
        print(f"  Total changeovers: {analysis['total_changeovers']:.1f}")

        # Calculate production per mix
        if analysis['total_mixes'] > 0:
            units_per_mix = analysis['total_production'] / analysis['total_mixes']
            print(f"  Units per mix: {units_per_mix:.1f}")

            # Check if mix count looks integer
            fractional_part = analysis['total_mixes'] - int(analysis['total_mixes'])
            if fractional_part > 0.01:
                print(f"  WARNING: Mix count is not integer! Fractional part: {fractional_part:.3f}")
            else:
                print(f"  ✓ Mix count is integer")

        # Check production vs demand
        coverage = (analysis['total_production'] / total_demand * 100) if total_demand > 0 else 0
        print(f"  Demand coverage: {coverage:.1f}%")

        if coverage < 99:
            print(f"  WARNING: Production below demand! Shortfall: {total_demand - analysis['total_production']:,.0f} units")
        elif coverage > 101:
            print(f"  Note: Production exceeds demand by {analysis['total_production'] - total_demand:,.0f} units")
        else:
            print(f"  ✓ Production matches demand")

        return {
            'horizon': horizon_name,
            'days': (end_date - start_date).days + 1,
            'solve_time': solve_time,
            'status': str(results.termination_condition),
            'demand_entries': demand_count,
            'total_demand': total_demand,
            'continuous_vars': continuous_vars,
            'integer_vars': integer_vars,
            'binary_vars': binary_vars,
            'total_vars': continuous_vars + integer_vars + binary_vars,
            'constraints': constraints,
            **analysis
        }
    else:
        print(f"ERROR: Solver did not find a solution")
        print(f"Termination: {results.termination_condition}")
        return None


def main():
    """Run all benchmarks."""
    print("="*80)
    print("BENCHMARK WITH DEMAND - Correct Date Alignment")
    print("="*80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Forecast runs from 2025-10-16 to 2027-01-09
    from datetime import date
    forecast_start = date(2025, 10, 16)

    benchmarks = [
        ('1-week', forecast_start, forecast_start + timedelta(days=6)),
        ('2-week', forecast_start, forecast_start + timedelta(days=13)),
        ('4-week', forecast_start, forecast_start + timedelta(days=27)),
    ]

    results = []
    for name, start, end in benchmarks:
        result = run_benchmark(name, start, end)
        if result:
            results.append(result)

    # Summary
    print("\n" + "="*80)
    print("BENCHMARK SUMMARY")
    print("="*80)
    print(f"\n{'Horizon':<10} {'Days':<6} {'Solve Time':<12} {'Total Prod':<15} {'Mixes':<10} {'Changes':<10} {'Status':<12}")
    print("-"*80)

    for r in results:
        print(f"{r['horizon']:<10} {r['days']:<6} {format_time(r['solve_time']):<12} {r['total_production']:>13,.0f}  {r['total_mixes']:>8.1f}  {r['total_changeovers']:>8.1f}  {r['status']:<12}")

    print("\n" + "="*80)
    print("VARIABLE COUNTS")
    print("="*80)
    print(f"\n{'Horizon':<10} {'Continuous':<12} {'Integer':<10} {'Binary':<10} {'Total':<12} {'Constraints':<12}")
    print("-"*80)

    for r in results:
        print(f"{r['horizon']:<10} {r['continuous_vars']:>10,}  {r['integer_vars']:>8,}  {r['binary_vars']:>8,}  {r['total_vars']:>10,}  {r['constraints']:>10,}")

    # Save detailed results
    output_file = Path(__file__).parent / "benchmark_with_demand_results.txt"
    with open(output_file, 'w') as f:
        f.write("BENCHMARK WITH DEMAND - Detailed Results\n")
        f.write("="*80 + "\n")
        f.write(f"Run date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Forecast start: {forecast_start.strftime('%Y-%m-%d')}\n\n")

        for r in results:
            f.write(f"\n{r['horizon'].upper()}\n")
            f.write("-"*40 + "\n")
            f.write(f"Planning days: {r['days']}\n")
            f.write(f"Solve time: {format_time(r['solve_time'])}\n")
            f.write(f"Solver status: {r['status']}\n")
            f.write(f"Demand entries: {r['demand_entries']:,}\n")
            f.write(f"Total demand: {r['total_demand']:,.0f} units\n")
            f.write(f"Total production: {r['total_production']:,.0f} units\n")
            f.write(f"Total mixes: {r['total_mixes']:.1f}\n")
            f.write(f"Products produced: {len(r['products_produced'])}\n")
            f.write(f"Production days: {r['production_days']:.1f}\n")
            f.write(f"Total changeovers: {r['total_changeovers']:.1f}\n")
            f.write(f"Objective value: ${r['objective_value']:,.2f}\n")
            f.write(f"Variables: {r['total_vars']:,} (cont: {r['continuous_vars']:,}, int: {r['integer_vars']:,}, bin: {r['binary_vars']:,})\n")
            f.write(f"Constraints: {r['constraints']:,}\n")

    print(f"\nDetailed results saved to: {output_file}")
    print(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
