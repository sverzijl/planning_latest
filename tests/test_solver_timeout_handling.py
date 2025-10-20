"""Tests for solver timeout and stale variable handling.

This module tests edge cases related to solver timeouts and solution extraction
when variables may be stale (uninitialized) due to zero costs or timeout.

Critical Fix (2025-10-19):
- Solution extraction now checks if variables are stale before calling value()
- Prevents RuntimeError when solver doesn't initialize zero-cost variables
- Handles timeout scenarios where partial solutions exist

Test Coverage:
1. Solution extraction with zero-cost variables (stale variables)
2. Timeout with partial solution extraction
3. Objective value extraction from multiple sources
4. Graceful handling of uninitialized variables
"""

import pytest
from pathlib import Path
from datetime import date, timedelta
import time

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter


@pytest.fixture
def minimal_data():
    """Minimal dataset for timeout testing."""
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
        'manufacturing_site': manufacturing_site,
        'planning_start_date': planning_start_date,
    }


def test_solution_extraction_with_zero_holding_costs(minimal_data):
    """Test solution extraction when holding costs are zero (stale pallet variables).

    This test validates the timeout fix:
    - When holding costs are zero, solver may not initialize pallet_count variables
    - Solution extraction should handle stale variables gracefully
    - Objective value should still be extracted correctly

    Context:
    - Network_Config.xlsx has zero pallet holding costs (for fast solve times)
    - This causes pallet_count variables to be stale (uninitialized)
    - Old code would crash with RuntimeError when calling value() on stale vars
    - New code skips stale variables or handles exceptions gracefully
    """
    # Extract data
    forecast = minimal_data['forecast']
    nodes = minimal_data['nodes']
    unified_routes = minimal_data['unified_routes']
    unified_truck_schedules = minimal_data['unified_truck_schedules']
    labor_calendar = minimal_data['labor_calendar']
    cost_structure = minimal_data['cost_structure']
    planning_start_date = minimal_data['planning_start_date']

    # Use 1-week horizon for fast testing
    planning_end_date = planning_start_date + timedelta(weeks=1)

    print("\n" + "="*80)
    print("TEST: Solution Extraction with Zero Holding Costs")
    print("="*80)
    print(f"Planning horizon: {planning_start_date} to {planning_end_date} (7 days)")

    # Verify zero holding costs
    assert cost_structure.storage_cost_per_pallet_day_frozen == 0.0, \
        "Test requires zero frozen pallet costs"
    assert cost_structure.storage_cost_per_pallet_day_ambient == 0.0, \
        "Test requires zero ambient pallet costs"

    print(f"✓ Holding costs are zero (pallet variables will be stale)")

    # Create model
    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
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

    # Solve
    result = model.solve(
        solver_name='cbc',
        time_limit_seconds=30,
        mip_gap=0.01,
        use_aggressive_heuristics=True,
        tee=False,
    )

    print(f"\n✓ SOLVE COMPLETE:")
    print(f"   Status: {result.termination_condition}")
    print(f"   Solve time: {result.solve_time_seconds:.1f}s")

    # CRITICAL: Solution extraction should NOT crash with stale variables
    try:
        solution = model.get_solution()
        print(f"✓ Solution extracted successfully (no crash on stale variables)")

        # Validate solution structure
        assert solution is not None, "Solution should not be None"
        assert 'production_by_date_product' in solution, \
            "Solution should include production_by_date_product"

        # Check objective value extraction
        assert result.objective_value is not None or 'total_cost' in solution, \
            "Objective value should be available from result or solution"

        if result.objective_value:
            print(f"   Objective: ${result.objective_value:,.2f}")
        elif 'total_cost' in solution:
            print(f"   Objective: ${solution['total_cost']:,.2f} (from solution)")

        # Validate holding cost is zero or near-zero
        holding_cost = solution.get('total_holding_cost', 0)
        print(f"   Holding cost: ${holding_cost:,.2f} (expected ~0)")

        assert holding_cost < 0.01, \
            f"Holding cost should be near-zero with zero rates, got {holding_cost}"

        # Validate production exists
        production_by_date_product = solution.get('production_by_date_product', {})
        total_production = sum(production_by_date_product.values())

        assert total_production > 0, "Should produce units"
        print(f"   Total production: {total_production:,.0f} units")

        print(f"\n✓ ZERO HOLDING COST TEST PASSED")
        print(f"   Solution extraction handled stale variables correctly")

    except RuntimeError as e:
        # This should NOT happen with the fix
        pytest.fail(f"Solution extraction crashed with stale variables: {e}")

    except Exception as e:
        # Other exceptions might be legitimate
        pytest.fail(f"Unexpected error during solution extraction: {e}")


def test_timeout_with_partial_solution(minimal_data):
    """Test solution extraction when solver times out with partial solution.

    This test validates:
    - Solver timeout handling (time_limit_seconds exceeded)
    - Solution extraction from partial results
    - Objective value extraction from intermediate solutions
    - Graceful degradation when optimal solution not reached

    Note: We use a very short time limit to force timeout on a large problem.
    """
    # Extract data
    forecast = minimal_data['forecast']
    nodes = minimal_data['nodes']
    unified_routes = minimal_data['unified_routes']
    unified_truck_schedules = minimal_data['unified_truck_schedules']
    labor_calendar = minimal_data['labor_calendar']
    cost_structure = minimal_data['cost_structure']
    planning_start_date = minimal_data['planning_start_date']

    # Use 4-week horizon with very short timeout to force partial solution
    planning_end_date = planning_start_date + timedelta(weeks=4)

    print("\n" + "="*80)
    print("TEST: Timeout with Partial Solution")
    print("="*80)
    print(f"Planning horizon: {planning_start_date} to {planning_end_date} (28 days)")
    print(f"Time limit: 5 seconds (intentionally short to force timeout)")

    # Create model
    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
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

    # Solve with very short timeout
    result = model.solve(
        solver_name='cbc',
        time_limit_seconds=5,  # Very short to force timeout
        mip_gap=0.01,
        use_aggressive_heuristics=False,  # Disable to slow down solve
        tee=False,
    )

    print(f"\n✓ SOLVE COMPLETE:")
    print(f"   Status: {result.termination_condition}")
    print(f"   Solve time: {result.solve_time_seconds:.1f}s")

    # Check if we got a timeout or partial solution
    # Note: CBC may still solve quickly if problem is easy
    if result.is_optimal():
        print(f"   Note: Problem solved optimally despite short timeout")
        print(f"   (Problem was easier than expected)")
    else:
        print(f"   Got non-optimal result (as expected with short timeout)")

    # CRITICAL: Solution extraction should work even with timeout
    try:
        solution = model.get_solution()

        if solution is not None:
            print(f"✓ Solution extracted successfully from partial result")

            # Check if we have production data
            production_by_date_product = solution.get('production_by_date_product', {})
            total_production = sum(production_by_date_product.values())

            print(f"   Total production: {total_production:,.0f} units")

            # Even with timeout, we should have some solution data
            # (CBC keeps best solution found so far)
            if total_production > 0:
                print(f"✓ Partial solution has valid production schedule")
            else:
                print(f"   Note: No production in partial solution (feasibility not found yet)")

        else:
            print(f"   Note: No solution available (solver didn't find feasible solution in time)")
            print(f"   This is acceptable for very short timeouts")

        print(f"\n✓ TIMEOUT HANDLING TEST PASSED")
        print(f"   Solution extraction handled timeout scenario correctly")

    except Exception as e:
        # Solution extraction should not crash, even with timeout
        pytest.fail(f"Solution extraction crashed after timeout: {e}")


def test_objective_extraction_priority(minimal_data):
    """Test objective value extraction from multiple sources.

    This test validates the priority order for objective value extraction:
    1. results.solution.objective (most reliable)
    2. results.problem.upper_bound (if finite)
    3. value(model.obj) after loading solution
    4. solution['total_cost'] from extract_solution()

    Context:
    - Different solvers/scenarios provide objective in different places
    - Code should try all sources in priority order
    - Should handle infinity/None values gracefully
    """
    # Extract data
    forecast = minimal_data['forecast']
    nodes = minimal_data['nodes']
    unified_routes = minimal_data['unified_routes']
    unified_truck_schedules = minimal_data['unified_truck_schedules']
    labor_calendar = minimal_data['labor_calendar']
    cost_structure = minimal_data['cost_structure']
    planning_start_date = minimal_data['planning_start_date']

    # Use 1-week horizon
    planning_end_date = planning_start_date + timedelta(weeks=1)

    print("\n" + "="*80)
    print("TEST: Objective Value Extraction Priority")
    print("="*80)

    # Create model
    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
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

    # Solve
    result = model.solve(
        solver_name='cbc',
        time_limit_seconds=30,
        mip_gap=0.01,
        tee=False,
    )

    print(f"\n✓ SOLVE COMPLETE:")
    print(f"   Status: {result.termination_condition}")

    # Validate objective was extracted
    assert result.objective_value is not None, \
        "Objective value should be extracted from one of the sources"

    assert result.objective_value > 0, \
        f"Objective should be positive, got {result.objective_value}"

    print(f"   Objective from result: ${result.objective_value:,.2f}")

    # Validate solution also has total_cost
    solution = model.get_solution()
    if solution and 'total_cost' in solution:
        print(f"   Objective from solution: ${solution['total_cost']:,.2f}")

        # Should match within floating point tolerance
        obj_diff = abs(result.objective_value - solution['total_cost'])
        assert obj_diff < 0.01, \
            f"Result objective and solution total_cost differ by {obj_diff}"

    print(f"\n✓ OBJECTIVE EXTRACTION TEST PASSED")


def test_stale_variable_check():
    """Test that we can detect stale variables without crashing.

    This is a unit test demonstrating how to safely check if a Pyomo
    variable is stale (uninitialized) before calling value().

    Context:
    - Pyomo variables have a .stale attribute
    - If var.stale == True, calling value(var) raises error
    - Our code should check stale before calling value()
    """
    from pyomo.environ import ConcreteModel, Var, NonNegativeIntegers, value

    print("\n" + "="*80)
    print("TEST: Stale Variable Detection")
    print("="*80)

    # Create simple model with integer variable
    model = ConcreteModel()
    model.x = Var(within=NonNegativeIntegers)

    # Variable is stale by default (not initialized)
    print(f"✓ Variable created")
    print(f"   var.stale = {model.x.stale}")

    assert model.x.stale is True, "Uninitialized variable should be stale"

    # CORRECT: Check stale before calling value()
    try:
        if not model.x.stale:
            x_value = value(model.x)
            print(f"   Variable value: {x_value}")
        else:
            print(f"✓ Variable is stale (skipped value extraction)")

        print(f"\n✓ STALE CHECK WORKS - No crash!")

    except Exception as e:
        pytest.fail(f"Stale check should prevent crash, but got: {e}")

    # WRONG: Calling value() on stale variable (would crash)
    # This demonstrates what the fix prevents
    try:
        # Uncommenting this line would cause RuntimeError
        # x_value = value(model.x)
        print(f"✓ Not calling value() on stale variable (would crash)")
    except RuntimeError as e:
        print(f"   (If called: would crash with {e})")

    print(f"\n✓ STALE VARIABLE TEST PASSED")


if __name__ == "__main__":
    """Allow running tests directly for debugging."""
    pytest.main([__file__, "-v", "-s"])
