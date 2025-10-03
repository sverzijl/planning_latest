"""Forecast Editor - In-app forecast adjustment tool.

This page enables quick demand adjustments without Excel re-upload.
Saves 15 min/adjustment × 3 adjustments/week = 45 min/week per planner.

Features:
- Editable data table with st.data_editor()
- Bulk edit operations (percentage, absolute, copy, scale)
- Real-time validation with warnings/errors
- Change tracking and summary
- Impact preview (before/after comparison)
- Apply changes to session state
- Integration with planning workflow
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
from datetime import datetime, date
from typing import Dict, Any, Optional, List, Tuple
import plotly.graph_objects as go
from ui import session_state
from ui.components.styling import (
    apply_custom_css,
    section_header,
    colored_metric,
    success_badge,
    warning_badge,
    error_badge,
    info_badge,
    info_box,
    status_badge,
)
from ui.components.date_filter import render_date_range_filter, apply_date_filter
from src.models.forecast import ForecastEntry, Forecast

# Page config
st.set_page_config(
    page_title="Forecast Editor",
    page_icon="📝",
    layout="wide",
)

# Apply custom CSS
apply_custom_css()

# Initialize session state
session_state.initialize_session_state()


# ========== Helper Functions ==========

def forecast_to_dataframe(forecast: Forecast) -> pd.DataFrame:
    """Convert Forecast object to DataFrame for editing.

    Args:
        forecast: Forecast object with entries

    Returns:
        DataFrame with columns: Location, Product, Date, Original Quantity
    """
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
    """Convert edited DataFrame back to Forecast object.

    Args:
        df: DataFrame with Adjusted_Quantity column
        original_forecast: Original forecast for metadata

    Returns:
        New Forecast object with updated quantities
    """
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
    """Identify and calculate changes between original and adjusted quantities.

    Args:
        df: DataFrame with Original_Quantity and Adjusted_Quantity columns

    Returns:
        DataFrame with additional Delta and Pct_Change columns
    """
    df = df.copy()
    df['Delta'] = df['Adjusted_Quantity'] - df['Original_Quantity']
    df['Pct_Change'] = ((df['Adjusted_Quantity'] - df['Original_Quantity']) /
                        df['Original_Quantity'].replace(0, 1)) * 100
    return df


def get_change_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate summary statistics for forecast changes.

    Args:
        df: DataFrame with Delta column

    Returns:
        Dictionary with change metrics
    """
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


def validate_forecast_changes(df: pd.DataFrame) -> Dict[str, Any]:
    """Validate forecast changes and return validation results.

    Args:
        df: DataFrame with Adjusted_Quantity and Delta columns

    Returns:
        Dictionary with validation results
    """
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
    filters: Dict[str, Any]
) -> pd.DataFrame:
    """Apply bulk adjustment operation to filtered forecasts.

    Args:
        df: DataFrame with forecast data
        operation: Type of adjustment ("percentage", "absolute", "scale_location", "scale_product")
        value: Adjustment value
        filters: Filter criteria (locations, products, date_range)

    Returns:
        Updated DataFrame
    """
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
        # Value is a multiplier for specific location
        if filters.get('locations'):
            for loc in filters['locations']:
                loc_mask = df['Location'] == loc
                df.loc[loc_mask, 'Adjusted_Quantity'] = df.loc[loc_mask, 'Adjusted_Quantity'] * (1 + value / 100)
    elif operation == "scale_product":
        # Value is an adjustment for specific product
        if filters.get('products'):
            for prod in filters['products']:
                prod_mask = df['Product'] == prod
                df.loc[prod_mask, 'Adjusted_Quantity'] = df.loc[prod_mask, 'Adjusted_Quantity'] + value

    # Ensure no negative quantities
    df['Adjusted_Quantity'] = df['Adjusted_Quantity'].clip(lower=0)

    return df


def calculate_impact_metrics(df: pd.DataFrame) -> Dict[str, float]:
    """Calculate estimated impact on production and logistics.

    Args:
        df: DataFrame with Original_Quantity and Adjusted_Quantity

    Returns:
        Dictionary with impact metrics
    """
    original_total = df['Original_Quantity'].sum()
    adjusted_total = df['Adjusted_Quantity'].sum()
    delta = adjusted_total - original_total

    # Rough estimates (would need actual capacity data for precise calculation)
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


def create_comparison_chart(df: pd.DataFrame) -> go.Figure:
    """Create before/after comparison chart.

    Args:
        df: DataFrame with Date, Original_Quantity, Adjusted_Quantity

    Returns:
        Plotly figure
    """
    # Aggregate by date
    daily_original = df.groupby('Date')['Original_Quantity'].sum().reset_index()
    daily_adjusted = df.groupby('Date')['Adjusted_Quantity'].sum().reset_index()

    fig = go.Figure()

    # Original forecast
    fig.add_trace(go.Scatter(
        x=daily_original['Date'],
        y=daily_original['Original_Quantity'],
        mode='lines+markers',
        name='Original Forecast',
        line=dict(color='#757575', width=2),
        marker=dict(size=6),
    ))

    # Adjusted forecast
    fig.add_trace(go.Scatter(
        x=daily_adjusted['Date'],
        y=daily_adjusted['Adjusted_Quantity'],
        mode='lines+markers',
        name='Adjusted Forecast',
        line=dict(color='#1E88E5', width=2),
        marker=dict(size=6),
    ))

    # Highlight significant changes
    merged = pd.merge(daily_original, daily_adjusted, on='Date', suffixes=('_orig', '_adj'))
    merged['delta'] = merged['Adjusted_Quantity'] - merged['Original_Quantity']
    significant = merged[merged['delta'].abs() > merged['Original_Quantity'] * 0.2]  # >20% change

    if not significant.empty:
        fig.add_trace(go.Scatter(
            x=significant['Date'],
            y=significant['Adjusted_Quantity'],
            mode='markers',
            name='Significant Change (>20%)',
            marker=dict(size=12, color='#FB8C00', symbol='diamond'),
            showlegend=True,
        ))

    fig.update_layout(
        title="Daily Demand: Original vs. Adjusted",
        xaxis_title="Date",
        yaxis_title="Units",
        hovermode='x unified',
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    return fig


def apply_forecast_changes() -> None:
    """Save adjusted forecast to session state and invalidate plans."""
    if 'adjusted_forecast_df' not in st.session_state:
        return

    # Convert DataFrame back to Forecast object
    adjusted_df = st.session_state.adjusted_forecast_df
    original_forecast = st.session_state.forecast

    new_forecast = dataframe_to_forecast(adjusted_df, original_forecast)

    # Update session state
    st.session_state.forecast = new_forecast

    # Clear planning and optimization results to force re-run
    st.session_state.planning_complete = False
    st.session_state.current_step = 0

    if 'optimization_complete' in st.session_state:
        st.session_state.optimization_complete = False

    # Clear old results
    if 'production_schedule' in st.session_state:
        st.session_state.production_schedule = None
    if 'shipments' in st.session_state:
        st.session_state.shipments = None
    if 'truck_plan' in st.session_state:
        st.session_state.truck_plan = None
    if 'cost_breakdown' in st.session_state:
        st.session_state.cost_breakdown = None
    if 'optimization_results' in st.session_state:
        del st.session_state.optimization_results

    # Mark that changes have been applied
    st.session_state.forecast_changes_applied = True


# ========== Main Page ==========

# Page title
st.markdown(section_header("Forecast Editor", level=1, icon="📝"), unsafe_allow_html=True)
st.markdown(
    """
    <div class="body-text" style="margin-bottom: 24px;">
    Quickly adjust demand forecasts without Excel re-upload. Make percentage or absolute adjustments,
    preview impact, and apply changes to trigger re-planning.
    </div>
    """,
    unsafe_allow_html=True
)

# Check if data uploaded
if not session_state.is_data_uploaded():
    st.markdown(
        info_box(
            "No forecast data loaded. Please upload data first.",
            "info",
            "ℹ️ No Data"
        ),
        unsafe_allow_html=True
    )
    if st.button("📤 Go to Upload Page", type="primary"):
        st.switch_page("pages/1_Upload_Data.py")
    st.stop()

# Get forecast data
forecast = st.session_state.forecast

if not forecast or not forecast.entries:
    st.markdown(
        info_box(
            "Forecast has no entries. Please upload valid forecast data.",
            "warning",
            "⚠️ Empty Forecast"
        ),
        unsafe_allow_html=True
    )
    st.stop()

# Initialize adjusted forecast in session state if not present
if 'adjusted_forecast_df' not in st.session_state:
    df = forecast_to_dataframe(forecast)
    df['Adjusted_Quantity'] = df['Original_Quantity'].copy()
    st.session_state.adjusted_forecast_df = df
    st.session_state.forecast_undo_stack = []

# Get current adjusted forecast
df = st.session_state.adjusted_forecast_df.copy()

# Calculate changes
df = identify_changes(df)

st.divider()

# ========== Change Summary ==========

st.markdown(section_header("Changes Summary", level=2), unsafe_allow_html=True)

summary = get_change_summary(df)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(
        colored_metric("Forecasts Modified", f"{summary['num_changed']}", "accent"),
        unsafe_allow_html=True
    )

with col2:
    delta_sign = "+" if summary['total_delta'] >= 0 else ""
    delta_color = "success" if summary['total_delta'] >= 0 else "error"
    st.markdown(
        colored_metric("Total Delta", f"{delta_sign}{summary['total_delta']:,.0f} units", delta_color),
        unsafe_allow_html=True
    )

with col3:
    pct_sign = "+" if summary['pct_change_total'] >= 0 else ""
    st.markdown(
        colored_metric("% Change", f"{pct_sign}{summary['pct_change_total']:.1f}%", "primary"),
        unsafe_allow_html=True
    )

with col4:
    if summary['num_changed'] == 0:
        st.markdown(info_badge("No Changes"), unsafe_allow_html=True)
    else:
        st.markdown(success_badge(f"+{summary['num_increased']} Up"), unsafe_allow_html=True)
        st.markdown(error_badge(f"-{summary['num_decreased']} Down"), unsafe_allow_html=True)

# Validation
validation = validate_forecast_changes(df)

if not validation['is_valid']:
    for error in validation['errors']:
        st.markdown(error_badge(error), unsafe_allow_html=True)

if validation['warnings']:
    for warning in validation['warnings']:
        st.markdown(warning_badge(warning), unsafe_allow_html=True)

if validation['is_valid'] and not validation['warnings']:
    st.markdown(success_badge("All changes valid"), unsafe_allow_html=True)

st.divider()

# ========== Bulk Edit Operations ==========

st.markdown(section_header("Bulk Edit Operations", level=2), unsafe_allow_html=True)

with st.expander("🛠️ Bulk Adjustment Tools", expanded=False):
    st.markdown("Apply bulk adjustments to multiple forecasts at once.")

    col1, col2 = st.columns([1, 2])

    with col1:
        operation = st.selectbox(
            "Operation Type",
            [
                "percentage",
                "absolute",
            ],
            format_func=lambda x: {
                "percentage": "Percentage Adjustment (%)",
                "absolute": "Absolute Adjustment (units)",
            }[x],
            key="bulk_operation"
        )

        if operation == "percentage":
            value = st.number_input(
                "Percentage Change",
                min_value=-100.0,
                max_value=500.0,
                value=10.0,
                step=5.0,
                help="Positive to increase, negative to decrease",
                key="bulk_value_pct"
            )
        else:
            value = st.number_input(
                "Unit Change",
                min_value=-100000.0,
                max_value=100000.0,
                value=1000.0,
                step=100.0,
                help="Positive to increase, negative to decrease",
                key="bulk_value_abs"
            )

    with col2:
        st.markdown("**Filters** (leave empty to apply to all)")

        # Get unique values
        all_locations = sorted(df['Location'].unique().tolist())
        all_products = sorted(df['Product'].unique().tolist())

        filter_locations = st.multiselect(
            "Locations",
            all_locations,
            key="bulk_filter_locations"
        )

        filter_products = st.multiselect(
            "Products",
            all_products,
            key="bulk_filter_products"
        )

        col_date1, col_date2 = st.columns(2)
        with col_date1:
            filter_date_start = st.date_input(
                "Start Date",
                value=None,
                key="bulk_filter_date_start"
            )
        with col_date2:
            filter_date_end = st.date_input(
                "End Date",
                value=None,
                key="bulk_filter_date_end"
            )

    # Preview impact
    filters = {
        'locations': filter_locations if filter_locations else None,
        'products': filter_products if filter_products else None,
        'date_start': pd.Timestamp(filter_date_start) if filter_date_start else None,
        'date_end': pd.Timestamp(filter_date_end) if filter_date_end else None,
    }

    preview_df = apply_bulk_adjustment(df, operation, value, filters)
    preview_df = identify_changes(preview_df)
    preview_summary = get_change_summary(preview_df)

    st.markdown("**Preview Impact:**")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Rows Affected", preview_summary['num_changed'])
    with col2:
        st.metric("Total Delta", f"{preview_summary['total_delta']:,.0f} units")
    with col3:
        st.metric("% Change", f"{preview_summary['pct_change_total']:.1f}%")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Apply Bulk Adjustment", type="primary", use_container_width=True):
            # Save to undo stack
            st.session_state.forecast_undo_stack.append(st.session_state.adjusted_forecast_df.copy())
            # Apply adjustment
            st.session_state.adjusted_forecast_df = preview_df[['Location', 'Product', 'Date', 'Original_Quantity', 'Adjusted_Quantity']]
            st.rerun()

    with col2:
        if st.button("Cancel", use_container_width=True):
            pass

st.divider()

# ========== Editable Forecast Table ==========

st.markdown(section_header("Forecast Data", level=2), unsafe_allow_html=True)

# Filtering controls
with st.expander("🔍 Filters", expanded=False):
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        filter_locations = st.multiselect(
            "Locations",
            sorted(df['Location'].unique().tolist()),
            key="table_filter_locations"
        )

    with col2:
        filter_products = st.multiselect(
            "Products",
            sorted(df['Product'].unique().tolist()),
            key="table_filter_products"
        )

    with col3:
        show_only_changed = st.checkbox("Show only changed", value=False, key="show_only_changed")

    with col4:
        sort_by = st.selectbox(
            "Sort by",
            ["Date", "Location", "Product", "Delta"],
            key="sort_by"
        )

# Apply filters
filtered_df = df.copy()

if filter_locations:
    filtered_df = filtered_df[filtered_df['Location'].isin(filter_locations)]

if filter_products:
    filtered_df = filtered_df[filtered_df['Product'].isin(filter_products)]

if show_only_changed:
    filtered_df = filtered_df[filtered_df['Delta'] != 0]

# Sort
if sort_by:
    ascending = sort_by != "Delta"  # Show largest deltas first
    filtered_df = filtered_df.sort_values(by=sort_by, ascending=ascending)

st.caption(f"Showing {len(filtered_df):,} of {len(df):,} forecasts")

# Prepare display DataFrame with color coding
display_df = filtered_df.copy()
display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d')

# Editable table
st.markdown("**Edit Adjusted Quantity values directly in the table:**")

edited_df = st.data_editor(
    display_df[['Location', 'Product', 'Date', 'Original_Quantity', 'Adjusted_Quantity', 'Delta', 'Pct_Change']],
    column_config={
        "Location": st.column_config.TextColumn("Location", width="small"),
        "Product": st.column_config.TextColumn("Product", width="small"),
        "Date": st.column_config.TextColumn("Date", width="small"),
        "Original_Quantity": st.column_config.NumberColumn(
            "Original Qty",
            format="%.0f",
            disabled=True,
            width="small"
        ),
        "Adjusted_Quantity": st.column_config.NumberColumn(
            "Adjusted Qty",
            format="%.0f",
            min_value=0,
            width="small"
        ),
        "Delta": st.column_config.NumberColumn(
            "Delta",
            format="%.0f",
            disabled=True,
            width="small"
        ),
        "Pct_Change": st.column_config.NumberColumn(
            "% Change",
            format="%.1f%%",
            disabled=True,
            width="small"
        ),
    },
    hide_index=True,
    use_container_width=True,
    key="forecast_editor",
    height=400,
)

# Update session state if edits were made
if not edited_df.equals(display_df[['Location', 'Product', 'Date', 'Original_Quantity', 'Adjusted_Quantity', 'Delta', 'Pct_Change']]):
    # Merge changes back to full DataFrame
    edited_df['Date'] = pd.to_datetime(edited_df['Date'])

    # Update the full adjusted forecast
    updated_df = df.copy()
    for idx, row in edited_df.iterrows():
        mask = (
            (updated_df['Location'] == row['Location']) &
            (updated_df['Product'] == row['Product']) &
            (updated_df['Date'] == row['Date'])
        )
        updated_df.loc[mask, 'Adjusted_Quantity'] = row['Adjusted_Quantity']

    st.session_state.adjusted_forecast_df = updated_df[['Location', 'Product', 'Date', 'Original_Quantity', 'Adjusted_Quantity']]

st.divider()

# ========== Impact Preview ==========

st.markdown(section_header("Impact Preview", level=2), unsafe_allow_html=True)

# Calculate impact metrics
impact = calculate_impact_metrics(df)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(
        colored_metric("Original Demand", f"{impact['original_demand']:,.0f} units", "primary"),
        unsafe_allow_html=True
    )

with col2:
    st.markdown(
        colored_metric("Adjusted Demand", f"{impact['adjusted_demand']:,.0f} units", "accent"),
        unsafe_allow_html=True
    )

with col3:
    delta_sign = "+" if impact['demand_delta'] >= 0 else ""
    st.markdown(
        colored_metric(
            "Labor Hours Impact",
            f"{delta_sign}{impact['labor_hours_delta']:.1f} hours",
            "secondary"
        ),
        unsafe_allow_html=True
    )

with col4:
    delta_sign = "+" if impact['demand_delta'] >= 0 else ""
    st.markdown(
        colored_metric(
            "Truck Capacity Impact",
            f"{delta_sign}{impact['trucks_delta']:.2f} trucks",
            "warning"
        ),
        unsafe_allow_html=True
    )

# Comparison chart
if summary['num_changed'] > 0:
    st.markdown("**Daily Demand Comparison:**")
    fig = create_comparison_chart(df)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No changes to preview. Make adjustments to see impact.")

st.divider()

# ========== Actions ==========

st.markdown(section_header("Actions", level=2), unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("🔄 Reset All Changes", use_container_width=True, type="secondary"):
        if summary['num_changed'] > 0:
            # Confirm reset
            if 'confirm_reset' not in st.session_state:
                st.session_state.confirm_reset = True
                st.rerun()
        else:
            st.info("No changes to reset")

with col2:
    if st.button("↶ Undo Last Change", use_container_width=True, disabled=len(st.session_state.forecast_undo_stack) == 0):
        if st.session_state.forecast_undo_stack:
            st.session_state.adjusted_forecast_df = st.session_state.forecast_undo_stack.pop()
            st.rerun()

with col3:
    # Export adjusted forecast
    if st.button("💾 Export to Excel", use_container_width=True):
        # Convert to Excel-friendly format
        export_df = df[['Location', 'Product', 'Date', 'Original_Quantity', 'Adjusted_Quantity', 'Delta', 'Pct_Change']].copy()
        export_df['Date'] = export_df['Date'].dt.strftime('%Y-%m-%d')

        # Use download button
        csv = export_df.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"adjusted_forecast_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )

with col4:
    apply_disabled = summary['num_changed'] == 0 or not validation['is_valid']

    if st.button("✅ Apply Changes", use_container_width=True, type="primary", disabled=apply_disabled):
        if 'confirm_apply' not in st.session_state:
            st.session_state.confirm_apply = True
            st.rerun()

# Confirmation dialogs
if st.session_state.get('confirm_reset', False):
    st.warning("⚠️ This will reset all changes. Are you sure?")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Yes, Reset All", type="primary"):
            # Reset to original
            df = forecast_to_dataframe(forecast)
            df['Adjusted_Quantity'] = df['Original_Quantity'].copy()
            st.session_state.adjusted_forecast_df = df
            st.session_state.forecast_undo_stack = []
            st.session_state.confirm_reset = False
            st.rerun()
    with col2:
        if st.button("Cancel"):
            st.session_state.confirm_reset = False
            st.rerun()

if st.session_state.get('confirm_apply', False):
    st.success("✅ This will update the forecast and invalidate current planning results. Continue?")

    st.markdown(
        info_box(
            f"""
            <strong>Changes to be applied:</strong><br>
            • {summary['num_changed']} forecasts modified<br>
            • Total demand change: {summary['total_delta']:+,.0f} units ({summary['pct_change_total']:+.1f}%)<br>
            • {summary['locations_affected']} locations affected<br>
            • {summary['products_affected']} products affected<br>
            • {summary['dates_affected']} dates affected
            """,
            "info",
            "ℹ️ Summary"
        ),
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Yes, Apply and Re-Plan", type="primary"):
            apply_forecast_changes()
            st.session_state.confirm_apply = False
            st.success("✅ Forecast updated successfully! Planning results have been cleared.")
            st.info("Navigate to Planning Workflow or Optimization to generate new plans.")
            st.rerun()
    with col2:
        if st.button("Cancel"):
            st.session_state.confirm_apply = False
            st.rerun()

st.divider()

# ========== Navigation ==========

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("← Back to Data Summary", use_container_width=True):
        st.switch_page("pages/2_Data_Summary.py")

with col2:
    if st.button("🚀 Go to Planning", use_container_width=True, type="secondary"):
        st.switch_page("pages/3_Planning_Workflow.py")

with col3:
    if st.button("⚡ Go to Optimization", use_container_width=True, type="secondary"):
        st.switch_page("pages/10_Optimization.py")
