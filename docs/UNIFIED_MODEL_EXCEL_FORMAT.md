# Unified Node Model - Excel Template Specification

## Overview

This document specifies the Excel template format for the Unified Node Model.

**Key Differences from Legacy Format:**
- "Nodes" sheet instead of "Locations" (with capability columns)
- "TruckSchedules" has explicit `origin_node_id` column
- Cleaner, more intuitive structure
- No need for location type classification

---

## Sheet 1: Nodes

**Purpose:** Define all nodes in the supply chain network with their capabilities

**Columns:**

| Column | Type | Required | Description | Example |
|--------|------|----------|-------------|---------|
| `node_id` | String | Yes | Unique node identifier | `6122` |
| `node_name` | String | Yes | Human-readable name | `Manufacturing Site` |
| `can_manufacture` | Boolean | Yes | Can this node produce product? | `TRUE` |
| `production_rate_per_hour` | Float | If manufacturing | Units per hour production rate | `1400.0` |
| `can_store` | Boolean | Yes | Can this node hold inventory? | `TRUE` |
| `storage_mode` | String | Yes | Temperature capability: `frozen`, `ambient`, or `both` | `ambient` |
| `storage_capacity` | Float | No | Maximum capacity in units (blank = unlimited) | `100000` |
| `has_demand` | Boolean | Yes | Is this a demand destination? | `FALSE` |
| `requires_truck_schedules` | Boolean | Yes | Do outbound shipments need truck schedules? | `TRUE` |
| `latitude` | Float | No | GPS latitude for visualization | `-37.8136` |
| `longitude` | Float | No | GPS longitude for visualization | `144.9631` |

**Example Rows:**

```
node_id | node_name             | can_manufacture | production_rate_per_hour | can_store | storage_mode | has_demand | requires_truck_schedules
6122    | Manufacturing Site    | TRUE            | 1400.0                   | TRUE      | ambient      | FALSE      | TRUE
6125    | VIC Hub (Keilor Park) | FALSE           |                          | TRUE      | ambient      | TRUE       | FALSE
Lineage | Lineage Frozen Buffer | FALSE           |                          | TRUE      | frozen       | FALSE      | FALSE
6130    | WA Breadroom          | FALSE           |                          | TRUE      | both         | TRUE       | FALSE
```

**Notes:**
- `can_manufacture=TRUE` requires `production_rate_per_hour`
- `storage_mode=both` allows freeze/thaw operations (e.g., 6130 for WA thawing)
- `requires_truck_schedules=TRUE` means outbound shipments MUST use scheduled trucks

---

## Sheet 2: Routes

**Purpose:** Define connections between nodes

**Columns:**

| Column | Type | Required | Description | Example |
|--------|------|----------|-------------|---------|
| `route_id` | String | Yes | Unique route identifier | `R1` |
| `origin_node_id` | String | Yes | Origin node ID | `6122` |
| `destination_node_id` | String | Yes | Destination node ID | `6125` |
| `transit_days` | Float | Yes | Transit time in days (0.0 = instant, 0.5 = half day, 1.0 = one day) | `1.0` |
| `transport_mode` | String | Yes | `frozen` or `ambient` | `ambient` |
| `cost_per_unit` | Float | Yes | Variable cost per unit shipped | `0.30` |

**Example Rows:**

```
route_id | origin_node_id | destination_node_id | transit_days | transport_mode | cost_per_unit
R1       | 6122           | 6125                | 1.0          | ambient        | 0.30
R2       | 6122           | 6110                | 1.5          | ambient        | 0.40
R4       | 6122           | Lineage             | 0.5          | ambient        | 0.20
R10      | Lineage        | 6130                | 3.0          | frozen         | 0.50
R7       | 6125           | 6123                | 0.5          | ambient        | 0.15
```

**Notes:**
- Routes can connect ANY nodes (not just manufacturing-origin)
- `transit_days=0.0` for instant transfers (same location, different temperature)
- State transitions automatic based on `transport_mode` + destination `storage_mode`

---

## Sheet 3: TruckSchedules

**Purpose:** Define truck schedules that constrain shipments on specific routes

**Columns:**

| Column | Type | Required | Description | Example |
|--------|------|----------|-------------|---------|
| `truck_id` | String | Yes | Unique truck identifier | `T1` |
| `truck_name` | String | Yes | Descriptive name | `Morning 6125 (Mon)` |
| `origin_node_id` | String | Yes | **Origin node** (NEW!) | `6122` |
| `destination_node_id` | String | Yes | Destination node | `6125` |
| `departure_type` | String | Yes | `morning` or `afternoon` | `morning` |
| `departure_time` | Time | Yes | HH:MM format | `08:00` |
| `day_of_week` | String | No | `monday`, `tuesday`, etc. (blank = daily) | `monday` |
| `capacity` | Float | Yes | Truck capacity in units | `14080` |
| `cost_fixed` | Float | Yes | Fixed cost per departure | `100.0` |
| `cost_per_unit` | Float | Yes | Variable cost per unit | `0.30` |
| `intermediate_stops` | String | No | Comma-separated node IDs | `Lineage` |
| `pallet_capacity` | Integer | No | Maximum pallets (default: 44) | `44` |
| `units_per_pallet` | Integer | No | Units per pallet (default: 320) | `320` |
| `units_per_case` | Integer | No | Units per case (default: 10) | `10` |

**Example Rows:**

```
truck_id | truck_name          | origin_node_id | destination_node_id | departure_type | day_of_week | capacity
T1       | Morning 6125 (Mon)  | 6122           | 6125                | morning        | monday      | 14080
T3       | Morning Lineage Wed | 6122           | 6125                | morning        | wednesday   | 14080
T_HUB1   | Hub to Clayton Wed  | 6125           | 6123                | morning        | wednesday   | 14080
```

**Key Improvement:** `origin_node_id` column allows truck schedules from ANY node!
- Manufacturing trucks: origin=6122
- **Hub trucks** (NEW!): origin=6125, 6104, etc.

---

## Sheet 4: LaborCalendar

**Same as legacy format** - no changes needed

**Columns:** date, fixed_hours, regular_rate, overtime_rate, non_fixed_rate, minimum_hours, is_fixed_day

---

## Sheet 5: CostParameters

**Same as legacy format** - no changes needed

**Columns:** cost_type, value, unit

**Key Parameters:**
- `production_cost_per_unit`: $5.00
- `shortage_penalty_per_unit`: $10,000.00 (increased!)
- `transport_cost_per_unit`: (deprecated - use route-specific costs)

---

## Sheet 6: InitialInventory (Optional)

**Updated format for unified model**

**Columns:**

| Column | Type | Required | Description | Example |
|--------|------|----------|-------------|---------|
| `node_id` | String | Yes | Node where inventory located | `6125` |
| `product_id` | String | Yes | Product identifier | `HELGAS GFREE WHOLEM 500G` |
| `quantity` | Float | Yes | Inventory quantity in units | `5000` |
| `production_date` | Date | No | When was this produced? (for age tracking) | `2025-10-01` |
| `state` | String | Yes | `frozen`, `ambient`, or `thawed` | `ambient` |

**Example Rows:**

```
node_id | product_id               | quantity | production_date | state
6125    | HELGAS GFREE WHOLEM 500G | 5000     | 2025-10-01      | ambient
Lineage | WONDER GFREE WHITE 470G  | 10000    | 2025-09-28      | frozen
```

---

## Backward Compatibility

**The unified model can use EITHER:**

1. **New unified format** (Nodes, Routes with origin_node_id in trucks)
2. **Legacy format** (Locations, Routes) via `LegacyToUnifiedConverter`

The converter automatically:
- Converts Locations → Nodes (with capability inference)
- Adds `origin_node_id` to truck schedules (assumes manufacturing)
- Preserves all functionality

---

## Migration Path

**For existing users:**
1. Keep using legacy format - converter handles it automatically
2. Gradually migrate to new format for cleaner data
3. New format enables hub truck scheduling

**For new users:**
- Start with unified format directly
- Clearer, more intuitive structure
- Full feature access from day one

---

## Example: Complete Minimal Configuration

**Nodes Sheet:**
```
node_id | node_name          | can_manufacture | production_rate_per_hour | can_store | storage_mode | has_demand | requires_truck_schedules
MFG     | Manufacturing      | TRUE            | 1400.0                   | TRUE      | ambient      | FALSE      | TRUE
HUB     | Regional Hub       | FALSE           |                          | TRUE      | ambient      | TRUE       | FALSE
SPOKE   | Spoke Location     | FALSE           |                          | TRUE      | ambient      | TRUE       | FALSE
```

**Routes Sheet:**
```
route_id | origin_node_id | destination_node_id | transit_days | transport_mode | cost_per_unit
R1       | MFG            | HUB                 | 1.0          | ambient        | 1.00
R2       | HUB            | SPOKE               | 0.5          | ambient        | 0.50
```

**TruckSchedules Sheet:**
```
truck_id | truck_name     | origin_node_id | destination_node_id | departure_type | day_of_week | capacity
T1       | MFG to Hub Mon | MFG            | HUB                 | morning        | monday      | 14080
T2       | Hub to Spoke   | HUB            | SPOKE               | morning        |             | 14080
```

This minimal config demonstrates hub truck scheduling - not possible in legacy format!
