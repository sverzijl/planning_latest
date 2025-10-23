#!/usr/bin/env python3
"""Integration test with user's actual data files to diagnose timeout issue.

Files used:
- Network_Config.xlsx
- Gfree Forecast.xlsm
- inventory_latest.XLSX

User reports: Times out even with 10 minutes, high MIP gap, allowing shortages, 4-week horizon.
Goal: Reproduce issue, diagnose with Pyomo skill, and fix.
"""

import time
from datetime import timedelta, date
from pathlib import Path

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType


def main():
    print("="*80)
    print("USER DATA TIMEOUT DIAGNOSIS")
    print("="*80)
    print("\nConfiguration:")
    print("  - Allow shortages: True")
    print("  - MIP gap: 5% (relaxed)")
    print("  - Time limit: 10 minutes (600s)")
    print("  - Horizon: 4 weeks")

    # Load data
    data_dir = Path("data/examples")
    forecast_file = data_dir / "Gfree Forecast.xlsm"
    network_file = data_dir / "Network_Config.xlsx"
    inventory_file = data_dir / "inventory_latest.XLSX"

    print(f"\nLoading data files:")
    print(f"  Forecast: {forecast_file.name}")
    print(f"  Network: {network_file.name}")
    print(f"  Inventory: {inventory_file.name}")

    if not forecast_file.exists():
        print(f"\n❌ ERROR: {forecast_file} not found")
        return
    if not network_file.exists():
        print(f"\n❌ ERROR: {network_file} not found")
        return
    if not inventory_file.exists():
        print(f"\n❌ ERROR: {inventory_file} not found")
        inventory_file = None

    # Parse data
    parser = MultiFileParser(
        forecast_file=str(forecast_file),
        network_file=str(network_file),
        inventory_file=str(inventory_file) if inventory_file else None,
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Parse inventory if available
    initial_inventory = None
    inventory_snapshot_date = None
    if inventory_file and inventory_file.exists():
        try:
            inventory_snapshot = parser.parse_inventory(snapshot_date=None)
            initial_inventory = inventory_snapshot
            inventory_snapshot_date = inventory_snapshot.snapshot_date
            print(f"  ✓ Inventory loaded: {inventory_snapshot_date}")
        except Exception as e:
            print(f"  ⚠ Inventory parse failed: {e}")

    # Get manufacturing site
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    if not manufacturing_locations:
        print("\n❌ ERROR: No manufacturing location found")
        return

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

    # Set planning horizon
    if inventory_snapshot_date:
        start_date = inventory_snapshot_date
    else:
        start_date = min(entry.forecast_date for entry in forecast.entries)

    end_date = start_date + timedelta(days=27)  # 4 weeks

    # Data summary
    print(f"\n{'='*80}")
    print("DATA SUMMARY")
    print(f"{'='*80}")
    print(f"Forecast entries: {len(forecast.entries):,}")
    print(f"Date range: {min(e.forecast_date for e in forecast.entries)} to {max(e.forecast_date for e in forecast.entries)}")
    print(f"Total demand: {sum(e.quantity for e in forecast.entries):,.0f} units")
    print(f"Products: {len(set(e.product_id for e in forecast.entries))}")
    print(f"Nodes: {len(nodes)}")
    print(f"Routes: {len(unified_routes)}")
    print(f"Truck schedules: {len(unified_truck_schedules)}")
    print(f"Planning horizon: {start_date} to {end_date} (28 days)")

    if initial_inventory:
        inv_dict = initial_inventory.to_optimization_dict()
        print(f"Initial inventory: {sum(inv_dict.values()):,.0f} units")

    # Create model
    print(f"\n{'='*80}")
    print("CREATING MODEL")
    print(f"{'='*80}")

    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=inv_dict if initial_inventory else None,
        inventory_snapshot_date=inventory_snapshot_date,
        use_batch_tracking=True,
        allow_shortages=True,  # User setting
        enforce_shelf_life=True,
    )

    # Build model to get statistics
    print("\nBuilding Pyomo model...")
    build_start = time.time()
    pyomo_model = model.build_model()
    build_time = time.time() - build_start
    print(f"Build time: {build_time:.2f}s")

    # Get model statistics
    model.model = pyomo_model
    stats = model.get_model_statistics()

    print(f"\n{'='*80}")
    print("MODEL STATISTICS (Pyomo Analysis)")
    print(f"{'='*80}")
    print(f"Total variables:     {stats['num_variables']:,}")
    print(f"  - Binary:          {stats['num_binary_vars']:,}")
    print(f"  - Integer:         {stats['num_integer_vars']:,}")
    print(f"  - Continuous:      {stats['num_continuous_vars']:,}")
    print(f"Total constraints:   {stats['num_constraints']:,}")

    # CRITICAL: Check for signs of infeasibility or unusual structure
    print(f"\n{'='*80}")
    print("POTENTIAL ISSUES TO INVESTIGATE:")
    print(f"{'='*80}")

    # Check if problem is unusually large
    if stats['num_variables'] > 100000:
        print(f"⚠️  VERY LARGE: {stats['num_variables']:,} variables (may cause timeout)")

    if stats['num_integer_vars'] > 5000:
        print(f"⚠️  MANY INTEGERS: {stats['num_integer_vars']:,} integer vars (MIP difficulty)")

    if stats['num_constraints'] > 50000:
        print(f"⚠️  MANY CONSTRAINTS: {stats['num_constraints']:,} constraints")

    # Try solving with CBC first (shorter timeout to see behavior)
    print(f"\n{'='*80}")
    print("ATTEMPT 1: CBC SOLVER (2 minute timeout)")
    print(f"{'='*80}")

    print("\nSolving with CBC (relaxed gap: 5%, allow shortages)...")
    start_solve = time.time()

    try:
        result = model.solve(
            solver_name='cbc',
            time_limit_seconds=120,  # 2 minutes to see if it progresses
            mip_gap=0.05,  # 5% gap (relaxed)
            tee=True,  # Show solver output to see what's happening
        )
        solve_time = time.time() - start_solve

        print(f"\n{'='*80}")
        print("CBC RESULTS")
        print(f"{'='*80}")
        print(f"Status: {result.termination_condition}")
        print(f"Time: {solve_time:.2f}s")
        if result.objective_value:
            print(f"Objective: ${result.objective_value:,.2f}")
        if result.gap:
            print(f"MIP Gap: {result.gap:.2%}")

        if solve_time > 110:
            print(f"\n⚠️  TIMEOUT: Solver used nearly full time limit")
            print(f"   This suggests:")
            print(f"     - Problem may be infeasible")
            print(f"     - Problem structure may be problematic")
            print(f"     - Initial solution very hard to find")

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ ERROR during solve: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n{'='*80}")
    print("DIAGNOSIS NEEDED")
    print(f"{'='*80}")
    print("\nNext steps:")
    print("  1. Analyze solver output for warning signs")
    print("  2. Check if initial feasible solution found")
    print("  3. Use Pyomo skill to identify constraint conflicts")
    print("  4. Check for tight constraints or infeasibility")


if __name__ == "__main__":
    main()
