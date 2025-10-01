# Distribution Network Routes

## Overview

This document defines the complete **2-echelon hub-and-spoke distribution network** with frozen buffer for gluten-free bread distribution from manufacturing (Location 6122) to 9 breadroom destinations across Australia.

## Network Topology

```
                    Manufacturing (6122)
                           |
        +------------------+------------------+------------------+
        |                  |                  |                  |
    6104 (Hub)          6110             6125 (Hub)        Lineage (Frozen)
        |             (Direct)               |                  |
    +---+---+                      +---------+--------+         |
    |       |                      |         |        |         |
  6105    6103                   6123      6134     6120      6130
 (NSW)   (ACT)                  (VIC)     (SA)     (TAS)     (WA)
                                                            [Thawed]
```

**Network Type:** 2-Echelon Hub-and-Spoke + Frozen Buffer
- **Tier 1:** Manufacturing site (6122)
- **Tier 2:** Regional hubs (6104, 6125) + Direct destinations (6110) + Frozen buffer (Lineage)
- **Tier 3:** Final breadrooms served by hubs + Special thawing facility (6130)

## Route Legs

### Primary Routes (Tier 1: Manufacturing → Hubs/Direct)

| Route ID | Origin | Destination | Type | Mode | Purpose |
|----------|--------|-------------|------|------|---------|
| R1 | 6122 | 6104 | Hub | Ambient/Frozen | NSW/ACT regional hub |
| R2 | 6122 | 6110 | Direct | Ambient/Frozen | Direct to QLD |
| R3 | 6122 | 6125 | Hub | Ambient/Frozen | VIC/TAS/SA regional hub |
| R4 | 6122 | Lineage | Frozen Buffer | Frozen | Intermediate frozen storage for WA |

### Secondary Routes (Tier 2: Hubs → Final Destinations)

| Route ID | Origin | Destination | Hub | Mode | Distance Type |
|----------|--------|-------------|-----|------|---------------|
| R5 | 6104 | 6105 | NSW/ACT | Ambient | Local (Sydney metro) |
| R6 | 6104 | 6103 | NSW/ACT | Ambient | Regional (Sydney to Canberra) |
| R7 | 6125 | 6123 | VIC/TAS/SA | Ambient | Local (Melbourne metro) |
| R8 | 6125 | 6134 | VIC/TAS/SA | Ambient | Regional (Melbourne to Adelaide) |
| R9 | 6125 | 6120 | VIC/TAS/SA | Ambient/Frozen | Long-haul (Melbourne to Hobart) |

### Special Frozen Route (Tier 2: Frozen Buffer → WA with Thawing)

| Route ID | Origin | Destination | Mode | Special Operation |
|----------|--------|-------------|------|-------------------|
| R10 | Lineage | 6130 | Frozen | **Thawed at 6130, shelf life resets to 14 days** |

## Hub Assignments

### Hub 1: 6104 (QBA-Moorebank, NSW)
**Serves:** NSW & ACT region

**Dual Role:**
1. **Distribution Hub** - Receives consolidated shipments from manufacturing (6122)
2. **Local Breadroom** - Serves Moorebank's own market demand (432,595 units forecasted)

**Coverage:**
- **6105** - QBA-Rydalmere (NSW) - Local Sydney distribution (301,846 units forecasted)
- **6103** - QBA-Canberra (ACT) - Regional NSW to ACT (115,400 units forecasted)

**Total Hub Region Demand:** 849,841 units = 6104 (432,595) + 6105 (301,846) + 6103 (115,400)

**Critical Note:** The forecast for 6104 represents ONLY 6104's local market, NOT 6105 or 6103 demand. Each location has an independent forecast. Product arriving at 6104 must be allocated between local fulfillment and forwarding to spoke locations.

**Rationale:** Moorebank is strategically located in western Sydney, serving as consolidation point for NSW and ACT deliveries.

### Hub 2: 6125 (QBA-Keilor Park, VIC)
**Serves:** VIC, TAS, SA region

**Dual Role:**
1. **Distribution Hub** - Receives consolidated shipments from manufacturing (6122)
2. **Local Breadroom** - Serves Keilor Park's own market demand (258,739 units forecasted)

**Coverage:**
- **6123** - QBA-Clayton-Fairbank (VIC) - Local Melbourne distribution (339,750 units forecasted)
- **6134** - QBA-West Richmond SA (SA) - Regional Melbourne to Adelaide (247,050 units forecasted)
- **6120** - QBA-Hobart (TAS) - Long-haul Melbourne to Tasmania (58,458 units forecasted)

**Total Hub Region Demand:** 903,996 units = 6125 (258,739) + 6123 (339,750) + 6134 (247,050) + 6120 (58,458)

**Critical Note:** The forecast for 6125 represents ONLY 6125's local market, NOT 6123, 6134, or 6120 demand. Each location has an independent forecast. Product arriving at 6125 must be allocated between local fulfillment and forwarding to spoke locations.

**Rationale:** Keilor Park in Melbourne serves as consolidation point for Victoria and southern/island states.

## Direct Routes

### 6110 (QBA-Burleigh Heads, QLD)
**Route:** 6122 → 6110 (Direct)

**Characteristics:**
- **Distance:** Long-haul (QLD is distant from manufacturing)
- **Frequency:** Potentially less frequent than hubs
- **Mode:** Ambient or frozen depending on frequency
- **Rationale:** Direct shipping, possibly consolidated on less-frequent truck or via separate QLD-focused truck

## Special Case: Western Australia (6130) with Frozen Storage

### The Lineage → 6130 Frozen Route

**Complete Path:** 6122 → Lineage → 6130

**Route Characteristics:**
- **Total Distance:** ~3,200 km (extremely long-haul)
- **Primary Transport Mode:** FROZEN (120-day shelf life)
- **Intermediate Storage:** Lineage (external frozen storage facility)
- **Final Leg:** Lineage → 6130 (frozen delivery)

**Critical Operation - Thawing at 6130:**
1. **Arrival:** Product arrives FROZEN at 6130 (Canning Vale, WA)
2. **Thawing:** Product is thawed at 6130 facility
3. **Shelf Life Reset:** Upon thawing, shelf life resets to **14 days** (not 17)
4. **Storage:** 6130 stores thawed product in ambient conditions
5. **Market Release:** 6130 releases product to local WA market

**6130 Dual Role:**
- **Breadroom:** Receives forecast demand like other breadrooms
- **Thawing Facility:** Converts frozen product to ambient (14-day shelf life)
- **Distribution Center:** Stores and releases product to WA market

**Why Frozen Route:**
- **Distance:** Perth is ~3,200 km from manufacturing (Sydney/Melbourne area)
- **Shelf Life:** Frozen transport (120 days) enables buffer stock at Lineage
- **Flexibility:** Allows infrequent, large shipments rather than daily ambient deliveries
- **Cost Trade-off:** Frozen transport cost vs. extended shelf life and consolidation

### Lineage Frozen Storage Facility

**Location:** Not specified (possibly co-located with 6122 or strategic midpoint)

**Characteristics:**
- **Type:** External frozen storage (not a breadroom)
- **Storage Mode:** Frozen only (120-day shelf life maintained)
- **Purpose:** Intermediate buffer/consolidation for WA route
- **Capacity:** Unknown (should be sized for WA demand buffer)
- **Ownership:** External 3PL or owned facility

**Function:**
- **Consolidation:** Accumulate product from multiple production runs
- **Buffer Stock:** Maintain frozen inventory for WA demand smoothing
- **Frequency Management:** Enable less frequent large shipments to Perth
- **Risk Mitigation:** Buffer against transport delays or demand spikes

**Location ID Suggestion:** "LIN01" or keep as "Lineage"

## Multi-Step Path Examples

### Example 1: NSW Local Delivery (6105)
```
6122 (Manufacturing)
  → [Ambient/Frozen, Hub truck]
6104 (Moorebank Hub)
  → [Ambient, Local delivery]
6105 (Rydalmere)
```
**Shelf Life:** 17 days ambient (or 120→thaw→14 if frozen initially)

### Example 2: ACT Regional Delivery (6103)
```
6122 (Manufacturing)
  → [Ambient/Frozen, Hub truck]
6104 (Moorebank Hub)
  → [Ambient, Regional delivery]
6103 (Canberra)
```
**Shelf Life:** 17 days ambient (or 120→thaw→14 if frozen initially)

### Example 3: VIC Local Delivery (6123)
```
6122 (Manufacturing)
  → [Ambient/Frozen, Hub truck]
6125 (Keilor Park Hub)
  → [Ambient, Local delivery]
6123 (Clayton-Fairbank)
```
**Shelf Life:** 17 days ambient (or 120→thaw→14 if frozen initially)

### Example 4: SA Regional Delivery (6134)
```
6122 (Manufacturing)
  → [Ambient/Frozen, Hub truck]
6125 (Keilor Park Hub)
  → [Ambient, Regional delivery]
6134 (West Richmond SA)
```
**Shelf Life:** 17 days ambient (or 120→thaw→14 if frozen initially)

### Example 5: TAS Long-Haul Delivery (6120)
```
6122 (Manufacturing)
  → [Ambient/Frozen, Hub truck]
6125 (Keilor Park Hub)
  → [Ambient/Frozen, Long-haul including ferry]
6120 (Hobart)
```
**Shelf Life:** 17 days ambient (or 120→thaw→14 if frozen initially)
**Note:** May require frozen due to ferry transit time

### Example 6: QLD Direct Delivery (6110)
```
6122 (Manufacturing)
  → [Ambient/Frozen, Direct truck]
6110 (Burleigh Heads)
```
**Shelf Life:** 17 days ambient (or 120→thaw→14 if frozen initially)

### Example 7: WA Frozen-Buffered Delivery (6130) ⚠️ SPECIAL CASE
```
6122 (Manufacturing)
  → [FROZEN, Buffer truck]
Lineage (Frozen Storage) [Maintain 120-day shelf life]
  → [FROZEN, Long-haul to Perth]
6130 (Canning Vale) [THAWING OCCURS HERE]
  → [Ambient 14-day shelf life after thaw]
Market Release
```
**Critical:** Shelf life resets to **14 days** upon thawing at 6130

## State Transitions Along Routes

### Ambient-Only Routes
- **Product State:** Ambient throughout
- **Shelf Life:** 17 days (no transitions)
- **Transit Impact:** Days in transit reduce remaining shelf life
- **Destination:** Must arrive with ≥7 days remaining

### Frozen-Then-Thawed Routes (If Used)
- **Production:** Ambient or frozen after production
- **Transport:** Frozen (120-day shelf life)
- **Hub/Destination:** Thawed at destination
- **Post-Thaw:** 14 days shelf life (CRITICAL: Not 17!)
- **Market Release:** Must occur within 14 days and arrive at breadroom with ≥7 days

### WA Special Case (6130)
1. **6122 Production:** Ambient or frozen
2. **6122 → Lineage:** Frozen (120 days)
3. **Lineage Storage:** Frozen (120 days maintained)
4. **Lineage → 6130:** Frozen (120 days)
5. **At 6130:** **THAWED - Reset to 14 days**
6. **6130 Storage:** Ambient (14 days)
7. **Market Release:** Within 14 days, ≥7 days at customer

## Truck Departure Schedule from Manufacturing (6122)

### Truck Specifications

- **Capacity:** 44 pallets per truck
- **Pallet size:** 32 cases per pallet
- **Case size:** 10 units per case
- **Total truck capacity:** 44 pallets × 32 cases × 10 units = **14,080 units**
- **Critical constraint:** Partial pallets occupy full pallet space

### Morning Truck (Daily Monday-Friday)

**Standard Route (Mon, Tue, Thu, Fri):**
```
6122 (Manufacturing) → 6125 (Keilor Park Hub, VIC)
```

**Special Wednesday Route:**
```
6122 (Manufacturing) → Lineage (Frozen Storage) → 6125 (Keilor Park Hub, VIC)
```

**Characteristics:**
- Departs every weekday morning
- Loads D-1 production (previous day's production only)
- Capacity: 14,080 units
- Wednesday: Must allocate capacity between Lineage frozen drop and 6125 delivery
- Serves 6125 hub region (903,996 units total demand)

### Afternoon Truck (Day-Specific Destinations)

**Weekly Schedule:**

| Day | Destination | Route | Capacity |
|-----|-------------|-------|----------|
| **Monday** | 6104 | 6122 → 6104 (Moorebank Hub, NSW) | 14,080 units |
| **Tuesday** | 6110 | 6122 → 6110 (Burleigh Heads, QLD) | 14,080 units |
| **Wednesday** | 6104 | 6122 → 6104 (Moorebank Hub, NSW) | 14,080 units |
| **Thursday** | 6110 | 6122 → 6110 (Burleigh Heads, QLD) | 14,080 units |
| **Friday** | **6110 AND 6104** | **TWO TRUCKS** (double capacity) | 28,160 units |

**Characteristics:**
- Day-specific fixed destinations (cannot be changed)
- Loads D-1 production primarily
- Can load D0 (same-day) production if ready before departure
- Friday: Two afternoon trucks provide extra capacity for end-of-week shipments

**Weekly Shipment Frequency:**
- **6125:** 5 shipments/week (daily morning service)
- **6104:** 3 shipments/week (Mon/Wed/Fri afternoon)
- **6110:** 3 shipments/week (Tue/Thu/Fri afternoon)
- **Lineage:** 1 shipment/week (Wednesday morning)

### Hub Outbound Schedule

**From 6104 (Moorebank Hub):**
- **Destinations:** 6105 (Rydalmere), 6103 (Canberra)
- **Departure timing:** Morning departures (assumed)
- **Frequency:** Based on hub inventory and spoke demand

**From 6125 (Keilor Park Hub):**
- **Destinations:** 6123 (Clayton), 6134 (Adelaide), 6120 (Hobart)
- **Departure timing:** Morning departures (assumed)
- **Frequency:** Based on hub inventory and spoke demand

### Weekly Capacity Summary

| Route | Trucks/Week | Capacity/Truck | Weekly Capacity |
|-------|-------------|----------------|-----------------|
| Morning → 6125 | 5 | 14,080 | 70,400 units |
| Afternoon → 6104 | 3 | 14,080 | 42,240 units |
| Afternoon → 6110 | 3 | 14,080 | 42,240 units |
| **TOTAL** | **11** | | **154,880 units/week** |

**Capacity vs. Demand:**
- Total network demand: 2,407,299 units / 204 days = 11,800 units/day
- Weekly demand: ~82,600 units/week
- Weekly capacity: 154,880 units/week
- **Utilization:** 53% (significant headroom for variability)

### Wednesday Morning Lineage Routing

**Special Consideration:**

On Wednesday mornings, the truck must serve both Lineage (frozen buffer for WA) and 6125 (VIC/TAS/SA hub):

```
6122 → Lineage → 6125
       ↓
   [Drop frozen stock]
       ↓
   [Continue to 6125]
```

**Allocation Decision:**
- 44 pallets total must be split between two destinations
- Example: 14 pallets to Lineage + 30 pallets to 6125
- Trade-off: Frozen buffer (Lineage) vs. immediate hub service (6125)
- Optimization: Balance 6130 (WA) long-term needs with 6125 region daily demand

### Truck Loading Implications

### Fixed Routing (Phase 1-2)
- Truck destinations are predetermined by day of week
- Cannot change Monday's 6104 destination to 6110, for example
- Optimization focuses on: production quantities, batch timing, hub forwarding decisions

### Flexible Routing (Phase 3-4)
**Potential future optimization:**
- Dynamic truck-destination assignments based on demand
- May allow Tuesday truck to go to 6104 instead of 6110 if demand dictates
- Not currently implemented (requires approval/operational changes)

## Optimization Considerations

### Hub Consolidation Benefits
- **Reduced primary routes:** 4 primary vs. 9 direct routes
- **Truck utilization:** Larger consolidated shipments
- **Frequency:** More reliable daily service to hubs

### Hub Consolidation Costs
- **Additional handling:** Product handled twice (hub + final delivery)
- **Transit time:** Longer total time (2 legs vs. 1)
- **Shelf life impact:** More days consumed in transit

### Frozen vs. Ambient Trade-offs
- **Frozen benefits:** Extended shelf life (120 days), infrequent shipments, buffer stock
- **Frozen costs:** Higher transport cost, cold chain infrastructure, thawing operations
- **Optimal use:** Long-haul routes (TAS, WA) where ambient shelf life insufficient

### WA Route (6130) Specific
- **Optimization Challenge:** Balance frozen buffer stock at Lineage vs. shipment frequency
- **Thawing Timing:** Critical decision - thaw early (risk waste) or late (risk stockout)
- **Demand Variability:** Frozen buffer provides hedge against forecast errors

## Network Statistics

- **Total Locations:** 11 (1 manufacturing + 1 frozen storage + 9 breadrooms)
- **Total Route Legs:** 10 (4 primary + 5 secondary + 1 frozen buffer)
- **Hub Locations:** 2 (6104, 6125)
- **Direct Destinations:** 1 (6110)
- **Hub-Served Destinations:** 5 (6103, 6105, 6120, 6123, 6134)
- **Frozen-Buffered Destinations:** 1 (6130)
- **States Covered:** 6 (NSW, VIC, QLD, ACT, TAS, WA, SA)
- **Maximum Echelons:** 3 (6122 → Lineage → 6130)

## Future Extensions

**Potential Network Enhancements:**
- Additional regional hubs for better coverage
- Direct routes for high-volume breadrooms
- Alternative frozen facilities for other long-haul routes
- Cross-docking operations at hubs
- Reverse logistics for returns/waste
