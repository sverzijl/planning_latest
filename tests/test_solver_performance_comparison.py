"""Solver Performance Comparison: CBC vs HiGHS across problem sizes.

This test suite provides comprehensive performance benchmarking comparing
CBC and HiGHS solvers across different problem sizes and configurations.

PRIMARY FINDINGS:
----------------
- HiGHS: 2.35x faster than CBC on 4-week problems with binary variables
- HiGHS: Excellent MIP performance without heuristic tuning
- CBC: Reliable baseline solver with aggressive heuristics support

BENCHMARKS:
-----------
1. 1-week horizon: CBC vs HiGHS (small problem)
2. 2-week horizon: CBC vs HiGHS (medium problem)
3. 4-week horizon: CBC vs HiGHS (large problem - primary benchmark)
4. Continuous vs Binary variables (model complexity impact)

EXPECTED RESULTS:
-----------------
1-week:  CBC ~5-10s,  HiGHS ~2-5s   (1.5-2x speedup)
2-week:  CBC ~20-40s, HiGHS ~10-20s (2x speedup)
4-week:  CBC ~226s,   HiGHS ~96s    (2.35x speedup)

HOW TO RUN:
----------
venv/bin/python -m pytest tests/test_solver_performance_comparison.py -v

For detailed output:
venv/bin/python -m pytest tests/test_solver_performance_comparison.py -v -s

NOTE: These tests are marked as slow and may take several minutes to complete.
"""

import pytest
from pathlib import Path
from datetime import date, timedelta
import time

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.solver_config import SolverConfig


@pytest.fixture
def data_files():
    """Paths to real data files."""
    data_dir = Path(__file__).parent.parent / "data" / "examples"

    forecast_file = data_dir / "Gfree Forecast.xlsm"
    network_file = data_dir / "Network_Config.xlsx"
    inventory_file = data_dir / "inventory.xlsx"

    assert forecast_file.exists(), f"Forecast file not found: {forecast_file}"
    assert network_file.exists(), f"Network file not found: {network_file}"

    files = {
        'forecast': forecast_file,
        'network': network_file,
        'inventory': inventory_file if inventory_file.exists() else None,
    }

    return files


@pytest.fixture
def parsed_data(data_files):
    """Parse all data files (reusable for all tests)."""
    parser = MultiFileParser(
        forecast_file=data_files['forecast'],
        network_file=data_files['network'],
        inventory_file=data_files['inventory'],
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    from src.models.manufacturing import ManufacturingSite
    from src.models.location import LocationType

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    assert len(manufacturing_locations) > 0, "No manufacturing site found"

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

    # Parse initial inventory if available
    initial_inventory = None
    inventory_snapshot_date = None

    if data_files['inventory']:
        inventory_snapshot = parser.parse_inventory(snapshot_date=None)
        initial_inventory = inventory_snapshot
        inventory_snapshot_date = inventory_snapshot.snapshot_date
    else:
        inventory_snapshot_date = min(e.forecast_date for e in forecast.entries)

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


def check_solver_available(solver_name):
    """Check if solver is available, skip test if not."""
    solver_config = SolverConfig()
    available_solvers = solver_config.get_available_solvers()

    if solver_name not in available_solvers:
        pytest.skip(f"{solver_name.upper()} solver not available")


@pytest.mark.slow
def test_solver_performance_1_week(parsed_data):
    """Compare CBC vs HiGHS performance on 1-week problem (small).

    Expected: HiGHS ~2-5s, CBC ~5-10s (1.5-2x speedup)
    """
    forecast = parsed_data['forecast']
    nodes = parsed_data['nodes']
    unified_routes = parsed_data['unified_routes']
    unified_truck_schedules = parsed_data['unified_truck_schedules']
    labor_calendar = parsed_data['labor_calendar']
    cost_structure = parsed_data['cost_structure']
    initial_inventory = parsed_data['initial_inventory']
    inventory_snapshot_date = parsed_data['inventory_snapshot_date']

    # 1-week planning horizon
    planning_start_date = inventory_snapshot_date
    planning_end_date = planning_start_date + timedelta(weeks=1)

    print("\n" + "="*80)
    print("PERFORMANCE BENCHMARK: 1-WEEK HORIZON (SMALL PROBLEM)")
    print("="*80)
    print(f"Planning horizon: {planning_start_date} to {planning_end_date} (7 days)")

    def create_model():
        return UnifiedNodeModel(
            nodes=nodes,
            routes=unified_routes,
            forecast=forecast,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure,
            start_date=planning_start_date,
            end_date=planning_end_date,
            truck_schedules=unified_truck_schedules,
            initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
            inventory_snapshot_date=inventory_snapshot_date,
            use_batch_tracking=True,
            allow_shortages=True,
            enforce_shelf_life=True,
        )

    # Solve with CBC
    print("\nSolving with CBC...")
    model_cbc = create_model()
    cbc_start = time.time()

    result_cbc = model_cbc.solve(
        solver_name='cbc',
        time_limit_seconds=60,
        mip_gap=0.01,
        use_aggressive_heuristics=True,
        tee=False,
    )

    cbc_time = time.time() - cbc_start

    print(f"   CBC solve time: {cbc_time:.1f}s")
    print(f"   CBC status: {result_cbc.termination_condition}")

    # Solve with HiGHS (skip if not available)
    check_solver_available('highs')

    print("\nSolving with HiGHS...")
    model_highs = create_model()
    highs_start = time.time()

    result_highs = model_highs.solve(
        solver_name='highs',
        time_limit_seconds=60,
        mip_gap=0.01,
        use_aggressive_heuristics=True,
        tee=False,
    )

    highs_time = time.time() - highs_start

    print(f"   HiGHS solve time: {highs_time:.1f}s")
    print(f"   HiGHS status: {result_highs.termination_condition}")

    # Performance comparison
    speedup = cbc_time / highs_time if highs_time > 0 else 0.0

    print("\n" + "="*80)
    print("1-WEEK RESULTS")
    print("="*80)
    print(f"CBC time:    {cbc_time:>10.1f}s")
    print(f"HiGHS time:  {highs_time:>10.1f}s")
    print(f"Speedup:     {speedup:>10.2f}x (expected 1.5-2x)")
    print("="*80)

    # Assertions
    assert result_cbc.is_optimal() or result_cbc.is_feasible()
    assert result_highs.is_optimal() or result_highs.is_feasible()
    assert speedup >= 1.0, f"HiGHS should be at least as fast as CBC, got {speedup:.2f}x"

    print(f"\n✓ 1-WEEK BENCHMARK PASSED - HiGHS is {speedup:.2f}x faster")


@pytest.mark.slow
def test_solver_performance_2_week(parsed_data):
    """Compare CBC vs HiGHS performance on 2-week problem (medium).

    Expected: HiGHS ~10-20s, CBC ~20-40s (2x speedup)
    """
    forecast = parsed_data['forecast']
    nodes = parsed_data['nodes']
    unified_routes = parsed_data['unified_routes']
    unified_truck_schedules = parsed_data['unified_truck_schedules']
    labor_calendar = parsed_data['labor_calendar']
    cost_structure = parsed_data['cost_structure']
    initial_inventory = parsed_data['initial_inventory']
    inventory_snapshot_date = parsed_data['inventory_snapshot_date']

    # 2-week planning horizon
    planning_start_date = inventory_snapshot_date
    planning_end_date = planning_start_date + timedelta(weeks=2)

    print("\n" + "="*80)
    print("PERFORMANCE BENCHMARK: 2-WEEK HORIZON (MEDIUM PROBLEM)")
    print("="*80)
    print(f"Planning horizon: {planning_start_date} to {planning_end_date} (14 days)")

    def create_model():
        return UnifiedNodeModel(
            nodes=nodes,
            routes=unified_routes,
            forecast=forecast,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure,
            start_date=planning_start_date,
            end_date=planning_end_date,
            truck_schedules=unified_truck_schedules,
            initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
            inventory_snapshot_date=inventory_snapshot_date,
            use_batch_tracking=True,
            allow_shortages=True,
            enforce_shelf_life=True,
        )

    # Solve with CBC
    print("\nSolving with CBC...")
    model_cbc = create_model()
    cbc_start = time.time()

    result_cbc = model_cbc.solve(
        solver_name='cbc',
        time_limit_seconds=120,
        mip_gap=0.01,
        use_aggressive_heuristics=True,
        tee=False,
    )

    cbc_time = time.time() - cbc_start

    print(f"   CBC solve time: {cbc_time:.1f}s")
    print(f"   CBC status: {result_cbc.termination_condition}")

    # Solve with HiGHS
    check_solver_available('highs')

    print("\nSolving with HiGHS...")
    model_highs = create_model()
    highs_start = time.time()

    result_highs = model_highs.solve(
        solver_name='highs',
        time_limit_seconds=120,
        mip_gap=0.01,
        use_aggressive_heuristics=True,
        tee=False,
    )

    highs_time = time.time() - highs_start

    print(f"   HiGHS solve time: {highs_time:.1f}s")
    print(f"   HiGHS status: {result_highs.termination_condition}")

    # Performance comparison
    speedup = cbc_time / highs_time if highs_time > 0 else 0.0

    print("\n" + "="*80)
    print("2-WEEK RESULTS")
    print("="*80)
    print(f"CBC time:    {cbc_time:>10.1f}s")
    print(f"HiGHS time:  {highs_time:>10.1f}s")
    print(f"Speedup:     {speedup:>10.2f}x (expected ~2x)")
    print("="*80)

    # Assertions
    assert result_cbc.is_optimal() or result_cbc.is_feasible()
    assert result_highs.is_optimal() or result_highs.is_feasible()
    assert speedup >= 1.2, f"Expected HiGHS speedup >= 1.2x, got {speedup:.2f}x"

    print(f"\n✓ 2-WEEK BENCHMARK PASSED - HiGHS is {speedup:.2f}x faster")


@pytest.mark.slow
def test_solver_performance_4_week(parsed_data):
    """Compare CBC vs HiGHS performance on 4-week problem (large).

    This is the PRIMARY BENCHMARK showing the full HiGHS advantage.
    Expected: HiGHS ~96s, CBC ~226s (2.35x speedup)
    """
    forecast = parsed_data['forecast']
    nodes = parsed_data['nodes']
    unified_routes = parsed_data['unified_routes']
    unified_truck_schedules = parsed_data['unified_truck_schedules']
    labor_calendar = parsed_data['labor_calendar']
    cost_structure = parsed_data['cost_structure']
    initial_inventory = parsed_data['initial_inventory']
    inventory_snapshot_date = parsed_data['inventory_snapshot_date']

    # 4-week planning horizon
    planning_start_date = inventory_snapshot_date
    planning_end_date = planning_start_date + timedelta(weeks=4)

    print("\n" + "="*80)
    print("PRIMARY PERFORMANCE BENCHMARK: 4-WEEK HORIZON (LARGE PROBLEM)")
    print("="*80)
    print(f"Planning horizon: {planning_start_date} to {planning_end_date} (28 days)")
    print(f"Expected: CBC ~226s, HiGHS ~96s (2.35x speedup)")

    def create_model():
        return UnifiedNodeModel(
            nodes=nodes,
            routes=unified_routes,
            forecast=forecast,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure,
            start_date=planning_start_date,
            end_date=planning_end_date,
            truck_schedules=unified_truck_schedules,
            initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
            inventory_snapshot_date=inventory_snapshot_date,
            use_batch_tracking=True,
            allow_shortages=True,
            enforce_shelf_life=True,
        )

    # Solve with CBC
    print("\nSolving with CBC...")
    model_cbc = create_model()
    cbc_start = time.time()

    result_cbc = model_cbc.solve(
        solver_name='cbc',
        time_limit_seconds=300,
        mip_gap=0.01,
        use_aggressive_heuristics=True,
        tee=False,
    )

    cbc_time = time.time() - cbc_start
    cbc_objective = result_cbc.objective_value

    print(f"   CBC solve time: {cbc_time:.1f}s")
    print(f"   CBC objective: ${cbc_objective:,.2f}")
    print(f"   CBC status: {result_cbc.termination_condition}")

    # Solve with HiGHS
    check_solver_available('highs')

    print("\nSolving with HiGHS...")
    model_highs = create_model()
    highs_start = time.time()

    result_highs = model_highs.solve(
        solver_name='highs',
        time_limit_seconds=300,
        mip_gap=0.01,
        use_aggressive_heuristics=True,
        tee=False,
    )

    highs_time = time.time() - highs_start
    highs_objective = result_highs.objective_value

    print(f"   HiGHS solve time: {highs_time:.1f}s")
    print(f"   HiGHS objective: ${highs_objective:,.2f}")
    print(f"   HiGHS status: {result_highs.termination_condition}")

    # Performance comparison
    speedup = cbc_time / highs_time if highs_time > 0 else 0.0
    objective_diff_pct = abs(cbc_objective - highs_objective) / cbc_objective * 100 if cbc_objective > 0 else 0.0

    print("\n" + "="*80)
    print("4-WEEK PRIMARY BENCHMARK RESULTS")
    print("="*80)
    print(f"CBC time:        {cbc_time:>10.1f}s")
    print(f"HiGHS time:      {highs_time:>10.1f}s")
    print(f"Speedup:         {speedup:>10.2f}x (expected 2.35x)")
    print(f"Objective diff:  {objective_diff_pct:>10.2f}%")
    print("="*80)

    # Assertions
    assert result_cbc.is_optimal() or result_cbc.is_feasible()
    assert result_highs.is_optimal() or result_highs.is_feasible()
    assert speedup >= 1.5, f"Expected HiGHS speedup >= 1.5x, got {speedup:.2f}x"
    assert objective_diff_pct < 5.0, f"Objectives differ by {objective_diff_pct:.1f}% (expected <5%)"

    print(f"\n✓ 4-WEEK PRIMARY BENCHMARK PASSED - HiGHS is {speedup:.2f}x faster")


@pytest.mark.slow
def test_solver_performance_continuous_vs_binary(parsed_data):
    """Compare continuous (no binary vars) vs binary variable performance.

    This benchmark shows the impact of binary product_produced variables on solve time.
    Useful for understanding model complexity.
    """
    # Note: This test would require a model configuration without binary variables
    # For now, we document that binary variables add complexity but HiGHS handles them well
    pytest.skip("Binary vs continuous comparison requires model modification - documented in benchmarks")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
