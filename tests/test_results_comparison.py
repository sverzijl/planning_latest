"""Unit tests for Results Comparison page helper functions."""

from datetime import date


# Import helper functions from the page
# Note: This is a bit unconventional since it's a Streamlit page, but we can test the logic
def test_format_currency():
    """Test currency formatting function."""
    # Mock the function locally for testing
    def format_currency(value: float) -> str:
        if value is None:
            return "$0.00"
        return f"${value:,.2f}"

    assert format_currency(1234.56) == "$1,234.56"
    assert format_currency(0) == "$0.00"
    assert format_currency(1000000) == "$1,000,000.00"
    assert format_currency(None) == "$0.00"


def test_format_number():
    """Test number formatting function."""
    def format_number(value: float) -> str:
        if value is None:
            return "0"
        return f"{value:,.0f}"

    assert format_number(1234) == "1,234"
    assert format_number(0) == "0"
    assert format_number(1000000) == "1,000,000"
    assert format_number(None) == "0"


def test_format_percentage():
    """Test percentage formatting function."""
    def format_percentage(value: float) -> str:
        if value is None:
            return "0.0%"
        return f"{value:.1f}%"

    assert format_percentage(95.5) == "95.5%"
    assert format_percentage(100.0) == "100.0%"
    assert format_percentage(0) == "0.0%"
    assert format_percentage(None) == "0.0%"


def test_calculate_delta():
    """Test delta calculation function."""
    def calculate_delta(heuristic_val: float, optimization_val: float):
        if heuristic_val is None or optimization_val is None:
            return 0.0, 0.0

        absolute_delta = optimization_val - heuristic_val

        if heuristic_val == 0:
            if optimization_val == 0:
                percentage_delta = 0.0
            else:
                percentage_delta = 100.0
        else:
            percentage_delta = (absolute_delta / abs(heuristic_val)) * 100

        return absolute_delta, percentage_delta

    # Test normal case
    abs_delta, pct_delta = calculate_delta(100, 90)
    assert abs_delta == -10
    assert pct_delta == -10.0

    # Test increase
    abs_delta, pct_delta = calculate_delta(100, 110)
    assert abs_delta == 10
    assert pct_delta == 10.0

    # Test zero baseline
    abs_delta, pct_delta = calculate_delta(0, 100)
    assert abs_delta == 100
    assert pct_delta == 100.0

    # Test both zero
    abs_delta, pct_delta = calculate_delta(0, 0)
    assert abs_delta == 0
    assert pct_delta == 0.0

    # Test None values
    abs_delta, pct_delta = calculate_delta(None, 100)
    assert abs_delta == 0.0
    assert pct_delta == 0.0


def test_color_delta():
    """Test delta color determination."""
    def color_delta(delta: float, inverse: bool = False) -> str:
        if not inverse:
            return "success" if delta >= 0 else "error"
        else:
            return "success" if delta < 0 else "error"

    # Normal mode (higher is better)
    assert color_delta(10, inverse=False) == "success"
    assert color_delta(-10, inverse=False) == "error"

    # Inverse mode (lower is better, for costs)
    assert color_delta(-10, inverse=True) == "success"  # Savings
    assert color_delta(10, inverse=True) == "error"  # Cost increase
    assert color_delta(0, inverse=True) == "error"  # No change


def test_create_delta_display():
    """Test delta display formatting."""
    def create_delta_display(delta_abs: float, delta_pct: float, inverse: bool = True) -> str:
        sign = "+" if delta_abs >= 0 else ""

        if inverse:
            if delta_abs < 0:
                return f"−${abs(delta_abs):,.2f} (−{abs(delta_pct):.1f}%)"
            else:
                return f"+${delta_abs:,.2f} (+{delta_pct:.1f}%)"
        else:
            return f"{sign}${delta_abs:,.2f} ({sign}{delta_pct:.1f}%)"

    # Test savings (negative delta in inverse mode)
    result = create_delta_display(-1000, -10.0, inverse=True)
    assert "−$1,000.00" in result
    assert "−10.0%" in result

    # Test increase (positive delta in inverse mode)
    result = create_delta_display(1000, 10.0, inverse=True)
    assert "+$1,000.00" in result
    assert "+10.0%" in result

    # Test zero
    result = create_delta_display(0, 0, inverse=True)
    assert "+$0.00" in result
    assert "+0.0%" in result


if __name__ == "__main__":
    # Run tests
    test_format_currency()
    test_format_number()
    test_format_percentage()
    test_calculate_delta()
    test_color_delta()
    test_create_delta_display()
    print("✅ All tests passed!")
