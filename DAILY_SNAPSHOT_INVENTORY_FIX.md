# Daily Snapshot Initial Inventory Fix

## Problem Summary

When users loaded inventory with a snapshot date (e.g., 08/10/2025), the Daily Snapshot tab showed:
1. Wrong start date (03/10/2025 instead of 08/10/2025)
2. Only manufacturing location (6122) visible
3. Inventory never decreased (stuck at 6122)
4. No outflows or in-transit shipments
5. Zero units supplied in demand satisfaction

**Root cause:** Initial inventory was NOT converted to ProductionBatch objects, so DailySnapshotGenerator couldn't track inventory movement through the network.

## Solution Implemented

### 1. Modified `/home/sverzijl/planning_latest/ui/utils/result_adapter.py`

**Changes:**

A) **Added `inventory_snapshot_date` parameter to `adapt_optimization_results()`** (line 23):
```python
def adapt_optimization_results(
    model: Any, 
    result: dict,
    inventory_snapshot_date: Optional[Date] = None  # NEW
) -> Optional[Dict[str, Any]]:
```

B) **Passed parameter to `_create_production_schedule()`** (line 45):
```python
production_schedule = _create_production_schedule(
    model, 
    solution,
    inventory_snapshot_date  # NEW
)
```

C) **Updated `_create_production_schedule()` signature** (line 68):
```python
def _create_production_schedule(
    model: Any, 
    solution: dict,
    inventory_snapshot_date: Optional[Date] = None  # NEW
) -> ProductionSchedule:
```

D) **Created virtual batches from initial inventory** (lines 77-92):
```python
# CREATE BATCHES FROM INITIAL INVENTORY
if hasattr(model, 'initial_inventory') and model.initial_inventory and inventory_snapshot_date:
    for (location_id, product_id), quantity in model.initial_inventory.items():
        if quantity > 0:
            # Create virtual batch for initial inventory
            # Use snapshot_date - 1 so inventory exists on snapshot_date
            batch = ProductionBatch(
                id=f"INIT-{location_id}-{product_id}",
                product_id=product_id,
                manufacturing_site_id=location_id,  # CRITICAL: Use actual location!
                production_date=inventory_snapshot_date - timedelta(days=1),
                quantity=quantity,
                labor_hours_used=0,  # Initial inventory has no labor cost
                production_cost=0,  # Initial inventory is sunk cost
            )
            batches.append(batch)
```

E) **Fixed schedule start date calculation** (lines 122-131):
```python
# Determine actual schedule start date
if inventory_snapshot_date:
    # Use inventory snapshot date as schedule start
    actual_start_date = inventory_snapshot_date
elif batches:
    # Use earliest production/batch date if no inventory
    actual_start_date = min(b.production_date for b in batches)
else:
    # Fallback to model start date
    actual_start_date = model.start_date
```

### 2. Modified `/home/sverzijl/planning_latest/ui/pages/3_Results.py`

**Changes:**

Updated `get_current_results()` function (lines 193-211) to retrieve and pass inventory snapshot date:

```python
def get_current_results():
    """Get results based on currently selected source."""
    if st.session_state.result_source == 'optimization':
        opt_results = session_state.get_optimization_results()

        # Get inventory snapshot date from session state
        inventory_snapshot_date = st.session_state.get('inventory_snapshot_date')  # NEW

        adapted_results = adapt_optimization_results(
            model=opt_results['model'],
            result=opt_results['result'],
            inventory_snapshot_date=inventory_snapshot_date  # NEW
        )
        if adapted_results is None:
            st.error("❌ Optimization results are not available.")
            st.stop()
        return adapted_results
    else:
        return session_state.get_planning_results()
```

### 3. Modified `/home/sverzijl/planning_latest/src/analysis/daily_snapshot.py`

**Changes:**

Updated `_calculate_location_inventory()` method (lines 399-403) to use batch's actual location:

**BEFORE:**
```python
# Start with all batches at manufacturing site on their production date
if location_id == self.production_schedule.manufacturing_site_id:
    for batch in self.production_schedule.production_batches:
        if batch.production_date <= snapshot_date:
            batch_quantities[batch.id] = batch.quantity
```

**AFTER:**
```python
# Start with batches at their ACTUAL location (from manufacturing_site_id field)
# This handles both regular production (always at manufacturing) and initial inventory (can be anywhere)
for batch in self.production_schedule.production_batches:
    if batch.manufacturing_site_id == location_id and batch.production_date <= snapshot_date:
        batch_quantities[batch.id] = batch.quantity
```

## How It Works

1. **Initial Inventory Loading**: When user loads inventory file with snapshot date (e.g., 08/10/2025), session state stores both `initial_inventory` dict and `inventory_snapshot_date`.

2. **Batch Creation**: When optimization results are adapted, the adapter now:
   - Creates virtual ProductionBatch objects for initial inventory
   - Sets `manufacturing_site_id` to the ACTUAL location (not just 6122)
   - Sets `production_date` to snapshot_date - 1 day
   - Sets costs to 0 (sunk cost)

3. **Inventory Tracking**: DailySnapshotGenerator now:
   - Places each batch at its correct initial location (via `manufacturing_site_id`)
   - Tracks batch movement through shipments
   - Correctly shows inventory at multiple locations
   - Shows outflows when shipments depart
   - Shows in-transit when shipments are moving
   - Shows demand satisfaction when deliveries arrive

## Benefits

- **Correct start date**: Date range now starts at inventory snapshot date (08/10/2025)
- **Multiple locations visible**: Shows inventory at all locations (6104, 6125, 6130, etc.)
- **Inventory movement**: Inventory decreases as shipments depart and increases as they arrive
- **Outflows tracked**: Shows departures from all locations
- **In-transit visible**: Shows shipments moving through network
- **Demand satisfaction**: Shows actual units supplied to destinations

## Backwards Compatibility

All changes are backwards compatible:
- `inventory_snapshot_date` parameter is optional (defaults to None)
- When None, behavior is unchanged (uses model.start_date)
- Works with or without initial inventory
- No changes to existing heuristic planning flow

## Testing Recommendations

1. Load inventory file with snapshot date 08/10/2025
2. Run optimization with initial inventory
3. View Results > Daily Snapshot tab
4. Verify:
   - Date range starts at 08/10/2025
   - Multiple locations show inventory
   - Inventory decreases over time
   - Outflows show shipment departures
   - In-transit shows moving shipments
   - Demand satisfaction shows non-zero supplied units

## Files Modified

1. `/home/sverzijl/planning_latest/ui/utils/result_adapter.py`
2. `/home/sverzijl/planning_latest/ui/pages/3_Results.py`
3. `/home/sverzijl/planning_latest/src/analysis/daily_snapshot.py`

All files validated with `python3 -m py_compile` - no syntax errors.

## Visual Flow Diagram

### BEFORE (Broken):
```
Initial Inventory Load:
  {(6104, "WW"): 5000, (6125, "WW"): 3000}
  ↓
Optimization Model:
  Uses initial_inventory dict internally
  ↓
Result Adapter:
  Creates ONLY production batches from solution
  (Initial inventory NOT converted to batches)
  ↓
DailySnapshotGenerator:
  Looks for batches at manufacturing site (6122) only
  Can't find inventory at 6104 or 6125
  Result: WRONG - Shows 0 inventory at all locations
```

### AFTER (Fixed):
```
Initial Inventory Load:
  {(6104, "WW"): 5000, (6125, "WW"): 3000}
  snapshot_date = 2025-10-08
  ↓
Optimization Model:
  Uses initial_inventory dict internally
  ↓
Result Adapter:
  1. Creates virtual batches for initial inventory:
     - INIT-6104-WW: 5000 units at location 6104, date 2025-10-07
     - INIT-6125-WW: 3000 units at location 6125, date 2025-10-07
  2. Creates production batches from solution
  3. Sets schedule_start_date = 2025-10-08
  ↓
DailySnapshotGenerator:
  Looks for batches at EACH location using manufacturing_site_id
  Finds INIT-6104-WW at location 6104
  Finds INIT-6125-WW at location 6125
  Tracks movement through shipments
  Result: CORRECT - Shows inventory at all locations, tracks movement
```

## Code Flow Detail

```
User Action: Upload inventory with snapshot date
  ↓
session_state.store_parsed_data(
  initial_inventory={(6104, "WW"): 5000, (6125, "WW"): 3000},
  inventory_snapshot_date=date(2025, 10, 8)
)
  ↓
User Action: Run Optimization
  ↓
IntegratedProductionDistributionModel.build_model()
  Uses initial_inventory as constraint
  ↓
User Action: View Results > Daily Snapshot
  ↓
get_current_results()
  inventory_snapshot_date = st.session_state.get('inventory_snapshot_date')
  ↓
adapt_optimization_results(model, result, inventory_snapshot_date)
  ↓
_create_production_schedule(model, solution, inventory_snapshot_date)
  
  # NEW CODE: Create virtual batches for initial inventory
  for (location_id, product_id), quantity in model.initial_inventory.items():
    batch = ProductionBatch(
      id=f"INIT-{location_id}-{product_id}",
      manufacturing_site_id=location_id,  # ← KEY FIX
      production_date=inventory_snapshot_date - timedelta(days=1),
      quantity=quantity
    )
    batches.append(batch)
  
  # Set correct start date
  actual_start_date = inventory_snapshot_date  # ← KEY FIX
  ↓
DailySnapshotGenerator._calculate_location_inventory(location_id, snapshot_date)
  
  # NEW CODE: Use batch's actual location
  for batch in production_batches:
    if batch.manufacturing_site_id == location_id:  # ← KEY FIX
      batch_quantities[batch.id] = batch.quantity
  
  # Then track movement through shipments...
  ↓
Result: Inventory correctly displayed at all locations
```

## Key Insights

1. **ProductionBatch is the tracking unit**: The entire system tracks inventory using ProductionBatch objects, not raw dictionaries.

2. **manufacturing_site_id is the location field**: Despite the name, this field indicates WHERE the batch currently is, not just where it was produced.

3. **Initial inventory = virtual production**: We treat initial inventory as if it was "produced" one day before the snapshot date, creating virtual batches.

4. **Sunk costs**: Initial inventory has zero labor cost and production cost because it's already paid for.

5. **Date arithmetic**: Using `snapshot_date - 1` for production_date ensures the inventory "exists" on the snapshot date when the generator looks for batches with `production_date <= snapshot_date`.

