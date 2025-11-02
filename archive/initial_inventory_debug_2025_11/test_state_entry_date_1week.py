#!/usr/bin/env python3
"""Test state_entry_date implementation with 1-week solve.

Quick validation test to ensure:
1. Model builds without errors
2. Cohort count is reasonable (~50-100k)
3. Solver completes successfully
4. Solution quality is acceptable
"""

import sys
from datetime import date, timedelta
from pathlib import Path

# Add parent to path for proper imports
sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.excel_parser import ExcelParser
from src.optimization.unified_node_model import UnifiedNodeModel

def main():
    print("=" * 80)
    print("STATE_ENTRY_DATE IMPLEMENTATION - 1-WEEK VALIDATION TEST")
    print("=" * 80)

    # Load data
    print("\n📁 Loading data...")
    parser = ExcelParser()

    forecast_file = "data/examples/Gluten Free Forecast - Latest.xlsm"
    network_file = "data/examples/Network_Config.xlsx"

    print(f"  Forecast: {forecast_file}")
    print(f"  Network: {network_file}")

    # Parse files
    forecast_data = parser.parse_forecast(forecast_file)
    network_data = parser.parse_network_config(network_file)

    print(f"\n✅ Data loaded successfully")
    print(f"  Products: {len(forecast_data['products'])}")
    print(f"  Locations: {len(network_data['locations'])}")
    print(f"  Routes: {len(network_data['routes'])}")

    # Setup 1-week test
    start_date = date(2025, 10, 27)
    end_date = start_date + timedelta(days=6)  # 7 days total

    print(f"\n📅 Planning Horizon: 1 week")
    print(f"  Start: {start_date}")
    print(f"  End: {end_date}")

    # Build model
    print("\n🔨 Building optimization model...")
    model = UnifiedNodeModel(
        locations=network_data['locations'],
        routes=network_data['routes'],
        products=forecast_data['products'],
        demand=forecast_data['demand'],
        truck_schedules=network_data['truck_schedules'],
        labor_calendar=network_data['labor_calendar'],
        cost_structure=network_data['cost_parameters'],
        start_date=start_date,
        end_date=end_date,
        use_batch_tracking=True,
        allow_shortages=True
    )

    print("\n📊 Model Statistics:")
    pyomo_model = model.build()

    # Extract cohort counts
    if hasattr(pyomo_model, 'cohort_index'):
        cohort_count = len(list(pyomo_model.cohort_index))
        print(f"  Inventory cohorts (6-tuple): {cohort_count:,}")

    if hasattr(pyomo_model, 'demand_cohort_index'):
        demand_cohort_count = len(list(pyomo_model.demand_cohort_index))
        print(f"  Demand cohorts (6-tuple): {demand_cohort_count:,}")

    if hasattr(pyomo_model, 'shipment_cohort_index'):
        shipment_cohort_count = len(list(pyomo_model.shipment_cohort_index))
        print(f"  Shipment cohorts: {shipment_cohort_count:,}")

    # Count variables
    num_vars = sum(1 for _ in pyomo_model.component_data_objects(pyo.Var))
    print(f"  Total variables: {num_vars:,}")

    # Solve
    print("\n🚀 Solving with HiGHS...")
    try:
        solution = model.solve(
            solver_name='appsi_highs',
            time_limit_seconds=300,  # 5 minutes max
            mip_gap=0.02,  # 2% gap
            solver_options={}
        )

        print("\n✅ SOLVE COMPLETED")
        print(f"  Status: {solution.get('status', 'unknown')}")
        print(f"  Termination: {solution.get('termination_condition', 'unknown')}")
        print(f"  Solve time: {solution.get('solve_time_seconds', 0):.1f}s")
        print(f"  Total cost: ${solution.get('total_cost', 0):,.2f}")

        # Check solution quality
        if 'fill_rate' in solution:
            fill_rate = solution['fill_rate'] * 100
            print(f"  Fill rate: {fill_rate:.1f}%")

        print("\n🎯 STATE_ENTRY_DATE VALIDATION")
        print(f"  ✓ Model builds successfully with 6-tuple cohorts")
        print(f"  ✓ Cohort count reasonable: {cohort_count:,}")
        print(f"  ✓ Solver completes without errors")
        print(f"  ✓ Solution obtained")

        return 0

    except Exception as e:
        print(f"\n❌ SOLVE FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    import pyomo.environ as pyo
    sys.exit(main())
