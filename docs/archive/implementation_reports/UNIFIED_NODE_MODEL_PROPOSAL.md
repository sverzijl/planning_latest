# Unified Node Model - Proposal & Implementation Plan

## Executive Summary

**Proposal:** Simplify the model architecture by eliminating special-purpose location types (manufacturing/storage/breadroom) and virtual locations (6122_Storage). Replace with a unified node model where all locations are nodes with capabilities.

**Expected Benefits:**
- Eliminate 6122 vs 6122_Storage dual representation bugs
- Enable truck schedule constraints for ANY route (not just manufacturing-origin)
- Cleaner state transition logic
- More extensible for future enhancements
- Reduce model complexity and potential for bugs

---

## Current Model Architecture

### Location Types
- **Manufacturing (6122):** Produces product, has production capacity/labor
- **Storage (Lineage):** Intermediate storage only, no production or demand
- **Breadroom (6104, 6125, etc.):** End destinations with demand
- **Virtual (6122_Storage):** Artificial node for inventory tracking before truck loading

### Current Issues

**1. Dual Representation Problem:**
```
6122 (Real Manufacturing)
  ↓ (implicit transfer)
6122_Storage (Virtual)
  ↓ via truck schedules
Destinations
```
- Two sets of legs: `(6122, dest)` and `(6122_Storage, dest)`
- Truck constraints link to one set, inventory uses another
- Creates bypass routes that violate truck schedules
- Causes weekend shipping when trucks don't run

**2. Truck Schedule Limitations:**
- Only works for manufacturing-origin trucks
- Cannot constrain hub-to-spoke trucks (6125 → 6123)
- Hardcoded to `6122_Storage` inventory balance
- Not generalizable

**3. State Transition Complexity:**
- Scattered logic across constraints
- Automatic freeze/thaw rules
- Hard to extend or modify

**4. Inventory Tracking Issues:**
- Hub inventory disappearing (zero display bug)
- Complex cohort reachability logic
- Multiple code paths for same concept

---

## Proposed Unified Node Model

### Node Definition

```python
class Node:
    id: str
    name: str

    # Capabilities (all optional)
    can_manufacture: bool = False
    production_rate: float = None        # units/hour (if can_manufacture)

    can_store: bool = True               # Almost all nodes can store
    storage_mode: StorageMode            # FROZEN | AMBIENT | BOTH
    storage_capacity: float = None       # units (None = unlimited)

    has_demand: bool = False             # Is this a demand point?

    # Truck constraints (if applicable)
    has_truck_constraints: bool = False  # Do outbound shipments require trucks?
```

### Route Definition

```python
class Route:
    id: str
    origin_id: str
    destination_id: str
    transit_days: float                  # 0 = instant, 0.5 = half day, 1.0 = one day
    transport_mode: TransportMode        # FROZEN | AMBIENT
    cost_per_unit: float
```

### Truck Schedule (Generalized)

```python
class TruckSchedule:
    id: str
    origin_id: str                       # NEW: Can be ANY node (not just 6122)
    destination_id: str
    departure_type: str                  # morning | afternoon
    day_of_week: Optional[str]           # monday | tuesday | ... | None (daily)
    capacity: float
    intermediate_stops: List[str] = []
```

---

## State Transition Rules (Unified)

**On Arrival at Destination Node:**

| Product State | Dest Storage Mode | Result State | Shelf Life |
|---------------|-------------------|--------------|------------|
| Ambient | AMBIENT | Ambient | No change (continues aging) |
| Ambient | FROZEN | Frozen | Reset to 120 days |
| Frozen | FROZEN | Frozen | No change (continues aging) |
| Frozen | AMBIENT | Thawed | Reset to 14 days |

**On Production:**
- Frozen node → produces frozen (120-day shelf life)
- Ambient node → produces ambient (17-day shelf life)

**Single Rule:** Shelf life resets when product changes state (ambient→frozen, frozen→thawed)

---

## Current vs Proposed Model Comparison

### Inventory Balance Equation

**Current (Complex):**
```python
# Special case for 6122_Storage
if loc == '6122_Storage':
    inventory[t] = inventory[t-1] + production[t] - truck_loads[t]

# Different case for hubs with demand
elif loc in destinations and loc in locations_with_outbound_legs:
    inventory[t] = inventory[t-1] + arrivals[t] - demand[t] - departures[t]

# Different case for intermediate storage
elif loc in intermediate_storage:
    inventory[t] = inventory[t-1] + arrivals[t] - departures[t]
```

**Proposed (Unified):**
```python
# Same equation for ALL nodes
inventory[node, product, cohort, date] = (
    inventory[node, product, cohort, date-1] +
    production[node, product, date] if (cohort.prod_date == date) +  # Manufacturing capability
    arrivals_from_routes[node, product, cohort, date] +
    state_transition_inflows[node, product, cohort, date] -
    demand[node, product, cohort, date] -  # Demand capability
    departures_via_routes[node, product, cohort, date] -
    state_transition_outflows[node, product, cohort, date]
)
```

### Truck Constraints

**Current:**
- Hardcoded to 6122_Storage
- Cannot constrain hub trucks

**Proposed:**
```python
# For ANY route with truck schedules defined
if route.has_truck_schedules():
    shipment[route, product, date] == sum(
        truck_load[truck, route, product, date]
        for truck in trucks_serving_route
        if truck.operates_on_date(date)
    )
```

---

## Implementation Plan

### Phase 1: Create Baseline Tests (Test Current Model)

**Purpose:** Establish regression tests before making changes

**Tests to Create:**

1. **test_unified_model_baseline_1week.py**
   - 1-week horizon, no initial inventory
   - Assert: Solves optimally
   - Assert: Fill rate ≥ 95%
   - Assert: Hub inventory > 0 on weekends
   - Capture: Total cost, production schedule, shipments

2. **test_unified_model_baseline_2week.py**
   - 2-week horizon, no initial inventory
   - Same assertions as 1-week
   - Check: Weekend patterns across both weeks

3. **test_unified_model_baseline_4week.py**
   - 4-week horizon, no initial inventory
   - Same assertions
   - Performance: Solve time < 30s

4. **test_unified_model_baseline_with_initial_inventory.py**
   - 4-week horizon with initial inventory
   - Assert: Initial inventory properly consumed
   - Assert: Solves optimally

5. **test_unified_model_truck_constraints.py**
   - Verify trucks only run on scheduled days
   - Verify no weekend manufacturing outflows
   - Verify hub inventory accumulation on weekends

6. **test_unified_model_state_transitions.py**
   - Verify frozen product to ambient node → thaws (14 days)
   - Verify ambient product to frozen node → freezes (120 days)
   - Verify 6130 (WA) receives frozen and thaws properly

**Run ALL tests with current model - capture results as baseline.**

### Phase 2: Design New Unified Architecture

**2.1 New Data Models:**

```python
# src/models/unified_node.py
@dataclass
class NodeCapabilities:
    """Capabilities flags for a unified node."""
    can_manufacture: bool = False
    production_rate_per_hour: Optional[float] = None

    can_store: bool = True
    storage_mode: StorageMode = StorageMode.AMBIENT  # FROZEN | AMBIENT | BOTH
    storage_capacity: Optional[float] = None

    has_demand: bool = False

    # Truck constraints apply to outbound shipments from this node
    requires_truck_schedules: bool = False


@dataclass
class UnifiedNode:
    """Unified node representation - replaces Location/ManufacturingSite/etc."""
    id: str
    name: str
    capabilities: NodeCapabilities
    latitude: Optional[float] = None
    longitude: Optional[float] = None
```

**2.2 Modified Route Model:**

```python
# src/models/unified_route.py
@dataclass
class UnifiedRoute:
    """Route connecting two nodes."""
    id: str
    origin_node_id: str
    destination_node_id: str
    transit_days: float  # 0 = instant, 0.5 = half-day, 1.0 = one day
    transport_mode: TransportMode  # FROZEN | AMBIENT
    cost_per_unit: float
```

**2.3 Generalized Truck Schedules:**

```python
# src/models/unified_truck.py
@dataclass
class UnifiedTruckSchedule:
    """Truck schedule for ANY route (not just manufacturing-origin)."""
    id: str
    origin_node_id: str  # NEW: Can be 6122, 6125, 6104, etc.
    destination_node_id: str
    day_of_week: Optional[DayOfWeek]
    departure_type: DepartureType
    capacity: float
    intermediate_stops: List[str] = field(default_factory=list)
```

### Phase 3: Create New Unified Model

**File:** `src/optimization/unified_node_model.py`

**Key Design Elements:**

1. **Single Inventory Variable:**
   ```python
   # inventory[node, product, prod_date, curr_date, state]
   # state ∈ {frozen, ambient, thawed}
   ```

2. **State-Aware Routes:**
   ```python
   # shipment[(origin, dest), product, prod_date, delivery_date, arrival_state]
   # arrival_state determined by route.transport_mode + dest.storage_mode
   ```

3. **Unified Balance Constraint:**
   ```python
   for node in all_nodes:
       for state in node.supported_states():
           inventory[node, prod, cohort, date, state] = (
               prev_inventory +
               production_inflow +
               route_arrivals_in_this_state +
               state_transitions_to_this_state -
               demand_consumption -
               route_departures_from_this_state -
               state_transitions_from_this_state
           )
   ```

4. **Generalized Truck Constraints:**
   ```python
   for route in routes_with_trucks:
       for date in dates:
           shipment[route, prod, date] = sum(
               truck_load[truck, route, prod, date]
               for truck in route.applicable_trucks(date)
           )
   ```

### Phase 4: Migration Strategy

**4.1 Parallel Implementation:**
- Keep existing `IntegratedProductionDistributionModel` unchanged
- Build `UnifiedNodeModel` in parallel
- Both can coexist during development

**4.2 Data Conversion Layer:**
```python
# src/optimization/legacy_to_unified_converter.py
def convert_legacy_to_unified(
    manufacturing_site, locations, routes, truck_schedules
) -> Tuple[List[UnifiedNode], List[UnifiedRoute], List[UnifiedTruckSchedule]]:
    """Convert legacy data structures to unified model."""

    nodes = []

    # Convert manufacturing site
    nodes.append(UnifiedNode(
        id=manufacturing_site.id,
        name=manufacturing_site.name,
        capabilities=NodeCapabilities(
            can_manufacture=True,
            production_rate_per_hour=manufacturing_site.production_rate,
            storage_mode=manufacturing_site.storage_mode,
            requires_truck_schedules=True  # Manufacturing uses trucks
        )
    ))

    # Convert other locations
    for loc in locations:
        # Determine capabilities
        has_demand = loc.id in demand_locations

        nodes.append(UnifiedNode(
            id=loc.id,
            name=loc.name,
            capabilities=NodeCapabilities(
                can_manufacture=False,
                can_store=True,
                storage_mode=loc.storage_mode,
                has_demand=has_demand,
                requires_truck_schedules=False  # Hubs don't require trucks (yet)
            )
        ))

    # Routes remain mostly unchanged
    unified_routes = [convert_route(r) for r in routes]

    # Truck schedules: add origin_id (currently implicit as 6122)
    unified_trucks = []
    for truck in truck_schedules:
        unified_trucks.append(UnifiedTruckSchedule(
            id=truck.id,
            origin_node_id='6122',  # Currently all from manufacturing
            destination_node_id=truck.destination_id,
            day_of_week=truck.day_of_week,
            # ... other fields
        ))

    return nodes, unified_routes, unified_trucks
```

**4.3 Testing Strategy:**
- Run baseline tests with legacy model → capture results
- Run same tests with unified model → compare results
- Ensure identical or improved solutions

### Phase 5: Progressive Implementation

**Step 1: Build Unified Model Structure (No Solve)**
- Create UnifiedNode, UnifiedRoute, UnifiedTruckSchedule models
- Build conversion layer
- Test: Model builds without errors

**Step 2: Implement Core Constraints**
- Inventory balance (single unified equation)
- Production capacity
- Demand satisfaction
- Test: 1-week solves optimally

**Step 3: Add State Transitions**
- Freeze, thaw, state-dependent shelf life
- Test: Lineage→6130 frozen routing works

**Step 4: Add Truck Constraints**
- Generalized truck linking (works for any origin)
- Test: Day-of-week constraints enforced

**Step 5: Full Integration**
- All features working
- Run full test suite
- Compare with baseline

### Phase 6: UI Integration

**6.1 Update Excel Parser:**
- Add optional `capabilities` columns to Locations sheet
- Add `origin_node_id` column to TruckSchedules sheet
- Backward compatible with existing files

**6.2 Update UI:**
- Add model selector: "Legacy Model" vs "Unified Model"
- Both use same input files
- Compare results side-by-side

**6.3 Deprecation Path:**
- Phase 1-2: Both models available
- Phase 3: Unified model becomes default
- Phase 4: Remove legacy model (after validation period)

---

## Benefits Analysis

### 1. Eliminates 6122_Storage Bugs ✅
- **Current:** Dual representation causes bypass routes
- **Proposed:** Single node, no virtual locations needed
- **Impact:** Fixes weekend shipping bug, hub inventory bugs

### 2. Enables Hub Truck Constraints ✅
- **Current:** Can't define truck schedules from hubs
- **Proposed:** Truck schedules work for ANY node
- **Impact:** Can model 6125→6123 Monday-only trucks, etc.

### 3. Cleaner State Transitions ✅
- **Current:** Scattered automatic freeze/thaw logic
- **Proposed:** Single unified state transition rule
- **Impact:** Easier to understand, modify, and extend

### 4. Simpler Inventory Balance ✅
- **Current:** 3-4 different balance equations for different location types
- **Proposed:** Single equation for all nodes
- **Impact:** Less code, fewer bugs, easier maintenance

### 5. Better Extensibility ✅
- **Current:** Adding new location type requires model changes
- **Proposed:** Just add capabilities flags
- **Impact:** Future features easier to implement

### 6. Performance Impact ❓
- **Concern:** Might create more variables (separate frozen/ambient inventory at all nodes)
- **Mitigation:** Use sparse indexing (only create variables where needed)
- **Need to test:** Compare solve times current vs unified

---

## Risks & Mitigation

### Risk 1: Breaking Changes
**Risk:** New model might not match existing solutions
**Mitigation:**
- Build comprehensive baseline tests first
- Run both models in parallel during transition
- Validate identical results before switching

### Risk 2: Performance Degradation
**Risk:** More flexibility might mean more variables
**Mitigation:**
- Use sparse cohort indexing (only valid states)
- Benchmark solve times at each step
- Optimize if needed

### Risk 3: Development Time
**Risk:** Major refactor takes significant time
**Mitigation:**
- Incremental implementation with tests at each step
- Keep legacy model working during development
- Can abandon if issues arise

---

## Recommended Approach

### Option A: Full Unified Model (Recommended)
**Pros:**
- Cleanest architecture
- Fixes all current bugs
- Most extensible

**Cons:**
- Larger up-front effort
- Need careful testing

**Timeline:** 2-3 days development + 1-2 days testing

### Option B: Minimal Fix (Quick Fix)
**Pros:**
- Smaller change to current model
- Faster to implement

**Cons:**
- Doesn't address root cause
- Still has dual representation
- Limited extensibility

**Approach:** Add synchronization constraint between 6122 and 6122_Storage legs

**Timeline:** 1 day

### Option C: Hybrid Approach
**Pros:**
- Quick fix now (Option B)
- Plan for unified model later

**Cons:**
- Technical debt accumulates
- May still have bugs

---

## Decision Point

**Recommendation:** Proceed with **Option A (Full Unified Model)** because:

1. **Fixes root cause** - eliminates 6122/6122_Storage confusion permanently
2. **Enables future features** - hub truck constraints, multi-manufacturing sites, etc.
3. **Cleaner codebase** - easier to maintain and extend
4. **Current bugs severe** - dual legs causing weekend violations, hub inventory issues

**Test-Driven Development Approach:**
1. Write all baseline tests first (capture current behavior)
2. Implement unified model incrementally
3. Run tests after each step
4. Only proceed if tests pass
5. Can abort and revert if issues arise

**User can test in parallel:** Legacy model remains functional during development

---

## Next Steps

1. **Get user approval** for Option A vs B vs C
2. **If Option A approved:**
   - Create baseline test suite (6 tests)
   - Run and capture results
   - Begin unified model implementation
   - Track progress with frequent commits

3. **If Option B preferred:**
   - Debug synchronization constraint
   - Fix 4-week horizon issue
   - More limited solution

Would you like me to proceed with Option A (Unified Model) and create the baseline test suite?
