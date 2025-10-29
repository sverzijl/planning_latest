# UI Components

This directory contains reusable UI components for the Streamlit application. All components follow the design system defined in `ui/assets/styles.css` and support consistent styling through `ui/components/styling.py`.

## Table of Contents

- [Date Filter Component](#date-filter-component)
- [Chart Components](#chart-components)
- [Data Table Components](#data-table-components)
- [Network Visualization](#network-visualization)
- [Styling Utilities](#styling-utilities)

## Date Filter Component

**File:** `date_filter.py`

A reusable date range filter component for analysis pages. Provides quick select buttons and custom date range selection with session state persistence and URL parameter synchronization.

### Core Functions

#### `render_date_range_filter()`

Main component that renders the filter UI and manages state.

```python
from ui.components import render_date_range_filter

# Render filter
start_date, end_date = render_date_range_filter(
    min_date=df['date'].min(),
    max_date=df['date'].max(),
    default_range="2weeks",
    key_prefix="my_filter",
    include_url_params=True
)
```

**Parameters:**
- `min_date` (datetime): Minimum selectable date from data
- `max_date` (datetime): Maximum selectable date from data
- `default_range` (str): Default selection - "all", "week", "2weeks", "month", or "custom"
- `key_prefix` (str): Unique prefix for session state keys (prevents conflicts)
- `include_url_params` (bool): Whether to sync with URL query parameters for shareable links

**Returns:** `Tuple[datetime, datetime]` - (start_date, end_date) representing selected range

**Features:**
- Quick select buttons: "Next Week", "Next 2 Weeks", "Next Month", "All", "Custom"
- Custom date picker (shown when "Custom" is selected)
- Reset button (shown when not using default range)
- Visual feedback showing current selection
- Session state persistence across page navigation
- URL parameter sync for shareable links

#### `apply_date_filter()`

Helper to filter DataFrames based on selected range.

```python
from ui.components import apply_date_filter

# Filter DataFrame
filtered_df = apply_date_filter(
    df=production_data,
    date_column='production_date',
    start_date=start_date,
    end_date=end_date
)
```

**Parameters:**
- `df` (pd.DataFrame): DataFrame to filter
- `date_column` (str): Name of date column to filter on
- `start_date` (datetime): Start of range (inclusive)
- `end_date` (datetime): End of range (inclusive)

**Returns:** `pd.DataFrame` - Filtered DataFrame (copy, not view)

#### `get_quick_range_dates()`

Calculate dates for quick select options.

```python
from ui.components import get_quick_range_dates

# Get date range for "2 weeks from today"
start, end = get_quick_range_dates(
    range_type="2weeks",
    min_date=min_date,
    max_date=max_date,
    reference_date=datetime.now()  # Optional, defaults to today
)
```

**Parameters:**
- `range_type` (str): "week", "2weeks", "month", "all", or "custom"
- `min_date` (datetime): Minimum available date
- `max_date` (datetime): Maximum available date
- `reference_date` (datetime, optional): Starting point (defaults to today)

**Returns:** `Tuple[datetime, datetime]` - (start_date, end_date)

**Smart Behavior:**
- If `reference_date` (today) is within planning horizon: Uses today as start
- If today is before planning horizon: Uses `min_date` as start
- If today is after planning horizon: Uses `min_date` as start
- Automatically caps ranges at `max_date` (won't exceed available data)

#### `calculate_date_stats()`

Calculate statistics about filtered data for display.

```python
from ui.components import calculate_date_stats

stats = calculate_date_stats(
    df=filtered_df,
    date_column='production_date',
    start_date=start_date,
    end_date=end_date,
    quantity_column='units'  # Optional
)

# stats = {
#     'num_records': 42,
#     'num_days': 14,
#     'unique_dates': 10,
#     'total_quantity': 15000,
#     'avg_per_day': 1071.4,
#     'start_date': datetime(...),
#     'end_date': datetime(...)
# }
```

**Parameters:**
- `df` (pd.DataFrame): Filtered DataFrame
- `date_column` (str): Name of date column
- `start_date` (datetime): Filter start date
- `end_date` (datetime): Filter end date
- `quantity_column` (str, optional): Column name for quantity aggregation

**Returns:** `dict` - Statistics dictionary

#### `sync_url_params()`

Sync date filter with URL query parameters (called automatically by `render_date_range_filter`).

```python
from ui.components import sync_url_params

sync_url_params(
    start_date=start_date,
    end_date=end_date,
    param_prefix="date"
)
```

Creates URL like: `?date_start=2025-01-01&date_end=2025-01-14`

### Integration Examples

#### Production Schedule Page

```python
import streamlit as st
import pandas as pd
from datetime import datetime
from ui.components import render_date_range_filter, apply_date_filter

# Get date range from production schedule
min_date = datetime.combine(
    min(batch.production_date for batch in production_schedule.production_batches),
    datetime.min.time()
)
max_date = datetime.combine(
    max(batch.production_date for batch in production_schedule.production_batches),
    datetime.min.time()
)

# Render filter
filter_start_date, filter_end_date = render_date_range_filter(
    min_date=min_date,
    max_date=max_date,
    default_range="2weeks",
    key_prefix="production_filter",
    include_url_params=True
)

# Filter production batches
filtered_batches = [
    b for b in production_schedule.production_batches
    if filter_start_date.date() <= b.production_date <= filter_end_date.date()
]

# Use filtered_batches for all visualizations
```

#### Distribution Plan Page

```python
# Filter by delivery date
delivery_dates = [s.delivery_date for s in shipments if s.delivery_date]
min_date = datetime.combine(min(delivery_dates), datetime.min.time())
max_date = datetime.combine(max(delivery_dates), datetime.min.time())

# Render filter
filter_start_date, filter_end_date = render_date_range_filter(
    min_date=min_date,
    max_date=max_date,
    default_range="2weeks",
    key_prefix="distribution_filter"
)

# Filter shipments
filtered_shipments = [
    s for s in shipments
    if filter_start_date.date() <= s.delivery_date <= filter_end_date.date()
]
```

#### Cost Analysis Page

```python
# Filter cost data by date (handle Optional fields safely)
labor_by_date = cost_breakdown.labor.by_date or {}
all_dates = list(labor_by_date.keys())

if all_dates:
    min_date = datetime.combine(min(all_dates), datetime.min.time())
    max_date = datetime.combine(max(all_dates), datetime.min.time())

    # Render filter
    filter_start_date, filter_end_date = render_date_range_filter(
        min_date=min_date,
        max_date=max_date,
        default_range="2weeks",
        key_prefix="cost_filter"
    )

    # Filter cost dictionaries
    filtered_labor_by_date = {
        d: cost for d, cost in labor_by_date.items()
        if filter_start_date.date() <= d <= filter_end_date.date()
    }

    # Recalculate totals for filtered period
    total_labor_cost = sum(filtered_labor_by_date.values())
else:
    st.info("No daily cost data available")
```

### Design Principles

1. **Session State Persistence:** Filter selections persist across page navigation and refreshes
2. **URL Shareability:** Optional URL parameter sync enables sharing specific date ranges via links
3. **Smart Defaults:** Automatically selects meaningful defaults based on current date and planning horizon
4. **Visual Feedback:** Clear indication of current selection with info/success messages
5. **Unique Keys:** `key_prefix` parameter prevents state conflicts when using multiple filters on same page
6. **Inclusive Ranges:** Start and end dates are both inclusive in filtering
7. **Flexible Date Types:** Handles both `datetime` and `date` objects seamlessly
8. **Copy, Not View:** `apply_date_filter` returns a copy to prevent unintended mutations

### Best Practices

1. **Use unique `key_prefix` values:** Prevents session state conflicts
   ```python
   # Good
   render_date_range_filter(..., key_prefix="production_filter")
   render_date_range_filter(..., key_prefix="cost_filter")

   # Bad - will conflict
   render_date_range_filter(..., key_prefix="date_filter")
   render_date_range_filter(..., key_prefix="date_filter")
   ```

2. **Convert dates to datetime:** Ensure consistency
   ```python
   # Good
   min_datetime = datetime.combine(min_date, datetime.min.time())

   # Also works, but less explicit
   min_datetime = min_date  # Function handles conversion
   ```

3. **Show filtered vs total counts:** Help users understand what they're viewing
   ```python
   if len(filtered_data) < len(all_data):
       st.caption(f"Filtered: {len(filtered_data)} / {len(all_data)} records")
   ```

4. **Filter all related data:** Maintain consistency across charts and tables
   ```python
   # Filter main data
   filtered_batches = [b for b in batches if ...]

   # Also filter related aggregations
   filtered_daily_totals = {d: qty for d, qty in daily_totals.items() if ...}
   ```

5. **Enable URL params for public dashboards:** Makes sharing specific views easy
   ```python
   # For internal pages
   render_date_range_filter(..., include_url_params=False)

   # For dashboards/reports
   render_date_range_filter(..., include_url_params=True)
   ```

---

## Chart Components

### Cost Charts (`cost_charts.py`)

- `render_cost_pie_chart()` - Pie chart showing cost proportions
- `render_cost_breakdown_chart()` - Bar chart of cost components
- `render_daily_cost_chart()` - Daily cost trends over time
- `render_labor_cost_breakdown()` - Labor cost analysis
- `render_transport_cost_by_route()` - Transport costs by route
- `render_cost_waterfall()` - Waterfall chart for cost per unit

### Production Charts (`production_gantt.py`)

- `render_production_gantt()` - Gantt chart of production batches
- `render_labor_hours_chart()` - Daily labor hours vs capacity
- `render_daily_production_chart()` - Daily production quantities by product
- `render_capacity_utilization_chart()` - Production capacity utilization over time

### Truck Loading Charts (`truck_loading_timeline.py`)

- `render_truck_loading_timeline()` - Timeline of truck departures and loading
- `render_truck_utilization_chart()` - Truck capacity utilization
- `render_shipments_by_destination_chart()` - Shipment distribution by destination
- `render_daily_truck_count_chart()` - Daily truck count over time

---

## Data Table Components

**File:** `data_tables.py`

- `render_production_batches_table()` - Production batch details
- `render_shipments_table()` - Shipment details
- `render_truck_loads_table()` - Truck loading manifest
- `render_unassigned_shipments_table()` - Unassigned shipments
- `render_cost_summary_table()` - Cost breakdown summary
- `render_labor_breakdown_table()` - Labor cost details
- `render_daily_breakdown_table()` - Daily production summary

---

## Network Visualization

**File:** `network_graph.py`

- `render_network_graph()` - Interactive network diagram showing routes and hubs
- `render_connectivity_matrix()` - Matrix visualization of location connectivity

---

## Styling Utilities

**File:** `styling.py`

Provides helper functions for consistent styling across all components. See file documentation for details.

Key functions:
- `apply_custom_css()` - Inject design system CSS
- `section_header()` - Styled section headers
- `colored_metric()` - Metric cards with color borders
- `status_badge()` - Status indicators
- `info_box()` - Styled info/warning/success boxes

---

## Development Guidelines

### Creating New Components

1. **Follow naming convention:** `render_<component_name>()`
2. **Use type hints:** All parameters and returns should be typed
3. **Add docstrings:** Include usage examples in module docstring
4. **Export in `__init__.py`:** Add to `__all__` list
5. **Use design system:** Import and use `styling.py` utilities
6. **Write tests:** Add tests to `tests/test_<component>.py`
7. **Update this README:** Document the new component

### Component Template

```python
\"\"\"Component name and description.

Usage:
    from ui.components import render_my_component

    fig = render_my_component(data, height=400)
    st.plotly_chart(fig, use_container_width=True)
\"\"\"

import plotly.graph_objects as go
from typing import Optional


def render_my_component(
    data: SomeType,
    height: int = 400,
    title: Optional[str] = None
) -> go.Figure:
    \"\"\"Render a custom visualization component.

    Args:
        data: Input data object
        height: Chart height in pixels
        title: Optional chart title

    Returns:
        Plotly Figure object
    \"\"\"
    # Implementation
    pass
```

### Testing Components

1. **Unit tests:** Test logic and data transformations
2. **Integration tests:** Test with real data structures
3. **Visual tests:** Manual testing in UI (screenshots for documentation)
4. **Edge cases:** Empty data, single item, very large datasets

### Performance Considerations

1. **Cache expensive operations:** Use `@st.cache_data` where appropriate
2. **Lazy loading:** Only process data that will be displayed
3. **Limit data size:** Filter/sample large datasets before visualization
4. **Optimize chart libraries:** Use appropriate chart types for data size

---

## Version History

- **v1.1.0** (2025-10-02): Added date filter component with full URL parameter support
- **v1.0.0** (2025-10-01): Initial component library with charts, tables, and network visualization
