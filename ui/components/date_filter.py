"""Date Range Filter Component for Streamlit Apps

This component provides a reusable date range filter for analysis pages.

Basic Usage:
    from ui.components.date_filter import render_date_range_filter, apply_date_filter

    # Render filter
    start_date, end_date = render_date_range_filter(
        min_date=df['date'].min(),
        max_date=df['date'].max(),
        default_range="2weeks"
    )

    # Apply to DataFrame
    filtered_df = apply_date_filter(df, 'date', start_date, end_date)

Features:
    - Quick select buttons (Week, 2 Weeks, Month, All)
    - Custom date range selection
    - URL parameter sync for shareable links
    - Session state persistence
    - Visual feedback on current selection
"""

from datetime import datetime, timedelta, date
from typing import Tuple, Optional, Literal
import pandas as pd
import streamlit as st


RangeType = Literal["week", "2weeks", "month", "all", "custom"]


def get_quick_range_dates(
    range_type: str,
    min_date: datetime,
    max_date: datetime,
    reference_date: Optional[datetime] = None
) -> Tuple[datetime, datetime]:
    """Calculate date range for quick select option.

    Args:
        range_type: "week", "2weeks", "month", "all", "custom"
        min_date: Minimum available date
        max_date: Maximum available date
        reference_date: Starting point (default: today)

    Returns:
        (start_date, end_date) tuple
    """
    # Convert date objects to datetime if needed
    if isinstance(min_date, date) and not isinstance(min_date, datetime):
        min_date = datetime.combine(min_date, datetime.min.time())
    if isinstance(max_date, date) and not isinstance(max_date, datetime):
        max_date = datetime.combine(max_date, datetime.min.time())

    if reference_date is None:
        reference_date = datetime.now()
    elif isinstance(reference_date, date) and not isinstance(reference_date, datetime):
        reference_date = datetime.combine(reference_date, datetime.min.time())

    # Determine starting point
    # If today is within planning horizon, use today
    # Otherwise, use min_date
    if min_date <= reference_date <= max_date:
        start_ref = reference_date
    else:
        start_ref = min_date

    if range_type == "all":
        return min_date, max_date
    elif range_type == "week":
        # Next 7 days from reference
        end = start_ref + timedelta(days=6)
        return start_ref, min(end, max_date)
    elif range_type == "2weeks":
        # Next 14 days from reference
        end = start_ref + timedelta(days=13)
        return start_ref, min(end, max_date)
    elif range_type == "month":
        # Next 30 days from reference
        end = start_ref + timedelta(days=29)
        return start_ref, min(end, max_date)
    else:
        # Custom or unknown - return full range
        return min_date, max_date


def apply_date_filter(
    df: pd.DataFrame,
    date_column: str,
    start_date: datetime,
    end_date: datetime
) -> pd.DataFrame:
    """Filter DataFrame by date range.

    Args:
        df: DataFrame to filter
        date_column: Name of date column
        start_date: Start of range (inclusive)
        end_date: End of range (inclusive)

    Returns:
        Filtered DataFrame
    """
    if df.empty or date_column not in df.columns:
        return df

    # Convert date objects to datetime for comparison
    if isinstance(start_date, date) and not isinstance(start_date, datetime):
        start_date = datetime.combine(start_date, datetime.min.time())
    if isinstance(end_date, date) and not isinstance(end_date, datetime):
        end_date = datetime.combine(end_date, datetime.max.time())

    # Ensure the date column is datetime type
    if not pd.api.types.is_datetime64_any_dtype(df[date_column]):
        df_copy = df.copy()
        df_copy[date_column] = pd.to_datetime(df_copy[date_column])
    else:
        df_copy = df

    # Filter
    mask = (df_copy[date_column] >= start_date) & (df_copy[date_column] <= end_date)
    return df_copy[mask].copy()


def sync_url_params(
    start_date: datetime,
    end_date: datetime,
    param_prefix: str = "date"
) -> None:
    """Sync date range to URL query parameters.

    Args:
        start_date: Filter start date
        end_date: Filter end date
        param_prefix: URL parameter prefix
    """
    try:
        # Format dates as strings
        start_str = start_date.strftime("%Y-%m-%d") if isinstance(start_date, datetime) else str(start_date)
        end_str = end_date.strftime("%Y-%m-%d") if isinstance(end_date, datetime) else str(end_date)

        # Set query params
        st.query_params[f"{param_prefix}_start"] = start_str
        st.query_params[f"{param_prefix}_end"] = end_str
    except Exception:
        # Silently fail if query params not available
        pass


def load_url_params(
    param_prefix: str = "date"
) -> Optional[Tuple[str, str]]:
    """Load date range from URL query parameters.

    Args:
        param_prefix: URL parameter prefix

    Returns:
        (start_date_str, end_date_str) tuple or None if not available
    """
    try:
        start_str = st.query_params.get(f"{param_prefix}_start")
        end_str = st.query_params.get(f"{param_prefix}_end")

        if start_str and end_str:
            return start_str, end_str
        return None
    except Exception:
        return None


def render_date_range_filter(
    min_date: datetime,
    max_date: datetime,
    default_range: str = "all",
    key_prefix: str = "date_filter",
    include_url_params: bool = True
) -> Tuple[datetime, datetime]:
    """Render date range filter UI component.

    Args:
        min_date: Minimum selectable date (from data)
        max_date: Maximum selectable date (from data)
        default_range: Default selection - "all", "week", "2weeks", "month", "custom"
        key_prefix: Unique prefix for session state keys
        include_url_params: Whether to sync with URL query parameters

    Returns:
        (start_date, end_date) tuple representing selected range
    """
    # Convert date objects to datetime if needed
    if isinstance(min_date, date) and not isinstance(min_date, datetime):
        min_date = datetime.combine(min_date, datetime.min.time())
    if isinstance(max_date, date) and not isinstance(max_date, datetime):
        max_date = datetime.combine(max_date, datetime.min.time())

    # Initialize session state keys
    range_type_key = f"{key_prefix}_range_type"
    start_date_key = f"{key_prefix}_start_date"
    end_date_key = f"{key_prefix}_end_date"

    # Try to load from URL params first (if enabled)
    url_dates = None
    if include_url_params:
        url_dates = load_url_params(param_prefix=key_prefix)

    # Initialize session state if not already set
    if range_type_key not in st.session_state:
        # Check URL params first
        if url_dates:
            try:
                url_start = datetime.strptime(url_dates[0], "%Y-%m-%d")
                url_end = datetime.strptime(url_dates[1], "%Y-%m-%d")
                st.session_state[range_type_key] = "custom"
                st.session_state[start_date_key] = url_start
                st.session_state[end_date_key] = url_end
            except Exception:
                # Fall back to default
                st.session_state[range_type_key] = default_range
        else:
            st.session_state[range_type_key] = default_range

    if start_date_key not in st.session_state or end_date_key not in st.session_state:
        # Calculate initial dates based on range type
        start, end = get_quick_range_dates(
            st.session_state.get(range_type_key, default_range),
            min_date,
            max_date
        )
        st.session_state[start_date_key] = start
        st.session_state[end_date_key] = end

    # Create UI
    st.markdown("### Date Range")

    # Quick select buttons
    col1, col2, col3, col4, col5, col6 = st.columns([1.2, 1.4, 1.2, 0.8, 1.2, 0.8])

    with col1:
        if st.button("Next Week", use_container_width=True,
                     type="primary" if st.session_state[range_type_key] == "week" else "secondary"):
            st.session_state[range_type_key] = "week"
            start, end = get_quick_range_dates("week", min_date, max_date)
            st.session_state[start_date_key] = start
            st.session_state[end_date_key] = end
            st.rerun()

    with col2:
        if st.button("Next 2 Weeks", use_container_width=True,
                     type="primary" if st.session_state[range_type_key] == "2weeks" else "secondary"):
            st.session_state[range_type_key] = "2weeks"
            start, end = get_quick_range_dates("2weeks", min_date, max_date)
            st.session_state[start_date_key] = start
            st.session_state[end_date_key] = end
            st.rerun()

    with col3:
        if st.button("Next Month", use_container_width=True,
                     type="primary" if st.session_state[range_type_key] == "month" else "secondary"):
            st.session_state[range_type_key] = "month"
            start, end = get_quick_range_dates("month", min_date, max_date)
            st.session_state[start_date_key] = start
            st.session_state[end_date_key] = end
            st.rerun()

    with col4:
        if st.button("All", use_container_width=True,
                     type="primary" if st.session_state[range_type_key] == "all" else "secondary"):
            st.session_state[range_type_key] = "all"
            st.session_state[start_date_key] = min_date
            st.session_state[end_date_key] = max_date
            st.rerun()

    with col5:
        if st.button("Custom", use_container_width=True,
                     type="primary" if st.session_state[range_type_key] == "custom" else "secondary"):
            st.session_state[range_type_key] = "custom"

    with col6:
        # Reset button (only show if filtered)
        if st.session_state[range_type_key] != default_range:
            if st.button("Reset", use_container_width=True):
                st.session_state[range_type_key] = default_range
                start, end = get_quick_range_dates(default_range, min_date, max_date)
                st.session_state[start_date_key] = start
                st.session_state[end_date_key] = end
                st.rerun()

    # Custom date pickers (only show if custom selected)
    if st.session_state[range_type_key] == "custom":
        col1, col2 = st.columns(2)

        with col1:
            new_start = st.date_input(
                "Start Date",
                value=st.session_state[start_date_key],
                min_value=min_date,
                max_value=max_date,
                key=f"{key_prefix}_start_picker"
            )
            if new_start != st.session_state[start_date_key]:
                st.session_state[start_date_key] = datetime.combine(new_start, datetime.min.time())
                st.rerun()

        with col2:
            new_end = st.date_input(
                "End Date",
                value=st.session_state[end_date_key],
                min_value=min_date,
                max_value=max_date,
                key=f"{key_prefix}_end_picker"
            )
            if new_end != st.session_state[end_date_key]:
                st.session_state[end_date_key] = datetime.combine(new_end, datetime.max.time())
                st.rerun()

    # Get current selected dates
    start_date = st.session_state[start_date_key]
    end_date = st.session_state[end_date_key]

    # Sync to URL params if enabled
    if include_url_params:
        sync_url_params(start_date, end_date, param_prefix=key_prefix)

    # Show current selection with visual feedback
    date_range_days = (end_date - start_date).days + 1
    is_filtered = st.session_state[range_type_key] != "all"

    # Format dates for display
    start_str = start_date.strftime("%b %d, %Y") if isinstance(start_date, datetime) else str(start_date)
    end_str = end_date.strftime("%b %d, %Y") if isinstance(end_date, datetime) else str(end_date)

    if is_filtered:
        st.info(f"**Showing:** {start_str} to {end_str} ({date_range_days} days)")
    else:
        st.success(f"**Showing all dates:** {start_str} to {end_str} ({date_range_days} days)")

    return start_date, end_date


def calculate_date_stats(
    df: pd.DataFrame,
    date_column: str,
    start_date: datetime,
    end_date: datetime,
    quantity_column: Optional[str] = None
) -> dict:
    """Calculate statistics about filtered data for display.

    Args:
        df: Filtered DataFrame
        date_column: Name of date column
        start_date: Filter start date
        end_date: Filter end date
        quantity_column: Optional column name for quantity aggregation

    Returns:
        Dictionary with stats (num_records, num_days, total_quantity, etc.)
    """
    stats = {
        'num_records': len(df),
        'num_days': (end_date - start_date).days + 1,
        'start_date': start_date,
        'end_date': end_date
    }

    if not df.empty and date_column in df.columns:
        unique_dates = df[date_column].nunique()
        stats['unique_dates'] = unique_dates

    if quantity_column and quantity_column in df.columns:
        stats['total_quantity'] = df[quantity_column].sum()
        stats['avg_per_day'] = stats['total_quantity'] / stats['num_days'] if stats['num_days'] > 0 else 0

    return stats
