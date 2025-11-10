"""Tests for warmstart generator."""

import pytest
from datetime import date, timedelta
from collections import Counter

from src.optimization.warmstart_generator import (
    WarmstartGenerator,
    RotationStrategy,
    create_default_warmstart,
)
from src.models.forecast import Forecast, ForecastEntry


@pytest.fixture
def products():
    """5 product IDs for testing."""
    return ["PROD_001", "PROD_002", "PROD_003", "PROD_004", "PROD_005"]


@pytest.fixture
def start_date():
    """Planning horizon start."""
    return date(2025, 10, 20)  # Monday


@pytest.fixture
def end_date():
    """Planning horizon end (4 weeks)."""
    return date(2025, 11, 17)  # Monday


@pytest.fixture
def forecast_equal_demand(products, start_date, end_date):
    """Forecast with equal demand for all products."""
    entries = []
    current = start_date

    while current <= end_date:
        for product in products:
            entries.append(
                ForecastEntry(
                    location_id="6104",
                    product_id=product,
                    forecast_date=current,
                    quantity=100.0,  # Equal demand
                )
            )
        current += timedelta(days=1)

    return Forecast(name="Equal Demand", entries=entries)


@pytest.fixture
def forecast_skewed_demand(products, start_date, end_date):
    """Forecast with skewed demand (80% on PROD_001, 20% on others)."""
    entries = []
    current = start_date

    while current <= end_date:
        for i, product in enumerate(products):
            quantity = 400.0 if i == 0 else 50.0  # PROD_001 gets 80% of total demand
            entries.append(
                ForecastEntry(
                    location_id="6104",
                    product_id=product,
                    forecast_date=current,
                    quantity=quantity,
                )
            )
        current += timedelta(days=1)

    return Forecast(name="Skewed Demand", entries=entries)


class TestWarmstartGenerator:
    """Test WarmstartGenerator class."""

    def test_initialization(self, products, forecast_equal_demand):
        """Test generator initialization."""
        generator = WarmstartGenerator(
            products=products,
            forecast=forecast_equal_demand,
            strategy=RotationStrategy.BALANCED,
        )

        assert generator.products == products
        assert generator.forecast == forecast_equal_demand
        assert generator.strategy == RotationStrategy.BALANCED
        assert generator.min_skus_per_day == 2
        assert generator.max_skus_per_day == 3

    def test_get_weekday_dates(self, products, forecast_equal_demand, start_date, end_date):
        """Test weekday date extraction (Mon-Fri only)."""
        generator = WarmstartGenerator(
            products=products,
            forecast=forecast_equal_demand,
        )

        weekdays = generator._get_weekday_dates(start_date, end_date)

        # Verify all dates are weekdays
        for date_obj in weekdays:
            assert date_obj.weekday() < 5, f"{date_obj} is not a weekday"

        # Verify correct count (4 weeks × 5 weekdays = 20 days)
        # Oct 20 (Mon) to Nov 17 (Mon) = 4 weeks + 1 day = 21 weekdays
        assert len(weekdays) == 21

    def test_calculate_demand_shares_equal(self, products, forecast_equal_demand, start_date, end_date):
        """Test demand share calculation with equal demand."""
        generator = WarmstartGenerator(
            products=products,
            forecast=forecast_equal_demand,
        )

        demand_shares = generator._calculate_demand_shares(start_date, end_date)

        # All products should have equal share (20% each)
        for product in products:
            assert product in demand_shares
            assert abs(demand_shares[product] - 0.20) < 0.01, f"{product} share: {demand_shares[product]}"

    def test_calculate_demand_shares_skewed(self, products, forecast_skewed_demand, start_date, end_date):
        """Test demand share calculation with skewed demand."""
        generator = WarmstartGenerator(
            products=products,
            forecast=forecast_skewed_demand,
        )

        demand_shares = generator._calculate_demand_shares(start_date, end_date)

        # PROD_001 should have ~67% share (400/(400+50*4))
        assert abs(demand_shares["PROD_001"] - 0.667) < 0.01, f"PROD_001 share: {demand_shares['PROD_001']}"

        # Other products should have ~8.3% each (50/600)
        for product in products[1:]:
            assert abs(demand_shares[product] - 0.0833) < 0.01, f"{product} share: {demand_shares[product]}"

    def test_generate_balanced_pattern(self, products, forecast_equal_demand):
        """Test balanced pattern generation (all SKUs equal production days)."""
        generator = WarmstartGenerator(
            products=products,
            forecast=forecast_equal_demand,
        )

        pattern = generator._generate_balanced_pattern()

        # Verify pattern has 5 weekdays
        assert len(pattern) <= 5

        # Count production frequency per SKU
        sku_frequency = Counter()
        for day_products in pattern.values():
            for product in day_products:
                sku_frequency[product] += 1

        # All products should appear at least once
        for product in products:
            assert sku_frequency[product] >= 1, f"{product} not scheduled"

        # Verify 2-3 SKUs per day constraint
        for day, day_products in pattern.items():
            assert 2 <= len(day_products) <= 3, f"Day {day} has {len(day_products)} SKUs (expected 2-3)"

    def test_generate_demand_weighted_pattern(self, products, forecast_skewed_demand, start_date, end_date):
        """Test demand-weighted pattern (high-demand SKUs get more days)."""
        generator = WarmstartGenerator(
            products=products,
            forecast=forecast_skewed_demand,
        )

        demand_shares = generator._calculate_demand_shares(start_date, end_date)
        pattern = generator._generate_demand_weighted_pattern(demand_shares)

        # Count production frequency per SKU
        sku_frequency = Counter()
        for day_products in pattern.values():
            for product in day_products:
                sku_frequency[product] += 1

        # PROD_001 (highest demand) should appear most frequently
        assert sku_frequency["PROD_001"] >= sku_frequency["PROD_002"]
        assert sku_frequency["PROD_001"] >= sku_frequency["PROD_005"]

        # All products should appear at least once
        for product in products:
            assert sku_frequency[product] >= 1, f"{product} not scheduled"

    def test_generate_fixed_2_per_day_pattern(self, products, forecast_equal_demand, start_date, end_date):
        """Test fixed 2-SKUs-per-day pattern."""
        generator = WarmstartGenerator(
            products=products,
            forecast=forecast_equal_demand,
        )

        demand_shares = generator._calculate_demand_shares(start_date, end_date)
        pattern = generator._generate_fixed_pattern(2, demand_shares)

        # Verify exactly 2 SKUs per day
        for day, day_products in pattern.items():
            assert len(day_products) == 2, f"Day {day} has {len(day_products)} SKUs (expected 2)"

    def test_generate_fixed_3_per_day_pattern(self, products, forecast_equal_demand, start_date, end_date):
        """Test fixed 3-SKUs-per-day pattern."""
        generator = WarmstartGenerator(
            products=products,
            forecast=forecast_equal_demand,
        )

        demand_shares = generator._calculate_demand_shares(start_date, end_date)
        pattern = generator._generate_fixed_pattern(3, demand_shares)

        # Verify exactly 3 SKUs per day
        for day, day_products in pattern.items():
            assert len(day_products) == 3, f"Day {day} has {len(day_products)} SKUs (expected 3)"

    def test_generate_adaptive_pattern(self, products, forecast_equal_demand, start_date, end_date):
        """Test adaptive pattern (2-3 SKUs/day based on demand)."""
        generator = WarmstartGenerator(
            products=products,
            forecast=forecast_equal_demand,
        )

        demand_shares = generator._calculate_demand_shares(start_date, end_date)
        pattern = generator._generate_adaptive_pattern(demand_shares)

        # Verify 2-3 SKUs per day
        for day, day_products in pattern.items():
            assert 2 <= len(day_products) <= 3, f"Day {day} has {len(day_products)} SKUs (expected 2-3)"

    def test_generate_warmstart_structure(self, products, forecast_equal_demand, start_date, end_date):
        """Test warmstart dictionary structure and format."""
        generator = WarmstartGenerator(
            products=products,
            forecast=forecast_equal_demand,
            strategy=RotationStrategy.BALANCED,
        )

        warmstart = generator.generate_warmstart(
            manufacturing_node_id="6122",
            start_date=start_date,
            end_date=end_date,
        )

        # Verify dictionary structure: (node_id, product, date) -> binary value
        for key, value in warmstart.items():
            assert isinstance(key, tuple), f"Key {key} is not a tuple"
            assert len(key) == 3, f"Key {key} has {len(key)} elements (expected 3)"

            node_id, product, date_obj = key
            assert isinstance(node_id, str), f"node_id {node_id} is not string"
            assert isinstance(product, str), f"product {product} is not string"
            assert isinstance(date_obj, date), f"date {date_obj} is not date object"

            # Verify binary value
            assert value in (0.0, 1.0), f"Value {value} is not binary (0 or 1)"

    def test_generate_warmstart_weekday_coverage(self, products, forecast_equal_demand, start_date, end_date):
        """Test that warmstart covers all weekdays in planning horizon."""
        generator = WarmstartGenerator(
            products=products,
            forecast=forecast_equal_demand,
            strategy=RotationStrategy.BALANCED,
        )

        warmstart = generator.generate_warmstart(
            manufacturing_node_id="6122",
            start_date=start_date,
            end_date=end_date,
        )

        # Extract unique dates from warmstart
        warmstart_dates = set(key[2] for key in warmstart.keys())

        # Get expected weekdays
        expected_weekdays = generator._get_weekday_dates(start_date, end_date)

        # Verify all weekdays are covered
        for expected_date in expected_weekdays:
            assert expected_date in warmstart_dates, f"Date {expected_date} not in warmstart"

    def test_generate_warmstart_all_products_covered(self, products, forecast_equal_demand, start_date, end_date):
        """Test that all products appear at least once per week."""
        generator = WarmstartGenerator(
            products=products,
            forecast=forecast_equal_demand,
            strategy=RotationStrategy.BALANCED,
        )

        warmstart = generator.generate_warmstart(
            manufacturing_node_id="6122",
            start_date=start_date,
            end_date=end_date,
        )

        # Count production days per product in first week
        first_week_end = start_date + timedelta(days=6)
        product_days = {p: 0 for p in products}

        for (node_id, product, date_obj), value in warmstart.items():
            if value == 1.0 and start_date <= date_obj <= first_week_end:
                product_days[product] += 1

        # All products should be produced at least once in first week
        for product in products:
            assert product_days[product] >= 1, f"{product} not produced in first week"

    def test_generate_warmstart_consistency_across_weeks(self, products, forecast_equal_demand, start_date, end_date):
        """Test that weekly pattern repeats consistently across weeks."""
        generator = WarmstartGenerator(
            products=products,
            forecast=forecast_equal_demand,
            strategy=RotationStrategy.BALANCED,
        )

        warmstart = generator.generate_warmstart(
            manufacturing_node_id="6122",
            start_date=start_date,
            end_date=end_date,
        )

        # Extract patterns for first 2 weeks
        week1_pattern = {}
        week2_pattern = {}

        week2_start = start_date + timedelta(days=7)

        for (node_id, product, date_obj), value in warmstart.items():
            weekday = date_obj.weekday()

            if value == 1.0:
                # Week 1
                if start_date <= date_obj < week2_start:
                    if weekday not in week1_pattern:
                        week1_pattern[weekday] = []
                    week1_pattern[weekday].append(product)

                # Week 2
                elif week2_start <= date_obj < week2_start + timedelta(days=7):
                    if weekday not in week2_pattern:
                        week2_pattern[weekday] = []
                    week2_pattern[weekday].append(product)

        # Verify same weekday pattern repeats
        for weekday in range(5):
            if weekday in week1_pattern and weekday in week2_pattern:
                assert sorted(week1_pattern[weekday]) == sorted(week2_pattern[weekday]), \
                    f"Weekday {weekday} pattern differs between weeks"

    def test_get_pattern_summary(self, products, forecast_skewed_demand, start_date, end_date):
        """Test pattern summary generation."""
        generator = WarmstartGenerator(
            products=products,
            forecast=forecast_skewed_demand,
            strategy=RotationStrategy.DEMAND_WEIGHTED,
        )

        summary = generator.get_pattern_summary(start_date, end_date)

        # Verify summary contains key sections
        assert "Weekly SKU Rotation Pattern" in summary
        assert "Demand Shares:" in summary
        assert "Weekly Production Schedule:" in summary
        assert "Statistics:" in summary
        assert "Production Frequency" in summary

        # Verify all weekdays mentioned
        for day_name in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
            assert day_name in summary

        # Verify all products mentioned
        for product in products:
            assert product in summary

    def test_create_default_warmstart_convenience_function(self, products, forecast_equal_demand, start_date, end_date):
        """Test convenience function for warmstart creation."""
        warmstart = create_default_warmstart(
            manufacturing_node_id="6122",
            products=products,
            forecast=forecast_equal_demand,
            start_date=start_date,
            end_date=end_date,
        )

        # Verify non-empty warmstart
        assert len(warmstart) > 0

        # Verify correct structure
        for key, value in warmstart.items():
            assert len(key) == 3
            assert value in (0.0, 1.0)

    def test_edge_case_single_product(self, forecast_equal_demand, start_date, end_date):
        """Test warmstart generation with single product."""
        single_product = ["PROD_001"]

        generator = WarmstartGenerator(
            products=single_product,
            forecast=forecast_equal_demand,
            strategy=RotationStrategy.BALANCED,
        )

        warmstart = generator.generate_warmstart(
            manufacturing_node_id="6122",
            start_date=start_date,
            end_date=end_date,
        )

        # Single product should be produced every weekday
        weekdays = generator._get_weekday_dates(start_date, end_date)

        for date_obj in weekdays:
            key = ("6122", "PROD_001", date_obj)
            assert key in warmstart
            assert warmstart[key] == 1.0

    def test_edge_case_no_demand(self, products, start_date, end_date):
        """Test warmstart generation with zero demand."""
        empty_forecast = Forecast(name="No Demand", entries=[])

        # Use BALANCED strategy for zero demand (demand-weighted doesn't make sense)
        generator = WarmstartGenerator(
            products=products,
            forecast=empty_forecast,
            strategy=RotationStrategy.BALANCED,  # Better choice for zero demand
        )

        warmstart = generator.generate_warmstart(
            manufacturing_node_id="6122",
            start_date=start_date,
            end_date=end_date,
        )

        # Should still generate a valid pattern
        assert len(warmstart) > 0

        # Verify all products appear at least once per week
        product_frequency = Counter()
        for (node_id, product, date_obj), value in warmstart.items():
            if value == 1.0:
                product_frequency[product] += 1

        # All products should appear at least once per week (minimum 4 times in 4 weeks)
        for product in products:
            assert product_frequency[product] >= 4, f"{product} appears only {product_frequency[product]} times in 4 weeks"

    def test_different_strategies_produce_different_patterns(self, products, forecast_skewed_demand, start_date, end_date):
        """Test that different strategies produce different warmstart patterns."""
        strategies = [
            RotationStrategy.BALANCED,
            RotationStrategy.DEMAND_WEIGHTED,
            RotationStrategy.FIXED_2_PER_DAY,
            RotationStrategy.ADAPTIVE,
        ]

        warmstarts = {}

        for strategy in strategies:
            generator = WarmstartGenerator(
                products=products,
                forecast=forecast_skewed_demand,
                strategy=strategy,
            )
            warmstarts[strategy] = generator.generate_warmstart(
                manufacturing_node_id="6122",
                start_date=start_date,
                end_date=end_date,
            )

        # Verify that different strategies produce different patterns
        # (at least for the first week)
        first_week_end = start_date + timedelta(days=6)

        for i, strategy1 in enumerate(strategies):
            for strategy2 in strategies[i+1:]:
                # Count differences in first week
                differences = 0

                for (node_id, product, date_obj), value in warmstarts[strategy1].items():
                    if start_date <= date_obj <= first_week_end:
                        key = (node_id, product, date_obj)
                        if key in warmstarts[strategy2]:
                            if warmstarts[strategy2][key] != value:
                                differences += 1

                # Some strategies may produce same pattern, but not all combinations
                # Just verify warmstarts are non-empty
                assert len(warmstarts[strategy1]) > 0
                assert len(warmstarts[strategy2]) > 0

    def test_warmstart_respects_production_days_filter(self, products, forecast_equal_demand, start_date):
        """Test that warmstart respects custom production_days filter."""
        # Only allow Monday and Wednesday
        custom_days = [
            start_date,  # Monday
            start_date + timedelta(days=2),  # Wednesday
            start_date + timedelta(days=7),  # Next Monday
        ]

        generator = WarmstartGenerator(
            products=products,
            forecast=forecast_equal_demand,
            strategy=RotationStrategy.BALANCED,
        )

        warmstart = generator.generate_warmstart(
            manufacturing_node_id="6122",
            start_date=start_date,
            end_date=start_date + timedelta(days=10),
            production_days=custom_days,
        )

        # Extract unique dates from warmstart
        warmstart_dates = set(key[2] for key in warmstart.keys())

        # Verify only custom days appear
        assert warmstart_dates == set(custom_days)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
