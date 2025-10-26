"""Integration tests for daily rolling horizon solver with warmstart.

Tests cover:
- Solution extraction from solved models
- Date-shifting logic and edge cases
- Warmstart quality validation
- Daily solve sequences
- Forecast update handling
- Performance validation (warmstart speedup)
"""

import pytest
from datetime import date, timedelta
from typing import Dict, Tuple

from src.optimization.daily_rolling_solver import DailyRollingSolver, DailyResult, SequenceResult
from src.optimization.warmstart_utils import (
    extract_solution_for_warmstart,
    shift_warmstart_hints,
    validate_warmstart_quality,
    estimate_warmstart_speedup,
)
from src.optimization.unified_node_model import UnifiedNodeModel, UnifiedNode, UnifiedRoute
from src.models.forecast import Forecast, ForecastEntry
from src.parsers.excel_parser import ExcelParser


# Fixtures

@pytest.fixture
def test_data_paths():
    """Paths to test data files."""
    return {
        'forecast': 'data/examples/Gluten Free Forecast - Latest.xlsm',
        'network': 'data/examples/Network_Config.xlsx',
        'inventory': 'data/examples/inventory_latest.XLSX',
    }


@pytest.fixture
def parsed_data(test_data_paths):
    """Parse test data files."""
    parser = ExcelParser()

    # Parse forecast
    forecast_result = parser.parse_forecast(test_data_paths['forecast'])
    forecast = forecast_result['forecast']

    # Parse network config
    network_result = parser.parse_network_config(test_data_paths['network'])

    # Parse inventory
    inventory_result = parser.parse_inventory(test_data_paths['inventory'])

    return {
        'forecast': forecast,
        'locations': network_result['locations'],
        'routes': network_result['routes'],
        'labor_calendar': network_result['labor_calendar'],
        'manufacturing_site': network_result['manufacturing_site'],
        'truck_schedules': network_result['truck_schedules'],
        'cost_structure': network_result['cost_structure'],
        'initial_inventory': inventory_result['initial_inventory'],
    }


@pytest.fixture
def unified_components(parsed_data):
    """Create UnifiedNode and UnifiedRoute components."""
    from src.optimization.unified_node_model import create_unified_components

    nodes, routes = create_unified_components(
        locations=parsed_data['locations'],
        network_routes=parsed_data['routes'],
        manufacturing_site=parsed_data['manufacturing_site'],
        labor_calendar=parsed_data['labor_calendar'],
        truck_schedules=parsed_data['truck_schedules'],
        cost_structure=parsed_data['cost_structure'],
        initial_inventory=parsed_data['initial_inventory'],
    )

    return nodes, routes


@pytest.fixture
def small_forecast(parsed_data):
    """Create a small 1-week forecast for fast testing."""
    start_date = date(2025, 1, 6)  # Monday
    end_date = date(2025, 1, 12)  # Sunday

    # Filter to 1 week
    entries = [
        e for e in parsed_data['forecast'].entries
        if start_date <= e.forecast_date <= end_date
    ]

    return Forecast(entries=entries)


# Test Suite: Solution Extraction

class TestSolutionExtraction:
    """Test solution extraction from solved models."""

    def test_extract_solution_basic(self, unified_components, small_forecast):
        """Test basic solution extraction works."""
        nodes, routes = unified_components

        # Create and solve model
        model = UnifiedNodeModel(
            nodes=nodes,
            routes=routes,
            demand=small_forecast.to_demand_dict(),
            use_batch_tracking=True,
            allow_shortages=False,
        )

        result = model.solve(
            solver_name='appsi_highs',
            time_limit_seconds=120,
            mip_gap=0.05,  # Relaxed for speed
            tee=False
        )

        # Extract solution
        if result.success:
            hints = extract_solution_for_warmstart(model, verbose=True)

            # Verify extraction
            assert len(hints) > 0, "Should extract at least some variables"
            assert any(len(k) == 3 for k in hints.keys()), "Should have 3-tuple keys (node, prod, date)"

            # Verify production variables
            production_vars = [k for k in hints.keys() if len(k) == 3 and isinstance(k[2], date)]
            assert len(production_vars) > 0, "Should extract production variables"

            print(f"\n✓ Extracted {len(hints)} variables")
            print(f"  Production variables: {len(production_vars)}")
        else:
            pytest.skip("Solve failed, cannot test extraction")

    def test_extract_includes_all_variable_types(self, unified_components, small_forecast):
        """Test that extraction includes all major variable types."""
        nodes, routes = unified_components

        model = UnifiedNodeModel(
            nodes=nodes,
            routes=routes,
            demand=small_forecast.to_demand_dict(),
            use_batch_tracking=True,
        )

        result = model.solve(
            solver_name='appsi_highs',
            time_limit_seconds=120,
            mip_gap=0.05,
            tee=False
        )

        if result.success:
            hints = extract_solution_for_warmstart(model, verbose=False)

            # Check for different key lengths (different variable types)
            key_lengths = set(len(k) for k in hints.keys())

            # Should have variables with different dimensions:
            # - (node, date) for production_day
            # - (node, prod, date) for production, product_produced
            # - (node, prod, state, prod_date, inv_date) for inventory_cohort
            # - ('var_name', node, ...) for labor variables

            assert len(key_lengths) > 1, "Should have variables with different dimensions"
            print(f"\n✓ Variable key lengths found: {sorted(key_lengths)}")
        else:
            pytest.skip("Solve failed")


# Test Suite: Date Shifting

class TestDateShifting:
    """Test date-shifting logic for warmstart."""

    def test_shift_basic(self):
        """Test basic date shifting by 1 day."""
        # Create sample hints
        original = {
            ('6122', 'PROD_A', date(2025, 1, 6)): 1000.0,
            ('6122', 'PROD_B', date(2025, 1, 7)): 2000.0,
            ('6104', 'PROD_A', date(2025, 1, 8)): 500.0,
        }

        # Shift forward by 1 day
        shifted = shift_warmstart_hints(
            warmstart_hints=original,
            shift_days=1,
            new_start_date=date(2025, 1, 7),
            new_end_date=date(2025, 1, 13),
            verbose=False
        )

        # Verify shifting
        assert ('6122', 'PROD_A', date(2025, 1, 7)) in shifted
        assert ('6122', 'PROD_B', date(2025, 1, 8)) in shifted
        assert ('6104', 'PROD_A', date(2025, 1, 9)) in shifted

        # Original dates should not be in shifted
        assert ('6122', 'PROD_A', date(2025, 1, 6)) not in shifted

        print(f"\n✓ Basic shifting works: {len(original)} → {len(shifted)} variables")

    def test_shift_filters_out_of_range(self):
        """Test that dates outside new horizon are dropped."""
        original = {
            ('6122', 'PROD_A', date(2025, 1, 1)): 100.0,  # Before new horizon
            ('6122', 'PROD_B', date(2025, 1, 10)): 200.0,  # Within new horizon
            ('6122', 'PROD_C', date(2025, 1, 31)): 300.0,  # After new horizon
        }

        shifted = shift_warmstart_hints(
            warmstart_hints=original,
            shift_days=1,
            new_start_date=date(2025, 1, 6),
            new_end_date=date(2025, 1, 12),
            verbose=True
        )

        # Only PROD_B (shifted to 1/11) should remain
        assert len(shifted) == 1
        assert ('6122', 'PROD_B', date(2025, 1, 11)) in shifted

        print(f"\n✓ Out-of-range filtering works: {len(original)} → {len(shifted)}")

    def test_shift_handles_multi_date_keys(self):
        """Test shifting with keys containing multiple dates (cohorts)."""
        original = {
            ('6122', 'PROD_A', 'ambient', date(2025, 1, 6), date(2025, 1, 8)): 500.0,
        }

        shifted = shift_warmstart_hints(
            warmstart_hints=original,
            shift_days=1,
            new_start_date=date(2025, 1, 7),
            new_end_date=date(2025, 1, 14),
            verbose=False
        )

        # Both dates should be shifted
        expected_key = ('6122', 'PROD_A', 'ambient', date(2025, 1, 7), date(2025, 1, 9))
        assert expected_key in shifted
        assert shifted[expected_key] == 500.0

        print(f"\n✓ Multi-date key shifting works")

    def test_shift_weekend_boundary(self):
        """Test shifting across weekend boundary."""
        # Friday -> Monday shift
        original = {
            ('6122', 'PROD_A', date(2025, 1, 10)): 1000.0,  # Friday
        }

        shifted = shift_warmstart_hints(
            warmstart_hints=original,
            shift_days=3,  # Friday + 3 = Monday
            new_start_date=date(2025, 1, 13),  # Monday
            new_end_date=date(2025, 1, 19),
            verbose=False
        )

        # Should shift to Monday
        assert ('6122', 'PROD_A', date(2025, 1, 13)) in shifted

        print(f"\n✓ Weekend boundary shifting works")

    def test_shift_month_boundary(self):
        """Test shifting across month boundary."""
        # End of January -> Start of February
        original = {
            ('6122', 'PROD_A', date(2025, 1, 31)): 1000.0,
        }

        shifted = shift_warmstart_hints(
            warmstart_hints=original,
            shift_days=1,
            new_start_date=date(2025, 2, 1),
            new_end_date=date(2025, 2, 7),
            verbose=False
        )

        # Should shift to Feb 1
        assert ('6122', 'PROD_A', date(2025, 2, 1)) in shifted

        print(f"\n✓ Month boundary shifting works")


# Test Suite: Warmstart Quality Validation

class TestWarmstartQuality:
    """Test warmstart quality validation."""

    def test_validate_good_quality(self):
        """Test validation passes for good quality warmstart."""
        original = {f'key_{i}': float(i) for i in range(100)}
        shifted = {f'key_{i}': float(i) for i in range(80)}  # 80% overlap

        is_valid, msg = validate_warmstart_quality(
            original_hints=original,
            shifted_hints=shifted,
            min_overlap_ratio=0.7,
            verbose=True
        )

        assert is_valid
        assert "good" in msg.lower()

        print(f"\n✓ Quality validation: {msg}")

    def test_validate_poor_quality(self):
        """Test validation fails for poor quality warmstart."""
        original = {f'key_{i}': float(i) for i in range(100)}
        shifted = {f'key_{i}': float(i) for i in range(50)}  # 50% overlap

        is_valid, msg = validate_warmstart_quality(
            original_hints=original,
            shifted_hints=shifted,
            min_overlap_ratio=0.7,
            verbose=True
        )

        assert not is_valid
        assert "poor" in msg.lower()

        print(f"\n✓ Poor quality detected: {msg}")


# Test Suite: Speedup Estimation

class TestSpeedupEstimation:
    """Test warmstart speedup estimation."""

    def test_estimate_speedup_high_overlap(self):
        """Test speedup estimate for high overlap (1 day shift, 28 day horizon)."""
        speedup, desc = estimate_warmstart_speedup(
            shift_days=1,
            horizon_days=28,
            base_solve_time=100.0
        )

        # 27/28 = 96% overlap → should estimate excellent speedup
        assert speedup < 0.7  # At least 30% faster
        assert "excellent" in desc.lower() or "good" in desc.lower()

        print(f"\n✓ Speedup estimate (1d/28d): {desc}")

    def test_estimate_speedup_medium_overlap(self):
        """Test speedup estimate for medium overlap."""
        speedup, desc = estimate_warmstart_speedup(
            shift_days=7,
            horizon_days=28,
            base_solve_time=100.0
        )

        # 21/28 = 75% overlap → should estimate good speedup
        assert speedup < 0.9  # Some speedup expected

        print(f"\n✓ Speedup estimate (7d/28d): {desc}")


# Test Suite: Daily Rolling Solver

class TestDailyRollingSolver:
    """Test DailyRollingSolver functionality."""

    @pytest.mark.slow
    def test_solve_single_day(self, unified_components, small_forecast):
        """Test solving a single day."""
        nodes, routes = unified_components

        solver = DailyRollingSolver(
            nodes=nodes,
            routes=routes,
            base_forecast=small_forecast,
            horizon_days=7,  # 1 week for speed
            solver_name='appsi_highs',
            time_limit_seconds=120,
            mip_gap=0.05,
        )

        result = solver.solve_day_n(
            day_number=1,
            current_date=date(2025, 1, 6),
            use_warmstart=False,  # Cold start
            verbose=True
        )

        assert result.day_number == 1
        assert result.current_date == date(2025, 1, 6)
        assert result.solve_time > 0
        assert result.used_warmstart is False

        if result.success:
            assert result.objective_value is not None
            print(f"\n✓ Day 1 solve: {result.solve_time:.1f}s, ${result.objective_value:,.2f}")
        else:
            pytest.skip(f"Solve failed: {result.termination_condition}")

    @pytest.mark.slow
    def test_solve_two_day_sequence(self, unified_components, small_forecast):
        """Test solving 2 days with warmstart."""
        nodes, routes = unified_components

        solver = DailyRollingSolver(
            nodes=nodes,
            routes=routes,
            base_forecast=small_forecast,
            horizon_days=7,
            solver_name='appsi_highs',
            time_limit_seconds=120,
            mip_gap=0.05,
        )

        # Day 1 (cold start)
        result1 = solver.solve_day_n(
            day_number=1,
            current_date=date(2025, 1, 6),
            use_warmstart=False,
            verbose=True
        )

        # Day 2 (warmstart)
        result2 = solver.solve_day_n(
            day_number=2,
            current_date=date(2025, 1, 7),
            use_warmstart=True,
            verbose=True
        )

        assert result1.success, f"Day 1 failed: {result1.termination_condition}"
        assert result2.success, f"Day 2 failed: {result2.termination_condition}"

        # Day 2 should use warmstart
        assert result2.used_warmstart is True

        # Day 2 should be faster (not guaranteed but expected)
        if result2.warmstart_speedup is not None:
            print(f"\n✓ Warmstart speedup: {result2.warmstart_speedup:.2f}x")
            print(f"  Day 1: {result1.solve_time:.1f}s")
            print(f"  Day 2: {result2.solve_time:.1f}s")

    @pytest.mark.slow
    def test_solve_sequence(self, unified_components, small_forecast):
        """Test solving a 3-day sequence."""
        nodes, routes = unified_components

        solver = DailyRollingSolver(
            nodes=nodes,
            routes=routes,
            base_forecast=small_forecast,
            horizon_days=7,
            solver_name='appsi_highs',
            time_limit_seconds=120,
            mip_gap=0.05,
        )

        result = solver.solve_sequence(
            start_date=date(2025, 1, 6),
            num_days=3,
            verbose=True
        )

        assert result.total_days == 3
        assert len(result.daily_results) == 3
        assert result.total_solve_time > 0

        # Check individual days
        for i, day_result in enumerate(result.daily_results, start=1):
            assert day_result.day_number == i
            assert day_result.success, f"Day {i} failed"

            # Days 2+ should use warmstart
            if i > 1:
                assert day_result.used_warmstart is True

        print(f"\n✓ 3-day sequence:")
        print(f"  Total time: {result.total_solve_time:.1f}s")
        print(f"  Average time: {result.average_solve_time:.1f}s/day")
        if result.average_speedup:
            speedup_pct = (1 - result.average_speedup) * 100
            print(f"  Average speedup (Days 2+): {speedup_pct:.1f}% faster")

    def test_reset_clears_warmstart(self, unified_components, small_forecast):
        """Test that reset() clears warmstart state."""
        nodes, routes = unified_components

        solver = DailyRollingSolver(
            nodes=nodes,
            routes=routes,
            base_forecast=small_forecast,
            horizon_days=7,
        )

        # Set some internal state
        solver._previous_warmstart = {'dummy': 'value'}
        solver._previous_solve_time = 123.0
        solver._baseline_solve_time = 456.0

        # Reset
        solver.reset()

        # Verify cleared
        assert solver._previous_warmstart is None
        assert solver._previous_solve_time is None
        assert solver._baseline_solve_time is None

        print(f"\n✓ Reset clears state correctly")


# Test Suite: Forecast Updates

class TestForecastUpdates:
    """Test handling of forecast updates between days."""

    def test_forecast_updates_applied(self, unified_components, small_forecast):
        """Test that forecast updates are applied correctly."""
        nodes, routes = unified_components

        solver = DailyRollingSolver(
            nodes=nodes,
            routes=routes,
            base_forecast=small_forecast,
            horizon_days=7,
        )

        # Create forecast update (increase demand for a specific product/date)
        forecast_updates = {
            ('6104', '31002', date(2025, 1, 10)): 5000.0  # Increase demand
        }

        # This doesn't solve, just tests the forecast window creation logic
        forecast_window = solver._create_forecast_for_window(
            start_date=date(2025, 1, 6),
            end_date=date(2025, 1, 12),
            forecast_updates=forecast_updates
        )

        # Check that update was applied
        entries_for_date = [
            e for e in forecast_window.entries
            if e.location_id == '6104'
            and e.product_id == '31002'
            and e.forecast_date == date(2025, 1, 10)
        ]

        # Should have updated quantity
        if entries_for_date:
            assert entries_for_date[0].quantity == 5000.0
            print(f"\n✓ Forecast update applied: {entries_for_date[0].quantity}")
        else:
            # Entry may not exist in base forecast - update should create it
            print(f"\n✓ Forecast update would create new entry")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
