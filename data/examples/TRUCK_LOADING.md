# Truck Loading Module

Complete guide to the truck loading system for production-distribution planning.

## Table of Contents

1. [Overview](#overview)
2. [Key Concepts](#key-concepts)
3. [Data Models](#data-models)
4. [Components](#components)
5. [Business Rules](#business-rules)
6. [Usage Examples](#usage-examples)
7. [API Reference](#api-reference)

---

## Overview

The truck loading module converts production schedules into truck load plans by:

1. **Expanding production batches into individual shipments** (one per destination)
2. **Assigning shipments to specific truck departures** based on timing and destination
3. **Enforcing capacity constraints** (units and pallets)
4. **Managing D-1 vs D0 production timing** for truck departure compatibility

**Purpose:** Bridge production planning and distribution execution by creating detailed truck loading plans that respect manufacturing timing, truck schedules, and capacity constraints.

**Module Location:** `src/distribution/`

**Key Files:**
- `src/models/shipment.py` - Shipment data model
- `src/distribution/shipment_planner.py` - Shipment planning logic
- `src/distribution/truck_loader.py` - Truck loading logic

---

## Key Concepts

### D-1 vs D0 Production

**Critical Concept:** Truck loading depends on when production occurs relative to truck departure.

- **D-1 Production:** Batch produced the day **before** truck departs
  - Example: Produce Monday → Truck departs Tuesday (D-1)
  - Available for **all trucks** (morning and afternoon)

- **D0 Production:** Batch produced the **same day** as truck departs
  - Example: Produce Tuesday → Truck departs Tuesday (D0)
  - Only available for **afternoon trucks** (if ready before departure)
  - Morning trucks cannot load D0 production (not ready in time)

**Business Rule:**
- Morning trucks: **D-1 only**
- Afternoon trucks: **D-1 or D0** (prefer D-1)

### Destination Matching

**Shipments are assigned to trucks based on first leg destination.**

Example routing:
- Shipment to 6103 (VIC): Route 6122 → 6125 → 6103
- First leg: 6122 → 6125
- **Shipment goes on trucks destined for 6125**

**Why First Leg?**
- Trucks depart from manufacturing (6122) to regional hubs
- Hub determines which spoke destinations can be served
- First leg destination = truck's destination

### Capacity Constraints

**Truck capacity limits:**
- **Units:** 14,080 units per truck (1400 units/hour × 10 hours average)
- **Pallets:** 44 pallets per truck (standard trailer capacity)
- **Packaging:** 320 units per pallet (32 cases × 10 units/case)

**Critical Rule: Partial pallets occupy full pallet space**
- 1 unit = 1 pallet space
- 319 units = 1 pallet space
- 320 units = 1 pallet space
- 640 units = 2 pallet spaces

**Optimization Target:** Minimize partial pallets by batching in 320-unit increments.

### Truck Departure Schedule

**Morning Truck (Daily Monday-Friday):**
- Standard route: 6122 → 6125
- Wednesday special: 6122 → Lineage → 6125 (frozen drop-off)
- Loads **D-1 production only**

**Afternoon Truck (Day-Specific Destinations):**
- Monday: 6122 → 6104 (NSW/ACT hub)
- Tuesday: 6122 → 6110 (QLD direct)
- Wednesday: 6122 → 6104
- Thursday: 6122 → 6110
- Friday: **TWO trucks** - 6122 → 6110 AND 6122 → 6104
- Loads **D-1 or D0 production**

**Weekly Capacity:**
- 11 truck departures per week
- Maximum: 154,880 units/week (11 trucks × 14,080 units)

---

## Data Models

### Shipment

Links a production batch to a specific delivery destination.

**File:** `src/models/shipment.py`

```python
from src.models.shipment import Shipment

shipment = Shipment(
    id="SHIP-001",
    batch_id="BATCH-2025-01-15-PROD1",
    product_id="PROD1",
    quantity=3200.0,  # 10 pallets
    origin_id="6122",
    destination_id="6103",
    delivery_date=date(2025, 1, 20),
    route=route_to_6103,
    production_date=date(2025, 1, 15),
    assigned_truck_id=None  # Not yet assigned
)
```

**Key Attributes:**
- `id`: Unique shipment identifier
- `batch_id`: Links to production batch
- `quantity`: Units in this shipment
- `destination_id`: Final destination location
- `route`: Complete route path (includes first leg destination)
- `production_date`: When batch was produced (critical for D-1/D0 logic)
- `assigned_truck_id`: Truck schedule ID once assigned

**Key Methods:**
- `first_leg_destination` - Returns destination of first route leg (for truck matching)
- `is_d1_production(truck_departure_date)` - Check if D-1 relative to truck
- `is_d0_production(truck_departure_date)` - Check if D0 relative to truck

### TruckLoad

Represents a loaded truck with assigned shipments.

**File:** `src/distribution/truck_loader.py`

```python
from src.distribution.truck_loader import TruckLoad

truck_load = TruckLoad(
    truck_schedule_id="MORNING-MON-FRI",
    truck_name="Morning Truck",
    departure_date=date(2025, 1, 15),
    departure_type="morning",
    destination_id="6125",
    shipments=[],
    total_units=0.0,
    total_pallets=0,
    capacity_units=14080.0,
    capacity_pallets=44,
    capacity_utilization=0.0,
    is_full=False
)
```

**Key Attributes:**
- `truck_schedule_id`: ID of truck schedule
- `departure_date`: Date of truck departure
- `departure_type`: "morning" or "afternoon"
- `destination_id`: Truck's destination (matches shipment first leg)
- `shipments`: List of assigned shipments
- `total_units`: Sum of shipment quantities
- `total_pallets`: Pallets required (accounting for partial pallets)
- `capacity_utilization`: Pallet capacity used (0.0 to 1.0)
- `is_full`: True if at capacity

### TruckLoadPlan

Complete truck loading plan with all assignments.

**File:** `src/distribution/truck_loader.py`

```python
from src.distribution.truck_loader import TruckLoadPlan

plan = TruckLoadPlan(
    loads=[truck_load_1, truck_load_2, ...],
    unassigned_shipments=[],
    infeasibilities=[],
    total_trucks_used=10,
    total_shipments=25,
    average_utilization=0.82
)
```

**Key Attributes:**
- `loads`: List of truck loads (one per truck departure)
- `unassigned_shipments`: Shipments that couldn't be assigned
- `infeasibilities`: List of constraint violation messages
- `total_trucks_used`: Number of trucks used
- `total_shipments`: Total shipments (assigned + unassigned)
- `average_utilization`: Average capacity utilization across trucks

**Key Methods:**
- `is_feasible()` - Returns True if all shipments assigned

---

## Components

### ShipmentPlanner

Expands production schedule into individual destination shipments.

**File:** `src/distribution/shipment_planner.py`

**Purpose:** Convert aggregated production requirements into individual shipments, one per destination.

**Input:** ProductionSchedule (with batches and requirements)
**Output:** List[Shipment] (one per destination in each requirement)

**Key Logic:**
1. For each ProductionRequirement:
   - Find corresponding ProductionBatch
   - Extract demand_details (list of destinations)
   - Create one Shipment per demand detail
2. Each shipment preserves:
   - Route to destination
   - Delivery date
   - Production date from batch

**Example:**

```python
from src.distribution import ShipmentPlanner

planner = ShipmentPlanner()
shipments = planner.create_shipments(production_schedule)

# If production schedule has:
# - Batch 1: 1000 units PROD1 on 2025-01-15
#   - 500 units → 6103 (via 6125)
#   - 500 units → 6101 (via 6104)
# Creates 2 shipments:
# - Shipment 1: 500 units → 6103, first_leg = 6125
# - Shipment 2: 500 units → 6101, first_leg = 6104
```

**Helper Methods:**
- `get_shipments_by_destination(shipments)` - Group by first leg destination
- `get_shipments_by_production_date(shipments)` - Group by production date

### TruckLoader

Assigns shipments to truck departures.

**File:** `src/distribution/truck_loader.py`

**Purpose:** Match shipments to appropriate trucks based on destination and timing.

**Input:**
- List[Shipment] - Shipments to assign
- List[TruckSchedule] - Available truck schedules
- start_date, end_date - Planning horizon

**Output:** TruckLoadPlan with assignments and statistics

**Key Logic:**

1. **For each date in planning horizon:**
   - Get trucks departing on this date (morning + afternoon)

2. **For each truck:**
   - Create empty truck load
   - Find compatible shipments:
     - Destination matches truck destination
     - Timing compatible (D-1 or D0 per truck type)
   - Sort shipments: D-1 first, then by quantity (largest first)
   - Load shipments until truck full

3. **Capacity checking:**
   - Units: total_units + shipment.quantity ≤ capacity_units
   - Pallets: total_pallets + ceil(quantity/320) ≤ capacity_pallets
   - Stop when either limit reached

**Example:**

```python
from src.distribution import TruckLoader

loader = TruckLoader(truck_schedules)
plan = loader.assign_shipments_to_trucks(
    shipments=shipments,
    start_date=date(2025, 1, 15),
    end_date=date(2025, 1, 20)
)

if plan.is_feasible():
    print(f"Success! {plan.total_trucks_used} trucks loaded")
    print(f"Average utilization: {plan.average_utilization:.1%}")
else:
    print(f"Infeasible: {len(plan.unassigned_shipments)} shipments unassigned")
    for msg in plan.infeasibilities:
        print(f"  - {msg}")
```

**Key Methods:**
- `assign_shipments_to_trucks(shipments, start_date, end_date)` - Main assignment method
- `get_trucks_for_date(departure_date)` - Get trucks departing on specific date

---

## Business Rules

### 1. Destination Matching Rule

**Rule:** Shipment can only go on truck if truck's destination matches shipment's first leg destination.

**Example:**
- Shipment to 6103: Route 6122 → 6125 → 6103
- First leg destination: 6125
- Compatible trucks: Morning truck (goes to 6125), not afternoon Monday truck (goes to 6104)

### 2. Morning Truck Timing Rule

**Rule:** Morning trucks can only load D-1 production.

**Reason:** Morning trucks depart early (e.g., 6 AM). D0 production not ready yet.

**Example:**
- Truck departs: Tuesday 6 AM
- D-1 production: Monday (✅ ready)
- D0 production: Tuesday (❌ not ready)

### 3. Afternoon Truck Timing Rule

**Rule:** Afternoon trucks can load D-1 or D0 production.

**Preference:** Load D-1 first (already available), then D0 if space remains.

**Example:**
- Truck departs: Tuesday 2 PM
- D-1 production: Monday (✅ ready, high priority)
- D0 production: Tuesday (✅ ready if produced before 2 PM, lower priority)

### 4. Capacity Constraint Rules

**Unit Capacity:**
- Maximum: 14,080 units per truck
- Reject shipment if: total_units + shipment.quantity > 14,080

**Pallet Capacity:**
- Maximum: 44 pallets per truck
- Pallets required: `ceil(shipment.quantity / 320)`
- Partial pallets count as full pallets
- Reject shipment if: total_pallets + pallets_needed > 44

**Which Reaches First:**
- Check both limits
- Truck is full when **either** limit reached

### 5. Shipment Priority Rule

**Rule:** When multiple shipments compatible, prioritize:
1. D-1 production (before D0)
2. Larger shipments (largest first)

**Reason:**
- D-1 more certain (already produced)
- Larger shipments minimize partial pallets

### 6. Flexible Routing Rule (Phase 3)

**Current (Phase 2):** Trucks have fixed destinations.

**Future (Phase 3):** Truck destinations may be optimized based on demand.

**Placeholder:** Shipments to flexible-route trucks currently unassigned (returns infeasibility).

---

## Usage Examples

### Example 1: Basic Shipment Planning

```python
from src.distribution import ShipmentPlanner
from datetime import date

# Assume production_schedule created by ProductionScheduler
planner = ShipmentPlanner()
shipments = planner.create_shipments(production_schedule)

print(f"Created {len(shipments)} shipments from production schedule")

# Group by first leg destination
by_destination = planner.get_shipments_by_destination(shipments)
for dest, dest_shipments in by_destination.items():
    total_units = sum(s.quantity for s in dest_shipments)
    print(f"  {dest}: {len(dest_shipments)} shipments, {total_units:.0f} units")
```

### Example 2: Truck Loading

```python
from src.distribution import TruckLoader
from datetime import date

# Load truck schedules
loader = TruckLoader(truck_schedules)

# Assign shipments to trucks
plan = loader.assign_shipments_to_trucks(
    shipments=shipments,
    start_date=date(2025, 1, 15),
    end_date=date(2025, 1, 20)
)

# Check feasibility
if plan.is_feasible():
    print(f"✅ All {plan.total_shipments} shipments assigned to {plan.total_trucks_used} trucks")
    print(f"Average truck utilization: {plan.average_utilization:.1%}")
else:
    print(f"❌ Infeasible plan")
    print(f"  Unassigned shipments: {len(plan.unassigned_shipments)}")
    for msg in plan.infeasibilities[:5]:  # Show first 5
        print(f"  - {msg}")
```

### Example 3: Analyzing Truck Loads

```python
# Iterate through truck loads
for truck_load in plan.loads:
    print(f"\n{truck_load.truck_name} on {truck_load.departure_date}:")
    print(f"  Destination: {truck_load.destination_id}")
    print(f"  Shipments: {len(truck_load.shipments)}")
    print(f"  Total units: {truck_load.total_units:.0f} / {truck_load.capacity_units:.0f}")
    print(f"  Total pallets: {truck_load.total_pallets} / {truck_load.capacity_pallets}")
    print(f"  Utilization: {truck_load.capacity_utilization:.1%}")

    # List shipments
    for shipment in truck_load.shipments:
        pallets = math.ceil(shipment.quantity / 320)
        print(f"    - {shipment.id}: {shipment.quantity:.0f} units ({pallets} pallets) → {shipment.destination_id}")
```

### Example 4: D-1 vs D0 Analysis

```python
from datetime import date

truck_departure = date(2025, 1, 16)  # Tuesday

for shipment in shipments:
    is_d1 = shipment.is_d1_production(truck_departure)
    is_d0 = shipment.is_d0_production(truck_departure)

    if is_d1:
        status = "D-1 (high priority)"
    elif is_d0:
        status = "D0 (lower priority, afternoon only)"
    else:
        status = "Not compatible with this truck"

    print(f"Shipment {shipment.id} produced {shipment.production_date}: {status}")
```

### Example 5: Checking Unassigned Shipments

```python
if not plan.is_feasible():
    print(f"\nUnassigned Shipments ({len(plan.unassigned_shipments)}):")

    for shipment in plan.unassigned_shipments:
        print(f"  {shipment.id}:")
        print(f"    Product: {shipment.product_id}")
        print(f"    Quantity: {shipment.quantity:.0f} units")
        print(f"    Destination: {shipment.destination_id}")
        print(f"    First leg: {shipment.first_leg_destination}")
        print(f"    Production date: {shipment.production_date}")
        print(f"    Delivery date: {shipment.delivery_date}")
```

---

## API Reference

### ShipmentPlanner

#### `create_shipments(schedule: ProductionSchedule) -> List[Shipment]`

Create shipments from production schedule.

**Parameters:**
- `schedule`: ProductionSchedule with batches and requirements

**Returns:**
- List of Shipment objects, one per demand detail

**Example:**
```python
shipments = planner.create_shipments(schedule)
```

#### `get_shipments_by_destination(shipments: List[Shipment]) -> Dict[str, List[Shipment]]`

Group shipments by first leg destination.

**Parameters:**
- `shipments`: List of shipments

**Returns:**
- Dictionary mapping first_leg_destination → list of shipments

**Example:**
```python
by_dest = planner.get_shipments_by_destination(shipments)
shipments_to_6125 = by_dest["6125"]
```

#### `get_shipments_by_production_date(shipments: List[Shipment]) -> Dict[date, List[Shipment]]`

Group shipments by production date.

**Parameters:**
- `shipments`: List of shipments

**Returns:**
- Dictionary mapping production_date → list of shipments

**Example:**
```python
by_date = planner.get_shipments_by_production_date(shipments)
monday_shipments = by_date[date(2025, 1, 15)]
```

### TruckLoader

#### `__init__(truck_schedules: List[TruckSchedule])`

Initialize truck loader.

**Parameters:**
- `truck_schedules`: List of truck schedule definitions

#### `assign_shipments_to_trucks(shipments: List[Shipment], start_date: date, end_date: date) -> TruckLoadPlan`

Assign shipments to trucks across a date range.

**Parameters:**
- `shipments`: List of shipments to assign
- `start_date`: First date to consider for truck departures
- `end_date`: Last date to consider for truck departures

**Returns:**
- TruckLoadPlan with assignments and unassigned shipments

**Example:**
```python
plan = loader.assign_shipments_to_trucks(
    shipments=shipments,
    start_date=date(2025, 1, 15),
    end_date=date(2025, 1, 20)
)
```

#### `get_trucks_for_date(departure_date: date) -> List[TruckSchedule]`

Get all trucks that depart on a specific date.

**Parameters:**
- `departure_date`: Date to check

**Returns:**
- List of truck schedules that depart on this date

**Example:**
```python
trucks_monday = loader.get_trucks_for_date(date(2025, 1, 15))
print(f"{len(trucks_monday)} trucks depart on Monday")
```

### Shipment

#### `first_leg_destination: str` (property)

Get the destination of the first route leg.

**Returns:**
- Destination ID of first leg in route

**Example:**
```python
# Route: 6122 → 6125 → 6103
first_leg = shipment.first_leg_destination  # Returns "6125"
```

#### `is_d1_production(truck_departure_date: date) -> bool`

Check if this is D-1 production relative to truck departure.

**Parameters:**
- `truck_departure_date`: Date when truck departs

**Returns:**
- True if production_date is one day before truck departure

**Example:**
```python
shipment.production_date = date(2025, 1, 15)
truck_departs = date(2025, 1, 16)
is_d1 = shipment.is_d1_production(truck_departs)  # True
```

#### `is_d0_production(truck_departure_date: date) -> bool`

Check if this is D0 (same-day) production relative to truck departure.

**Parameters:**
- `truck_departure_date`: Date when truck departs

**Returns:**
- True if production_date equals truck departure date

**Example:**
```python
shipment.production_date = date(2025, 1, 16)
truck_departs = date(2025, 1, 16)
is_d0 = shipment.is_d0_production(truck_departs)  # True
```

---

## Next Steps

- **Phase 3:** Flexible truck routing (optimize destinations, not fixed)
- **Phase 3:** Consolidation logic (combine small shipments)
- **Phase 3:** Multi-stop truck routes (pickup from multiple hubs)
- **Phase 4:** Real-time truck tracking integration
- **Phase 4:** Dynamic re-routing based on delays

---

**Module Version:** Phase 2 (Fixed truck destinations)

**Last Updated:** 2025-10-02

**Related Documentation:**
- `MANUFACTURING_SCHEDULE.md` - Production timing and truck departure details
- `NETWORK_ROUTES.md` - Complete route topology
- `COST_CALCULATION.md` - Cost calculation module
