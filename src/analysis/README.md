# Analysis Module

Backend data processor for production planning analysis and visualization.

## Overview

The analysis module provides tools for post-processing and analyzing production planning results. It transforms raw planning data (production schedules, shipments, etc.) into structured snapshots and reports suitable for visualization and decision-making.

## Components

### Daily Snapshot Generator (`daily_snapshot.py`)

Generates daily inventory snapshots showing the state of the supply chain on any given date.

**Key Features:**
- Track inventory at each location over time
- Monitor in-transit shipments
- Analyze production activity
- Track inventory flows (inflows/outflows)
- Measure demand satisfaction
- Calculate fill rates and shortages

**Data Classes:**
- `BatchInventory`: Individual batch at a location
- `LocationInventory`: Aggregated inventory at a location
- `TransitInventory`: Shipments in transit
- `InventoryFlow`: Inventory movements (production, arrivals, departures, demand)
- `DemandRecord`: Demand vs. supply comparison
- `DailySnapshot`: Complete snapshot for a single date

**Main Class:**
- `DailySnapshotGenerator`: Generates snapshots from planning results

## Installation

No additional dependencies beyond the main project requirements.

```bash
# The analysis module uses only standard library and existing project dependencies
pip install -r requirements.txt
```

## Quick Start

```python
from datetime import date
from src.analysis import DailySnapshotGenerator

# Create generator with planning results
generator = DailySnapshotGenerator(
    production_schedule=production_schedule,
    shipments=shipments,
    locations_dict=locations,
    forecast=forecast
)

# Generate snapshots
snapshots = generator.generate_snapshots(
    start_date=date(2025, 1, 1),
    end_date=date(2025, 1, 31)
)

# Access snapshot data
for snapshot in snapshots:
    print(f"Date: {snapshot.date}")
    print(f"Total Inventory: {snapshot.total_system_inventory:.0f}")
    print(f"In Transit: {snapshot.total_in_transit:.0f}")
```

## Use Cases

### 1. Inventory Tracking Dashboard

Create a dashboard showing daily inventory levels across locations:

```python
# Generate snapshots for visualization
snapshots = generator.generate_snapshots(start_date, end_date)

# Extract data for plotting
dates = [s.date for s in snapshots]
inventory_levels = [s.total_system_inventory for s in snapshots]

# Plot with your favorite library (plotly, matplotlib, etc.)
```

### 2. Demand Satisfaction Analysis

Analyze how well the plan satisfies demand:

```python
# Calculate overall fill rate
total_demand = sum(
    sum(d.demand_quantity for d in s.demand_satisfied)
    for s in snapshots
)
total_supplied = sum(
    sum(d.supplied_quantity for d in s.demand_satisfied)
    for s in snapshots
)
overall_fill_rate = (total_supplied / total_demand) * 100

# Identify problematic dates/locations
shortages = [
    (s.date, d.destination_id, d.product_id, d.shortage_quantity)
    for s in snapshots
    for d in s.demand_satisfied
    if not d.is_satisfied
]
```

### 3. Batch Tracking

Track individual batches through the supply chain:

```python
def track_batch(batch_id, snapshots):
    """Follow a batch through the network."""
    for snapshot in snapshots:
        # Check each location
        for loc_inv in snapshot.location_inventory.values():
            for batch in loc_inv.batches:
                if batch.batch_id == batch_id:
                    print(f"{snapshot.date}: {batch.quantity} at {loc_inv.location_name}")
```

### 4. Flow Analysis

Understand inventory movements:

```python
# Analyze daily flows
for snapshot in snapshots:
    production_flow = sum(f.quantity for f in snapshot.inflows if f.flow_type == "production")
    shipment_flow = sum(f.quantity for f in snapshot.outflows if f.flow_type == "departure")
    demand_flow = sum(f.quantity for f in snapshot.outflows if f.flow_type == "demand")

    print(f"{snapshot.date}: Produced {production_flow}, Shipped {shipment_flow}, Delivered {demand_flow}")
```

### 5. Inventory Age Analysis

Monitor inventory freshness:

```python
# Find old inventory
for snapshot in snapshots:
    for loc_inv in snapshot.location_inventory.values():
        old_batches = [b for b in loc_inv.batches if b.age_days > 10]
        if old_batches:
            print(f"{snapshot.date} - {loc_inv.location_name}: {len(old_batches)} batches over 10 days old")
```

## Architecture

### Design Principles

1. **Efficient Indexing**: Pre-builds lookup structures for O(1) date-based queries
2. **Immutable Data**: Uses dataclasses for clear, immutable snapshot data
3. **Lazy Evaluation**: Supports generator-based snapshot creation for memory efficiency
4. **Separation of Concerns**: Pure data processing, no visualization logic
5. **Type Safety**: Full type hints for IDE support and validation

### Performance

The generator builds efficient indexes during initialization:

```
Initialization: O(S) where S = number of shipments
Single Snapshot: O(S) where S = number of shipments/batches
Snapshot Range: O(D*S) where D = number of dates, S = shipments/batches
```

For a typical 6-month plan:
- ~1000 shipments
- ~200 dates
- Memory: ~10-50 MB
- Generation time: <1 second per snapshot

### Memory Optimization

For large plans (>1000 dates), use lazy generation:

```python
from datetime import timedelta

def generate_snapshots_lazy(generator, start_date, end_date):
    current_date = start_date
    while current_date <= end_date:
        yield generator._generate_single_snapshot(current_date)
        current_date += timedelta(days=1)
```

## Data Flow

```
Input:
  - ProductionSchedule (batches)
  - List[Shipment] (routes, timing)
  - Dict[str, Location] (locations)
  - Forecast (demand)
         ↓
  DailySnapshotGenerator
    - Builds lookup indexes
    - Tracks batch movement
    - Calculates flows
         ↓
Output:
  - List[DailySnapshot]
    - Location inventory
    - Transit inventory
    - Production activity
    - Flows (in/out)
    - Demand satisfaction
```

## Integration

### With UI (Streamlit)

```python
# In ui/pages/3_Results.py
from src.analysis import DailySnapshotGenerator

if st.session_state.get('results'):
    generator = DailySnapshotGenerator(...)
    snapshot_date = st.date_input("Snapshot Date")
    snapshot = generator._generate_single_snapshot(snapshot_date)

    # Display in UI
    st.metric("Inventory", snapshot.total_system_inventory)
    st.dataframe(snapshot.demand_satisfied)
```

### With Exporters

```python
# In src/exporters/
from src.analysis import DailySnapshotGenerator

def export_snapshots_to_excel(snapshots, filename):
    """Export snapshots to Excel for external analysis."""
    # Convert to DataFrames
    # Write to Excel
    pass
```

### With Optimization

```python
# Compare planned vs. actual
planned_snapshots = generator.generate_snapshots(start, end)
actual_snapshots = actual_generator.generate_snapshots(start, end)

# Calculate variance
for planned, actual in zip(planned_snapshots, actual_snapshots):
    inventory_variance = actual.total_system_inventory - planned.total_system_inventory
    print(f"{planned.date}: Variance = {inventory_variance}")
```

## Testing

Comprehensive test suite in `tests/test_daily_snapshot.py`:

```bash
pytest tests/test_daily_snapshot.py -v
```

Tests cover:
- Snapshot generation
- Inventory tracking through network
- In-transit detection
- Flow calculations
- Demand satisfaction
- Edge cases (empty data, no shipments, etc.)

## Future Enhancements

Planned features:
1. **Shelf Life Tracking**: Track remaining shelf life in batches
2. **Cost Attribution**: Attribute costs to inventory (holding, transport)
3. **Alerts**: Automatic detection of issues (stockouts, old inventory)
4. **Aggregation**: Weekly/monthly rollups
5. **Comparison**: Compare multiple scenarios
6. **Forecasting**: Predict future inventory levels
7. **Database Export**: Direct export to database tables

## Documentation

- `USAGE_EXAMPLE.md`: Comprehensive usage examples
- `README.md`: This file
- Inline docstrings: All classes and methods documented

## License

Part of the planning_latest project.
