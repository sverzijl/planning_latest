"""Example script to visualize an optimization solution using pyxel.

This script demonstrates how to:
1. Load network configuration and forecast data
2. Run the optimization
3. Launch the 8-bit retro visualization

Usage:
    python examples/visualize_solution.py

Controls in visualization:
    SPACE - Pause/unpause
    R - Reset to start
    UP/DOWN - Increase/decrease animation speed
    Q - Quit
    MOUSE - Click on locations to see details
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from parsers.excel_parser import ExcelParser
from optimization.integrated_model import IntegratedProductionDistributionModel
from optimization.solver_config import SolverConfig
from visualization.retro_viz import visualize_solution


def main():
    """Run optimization and visualize the solution."""
    print("=" * 60)
    print("Gluten-Free Bread Distribution - Retro Visualization")
    print("=" * 60)

    # Load data
    print("\n1. Loading network configuration and forecast data...")
    data_dir = Path(__file__).parent.parent / "data" / "examples"

    # Network configuration
    network_file = data_dir / "Network_Config.xlsx"
    if not network_file.exists():
        print(f"Error: Network configuration file not found: {network_file}")
        print("Please ensure Network_Config.xlsx is in data/examples/")
        return

    # Forecast file
    forecast_file = data_dir / "Gfree Forecast.xlsm"
    if not forecast_file.exists():
        print(f"Error: Forecast file not found: {forecast_file}")
        print("Please ensure Gfree Forecast.xlsm is in data/examples/")
        return

    # Parse network configuration
    parser = ExcelParser(str(network_file))
    parser.parse()

    locations = parser.get_locations()
    routes = parser.get_routes()
    labor_calendar = parser.get_labor_calendar()
    truck_schedules = parser.get_truck_schedules()
    cost_params = parser.get_cost_parameters()

    print(f"   Loaded {len(locations)} locations")
    print(f"   Loaded {len(routes)} routes")
    print(f"   Loaded {len(truck_schedules)} truck schedules")

    # Parse forecast
    forecast_parser = ExcelParser(str(forecast_file))
    forecast_parser.parse()
    forecast_data = forecast_parser.get_forecast()
    products = forecast_parser.get_products()

    print(f"   Loaded {len(products)} products")
    print(f"   Loaded {len(forecast_data)} forecast entries")

    # Create optimization model
    print("\n2. Building optimization model...")

    # Use a shorter planning horizon for faster solving
    from datetime import datetime, timedelta
    start_date = datetime(2025, 1, 6).date()
    planning_days = 14  # 2 weeks for faster demo

    model = IntegratedProductionDistributionModel(
        locations=locations,
        routes=routes,
        products=products,
        forecast=forecast_data,
        labor_calendar=labor_calendar,
        truck_schedules=truck_schedules,
        cost_structure=cost_params,
        planning_start_date=start_date,
        planning_days=planning_days,
        allow_shortages=True,
        enforce_shelf_life=True,
        use_batch_tracking=False,  # Disable for faster solving
    )

    # Solve
    print("\n3. Solving optimization model...")
    print("   This may take 30-60 seconds...")

    solver_config = SolverConfig()
    result = model.solve(
        time_limit_seconds=60,
        mip_gap=0.02,  # 2% gap tolerance
        tee=False,
    )

    if not result.is_feasible():
        print(f"\nOptimization failed: {result.infeasibility_message}")
        return

    print(f"\n✓ Optimization complete!")
    print(f"   Status: {result.termination_condition}")
    print(f"   Objective: ${result.objective_value:,.2f}")
    print(f"   Solve time: {result.solve_time_seconds:.1f}s")
    print(f"   MIP gap: {result.gap*100:.2f}%")

    # Get solution data
    solution = model.get_solution()

    # Launch visualization
    print("\n4. Launching 8-bit retro visualization...")
    print("\n" + "=" * 60)
    print("VISUALIZATION CONTROLS:")
    print("  SPACE     - Pause/unpause animation")
    print("  R         - Reset to start")
    print("  UP/DOWN   - Increase/decrease animation speed")
    print("  MOUSE     - Click locations to see details")
    print("  Q         - Quit")
    print("=" * 60)
    print("\nStarting visualization...\n")

    # Create a simple network config object for the visualizer
    class NetworkConfig:
        def __init__(self, locations, routes):
            self.locations = locations
            self.routes = routes

    network_config = NetworkConfig(locations, routes)

    # Launch visualization
    try:
        visualize_solution(
            solution=solution,
            network_config=network_config,
            truck_schedules=truck_schedules,
            animation_speed=2.0,  # Start at 2x speed
        )
    except Exception as e:
        print(f"\nError launching visualization: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
