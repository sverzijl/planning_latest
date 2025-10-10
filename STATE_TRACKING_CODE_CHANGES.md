# State Tracking Code Changes - Detailed Implementation

## Summary

This document outlines the exact code changes needed to implement frozen/ambient state tracking in `integrated_model.py`. The implementation is complex and touches many parts of the model.

**Estimated Changes:** ~200 lines modified across 5 major sections

## Section 1: Data Extraction (_extract_data method, ~line 186)

### Add Location Storage Mode Tracking

**After line 199 (destinations extraction), add:**

```python
# Create location lookup dictionary
self.location_by_id: Dict[str, Location] = {loc.id: loc for loc in self.locations}

# Categorize locations by storage capability
self.locations_frozen_storage: Set[str] = {
    loc.id for loc in self.locations
    if loc.storage_mode in [StorageMode.FROZEN, StorageMode.BOTH]
}
self.locations_ambient_storage: Set[str] = {
    loc.id for loc in self.locations
    if loc.storage_mode in [StorageMode.AMBIENT, StorageMode.BOTH]
}

# Identify intermediate storage locations (storage type, no demand)
self.intermediate_storage: Set[str] = {
    loc.id for loc in self.locations
    if loc.type == LocationType.STORAGE and loc.id not in self.destinations
}

# All locations that need inventory tracking (destinations + intermediate)
self.inventory_locations: Set[str] = self.destinations | self.intermediate_storage
```

### Determine Arrival State for Each Route

**After route enumeration (~line 430), add:**

```python
# Determine arrival state for each route
# frozen route + frozen-only destination → frozen
# anything else → ambient (thaws if needed)
self.route_arrival_state: Dict[int, str] = {}  # route_index -> 'frozen' or 'ambient'

for route in self.enumerated_routes:
    dest_loc = self.location_by_id.get(route.destination_id)

    # Check if route is frozen throughout
    is_frozen_route = self._is_frozen_route(route)

    # Determine arrival state
    if is_frozen_route and dest_loc and dest_loc.storage_mode == StorageMode.FROZEN:
        # Frozen route to frozen-only storage → stays frozen
        self.route_arrival_state[route.index] = 'frozen'
    else:
        # Everything else arrives as ambient
        # (thaws if frozen route to non-frozen destination)
        self.route_arrival_state[route.index] = 'ambient'
```

## Section 2: Variable Creation (_create_variables method, ~line 750)

### Replace Single Inventory Variable with State-Specific Variables

**Current code (~line 759-834):**
```python
# Create sparse index set for inventory variables
self.inventory_index_set = set()
for (dest, prod, date) in self.demand.keys():
    for d in sorted_dates:
        self.inventory_index_set.add((dest, prod, d))

model.inventory_index = list(self.inventory_index_set)

# Decision variables: inventory[dest, product, date]
model.inventory = Var(
    model.inventory_index,
    within=NonNegativeReals,
    doc="Inventory at destination by product and date"
)
```

**Replace with:**
```python
# Create sparse index sets for state-specific inventory variables
# Include both demand locations and intermediate storage
self.inventory_frozen_index_set = set()
self.inventory_ambient_index_set = set()

for loc in self.inventory_locations:
    loc_obj = self.location_by_id.get(loc)
    if not loc_obj:
        continue

    for prod in self.products:
        for date in sorted_dates:
            # Add frozen inventory if location supports frozen storage
            if loc in self.locations_frozen_storage:
                self.inventory_frozen_index_set.add((loc, prod, date))

            # Add ambient inventory if location supports ambient storage
            if loc in self.locations_ambient_storage:
                self.inventory_ambient_index_set.add((loc, prod, date))

model.inventory_frozen_index = list(self.inventory_frozen_index_set)
model.inventory_ambient_index = list(self.inventory_ambient_index_set)

# Decision variables: inventory_frozen[loc, product, date]
model.inventory_frozen = Var(
    model.inventory_frozen_index,
    within=NonNegativeReals,
    doc="Frozen inventory at location by product and date"
)

# Decision variables: inventory_ambient[loc, product, date]
model.inventory_ambient = Var(
    model.inventory_ambient_index,
    within=NonNegativeReals,
    doc="Ambient/thawed inventory at location by product and date"
)
```

## Section 3: Inventory Balance Constraints (~line 1004)

### Replace Single Inventory Balance with State-Specific Balances

**Current constraint (~line 1013-1079):**
```python
def inventory_balance_rule(model, dest, prod, date):
    # Single inventory balance
    ...
```

**Replace with TWO constraints:**

```python
def inventory_frozen_balance_rule(model, loc, prod, date):
    """
    Frozen inventory balance at location.

    frozen_inv[t] = frozen_inv[t-1] + frozen_arrivals[t] - frozen_outflows[t]

    Frozen inventory:
    - Increases from frozen route arrivals
    - Decreases from outbound shipments on frozen routes
    - Does NOT satisfy demand directly (must thaw first)
    """
    # Get routes delivering frozen to this location
    routes_frozen_arrival = [
        r for r in self.routes_to_destination.get(loc, [])
        if self.route_arrival_state.get(r) == 'frozen'
    ]

    # Frozen arrivals
    frozen_arrivals = sum(
        model.shipment[r, prod, date]
        for r in routes_frozen_arrival
    )

    # Frozen outflows (shipments departing from this location)
    # For intermediate storage like Lineage
    frozen_outflows = 0
    if loc in self.intermediate_storage:
        routes_from_loc = [
            r for r in range(len(self.enumerated_routes))
            if self.enumerated_routes[r].origin_id == loc
        ]
        # Calculate production date needed for each outbound shipment
        for r in routes_from_loc:
            route = self.enumerated_routes[r]
            prod_date = date - timedelta(days=int(route.total_transit_days))
            if prod_date in self.production_dates:
                frozen_outflows += model.shipment[r, prod, prod_date]

    # Previous frozen inventory
    prev_date = self.date_previous.get(date)
    if prev_date is None:
        prev_frozen = self.initial_inventory.get((loc, prod, 'frozen'), 0)
    else:
        if (loc, prod, prev_date) in self.inventory_frozen_index_set:
            prev_frozen = model.inventory_frozen[loc, prod, prev_date]
        else:
            prev_frozen = 0

    # Balance equation
    return model.inventory_frozen[loc, prod, date] == (
        prev_frozen + frozen_arrivals - frozen_outflows
    )

model.inventory_frozen_balance_con = Constraint(
    model.inventory_frozen_index,
    rule=inventory_frozen_balance_rule,
    doc="Frozen inventory balance at locations"
)

def inventory_ambient_balance_rule(model, loc, prod, date):
    """
    Ambient inventory balance at location.

    ambient_inv[t] = ambient_inv[t-1] + ambient_arrivals[t] - demand[t] - shortage[t]

    Ambient inventory:
    - Increases from ambient route arrivals (including thawed from frozen routes)
    - Decreases from demand satisfaction
    - Subject to shelf life constraints
    """
    # Get routes delivering ambient to this location
    routes_ambient_arrival = [
        r for r in self.routes_to_destination.get(loc, [])
        if self.route_arrival_state.get(r) == 'ambient'
    ]

    # Ambient arrivals (includes automatic thawing)
    ambient_arrivals = sum(
        model.shipment[r, prod, date]
        for r in routes_ambient_arrival
    )

    # Demand on this date (0 if no demand or intermediate storage)
    demand_qty = self.demand.get((loc, prod, date), 0.0)

    # Shortage
    shortage_qty = 0
    if self.allow_shortages and (loc, prod, date) in self.demand:
        shortage_qty = model.shortage[loc, prod, date]

    # Previous ambient inventory
    prev_date = self.date_previous.get(date)
    if prev_date is None:
        prev_ambient = self.initial_inventory.get((loc, prod, 'ambient'), 0)
    else:
        if (loc, prod, prev_date) in self.inventory_ambient_index_set:
            prev_ambient = model.inventory_ambient[loc, prod, prev_date]
        else:
            prev_ambient = 0

    # Balance equation
    return model.inventory_ambient[loc, prod, date] == (
        prev_ambient + ambient_arrivals - demand_qty - shortage_qty
    )

model.inventory_ambient_balance_con = Constraint(
    model.inventory_ambient_index,
    rule=inventory_ambient_balance_rule,
    doc="Ambient inventory balance at locations"
)
```

## Section 4: Objective Function (~line 1420)

### Update Inventory Holding Cost

**Current code (~line 1434-1445):**
```python
# Inventory holding costs
for dest in self.destinations:
    for prod in self.products:
        for date in sorted_dates:
            if (dest, prod, date) in self.inventory_index_set:
                # Uses ambient storage rate
                holding_cost_per_unit_day = self.cost_structure.inventory_holding_cost_per_unit_day or 0.0
                inventory_cost += holding_cost_per_unit_day * model.inventory[dest, prod, date]
```

**Replace with:**
```python
# Inventory holding costs (state-specific rates)
frozen_holding_rate = self.cost_structure.frozen_holding_cost_per_unit_day or 0.0
ambient_holding_rate = self.cost_structure.inventory_holding_cost_per_unit_day or 0.0

for loc in self.inventory_locations:
    for prod in self.products:
        for date in sorted_dates:
            # Frozen inventory holding cost
            if (loc, prod, date) in self.inventory_frozen_index_set:
                inventory_cost += frozen_holding_rate * model.inventory_frozen[loc, prod, date]

            # Ambient inventory holding cost
            if (loc, prod, date) in self.inventory_ambient_index_set:
                inventory_cost += ambient_holding_rate * model.inventory_ambient[loc, prod, date]
```

## Section 5: Solution Extraction (~line 1550)

### Update to Extract State-Specific Inventory

**Current code (~line 1574-1580):**
```python
# Extract ending inventory
ending_inventory = {}
for dest in self.destinations:
    for prod in self.products:
        if (dest, prod, self.end_date) in self.inventory_index_set:
            qty = value(model.inventory[dest, prod, self.end_date])
            if qty > 0.01:
                ending_inventory[(dest, prod)] = qty
```

**Replace with:**
```python
# Extract ending inventory (state-specific)
ending_inventory_frozen = {}
ending_inventory_ambient = {}

for loc in self.inventory_locations:
    for prod in self.products:
        # Frozen inventory
        if (loc, prod, self.end_date) in self.inventory_frozen_index_set:
            qty = value(model.inventory_frozen[loc, prod, self.end_date])
            if qty > 0.01:
                ending_inventory_frozen[(loc, prod)] = qty

        # Ambient inventory
        if (loc, prod, self.end_date) in self.inventory_ambient_index_set:
            qty = value(model.inventory_ambient[loc, prod, self.end_date])
            if qty > 0.01:
                ending_inventory_ambient[(loc, prod)] = qty

# Combine for backward compatibility
ending_inventory = {}
for key, qty in ending_inventory_frozen.items():
    ending_inventory[key] = {'frozen': qty, 'ambient': 0}
for key, qty in ending_inventory_ambient.items():
    if key in ending_inventory:
        ending_inventory[key]['ambient'] = qty
    else:
        ending_inventory[key] = {'frozen': 0, 'ambient': qty}
```

## Additional Changes Needed

### Import StorageMode enum
**At top of file (~line 10):**
```python
from src.models.location import Location, LocationType, StorageMode
```

### Update CostStructure (if needed)
If `frozen_holding_cost_per_unit_day` doesn't exist in CostStructure model, add it or default to same as ambient.

## Testing Approach

1. **Verify model builds** without errors
2. **Test with current data** - should produce same or better results
3. **Verify Lineage inventory** - check frozen inventory accumulates at Lineage
4. **Verify 6130 thawing** - check product arrives as ambient (thawed) at 6130
5. **Compare costs** - new model should have same or lower cost (frozen buffer value)

## Complexity Assessment

**Total Changes:**
- ~50 lines in data extraction
- ~40 lines in variable creation
- ~120 lines in constraints
- ~20 lines in objective
- ~30 lines in solution extraction
- **Total: ~260 lines of code changes**

**Risk Level:** HIGH - touches core model logic
**Recommendation:** Implement incrementally with testing at each step

## Implementation Order

1. ✅ Data extraction (location categorization)
2. ✅ Variable creation (state-specific inventory)
3. Test model builds
4. ✅ Frozen inventory balance constraint
5. Test frozen balance
6. ✅ Ambient inventory balance constraint
7. Test ambient balance
8. ✅ Objective function update
9. ✅ Solution extraction update
10. Full integration test

Would you like me to proceed with implementing these changes, or would you prefer to review this plan first?
