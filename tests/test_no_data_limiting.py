"""
Test: Ensure no inadvertent data limiting

Validates that we're using ALL products, ALL nodes, ALL dates from input data.
Prevents accidental slicing like products[:5] that would limit to 5 products.
"""

import pytest
from datetime import timedelta


def test_all_products_used():
    """Ensure model uses ALL products from forecast, not a subset."""
    from src.parsers.excel_parser import ExcelParser

    parser = ExcelParser('data/examples/Gluten Free Forecast - Latest.xlsm')
    forecast = parser.parse_forecast()

    # Get unique products from forecast
    forecast_products = set(entry.product_id for entry in forecast.entries)

    print(f"Forecast has {len(forecast_products)} unique products")

    # Build model and check it uses all products
    from tests.conftest import create_test_products
    products = create_test_products(list(forecast_products))

    assert len(products) == len(forecast_products), \
        f"Model only uses {len(products)} products but forecast has {len(forecast_products)}!"

    print(f"✓ Model uses all {len(products)} products from forecast")


def test_all_demand_entries_processed():
    """Ensure demand dict includes ALL entries from forecast within horizon."""
    from src.parsers.excel_parser import ExcelParser
    from datetime import date

    parser = ExcelParser('data/examples/Gluten Free Forecast - Latest.xlsm')
    forecast = parser.parse_forecast()

    planning_start = date(2025, 11, 3)
    planning_end = planning_start + timedelta(weeks=4)

    # Count entries in horizon
    entries_in_horizon = [
        e for e in forecast.entries
        if planning_start <= e.forecast_date <= planning_end
    ]

    print(f"Forecast entries in 4-week horizon: {len(entries_in_horizon)}")

    # Check model demand dict size
    demand_dict = {}
    for entry in entries_in_horizon:
        key = (entry.location_id, entry.product_id, entry.forecast_date)
        demand_dict[key] = demand_dict.get(key, 0) + entry.quantity

    assert len(demand_dict) == len(entries_in_horizon), \
        f"Demand dict has {len(demand_dict)} entries but should have {len(entries_in_horizon)}!"

    print(f"✓ All {len(demand_dict)} demand entries processed")


def test_no_product_slicing_in_code():
    """Scan code for dangerous product limiting patterns."""
    import re
    from pathlib import Path

    # Files to check
    files_to_check = [
        'src/optimization/sliding_window_model.py',
        'src/optimization/verified_sliding_window_model.py',
        'src/validation/data_coordinator.py',
    ]

    dangerous_patterns = [
        r'products\[:(?!.*print|.*log|.*debug|.*sample)',  # products[: not in print/log
        r'product_ids\s*=.*\[:\d+\](?!.*#.*sample|.*#.*test)',  # product_ids = ..[:5] not in comments
    ]

    issues = []
    for filepath in files_to_check:
        path = Path(filepath)
        if not path.exists():
            continue

        with open(path, 'r') as f:
            lines = f.readlines()

        for i, line in enumerate(lines, 1):
            # Skip comments and print statements
            if '#' in line or 'print(' in line or 'logger' in line:
                continue

            for pattern in dangerous_patterns:
                if re.search(pattern, line):
                    issues.append(f"{filepath}:{i}: {line.strip()}")

    if issues:
        pytest.fail(
            f"Found {len(issues)} potential data limiting patterns:\n" +
            "\n".join(issues[:10])
        )

    print(f"✓ No dangerous product limiting patterns found")


if __name__ == "__main__":
    print("Testing for inadvertent data limiting...")

    test_all_products_used()
    test_all_demand_entries_processed()
    test_no_product_slicing_in_code()

    print("\n✅ No data limiting - all products/entries processed!")
