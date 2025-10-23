#!/usr/bin/env python3
"""
Performance benchmarks for mix-based production implementation.

Tests 1-week, 2-week, and 4-week planning horizons with real data files.
Measures solve time, variables, constraints, MIP gap, and solution quality.
"""

from datetime import date, timedelta
from pathlib import Path
import time
from typing import Dict, Any

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models import ManufacturingSite, LocationType
from src.models.product import Product


def run_benchmark(weeks: int) -> Dict[str, Any]:
    """
    Run benchmark for specified planning horizon.

    Args:
        weeks: Planning horizon in weeks (1, 2, or 4)

    Returns:
        Dictionary with benchmark results
    """
    print(f"\n{'='*80}")
    print(f"BENCHMARK: {weeks}-week planning horizon")
    print(f"{'='*80}")

    # Define data file paths
    base_dir = Path("/home/sverzijl/planning_latest")
    data_dir = base_dir / "data" / "examples"

    network_file = data_dir / "Network_Config.xlsx"
    forecast_file = data_dir / "Gluten Free Forecast - Latest.xlsm"
    if not forecast_file.exists():
        forecast_file = data_dir / "GFree Forecast.xlsm"
    inventory_file = data_dir / "inventory_latest.XLSX"

    print(f"\nLoading data files:")
    print(f"  Network:   {network_file.name}")
    print(f"  Forecast:  {forecast_file.name}")
    print(f"  Inventory: {inventory_file.name if inventory_file.exists() else 'None'}")

    # Load data using MultiFileParser (matches UI workflow)
    load_start = time.time()

    parser = MultiFileParser(
        forecast_file=str(forecast_file),
        network_file=str(network_file),
        inventory_file=str(inventory_file) if inventory_file.exists() else None
    )

    # Parse all data
    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Get manufacturing site from locations
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    if not manufacturing_locations:
        raise ValueError("No manufacturing site found in locations")

    manuf_loc = manufacturing_locations[0]

    # Create ManufacturingSite
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

    # Parse initial inventory if available
    initial_inventory = None
    if inventory_file.exists():
        initial_inventory = parser.parse_inventory(snapshot_date=None)

    # Extract product IDs from forecast and create products with units_per_mix
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = {}
    for prod_id in product_ids:
        products[prod_id] = Product(
            id=prod_id,
            name=f"Product {prod_id}",
            sku=prod_id,
            units_per_mix=415  # Standard mix size
        )

    # Convert to unified format
    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    load_time = time.time() - load_start

    print(f"\nData loaded in {load_time:.2f}s")
    print(f"  Products: {len(products)}")
    print(f"  Nodes: {len(nodes)}")
    print(f"  Routes: {len(unified_routes)}")
    print(f"  Labor days: {len(labor_calendar.days)}")
    print(f"  Truck schedules: {len(unified_truck_schedules)}")
    print(f"  Forecast records: {len(forecast.entries)}")
    print(f"  Inventory snapshot: {'Yes' if initial_inventory else 'No'}")

    # Calculate date range
    start_date = date(2025, 1, 6)  # Monday
    end_date = start_date + timedelta(days=weeks * 7 - 1)

    print(f"\nPlanning horizon: {start_date} to {end_date} ({weeks} weeks)")

    # Create model with mix-based production
    print("\nCreating optimization model...")
    create_start = time.time()

    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,  # Pass products for mix-based production
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
        inventory_snapshot_date=initial_inventory.snapshot_date if initial_inventory else None,
        use_batch_tracking=True,
        allow_shortages=False,
        enforce_shelf_life=True
    )

    create_time = time.time() - create_start
    print(f"\nModel created in {create_time:.2f}s")

    # Solve with APPSI HiGHS
    print("\nSolving with APPSI HiGHS (1% MIP gap, 600s time limit)...")
    solve_start = time.time()

    result = model.solve(
        solver_name='appsi_highs',
        time_limit_seconds=600.0,
        mip_gap=0.01,
        tee=False
    )

    solve_time = time.time() - solve_start

    # Get model statistics from the solved model
    num_vars = 0
    num_continuous = 0
    num_integer = 0
    num_binary = 0
    num_constraints = 0

    if hasattr(model, 'model') and model.model is not None:
        from pyomo.environ import Var
        pyomo_model = model.model
        num_vars = pyomo_model.nvariables()
        num_constraints = pyomo_model.nconstraints()

        # Count variable types
        for var in pyomo_model.component_data_objects(Var):
            if var.is_continuous():
                num_continuous += 1
            elif var.is_binary():
                num_binary += 1
            elif var.is_integer():
                num_integer += 1

    print(f"\nSolve completed in {solve_time:.2f}s")
    print(f"  Success: {result.success}")
    print(f"  Feasible: {result.is_feasible()}")
    print(f"  Optimal: {result.is_optimal()}")
    if result.gap is not None:
        print(f"  MIP gap: {result.gap:.4f}")
    print(f"  Variables: {num_vars} ({num_continuous} cont, {num_integer} int, {num_binary} bin)")
    print(f"  Constraints: {num_constraints}")

    # Extract solution statistics
    total_production = 0.0
    total_mixes = 0.0
    total_changeovers = 0.0

    if result.is_feasible() and hasattr(model, 'model') and model.model is not None:
        from pyomo.core.base.var import value
        pyomo_model = model.model

        # Sum production variables (units)
        if hasattr(pyomo_model, 'production'):
            for idx in pyomo_model.production:
                val = value(pyomo_model.production[idx])
                if val and val > 0.01:
                    total_production += val

        # Sum mix_count variables
        if hasattr(pyomo_model, 'mix_count'):
            for idx in pyomo_model.mix_count:
                val = value(pyomo_model.mix_count[idx])
                if val and val > 0.01:
                    total_mixes += val

        # Count changeovers (product_start variables)
        if hasattr(pyomo_model, 'product_start'):
            for idx in pyomo_model.product_start:
                val = value(pyomo_model.product_start[idx])
                if val and val > 0.5:  # Binary variable
                    total_changeovers += 1

        print(f"\nSolution quality:")
        print(f"  Total cost: ${result.objective_value:,.2f}")
        print(f"  Total production: {total_production:,.0f} units")
        print(f"  Total mixes: {total_mixes:,.1f}")
        print(f"  Total changeovers: {total_changeovers:.0f}")
    elif not result.is_feasible():
        print("\nNo feasible solution found!")

    # Return benchmark results
    return {
        'weeks': weeks,
        'start_date': start_date,
        'end_date': end_date,
        'load_time': load_time,
        'create_time': create_time,
        'solve_time': solve_time,
        'total_time': load_time + create_time + solve_time,
        'num_vars': num_vars,
        'num_continuous': num_continuous,
        'num_integer': num_integer,
        'num_binary': num_binary,
        'num_constraints': num_constraints,
        'success': result.success,
        'feasible': result.is_feasible(),
        'optimal': result.is_optimal(),
        'mip_gap': result.gap if result.gap is not None else float('nan'),
        'objective_value': result.objective_value if result.is_feasible() else float('nan'),
        'total_production': total_production,
        'total_mixes': total_mixes,
        'total_changeovers': total_changeovers
    }


def print_results_table(results):
    """Print formatted benchmark results table."""
    print("\n" + "="*120)
    print("BENCHMARK RESULTS SUMMARY")
    print("="*120)

    # Header
    print(f"\n{'Horizon':<10} {'Load':>8} {'Create':>8} {'Solve':>8} {'Total':>8} "
          f"{'Vars':>8} {'Cont':>8} {'Int':>7} {'Bin':>7} {'Constr':>8} "
          f"{'Status':<12} {'MIP Gap':>9} {'Cost':>12}")
    print("-"*120)

    import math

    # Data rows
    for r in results:
        status_str = 'OPTIMAL' if r['optimal'] else ('FEASIBLE' if r['feasible'] else 'INFEASIBLE')
        mip_gap_str = f"{r['mip_gap']*100:.2f}%" if not math.isnan(r['mip_gap']) else "N/A"
        cost_str = f"${r['objective_value']:,.0f}" if not math.isnan(r['objective_value']) else "N/A"

        print(f"{r['weeks']}-week    "
              f"{r['load_time']:>7.1f}s "
              f"{r['create_time']:>7.1f}s "
              f"{r['solve_time']:>7.1f}s "
              f"{r['total_time']:>7.1f}s "
              f"{r['num_vars']:>8,} "
              f"{r['num_continuous']:>8,} "
              f"{r['num_integer']:>7,} "
              f"{r['num_binary']:>7,} "
              f"{r['num_constraints']:>8,} "
              f"{status_str:<12} "
              f"{mip_gap_str:>9} "
              f"{cost_str:>12}")

    print("\n" + "="*120)
    print("\nSOLUTION QUALITY")
    print("="*120)

    print(f"\n{'Horizon':<10} {'Production':>15} {'Mixes':>12} {'Changeovers':>12}")
    print("-"*50)

    for r in results:
        if r['feasible']:
            print(f"{r['weeks']}-week    "
                  f"{r['total_production']:>15,.0f} "
                  f"{r['total_mixes']:>12,.1f} "
                  f"{r['total_changeovers']:>12,.0f}")
        else:
            print(f"{r['weeks']}-week    {'N/A':>15} {'N/A':>12} {'N/A':>12}")

    print("\n" + "="*120)
    print("\nPERFORMANCE VS TARGETS")
    print("="*120)

    targets = {
        1: 100,
        2: 200,
        4: 400
    }

    print(f"\n{'Horizon':<10} {'Solve Time':>12} {'Target':>12} {'Status':>12}")
    print("-"*50)

    for r in results:
        target = targets.get(r['weeks'], 0)
        status = "PASS ✓" if r['solve_time'] < target else "FAIL ✗"
        print(f"{r['weeks']}-week    "
              f"{r['solve_time']:>11.1f}s "
              f"{target:>11.0f}s "
              f"{status:>12}")

    print()


def main():
    """Run all benchmarks and generate report."""
    print("="*120)
    print("MIX-BASED PRODUCTION PERFORMANCE BENCHMARKS")
    print("="*120)
    print(f"\nDate: {date.today()}")
    print("Solver: APPSI HiGHS")
    print("MIP Gap: 1%")
    print("Time Limit: 600s (10 minutes)")
    print("Batch Tracking: Enabled")
    print("Pallet-Based Costs: Disabled")

    # Run benchmarks for different horizons
    horizons = [1, 2, 4]
    results = []

    for weeks in horizons:
        try:
            result = run_benchmark(weeks)
            results.append(result)
        except Exception as e:
            print(f"\n❌ ERROR in {weeks}-week benchmark: {e}")
            import traceback
            traceback.print_exc()
            continue

    # Print results table
    if results:
        print_results_table(results)

        # Check if all benchmarks passed
        targets = {1: 100, 2: 200, 4: 400}
        all_passed = all(r['solve_time'] < targets.get(r['weeks'], float('inf'))
                        and r['feasible']
                        for r in results)

        if all_passed:
            print("\n✅ All benchmarks passed performance targets!")
        else:
            print("\n⚠️  Some benchmarks did not meet performance targets or failed to solve.")
    else:
        print("\n❌ No benchmarks completed successfully.")


if __name__ == "__main__":
    main()
