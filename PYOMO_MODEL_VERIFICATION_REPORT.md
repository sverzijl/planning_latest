# Pyomo Model Inventory Tracking Verification Report

## Executive Summary

**RESULT: MODEL IS CORRECT**

The Pyomo model in `/home/sverzijl/planning_latest/src/optimization/integrated_model.py` correctly tracks inventory at ALL relevant locations. The model properly creates inventory variables and balance constraints for every location that appears in the forecast data.

**Key Finding:** The "missing" locations (6107, 6115, 6118, 6122, 6127) are NOT in the actual forecast data being used. The model correctly tracks inventory ONLY for locations with demand or intermediate storage requirements.

## Verification Methodology

### Test Setup
- **Data Files:**
  - Network configuration: `/home/sverzijl/planning_latest/data/examples/Network_Config.xlsx`
  - Forecast data: `/home/sverzijl/planning_latest/data/examples/Gfree Forecast_Converted.xlsx`
- **Planning Horizon:** 2025-05-29 to 2025-12-22 (208 days)
- **Model Settings:** `allow_shortages=True`, `enforce_shelf_life=True`

### Verification Checklist

✅ **1. Inventory Location Set Creation**
- **Code:** Lines 221-223 in `integrated_model.py`
- **Logic:** `self.inventory_locations = self.destinations | self.intermediate_storage | {'6122_Storage'}`
- **Result:** CORRECT - Includes all demand locations + intermediate storage + virtual manufacturing storage

✅ **2. Inventory Variable Definition**
- **Code:** Lines 1052-1062 in `integrated_model.py`
- **Variables Created:**
  - `model.inventory_frozen[loc, prod, date]` - Frozen inventory (3 locations support frozen)
  - `model.inventory_ambient[loc, prod, date]` - Ambient inventory (10 locations support ambient)
- **Result:** CORRECT - Variables created for all locations in sparse index sets based on storage capabilities

✅ **3. Inventory Balance Constraints**
- **Code:** Lines 1271-1475 in `integrated_model.py`
- **Constraints:**
  - `inventory_frozen_balance_con` - Tracks frozen inventory (3 locations)
  - `inventory_ambient_balance_con` - Tracks ambient inventory (10 locations)
- **Result:** CORRECT - Balance equations properly model inventory flow at ALL tracked locations

## Detailed Analysis

### 1. Destination Locations (from Forecast)

The model tracks **9 breadroom destinations** that have demand in the forecast:

| Location ID | Name | Type | Storage Mode | Frozen Var | Ambient Var |
|-------------|------|------|--------------|------------|-------------|
| 6103 | QBA-Canberra | breadroom | ambient | ❌ | ✅ |
| 6104 | QBA-Moorebank (NSW Hub) | breadroom | ambient | ❌ | ✅ |
| 6105 | QBA-Rydalmere | breadroom | ambient | ❌ | ✅ |
| 6110 | QBA-Burleigh Heads | breadroom | ambient | ❌ | ✅ |
| 6120 | QBA-Hobart | breadroom | both | ✅ | ✅ |
| 6123 | QBA-Clayton-Fairbank | breadroom | ambient | ❌ | ✅ |
| 6125 | QBA-Keilor Park (VIC Hub) | breadroom | ambient | ❌ | ✅ |
| 6130 | QBA-Canning Vale (WA Thawing) | breadroom | both | ✅ | ✅ |
| 6134 | QBA-West Richmond SA | breadroom | ambient | ❌ | ✅ |

**Analysis:**
- All 9 destinations have ambient inventory variables (100% coverage)
- 2 locations (6120, 6130) support BOTH frozen and ambient storage
- Model correctly creates frozen variables only for locations that support frozen storage

### 2. Intermediate Storage Locations

| Location ID | Name | Type | Storage Mode | Frozen Var | Ambient Var |
|-------------|------|------|--------------|------------|-------------|
| Lineage | Lineage Frozen Storage | storage | frozen | ✅ | ❌ |

**Analysis:**
- Lineage frozen buffer is correctly tracked with frozen inventory variable
- No ambient variable (correct - Lineage only supports frozen storage)

### 3. Virtual Manufacturing Storage

| Location ID | Name | Frozen Var | Ambient Var |
|-------------|------|------------|-------------|
| 6122_Storage | Virtual manufacturing storage | ❌ | ✅ |

**Analysis:**
- Virtual location to track production → truck loading flow
- Only ambient storage (correct - production is always ambient)
- Special balance constraint (lines 1372-1409): `inventory = prev + production - truck_loads`

### 4. Manufacturing Site (6122)

**Important:** Location 6122 (Manufacturing Site) is NOT in `inventory_locations` and does NOT have inventory variables.

**Why is this correct?**
- Manufacturing site has separate production variables: `model.production[date, product]`
- Inventory tracking is handled by virtual location `6122_Storage`
- Production flows directly into 6122_Storage, trucks load from 6122_Storage
- This design separates production capacity from inventory management

### 5. "Missing" Locations Explanation

The following locations were NOT found in the model:

| Location ID | Status | Reason |
|-------------|--------|--------|
| 6107 | ❌ Not in data | Not present in forecast or network configuration |
| 6115 | ❌ Not in data | Not present in forecast or network configuration |
| 6118 | ❌ Not in data | Not present in forecast or network configuration |
| 6127 | ❌ Not in data | Not present in forecast or network configuration |

**Analysis:**
- These locations are NOT in the actual forecast data being used
- The model CORRECTLY excludes locations without demand
- This is optimal behavior (no unnecessary variables/constraints)

## Inventory Balance Constraint Logic Verification

### Frozen Inventory Balance (Lines 1271-1343)

```python
inventory_frozen[loc, prod, date] =
    prev_frozen
    + frozen_arrivals      # Shipments arriving in frozen state
    - frozen_outflows      # Shipments departing from intermediate storage
```

**Verification:**
- ✅ Correctly accumulates frozen arrivals from incoming routes
- ✅ Correctly deducts frozen outflows from intermediate storage (Lineage)
- ✅ No shelf life decay (120-day limit is generous)
- ✅ Does not satisfy demand directly (frozen must thaw first)

**Locations with frozen inventory:** 3
- Lineage (intermediate frozen buffer)
- 6120 (Hobart - supports frozen and ambient)
- 6130 (Canning Vale - receives frozen, thaws on-site)

### Ambient Inventory Balance (Lines 1346-1475)

**Standard locations (Lines 1411-1469):**
```python
inventory_ambient[loc, prod, date] =
    prev_ambient
    + ambient_arrivals     # Includes automatic thawing from frozen routes
    - demand_qty           # Demand satisfaction
    + shortage_qty         # Unsatisfied demand (if allowed)
    - ambient_outflows     # Shipments departing from hubs
```

**Special: 6122_Storage (Lines 1372-1409):**
```python
inventory_ambient[6122_Storage, prod, date] =
    prev_ambient
    + production[date, prod]         # Production on this date
    - truck_loads[departing on date] # Trucks loading from storage
```

**Verification:**
- ✅ Correctly accumulates ambient arrivals (including automatic thawing)
- ✅ Correctly deducts demand satisfaction
- ✅ Correctly handles shortage (unsatisfied demand adds back to inventory)
- ✅ Correctly deducts outflows from hub locations (6104, 6125)
- ✅ Special logic for 6122_Storage correctly links production → trucks

**Locations with ambient inventory:** 10
- All 9 breadroom destinations
- 1 virtual manufacturing storage (6122_Storage)

## Critical Location Checks

### Hub Location: 6104 (NSW/ACT Hub)

```
Location: 6104 (QBA-Moorebank (NSW Hub))
  Type: breadroom
  Storage mode: ambient
  ✅ In destinations: True
  ✅ In inventory_locations: True
  ✅ Has ambient variables: True
  ✅ Has ambient constraints: True
  ✅ Tracks incoming shipments from 6122
  ✅ Tracks outgoing shipments to spoke breadrooms
  ✅ Satisfies local demand (hub also consumes product)
```

**Verification:** CORRECT - Hub inventory fully tracked with inflows, outflows, and demand

### Hub Location: 6125 (VIC/TAS/SA Hub)

```
Location: 6125 (QBA-Keilor Park (VIC Hub))
  Type: breadroom
  Storage mode: ambient
  ✅ In destinations: True
  ✅ In inventory_locations: True
  ✅ Has ambient variables: True
  ✅ Has ambient constraints: True
  ✅ Tracks incoming shipments from 6122
  ✅ Tracks outgoing shipments to spoke breadrooms
  ✅ Satisfies local demand
```

**Verification:** CORRECT - Hub inventory fully tracked with inflows, outflows, and demand

### Thawing Location: 6130 (Cairns - WA Thawing)

```
Location: 6130 (QBA-Canning Vale (WA Thawing))
  Type: breadroom
  Storage mode: both
  ✅ In destinations: True
  ✅ In inventory_locations: True
  ✅ Has frozen variables: True
  ✅ Has ambient variables: True
  ✅ Has frozen constraints: True
  ✅ Has ambient constraints: True
  ✅ Receives frozen shipments (via Lineage frozen buffer)
  ✅ Automatic thawing on arrival (shelf life resets to 14 days)
```

**Verification:** CORRECT - Both frozen and ambient inventory tracked; automatic thawing handled

## Model Structure Summary

### Set Relationships

```
destinations (9 locations)
    ↓
    Set of locations with demand in forecast

intermediate_storage (1 location)
    ↓
    Set of LocationType.STORAGE not in destinations

inventory_locations = destinations ∪ intermediate_storage ∪ {'6122_Storage'}
    ↓
    (9 + 1 + 1 = 11 locations total)
```

### Variable Creation Logic

**Frozen inventory variables:**
```python
For each loc in inventory_locations:
    If loc supports frozen storage:
        Create inventory_frozen[loc, prod, date] for all products and dates
```

**Ambient inventory variables:**
```python
For each loc in inventory_locations:
    If loc supports ambient storage OR loc == '6122_Storage':
        Create inventory_ambient[loc, prod, date] for all products and dates
```

**Result:**
- Frozen variables: 3 locations × products × dates (sparse index)
- Ambient variables: 10 locations × products × dates (sparse index)

### Constraint Creation Logic

**Balance constraints created for:**
- Every (loc, prod, date) tuple in sparse index sets
- Frozen balance: 3 locations
- Ambient balance: 10 locations

## Code References

### Key Code Sections

1. **Inventory location set creation** (Lines 197-223)
   ```python
   self.destinations: Set[str] = {e.location_id for e in self.forecast.entries}
   self.intermediate_storage: Set[str] = {
       loc.id for loc in self.locations
       if loc.type == LocationType.STORAGE and loc.id not in self.destinations
   }
   self.inventory_locations: Set[str] = self.destinations | self.intermediate_storage | {'6122_Storage'}
   ```

2. **Sparse index set creation** (Lines 909-937)
   ```python
   for loc in self.inventory_locations:
       if loc == '6122_Storage':
           # Virtual storage: ambient only
           for prod in self.products:
               for date in sorted_dates:
                   self.inventory_ambient_index_set.add((loc, prod, date))
       else:
           loc_obj = self.location_by_id.get(loc)
           for prod in self.products:
               for date in sorted_dates:
                   if loc in self.locations_frozen_storage:
                       self.inventory_frozen_index_set.add((loc, prod, date))
                   if loc in self.locations_ambient_storage:
                       self.inventory_ambient_index_set.add((loc, prod, date))
   ```

3. **Inventory variables** (Lines 1052-1062)
   ```python
   model.inventory_frozen = Var(
       model.inventory_frozen_index,
       within=NonNegativeReals,
       doc="Frozen inventory at location by product and date (no shelf life decay)"
   )
   model.inventory_ambient = Var(
       model.inventory_ambient_index,
       within=NonNegativeReals,
       doc="Ambient/thawed inventory at location by product and date (subject to shelf life)"
   )
   ```

4. **Frozen balance constraint** (Lines 1271-1343)
   - Handles frozen arrivals and outflows
   - Used at: Lineage, 6120, 6130

5. **Ambient balance constraint** (Lines 1346-1475)
   - Standard logic: arrivals - demand + shortage - outflows
   - Special logic for 6122_Storage: production - truck loads
   - Used at: All 9 destinations + 6122_Storage

## Conclusion

### Findings

1. **Model Structure:** ✅ CORRECT
   - Inventory locations set properly includes all destinations + intermediate storage + virtual storage
   - No physical locations are missing from tracking

2. **Variable Creation:** ✅ CORRECT
   - Frozen variables created for all locations supporting frozen storage (3 locations)
   - Ambient variables created for all locations supporting ambient storage (10 locations)
   - Sparse indexing correctly optimizes model size

3. **Constraint Logic:** ✅ CORRECT
   - Frozen balance correctly tracks frozen inventory with no shelf life decay
   - Ambient balance correctly tracks ambient inventory with demand satisfaction
   - Special 6122_Storage constraint correctly links production to truck loading
   - Hub locations (6104, 6125) correctly track inflows, outflows, and demand
   - Thawing location (6130) correctly tracks both frozen and ambient states

4. **Coverage:** ✅ COMPLETE
   - All 9 demand locations have inventory tracking
   - All 1 intermediate storage location has inventory tracking
   - Virtual manufacturing storage (6122_Storage) has inventory tracking
   - Total: 11 locations tracked (10 physical + 1 virtual)

### Recommendation

**The Pyomo model inventory tracking is CORRECT and COMPLETE.**

The bug mentioned in the task description is NOT in the model structure. The model correctly tracks inventory at ALL relevant locations. Any issues with inventory data extraction or reporting must be in:

1. **Data extraction logic** - How solution values are retrieved from Pyomo variables
2. **Reporting/display logic** - How inventory is presented to users
3. **Solution parsing** - How variable values are interpreted after solve

**Next Steps:**
- Review data extraction code in solution retrieval functions
- Check daily snapshot feature implementation
- Verify variable value access patterns (sparse index handling)

### Model Design Strengths

1. **Sparse indexing** - Only creates variables for valid (location, storage_mode) combinations
2. **Explicit storage modes** - Separates frozen and ambient inventory with different constraints
3. **Virtual storage** - Clean separation between production and truck loading via 6122_Storage
4. **Hub support** - Correctly models 2-echelon network with hub inflows/outflows
5. **State transitions** - Automatic thawing handled by routing leg arrival state

## Verification Script

The complete verification script is saved at:
`/home/sverzijl/planning_latest/verify_model_inventory_locations.py`

To re-run verification:
```bash
/home/sverzijl/planning_latest/venv/bin/python verify_model_inventory_locations.py
```
