"""Unit tests for forecast editor helper functions.

Tests cover:
- Forecast to DataFrame conversion
- DataFrame to Forecast conversion
- Change identification
- Validation logic
- Bulk adjustment operations
- Impact metric calculation
"""

import pytest
import pandas as pd
from datetime import date, datetime
from src.models.forecast import Forecast, ForecastEntry


# ========== Helper Functions (copied from page for testing) ==========

def forecast_to_dataframe(forecast: Forecast) -> pd.DataFrame:
    """Convert Forecast object to DataFrame for editing."""
    if not forecast or not forecast.entries:
        return pd.DataFrame(columns=['Location', 'Product', 'Date', 'Original_Quantity'])

    data = []
    for entry in forecast.entries:
        data.append({
            'Location': entry.location_id,
            'Product': entry.product_id,
            'Date': entry.forecast_date,
            'Original_Quantity': entry.quantity,
        })

    df = pd.DataFrame(data)
    df['Date'] = pd.to_datetime(df['Date'])
    return df


def dataframe_to_forecast(df: pd.DataFrame, original_forecast: Forecast) -> Forecast:
    """Convert edited DataFrame back to Forecast object."""
    entries = []
    for _, row in df.iterrows():
        entry = ForecastEntry(
            location_id=str(row['Location']),
            product_id=str(row['Product']),
            forecast_date=row['Date'].date() if isinstance(row['Date'], pd.Timestamp) else row['Date'],
            quantity=float(row['Adjusted_Quantity']),
        )
        entries.append(entry)

    return Forecast(
        name=f"{original_forecast.name} (Edited)",
        entries=entries,
        creation_date=date.today()
    )


def identify_changes(df: pd.DataFrame) -> pd.DataFrame:
    """Identify and calculate changes between original and adjusted quantities."""
    df = df.copy()
    df['Delta'] = df['Adjusted_Quantity'] - df['Original_Quantity']
    df['Pct_Change'] = ((df['Adjusted_Quantity'] - df['Original_Quantity']) /
                        df['Original_Quantity'].replace(0, 1)) * 100
    return df


def get_change_summary(df: pd.DataFrame) -> dict:
    """Calculate summary statistics for forecast changes."""
    changes = df[df['Delta'] != 0]

    summary = {
        'num_changed': len(changes),
        'num_increased': len(changes[changes['Delta'] > 0]),
        'num_decreased': len(changes[changes['Delta'] < 0]),
        'total_delta': df['Delta'].sum(),
        'total_original': df['Original_Quantity'].sum(),
        'total_adjusted': df['Adjusted_Quantity'].sum(),
        'pct_change_total': ((df['Adjusted_Quantity'].sum() - df['Original_Quantity'].sum()) /
                            df['Original_Quantity'].sum() * 100) if df['Original_Quantity'].sum() > 0 else 0,
        'locations_affected': changes['Location'].nunique() if len(changes) > 0 else 0,
        'products_affected': changes['Product'].nunique() if len(changes) > 0 else 0,
        'dates_affected': changes['Date'].nunique() if len(changes) > 0 else 0,
    }

    return summary


def validate_forecast_changes(df: pd.DataFrame) -> dict:
    """Validate forecast changes and return validation results."""
    validation = {
        'is_valid': True,
        'errors': [],
        'warnings': [],
    }

    # Check for negative quantities
    negative_mask = df['Adjusted_Quantity'] < 0
    if negative_mask.any():
        num_negative = negative_mask.sum()
        validation['is_valid'] = False
        validation['errors'].append(f"{num_negative} forecast(s) have negative quantities")

    # Check for extreme changes (>100% or >10,000 units)
    extreme_pct_mask = df['Pct_Change'].abs() > 100
    extreme_abs_mask = df['Delta'].abs() > 10000
    extreme_mask = extreme_pct_mask | extreme_abs_mask

    if extreme_mask.any():
        num_extreme = extreme_mask.sum()
        validation['warnings'].append(
            f"{num_extreme} forecast(s) have extreme changes (>100% or >10,000 units)"
        )

    # Check for very large total change
    total_pct_change = abs((df['Adjusted_Quantity'].sum() - df['Original_Quantity'].sum()) /
                          df['Original_Quantity'].sum() * 100) if df['Original_Quantity'].sum() > 0 else 0

    if total_pct_change > 50:
        validation['warnings'].append(
            f"Total demand changed by {total_pct_change:.1f}% - please verify capacity"
        )

    return validation


def apply_bulk_adjustment(
    df: pd.DataFrame,
    operation: str,
    value: float,
    filters: dict
) -> pd.DataFrame:
    """Apply bulk adjustment operation to filtered forecasts."""
    df = df.copy()

    # Apply filters to determine which rows to adjust
    mask = pd.Series([True] * len(df), index=df.index)

    if filters.get('locations'):
        mask &= df['Location'].isin(filters['locations'])

    if filters.get('products'):
        mask &= df['Product'].isin(filters['products'])

    if filters.get('date_start') and filters.get('date_end'):
        mask &= (df['Date'] >= filters['date_start']) & (df['Date'] <= filters['date_end'])

    # Apply adjustment
    if operation == "percentage":
        df.loc[mask, 'Adjusted_Quantity'] = df.loc[mask, 'Adjusted_Quantity'] * (1 + value / 100)
    elif operation == "absolute":
        df.loc[mask, 'Adjusted_Quantity'] = df.loc[mask, 'Adjusted_Quantity'] + value
    elif operation == "scale_location":
        if filters.get('locations'):
            for loc in filters['locations']:
                loc_mask = df['Location'] == loc
                df.loc[loc_mask, 'Adjusted_Quantity'] = df.loc[loc_mask, 'Adjusted_Quantity'] * (1 + value / 100)
    elif operation == "scale_product":
        if filters.get('products'):
            for prod in filters['products']:
                prod_mask = df['Product'] == prod
                df.loc[prod_mask, 'Adjusted_Quantity'] = df.loc[prod_mask, 'Adjusted_Quantity'] + value

    # Ensure no negative quantities
    df['Adjusted_Quantity'] = df['Adjusted_Quantity'].clip(lower=0)

    return df


def calculate_impact_metrics(df: pd.DataFrame) -> dict:
    """Calculate estimated impact on production and logistics."""
    original_total = df['Original_Quantity'].sum()
    adjusted_total = df['Adjusted_Quantity'].sum()
    delta = adjusted_total - original_total

    production_rate = 1400  # units/hour
    truck_capacity = 14080  # units/truck

    impact = {
        'original_demand': original_total,
        'adjusted_demand': adjusted_total,
        'demand_delta': delta,
        'demand_pct_change': (delta / original_total * 100) if original_total > 0 else 0,
        'labor_hours_delta': abs(delta) / production_rate,
        'trucks_delta': abs(delta) / truck_capacity,
    }

    return impact


# ========== Test Fixtures ==========

@pytest.fixture
def sample_forecast():
    """Create a sample forecast for testing."""
    entries = [
        ForecastEntry(
            location_id="6104",
            product_id="ProductA",
            forecast_date=date(2025, 1, 1),
            quantity=1000.0
        ),
        ForecastEntry(
            location_id="6104",
            product_id="ProductB",
            forecast_date=date(2025, 1, 1),
            quantity=2000.0
        ),
        ForecastEntry(
            location_id="6125",
            product_id="ProductA",
            forecast_date=date(2025, 1, 2),
            quantity=1500.0
        ),
        ForecastEntry(
            location_id="6125",
            product_id="ProductB",
            forecast_date=date(2025, 1, 2),
            quantity=2500.0
        ),
    ]

    return Forecast(name="Test Forecast", entries=entries)


@pytest.fixture
def sample_dataframe():
    """Create a sample DataFrame for testing."""
    data = {
        'Location': ['6104', '6104', '6125', '6125'],
        'Product': ['ProductA', 'ProductB', 'ProductA', 'ProductB'],
        'Date': pd.to_datetime(['2025-01-01', '2025-01-01', '2025-01-02', '2025-01-02']),
        'Original_Quantity': [1000.0, 2000.0, 1500.0, 2500.0],
        'Adjusted_Quantity': [1000.0, 2000.0, 1500.0, 2500.0],
    }
    return pd.DataFrame(data)


# ========== Tests ==========

class TestForecastConversion:
    """Tests for forecast <-> DataFrame conversion."""

    def test_forecast_to_dataframe_basic(self, sample_forecast):
        """Test basic conversion from Forecast to DataFrame."""
        df = forecast_to_dataframe(sample_forecast)

        assert len(df) == 4
        assert list(df.columns) == ['Location', 'Product', 'Date', 'Original_Quantity']
        assert df['Original_Quantity'].sum() == 7000.0

    def test_forecast_to_dataframe_empty(self):
        """Test conversion with empty forecast."""
        empty_forecast = Forecast(name="Empty", entries=[])
        df = forecast_to_dataframe(empty_forecast)

        assert len(df) == 0
        assert list(df.columns) == ['Location', 'Product', 'Date', 'Original_Quantity']

    def test_dataframe_to_forecast_basic(self, sample_dataframe, sample_forecast):
        """Test basic conversion from DataFrame to Forecast."""
        forecast = dataframe_to_forecast(sample_dataframe, sample_forecast)

        assert len(forecast.entries) == 4
        assert forecast.name == "Test Forecast (Edited)"
        assert sum(e.quantity for e in forecast.entries) == 7000.0

    def test_forecast_roundtrip(self, sample_forecast):
        """Test roundtrip conversion Forecast -> DataFrame -> Forecast."""
        # Convert to DataFrame
        df = forecast_to_dataframe(sample_forecast)
        df['Adjusted_Quantity'] = df['Original_Quantity'] * 1.1  # 10% increase

        # Convert back to Forecast
        new_forecast = dataframe_to_forecast(df, sample_forecast)

        assert len(new_forecast.entries) == len(sample_forecast.entries)
        assert sum(e.quantity for e in new_forecast.entries) == pytest.approx(7700.0)


class TestChangeIdentification:
    """Tests for change identification and summary."""

    def test_identify_changes_no_change(self, sample_dataframe):
        """Test change identification when no changes made."""
        df = identify_changes(sample_dataframe)

        assert 'Delta' in df.columns
        assert 'Pct_Change' in df.columns
        assert df['Delta'].sum() == 0
        assert all(df['Pct_Change'] == 0)

    def test_identify_changes_with_increase(self, sample_dataframe):
        """Test change identification with quantity increases."""
        sample_dataframe['Adjusted_Quantity'] = sample_dataframe['Original_Quantity'] * 1.2  # 20% increase
        df = identify_changes(sample_dataframe)

        assert df['Delta'].sum() == pytest.approx(1400.0)  # 20% of 7000
        assert all(abs(df['Pct_Change'] - 20.0) < 0.01)  # All approximately 20%

    def test_identify_changes_with_decrease(self, sample_dataframe):
        """Test change identification with quantity decreases."""
        sample_dataframe.loc[0, 'Adjusted_Quantity'] = 500.0  # Decrease from 1000 to 500
        df = identify_changes(sample_dataframe)

        assert df.loc[0, 'Delta'] == -500.0
        assert df.loc[0, 'Pct_Change'] == pytest.approx(-50.0)

    def test_get_change_summary_no_changes(self, sample_dataframe):
        """Test change summary with no changes."""
        df = identify_changes(sample_dataframe)
        summary = get_change_summary(df)

        assert summary['num_changed'] == 0
        assert summary['num_increased'] == 0
        assert summary['num_decreased'] == 0
        assert summary['total_delta'] == 0

    def test_get_change_summary_with_changes(self, sample_dataframe):
        """Test change summary with mixed changes."""
        sample_dataframe.loc[0, 'Adjusted_Quantity'] = 1500.0  # +500
        sample_dataframe.loc[1, 'Adjusted_Quantity'] = 1500.0  # -500
        df = identify_changes(sample_dataframe)
        summary = get_change_summary(df)

        assert summary['num_changed'] == 2
        assert summary['num_increased'] == 1
        assert summary['num_decreased'] == 1
        assert summary['total_delta'] == 0  # Net zero change
        assert summary['locations_affected'] == 1
        assert summary['products_affected'] == 2


class TestValidation:
    """Tests for forecast change validation."""

    def test_validate_no_changes(self, sample_dataframe):
        """Test validation with no changes."""
        df = identify_changes(sample_dataframe)
        validation = validate_forecast_changes(df)

        assert validation['is_valid'] is True
        assert len(validation['errors']) == 0
        assert len(validation['warnings']) == 0

    def test_validate_negative_quantities(self, sample_dataframe):
        """Test validation rejects negative quantities."""
        sample_dataframe.loc[0, 'Adjusted_Quantity'] = -100.0
        df = identify_changes(sample_dataframe)
        validation = validate_forecast_changes(df)

        assert validation['is_valid'] is False
        assert len(validation['errors']) == 1
        assert "negative quantities" in validation['errors'][0]

    def test_validate_extreme_percentage_change(self, sample_dataframe):
        """Test validation warns on extreme percentage changes."""
        sample_dataframe.loc[0, 'Adjusted_Quantity'] = 3000.0  # 200% increase
        df = identify_changes(sample_dataframe)
        validation = validate_forecast_changes(df)

        assert validation['is_valid'] is True  # Warning, not error
        assert len(validation['warnings']) == 1
        assert "extreme changes" in validation['warnings'][0]

    def test_validate_extreme_absolute_change(self, sample_dataframe):
        """Test validation warns on extreme absolute changes."""
        sample_dataframe.loc[0, 'Adjusted_Quantity'] = 15000.0  # +14000 units
        df = identify_changes(sample_dataframe)
        validation = validate_forecast_changes(df)

        assert validation['is_valid'] is True  # Warning, not error
        assert len(validation['warnings']) > 0

    def test_validate_large_total_change(self, sample_dataframe):
        """Test validation warns on large total demand change."""
        sample_dataframe['Adjusted_Quantity'] = sample_dataframe['Original_Quantity'] * 2.0  # 100% increase
        df = identify_changes(sample_dataframe)
        validation = validate_forecast_changes(df)

        assert validation['is_valid'] is True
        assert any("capacity" in w for w in validation['warnings'])


class TestBulkAdjustment:
    """Tests for bulk adjustment operations."""

    def test_bulk_percentage_adjustment_all(self, sample_dataframe):
        """Test percentage adjustment to all forecasts."""
        filters = {}
        df = apply_bulk_adjustment(sample_dataframe, "percentage", 10.0, filters)

        assert df['Adjusted_Quantity'].sum() == pytest.approx(7700.0)  # 10% increase

    def test_bulk_absolute_adjustment_all(self, sample_dataframe):
        """Test absolute adjustment to all forecasts."""
        filters = {}
        df = apply_bulk_adjustment(sample_dataframe, "absolute", 100.0, filters)

        assert df['Adjusted_Quantity'].sum() == pytest.approx(7400.0)  # +100 per row

    def test_bulk_adjustment_filtered_by_location(self, sample_dataframe):
        """Test bulk adjustment filtered by location."""
        filters = {'locations': ['6104']}
        df = apply_bulk_adjustment(sample_dataframe, "absolute", 500.0, filters)

        # Only 2 rows at 6104 should be adjusted
        assert df[df['Location'] == '6104']['Adjusted_Quantity'].sum() == pytest.approx(4000.0)
        assert df[df['Location'] == '6125']['Adjusted_Quantity'].sum() == pytest.approx(4000.0)

    def test_bulk_adjustment_filtered_by_product(self, sample_dataframe):
        """Test bulk adjustment filtered by product."""
        filters = {'products': ['ProductA']}
        df = apply_bulk_adjustment(sample_dataframe, "percentage", 20.0, filters)

        # Only ProductA rows should increase by 20%
        product_a_total = df[df['Product'] == 'ProductA']['Adjusted_Quantity'].sum()
        assert product_a_total == pytest.approx(3000.0)  # (1000 + 1500) * 1.2

    def test_bulk_adjustment_filtered_by_date(self, sample_dataframe):
        """Test bulk adjustment filtered by date range."""
        filters = {
            'date_start': pd.Timestamp('2025-01-01'),
            'date_end': pd.Timestamp('2025-01-01')
        }
        df = apply_bulk_adjustment(sample_dataframe, "absolute", 1000.0, filters)

        # Only 2025-01-01 rows should be adjusted
        jan1_total = df[df['Date'] == pd.Timestamp('2025-01-01')]['Adjusted_Quantity'].sum()
        assert jan1_total == pytest.approx(5000.0)  # 1000 + 2000 + 1000 + 1000

    def test_bulk_adjustment_prevents_negative(self, sample_dataframe):
        """Test bulk adjustment prevents negative quantities."""
        filters = {}
        df = apply_bulk_adjustment(sample_dataframe, "absolute", -2000.0, filters)

        # All quantities should be clipped to 0
        assert all(df['Adjusted_Quantity'] >= 0)
        assert df.loc[0, 'Adjusted_Quantity'] == 0  # 1000 - 2000 = 0 (clipped)

    def test_bulk_adjustment_combined_filters(self, sample_dataframe):
        """Test bulk adjustment with multiple filters."""
        filters = {
            'locations': ['6104'],
            'products': ['ProductA']
        }
        df = apply_bulk_adjustment(sample_dataframe, "percentage", 50.0, filters)

        # Only 6104 + ProductA should increase (1 row)
        assert df.loc[0, 'Adjusted_Quantity'] == pytest.approx(1500.0)
        assert df.loc[1, 'Adjusted_Quantity'] == 2000.0  # Unchanged
        assert df.loc[2, 'Adjusted_Quantity'] == 1500.0  # Unchanged


class TestImpactMetrics:
    """Tests for impact metric calculation."""

    def test_calculate_impact_no_change(self, sample_dataframe):
        """Test impact calculation with no changes."""
        df = identify_changes(sample_dataframe)
        impact = calculate_impact_metrics(df)

        assert impact['original_demand'] == 7000.0
        assert impact['adjusted_demand'] == 7000.0
        assert impact['demand_delta'] == 0
        assert impact['demand_pct_change'] == 0
        assert impact['labor_hours_delta'] == 0
        assert impact['trucks_delta'] == 0

    def test_calculate_impact_with_increase(self, sample_dataframe):
        """Test impact calculation with demand increase."""
        sample_dataframe['Adjusted_Quantity'] = sample_dataframe['Original_Quantity'] * 1.2  # 20% increase
        df = identify_changes(sample_dataframe)
        impact = calculate_impact_metrics(df)

        assert impact['original_demand'] == 7000.0
        assert impact['adjusted_demand'] == pytest.approx(8400.0)
        assert impact['demand_delta'] == pytest.approx(1400.0)
        assert impact['demand_pct_change'] == pytest.approx(20.0)
        assert impact['labor_hours_delta'] == pytest.approx(1.0)  # 1400 / 1400
        assert impact['trucks_delta'] == pytest.approx(0.0994, rel=0.01)  # 1400 / 14080

    def test_calculate_impact_with_decrease(self, sample_dataframe):
        """Test impact calculation with demand decrease."""
        sample_dataframe['Adjusted_Quantity'] = sample_dataframe['Original_Quantity'] * 0.8  # 20% decrease
        df = identify_changes(sample_dataframe)
        impact = calculate_impact_metrics(df)

        assert impact['adjusted_demand'] == pytest.approx(5600.0)
        assert impact['demand_delta'] == pytest.approx(-1400.0)
        assert impact['demand_pct_change'] == pytest.approx(-20.0)
        assert impact['labor_hours_delta'] == pytest.approx(1.0)  # abs(-1400) / 1400

    def test_calculate_impact_large_change(self, sample_dataframe):
        """Test impact calculation with large demand change."""
        sample_dataframe['Adjusted_Quantity'] = sample_dataframe['Original_Quantity'] * 2.0  # Double
        df = identify_changes(sample_dataframe)
        impact = calculate_impact_metrics(df)

        assert impact['demand_delta'] == pytest.approx(7000.0)
        assert impact['labor_hours_delta'] == pytest.approx(5.0)  # 7000 / 1400
        assert impact['trucks_delta'] == pytest.approx(0.497, rel=0.01)  # 7000 / 14080


# ========== Integration Tests ==========

class TestEndToEndWorkflow:
    """Integration tests for complete editing workflow."""

    def test_complete_editing_workflow(self, sample_forecast):
        """Test complete workflow: Forecast -> Edit -> Validate -> Convert back."""
        # 1. Convert to DataFrame
        df = forecast_to_dataframe(sample_forecast)
        df['Adjusted_Quantity'] = df['Original_Quantity'].copy()

        # 2. Make edits
        df.loc[0, 'Adjusted_Quantity'] = 1200.0  # +200
        df.loc[1, 'Adjusted_Quantity'] = 1800.0  # -200

        # 3. Identify changes
        df = identify_changes(df)
        summary = get_change_summary(df)

        assert summary['num_changed'] == 2
        assert summary['total_delta'] == 0  # Net zero

        # 4. Validate
        validation = validate_forecast_changes(df)
        assert validation['is_valid'] is True

        # 5. Calculate impact
        impact = calculate_impact_metrics(df)
        assert impact['demand_delta'] == 0

        # 6. Convert back to Forecast
        new_forecast = dataframe_to_forecast(df, sample_forecast)
        assert len(new_forecast.entries) == 4
        assert sum(e.quantity for e in new_forecast.entries) == 7000.0

    def test_bulk_edit_workflow(self, sample_forecast):
        """Test workflow with bulk edits."""
        # 1. Convert and prepare
        df = forecast_to_dataframe(sample_forecast)
        df['Adjusted_Quantity'] = df['Original_Quantity'].copy()

        # 2. Apply bulk adjustment
        filters = {'locations': ['6104']}
        df = apply_bulk_adjustment(df, "percentage", 50.0, filters)

        # 3. Identify and validate
        df = identify_changes(df)
        validation = validate_forecast_changes(df)

        assert validation['is_valid'] is True
        assert df['Adjusted_Quantity'].sum() == pytest.approx(8500.0)  # 6104 increased by 50%

        # 4. Convert back
        new_forecast = dataframe_to_forecast(df, sample_forecast)
        assert sum(e.quantity for e in new_forecast.entries) == pytest.approx(8500.0)
