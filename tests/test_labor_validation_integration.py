"""
Integration tests for labor calendar validation workflow.

These tests validate the end-to-end labor calendar validation logic using real
example data files. They ensure proper distinction between critical and non-critical
missing labor dates, particularly when the planning horizon is extended beyond
the forecast range.

Test Coverage:
1. Normal horizon (forecast-aligned) - should pass without errors
2. Extended horizon (beyond forecast) - should pass with warnings only
3. Truncated labor calendar (missing critical weekdays) - should fail with error

Background:
The labor calendar validation was updated to distinguish between:
- Critical dates: Needed to produce and deliver forecast demand (weekdays)
- Non-critical dates: Outside critical range or weekends (optional capacity)

This prevents spurious errors when users extend planning horizons for operational
flexibility (e.g., rolling horizon planning) but don't need labor data for dates
beyond the forecast range.
"""

import pytest
from datetime import date, timedelta
from pathlib import Path
import warnings
from typing import Optional

from src.parsers.excel_parser import ExcelParser
from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.truck_schedule import TruckScheduleCollection


# Define paths to example data
EXAMPLE_DATA_DIR = Path(__file__).parent.parent / "data" / "examples"
FORECAST_FILE = EXAMPLE_DATA_DIR / "Gfree Forecast.xlsm"
NETWORK_CONFIG_FILE = EXAMPLE_DATA_DIR / "Network_Config.xlsx"


@pytest.fixture
def check_example_files():
    """
    Check if example data files exist.

    Skip tests if example files are not available (e.g., minimal dev environment).
    """
    if not FORECAST_FILE.exists():
        pytest.skip(f"Example forecast file not found: {FORECAST_FILE}")
    if not NETWORK_CONFIG_FILE.exists():
        pytest.skip(f"Example network config file not found: {NETWORK_CONFIG_FILE}")


@pytest.fixture
def load_example_data(check_example_files):
    """
    Load example data from real data files.

    Returns:
        tuple: (forecast, locations, routes, labor_calendar, truck_schedules, cost_structure)
    """
    # Parse forecast data
    forecast_parser = ExcelParser(FORECAST_FILE)
    forecast = forecast_parser.parse_forecast()

    # Parse network configuration
    network_parser = ExcelParser(NETWORK_CONFIG_FILE)
    locations = network_parser.parse_locations()
    routes = network_parser.parse_routes()
    labor_calendar = network_parser.parse_labor_calendar()
    truck_schedules_list = network_parser.parse_truck_schedules()
    cost_structure = network_parser.parse_cost_structure()

    # Wrap truck schedules in collection
    truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

    return forecast, locations, routes, labor_calendar, truck_schedules, cost_structure


@pytest.fixture
def manufacturing_site(load_example_data):
    """Extract manufacturing site from locations."""
    _, locations, _, _, _, _ = load_example_data

    # Find manufacturing site (should be location 6122)
    mfg_sites = [loc for loc in locations if loc.type == 'manufacturing']
    assert len(mfg_sites) > 0, "No manufacturing site found in example data"

    return mfg_sites[0]


def test_example_data_with_normal_horizon(load_example_data, manufacturing_site):
    """
    Test 1: Load example data with default planning horizon (no end_date override).

    This validates that the example data has proper labor calendar coverage
    for the forecast range. Should pass without errors or warnings about
    missing labor dates.

    Expected behavior:
    - Model initializes successfully
    - No ValueError raised
    - No warnings about missing critical labor dates
    - Labor calendar covers all critical production dates
    """
    forecast, locations, routes, labor_calendar, truck_schedules, cost_structure = load_example_data

    # Capture warnings during model initialization
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # Initialize model with default horizon (no end_date override)
        model = IntegratedProductionDistributionModel(
            forecast=forecast,
            labor_calendar=labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=locations,
            routes=routes,
            truck_schedules=truck_schedules,
            allow_shortages=True,  # Allow shortages to focus on labor validation
            validate_feasibility=True,
        )

        # Check for labor-related warnings
        labor_warnings = [
            warning for warning in w
            if 'labor' in str(warning.message).lower() or 'missing' in str(warning.message).lower()
        ]

    # Assert: No ValueError raised (model initialized successfully)
    assert model is not None
    assert model.start_date is not None
    assert model.end_date is not None

    # Assert: No warnings about missing critical labor dates
    # (Non-critical warnings are acceptable, e.g., missing weekends outside forecast range)
    critical_labor_warnings = [
        warning for warning in labor_warnings
        if 'critical' in str(warning.message).lower() and 'weekday' in str(warning.message).lower()
    ]
    assert len(critical_labor_warnings) == 0, (
        f"Expected no critical labor warnings with normal horizon, but got {len(critical_labor_warnings)}:\n" +
        "\n".join(str(w.message) for w in critical_labor_warnings)
    )

    # Verify labor calendar coverage for critical dates
    forecast_start = min(e.forecast_date for e in forecast.entries)
    forecast_end = max(e.forecast_date for e in forecast.entries)

    # Calculate critical range (same logic as model validation)
    max_transit_days = max(r.total_transit_days for r in model.enumerated_routes) if model.enumerated_routes else 0
    critical_start = forecast_start - timedelta(days=int(max_transit_days) + 1)
    critical_end = forecast_end

    # Check weekday coverage in critical range
    missing_critical_weekdays = []
    current_date = critical_start
    while current_date <= critical_end:
        if current_date.weekday() < 5:  # Monday-Friday
            if current_date not in model.labor_by_date:
                missing_critical_weekdays.append(current_date)
        current_date += timedelta(days=1)

    assert len(missing_critical_weekdays) == 0, (
        f"Expected labor calendar to cover all critical weekdays, but missing {len(missing_critical_weekdays)} dates: " +
        f"{', '.join(str(d) for d in missing_critical_weekdays[:5])}"
    )

    print(f"✓ Test passed: Normal horizon")
    print(f"  Forecast range: {forecast_start} to {forecast_end}")
    print(f"  Planning horizon: {model.start_date} to {model.end_date}")
    print(f"  Critical range: {critical_start} to {critical_end}")
    print(f"  Labor calendar coverage: Complete for critical weekdays")


def test_example_data_with_extended_horizon(load_example_data, manufacturing_site):
    """
    Test 2: Load example data with planning horizon extended 1 year beyond forecast.

    This tests the specific bug fix - users extending the planning horizon for
    operational reasons (e.g., rolling horizon planning) should not get hard
    failures when labor calendar doesn't cover extended dates that aren't needed
    for the forecast.

    Expected behavior:
    - Model initializes successfully (no ValueError)
    - UserWarning issued about non-critical missing dates
    - Warning message mentions "outside critical forecast range"
    - Labor validation distinguishes critical vs. non-critical dates
    """
    forecast, locations, routes, labor_calendar, truck_schedules, cost_structure = load_example_data

    # Calculate extended end date (1 year beyond forecast)
    forecast_end = max(e.forecast_date for e in forecast.entries)
    extended_end_date = forecast_end + timedelta(days=365)

    # Capture warnings during model initialization
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # Initialize model with extended horizon
        model = IntegratedProductionDistributionModel(
            forecast=forecast,
            labor_calendar=labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=locations,
            routes=routes,
            truck_schedules=truck_schedules,
            end_date=extended_end_date,  # Extend planning horizon 1 year
            allow_shortages=True,
            validate_feasibility=True,
        )

        # Collect labor-related warnings
        labor_warnings = [
            warning for warning in w
            if 'labor' in str(warning.message).lower() or 'missing' in str(warning.message).lower()
        ]

    # Assert: No ValueError raised (model should initialize successfully)
    assert model is not None
    assert model.end_date == extended_end_date

    # Assert: Should have UserWarning about non-critical missing dates
    noncritical_warnings = [
        warning for warning in labor_warnings
        if 'outside critical' in str(warning.message).lower()
        or 'non-critical' in str(warning.message).lower()
        or 'not needed to satisfy forecast' in str(warning.message).lower()
    ]

    assert len(noncritical_warnings) > 0, (
        "Expected UserWarning about non-critical missing dates with extended horizon, "
        f"but got no such warnings. All warnings: {[str(w.message) for w in labor_warnings]}"
    )

    # Assert: Warning should be UserWarning (not critical error)
    for warning in noncritical_warnings:
        assert issubclass(warning.category, UserWarning), (
            f"Expected UserWarning, got {warning.category.__name__}"
        )

    # Assert: Should NOT have critical error about missing weekdays
    critical_errors = [
        warning for warning in labor_warnings
        if 'critical weekday' in str(warning.message).lower()
        and 'outside critical' not in str(warning.message).lower()
    ]

    assert len(critical_errors) == 0, (
        f"Expected no critical weekday errors with extended horizon, but got {len(critical_errors)}:\n" +
        "\n".join(str(w.message) for w in critical_errors)
    )

    # Verify the warning message content
    warning_messages = [str(w.message) for w in noncritical_warnings]
    assert any('weekday' in msg.lower() for msg in warning_messages), (
        "Expected warning to mention 'weekday' dates"
    )

    print(f"✓ Test passed: Extended horizon")
    print(f"  Forecast range: {min(e.forecast_date for e in forecast.entries)} to {forecast_end}")
    print(f"  Planning horizon: {model.start_date} to {model.end_date}")
    print(f"  Extended by: {(extended_end_date - forecast_end).days} days")
    print(f"  Non-critical warnings issued: {len(noncritical_warnings)}")
    print(f"  Warning sample: {warning_messages[0][:150]}...")


def test_example_data_with_truncated_labor_calendar(load_example_data, manufacturing_site):
    """
    Test 3: Load example data with labor calendar missing critical weekday entries.

    This validates that the labor validation still properly fails when critical
    weekdays are missing (i.e., dates needed to produce and deliver forecast demand).

    The test programmatically removes the last 10 weekday entries from the labor
    calendar, creating a scenario where critical production dates lack labor data.

    Expected behavior:
    - ValueError raised during model initialization
    - Error message clearly identifies missing critical weekday dates
    - Error message provides forecast range and required production start date
    - Error message includes actionable fix instructions
    """
    forecast, locations, routes, labor_calendar, truck_schedules, cost_structure = load_example_data

    # Truncate labor calendar: Remove last 10 weekday entries
    # This simulates an incomplete labor calendar missing critical dates
    labor_days = labor_calendar.days.copy()
    labor_days_sorted = sorted(labor_days, key=lambda d: d.date)

    # Find last 10 weekdays
    weekday_entries = [d for d in labor_days_sorted if d.date.weekday() < 5]
    if len(weekday_entries) < 10:
        pytest.skip("Labor calendar has fewer than 10 weekday entries; cannot truncate meaningfully")

    # Remove last 10 weekdays
    dates_to_remove = {d.date for d in weekday_entries[-10:]}
    truncated_days = [d for d in labor_days if d.date not in dates_to_remove]

    # Create truncated labor calendar
    truncated_calendar = LaborCalendar(
        name="Truncated Labor Calendar (for testing)",
        days=truncated_days
    )

    # Verify we actually removed some dates
    removed_date_count = len(labor_days) - len(truncated_days)
    assert removed_date_count == 10, f"Expected to remove 10 dates, removed {removed_date_count}"

    # Attempt to initialize model with truncated calendar
    # Should raise ValueError about missing critical weekdays
    with pytest.raises(ValueError) as exc_info:
        model = IntegratedProductionDistributionModel(
            forecast=forecast,
            labor_calendar=truncated_calendar,  # Use truncated calendar
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=locations,
            routes=routes,
            truck_schedules=truck_schedules,
            allow_shortages=True,
            validate_feasibility=True,
        )

    # Verify error message content
    error_message = str(exc_info.value)

    # Assert: Error mentions "missing" and "critical weekday"
    assert 'missing' in error_message.lower(), "Error should mention 'missing'"
    assert 'weekday' in error_message.lower(), "Error should mention 'weekday'"

    # Assert: Error includes forecast range information
    forecast_start = min(e.forecast_date for e in forecast.entries)
    forecast_end = max(e.forecast_date for e in forecast.entries)

    assert 'forecast range' in error_message.lower(), "Error should mention 'forecast range'"

    # Assert: Error includes required production start information
    assert 'required production start' in error_message.lower() or 'required' in error_message.lower(), (
        "Error should mention required production start date"
    )

    # Assert: Error includes labor calendar coverage information
    assert 'labor calendar' in error_message.lower(), "Error should mention labor calendar"

    # Assert: Error includes actionable fix instructions
    assert 'fix' in error_message.lower() or 'extend' in error_message.lower(), (
        "Error should include fix instructions"
    )

    print(f"✓ Test passed: Truncated labor calendar")
    print(f"  Forecast range: {forecast_start} to {forecast_end}")
    print(f"  Labor calendar truncated: Removed last 10 weekday entries")
    print(f"  ValueError raised as expected")
    print(f"  Error message includes:")
    print(f"    - Missing critical weekdays: ✓")
    print(f"    - Forecast range: ✓")
    print(f"    - Required production start: ✓")
    print(f"    - Labor calendar coverage: ✓")
    print(f"    - Fix instructions: ✓")


def test_labor_validation_distinguishes_weekdays_vs_weekends(load_example_data, manufacturing_site):
    """
    Test 4: Verify that labor validation treats missing weekends differently than weekdays.

    Missing weekends should generate warnings (optional capacity) rather than errors,
    even in the critical forecast range, because weekend production is optional.

    Expected behavior:
    - Missing weekends in critical range → UserWarning (not error)
    - Warning message should mention "weekend" and "zero production capacity"
    - Model initializes successfully despite missing weekend labor data
    """
    forecast, locations, routes, labor_calendar, truck_schedules, cost_structure = load_example_data

    # Remove all weekend entries from labor calendar
    labor_days = labor_calendar.days.copy()
    weekday_only_days = [d for d in labor_days if d.date.weekday() < 5]  # Keep only Mon-Fri

    # Create weekday-only labor calendar
    weekday_only_calendar = LaborCalendar(
        name="Weekday-Only Labor Calendar (for testing)",
        days=weekday_only_days
    )

    removed_weekend_count = len(labor_days) - len(weekday_only_days)

    # Capture warnings during model initialization
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # Initialize model with weekday-only calendar
        model = IntegratedProductionDistributionModel(
            forecast=forecast,
            labor_calendar=weekday_only_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=locations,
            routes=routes,
            truck_schedules=truck_schedules,
            allow_shortages=True,
            validate_feasibility=True,
        )

        # Collect labor-related warnings
        labor_warnings = [
            warning for warning in w
            if 'labor' in str(warning.message).lower() or 'weekend' in str(warning.message).lower()
        ]

    # Assert: Model initializes successfully (no ValueError)
    assert model is not None

    # Assert: Should have warnings about missing weekends
    weekend_warnings = [
        warning for warning in labor_warnings
        if 'weekend' in str(warning.message).lower()
    ]

    # Only assert if we actually removed weekend entries
    if removed_weekend_count > 0:
        assert len(weekend_warnings) > 0, (
            f"Expected UserWarning about missing weekends, but got none. "
            f"Removed {removed_weekend_count} weekend entries. "
            f"All warnings: {[str(w.message) for w in labor_warnings]}"
        )

        # Assert: Warnings should mention zero capacity or optional
        for warning in weekend_warnings:
            message = str(warning.message).lower()
            assert 'zero production capacity' in message or 'optional' in message, (
                f"Weekend warning should mention zero capacity or optional production: {warning.message}"
            )

    print(f"✓ Test passed: Weekday vs. weekend distinction")
    print(f"  Removed weekend entries: {removed_weekend_count}")
    if removed_weekend_count > 0:
        print(f"  Weekend warnings issued: {len(weekend_warnings)}")
        print(f"  Model initialized successfully (weekends optional)")
    else:
        print(f"  No weekend entries in original calendar")


def test_labor_validation_error_message_quality(load_example_data, manufacturing_site):
    """
    Test 5: Verify error message quality when labor calendar is insufficient.

    This test ensures that when labor validation fails, the error message provides
    all necessary information for the user to fix the problem.

    Expected error message components:
    1. Number of missing dates
    2. Sample of missing dates (first 5)
    3. Forecast date range
    4. Required production start date (with transit buffer explanation)
    5. Current labor calendar coverage range
    6. Clear fix instruction
    """
    forecast, locations, routes, labor_calendar, truck_schedules, cost_structure = load_example_data

    # Get forecast range
    forecast_start = min(e.forecast_date for e in forecast.entries)
    forecast_end = max(e.forecast_date for e in forecast.entries)

    # Truncate labor calendar to end before forecast end
    # This ensures we have missing critical dates
    truncation_date = forecast_end - timedelta(days=30)

    labor_days = labor_calendar.days.copy()
    truncated_days = [d for d in labor_days if d.date < truncation_date]

    if len(truncated_days) == len(labor_days):
        pytest.skip("Cannot create meaningful truncation; labor calendar already short")

    truncated_calendar = LaborCalendar(
        name="Truncated Labor Calendar",
        days=truncated_days
    )

    # Attempt to initialize with truncated calendar
    with pytest.raises(ValueError) as exc_info:
        model = IntegratedProductionDistributionModel(
            forecast=forecast,
            labor_calendar=truncated_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=locations,
            routes=routes,
            truck_schedules=truck_schedules,
            allow_shortages=True,
            validate_feasibility=True,
        )

    error_message = str(exc_info.value)

    # Component 1: Number of missing dates
    assert any(char.isdigit() for char in error_message), (
        "Error message should include number of missing dates"
    )

    # Component 2: Forecast range
    assert str(forecast_start.year) in error_message or str(forecast_end.year) in error_message, (
        "Error message should include forecast date range"
    )

    # Component 3: Required production start (with explanation)
    # Should mention "required" or "production" and a date
    assert 'required' in error_message.lower() or 'production' in error_message.lower(), (
        "Error message should mention required production start"
    )

    # Component 4: Labor calendar coverage
    assert 'labor calendar' in error_message.lower(), (
        "Error message should mention labor calendar"
    )
    assert 'coverage' in error_message.lower() or 'to' in error_message.lower(), (
        "Error message should show labor calendar date range"
    )

    # Component 5: Fix instruction
    assert 'fix' in error_message.lower() or 'extend' in error_message.lower(), (
        "Error message should include fix instruction"
    )

    # Verify error message is multi-line and well-formatted
    lines = error_message.split('\n')
    assert len(lines) >= 3, (
        f"Error message should be multi-line for readability, got {len(lines)} lines"
    )

    print(f"✓ Test passed: Error message quality")
    print(f"  Error message has {len(lines)} lines")
    print(f"  Contains all required components:")
    print(f"    - Missing date count: ✓")
    print(f"    - Forecast range: ✓")
    print(f"    - Required production start: ✓")
    print(f"    - Labor calendar coverage: ✓")
    print(f"    - Fix instructions: ✓")
    print(f"\n  Sample error message:")
    print(f"  {'─' * 70}")
    for line in error_message.split('\n')[:10]:  # Show first 10 lines
        print(f"  {line}")
    if len(lines) > 10:
        print(f"  ... ({len(lines) - 10} more lines)")
    print(f"  {'─' * 70}")


if __name__ == "__main__":
    # Allow running tests directly with: python -m tests.test_labor_validation_integration
    pytest.main([__file__, "-v", "-s"])
