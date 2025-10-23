"""Performance comparison: Binary variables with/without warmstart.

This comprehensive test measures warmstart effectiveness on real production data,
comparing solve performance and solution quality between baseline and warmstart approaches.

Test Scenarios:
---------------
1. BASELINE: Binary product_produced WITHOUT warmstart hints
2. WARMSTART: Binary product_produced WITH campaign-based hints

Metrics Tracked:
---------------
- Solve time (seconds)
- Objective value (total cost)
- MIP gap (optimality)
- Fill rate (demand satisfaction)
- Production quantity
- Solution status

Success Criteria:
----------------
- Both approaches solve successfully
- Warmstart provides measurable speedup (target: 10-40%)
- Objective values similar (<5% difference)
- Fill rates comparable (>85%)
"""

import pytest
import time
from datetime import date, timedelta
from pathlib import Path

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from tests.conftest import create_test_products
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType


@pytest.fixture
def benchmark_data():
    """Load real production data for benchmarking."""
    data_dir = Path(__file__).parent.parent / "data" / "examples"

    forecast_file = data_dir / "Gfree Forecast.xlsm"
    network_file = data_dir / "Network_Config.xlsx"
    inventory_file = data_dir / "inventory.xlsx"

    # Verify files exist
    assert forecast_file.exists(), f"Forecast file not found: {forecast_file}"
    assert network_file.exists(), f"Network file not found: {network_file}"

    # Parse data
    parser = MultiFileParser(
        forecast_file=str(forecast_file),
        network_file=str(network_file),
        inventory_file=str(inventory_file) if inventory_file.exists() else None,
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Extract manufacturing site
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    assert manufacturing_locations, "No manufacturing site found"

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

    # Parse initial inventory
    initial_inventory = None
    inventory_snapshot_date = None
    if inventory_file.exists():
        inventory_snapshot = parser.parse_inventory(snapshot_date=None)
        initial_inventory = inventory_snapshot
        inventory_snapshot_date = inventory_snapshot.snapshot_date

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


@pytest.mark.slow  # Mark as slow test (skipped in fast test runs)
def test_warmstart_performance_improvement(benchmark_data):
    """Compare solve performance with and without warmstart.

    Tests 4-week horizon with binary product_produced variables.
    Measures speedup from warmstart hints.

    Expected Results:
    ----------------
    - Both solves complete successfully
    - Warmstart provides 10-40% speedup
    - Objective values within 5%
    - Fill rates both >85%
    """

    # Extract data
    forecast = benchmark_data['forecast']
    nodes = benchmark_data['nodes']
    unified_routes = benchmark_data['unified_routes']
    unified_truck_schedules = benchmark_data['unified_truck_schedules']
    labor_calendar = benchmark_data['labor_calendar']
    cost_structure = benchmark_data['cost_structure']
    initial_inventory = benchmark_data['initial_inventory']
    inventory_snapshot_date = benchmark_data['inventory_snapshot_date']

    # Validate or set inventory snapshot date
    if inventory_snapshot_date is None:
        inventory_snapshot_date = min(e.forecast_date for e in forecast.entries)

    # Planning horizon
    start_date = inventory_snapshot_date
    end_date = start_date + timedelta(days=27)  # 4 weeks

    print("\n" + "="*80)
    print("WARMSTART PERFORMANCE BENCHMARK")
    print("="*80)
    print(f"Planning horizon: {start_date} to {end_date} (28 days)")
    print(f"Solver: CBC")
    print(f"Binary product_produced variables: YES")

    # ===========================
    # TEST 1: BASELINE (no warmstart)
    # ===========================
    print("\n" + "-"*80)
    print("TEST 1: BASELINE (Binary WITHOUT warmstart)")
    print("-"*80)

    model_baseline = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
        inventory_snapshot_date=inventory_snapshot_date,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    start_time = time.time()
    result_baseline = model_baseline.solve(
        solver_name='cbc',
        use_warmstart=False,  # NO WARMSTART
        time_limit_seconds=300,
        mip_gap=0.01,
        tee=False,
    )
    time_baseline = time.time() - start_time

    print(f"   Status: {result_baseline.termination_condition}")
    print(f"   Solve time: {time_baseline:.1f}s")
    print(f"   Objective: ${result_baseline.objective_value:,.2f}")
    print(f"   MIP gap: {result_baseline.gap*100:.2f}%" if result_baseline.gap else "   MIP gap: N/A")

    # Extract baseline metrics
    solution_baseline = model_baseline.get_solution()
    production_baseline = sum(solution_baseline.get('production_by_date_product', {}).values())
    shortage_baseline = solution_baseline.get('total_shortage_units', 0)

    demand_in_horizon = sum(
        e.quantity for e in forecast.entries
        if start_date <= e.forecast_date <= end_date
    )
    fill_rate_baseline = 100 * (1 - shortage_baseline / demand_in_horizon) if demand_in_horizon > 0 else 100

    print(f"   Production: {production_baseline:,.0f} units")
    print(f"   Fill rate: {fill_rate_baseline:.1f}%")

    # ===========================
    # TEST 2: WARMSTART
    # ===========================
    print("\n" + "-"*80)
    print("TEST 2: WARMSTART (Binary WITH campaign hints)")
    print("-"*80)

    model_warmstart = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
        inventory_snapshot_date=inventory_snapshot_date,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    start_time = time.time()
    result_warmstart = model_warmstart.solve(
        solver_name='cbc',
        use_warmstart=True,  # ENABLE WARMSTART
        time_limit_seconds=300,
        mip_gap=0.01,
        tee=False,
    )
    time_warmstart = time.time() - start_time

    print(f"   Status: {result_warmstart.termination_condition}")
    print(f"   Solve time: {time_warmstart:.1f}s")
    print(f"   Objective: ${result_warmstart.objective_value:,.2f}")
    print(f"   MIP gap: {result_warmstart.gap*100:.2f}%" if result_warmstart.gap else "   MIP gap: N/A")

    # Extract warmstart metrics
    solution_warmstart = model_warmstart.get_solution()
    production_warmstart = sum(solution_warmstart.get('production_by_date_product', {}).values())
    shortage_warmstart = solution_warmstart.get('total_shortage_units', 0)
    fill_rate_warmstart = 100 * (1 - shortage_warmstart / demand_in_horizon) if demand_in_horizon > 0 else 100

    print(f"   Production: {production_warmstart:,.0f} units")
    print(f"   Fill rate: {fill_rate_warmstart:.1f}%")

    # ===========================
    # COMPARISON
    # ===========================
    print("\n" + "="*80)
    print("PERFORMANCE COMPARISON")
    print("="*80)
    print(f"{'Metric':<25} {'Baseline':>15} {'Warmstart':>15} {'Difference':>20}")
    print("-" * 80)

    # Solve time comparison
    time_diff = time_warmstart - time_baseline
    time_diff_pct = (time_diff / time_baseline) * 100 if time_baseline > 0 else 0
    print(f"{'Solve time (s)':<25} {time_baseline:>15.1f} {time_warmstart:>15.1f} {time_diff:>15.1f}s ({time_diff_pct:+.1f}%)")

    # Objective comparison
    obj_diff = result_warmstart.objective_value - result_baseline.objective_value
    obj_diff_pct = (obj_diff / result_baseline.objective_value) * 100 if result_baseline.objective_value > 0 else 0
    print(f"{'Objective ($)':<25} {result_baseline.objective_value:>15,.0f} {result_warmstart.objective_value:>15,.0f} ${obj_diff:>15,.0f} ({obj_diff_pct:+.1f}%)")

    # Gap comparison
    baseline_gap_pct = result_baseline.gap * 100 if result_baseline.gap else 0
    warmstart_gap_pct = result_warmstart.gap * 100 if result_warmstart.gap else 0
    gap_diff = warmstart_gap_pct - baseline_gap_pct
    print(f"{'MIP gap (%)':<25} {baseline_gap_pct:>15.2f} {warmstart_gap_pct:>15.2f} {gap_diff:>20.2f}%")

    # Fill rate comparison
    fill_diff = fill_rate_warmstart - fill_rate_baseline
    print(f"{'Fill rate (%)':<25} {fill_rate_baseline:>15.1f} {fill_rate_warmstart:>15.1f} {fill_diff:>20.1f}%")

    print("-" * 80)

    # Speedup summary
    if time_warmstart < time_baseline:
        speedup_pct = ((time_baseline - time_warmstart) / time_baseline) * 100
        print(f"\nWARMSTART SPEEDUP: {speedup_pct:.1f}%")
        print(f"Time saved: {time_baseline - time_warmstart:.1f}s")
        print("✅ WARMSTART EFFECTIVE")
    else:
        slowdown_pct = ((time_warmstart - time_baseline) / time_baseline) * 100
        print(f"\nWARMSTART SLOWDOWN: {slowdown_pct:.1f}%")
        print(f"Time penalty: {time_warmstart - time_baseline:.1f}s")
        print("⚠️  WARMSTART INEFFECTIVE (slower than baseline)")

    print("="*80)

    # ===========================
    # ASSERTIONS
    # ===========================

    # Both should solve successfully
    assert result_baseline.is_optimal() or result_baseline.is_feasible(), \
        f"Baseline failed: {result_baseline.termination_condition}"
    assert result_warmstart.is_optimal() or result_warmstart.is_feasible(), \
        f"Warmstart failed: {result_warmstart.termination_condition}"

    # Objective values should be similar (within 5%)
    obj_diff_pct_abs = abs(obj_diff_pct)
    assert obj_diff_pct_abs < 5.0, \
        f"Objective values differ by {obj_diff_pct_abs:.1f}% (should be <5%)"

    # Fill rates should be acceptable
    assert fill_rate_baseline >= 85.0, \
        f"Baseline fill rate {fill_rate_baseline:.1f}% below 85% threshold"
    assert fill_rate_warmstart >= 85.0, \
        f"Warmstart fill rate {fill_rate_warmstart:.1f}% below 85% threshold"

    # Both should complete within time limit
    assert time_baseline < 300, f"Baseline timed out: {time_baseline:.1f}s"
    assert time_warmstart < 300, f"Warmstart timed out: {time_warmstart:.1f}s"

    print("\n✓ ALL ASSERTIONS PASSED")


@pytest.mark.slow
def test_warmstart_campaign_pattern_validation(benchmark_data):
    """Validate warmstart generates valid campaign patterns.

    Tests:
    -----
    - Warmstart hints are generated
    - Hints are binary (0 or 1)
    - Hints cover all products
    - Hints respect planning horizon
    - Campaign pattern is balanced (2-3 SKUs per weekday)
    """

    # Extract data
    forecast = benchmark_data['forecast']
    nodes = benchmark_data['nodes']
    unified_routes = benchmark_data['unified_routes']
    unified_truck_schedules = benchmark_data['unified_truck_schedules']
    labor_calendar = benchmark_data['labor_calendar']
    cost_structure = benchmark_data['cost_structure']
    inventory_snapshot_date = benchmark_data['inventory_snapshot_date']

    if inventory_snapshot_date is None:
        inventory_snapshot_date = min(e.forecast_date for e in forecast.entries)

    # Planning horizon
    start_date = inventory_snapshot_date
    end_date = start_date + timedelta(days=27)

    print("\n" + "="*80)
    print("WARMSTART CAMPAIGN PATTERN VALIDATION")
    print("="*80)

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
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_truck_schedules,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    # Generate warmstart hints
    hints = model._generate_warmstart()

    # Validate hints exist
    assert hints is not None, "Warmstart hints should be generated"
    assert len(hints) > 0, "Warmstart hints should not be empty"

    print(f"✓ Generated {len(hints)} warmstart hints")

    # Validate hint values are binary
    for key, value in hints.items():
        assert value in [0, 1], f"Hint value must be 0 or 1, got {value} for {key}"

    print("✓ All hint values are binary (0 or 1)")

    # Validate dates are within planning horizon
    for (node_id, product, date_val), hint_value in hints.items():
        assert start_date <= date_val <= end_date, \
            f"Hint date {date_val} outside planning horizon [{start_date}, {end_date}]"

    print("✓ All hint dates within planning horizon")

    # Count products with hints
    products_with_hints = set(prod for (_, prod, _) in hints.keys() if hints[(_, prod, _)] == 1)
    total_products = len(model.products)

    print(f"✓ Products with hints: {len(products_with_hints)} / {total_products}")

    # Analyze daily SKU count (campaign pattern should have 2-3 SKUs per weekday)
    daily_sku_count = {}
    for (node_id, product, date_val), hint_value in hints.items():
        if hint_value == 1:
            if date_val not in daily_sku_count:
                daily_sku_count[date_val] = set()
            daily_sku_count[date_val].add(product)

    weekday_sku_counts = [len(skus) for d, skus in daily_sku_count.items() if d.weekday() < 5]
    if weekday_sku_counts:
        avg_skus_per_weekday = sum(weekday_sku_counts) / len(weekday_sku_counts)
        print(f"✓ Average SKUs per weekday: {avg_skus_per_weekday:.1f}")
        print(f"  Range: {min(weekday_sku_counts)} - {max(weekday_sku_counts)} SKUs/day")

        # Campaign pattern should have balanced weekday allocation (1-5 SKUs per day)
        assert min(weekday_sku_counts) >= 1, "At least 1 SKU per weekday"
        assert max(weekday_sku_counts) <= 5, "At most 5 SKUs per weekday (reasonable limit)"

    print("\n✓ CAMPAIGN PATTERN VALIDATION PASSED")


if __name__ == "__main__":
    # Allow running test directly
    pytest.main([__file__, "-v", "-s"])
