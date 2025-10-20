"""Demonstration of Weekly SKU Rotation Warmstart Generator.

This script demonstrates the warmstart generator with realistic examples
and shows how to use it with the optimization model.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import date, timedelta
from src.optimization.warmstart_generator import (
    WarmstartGenerator,
    RotationStrategy,
    create_default_warmstart,
)
from src.models.forecast import Forecast, ForecastEntry


def create_sample_forecast(products, start_date, end_date, demand_pattern="equal"):
    """Create sample forecast for demonstration.

    Args:
        products: List of product IDs
        start_date: Forecast start date
        end_date: Forecast end date
        demand_pattern: "equal" or "skewed" demand distribution

    Returns:
        Forecast object
    """
    entries = []
    current = start_date

    # Define demand quantities based on pattern
    if demand_pattern == "equal":
        quantities = {prod: 100.0 for prod in products}
    elif demand_pattern == "skewed":
        # 80% demand on first product, 5% on each other
        quantities = {}
        quantities[products[0]] = 400.0  # 80% of total
        for prod in products[1:]:
            quantities[prod] = 25.0  # 5% each
    else:
        quantities = {prod: 100.0 for prod in products}

    while current <= end_date:
        for product in products:
            entries.append(
                ForecastEntry(
                    location_id="6104",
                    product_id=product,
                    forecast_date=current,
                    quantity=quantities[product],
                )
            )
        current += timedelta(days=1)

    return Forecast(name=f"Demo Forecast ({demand_pattern})", entries=entries)


def demonstrate_all_strategies():
    """Demonstrate all rotation strategies."""

    print("=" * 80)
    print("WEEKLY SKU ROTATION WARMSTART GENERATOR DEMONSTRATION")
    print("=" * 80)
    print()

    # Setup
    products = ["PROD_001", "PROD_002", "PROD_003", "PROD_004", "PROD_005"]
    start_date = date(2025, 10, 20)  # Monday
    end_date = date(2025, 11, 17)  # 4 weeks

    # Test each strategy
    strategies = [
        (RotationStrategy.BALANCED, "equal"),
        (RotationStrategy.DEMAND_WEIGHTED, "skewed"),
        (RotationStrategy.FIXED_2_PER_DAY, "equal"),
        (RotationStrategy.FIXED_3_PER_DAY, "equal"),
        (RotationStrategy.ADAPTIVE, "skewed"),
    ]

    for strategy, demand_pattern in strategies:
        print(f"\n{'=' * 80}")
        print(f"STRATEGY: {strategy.upper()}")
        print(f"DEMAND PATTERN: {demand_pattern.upper()}")
        print(f"{'=' * 80}\n")

        # Create forecast
        forecast = create_sample_forecast(products, start_date, end_date, demand_pattern)

        # Create generator
        generator = WarmstartGenerator(
            products=products,
            forecast=forecast,
            strategy=strategy,
        )

        # Generate warmstart
        warmstart = generator.generate_warmstart(
            manufacturing_node_id="6122",
            start_date=start_date,
            end_date=end_date,
        )

        # Get pattern summary
        summary = generator.get_pattern_summary(start_date, end_date)
        print(summary)
        print()

        # Show first week warmstart values
        print("First Week Warmstart Values:")
        print("-" * 80)

        first_week_end = start_date + timedelta(days=6)
        weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        for current_date in [start_date + timedelta(days=i) for i in range(7)]:
            if current_date > first_week_end:
                break

            weekday_name = weekday_names[current_date.weekday()]
            print(f"\n{weekday_name} {current_date.strftime('%Y-%m-%d')}:")

            scheduled_products = []
            for product in products:
                key = ("6122", product, current_date)
                if key in warmstart and warmstart[key] == 1.0:
                    scheduled_products.append(product)

            if scheduled_products:
                print(f"  Produce: {', '.join(scheduled_products)} ({len(scheduled_products)} SKUs)")
            else:
                print("  No production scheduled")

        print()


def demonstrate_warmstart_application():
    """Demonstrate how to apply warmstart to optimization model."""

    print("\n" + "=" * 80)
    print("WARMSTART APPLICATION EXAMPLE")
    print("=" * 80)
    print()

    products = ["PROD_001", "PROD_002", "PROD_003", "PROD_004", "PROD_005"]
    start_date = date(2025, 10, 20)
    end_date = date(2025, 11, 17)

    # Create forecast
    forecast = create_sample_forecast(products, start_date, end_date, "skewed")

    # Generate warmstart using convenience function
    print("Using convenience function to generate warmstart...")
    warmstart = create_default_warmstart(
        manufacturing_node_id="6122",
        products=products,
        forecast=forecast,
        start_date=start_date,
        end_date=end_date,
        strategy=RotationStrategy.DEMAND_WEIGHTED,
    )

    print(f"Generated {len(warmstart)} warmstart values")
    print()

    # Count binary variables
    ones_count = sum(1 for v in warmstart.values() if v == 1.0)
    zeros_count = sum(1 for v in warmstart.values() if v == 0.0)

    print(f"Warmstart Statistics:")
    print(f"  Total variables: {len(warmstart)}")
    print(f"  Variables = 1.0 (produce): {ones_count}")
    print(f"  Variables = 0.0 (don't produce): {zeros_count}")
    print()

    # Show example usage with model
    print("Example usage with UnifiedNodeModel:")
    print("-" * 80)
    print("""
# Step 1: Build optimization model
model = UnifiedNodeModel(
    nodes=nodes,
    routes=routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    start_date=start_date,
    end_date=end_date,
)

# Step 2: Generate warmstart values
warmstart = create_default_warmstart(
    manufacturing_node_id="6122",
    products=product_ids,
    forecast=forecast,
    start_date=start_date,
    end_date=end_date,
)

# Step 3: Build Pyomo model
model.build()

# Step 4: Apply warmstart to product_produced binary variables
for (node_id, product, date), value in warmstart.items():
    if (node_id, product, date) in model.model.product_produced:
        model.model.product_produced[node_id, product, date].set_value(value)

# Step 5: Solve with warmstart
result = model.solve()

# The solver will use warmstart values as initial solution,
# potentially reducing solve time by 20-50%
    """)


def demonstrate_strategy_comparison():
    """Compare different strategies side-by-side."""

    print("\n" + "=" * 80)
    print("STRATEGY COMPARISON")
    print("=" * 80)
    print()

    products = ["PROD_001", "PROD_002", "PROD_003", "PROD_004", "PROD_005"]
    start_date = date(2025, 10, 20)
    end_date = date(2025, 10, 26)  # Just 1 week for comparison

    # Create skewed demand
    forecast = create_sample_forecast(products, start_date, end_date, "skewed")

    strategies = [
        RotationStrategy.BALANCED,
        RotationStrategy.DEMAND_WEIGHTED,
        RotationStrategy.ADAPTIVE,
    ]

    print("Weekly Production Schedule Comparison:")
    print("-" * 80)
    print(f"{'Weekday':<12}", end="")
    for strategy in strategies:
        print(f"{strategy:<25}", end="")
    print()
    print("-" * 80)

    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    for day_idx in range(5):
        day_name = weekday_names[day_idx]
        print(f"{day_name:<12}", end="")

        for strategy in strategies:
            generator = WarmstartGenerator(
                products=products,
                forecast=forecast,
                strategy=strategy,
            )

            demand_shares = generator._calculate_demand_shares(start_date, end_date)

            if strategy == RotationStrategy.BALANCED:
                pattern = generator._generate_balanced_pattern()
            elif strategy == RotationStrategy.DEMAND_WEIGHTED:
                pattern = generator._generate_demand_weighted_pattern(demand_shares)
            elif strategy == RotationStrategy.ADAPTIVE:
                pattern = generator._generate_adaptive_pattern(demand_shares)
            else:
                pattern = {}

            products_for_day = pattern.get(day_idx, [])

            if products_for_day:
                products_str = ", ".join([p.replace("PROD_", "P") for p in products_for_day])
                print(f"{products_str:<25}", end="")
            else:
                print(f"{'(none)':<25}", end="")

        print()

    print("-" * 80)
    print()

    # Show demand distribution
    print("Demand Distribution:")
    print("-" * 80)

    generator = WarmstartGenerator(
        products=products,
        forecast=forecast,
        strategy=RotationStrategy.BALANCED,
    )
    demand_shares = generator._calculate_demand_shares(start_date, end_date)

    for product in products:
        share = demand_shares.get(product, 0.0)
        bar_length = int(share * 50)
        bar = "█" * bar_length
        print(f"{product}: {share:6.1%} {bar}")

    print()


if __name__ == "__main__":
    # Run demonstrations
    demonstrate_all_strategies()
    demonstrate_strategy_comparison()
    demonstrate_warmstart_application()

    print("\n" + "=" * 80)
    print("DEMONSTRATION COMPLETE")
    print("=" * 80)
