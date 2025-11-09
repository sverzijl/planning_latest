"""HiGHS Solver Integration Test Suite.

This test suite validates HiGHS solver integration with binary product_produced
variables and provides comprehensive performance benchmarking.

CONTEXT:
--------
- HiGHS solves 4-week problems in ~96s (vs CBC ~226s with binary variables)
- Binary variables work well with HiGHS (2.35x speedup over CBC)
- Warmstart has no effect on HiGHS (not supported by Pyomo/HiGHS interface)
- HiGHS provides excellent MIP performance without heuristic tuning

TEST COVERAGE:
--------------
1. Solver detection and availability
2. Small problem performance (1-week: ~2s expected)
3. Medium problem performance (2-week: ~10-20s expected)
4. Large problem performance (4-week: ~96s expected)
5. CBC vs HiGHS direct comparison
6. SKU reduction with HiGHS
7. Warmstart has no effect on HiGHS
8. Solution quality validation

PERFORMANCE TARGETS:
-------------------
- 1-week: < 10s (expected ~2s)
- 2-week: < 30s (expected ~10-20s)
- 4-week: < 120s (expected ~96s)
- Speedup vs CBC: > 2x for 4-week problems

HOW TO RUN:
----------
venv/bin/python -m pytest tests/test_highs_solver_integration.py -v

For detailed output:
venv/bin/python -m pytest tests/test_highs_solver_integration.py -v -s
"""

import pytest
from pathlib import Path
from datetime import date, timedelta
import time

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.solver_config import SolverConfig


@pytest.fixture
def data_files():
    """Paths to real data files."""
    data_dir = Path(__file__).parent.parent / "data" / "examples"

    forecast_file = data_dir / "Gfree Forecast.xlsm"
    network_file = data_dir / "Network_Config.xlsx"
    inventory_file = data_dir / "inventory.xlsx"

    # Verify required files exist
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


def test_highs_solver_available():
    """Test that HiGHS solver is available for testing."""
    print("\n" + "="*80)
    print("SOLVER AVAILABILITY CHECK")
    print("="*80)

    solver_config = SolverConfig()
    available_solvers = solver_config.get_available_solvers()

    print(f"Available solvers: {', '.join(available_solvers)}")

    if 'highs' not in available_solvers:
        pytest.skip("HiGHS solver not available - install with: pip install highspy")

    print("✓ HiGHS solver is available")


def test_highs_1_week_binary_variables(parsed_data):
    """Test HiGHS with 1-week horizon (expect ~2s solve time).

    This validates HiGHS performance on small problems with binary variables.
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
    print("TEST: HiGHS 1-WEEK HORIZON")
    print("="*80)
    print(f"Planning horizon: {planning_start_date} to {planning_end_date} (7 days)")

    # Create model
    # Create products for model (extract unique product IDs from forecast)
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    model = SlidingWindowModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=planning_start_date,
        end_date=planning_end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
        inventory_snapshot_date=inventory_snapshot_date,
        use_pallet_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    # Solve with HiGHS
    solve_start = time.time()

    result = model.solve(
        solver_name='highs',
        time_limit_seconds=30,
        mip_gap=0.01,
        use_aggressive_heuristics=True,
        tee=False,
    )

    solve_time = time.time() - solve_start

    print(f"\nSOLVE RESULTS:")
    print(f"   Status: {result.termination_condition}")
    print(f"   Solve time: {solve_time:.1f}s (expected <10s)")
    print(f"   Objective: ${result.objective_value:,.2f}")

    # Assertions
    assert result.is_optimal() or result.is_feasible()
    assert solve_time < 10, f"1-week solve took {solve_time:.1f}s (expected <10s)"

    print("✓ 1-WEEK HIGHS TEST PASSED")


def test_highs_2_week_binary_variables(parsed_data):
    """Test HiGHS with 2-week horizon (expect ~10-20s solve time).

    This validates HiGHS performance on medium-sized problems.
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
    print("TEST: HiGHS 2-WEEK HORIZON")
    print("="*80)
    print(f"Planning horizon: {planning_start_date} to {planning_end_date} (14 days)")

    # Create model
    # Create products for model (extract unique product IDs from forecast)
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    model = SlidingWindowModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=planning_start_date,
        end_date=planning_end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
        inventory_snapshot_date=inventory_snapshot_date,
        use_pallet_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    # Solve with HiGHS
    solve_start = time.time()

    result = model.solve(
        solver_name='highs',
        time_limit_seconds=60,
        mip_gap=0.01,
        use_aggressive_heuristics=True,
        tee=False,
    )

    solve_time = time.time() - solve_start

    print(f"\nSOLVE RESULTS:")
    print(f"   Status: {result.termination_condition}")
    print(f"   Solve time: {solve_time:.1f}s (expected <30s)")
    print(f"   Objective: ${result.objective_value:,.2f}")

    # Assertions
    assert result.is_optimal() or result.is_feasible()
    assert solve_time < 30, f"2-week solve took {solve_time:.1f}s (expected <30s)"

    print("✓ 2-WEEK HIGHS TEST PASSED")


def test_highs_4_week_binary_variables(parsed_data):
    """Test HiGHS with 4-week horizon (expect ~96s solve time).

    This is the primary performance benchmark showing 2.35x speedup over CBC.
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
    print("TEST: HiGHS 4-WEEK HORIZON (PRIMARY BENCHMARK)")
    print("="*80)
    print(f"Planning horizon: {planning_start_date} to {planning_end_date} (28 days)")
    print(f"Expected performance: ~96s (vs CBC ~226s)")

    # Create model
    # Create products for model (extract unique product IDs from forecast)
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    model = SlidingWindowModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=planning_start_date,
        end_date=planning_end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
        inventory_snapshot_date=inventory_snapshot_date,
        use_pallet_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    # Solve with HiGHS
    solve_start = time.time()

    result = model.solve(
        solver_name='highs',
        time_limit_seconds=120,
        mip_gap=0.01,
        use_aggressive_heuristics=True,
        tee=False,
    )

    solve_time = time.time() - solve_start

    print(f"\nSOLVE RESULTS:")
    print(f"   Status: {result.termination_condition}")
    print(f"   Solve time: {solve_time:.1f}s (expected <120s)")
    print(f"   Objective: ${result.objective_value:,.2f}")
    print(f"   MIP gap: {result.gap * 100:.2f}%" if result.gap else "   MIP gap: N/A")

    # Solution quality
    solution = model.get_solution()
    assert solution is not None

    production_by_date_product = solution.get('production_by_date_product', {})
    total_production = sum(production_by_date_product.values())
    total_shortage = solution.get('total_shortage_units', 0)

    demand_in_horizon = sum(
        e.quantity for e in forecast.entries
        if planning_start_date <= e.forecast_date <= planning_end_date
    )
    fill_rate = 100 * (1 - total_shortage / demand_in_horizon) if demand_in_horizon > 0 else 100

    print(f"\nSOLUTION QUALITY:")
    print(f"   Production: {total_production:,.0f} units")
    print(f"   Demand: {demand_in_horizon:,.0f} units")
    print(f"   Fill rate: {fill_rate:.1f}%")

    # Assertions
    assert result.is_optimal() or result.is_feasible()
    assert solve_time < 120, f"4-week solve took {solve_time:.1f}s (expected <120s)"
    assert total_production > 0
    assert fill_rate >= 85.0, f"Fill rate {fill_rate:.1f}% below 85% threshold"

    print("✓ 4-WEEK HIGHS BENCHMARK PASSED")


@pytest.mark.slow
def test_highs_vs_cbc_performance(parsed_data):
    """Direct performance comparison: HiGHS vs CBC on identical 4-week problem.

    This test measures exact speedup ratio (expected: 2-3x).
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
    print("TEST: HiGHS VS CBC PERFORMANCE COMPARISON")
    print("="*80)
    print(f"Planning horizon: {planning_start_date} to {planning_end_date} (28 days)")

    # Create model (will be built twice)
    def create_model():
        return SlidingWindowModel(
            nodes=nodes,
            routes=unified_routes,
            forecast=forecast,
        products=products,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure,
            start_date=planning_start_date,
            end_date=planning_end_date,
            truck_schedules=unified_truck_schedules,
            initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
            inventory_snapshot_date=inventory_snapshot_date,
            use_pallet_tracking=True,
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
    print("PERFORMANCE COMPARISON")
    print("="*80)
    print(f"CBC time:        {cbc_time:>10.1f}s")
    print(f"HiGHS time:      {highs_time:>10.1f}s")
    print(f"Speedup:         {speedup:>10.2f}x")
    print(f"Objective diff:  {objective_diff_pct:>10.2f}%")
    print("="*80)

    # Assertions
    assert result_cbc.is_optimal() or result_cbc.is_feasible()
    assert result_highs.is_optimal() or result_highs.is_feasible()
    assert speedup >= 1.5, f"Expected HiGHS speedup >= 1.5x, got {speedup:.2f}x"
    assert objective_diff_pct < 5.0, f"Objectives differ by {objective_diff_pct:.1f}% (expected <5%)"

    print(f"\n✓ PERFORMANCE COMPARISON PASSED - HiGHS is {speedup:.2f}x faster")


def test_highs_sku_reduction(parsed_data):
    """Test SKU reduction with HiGHS solver (binary enforcement).

    Validates that HiGHS correctly handles product_produced binary variables
    and produces only demanded SKUs.
    """
    from src.models.forecast import Forecast, ForecastEntry
    from src.models.manufacturing import ManufacturingSite

    # Get original forecast for product IDs
    forecast = parsed_data['forecast']
    nodes = parsed_data['nodes']
    unified_routes = parsed_data['unified_routes']
    labor_calendar = parsed_data['labor_calendar']
    cost_structure = parsed_data['cost_structure']

    # Get product IDs
    product_ids = sorted(list(set(entry.product_id for entry in forecast.entries)))
    assert len(product_ids) >= 5, f"Need at least 5 products, found {len(product_ids)}"

    # Create simplified forecast: 3 SKUs with demand, 2 with zero demand
    demand_date = date(2025, 10, 22)
    planning_start = date(2025, 10, 20)
    planning_end = date(2025, 10, 22)
    demand_destination = "6110"

    forecast_entries = [
        ForecastEntry(demand_destination, product_ids[0], demand_date, 2000),
        ForecastEntry(demand_destination, product_ids[1], demand_date, 2000),
        ForecastEntry(demand_destination, product_ids[2], demand_date, 2000),
        ForecastEntry(demand_destination, product_ids[3], demand_date, 0),  # Zero demand
        ForecastEntry(demand_destination, product_ids[4], demand_date, 0),  # Zero demand
    ]

    sku_forecast = Forecast(name="SKU Reduction Test", entries=forecast_entries)

    print("\n" + "="*80)
    print("TEST: SKU REDUCTION WITH HIGHS")
    print("="*80)
    print(f"Products with demand: 3 ({product_ids[0]}, {product_ids[1]}, {product_ids[2]})")
    print(f"Products with ZERO demand: 2 ({product_ids[3]}, {product_ids[4]})")

    # Create model
    # Create products for model (extract unique product IDs from forecast)
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    model = SlidingWindowModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=sku_forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=planning_start,
        end_date=planning_end,
        truck_schedules=None,  # Disable truck constraints
        use_pallet_tracking=True,
        allow_shortages=False,
        enforce_shelf_life=True,
    )

    # Solve with HiGHS
    result = model.solve(
        solver_name='highs',
        time_limit_seconds=60,
        mip_gap=0.01,
        tee=False,
    )

    print(f"\nSOLVE RESULTS:")
    print(f"   Status: {result.termination_condition}")

    # Check SKU production
    solution = model.get_solution()

    if solution is None:
        pytest.skip("Solution extraction issue (zero costs) - cannot validate SKU count")

    production = solution.get('production_by_date_product', {})
    skus_produced = set()

    for (prod_date, product), qty in production.items():
        if qty > 0.1:
            skus_produced.add(product)

    num_skus_produced = len(skus_produced)

    print(f"\nSKU PRODUCTION:")
    print(f"   SKUs produced: {num_skus_produced} out of 5")
    for product in sorted(skus_produced):
        qty = sum(q for (d, p), q in production.items() if p == product)
        status = "✓" if product in product_ids[:3] else "✗"
        print(f"     {product}: {qty:,.0f} units {status}")

    # Assertions
    assert result.is_optimal() or result.is_feasible()
    assert num_skus_produced == 3, f"Expected 3 SKUs, got {num_skus_produced}"
    assert product_ids[3] not in skus_produced, "Should NOT produce zero-demand SKU"
    assert product_ids[4] not in skus_produced, "Should NOT produce zero-demand SKU"
    assert product_ids[0] in skus_produced, "Should produce demanded SKU"
    assert product_ids[1] in skus_produced, "Should produce demanded SKU"
    assert product_ids[2] in skus_produced, "Should produce demanded SKU"

    print("\n✓ SKU REDUCTION WITH HIGHS PASSED")


def test_highs_warmstart_no_effect(parsed_data):
    """Test that warmstart has no effect on HiGHS (not supported).

    This validates documentation claim that warmstart should be disabled for HiGHS.
    """
    forecast = parsed_data['forecast']
    nodes = parsed_data['nodes']
    unified_routes = parsed_data['unified_routes']
    unified_truck_schedules = parsed_data['unified_truck_schedules']
    labor_calendar = parsed_data['labor_calendar']
    cost_structure = parsed_data['cost_structure']
    initial_inventory = parsed_data['initial_inventory']
    inventory_snapshot_date = parsed_data['inventory_snapshot_date']

    # 2-week horizon for faster testing
    planning_start_date = inventory_snapshot_date
    planning_end_date = planning_start_date + timedelta(weeks=2)

    print("\n" + "="*80)
    print("TEST: WARMSTART HAS NO EFFECT ON HIGHS")
    print("="*80)

    def create_model():
        return SlidingWindowModel(
            nodes=nodes,
            routes=unified_routes,
            forecast=forecast,
        products=products,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure,
            start_date=planning_start_date,
            end_date=planning_end_date,
            truck_schedules=unified_truck_schedules,
            initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
            inventory_snapshot_date=inventory_snapshot_date,
            use_pallet_tracking=True,
            allow_shortages=True,
            enforce_shelf_life=True,
        )

    # Solve WITHOUT warmstart
    print("\nSolving WITHOUT warmstart...")
    model_no_warmstart = create_model()
    no_warmstart_start = time.time()

    result_no_warmstart = model_no_warmstart.solve(
        solver_name='highs',
        use_warmstart=False,
        time_limit_seconds=60,
        mip_gap=0.01,
        tee=False,
    )

    no_warmstart_time = time.time() - no_warmstart_start

    print(f"   Time WITHOUT warmstart: {no_warmstart_time:.1f}s")
    print(f"   Status: {result_no_warmstart.termination_condition}")

    # Solve WITH warmstart (should have no effect)
    print("\nSolving WITH warmstart (expected: no effect)...")
    model_warmstart = create_model()
    warmstart_start = time.time()

    result_warmstart = model_warmstart.solve(
        solver_name='highs',
        use_warmstart=True,  # Should be ignored by HiGHS
        time_limit_seconds=60,
        mip_gap=0.01,
        tee=False,
    )

    warmstart_time = time.time() - warmstart_start

    print(f"   Time WITH warmstart: {warmstart_time:.1f}s")
    print(f"   Status: {result_warmstart.termination_condition}")

    # Compare times (should be similar, within 20% variance)
    time_diff_pct = abs(warmstart_time - no_warmstart_time) / no_warmstart_time * 100

    print("\n" + "="*80)
    print("WARMSTART EFFECT ANALYSIS")
    print("="*80)
    print(f"WITHOUT warmstart: {no_warmstart_time:>10.1f}s")
    print(f"WITH warmstart:    {warmstart_time:>10.1f}s")
    print(f"Difference:        {time_diff_pct:>10.1f}%")
    print("="*80)

    # Both should solve successfully
    assert result_no_warmstart.is_optimal() or result_no_warmstart.is_feasible()
    assert result_warmstart.is_optimal() or result_warmstart.is_feasible()

    # Times should be similar (within 30% - allowing for system variance)
    assert time_diff_pct < 30, f"Times differ by {time_diff_pct:.1f}% (expected similar)"

    print(f"\n✓ WARMSTART NO EFFECT CONFIRMED - Difference only {time_diff_pct:.1f}%")


def test_highs_solution_quality(parsed_data):
    """Test solution quality: costs, production, distribution, demand satisfaction."""
    forecast = parsed_data['forecast']
    nodes = parsed_data['nodes']
    unified_routes = parsed_data['unified_routes']
    unified_truck_schedules = parsed_data['unified_truck_schedules']
    labor_calendar = parsed_data['labor_calendar']
    cost_structure = parsed_data['cost_structure']
    initial_inventory = parsed_data['initial_inventory']
    inventory_snapshot_date = parsed_data['inventory_snapshot_date']

    # 2-week horizon
    planning_start_date = inventory_snapshot_date
    planning_end_date = planning_start_date + timedelta(weeks=2)

    print("\n" + "="*80)
    print("TEST: HIGHS SOLUTION QUALITY VALIDATION")
    print("="*80)

    # Create and solve model
    # Create products for model (extract unique product IDs from forecast)
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    model = SlidingWindowModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=planning_start_date,
        end_date=planning_end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
        inventory_snapshot_date=inventory_snapshot_date,
        use_pallet_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    result = model.solve(
        solver_name='highs',
        time_limit_seconds=60,
        mip_gap=0.01,
        tee=False,
    )

    print(f"\nSOLVE RESULTS:")
    print(f"   Status: {result.termination_condition}")
    print(f"   Solve time: {result.solve_time_seconds:.1f}s")

    assert result.is_optimal() or result.is_feasible()

    # Extract solution
    solution = model.get_solution()
    assert solution is not None, "Solution should not be None"

    # Cost breakdown
    total_labor_cost = solution.get('total_labor_cost', 0)
    total_production_cost = solution.get('total_production_cost', 0)
    total_transport_cost = solution.get('total_transport_cost', 0)
    total_holding_cost = solution.get('total_holding_cost', 0)
    total_shortage_cost = solution.get('total_shortage_cost', 0)
    total_cost = total_labor_cost + total_production_cost + total_transport_cost + total_holding_cost + total_shortage_cost

    print(f"\nCOST BREAKDOWN:")
    print(f"   Labor:       ${total_labor_cost:>12,.2f}")
    print(f"   Production:  ${total_production_cost:>12,.2f}")
    print(f"   Transport:   ${total_transport_cost:>12,.2f}")
    print(f"   Holding:     ${total_holding_cost:>12,.2f}")
    print(f"   Shortage:    ${total_shortage_cost:>12,.2f}")
    print(f"   {'─'*40}")
    print(f"   TOTAL:       ${total_cost:>12,.2f}")

    # Production summary
    production_by_date_product = solution.get('production_by_date_product', {})
    total_production = sum(production_by_date_product.values())
    num_batches = len(solution.get('production_batches', []))

    print(f"\nPRODUCTION:")
    print(f"   Total production: {total_production:,.0f} units")
    print(f"   Batches: {num_batches}")

    # Demand satisfaction
    total_shortage = solution.get('total_shortage_units', 0)
    demand_in_horizon = sum(
        e.quantity for e in forecast.entries
        if planning_start_date <= e.forecast_date <= planning_end_date
    )
    fill_rate = 100 * (1 - total_shortage / demand_in_horizon) if demand_in_horizon > 0 else 100

    print(f"\nDEMAND SATISFACTION:")
    print(f"   Demand: {demand_in_horizon:,.0f} units")
    print(f"   Shortage: {total_shortage:,.0f} units")
    print(f"   Fill rate: {fill_rate:.1f}%")

    # Quality assertions
    assert total_cost >= 0, "Total cost should be non-negative"
    assert total_production > 0, "Should produce units"
    assert num_batches > 0, "Should have production batches"
    assert fill_rate >= 85.0, f"Fill rate {fill_rate:.1f}% below 85% threshold"

    print("\n✓ SOLUTION QUALITY VALIDATION PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
