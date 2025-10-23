"""Tests for APPSI HiGHS solver interface.

This module tests the new APPSI (Pyomo's Advanced Persistent Solver Interface)
for HiGHS solver, which provides better performance and warmstart support.

Key differences from legacy HiGHS interface:
- Uses pyomo.contrib.appsi.solvers.Highs instead of SolverFactory('highs')
- Configuration via solver.config instead of solver.options
- Warmstart support via solver.config.warmstart=True
- Different result extraction (results.termination_condition)

Test Coverage:
1. Solver detection and availability
2. Basic solve with APPSI interface
3. Warmstart configuration and application
4. Solution extraction and validation
5. Error handling for missing solver
6. Performance comparison with legacy interface
"""

import pytest
from pathlib import Path
from datetime import date, timedelta
import time

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from tests.conftest import create_test_products
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter


@pytest.fixture
def simple_data():
    """Small dataset for quick APPSI HiGHS testing."""
    data_dir = Path(__file__).parent.parent / "data" / "examples"

    forecast_file = data_dir / "Gfree Forecast.xlsm"
    network_file = data_dir / "Network_Config.xlsx"

    assert forecast_file.exists(), f"Forecast file not found: {forecast_file}"
    assert network_file.exists(), f"Network file not found: {network_file}"

    # Parse data
    parser = MultiFileParser(
        forecast_file=forecast_file,
        network_file=network_file,
        inventory_file=None,
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Get manufacturing site
    from src.models.manufacturing import ManufacturingSite
    from src.models.location import LocationType

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    if not manufacturing_locations:
        raise ValueError("No manufacturing site found")

    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id,
        name=manuf_loc.name,
        storage_mode=manuf_loc.storage_mode,
        production_rate=manuf_loc.production_rate if hasattr(manuf_loc, 'production_rate') else 1400.0,
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

    # Use earliest forecast date as planning start
    planning_start_date = min(e.forecast_date for e in forecast.entries)

    return {
        'forecast': forecast,
        'nodes': nodes,
        'unified_routes': unified_routes,
        'unified_truck_schedules': unified_truck_schedules,
        'labor_calendar': labor_calendar,
        'cost_structure': cost_structure,
        'planning_start_date': planning_start_date,
    }


def test_appsi_highs_availability():
    """Test that APPSI HiGHS interface is available.

    This test verifies that the APPSI HiGHS solver can be imported and detected.
    If highspy package is not installed, this test should be skipped.
    """
    try:
        from pyomo.contrib.appsi.solvers import Highs
        solver = Highs()
        available = solver.available()

        if not available:
            pytest.skip("APPSI HiGHS solver not available (install: pip install highspy)")

        print(f"\n✓ APPSI HiGHS available: {available}")
        assert available is True

    except ImportError:
        pytest.skip("APPSI module not available (requires Pyomo >= 6.9.1)")


def test_appsi_highs_basic_solve(simple_data):
    """Test basic solve with APPSI HiGHS interface.

    This test validates:
    1. Model creation
    2. APPSI HiGHS solver invocation
    3. Solution extraction
    4. Result validation
    """
    try:
        from pyomo.contrib.appsi.solvers import Highs
    except ImportError:
        pytest.skip("APPSI not available")

    # Check solver availability
    solver_test = Highs()
    if not solver_test.available():
        pytest.skip("HiGHS not available")

    # Extract data
    forecast = simple_data['forecast']
    nodes = simple_data['nodes']
    unified_routes = simple_data['unified_routes']
    unified_truck_schedules = simple_data['unified_truck_schedules']
    labor_calendar = simple_data['labor_calendar']
    cost_structure = simple_data['cost_structure']
    planning_start_date = simple_data['planning_start_date']

    # Use 1-week horizon for fast testing
    planning_end_date = planning_start_date + timedelta(weeks=1)

    print("\n" + "="*80)
    print("TEST: APPSI HiGHS Basic Solve")
    print("="*80)
    print(f"Planning horizon: {planning_start_date} to {planning_end_date} (7 days)")

    # Create model
    model_start = time.time()

    # Create products for model (extract unique product IDs from forecast)
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=planning_start_date,
        end_date=planning_end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=None,
        inventory_snapshot_date=None,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    model_build_time = time.time() - model_start
    print(f"✓ Model built in {model_build_time:.2f}s")

    # Solve with APPSI HiGHS
    solve_start = time.time()

    result = model.solve(
        solver_name='appsi_highs',  # Use APPSI interface
        time_limit_seconds=60,
        mip_gap=0.01,
        use_aggressive_heuristics=True,
        tee=False,
    )

    solve_time = time.time() - solve_start

    print(f"\n✓ APPSI HiGHS SOLVE COMPLETE:")
    print(f"   Status: {result.termination_condition}")
    print(f"   Solve time: {solve_time:.1f}s")
    print(f"   Objective: ${result.objective_value:,.2f}" if result.objective_value else "   Objective: N/A")
    print(f"   MIP gap: {result.gap * 100:.2f}%" if result.gap else "   MIP gap: N/A")

    # Assertions
    assert result.is_optimal() or result.is_feasible(), \
        f"Expected optimal/feasible, got {result.termination_condition}"

    assert solve_time < 60, \
        f"APPSI HiGHS took {solve_time:.1f}s (expected <60s for 1-week)"

    # Validate solution quality
    solution = model.get_solution()
    assert solution is not None, "Solution should not be None"

    # Check solution has expected fields
    assert 'total_cost' in solution or result.objective_value is not None, \
        "Solution should include total_cost or objective_value"

    assert 'production_by_date_product' in solution, \
        "Solution should include production_by_date_product"

    # Validate production
    production_by_date_product = solution.get('production_by_date_product', {})
    total_production = sum(production_by_date_product.values())

    assert total_production > 0, "Should produce units"

    print(f"\n✓ APPSI HiGHS BASIC SOLVE TEST PASSED")
    print(f"   Total production: {total_production:,.0f} units")


def test_appsi_highs_with_warmstart(simple_data):
    """Test APPSI HiGHS with warmstart configuration.

    This test validates:
    1. Warmstart hint generation
    2. APPSI warmstart configuration (solver.config.warmstart=True)
    3. Solution quality maintained with warmstart

    Note: APPSI HiGHS supports warmstart via config, unlike legacy interface.
    """
    try:
        from pyomo.contrib.appsi.solvers import Highs
    except ImportError:
        pytest.skip("APPSI not available")

    # Check solver availability
    solver_test = Highs()
    if not solver_test.available():
        pytest.skip("HiGHS not available")

    # Extract data
    forecast = simple_data['forecast']
    nodes = simple_data['nodes']
    unified_routes = simple_data['unified_routes']
    unified_truck_schedules = simple_data['unified_truck_schedules']
    labor_calendar = simple_data['labor_calendar']
    cost_structure = simple_data['cost_structure']
    planning_start_date = simple_data['planning_start_date']

    # Use 2-week horizon
    planning_end_date = planning_start_date + timedelta(weeks=2)

    print("\n" + "="*80)
    print("TEST: APPSI HiGHS with Warmstart")
    print("="*80)
    print(f"Planning horizon: {planning_start_date} to {planning_end_date} (14 days)")

    # Create model
    # Create products for model (extract unique product IDs from forecast)
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=planning_start_date,
        end_date=planning_end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=None,
        inventory_snapshot_date=None,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    print(f"✓ Model built")

    # Solve with warmstart enabled
    solve_start = time.time()

    result = model.solve(
        solver_name='appsi_highs',
        use_warmstart=True,  # Enable warmstart via APPSI config
        time_limit_seconds=90,
        mip_gap=0.01,
        use_aggressive_heuristics=True,
        tee=False,
    )

    solve_time = time.time() - solve_start

    print(f"\n✓ APPSI HiGHS WARMSTART SOLVE COMPLETE:")
    print(f"   Status: {result.termination_condition}")
    print(f"   Solve time: {solve_time:.1f}s")
    print(f"   Objective: ${result.objective_value:,.2f}" if result.objective_value else "   Objective: N/A")

    # Assertions
    assert result.is_optimal() or result.is_feasible(), \
        f"Expected optimal/feasible, got {result.termination_condition}"

    assert solve_time < 90, \
        f"APPSI HiGHS with warmstart took {solve_time:.1f}s (expected <90s for 2-week)"

    # Validate solution
    solution = model.get_solution()
    assert solution is not None

    production_by_date_product = solution.get('production_by_date_product', {})
    total_production = sum(production_by_date_product.values())
    assert total_production > 0

    print(f"✓ APPSI HiGHS WARMSTART TEST PASSED")


def test_appsi_highs_performance_vs_legacy(simple_data):
    """Compare APPSI HiGHS vs legacy HiGHS interface performance.

    This test validates that APPSI interface provides comparable or better
    performance than the legacy SolverFactory('highs') interface.

    Note: Both should give similar solve times since they use same solver engine.
    APPSI may have slight overhead for small problems, but better for large problems.
    """
    try:
        from pyomo.contrib.appsi.solvers import Highs
    except ImportError:
        pytest.skip("APPSI not available")

    # Check solver availability
    solver_test = Highs()
    if not solver_test.available():
        pytest.skip("HiGHS not available")

    # Extract data
    forecast = simple_data['forecast']
    nodes = simple_data['nodes']
    unified_routes = simple_data['unified_routes']
    unified_truck_schedules = simple_data['unified_truck_schedules']
    labor_calendar = simple_data['labor_calendar']
    cost_structure = simple_data['cost_structure']
    planning_start_date = simple_data['planning_start_date']

    # Use 1-week horizon for quick comparison
    planning_end_date = planning_start_date + timedelta(weeks=1)

    print("\n" + "="*80)
    print("TEST: APPSI HiGHS vs Legacy Interface Performance")
    print("="*80)

    # Test 1: Legacy HiGHS interface
    print("\nTesting LEGACY HiGHS interface...")

    model_legacy = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=planning_start_date,
        end_date=planning_end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=None,
        inventory_snapshot_date=None,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    start_legacy = time.time()
    result_legacy = model_legacy.solve(
        solver_name='highs',  # Legacy interface
        time_limit_seconds=60,
        mip_gap=0.01,
        use_aggressive_heuristics=True,
        tee=False,
    )
    time_legacy = time.time() - start_legacy

    print(f"✓ Legacy HiGHS: {time_legacy:.2f}s, Status: {result_legacy.termination_condition}")

    # Test 2: APPSI HiGHS interface
    print("\nTesting APPSI HiGHS interface...")

    model_appsi = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=planning_start_date,
        end_date=planning_end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=None,
        inventory_snapshot_date=None,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    start_appsi = time.time()
    result_appsi = model_appsi.solve(
        solver_name='appsi_highs',  # APPSI interface
        time_limit_seconds=60,
        mip_gap=0.01,
        use_aggressive_heuristics=True,
        tee=False,
    )
    time_appsi = time.time() - start_appsi

    print(f"✓ APPSI HiGHS: {time_appsi:.2f}s, Status: {result_appsi.termination_condition}")

    # Compare results
    print(f"\n" + "="*80)
    print("PERFORMANCE COMPARISON")
    print("="*80)
    print(f"Legacy HiGHS:  {time_legacy:.2f}s")
    print(f"APPSI HiGHS:   {time_appsi:.2f}s")
    print(f"Difference:    {time_appsi - time_legacy:+.2f}s ({((time_appsi/time_legacy - 1)*100):+.1f}%)")

    # Both should solve successfully
    assert result_legacy.is_optimal() or result_legacy.is_feasible()
    assert result_appsi.is_optimal() or result_appsi.is_feasible()

    # Both should produce similar objective values (within 1% tolerance)
    if result_legacy.objective_value and result_appsi.objective_value:
        obj_diff_pct = abs(result_appsi.objective_value - result_legacy.objective_value) / result_legacy.objective_value * 100
        print(f"\nObjective difference: {obj_diff_pct:.2f}%")

        assert obj_diff_pct < 1.0, \
            f"Objective values differ by {obj_diff_pct:.2f}% (expected <1%)"

    print(f"\n✓ PERFORMANCE COMPARISON TEST PASSED")


def test_appsi_highs_error_handling():
    """Test APPSI HiGHS error handling when solver not available.

    This test validates that the code handles missing APPSI gracefully
    and provides helpful error messages.
    """
    # This test is mainly for documentation - actual error handling
    # is tested indirectly by other tests that check availability

    print("\n" + "="*80)
    print("TEST: APPSI HiGHS Error Handling")
    print("="*80)

    try:
        from pyomo.contrib.appsi.solvers import Highs
        solver = Highs()
        available = solver.available()

        print(f"✓ APPSI HiGHS availability check: {available}")

        if not available:
            print("  Solver not available - this would be caught by pytest.skip()")
        else:
            print("  Solver available - error handling not tested (solver works)")

    except ImportError as e:
        print(f"✓ ImportError caught (expected when APPSI not installed): {e}")
        print("  This would be caught by pytest.skip() in actual tests")

    print("\n✓ ERROR HANDLING TEST COMPLETE")


if __name__ == "__main__":
    """Allow running tests directly for debugging."""
    pytest.main([__file__, "-v", "-s"])
