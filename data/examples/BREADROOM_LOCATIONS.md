# Breadroom Locations

## Overview

These are the destination breadroom locations extracted from the **Gfree Forecast.xlsm** file. All breadrooms are Quality Bakers Australia (QBA) facilities receiving gluten-free bread products from the manufacturing site (ID: 6122).

## Breadroom Network

### Complete List (9 Locations)

| Location ID | Location Name | State/Territory | Region | Note |
|-------------|---------------|-----------------|--------|------|
| 6103 | QBA-Canberra | ACT | Southeast | Australian Capital Territory |
| 6104 | QBA-Moorebank | NSW | Southeast | Greater Sydney |
| 6105 | QBA-Rydalmere | NSW | Southeast | Greater Sydney |
| 6110 | QBA-Burleigh Heads | QLD | Northeast | Gold Coast region |
| 6120 | QBA-Hobart | TAS | Southeast | Tasmania |
| 6123 | QBA-Clayton - Fairbank | VIC | Southeast | Greater Melbourne |
| 6125 | QBA -Keilor Park | VIC | Southeast | Greater Melbourne |
| 6130 | QBA-Canning Vale | WA | West | Greater Perth |
| 6134 | QBA-West Richmond SA | SA | Central | Greater Adelaide |

### Geographic Distribution

**New South Wales (2):**
- 6104 - Moorebank
- 6105 - Rydalmere

**Victoria (2):**
- 6123 - Clayton - Fairbank
- 6125 - Keilor Park

**Queensland (1):**
- 6110 - Burleigh Heads

**Australian Capital Territory (1):**
- 6103 - Canberra

**Tasmania (1):**
- 6120 - Hobart

**Western Australia (1):**
- 6130 - Canning Vale

**South Australia (1):**
- 6134 - West Richmond SA

## Manufacturing Source

**Manufacturing Site:**
- **Location ID:** 6122 (per project specification)
- **Type:** Manufacturing facility
- **Function:** Production of all gluten-free bread products
- **Products:** 5 SKUs (Helgas and Wonder gluten-free varieties)

## Supply Chain Structure

### Network Topology

The distribution network follows a **2-echelon hub-and-spoke + frozen buffer** design:

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

**Network Layers:**
- **Tier 1:** Manufacturing (6122)
- **Tier 2:** Regional hubs (6104, 6125) + Direct (6110) + Frozen buffer (Lineage)
- **Tier 3:** Final breadrooms + Thawing facility (6130)

### Hub Assignments

#### Hub 1: 6104 (QBA-Moorebank, NSW)
**Serves:** NSW & ACT region

**Dual Role:**
1. **Regional Distribution Hub** - Receives consolidated shipments from manufacturing, forwards to spoke locations
2. **Local Breadroom** - Has its own independent demand forecast (432,595 units over 204 days)

**Spoke Destinations:**
- 6105 - QBA-Rydalmere (NSW) - Local Sydney (301,846 units forecasted)
- 6103 - QBA-Canberra (ACT) - Regional NSW to ACT (115,400 units forecasted)

**Total Hub Region Demand:** 849,841 units (6104 local + 6105 + 6103)

**Function:** Consolidation point for NSW and ACT deliveries from Melbourne/Sydney manufacturing area

**Critical Note:** The forecast for 6104 represents ONLY 6104's local market demand, NOT the demand for 6105 or 6103. Each location has an independent forecast.

#### Hub 2: 6125 (QBA-Keilor Park, VIC)
**Serves:** VIC, TAS, SA region

**Dual Role:**
1. **Regional Distribution Hub** - Receives consolidated shipments from manufacturing, forwards to spoke locations
2. **Local Breadroom** - Has its own independent demand forecast (258,739 units over 204 days)

**Spoke Destinations:**
- 6123 - QBA-Clayton-Fairbank (VIC) - Local Melbourne (339,750 units forecasted)
- 6134 - QBA-West Richmond SA (SA) - Regional VIC to SA (247,050 units forecasted)
- 6120 - QBA-Hobart (TAS) - Long-haul VIC to TAS (58,458 units forecasted)

**Total Hub Region Demand:** 903,996 units (6125 local + 6123 + 6134 + 6120)

**Function:** Consolidation point for Victoria and southern/island states

**Critical Note:** The forecast for 6125 represents ONLY 6125's local market demand, NOT the demand for 6123, 6134, or 6120. Each location has an independent forecast.

### Location Classification by Routing

**Regional Hubs (2 locations):**
- 6104 - Moorebank (NSW/ACT Hub)
- 6125 - Keilor Park (VIC/TAS/SA Hub)

**Hub-Served Breadrooms (5 locations):**
- 6103 - Canberra (via 6104)
- 6105 - Rydalmere (via 6104)
- 6120 - Hobart (via 6125)
- 6123 - Clayton-Fairbank (via 6125)
- 6134 - West Richmond SA (via 6125)

**Direct from Manufacturing (1 location):**
- 6110 - Burleigh Heads (QLD)

**Frozen-Buffered with Thawing Operation (1 location):**
- 6130 - Canning Vale (WA) - ⚠️ **Special Case**

### Special Case: 6130 (Canning Vale, WA)

**Route:** 6122 → Lineage (frozen storage) → 6130

**Unique Characteristics:**
- **Transport Mode:** FROZEN throughout (~3,200 km distance)
- **Intermediate Storage:** Lineage external frozen facility
- **Thawing Point:** Product thawed AT 6130 destination
- **Shelf Life Reset:** After thawing, shelf life resets to **14 days** (not 17)
- **Dual Role:** 6130 acts as:
  1. Receiving breadroom for WA demand
  2. Thawing facility (frozen → ambient conversion)
  3. Storage/distribution center for WA market release

**Why Frozen Route:**
- Perth is extremely distant (~3,200 km)
- Ambient 17-day shelf life insufficient for transit + market release
- Frozen transport (120 days) enables buffer stock and less frequent shipments
- Thawing at destination provides 14-day ambient shelf life for local market

### Key Characteristics

- **Total Network Nodes:** 11 (1 manufacturing + 1 frozen storage + 9 breadrooms)
- **Total Route Legs:** 10 (4 primary + 5 secondary + 1 frozen buffer)
- **Geographic Spread:** Nationwide across 6 Australian states/territories
- **Hub Consolidation:** 5 of 9 breadrooms served via hubs (56%)
- **Direct Routes:** 1 breadroom (11%)
- **Special Frozen Route:** 1 breadroom with thawing operation (11%)
- **Minimum Shelf Life Policy:** 7 days remaining at breadroom receipt

## Forecast Structure and Demand Independence

### Critical Understanding: Independent Forecasts

**All 9 locations have independent demand forecasts:**
- Each location's forecast represents ONLY that location's local market demand
- Hub forecasts (6104, 6125) do NOT include spoke location demand
- Total network demand = sum of all 9 independent forecasts = 2,407,299 units

**Hub Demand Allocation Challenge:**

When product arrives at a hub (e.g., 6104), it must be allocated between:
1. **Local market fulfillment** - Satisfy 6104's own demand (432,595 units)
2. **Forward to spokes** - Send to 6105 (301,846 units) and 6103 (115,400 units)

**Optimization Implications:**
- Product at hub can serve local demand OR be forwarded (allocation decision)
- Hub must receive enough for: local demand + all spoke demands + safety stock
- Timing matters: local demand can be filled immediately, spoke delivery adds transit time
- Shelf life consumed differently: local use vs. forward with additional transit days

**Example: 6104 Hub Region**
```
Manufacturing (6122) → 6104 Hub (receives 849,841+ units)
                         ├─ 6104 local: 432,595 units (immediate)
                         ├─ Forward to 6105: 301,846 units (+ transit time)
                         └─ Forward to 6103: 115,400 units (+ transit time)
```

### Demand by Location (Total Forecast: 204 days, 5 products)

| Location | Name | Region | Total Demand | % of Network |
|----------|------|--------|--------------|--------------|
| 6110 | QBA-Burleigh Heads | QLD | 542,121 | 22.5% |
| 6104 | QBA-Moorebank | NSW (Hub) | 432,595 | 18.0% |
| 6123 | QBA-Clayton-Fairbank | VIC | 339,750 | 14.1% |
| 6105 | QBA-Rydalmere | NSW | 301,846 | 12.5% |
| 6125 | QBA-Keilor Park | VIC (Hub) | 258,739 | 10.7% |
| 6134 | QBA-West Richmond SA | SA | 247,050 | 10.3% |
| 6103 | QBA-Canberra | ACT | 115,400 | 4.8% |
| 6130 | QBA-Canning Vale | WA | 111,341 | 4.6% |
| 6120 | QBA-Hobart | TAS | 58,458 | 2.4% |
| **TOTAL** | | | **2,407,299** | **100%** |

**Hub Region Totals:**
- 6104 Hub Region (NSW/ACT): 849,841 units (35.3%)
- 6125 Hub Region (VIC/TAS/SA): 903,996 units (37.6%)
- 6110 Direct (QLD): 542,121 units (22.5%)
- 6130 Frozen Route (WA): 111,341 units (4.6%)

## Network Design Considerations

### Hub-and-Spoke Benefits

**Advantages:**
- Reduced primary routes (4 vs. 9 direct)
- Better truck utilization via consolidation
- More frequent service to high-volume hubs
- Economies of scale in primary transport

**Trade-offs:**
- Additional handling at hubs
- Longer total transit time (2 legs vs. 1)
- More shelf life consumed in multi-step routes

### Route Planning Considerations

Each route requires:
1. **Origin-destination definition** (hub or direct)
2. **Transport mode selection** (frozen vs. ambient)
3. **Transit time specification** (varies by distance and mode)
4. **Intermediate storage** (Lineage for WA route)
5. **Thawing operations** (6130 only)

### Distance & Mode Groupings

**Short-haul (<100 km) - Ambient:**
- 6105, 6123 (local metro from hubs)

**Medium-haul (100-500 km) - Ambient:**
- 6103, 6110, 6134

**Long-haul (>500 km) - Ambient or Frozen:**
- 6120 (Tasmania - ferry crossing)

**Very long-haul (>3,000 km) - Frozen Required:**
- 6130 (Western Australia - frozen buffer + thawing)

### Truck Loading Strategy

With 2 daily truck departures (morning/afternoon) from manufacturing:

**Fixed routing (Phase 1-2):**
- **Truck 1:** Hub 6104 (NSW/ACT hub truck)
- **Truck 2:** Hub 6125 (VIC/TAS/SA hub truck)
- **Alternate trucks:** 6110 (QLD direct), Lineage (WA frozen buffer)

**Flexible routing (Phase 3-4):**
- Optimization determines truck-destination assignments
- Based on production volumes, demand, capacity, cost

## Test Data Requirements

When creating test scenarios, these breadrooms should be used as:
- **Demand points** in forecast data
- **Destination locations** in route definitions
- **Truck destination assignments** in truck schedules
- **Service level targets** in optimization objectives

## Future Extensions

**Possible additions:**
- GPS coordinates for each breadroom (for distance calculations)
- Delivery windows (time constraints for breadroom receiving)
- Storage capacity at each breadroom
- Minimum order quantities per breadroom
- Breadroom-specific shelf life policies (if they vary)
