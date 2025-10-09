# Daily Snapshot Component - Usage Guide

## Overview

The `render_daily_snapshot` component provides an interactive daily inventory snapshot view with comprehensive information about inventory levels, in-transit shipments, manufacturing activity, and demand satisfaction.

## File Location

`/home/sverzijl/planning_latest/ui/components/daily_snapshot.py`

## Features

### 1. Interactive Date Selection
- Select slider with date navigation
- Previous/Next day buttons
- Date format shows day of week for easy reference

### 2. Summary Metrics (Top Row)
- **Total Inventory**: All inventory across locations
- **In Transit**: Shipments currently in transit
- **Production**: Units produced on selected date
- **Demand**: Total demand for selected date

### 3. Location Inventory Section
- Expandable cards for each location
- Manufacturing site expanded by default
- Batch-level detail with:
  - Batch ID
  - Product
  - Quantity
  - Age (days since production)
  - Production date
- Color-coded by age:
  - 🟢 Green: Fresh (0-3 days)
  - 🟡 Yellow: Medium (4-7 days)
  - 🔴 Red: Old (8+ days)

### 4. In-Transit & Manufacturing (Two-Column Layout)

**In-Transit (Left Column):**
- Shows shipments currently in transit
- Route display: Origin → Destination
- Days in transit counter
- Product and quantity

**Manufacturing Activity (Right Column):**
- Batches produced on selected date
- Batch ID, product, quantity
- Labor hours used
- Total labor hours summary

### 5. Inflows & Outflows (Two-Column Layout)

**Inflows (Left Column):**
- Production events (blue background)
- Arrival events (green background)
- Location, product, quantity, details

**Outflows (Right Column):**
- Departure events (yellow background)
- Demand fulfillment (light blue background)
- Location, product, quantity, details

### 6. Demand Satisfaction Section
- Destination, product, demand quantity
- Supplied quantity
- Status (✅ Met or ⚠️ Short)
- Color-coded: Green for met, yellow for shortage
- Summary badge showing overall status

## Usage

### Basic Usage

```python
from ui.components import render_daily_snapshot

# In your Streamlit page
results = get_current_results()  # Your results dict
locations_list = st.session_state.get('locations', [])
locations = {loc.location_id: loc for loc in locations_list} if locations_list else {}

render_daily_snapshot(
    results=results,
    locations=locations,
    key_prefix="my_snapshot"
)
```

### Integration into Results Page

Add a new tab to the Results page (`ui/pages/3_Results.py`):

```python
# In the tab creation section
tab_overview, tab_production, tab_distribution, tab_costs, tab_comparison, tab_snapshot = st.tabs([
    "📊 Overview",
    "📦 Production",
    "🚚 Distribution",
    "💰 Costs",
    "⚖️ Comparison",
    "📸 Daily Snapshot"  # NEW TAB
])

# Add new tab content
with tab_snapshot:
    st.markdown("""
    <div class="info-box">
        <div style="font-weight: 600; margin-bottom: 8px;">📸 Daily Snapshot</div>
        <div>Interactive daily view of inventory, production, shipments, and demand.</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Get current results
    results = get_current_results()
    locations_list = st.session_state.get('locations', [])
    locations = {loc.location_id: loc for loc in locations_list} if locations_list else {}

    # Render snapshot
    from ui.components import render_daily_snapshot
    render_daily_snapshot(
        results=results,
        locations=locations,
        key_prefix="results_snapshot"
    )
```

### Required Data Structure

The `results` dictionary should contain:

```python
results = {
    'production_schedule': ProductionSchedule,  # Required
    'shipments': List[Shipment],                # Required
    'cost_breakdown': TotalCostBreakdown,       # Optional
}
```

**ProductionSchedule** should have:
- `production_batches`: List of `ProductionBatch` objects
- `daily_totals`: Dict[date, float]
- `daily_labor_hours`: Dict[date, float]

**Shipment** objects should have:
- `product_id`: str
- `origin_id`: str
- `destination_id`: str
- `quantity`: float
- `departure_date`: date (or `production_date`)
- `arrival_date`: date (optional)

**Location** objects should have:
- `location_id`: str
- `name`: str
- `location_type`: str (optional)

### Advanced Usage

#### Custom Key Prefix
Use different key prefixes to have multiple instances on the same page:

```python
render_daily_snapshot(results, locations, key_prefix="snapshot_1")
render_daily_snapshot(results, locations, key_prefix="snapshot_2")
```

#### Accessing Selected Date
The selected date is stored in session state:

```python
selected_date = st.session_state.get('daily_snapshot_selected_date')
# Or with custom prefix:
selected_date = st.session_state.get('my_snapshot_selected_date')
```

## Data Flow

1. **Component receives results and locations**
2. **Determines date range** from production batches and shipments
3. **User selects date** via slider or navigation buttons
4. **Generates snapshot** for selected date:
   - Filters production batches for selected date
   - Identifies in-transit shipments
   - Calculates inventory levels (simplified)
   - Extracts inflows/outflows
   - Retrieves demand from session state forecast
5. **Renders all sections** with color-coded tables

## Styling

The component uses the design system from `ui/components/styling.py`:

- `section_header()`: Section titles with icons
- `colored_metric()`: Summary metric cards
- `success_badge()`, `warning_badge()`, `error_badge()`: Status indicators
- Pandas DataFrame styling: Custom background colors for row highlighting

## Limitations & Future Enhancements

### Current Limitations

1. **Simplified Inventory Tracking**: The component shows production batches at manufacturing site but doesn't track full inventory movement through the network. For accurate inventory at hubs and breadrooms, you would need a proper inventory state tracking system.

2. **Demand Satisfaction**: Currently pulls from session state forecast. Actual fulfillment tracking would require comparing planned shipments to demand.

3. **No Shelf Life Display**: Age is shown in days but shelf life status (frozen/ambient/thawed) is not tracked.

### Suggested Enhancements

1. **Add Inventory State Tracker**: Implement proper batch tracking through the network with location transitions.

2. **Shelf Life Visualization**: Show remaining shelf life, storage mode (frozen/ambient), and expiration warnings.

3. **Demand vs. Supply Chart**: Add visual comparison of demand and planned supply for each destination.

4. **Export to CSV**: Add download button for snapshot data.

5. **Network Flow Diagram**: Add mini network visualization showing active flows on selected date.

6. **Batch Lineage**: Click on batch to see its journey through the network.

## Testing

A test file is provided to demo the component:

```bash
streamlit run test_daily_snapshot_ui.py
```

This creates mock data and demonstrates all component features.

## Dependencies

- `streamlit`
- `pandas`
- `src.models.location`
- `src.production.scheduler`
- `src.models.shipment`
- `ui.components.styling`

## File Structure

```
ui/components/
├── daily_snapshot.py          # Main component
├── __init__.py                # Export render_daily_snapshot
└── DAILY_SNAPSHOT_USAGE.md    # This file

test_daily_snapshot_ui.py      # Test/demo script
```

## Troubleshooting

### Issue: "No production schedule available"
**Solution**: Ensure `results['production_schedule']` is not None and contains batches.

### Issue: "No production or shipment data available"
**Solution**: Verify production batches and shipments have valid dates.

### Issue: Demand section is empty
**Solution**: Ensure forecast is loaded in `st.session_state['forecast']` with entries for the selected date.

### Issue: Location inventory shows only manufacturing site
**Solution**: This is expected behavior - the simplified inventory tracker only shows production batches at manufacturing. Full network inventory tracking requires additional implementation.

## Support

For questions or issues:
1. Check this usage guide
2. Review the test script (`test_daily_snapshot_ui.py`)
3. Examine the component source code for inline documentation
