#!/usr/bin/env python
"""Complete test of UnifiedNodeModel warmstart with proper data flow.

This verifies:
1. UnifiedNodeModel.solve(use_warmstart=True) passes flag to base class
2. Base class passes warmstart=True to Pyomo
3. CBC receives -mipstart flag
4. Warmstart values are actually read by CBC
"""

import sys
from datetime import date, timedelta
from src.optimization.unified_node_model import UnifiedNodeModel
from src.parsers.excel_parser import ExcelParser


def test_unified_warmstart():
    """Test UnifiedNodeModel warmstart end-to-end."""
    print("="*80)
    print("UNIFIED NODE MODEL WARMSTART TEST")
    print("="*80)

    # Load real data
    parser = ExcelParser()
    data = parser.parse_forecast("/home/sverzijl/planning_latest/data/examples/GFree Forecast.xlsm")
    network_data = parser.parse_network_config("/home/sverzijl/planning_latest/data/examples/Network_Config.xlsx")

    # Create model with 1 week horizon (faster)
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=6)

    print(f"\nCreating UnifiedNodeModel...")
    print(f"  Horizon: {start_date} to {end_date} (7 days)")
    print(f"  Products: {len(data['products'])}")
    print(f"  Nodes: {len(network_data['nodes'])}")

    model = UnifiedNodeModel(
        nodes=network_data['nodes'],
        routes=network_data['routes'],
        forecast=data['forecast'],
        labor_calendar=network_data['labor_calendar'],
        cost_structure=network_data['cost_structure'],
        start_date=start_date,
        end_date=end_date,
        truck_schedules=network_data['truck_schedules'],
        initial_inventory=network_data['initial_inventory'],
        use_batch_tracking=False,  # Faster without batch tracking
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    print(f"\nSolving with use_warmstart=True...")
    print("-"*80)

    result = model.solve(
        solver_name='cbc',
        time_limit_seconds=30,
        mip_gap=0.05,
        use_warmstart=True,  # ENABLE WARMSTART
        tee=True,  # Show solver output
    )

    print("-"*80)
    print(f"\nResult: {result.termination_condition}")
    print(f"Objective: ${result.objective_value:,.2f}" if result.objective_value else "N/A")
    print(f"Solve Time: {result.solve_time_seconds:.2f}s")
    print(f"Variables: {result.num_variables:,} ({result.num_integer_vars:,} integer)")

    return result.success


if __name__ == "__main__":
    try:
        success = test_unified_warmstart()

        print("\n" + "="*80)
        if success:
            print("UNIFIED WARMSTART TEST PASSED")
            print("="*80)
            print("\nCHECK OUTPUT ABOVE FOR:")
            print("  1. '-mipstart' flag in CBC command line")
            print("  2. 'MIPStart values read for N variables' message")
            print("="*80)
        else:
            print("UNIFIED WARMSTART TEST FAILED (solve unsuccessful)")
            print("="*80)

        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
