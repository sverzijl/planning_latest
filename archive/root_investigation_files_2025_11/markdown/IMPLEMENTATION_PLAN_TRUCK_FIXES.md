# Implementation Plan: Truck Schedule & Intermediate Stop Fixes

## Two Critical Bugs to Fix

### Bug 1: Intermediate Stops Ignored
- Lineage receives no shipments
- Wednesday truck (6122 → Lineage → 6125) skips Lineage
- 6130 (WA) has shortages

### Bug 2: Day-of-Week Not Enforced
- Shipments happen on wrong days
- Example: 6110 shipments on Monday (should only be Tue/Thu)
- in_transit variables created for all days

## Unified Solution

Both bugs stem from how routes and shipments are created. Fix together with comprehensive approach.

## Implementation Steps

### Step 1: Expand Intermediate Stops into Route Legs

**Location:** `src/optimization/legacy_to_unified_converter.py`

Add method to expand truck routes with intermediate stops:

```python
def expand_truck_intermediate_stops(
    self,
    truck_schedules: List[UnifiedTruckSchedule],
    routes: List[UnifiedRoute]
) -> List[UnifiedRoute]:
    """Expand truck routes with intermediate stops into explicit route legs.

    Example:
        Truck: 6122 → [Lineage] → 6125
        Creates routes:
            - 6122 → Lineage (leg 1)
            - Lineage → 6125 (leg 2)

    Returns:
        Extended route list with intermediate legs added
    """
    extended_routes = routes.copy()
    routes_added = []

    for truck in truck_schedules:
        if not truck.intermediate_stops:
            continue

        # Build full path
        path = [truck.origin_node_id] + truck.intermediate_stops + [truck.destination_node_id]

        # Create route for each leg
        for i in range(len(path) - 1):
            origin = path[i]
            dest = path[i + 1]

            # Check if route already exists
            existing = any(r for r in extended_routes
                          if r.origin_node_id == origin and r.destination_node_id == dest)

            if existing:
                continue  # Route exists, no need to create

            # Find original route properties or use defaults
            # For intermediate legs, inherit from full route if possible
            full_route = next((r for r in routes
                              if r.origin_node_id == truck.origin_node_id
                              and r.destination_node_id == truck.destination_node_id), None)

            # Create new route for this leg
            new_route = UnifiedRoute(
                origin_node_id=origin,
                destination_node_id=dest,
                transit_days=1.0,  # Default 1 day for intermediate legs
                transport_mode=TransportMode.AMBIENT,  # Will be overridden by freeze at Lineage
                cost_per_unit=0.0  # No additional cost for intermediate transfer
            )

            extended_routes.append(new_route)
            routes_added.append(f"{origin} → {dest}")

    if routes_added:
        print(f"  Expanded {len(routes_added)} intermediate stop routes:")
        for route in routes_added:
            print(f"    - {route}")

    return extended_routes
```

### Step 2: Build Truck-Route-Day Mapping

**Location:** `src/optimization/sliding_window_model.py` (in __init__)

Create mapping of which routes can be used on which days:

```python
def _build_truck_route_day_mapping(self):
    """Build mapping of (origin, dest) → valid departure days.

    Returns:
        Dict[(origin_id, dest_id), Set[day_of_week_name]]
    """
    truck_route_days = {}

    day_map = {
        0: 'monday', 1: 'tuesday', 2: 'wednesday', 3: 'thursday',
        4: 'friday', 5: 'saturday', 6: 'sunday'
    }

    for truck in self.truck_schedules:
        # Build path including intermediate stops
        path_nodes = [truck.origin_node_id]
        if truck.intermediate_stops:
            path_nodes.extend(truck.intermediate_stops)
        path_nodes.append(truck.destination_node_id)

        # Each leg in the path can be used on this truck's day
        for i in range(len(path_nodes) - 1):
            origin = path_nodes[i]
            dest = path_nodes[i + 1]
            route_key = (origin, dest)

            if route_key not in truck_route_days:
                truck_route_days[route_key] = set()

            if truck.day_of_week:
                # Specific day
                truck_route_days[route_key].add(truck.day_of_week.value)
            else:
                # Runs every day
                truck_route_days[route_key].update(day_map.values())

    return truck_route_days
```

### Step 3: Restrict in_transit Variable Creation

**Location:** `src/optimization/sliding_window_model.py` (lines 522-536)

Modify to only create variables for valid route-day combinations:

```python
# Build truck-route-day mapping
truck_route_days = self._build_truck_route_day_mapping()

day_of_week_map = {
    0: 'monday', 1: 'tuesday', 2: 'wednesday', 3: 'thursday',
    4: 'friday', 5: 'saturday', 6: 'sunday'
}

in_transit_index = []
skipped_combinations = 0

for route in self.routes:
    route_key = (route.origin_node_id, route.destination_node_id)
    valid_days = truck_route_days.get(route_key, set())

    if not valid_days:
        # No truck for this route - skip entirely
        skipped_combinations += len(model.dates) * len(model.products) * 2
        continue

    for prod in model.products:
        for departure_date in model.dates:
            # Check if truck runs on this day
            day_name = day_of_week_map[departure_date.weekday()]

            if day_name not in valid_days:
                skipped_combinations += 2  # 2 states
                continue  # No truck on this day

            # Truck available - create variables
            for state in ['frozen', 'ambient']:
                in_transit_index.append((
                    route.origin_node_id,
                    route.destination_node_id,
                    prod,
                    departure_date,
                    state
                ))

print(f"  In-transit variables: {len(in_transit_index)} (day-of-week enforced)")
if skipped_combinations > 0:
    print(f"  Skipped {skipped_combinations} invalid route-day combinations")
```

### Step 4: Handle Freeze at Lineage

**Location:** `src/optimization/sliding_window_model.py` (in state balance)

Ensure freeze flow is created at Lineage for ambient arrivals:

```python
# In _add_variables for freeze variables:
freeze_index = []
for node_id, node in self.nodes.items():
    if node.capabilities.can_store and 'frozen' in node.capabilities.storage_modes:
        # Can freeze goods at this node
        for prod in model.products:
            for t in model.dates:
                freeze_index.append((node_id, prod, t))

model.freeze = Var(freeze_index, within=NonNegativeReals, doc="Freeze flow: ambient → frozen")
```

Lineage should have:
- Ambient arrivals from 6122
- Freeze capability (ambient → frozen)
- Frozen departures to 6130

## Expected Results After Fix

### Monday Shipments (Corrected)
- 6122 → 6125: ✓ (morning truck)
- 6122 → 6104: ✓ (afternoon truck)
- 6122 → 6110: ✗ (no truck on Monday)

### Wednesday Shipments (Lineage Working)
- 6122 → Lineage: ✓ (intermediate stop, ambient)
- Lineage: Freeze operation (ambient → frozen)
- Lineage → 6130: ✓ (frozen, 7-day transit)
- Lineage → 6125: ✓ (continuation from intermediate stop)

### 6130 (WA) Demand
- Can now receive frozen goods from Lineage
- Shortages eliminated
- Full network path working

## Testing Plan

### Test 1: Truck Day Enforcement
```python
# Solve for Monday
# Verify shipments:
assert has_shipment(6122, 6125, monday)  # Morning truck
assert has_shipment(6122, 6104, monday)  # Afternoon truck
assert not has_shipment(6122, 6110, monday)  # No truck!
```

### Test 2: Lineage Intermediate Stop
```python
# Solve for Wednesday
# Verify shipments:
assert has_shipment(6122, 'Lineage', wednesday)  # Intermediate stop
assert has_shipment('Lineage', 6125, wednesday)  # Continuation
assert inventory['Lineage'] > 6400  # Received new goods
```

### Test 3: WA Demand Satisfaction
```python
# Check 6130 deliveries
assert fill_rate_6130 > 0.95  # High fill rate
assert shortages_6130 < 100  # Minimal shortages
```

## Complexity Estimate

- **Lines to change:** ~100-150
- **New functions:** 2 (expand_intermediate_stops, _build_truck_route_day_mapping)
- **Modified sections:** in_transit creation, truck constraints
- **Testing:** 3 new test cases

## Risk Assessment

**High impact change:**
- Modifies core shipment variable creation
- Changes model structure significantly
- Must ensure all existing functionality preserved

**Mitigation:**
- Implement incrementally
- Test each step
- Keep existing tests passing
- Add new tests for truck enforcement

## Sign-off

**Bugs Identified:** Truck day-of-week + Intermediate stops
**Plan Created:** November 4, 2025
**Ready for Implementation:** Yes
**Estimated Time:** 30-45 minutes
