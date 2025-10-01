# Manufacturing Schedule and Operations (Location 6122)

## Overview

This document details the complete manufacturing schedule, labor availability, production capacity, truck routing patterns, and packaging constraints for the gluten-free bread manufacturing facility (Location ID: 6122).

## Labor Schedule

### Weekly Labor Availability

| Day | Fixed Hours | Max Overtime | Total Max Hours | Notes |
|-----|-------------|--------------|-----------------|-------|
| Monday | 12 hours | 2 hours | 14 hours | Standard production day |
| Tuesday | 12 hours | 2 hours | 14 hours | Standard production day |
| Wednesday | 12 hours | 2 hours | 14 hours | Standard production day |
| Thursday | 12 hours | 2 hours | 14 hours | Standard production day |
| Friday | 12 hours | 2 hours | 14 hours | Standard production day |
| Saturday | 0 hours | Unlimited | Unlimited | Overtime only, 4-hour minimum payment |
| Sunday | 0 hours | Unlimited | Unlimited | Overtime only, 4-hour minimum payment |

### Labor Cost Structure

**Weekday (Monday-Friday):**
- **Fixed hours (0-12h):** Regular rate
- **Overtime hours (12-14h):** Premium rate (higher than regular)
- **Maximum:** 14 hours per day

**Weekend (Saturday-Sunday):**
- **All hours:** Overtime rate
- **Minimum payment:** Must pay for 4 hours even if working less
- **Use case:** Makeup production, demand spikes, or buffer stock building

**Public Holidays:**
- **Labor treatment:** Same as weekends (no fixed hours, 4-hour minimum payment, premium rate)
- **Production:** Available if needed, but at premium cost

### Public Holidays

**2025 Public Holidays (13 days):**

| Date | Day | Holiday |
|------|-----|---------|
| 1 January | Wednesday | New Year's Day |
| 27 January | Monday | Australia Day |
| 10 March | Monday | Labour Day |
| 18 April | Friday | Good Friday |
| 19 April | Saturday | Saturday before Easter Sunday |
| 20 April | Sunday | Easter Sunday |
| 21 April | Monday | Easter Monday |
| 25 April | Friday | ANZAC Day |
| 9 June | Monday | King's Birthday |
| 26 September | Friday | Friday before AFL Grand Final |
| 4 November | Tuesday | Melbourne Cup |
| 25 December | Thursday | Christmas Day |
| 26 December | Friday | Boxing Day |

**2026 Public Holidays (14 days):**

| Date | Day | Holiday |
|------|-----|---------|
| 1 January | Thursday | New Year's Day |
| 26 January | Monday | Australia Day |
| 9 March | Monday | Labour Day |
| 3 April | Friday | Good Friday |
| 4 April | Saturday | Saturday before Easter Sunday |
| 5 April | Sunday | Easter Sunday |
| 6 April | Monday | Easter Monday |
| 25 April | Saturday | ANZAC Day |
| 8 June | Monday | King's Birthday |
| TBD | Friday | Friday before AFL Grand Final (subject to AFL schedule) |
| 3 November | Tuesday | Melbourne Cup |
| 25 December | Friday | Christmas Day |
| 26 December | Saturday | Boxing Day |
| 28 December | Monday | Substitute day for Boxing Day |

**Impact on Production Planning:**
- 2025: 13 public holidays, 8 fall on weekdays (Wed, Mon, Mon, Fri, Fri, Mon, Fri, Tue, Thu, Fri)
- 2026: 14 public holidays, 8 fall on weekdays (Thu, Mon, Mon, Fri, Fri, Mon, Tue, Fri, Mon)
- Weekday public holidays reduce standard 12-hour fixed labor availability
- Production possible but at weekend rates (4h minimum, premium cost)
- Annual impact: ~8-10 fewer standard production days vs. 260 weekdays/year

## Production Capacity

### Production Rate
- **Rate:** 1,400 units per hour
- **Setup time:** Assumed negligible for daily continuous operations

### Daily Production Capacity

| Scenario | Hours | Production Capacity |
|----------|-------|---------------------|
| Regular weekday | 12 hours | 16,800 units |
| Weekday with max OT | 14 hours | 19,600 units |
| Weekend (4h minimum) | 4 hours | 5,600 units |
| Weekend (8 hours) | 8 hours | 11,200 units |

### Weekly Production Capacity

| Scenario | Calculation | Total Capacity |
|----------|-------------|----------------|
| Regular (no OT) | 5 days × 16,800 | 84,000 units/week |
| With 2h daily OT | 5 days × 19,600 | 98,000 units/week |
| With weekend (8h Sat) | 98,000 + 11,200 | 109,200 units/week |

**Average weekly demand:** ~82,600 units/week
**Capacity utilization (regular):** 98% (tight but feasible)
**Capacity utilization (with OT):** 84% (comfortable headroom)

## Packaging Structure

### Packaging Hierarchy

```
Truck (44 pallets)
  └─ Pallet (32 cases = 320 units)
       └─ Case (10 units)
            └─ Unit (1 loaf)
```

### Packaging Specifications

| Level | Quantity | Constraint |
|-------|----------|------------|
| **Unit** | 1 loaf | Base unit |
| **Case** | 10 units | Minimum shipping quantity - NO partial cases allowed |
| **Pallet** | 32 cases = 320 units | Full pallet or partial pallet (both occupy same space) |
| **Truck** | 44 pallets = 14,080 units | Maximum truck capacity |

### Critical Constraints

1. **No partial cases:** All production and shipping must be in multiples of 10 units
2. **Partial pallet space:** A pallet with 1 case or 31 cases both occupy 1 full pallet space
3. **Truck capacity:** Maximum 44 pallets regardless of how full each pallet is
4. **Optimization goal:** Minimize partial pallets to maximize truck utilization

### Pallet Efficiency Examples

| Units | Cases | Full Pallets | Partial Pallet | Total Pallets | Truck % | Efficiency |
|-------|-------|--------------|----------------|---------------|---------|------------|
| 14,080 | 1,408 | 44 | 0 cases | 44 | 100% | Optimal |
| 14,000 | 1,400 | 43 | 24 cases | 44 | 99.4% | Excellent |
| 13,600 | 1,360 | 42 | 16 cases | 43 | 97.7% | Good |
| 11,200 | 1,120 | 35 | 0 cases | 35 | 79.5% | Acceptable |
| 10,010 | 1,001 | 31 | 1 case | 32 | 71.1% | Poor (wasted space) |

**Recommendation:** Target production quantities that are multiples of 320 units (full pallets) to maximize efficiency.

## Truck Departure Schedule from 6122

### Morning Truck (Departs Daily, Monday-Friday)

**Standard Route (Mon, Tue, Thu, Fri):**
```
6122 (Manufacturing) → 6125 (Keilor Park Hub, VIC)
```

**Special Wednesday Route:**
```
6122 (Manufacturing) → Lineage (Frozen Storage) → 6125 (Keilor Park Hub, VIC)
```

**Characteristics:**
- Loads D-1 production (previous day's production)
- Capacity: 44 pallets = 14,080 units
- Destination: Always 6125 (VIC/TAS/SA hub)
- Wednesday: Drops frozen stock at Lineage before continuing to 6125
- Frequency: 5 departures per week

**6125 Hub Region Demand:**
- 6125 local: 258,739 units (204 days) = 1,268 units/day
- 6123 (via 6125): 339,750 units = 1,665 units/day
- 6134 (via 6125): 247,050 units = 1,211 units/day
- 6120 (via 6125): 58,458 units = 287 units/day
- **Total:** 903,996 units / 204 days = 4,431 units/day average

### Afternoon Truck (Day-Specific Destinations)

| Day | Destination | Route | Notes |
|-----|-------------|-------|-------|
| **Monday** | 6104 | 6122 → 6104 (Moorebank Hub, NSW) | NSW/ACT hub |
| **Tuesday** | 6110 | 6122 → 6110 (Burleigh Heads, QLD) | Direct to Queensland |
| **Wednesday** | 6104 | 6122 → 6104 (Moorebank Hub, NSW) | NSW/ACT hub |
| **Thursday** | 6110 | 6122 → 6110 (Burleigh Heads, QLD) | Direct to Queensland |
| **Friday** | **6110 AND 6104** | **TWO TRUCKS:** 6122 → 6110 AND 6122 → 6104 | Double capacity |

**Characteristics:**
- Primarily loads D-1 production
- Can include D0 (same-day) production if ready before departure
- Capacity per truck: 44 pallets = 14,080 units
- Friday: 2 trucks = 88 pallets = 28,160 units capacity

**6104 Hub Region (3 shipments/week: Mon, Wed, Fri):**
- 6104 local: 432,595 units = 2,121 units/day
- 6105 (via 6104): 301,846 units = 1,479 units/day
- 6103 (via 6104): 115,400 units = 566 units/day
- **Total:** 849,841 units / 204 days = 4,165 units/day
- **Per shipment:** 4,165 × (7/3) = 9,718 units every 2.3 days

**6110 Direct (3 shipments/week: Tue, Thu, Fri):**
- **Total:** 542,121 units / 204 days = 2,657 units/day
- **Per shipment:** 2,657 × (7/3) = 6,200 units every 2.3 days

### Weekly Truck Capacity Summary

| Route | Trucks/Week | Capacity/Truck | Weekly Capacity |
|-------|-------------|----------------|-----------------|
| Morning → 6125 | 5 | 14,080 | 70,400 units |
| Afternoon → 6104 | 3 | 14,080 | 42,240 units |
| Afternoon → 6110 | 3 | 14,080 | 42,240 units |
| **TOTAL** | **11** | | **154,880 units/week** |

**Capacity vs. Demand:**
- Weekly shipping capacity: 154,880 units
- Average weekly demand: ~82,600 units
- **Utilization:** 53% (significant headroom for demand variability)

## Hub Outbound Schedule

### Assumption: Hub Trucks Depart in Morning

**From 6104 (Moorebank) to Spoke Locations:**
- 6104 → 6105 (Rydalmere): Morning departures
- 6104 → 6103 (Canberra): Morning departures
- Frequency: Determined by hub inventory and spoke demand

**From 6125 (Keilor Park) to Spoke Locations:**
- 6125 → 6123 (Clayton): Morning departures
- 6125 → 6134 (Adelaide): Morning departures
- 6125 → 6120 (Hobart): Morning departures
- Frequency: Determined by hub inventory and spoke demand

## Transit Time Chains

### Via 6125 Hub (Daily Service)
```
Day 0: Production at 6122
Day 1 AM: Arrive at 6125 hub
Day 1: Allocate between 6125 local demand and spoke forwarding
Day 2 AM: Forward to spoke locations (6123, 6134, 6120)
Day 2 PM: Arrive at final destination
```
**Minimum transit:** 2 days from production to spoke breadroom

### Via 6104 Hub (3x/week Service)
```
Day 0: Production at 6122
Day 1 PM: Arrive at 6104 hub
Day 1-3: Hold inventory (2-3 days between shipments)
Day 2-4 AM: Forward to spoke locations (6105, 6103)
Day 2-4 PM: Arrive at final destination
```
**Minimum transit:** 2 days, up to 4 days depending on shipment schedule

### Direct to 6110 (3x/week Service)
```
Day 0: Production at 6122
Day 1 PM: Arrive at 6110
Day 1: Available for market release
```
**Minimum transit:** 1 day

### Via Lineage to 6130 (Weekly on Wednesday)
```
Day 0: Production at 6122 (frozen)
Day 1 AM: Arrive at Lineage (frozen storage)
Day 1-N: Hold frozen inventory (120-day shelf life)
Day N: Ship frozen to 6130 (Perth, WA)
Day N+3: Arrive at 6130 (frozen)
Day N+3: Thaw at 6130 (shelf life resets to 14 days)
Day N+3 onwards: Ambient storage at 6130, market release
```
**Minimum transit:** 4+ days (typically longer due to frozen buffering strategy)

## Wednesday Morning Special Routing

### Lineage Frozen Drop

**Route:** 6122 → Lineage → 6125

**Operational Details:**
- Single morning truck serves both Lineage and 6125
- Must allocate 44 pallets between two destinations
- Lineage stock: Frozen product for WA buffer (6130)
- 6125 stock: Ambient/frozen for VIC/TAS/SA region

**Allocation Decision:**
```
Example: 14,080-unit truck
- Option A: 4,480 units (14 pallets) to Lineage + 9,600 units (30 pallets) to 6125
- Option B: 6,400 units (20 pallets) to Lineage + 7,680 units (24 pallets) to 6125
- Option C: 3,200 units (10 pallets) to Lineage + 10,880 units (34 pallets) to 6125
```

**Optimization Considerations:**
- More to Lineage = build frozen buffer for WA
- More to 6125 = serve immediate VIC/TAS/SA demand
- Balance depends on: 6130 inventory level, 6125 region demand, forecast accuracy

## Shelf Life Impact by Route

### Ambient Route
- **Production Day 0:** 17 days remaining
- **After 1-day transit:** 16 days at destination
- **After 2-day transit:** 15 days at destination
- **After 4-day transit:** 13 days at destination
- **Breadroom minimum:** 7 days required at receipt

**Maximum transit time for ambient:** 10 days (17 - 7 = 10 days)

### Frozen-Then-Thawed Route (6130 via Lineage)
- **Production Day 0:** Freeze immediately (120 days frozen shelf life)
- **Frozen storage at Lineage:** No shelf life loss (remains 120 days)
- **Frozen transport to 6130:** No shelf life loss (remains 120 days)
- **Thawed at 6130:** **Shelf life resets to 14 days** (critical!)
- **After thawing:** 14 days available for market release
- **Breadroom minimum:** 7 days required at receipt

**Effective usable time after thaw:** 7 days maximum (14 - 7 = 7 days to distribute)

## Production Planning Implications

### Daily Production Targets

**Minimum daily production (no OT):**
- Must serve: 6125 AM truck (~4,400 units) + afternoon truck (~4,000-6,000 units)
- **Minimum:** ~8,400 units/day
- **Required hours:** 6 hours (50% of fixed labor)

**Typical daily production (balanced):**
- Serve both trucks at 70% capacity: 9,900 + 9,900 = 19,800 units
- **Required hours:** 14.1 hours (12h regular + 2.1h OT)
- **Infeasible:** Exceeds 14-hour daily limit
- **Realistic:** ~11,000-13,000 units/day (8-9 hours)

**Optimal production strategy:**
- Produce 11,200-14,000 units/day (8-10 hours)
- Minimize overtime usage
- Build small buffer for demand variability
- Optimize for full pallets (multiples of 320 units)

### Weekly Production Pattern

**Example Week (No weekend work):**

| Day | Hours | Production | Morning Truck | Afternoon Truck(s) | Total Shipped |
|-----|-------|------------|---------------|-------------------|---------------|
| Mon | 10 | 14,000 | 6125: 11,200 | 6104: 2,800 | 14,000 |
| Tue | 9 | 12,600 | 6125: 9,600 | 6110: 3,000 | 12,600 |
| Wed | 10 | 14,000 | 6125+Lineage: 11,200 | 6104: 2,800 | 14,000 |
| Thu | 9 | 12,600 | 6125: 9,600 | 6110: 3,000 | 12,600 |
| Fri | 12 | 16,800 | 6125: 11,200 | 6110+6104: 5,600 | 16,800 |
| **Total** | **50h** | **70,000** | | | **70,000** |

**Analysis:**
- Average: 10 hours/day, 14,000 units/day
- No overtime required
- Covers ~85% of average demand (82,600 units/week)
- Requires buffer inventory or occasional weekend makeup

## Key Operational Constraints

1. **Discrete packaging:** All quantities must be multiples of 10 units (case level)
2. **Pallet efficiency:** Target multiples of 320 units to avoid partial pallets
3. **Truck capacity:** Hard limit of 14,080 units per truck departure
4. **Labor availability:** 12 hours fixed M-F, max 14 hours with OT, weekend available with 4h minimum
5. **Production rate:** Fixed at 1,400 units/hour
6. **Day-specific routing:** Cannot change afternoon truck destinations (Mon→6104, Tue→6110, etc.)
7. **Wednesday allocation:** Must split morning truck between Lineage and 6125
8. **Shelf life:** Ambient products must reach breadroom within 10 days to have 7+ days remaining

## Optimization Opportunities

1. **Pallet optimization:** Produce 14,080 units (44 pallets exactly) when possible
2. **OT minimization:** Schedule production to use 12h fixed labor, avoiding OT premiums
3. **Weekend avoidance:** Plan production to avoid 4-hour minimum weekend payments
4. **Buffer positioning:** Hold safety stock at hubs (6104, 6125) rather than manufacturing
5. **Lineage utilization:** Build frozen buffer on Wednesdays to enable less frequent 6130 shipments
6. **Batch sizing:** Align production batches with truck capacities (14,080, 7,040, 3,520 units)

## Notes for Optimization Model (Phase 3)

When building the mathematical optimization model, ensure:

1. **Integer constraints:**
   - Production quantities: multiples of 10 (case constraint)
   - Pallet calculations: ceiling division for partial pallets
   - Truck utilization: max 44 pallets per truck

2. **Time-indexed decisions:**
   - Production quantities by day (Monday-Sunday)
   - Truck loading quantities by day and destination
   - Hub forwarding decisions by day and spoke location

3. **Cost minimization:**
   - Labor: fixed hours (regular) + overtime (premium) + weekend (4h minimum)
   - Transport: truck fixed cost + per-unit variable cost
   - Waste: expired product + insufficient shelf life at destination
   - Holding: inventory at hubs, Lineage, and manufacturing

4. **Constraints:**
   - Labor availability by day (12h M-F, unlimited weekend)
   - Truck capacity (44 pallets = 14,080 units)
   - Shelf life tracking (17 ambient, 120 frozen, 14 thawed)
   - Demand satisfaction with 7+ days remaining at breadroom
   - Hub allocation between local and spoke demands
