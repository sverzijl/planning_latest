"""Performance benchmark tests for batch tracking implementation.

This test suite benchmarks model size, solve time, and memory usage
for the batch tracking implementation across different horizons and scenarios.

These tests are designed to be run periodically (weekly) to track performance
trends and identify performance regressions.

Run with: pytest tests/test_cohort_performance.py -v --durations=10
"""

import pytest
import time
import gc
from datetime import date, timedelta
from typing import List, Dict, Tuple

from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route, RouteLeg


# ===========================
# Helper Functions
# ===========================


def create_test_scenario(
    horizon_days: int,
    num_products: int = 1,
    num_destinations: int = 1,
    daily_demand: float = 100.0
) -> Tuple[Forecast, LaborCalendar, ManufacturingSite, CostStructure, List[Location], List[Route]]:
    """Create a test scenario with specified parameters."""
    base_date = date(2025, 10, 13)

    # Create forecast
    entries = []
    for dest_idx in range(num_destinations):
        dest_id = f"610{3 + dest_idx}"
        for prod_idx in range(num_products):
            prod_id = f"17628{3 + prod_idx}"
            for day in range(horizon_days):
                entries.append(
                    ForecastEntry(
                        location_id=dest_id,
                        product_id=prod_id,
                        forecast_date=base_date + timedelta(days=day),
                        quantity=daily_demand
                    )
                )

    forecast = Forecast(name=f"{horizon_days}d Benchmark", entries=entries)

    # Create labor calendar
    labor_days = []
    for day in range(horizon_days + 7):  # Extra buffer
        current_date = base_date - timedelta(days=3) + timedelta(days=day)
        is_weekend = current_date.weekday() >= 5

        labor_days.append(
            LaborDay(
                calendar_date=current_date,
                fixed_hours=0.0 if is_weekend else 12.0,
                is_public_holiday=False,
                labor_cost_rate=50.0 if is_weekend else 40.0
            )
        )

    labor_calendar = LaborCalendar(days=labor_days)

    # Create manufacturing site
    manufacturing = ManufacturingSite(
        location_id="6122",
        production_rate_per_hour=1400.0,
        max_hours_per_day=14.0
    )

    # Create cost structure
    cost_structure = CostStructure(
        production_cost_per_unit=0.5,
        transport_cost_per_unit_per_km=0.01,
        holding_cost_per_unit_per_day=0.02,
        shortage_penalty_per_unit=100.0
    )

    # Create locations
    locations = [
        Location(
            id="6122",
            name="Manufacturing",
            type=LocationType.MANUFACTURING,
            storage_mode=StorageMode.BOTH
        )
    ]

    for dest_idx in range(num_destinations):
        dest_id = f"610{3 + dest_idx}"
        locations.append(
            Location(
                id=dest_id,
                name=f"Breadroom {dest_idx + 1}",
                type=LocationType.BREADROOM,
                storage_mode=StorageMode.AMBIENT
            )
        )

    # Create routes
    routes = []
    for dest_idx in range(num_destinations):
        dest_id = f"610{3 + dest_idx}"
        routes.append(
            Route(
                id=f"R{dest_idx + 1}",
                route_legs=[
                    RouteLeg(
                        from_location_id="6122",
                        to_location_id=dest_id,
                        transport_mode="ambient",
                        transit_days=2,
                        cost_per_unit=1.0
                    )
                ]
            )
        )

    return forecast, labor_calendar, manufacturing, cost_structure, locations, routes


def get_model_size(pyomo_model) -> Dict[str, int]:
    """Get model size statistics."""
    from pyomo.environ import Var, Constraint, Objective

    stats = {
        'variables': sum(1 for _ in pyomo_model.component_data_objects(Var)),
        'constraints': sum(1 for _ in pyomo_model.component_data_objects(Constraint)),
        'objectives': sum(1 for _ in pyomo_model.component_data_objects(Objective))
    }

    return stats


# ===========================
# Tests - Model Size Scaling
# ===========================


@pytest.mark.parametrize("horizon_days", [7, 14, 21])
def test_model_size_scaling_by_horizon(horizon_days: int) -> None:
    """Test how model size scales with planning horizon.

    For cohort models, size should scale roughly quadratically due to
    (production_date × current_date) combinations.
    """
    forecast, labor_calendar, manufacturing, cost_structure, locations, routes = \
        create_test_scenario(horizon_days=horizon_days)

    model = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        use_batch_tracking=True,
        validate_feasibility=False,
        allow_shortages=True
    )

    pyomo_model = model.build_model()
    stats = get_model_size(pyomo_model)

    print(f"\n{horizon_days}-day horizon: {stats['variables']} vars, "
          f"{stats['constraints']} constraints")

    # Rough upper bounds (adjust based on actual implementation)
    if horizon_days == 7:
        assert stats['variables'] < 500, f"Too many variables for 7-day: {stats['variables']}"
    elif horizon_days == 14:
        assert stats['variables'] < 2000, f"Too many variables for 14-day: {stats['variables']}"
    elif horizon_days == 21:
        assert stats['variables'] < 5000, f"Too many variables for 21-day: {stats['variables']}"


def test_model_size_comparison_legacy_vs_cohort() -> None:
    """Compare model sizes between legacy and cohort modes."""
    horizon_days = 14

    forecast, labor_calendar, manufacturing, cost_structure, locations, routes = \
        create_test_scenario(horizon_days=horizon_days)

    # Legacy mode
    model_legacy = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        use_batch_tracking=False,
        validate_feasibility=False,
        allow_shortages=True
    )

    pyomo_legacy = model_legacy.build_model()
    stats_legacy = get_model_size(pyomo_legacy)

    # Cohort mode
    model_cohort = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        use_batch_tracking=True,
        validate_feasibility=False,
        allow_shortages=True
    )

    pyomo_cohort = model_cohort.build_model()
    stats_cohort = get_model_size(pyomo_cohort)

    print(f"\nLegacy: {stats_legacy['variables']} vars")
    print(f"Cohort: {stats_cohort['variables']} vars")
    print(f"Ratio: {stats_cohort['variables'] / stats_legacy['variables']:.1f}x")

    # Cohort model will be larger (due to cohort tracking)
    # But should not be more than 5× larger for reasonable horizons
    ratio = stats_cohort['variables'] / stats_legacy['variables']
    assert ratio < 5.0, f"Cohort model too large: {ratio:.1f}x legacy"


# ===========================
# Tests - Build Time Performance
# ===========================


@pytest.mark.parametrize("horizon_days", [7, 14, 21])
def test_build_time_scaling(horizon_days: int) -> None:
    """Test model build time scaling with horizon."""
    forecast, labor_calendar, manufacturing, cost_structure, locations, routes = \
        create_test_scenario(horizon_days=horizon_days)

    model = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        use_batch_tracking=True,
        validate_feasibility=False,
        allow_shortages=True
    )

    gc.collect()  # Clean up before timing

    start = time.time()
    pyomo_model = model.build_model()
    build_time = time.time() - start

    print(f"\n{horizon_days}-day build time: {build_time:.2f}s")

    # Build time limits (generous to account for CI environment variability)
    if horizon_days == 7:
        assert build_time < 5.0, f"7-day build too slow: {build_time:.2f}s"
    elif horizon_days == 14:
        assert build_time < 10.0, f"14-day build too slow: {build_time:.2f}s"
    elif horizon_days == 21:
        assert build_time < 20.0, f"21-day build too slow: {build_time:.2f}s"

    assert pyomo_model is not None


def test_build_time_comparison_legacy_vs_cohort() -> None:
    """Compare build times between legacy and cohort modes."""
    horizon_days = 14

    forecast, labor_calendar, manufacturing, cost_structure, locations, routes = \
        create_test_scenario(horizon_days=horizon_days)

    # Time legacy mode
    model_legacy = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        use_batch_tracking=False,
        validate_feasibility=False,
        allow_shortages=True
    )

    gc.collect()
    start = time.time()
    pyomo_legacy = model_legacy.build_model()
    time_legacy = time.time() - start

    # Time cohort mode
    model_cohort = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        use_batch_tracking=True,
        validate_feasibility=False,
        allow_shortages=True
    )

    gc.collect()
    start = time.time()
    pyomo_cohort = model_cohort.build_model()
    time_cohort = time.time() - start

    print(f"\nLegacy build: {time_legacy:.2f}s")
    print(f"Cohort build: {time_cohort:.2f}s")
    print(f"Ratio: {time_cohort / time_legacy:.1f}x")

    # Cohort build should not be more than 3× slower
    if time_legacy > 0.1:  # Only check if legacy time is meaningful
        ratio = time_cohort / time_legacy
        assert ratio < 3.0, f"Cohort build too slow: {ratio:.1f}x legacy"


# ===========================
# Tests - Solve Time Performance
# ===========================


@pytest.mark.parametrize("horizon_days", [7, 14])
def test_solve_time_acceptable(horizon_days: int) -> None:
    """Test that solve time is within acceptable limits."""
    forecast, labor_calendar, manufacturing, cost_structure, locations, routes = \
        create_test_scenario(horizon_days=horizon_days)

    model = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        use_batch_tracking=True,
        validate_feasibility=False,
        allow_shortages=True
    )

    start = time.time()
    result = model.solve(time_limit_seconds=300)  # 5 minutes max
    elapsed = time.time() - start

    print(f"\n{horizon_days}-day solve time: {elapsed:.2f}s")
    print(f"Status: {result.get('solver_status', 'unknown')}")

    # Solve time limits
    if horizon_days == 7:
        assert elapsed < 60, f"7-day solve too slow: {elapsed:.2f}s"
    elif horizon_days == 14:
        assert elapsed < 180, f"14-day solve too slow: {elapsed:.2f}s"

    # Should find a solution
    assert result.get('solver_status') in ['optimal', 'feasible'], \
        f"Solver failed: {result.get('solver_status')}"


def test_solve_time_comparison_legacy_vs_cohort() -> None:
    """Compare solve times between legacy and cohort modes."""
    horizon_days = 7  # Use shorter horizon for faster test

    forecast, labor_calendar, manufacturing, cost_structure, locations, routes = \
        create_test_scenario(horizon_days=horizon_days)

    # Solve legacy
    model_legacy = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        use_batch_tracking=False,
        validate_feasibility=False,
        allow_shortages=True
    )

    start = time.time()
    result_legacy = model_legacy.solve(time_limit_seconds=120)
    time_legacy = time.time() - start

    # Solve cohort
    model_cohort = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        use_batch_tracking=True,
        validate_feasibility=False,
        allow_shortages=True
    )

    start = time.time()
    result_cohort = model_cohort.solve(time_limit_seconds=120)
    time_cohort = time.time() - start

    print(f"\nLegacy solve: {time_legacy:.2f}s ({result_legacy.get('solver_status')})")
    print(f"Cohort solve: {time_cohort:.2f}s ({result_cohort.get('solver_status')})")

    if time_legacy > 1.0:  # Only check if legacy time is meaningful
        ratio = time_cohort / time_legacy
        print(f"Ratio: {ratio:.1f}x")

        # Cohort solve should not be more than 2× slower
        assert ratio < 2.0, f"Cohort solve too slow: {ratio:.1f}x legacy"


# ===========================
# Tests - Scaling Analysis
# ===========================


def test_variable_count_scaling_formula() -> None:
    """Test that variable count follows expected scaling formula.

    For cohort models:
    - Inventory variables: O(horizon² × products × locations)
    - Production variables: O(horizon × products)
    - Shipment variables: O(horizon × routes × products)

    Total should be roughly O(horizon²) for fixed products/locations.
    """
    horizons = [7, 14, 21]
    variable_counts = []

    for horizon in horizons:
        forecast, labor_calendar, manufacturing, cost_structure, locations, routes = \
            create_test_scenario(horizon_days=horizon)

        model = IntegratedProductionDistributionModel(
            forecast=forecast,
            labor_calendar=labor_calendar,
            manufacturing_site=manufacturing,
            cost_structure=cost_structure,
            locations=locations,
            routes=routes,
            use_batch_tracking=True,
            validate_feasibility=False,
            allow_shortages=True
        )

        pyomo_model = model.build_model()
        stats = get_model_size(pyomo_model)

        variable_counts.append((horizon, stats['variables']))
        print(f"\n{horizon} days: {stats['variables']} variables")

    # Check scaling trend
    # From 7 to 14 days (2x horizon), variables should increase by ~4× (quadratic)
    if len(variable_counts) >= 2:
        h1, v1 = variable_counts[0]
        h2, v2 = variable_counts[1]

        horizon_ratio = h2 / h1
        variable_ratio = v2 / v1

        print(f"\nHorizon ratio: {horizon_ratio:.1f}x")
        print(f"Variable ratio: {variable_ratio:.1f}x")

        # For quadratic scaling, variable_ratio ≈ horizon_ratio²
        expected_ratio = horizon_ratio ** 2

        # Allow 50% tolerance
        assert variable_ratio < expected_ratio * 1.5, \
            f"Variables growing faster than quadratic: {variable_ratio:.1f}x vs {expected_ratio:.1f}x expected"


# ===========================
# Tests - Memory Usage
# ===========================


@pytest.mark.skipif(True, reason="Memory profiling requires additional dependencies")
def test_memory_usage_acceptable() -> None:
    """Test that memory usage is within acceptable limits.

    This test is skipped by default as it requires memory_profiler.
    Enable by installing: pip install memory_profiler
    """
    try:
        from memory_profiler import memory_usage
    except ImportError:
        pytest.skip("memory_profiler not installed")

    horizon_days = 14

    forecast, labor_calendar, manufacturing, cost_structure, locations, routes = \
        create_test_scenario(horizon_days=horizon_days)

    def build_and_solve():
        model = IntegratedProductionDistributionModel(
            forecast=forecast,
            labor_calendar=labor_calendar,
            manufacturing_site=manufacturing,
            cost_structure=cost_structure,
            locations=locations,
            routes=routes,
            use_batch_tracking=True,
            validate_feasibility=False,
            allow_shortages=True
        )
        model.solve(time_limit_seconds=60)

    mem_usage = memory_usage(build_and_solve, interval=0.1)
    peak_memory = max(mem_usage) - min(mem_usage)

    print(f"\nPeak memory usage: {peak_memory:.1f} MB")

    # Should use less than 500 MB for 14-day horizon
    assert peak_memory < 500, f"Memory usage too high: {peak_memory:.1f} MB"


# ===========================
# Performance Summary
# ===========================


def test_performance_summary_report() -> None:
    """Generate a performance summary report for multiple scenarios."""
    print("\n" + "=" * 60)
    print("BATCH TRACKING PERFORMANCE SUMMARY")
    print("=" * 60)

    scenarios = [
        (7, 1, 1, "7-day, 1 product, 1 destination"),
        (14, 1, 1, "14-day, 1 product, 1 destination"),
        (14, 2, 2, "14-day, 2 products, 2 destinations"),
    ]

    results = []

    for horizon, products, destinations, description in scenarios:
        forecast, labor_calendar, manufacturing, cost_structure, locations, routes = \
            create_test_scenario(
                horizon_days=horizon,
                num_products=products,
                num_destinations=destinations
            )

        model = IntegratedProductionDistributionModel(
            forecast=forecast,
            labor_calendar=labor_calendar,
            manufacturing_site=manufacturing,
            cost_structure=cost_structure,
            locations=locations,
            routes=routes,
            use_batch_tracking=True,
            validate_feasibility=False,
            allow_shortages=True
        )

        # Time build
        gc.collect()
        start = time.time()
        pyomo_model = model.build_model()
        build_time = time.time() - start

        # Get size
        stats = get_model_size(pyomo_model)

        # Time solve
        start = time.time()
        result = model.solve(time_limit_seconds=180)
        solve_time = time.time() - start

        results.append({
            'description': description,
            'variables': stats['variables'],
            'constraints': stats['constraints'],
            'build_time': build_time,
            'solve_time': solve_time,
            'status': result.get('solver_status', 'unknown')
        })

    # Print summary table
    print(f"\n{'Scenario':<40} {'Variables':<10} {'Constraints':<12} {'Build(s)':<10} {'Solve(s)':<10} {'Status':<10}")
    print("-" * 100)

    for r in results:
        print(f"{r['description']:<40} {r['variables']:<10} {r['constraints']:<12} "
              f"{r['build_time']:<10.2f} {r['solve_time']:<10.2f} {r['status']:<10}")

    print("=" * 60)

    # All should complete
    assert all(r['status'] in ['optimal', 'feasible'] for r in results), \
        "Some scenarios failed to solve"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--durations=10"])
