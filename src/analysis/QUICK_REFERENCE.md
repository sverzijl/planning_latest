# Daily Snapshot Module - Quick Reference

## Import

```python
from src.analysis import (
    DailySnapshotGenerator,
    DailySnapshot,
    BatchInventory,
    LocationInventory,
    TransitInventory,
    InventoryFlow,
    DemandRecord
)
```

## Setup

```python
generator = DailySnapshotGenerator(
    production_schedule=production_schedule,  # ProductionSchedule
    shipments=shipments,                      # List[Shipment]
    locations_dict=locations,                 # Dict[str, Location]
    forecast=forecast                         # Forecast
)
```

## Generate Snapshots

```python
# Single snapshot
snapshot = generator._generate_single_snapshot(date(2025, 1, 15))

# Date range
snapshots = generator.generate_snapshots(
    start_date=date(2025, 1, 1),
    end_date=date(2025, 1, 31)
)
```

## Access Data

### Summary Metrics
```python
snapshot.total_system_inventory  # float
snapshot.total_in_transit        # float
snapshot.date                    # Date
```

### Location Inventory
```python
for loc_id, loc_inv in snapshot.location_inventory.items():
    print(loc_inv.location_name)
    print(loc_inv.total_quantity)
    print(loc_inv.by_product)  # Dict[str, float]

    for batch in loc_inv.batches:
        print(batch.batch_id, batch.quantity, batch.age_days)
```

### In-Transit
```python
for transit in snapshot.in_transit:
    print(transit.origin_id)
    print(transit.destination_id)
    print(transit.quantity)
    print(transit.days_in_transit)
    print(transit.expected_arrival_date)
```

### Production Activity
```python
for batch in snapshot.production_activity:
    print(batch.product_id)
    print(batch.quantity)
    print(batch.batch_id)
```

### Flows
```python
# Inflows
for flow in snapshot.inflows:
    if flow.flow_type == "production":
        print(f"Produced {flow.quantity} at {flow.location_id}")
    elif flow.flow_type == "arrival":
        print(f"Arrived {flow.quantity} from {flow.counterparty}")

# Outflows
for flow in snapshot.outflows:
    if flow.flow_type == "departure":
        print(f"Departed {flow.quantity} to {flow.counterparty}")
    elif flow.flow_type == "demand":
        print(f"Delivered {flow.quantity} at {flow.location_id}")
```

### Demand Satisfaction
```python
for demand in snapshot.demand_satisfied:
    print(demand.destination_id)
    print(demand.product_id)
    print(demand.demand_quantity)
    print(demand.supplied_quantity)
    print(demand.shortage_quantity)
    print(demand.fill_rate)        # 0.0 to 1.0
    print(demand.is_satisfied)     # bool
```

## Common Patterns

### Total Production on Date
```python
total = sum(b.quantity for b in snapshot.production_activity)
```

### Total Demand on Date
```python
total = sum(d.demand_quantity for d in snapshot.demand_satisfied)
```

### Fill Rate
```python
total_demand = sum(d.demand_quantity for d in snapshot.demand_satisfied)
total_supplied = sum(d.supplied_quantity for d in snapshot.demand_satisfied)
fill_rate = (total_supplied / total_demand) if total_demand > 0 else 1.0
```

### Find Shortages
```python
shortages = [d for d in snapshot.demand_satisfied if not d.is_satisfied]
```

### Inventory by Product
```python
by_product = {}
for loc_inv in snapshot.location_inventory.values():
    for product_id, qty in loc_inv.by_product.items():
        by_product[product_id] = by_product.get(product_id, 0) + qty
```

### Old Inventory (>10 days)
```python
old_batches = []
for loc_inv in snapshot.location_inventory.values():
    old_batches.extend([b for b in loc_inv.batches if b.age_days > 10])
```

## Data Classes

| Class | Key Attributes | Purpose |
|-------|---------------|---------|
| `BatchInventory` | batch_id, product_id, quantity, age_days | Single batch at location |
| `LocationInventory` | location_id, batches, total_quantity, by_product | Aggregated inventory |
| `TransitInventory` | origin_id, destination_id, days_in_transit | Shipment in transit |
| `InventoryFlow` | flow_type, location_id, quantity | Inventory movement |
| `DemandRecord` | demand_quantity, supplied_quantity, fill_rate | Demand vs. supply |
| `DailySnapshot` | date, location_inventory, in_transit, flows | Complete snapshot |

## Flow Types

- `"production"`: New batch produced
- `"arrival"`: Shipment arrived from another location
- `"departure"`: Shipment departed to another location
- `"demand"`: Delivery to customer

## Performance

| Operation | Complexity | Typical Time |
|-----------|-----------|--------------|
| Initialize | O(S) | <0.1s |
| Single snapshot | O(S + B) | <0.01s |
| Range (200 days) | O(D * S) | <2s |

Where: S = shipments, B = batches, D = dates

## Memory-Efficient Pattern

```python
# For large date ranges
from datetime import timedelta

current = start_date
while current <= end_date:
    snapshot = generator._generate_single_snapshot(current)
    process(snapshot)  # Process immediately
    current += timedelta(days=1)
```

## Export to DataFrame

```python
import pandas as pd

data = []
for snapshot in snapshots:
    for loc_id, loc_inv in snapshot.location_inventory.items():
        data.append({
            'date': snapshot.date,
            'location': loc_inv.location_name,
            'quantity': loc_inv.total_quantity
        })

df = pd.DataFrame(data)
```

## Error Handling

The module handles:
- Empty shipments list
- Missing batches
- No demand on date
- Rounding errors (0.01 tolerance)
- Missing locations (uses location_id as name)

## See Also

- `USAGE_EXAMPLE.md` - Comprehensive examples
- `README.md` - Full documentation
- `daily_snapshot.py` - Source code with docstrings
