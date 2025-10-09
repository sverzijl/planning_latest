# Daily Snapshot Module - Usage Guide

## Overview

The `daily_snapshot.py` module provides comprehensive daily inventory tracking and analysis for production planning results. It generates snapshots showing:

- Inventory at each location (by batch)
- In-transit shipments
- Production activity
- Inflows and outflows
- Demand satisfaction

## Basic Usage

### Setup

```python
from datetime import date
from src.analysis import DailySnapshotGenerator
from src.production.scheduler import ProductionSchedule
from src.models.shipment import Shipment
from src.models.location import Location
from src.models.forecast import Forecast

# Assuming you have these from your planning results
production_schedule: ProductionSchedule = ...
shipments: List[Shipment] = ...
locations_dict: Dict[str, Location] = ...
forecast: Forecast = ...

# Create the snapshot generator
generator = DailySnapshotGenerator(
    production_schedule=production_schedule,
    shipments=shipments,
    locations_dict=locations_dict,
    forecast=forecast
)
```

### Generate Snapshots

```python
# Generate snapshots for a date range
start_date = date(2025, 1, 1)
end_date = date(2025, 1, 31)

snapshots = generator.generate_snapshots(start_date, end_date)

# Access snapshot data
for snapshot in snapshots:
    print(f"\nSnapshot for {snapshot.date}")
    print(f"Total system inventory: {snapshot.total_system_inventory:.0f} units")
    print(f"In transit: {snapshot.total_in_transit:.0f} units")
    print(f"Production: {len(snapshot.production_activity)} batches")
    print(f"Demand records: {len(snapshot.demand_satisfied)}")
```

## Data Structure Examples

### Location Inventory

```python
snapshot = snapshots[0]

# Iterate through locations
for loc_id, loc_inv in snapshot.location_inventory.items():
    print(f"\n{loc_inv.location_name} ({loc_id})")
    print(f"Total: {loc_inv.total_quantity:.0f} units")

    # Breakdown by product
    for product_id, quantity in loc_inv.by_product.items():
        print(f"  {product_id}: {quantity:.0f} units")

    # Individual batches
    for batch in loc_inv.batches:
        print(f"  Batch {batch.batch_id}: {batch.quantity:.0f} units, {batch.age_days} days old")
```

### In-Transit Shipments

```python
# Check what's in transit
for transit in snapshot.in_transit:
    print(f"{transit.origin_id} -> {transit.destination_id}")
    print(f"  Product: {transit.product_id}")
    print(f"  Quantity: {transit.quantity:.0f} units")
    print(f"  Day {transit.days_in_transit} of transit")
    print(f"  Arriving: {transit.expected_arrival_date}")
```

### Production Activity

```python
# Check what was produced today
if snapshot.production_activity:
    print(f"\nProduction on {snapshot.date}:")
    for batch in snapshot.production_activity:
        print(f"  {batch.product_id}: {batch.quantity:.0f} units (Batch {batch.batch_id})")
else:
    print(f"No production on {snapshot.date}")
```

### Inventory Flows

```python
# Analyze inflows
print(f"\nInflows on {snapshot.date}:")
for flow in snapshot.inflows:
    if flow.flow_type == "production":
        print(f"  PRODUCTION: {flow.quantity:.0f} units of {flow.product_id}")
    elif flow.flow_type == "arrival":
        print(f"  ARRIVAL: {flow.quantity:.0f} units from {flow.counterparty}")

# Analyze outflows
print(f"\nOutflows on {snapshot.date}:")
for flow in snapshot.outflows:
    if flow.flow_type == "departure":
        print(f"  DEPARTURE: {flow.quantity:.0f} units to {flow.counterparty}")
    elif flow.flow_type == "demand":
        print(f"  DEMAND: {flow.quantity:.0f} units delivered")
```

### Demand Satisfaction

```python
# Check demand fulfillment
print(f"\nDemand Satisfaction on {snapshot.date}:")
for demand in snapshot.demand_satisfied:
    fill_rate = demand.fill_rate * 100
    status = "OK" if demand.is_satisfied else "SHORT"

    print(f"  {demand.destination_id} - {demand.product_id}")
    print(f"    Demand: {demand.demand_quantity:.0f}")
    print(f"    Supplied: {demand.supplied_quantity:.0f}")
    print(f"    Fill Rate: {fill_rate:.1f}%")
    print(f"    Status: {status}")

    if not demand.is_satisfied:
        print(f"    Shortage: {demand.shortage_quantity:.0f} units")
```

## Advanced Usage

### Track Specific Batch Through Network

```python
def track_batch(batch_id: str, snapshots: List[DailySnapshot]):
    """Track a batch through the network over time."""
    print(f"\nTracking Batch {batch_id}:")

    for snapshot in snapshots:
        # Check each location
        for loc_id, loc_inv in snapshot.location_inventory.items():
            for batch in loc_inv.batches:
                if batch.batch_id == batch_id:
                    print(f"  {snapshot.date}: At {loc_id}, "
                          f"{batch.quantity:.0f} units, age {batch.age_days}d")

        # Check in-transit
        for transit in snapshot.in_transit:
            if transit.shipment_id.startswith(batch_id):  # Assuming shipment ID includes batch ID
                print(f"  {snapshot.date}: In transit from {transit.origin_id} "
                      f"to {transit.destination_id}")

# Use it
track_batch("BATCH_001", snapshots)
```

### Calculate Inventory Metrics

```python
def calculate_inventory_metrics(snapshots: List[DailySnapshot]):
    """Calculate key inventory metrics."""
    total_days = len(snapshots)

    avg_inventory = sum(s.total_system_inventory for s in snapshots) / total_days
    avg_in_transit = sum(s.total_in_transit for s in snapshots) / total_days

    total_production = sum(
        sum(b.quantity for b in s.production_activity)
        for s in snapshots
    )

    total_demand = sum(
        sum(d.demand_quantity for d in s.demand_satisfied)
        for s in snapshots
    )

    total_supplied = sum(
        sum(d.supplied_quantity for d in s.demand_satisfied)
        for s in snapshots
    )

    fill_rate = (total_supplied / total_demand * 100) if total_demand > 0 else 100.0

    print(f"Inventory Metrics ({total_days} days):")
    print(f"  Average Inventory: {avg_inventory:.0f} units")
    print(f"  Average In-Transit: {avg_in_transit:.0f} units")
    print(f"  Total Production: {total_production:.0f} units")
    print(f"  Total Demand: {total_demand:.0f} units")
    print(f"  Total Supplied: {total_supplied:.0f} units")
    print(f"  Overall Fill Rate: {fill_rate:.1f}%")

# Use it
calculate_inventory_metrics(snapshots)
```

### Export to DataFrame

```python
import pandas as pd

def snapshots_to_dataframe(snapshots: List[DailySnapshot]) -> pd.DataFrame:
    """Convert snapshots to pandas DataFrame for analysis."""
    data = []

    for snapshot in snapshots:
        for loc_id, loc_inv in snapshot.location_inventory.items():
            for product_id, quantity in loc_inv.by_product.items():
                data.append({
                    'date': snapshot.date,
                    'location_id': loc_id,
                    'location_name': loc_inv.location_name,
                    'product_id': product_id,
                    'quantity': quantity,
                    'num_batches': len([b for b in loc_inv.batches if b.product_id == product_id])
                })

    return pd.DataFrame(data)

# Use it
df = snapshots_to_dataframe(snapshots)
print(df.head())

# Pivot for visualization
pivot = df.pivot_table(
    values='quantity',
    index='date',
    columns='location_id',
    aggfunc='sum'
)
print(pivot)
```

### Identify Inventory Issues

```python
def identify_issues(snapshots: List[DailySnapshot]):
    """Identify potential inventory issues."""
    issues = []

    for snapshot in snapshots:
        # Check for shortages
        for demand in snapshot.demand_satisfied:
            if not demand.is_satisfied:
                issues.append({
                    'date': snapshot.date,
                    'type': 'shortage',
                    'location': demand.destination_id,
                    'product': demand.product_id,
                    'shortage': demand.shortage_quantity
                })

        # Check for old inventory (>10 days)
        for loc_id, loc_inv in snapshot.location_inventory.items():
            for batch in loc_inv.batches:
                if batch.age_days > 10:
                    issues.append({
                        'date': snapshot.date,
                        'type': 'old_inventory',
                        'location': loc_id,
                        'batch_id': batch.batch_id,
                        'age_days': batch.age_days
                    })

    return issues

# Use it
issues = identify_issues(snapshots)
print(f"Found {len(issues)} issues:")
for issue in issues[:10]:  # Show first 10
    print(f"  {issue}")
```

## Integration with UI

### Example for Streamlit

```python
import streamlit as st
import plotly.graph_objects as go

# In your Results page
if st.session_state.get('results'):
    results = st.session_state['results']

    # Create generator
    generator = DailySnapshotGenerator(
        production_schedule=results['production_schedule'],
        shipments=results['shipments'],
        locations_dict=results['locations'],
        forecast=st.session_state['forecast']
    )

    # Date selector
    snapshot_date = st.date_input("Select snapshot date")

    if st.button("Generate Snapshot"):
        snapshot = generator._generate_single_snapshot(snapshot_date)

        # Display summary
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Inventory", f"{snapshot.total_system_inventory:.0f}")
        col2.metric("In Transit", f"{snapshot.total_in_transit:.0f}")
        col3.metric("Production", len(snapshot.production_activity))

        # Location inventory table
        st.subheader("Location Inventory")
        inv_data = []
        for loc_id, loc_inv in snapshot.location_inventory.items():
            inv_data.append({
                'Location': loc_inv.location_name,
                'Total': loc_inv.total_quantity,
                **loc_inv.by_product
            })
        st.dataframe(inv_data)

        # Demand satisfaction
        st.subheader("Demand Satisfaction")
        demand_data = [{
            'Destination': d.destination_id,
            'Product': d.product_id,
            'Demand': d.demand_quantity,
            'Supplied': d.supplied_quantity,
            'Fill Rate': f"{d.fill_rate*100:.1f}%"
        } for d in snapshot.demand_satisfied]
        st.dataframe(demand_data)
```

## Performance Considerations

### Efficient Lookup

The generator builds efficient lookup structures during initialization:
- Batches indexed by production date
- Shipments indexed by departure, arrival, and delivery dates
- Uses defaultdict for fast lookups

This makes snapshot generation O(n) where n is the number of shipments and batches, rather than O(n*m) where m is the date range.

### Memory Usage

For large planning horizons (6+ months), consider:
1. Generating snapshots in batches
2. Writing snapshots to disk/database
3. Using generators instead of lists

```python
# Memory-efficient approach
def generate_snapshots_lazy(generator, start_date, end_date):
    """Generate snapshots one at a time."""
    current_date = start_date
    while current_date <= end_date:
        yield generator._generate_single_snapshot(current_date)
        current_date += timedelta(days=1)

# Use it
for snapshot in generate_snapshots_lazy(generator, start_date, end_date):
    # Process snapshot
    process_snapshot(snapshot)
    # Snapshot is garbage collected after processing
```

## Testing

See `tests/test_daily_snapshot.py` for comprehensive test examples with mock data.
