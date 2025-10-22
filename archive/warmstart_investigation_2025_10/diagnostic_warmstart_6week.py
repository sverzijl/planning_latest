"""Diagnostic script for 6-week warmstart timeout issue.

PHASE 1: ROOT CAUSE INVESTIGATION - EVIDENCE GATHERING

This script instruments the warmstart solve to capture:
1. Model statistics (variables, constraints) for Phase 1 and Phase 2
2. Solve performance (time, iterations, gap) for each phase
3. Warmstart extraction details (what values are being passed)
4. Cost structure configuration (pallet vs unit-based)

NO FIXES - ONLY EVIDENCE GATHERING
"""

import sys
import time
from datetime import date, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.excel_parser import ExcelParser
from src.optimization.unified_node_model import solve_weekly_pattern_warmstart
from pyomo.environ import Var, Constraint, Binary, value as pyo_value


def print_section(title: str):
    """Print formatted section header."""
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}")


def analyze_model_structure(pyomo_model, phase_name: str):
    """Analyze and report model structure."""
    print_section(f"{phase_name} Model Structure Analysis")

    # Count variables by type
    num_binary = 0
    num_integer = 0
    num_continuous = 0

    for v in pyomo_model.component_data_objects(Var, active=True):
        if v.is_binary():
            num_binary += 1
        elif v.is_integer():
            num_integer += 1
        else:
            num_continuous += 1

    total_vars = num_binary + num_integer + num_continuous
    num_constraints = sum(1 for _ in pyomo_model.component_data_objects(Constraint, active=True))

    print(f"\nVariable Counts:")
    print(f"  Binary:     {num_binary:,}")
    print(f"  Integer:    {num_integer:,}")
    print(f"  Continuous: {num_continuous:,}")
    print(f"  TOTAL:      {total_vars:,}")
    print(f"\nConstraints: {num_constraints:,}")

    # Check for specific variable types
    has_product_produced = hasattr(pyomo_model, 'product_produced')
    has_pallet_count = hasattr(pyomo_model, 'pallet_count')
    has_weekly_pattern = hasattr(pyomo_model, 'product_weekday_pattern')

    print(f"\nKey Variables Present:")
    print(f"  product_produced:       {has_product_produced}")
    print(f"  pallet_count:           {has_pallet_count}")
    print(f"  product_weekday_pattern:{has_weekly_pattern}")

    # If pallet_count exists, count them
    if has_pallet_count:
        pallet_count_size = len([1 for _ in pyomo_model.pallet_count])
        print(f"  pallet_count size:      {pallet_count_size:,}")

    # If weekly pattern exists, count them
    if has_weekly_pattern:
        pattern_size = len([1 for _ in pyomo_model.product_weekday_pattern])
        print(f"  weekly_pattern size:    {pattern_size:,}")

    return {
        'num_binary': num_binary,
        'num_integer': num_integer,
        'num_continuous': num_continuous,
        'num_constraints': num_constraints,
        'has_pallet_count': has_pallet_count,
        'has_weekly_pattern': has_weekly_pattern,
    }


def analyze_cost_structure(cost_structure):
    """Analyze cost structure configuration."""
    print_section("Cost Structure Configuration")

    # Check if pallet-based costs are configured
    has_pallet_fixed_frozen = getattr(cost_structure, 'storage_cost_fixed_per_pallet_frozen', 0.0) > 0
    has_pallet_fixed_ambient = getattr(cost_structure, 'storage_cost_fixed_per_pallet_ambient', 0.0) > 0
    has_pallet_daily_frozen = getattr(cost_structure, 'storage_cost_per_pallet_day_frozen', 0.0) > 0
    has_pallet_daily_ambient = getattr(cost_structure, 'storage_cost_per_pallet_day_ambient', 0.0) > 0

    has_unit_frozen = getattr(cost_structure, 'storage_cost_frozen_per_unit_day', 0.0) > 0
    has_unit_ambient = getattr(cost_structure, 'storage_cost_ambient_per_unit_day', 0.0) > 0

    print(f"\nPallet-Based Storage Costs:")
    print(f"  Fixed frozen:  ${getattr(cost_structure, 'storage_cost_fixed_per_pallet_frozen', 0.0):.2f}")
    print(f"  Fixed ambient: ${getattr(cost_structure, 'storage_cost_fixed_per_pallet_ambient', 0.0):.2f}")
    print(f"  Daily frozen:  ${getattr(cost_structure, 'storage_cost_per_pallet_day_frozen', 0.0):.4f}")
    print(f"  Daily ambient: ${getattr(cost_structure, 'storage_cost_per_pallet_day_ambient', 0.0):.4f}")

    print(f"\nUnit-Based Storage Costs:")
    print(f"  Frozen per unit-day:  ${getattr(cost_structure, 'storage_cost_frozen_per_unit_day', 0.0):.4f}")
    print(f"  Ambient per unit-day: ${getattr(cost_structure, 'storage_cost_ambient_per_unit_day', 0.0):.4f}")

    pallet_tracking = any([has_pallet_fixed_frozen, has_pallet_fixed_ambient,
                           has_pallet_daily_frozen, has_pallet_daily_ambient])
    unit_tracking = any([has_unit_frozen, has_unit_ambient])

    print(f"\nCost Model Type:")
    print(f"  Pallet-based: {pallet_tracking}")
    print(f"  Unit-based:   {unit_tracking}")

    if pallet_tracking and unit_tracking:
        print(f"  ⚠️  WARNING: Both pallet and unit costs configured!")
        print(f"      Pallet-based takes precedence per CLAUDE.md")

    return {
        'pallet_tracking': pallet_tracking,
        'unit_tracking': unit_tracking,
    }


def main():
    print_section("6-WEEK WARMSTART DIAGNOSTIC")
    print("\nPurpose: Gather evidence about warmstart timeout issue")
    print("Approach: Systematic debugging - NO FIXES, ONLY EVIDENCE")

    # Load data files
    print_section("Loading Data Files")

    forecast_file = "data/examples/Gluten Free Forecast - Latest.xlsm"
    network_file = "data/examples/Network_Config.xlsx"
    inventory_file = "data/examples/inventory.XLSX"

    print(f"\nForecast: {forecast_file}")
    print(f"Network:  {network_file}")
    print(f"Inventory: {inventory_file}")

    parser = ExcelParser()

    print("\nParsing forecast...")
    forecast = parser.parse_forecast(forecast_file)

    print("Parsing network configuration...")
    locations_df, routes_df, labor_df, trucks_df, costs_df = parser.parse_network_config(network_file)

    nodes = parser.parse_locations(locations_df)
    routes = parser.parse_routes(routes_df)
    labor_calendar = parser.parse_labor_calendar(labor_df)
    truck_schedules = parser.parse_truck_schedules(trucks_df)
    cost_structure = parser.parse_cost_parameters(costs_df)

    print("Parsing initial inventory...")
    initial_inventory, inventory_date = parser.parse_initial_inventory(inventory_file)

    # Analyze cost structure BEFORE running model
    cost_config = analyze_cost_structure(cost_structure)

    # Setup solve parameters
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=6*7 - 1)  # 6 weeks

    print_section("Solve Configuration")
    print(f"\nHorizon: {start_date} to {end_date} ({(end_date - start_date).days + 1} days)")
    print(f"MIP Gap: 3%")
    print(f"Batch Tracking: True")
    print(f"Allow Shortages: True")
    print(f"Solver: APPSI_HIGHS")
    print(f"Phase 1 Timeout: 120s")
    print(f"Phase 2 Timeout: 600s (10 minutes)")

    # Instrument the solve by modifying the function temporarily
    # We'll use a callback to capture model structure

    phase_stats = {}

    def progress_callback(phase, status, elapsed, cost):
        """Capture progress updates."""
        print(f"\n[CALLBACK] Phase {phase}: {status}, {elapsed:.1f}s, Cost: {cost}")
        if status == "complete":
            phase_stats[f"phase{phase}_time"] = elapsed
            phase_stats[f"phase{phase}_cost"] = cost

    # CRITICAL: We need to intercept the model building to analyze structure
    # This requires modifying solve_weekly_pattern_warmstart to expose models
    # For now, we'll run it and capture what we can from output

    print_section("Starting Two-Phase Warmstart Solve")
    print("\nMonitoring for evidence of:")
    print("  1. Phase 1 pallet tracking (should be DISABLED)")
    print("  2. Phase 2 pallet tracking (should be ENABLED)")
    print("  3. Variable counts in each phase")
    print("  4. Solve performance metrics")
    print("  5. Warmstart value extraction")

    start_time = time.time()

    try:
        result = solve_weekly_pattern_warmstart(
            nodes=nodes,
            routes=routes,
            forecast=forecast,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure,
            start_date=start_date,
            end_date=end_date,
            truck_schedules=truck_schedules,
            initial_inventory=initial_inventory,
            inventory_snapshot_date=inventory_date,
            use_batch_tracking=True,
            allow_shortages=True,
            enforce_shelf_life=True,
            solver_name='appsi_highs',
            time_limit_phase1=120,
            time_limit_phase2=600,
            mip_gap=0.03,
            tee=True,  # Show solver output
            progress_callback=progress_callback,
        )

        total_time = time.time() - start_time

        print_section("Solve Results")
        print(f"\nSuccess: {result.success}")
        print(f"Total Time: {total_time:.1f}s")
        print(f"Final Cost: ${result.objective_value:,.2f}")
        print(f"Termination: {result.termination_condition}")
        if result.gap:
            print(f"Gap: {result.gap*100:.2f}%")

        # Extract metadata
        if result.metadata:
            print(f"\nMetadata:")
            for key, value in result.metadata.items():
                if key not in ['model_phase2', 'weekly_pattern']:
                    print(f"  {key}: {value}")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        total_time = time.time() - start_time
        print(f"\nFailed after {total_time:.1f}s")

    print_section("Diagnostic Summary")
    print("\nEvidence Collected:")
    print(f"  1. Cost structure type: {'Pallet' if cost_config['pallet_tracking'] else 'Unit'}-based")
    print(f"  2. Solve initiated successfully")
    print(f"  3. Check output above for:")
    print(f"     - Phase 1 binary variable count (expect ~110 if no pallets)")
    print(f"     - Phase 2 binary variable count (expect ~280)")
    print(f"     - Pallet variable mentions in Phase 1 (should be NONE)")
    print(f"     - Solve times and termination conditions")

    print("\n" + "="*80)
    print("NEXT STEPS:")
    print("1. Review output above for Phase 1 pallet_count variable mentions")
    print("2. Compare Phase 1 variable counts against expected (~110 binary)")
    print("3. Check if Phase 1 and Phase 2 have similar integer variable counts")
    print("4. If Phase 1 has pallet_count, this confirms hypothesis:")
    print("   → Phase 1 is running with pallet tracking when it shouldn't")
    print("   → This makes Phase 1 slow and warmstart ineffective")
    print("="*80)


if __name__ == "__main__":
    main()
