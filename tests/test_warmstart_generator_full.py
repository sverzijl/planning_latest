"""Comprehensive unit tests for warmstart_generator.py.

This test suite validates the campaign-based warmstart hint generation algorithm
including basic functionality, edge cases, validation functions, and multi-week scenarios.
"""

import pytest
from datetime import date, timedelta
from collections import defaultdict

from src.optimization.warmstart_generator import (
    generate_campaign_warmstart,
    validate_warmstart_hints,
    validate_freshness_constraint,
    validate_daily_sku_limit,
    create_default_warmstart,
)


class TestCampaignWarmstartBasic:
    """Basic warmstart generation tests."""

    def test_generate_campaign_basic(self):
        """Test basic warmstart generation for 5 SKUs over 1 week."""
        # Setup
        manufacturing_node_id = "6122"
        products = ['PROD_001', 'PROD_002', 'PROD_003', 'PROD_004', 'PROD_005']
        start_date = date(2025, 10, 20)  # Monday
        end_date = start_date + timedelta(days=6)  # Sunday

        # Uniform demand
        demand_forecast = {}
        current = start_date
        while current <= end_date:
            for p in products:
                key = ("6122", p, current)
                demand_forecast[key] = 1000.0
            current += timedelta(days=1)

        # Generate warmstart
        warmstart = generate_campaign_warmstart(
            demand_forecast=demand_forecast,
            manufacturing_node_id=manufacturing_node_id,
            products=products,
            start_date=start_date,
            end_date=end_date,
            max_daily_production=19600,
            target_skus_per_weekday=3,
            freshness_days=7,
        )

        # Assertions
        assert isinstance(warmstart, dict)
        assert len(warmstart) > 0  # Should have some hints

        # All values are binary
        assert all(v in [0, 1] for v in warmstart.values())

        # Check weekday constraint (Mon-Fri)
        weekdays = [start_date + timedelta(days=i) for i in range(5)]
        for d in weekdays:
            skus_on_date = sum(
                warmstart.get((manufacturing_node_id, p, d), 0)
                for p in products
            )
            assert 1 <= skus_on_date <= 3, f"{d} has {skus_on_date} SKUs"

        # Check weekend constraint (Sat-Sun)
        weekends = [start_date + timedelta(days=i) for i in range(5, 7)]
        for d in weekends:
            skus_on_date = sum(
                warmstart.get((manufacturing_node_id, p, d), 0)
                for p in products
            )
            assert skus_on_date <= 1, f"{d} has {skus_on_date} SKUs (weekend)"

        # Freshness constraint (each product produced at least once in week)
        for p in products:
            production_days = sum(
                warmstart.get((manufacturing_node_id, p, d), 0)
                for d in weekdays  # Only check weekdays
            )
            assert production_days >= 1, f"{p} not produced on any weekday"

        print(f"✓ Test passed: {len(warmstart)} warmstart hints generated")

    def test_demand_weighted_allocation(self):
        """Test that high-demand SKUs get more production days."""
        manufacturing_node_id = "6122"
        products = ['SKU_HIGH', 'SKU_MED', 'SKU_LOW']
        start_date = date(2025, 10, 20)  # Monday
        end_date = start_date + timedelta(days=6)

        # Skewed demand: 70% / 20% / 10%
        demand_forecast = {}
        current = start_date
        while current <= end_date:
            demand_forecast[("6122", 'SKU_HIGH', current)] = 7000.0
            demand_forecast[("6122", 'SKU_MED', current)] = 2000.0
            demand_forecast[("6122", 'SKU_LOW', current)] = 1000.0
            current += timedelta(days=1)

        warmstart = generate_campaign_warmstart(
            demand_forecast=demand_forecast,
            manufacturing_node_id=manufacturing_node_id,
            products=products,
            start_date=start_date,
            end_date=end_date,
            max_daily_production=19600,
            target_skus_per_weekday=3,
            freshness_days=7,
        )

        # Count production days per SKU (weekdays only)
        weekdays = [start_date + timedelta(days=i) for i in range(5)]
        production_days = {}
        for p in products:
            production_days[p] = sum(
                warmstart.get((manufacturing_node_id, p, d), 0)
                for d in weekdays
            )

        # High-demand SKU should have most production days
        assert production_days['SKU_HIGH'] >= production_days['SKU_MED']
        assert production_days['SKU_MED'] >= production_days['SKU_LOW']

        print(f"✓ Demand-weighted allocation: {production_days}")

    def test_weekly_pattern_consistency(self):
        """Test that weekly pattern repeats across 4-week horizon."""
        manufacturing_node_id = "6122"
        products = ['SKU_A', 'SKU_B', 'SKU_C']
        start_date = date(2025, 10, 20)  # Monday
        end_date = start_date + timedelta(days=27)  # 4 weeks

        # Uniform demand
        demand_forecast = {}
        current = start_date
        while current <= end_date:
            for p in products:
                demand_forecast[("6122", p, current)] = 1000.0
            current += timedelta(days=1)

        warmstart = generate_campaign_warmstart(
            demand_forecast=demand_forecast,
            manufacturing_node_id=manufacturing_node_id,
            products=products,
            start_date=start_date,
            end_date=end_date,
            max_daily_production=19600,
            target_skus_per_weekday=3,
            freshness_days=7,
        )

        # Extract weekly patterns (weekdays only)
        weeks = []
        for week_num in range(4):
            week_start = start_date + timedelta(days=week_num * 7)
            weekdays = [week_start + timedelta(days=i) for i in range(5)]

            # Pattern: which SKUs on which weekdays
            week_pattern = {}
            for day_idx, d in enumerate(weekdays):
                skus_on_day = [
                    p for p in products
                    if warmstart.get((manufacturing_node_id, p, d), 0) == 1
                ]
                week_pattern[day_idx] = sorted(skus_on_day)
            weeks.append(week_pattern)

        # Check consistency across weeks
        for week_idx in range(1, 4):
            # Compare to first week (pattern should repeat)
            for day_idx in range(5):
                # Allow some flexibility due to demand-weighted allocation
                # At minimum, same number of SKUs should be produced each weekday
                week1_count = len(weeks[0][day_idx])
                week_n_count = len(weeks[week_idx][day_idx])
                assert abs(week1_count - week_n_count) <= 1, \
                    f"Week {week_idx+1} day {day_idx}: {week_n_count} SKUs vs Week 1: {week1_count}"

        print(f"✓ Weekly pattern consistent across 4 weeks")


class TestWarmstartConstraints:
    """Test constraint enforcement."""

    def test_max_skus_per_weekday_enforced(self):
        """Test that max SKUs per weekday is never exceeded."""
        manufacturing_node_id = "6122"
        products = [f'SKU_{i:02d}' for i in range(10)]  # 10 SKUs
        start_date = date(2025, 10, 20)  # Monday
        end_date = start_date + timedelta(days=6)

        # High demand across all SKUs
        demand_forecast = {}
        current = start_date
        while current <= end_date:
            for p in products:
                demand_forecast[("6122", p, current)] = 5000.0
            current += timedelta(days=1)

        warmstart = generate_campaign_warmstart(
            demand_forecast=demand_forecast,
            manufacturing_node_id=manufacturing_node_id,
            products=products,
            start_date=start_date,
            end_date=end_date,
            max_daily_production=19600,
            target_skus_per_weekday=3,
            freshness_days=7,
        )

        # Check constraint
        weekdays = [start_date + timedelta(days=i) for i in range(5)]
        for d in weekdays:
            skus_on_date = sum(
                warmstart.get((manufacturing_node_id, p, d), 0)
                for p in products
            )
            assert skus_on_date <= 3, f"{d} has {skus_on_date} SKUs (exceeds max 3)"

        print(f"✓ Max SKUs per weekday enforced")

    def test_weekend_minimization(self):
        """Test that weekend production is minimal."""
        manufacturing_node_id = "6122"
        products = ['SKU_A', 'SKU_B', 'SKU_C']
        start_date = date(2025, 10, 20)  # Monday
        end_date = start_date + timedelta(days=6)

        # Moderate demand (weekday capacity should be sufficient)
        demand_forecast = {}
        current = start_date
        while current <= end_date:
            for p in products:
                demand_forecast[("6122", p, current)] = 2000.0
            current += timedelta(days=1)

        warmstart = generate_campaign_warmstart(
            demand_forecast=demand_forecast,
            manufacturing_node_id=manufacturing_node_id,
            products=products,
            start_date=start_date,
            end_date=end_date,
            max_daily_production=19600,
            target_skus_per_weekday=3,
            freshness_days=7,
        )

        # Count weekend production
        weekends = [start_date + timedelta(days=i) for i in range(5, 7)]
        total_weekend_skus = sum(
            warmstart.get((manufacturing_node_id, p, d), 0)
            for p in products
            for d in weekends
        )

        # Should be minimal (0-2 SKU-days total for 3 SKUs over 2 days)
        assert total_weekend_skus <= 2, f"Weekend production too high: {total_weekend_skus}"

        print(f"✓ Weekend production minimized: {total_weekend_skus} SKU-days")

    def test_all_skus_produced_weekly(self):
        """Test that all SKUs are produced at least once per week."""
        manufacturing_node_id = "6122"
        products = [f'SKU_{i:02d}' for i in range(5)]
        start_date = date(2025, 10, 20)  # Monday
        end_date = start_date + timedelta(days=6)

        # Uniform demand
        demand_forecast = {}
        current = start_date
        while current <= end_date:
            for p in products:
                demand_forecast[("6122", p, current)] = 1000.0
            current += timedelta(days=1)

        warmstart = generate_campaign_warmstart(
            demand_forecast=demand_forecast,
            manufacturing_node_id=manufacturing_node_id,
            products=products,
            start_date=start_date,
            end_date=end_date,
            max_daily_production=19600,
            target_skus_per_weekday=3,
            freshness_days=7,
        )

        # Check each SKU
        weekdays = [start_date + timedelta(days=i) for i in range(5)]
        for p in products:
            production_days = sum(
                warmstart.get((manufacturing_node_id, p, d), 0)
                for d in weekdays
            )
            assert production_days >= 1, f"{p} not produced in week"

        print(f"✓ All SKUs produced at least once")

    def test_load_balancing(self):
        """Test that daily SKU counts are balanced (2-3 per day)."""
        manufacturing_node_id = "6122"
        products = [f'SKU_{i:02d}' for i in range(5)]
        start_date = date(2025, 10, 20)  # Monday
        end_date = start_date + timedelta(days=6)

        # Uniform demand
        demand_forecast = {}
        current = start_date
        while current <= end_date:
            for p in products:
                demand_forecast[("6122", p, current)] = 1000.0
            current += timedelta(days=1)

        warmstart = generate_campaign_warmstart(
            demand_forecast=demand_forecast,
            manufacturing_node_id=manufacturing_node_id,
            products=products,
            start_date=start_date,
            end_date=end_date,
            max_daily_production=19600,
            target_skus_per_weekday=3,
            freshness_days=7,
        )

        # Count SKUs per weekday
        weekdays = [start_date + timedelta(days=i) for i in range(5)]
        daily_counts = []
        for d in weekdays:
            count = sum(
                warmstart.get((manufacturing_node_id, p, d), 0)
                for p in products
            )
            daily_counts.append(count)

        # Check balance (should be 2-3 per day for 5 SKUs)
        assert all(2 <= c <= 3 for c in daily_counts), \
            f"Unbalanced daily counts: {daily_counts}"

        print(f"✓ Load balanced: {daily_counts} SKUs per day")


class TestWarmstartEdgeCases:
    """Test edge cases and error handling."""

    def test_edge_case_zero_demand(self):
        """Test handling of zero demand (should skip product)."""
        manufacturing_node_id = "6122"
        products = ['SKU_A', 'SKU_B', 'SKU_C']
        start_date = date(2025, 10, 20)
        end_date = start_date + timedelta(days=6)

        # Zero demand (empty forecast)
        demand_forecast = {}

        warmstart = generate_campaign_warmstart(
            demand_forecast=demand_forecast,
            manufacturing_node_id=manufacturing_node_id,
            products=products,
            start_date=start_date,
            end_date=end_date,
            max_daily_production=19600,
            target_skus_per_weekday=3,
            freshness_days=7,
        )

        # Should return empty hints (no demand = no production hints)
        assert len(warmstart) == 0, "Expected empty hints for zero demand"

        print(f"✓ Zero demand handled gracefully")

    def test_edge_case_single_product(self):
        """Test with single product (should work without errors)."""
        manufacturing_node_id = "6122"
        products = ['SKU_ONLY']
        start_date = date(2025, 10, 20)
        end_date = start_date + timedelta(days=6)

        # Demand for single product
        demand_forecast = {}
        current = start_date
        while current <= end_date:
            demand_forecast[("6122", 'SKU_ONLY', current)] = 5000.0
            current += timedelta(days=1)

        warmstart = generate_campaign_warmstart(
            demand_forecast=demand_forecast,
            manufacturing_node_id=manufacturing_node_id,
            products=products,
            start_date=start_date,
            end_date=end_date,
            max_daily_production=19600,
            target_skus_per_weekday=3,
            freshness_days=7,
        )

        # Should produce every weekday for max freshness
        weekdays = [start_date + timedelta(days=i) for i in range(5)]
        for d in weekdays:
            assert warmstart.get((manufacturing_node_id, 'SKU_ONLY', d), 0) == 1, \
                f"Single product should be produced on {d}"

        print(f"✓ Single product handled correctly")

    def test_edge_case_uneven_demand(self):
        """Test with 90% demand on one SKU."""
        manufacturing_node_id = "6122"
        products = ['SKU_DOMINANT', 'SKU_MINOR']
        start_date = date(2025, 10, 20)
        end_date = start_date + timedelta(days=6)

        # 90/10 demand split
        demand_forecast = {}
        current = start_date
        while current <= end_date:
            demand_forecast[("6122", 'SKU_DOMINANT', current)] = 9000.0
            demand_forecast[("6122", 'SKU_MINOR', current)] = 1000.0
            current += timedelta(days=1)

        warmstart = generate_campaign_warmstart(
            demand_forecast=demand_forecast,
            manufacturing_node_id=manufacturing_node_id,
            products=products,
            start_date=start_date,
            end_date=end_date,
            max_daily_production=19600,
            target_skus_per_weekday=3,
            freshness_days=7,
        )

        # Count production days
        weekdays = [start_date + timedelta(days=i) for i in range(5)]
        dominant_days = sum(
            warmstart.get((manufacturing_node_id, 'SKU_DOMINANT', d), 0)
            for d in weekdays
        )
        minor_days = sum(
            warmstart.get((manufacturing_node_id, 'SKU_MINOR', d), 0)
            for d in weekdays
        )

        # Dominant SKU should have more days
        assert dominant_days > minor_days, \
            f"Dominant SKU ({dominant_days} days) should have more than minor ({minor_days} days)"

        # But minor should still be produced (freshness)
        assert minor_days >= 1, "Minor SKU should still be produced"

        print(f"✓ Uneven demand handled: dominant={dominant_days}, minor={minor_days}")


class TestWarmstartMultiWeek:
    """Test multi-week horizon scenarios."""

    def test_multi_week_horizon(self):
        """Test 4-week horizon consistency."""
        manufacturing_node_id = "6122"
        products = ['SKU_A', 'SKU_B', 'SKU_C', 'SKU_D', 'SKU_E']
        start_date = date(2025, 10, 20)  # Monday
        end_date = start_date + timedelta(days=27)  # 4 weeks

        # Uniform demand
        demand_forecast = {}
        current = start_date
        while current <= end_date:
            for p in products:
                demand_forecast[("6122", p, current)] = 2000.0
            current += timedelta(days=1)

        warmstart = generate_campaign_warmstart(
            demand_forecast=demand_forecast,
            manufacturing_node_id=manufacturing_node_id,
            products=products,
            start_date=start_date,
            end_date=end_date,
            max_daily_production=19600,
            target_skus_per_weekday=3,
            freshness_days=7,
        )

        # Check each week independently
        for week_num in range(4):
            week_start = start_date + timedelta(days=week_num * 7)
            weekdays = [week_start + timedelta(days=i) for i in range(5)]

            # Each product produced at least once per week
            for p in products:
                week_production = sum(
                    warmstart.get((manufacturing_node_id, p, d), 0)
                    for d in weekdays
                )
                assert week_production >= 1, \
                    f"Week {week_num+1}: {p} not produced"

            # Each weekday has 1-3 SKUs
            for d in weekdays:
                daily_skus = sum(
                    warmstart.get((manufacturing_node_id, p, d), 0)
                    for p in products
                )
                assert 1 <= daily_skus <= 3, \
                    f"Week {week_num+1}, {d}: {daily_skus} SKUs (expected 1-3)"

        print(f"✓ 4-week horizon validated")


class TestValidationFunctions:
    """Test validation helper functions."""

    def test_validate_warmstart_hints(self):
        """Test validate_warmstart_hints() function."""
        products = ['SKU_A', 'SKU_B']
        start_date = date(2025, 10, 20)
        end_date = start_date + timedelta(days=6)

        # Valid hints
        hints = {
            ("6122", "SKU_A", start_date): 1,
            ("6122", "SKU_B", start_date + timedelta(days=1)): 1,
        }

        # Should not raise
        validate_warmstart_hints(hints, products, start_date, end_date)

        # Invalid value
        invalid_hints = {
            ("6122", "SKU_A", start_date): 2,  # Not binary!
        }

        with pytest.raises(ValueError, match="must be binary"):
            validate_warmstart_hints(invalid_hints, products, start_date, end_date)

        # Invalid date
        invalid_date_hints = {
            ("6122", "SKU_A", start_date - timedelta(days=10)): 1,
        }

        with pytest.raises(ValueError, match="outside planning horizon"):
            validate_warmstart_hints(invalid_date_hints, products, start_date, end_date)

        print(f"✓ validate_warmstart_hints() works correctly")

    def test_validate_freshness_constraint(self):
        """Test validate_freshness_constraint() function."""
        start_date = date(2025, 10, 20)

        # Hints with 7-day gap (violates freshness)
        hints = {
            ("6122", "SKU_A", start_date): 1,
            ("6122", "SKU_A", start_date + timedelta(days=10)): 1,  # 10-day gap
        }

        # Should fail for 7-day freshness
        result = validate_freshness_constraint(hints, freshness_days=7)
        assert result is False, "Should detect freshness violation"

        # Should pass for 14-day freshness
        result = validate_freshness_constraint(hints, freshness_days=14)
        assert result is True, "Should pass with 14-day freshness"

        print(f"✓ validate_freshness_constraint() works correctly")

    def test_validate_daily_sku_limit(self):
        """Test validate_daily_sku_limit() function."""
        start_date = date(2025, 10, 20)

        # Hints with 5 SKUs on one day
        hints = {
            ("6122", f"SKU_{i}", start_date): 1
            for i in range(5)
        }

        # Should fail for limit=3
        result = validate_daily_sku_limit(hints, max_skus_per_day=3)
        assert result is False, "Should detect daily limit violation"

        # Should pass for limit=5
        result = validate_daily_sku_limit(hints, max_skus_per_day=5)
        assert result is True, "Should pass with limit=5"

        print(f"✓ validate_daily_sku_limit() works correctly")


class TestCreateDefaultWarmstart:
    """Test convenience function create_default_warmstart()."""

    def test_create_default_warmstart(self):
        """Test create_default_warmstart() with default parameters."""
        manufacturing_node_id = "6122"
        products = ['SKU_A', 'SKU_B', 'SKU_C']
        start_date = date(2025, 10, 20)
        end_date = start_date + timedelta(days=13)  # 2 weeks

        # Demand
        demand_forecast = {}
        current = start_date
        while current <= end_date:
            for p in products:
                demand_forecast[("6122", p, current)] = 3000.0
            current += timedelta(days=1)

        # Use convenience function
        warmstart = create_default_warmstart(
            demand_forecast=demand_forecast,
            manufacturing_node_id=manufacturing_node_id,
            products=products,
            start_date=start_date,
            end_date=end_date,
            max_daily_production=19600,
        )

        # Should use default parameters (3 SKUs/day, 7-day freshness)
        assert len(warmstart) > 0
        assert all(v in [0, 1] for v in warmstart.values())

        print(f"✓ create_default_warmstart() works with defaults")


@pytest.mark.slow
class TestWarmstartPerformance:
    """Performance tests for warmstart generation."""

    def test_generation_time_under_1_second(self):
        """Test that warmstart generation completes in <1 second."""
        import time

        manufacturing_node_id = "6122"
        products = [f'SKU_{i:03d}' for i in range(20)]  # 20 SKUs
        start_date = date(2025, 10, 20)
        end_date = start_date + timedelta(days=27)  # 4 weeks

        # Generate demand
        demand_forecast = {}
        current = start_date
        while current <= end_date:
            for p in products:
                demand_forecast[("6122", p, current)] = 5000.0
            current += timedelta(days=1)

        # Measure generation time
        start_time = time.time()
        warmstart = generate_campaign_warmstart(
            demand_forecast=demand_forecast,
            manufacturing_node_id=manufacturing_node_id,
            products=products,
            start_date=start_date,
            end_date=end_date,
            max_daily_production=19600,
            target_skus_per_weekday=3,
            freshness_days=7,
        )
        elapsed = time.time() - start_time

        # Should be fast (<1 second)
        assert elapsed < 1.0, f"Generation took {elapsed:.3f}s (expected <1s)"
        assert len(warmstart) > 0

        print(f"✓ Generation time: {elapsed:.3f}s for 20 SKUs × 28 days")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
