# Cost Parameter Audit Report
**Date:** 2025-10-18
**Model:** UnifiedNodeModel

## Executive Summary

Out of **17 cost parameters** in Network_Config.xlsx CostParameters sheet:
- **6 are USED** by the optimization model
- **7 are REDUNDANT** (parsed but never used)
- **4 are CONDITIONALLY USED** (depending on configuration)

## Detailed Analysis

### ✅ USED Cost Parameters (6)

These parameters are actively used in the UnifiedNodeModel objective function:

| Parameter | Usage | Location in Code |
|-----------|-------|------------------|
| `production_cost_per_unit` | Production cost component | Line 2264: `production_cost += cost * production[...]` |
| `shortage_penalty_per_unit` | Penalty for unmet demand | Line 2337: `penalty_cost += penalty * shortage[...]` |
| `storage_cost_frozen_per_unit_day` | Unit-based frozen holding cost | Line 2353: Used in holding cost calculation |
| `storage_cost_ambient_per_unit_day` | Unit-based ambient holding cost | Line 2354: Used in holding cost calculation |
| `storage_cost_per_pallet_day_frozen` | Pallet-based frozen holding cost | Line 2349: Used when pallet tracking enabled |
| `storage_cost_per_pallet_day_ambient` | Pallet-based ambient holding cost | Line 2350: Used when pallet tracking enabled |

### ⚠️ CONDITIONALLY USED (4)

These parameters are used only in specific configurations:

| Parameter | Condition | Usage |
|-----------|-----------|-------|
| `storage_cost_fixed_per_pallet` | Used only if state-specific costs not set | Line 2346: Fallback via `get_fixed_pallet_costs()` |
| `storage_cost_fixed_per_pallet_frozen` | Used when pallet tracking enabled for frozen | Line 2346: State-specific fixed cost |
| `storage_cost_fixed_per_pallet_ambient` | Used when pallet tracking enabled for ambient | Line 2346: State-specific fixed cost |
| `waste_cost_multiplier` | **NEVER USED IN OPTIMIZATION** (only in helper methods) | CostStructure.calculate_waste_cost() - not called by model |

### ❌ REDUNDANT Cost Parameters (7)

These parameters are **parsed and stored but NEVER used** by the optimization model:

#### 1. Labor Costs (3 parameters - REDUNDANT)

| Parameter | Why Redundant |
|-----------|---------------|
| `default_regular_rate` | **Uses LaborCalendar.regular_rate instead** (per-date rates) |
| `default_overtime_rate` | **Uses LaborCalendar.overtime_rate instead** (per-date rates) |
| `default_non_fixed_rate` | **Uses LaborCalendar.non_fixed_rate instead** (per-date rates) |

**Evidence:**
- UnifiedNodeModel lines 2286-2303: Retrieves rates directly from `labor_day.regular_rate`, `labor_day.overtime_rate`, `labor_day.non_fixed_rate`
- No references to `self.cost_structure.default_*_rate` anywhere in UnifiedNodeModel

**Impact:** These three parameters exist in CostParameters but are completely ignored. The model exclusively uses the LaborCalendar sheet for labor rates.

#### 2. Transport Costs (3 parameters - REDUNDANT)

| Parameter | Why Redundant |
|-----------|---------------|
| `transport_cost_frozen_per_unit` | **Uses route.cost_per_unit from Routes sheet instead** |
| `transport_cost_ambient_per_unit` | **Uses route.cost_per_unit from Routes sheet instead** |
| `truck_fixed_cost` | **Not implemented in current model** |

**Evidence:**
- UnifiedNodeModel line 2274: `transport_cost += route.cost_per_unit * shipment[...]`
- No references to `self.cost_structure.transport_cost_*` in UnifiedNodeModel
- Routes sheet already specifies `cost` per route (which becomes `route.cost_per_unit`)

**Impact:** Transport costs come from the Routes sheet on a per-route basis, not from CostParameters. The frozen/ambient distinction is handled by having separate route entries.

#### 3. Setup Cost (1 parameter - REDUNDANT)

| Parameter | Why Redundant |
|-----------|---------------|
| `setup_cost` | **No setup/changeover costs in objective function** |

**Evidence:**
- Defined in CostStructure model (line 45-48)
- No references to `setup_cost` in UnifiedNodeModel objective function
- Changeover tracking exists (binary variables) but no cost applied

**Impact:** The model tracks product changeovers but assigns zero cost to them.

## Recommendations

### Option 1: Remove Redundant Parameters (Recommended)

**Remove from Network_Config.xlsx CostParameters sheet:**
- `default_regular_rate`
- `default_overtime_rate`
- `default_non_fixed_rate`
- `transport_cost_frozen_per_unit`
- `transport_cost_ambient_per_unit`
- `truck_fixed_cost`
- `setup_cost`

**Benefits:**
- Eliminates confusion (users won't set values that are ignored)
- Clearer configuration (parameters match actual model behavior)
- Easier maintenance (fewer parameters to document)

**Keep only:**
- `production_cost_per_unit`
- `shortage_penalty_per_unit`
- `storage_cost_frozen_per_unit_day`
- `storage_cost_ambient_per_unit_day`
- `storage_cost_per_pallet_day_frozen`
- `storage_cost_per_pallet_day_ambient`
- `storage_cost_fixed_per_pallet` (fallback)
- `storage_cost_fixed_per_pallet_frozen` (state-specific)
- `storage_cost_fixed_per_pallet_ambient` (state-specific)
- `waste_cost_multiplier` (keep for future use/documentation)

### Option 2: Document as "Reference Only"

Add a column to CostParameters sheet indicating which are used vs reference:

| cost_type | value | unit | status |
|-----------|-------|------|--------|
| default_regular_rate | 25 | $/hour | REFERENCE ONLY (use LaborCalendar) |
| transport_cost_frozen_per_unit | 0.5 | $/unit | REFERENCE ONLY (use Routes sheet) |

### Option 3: Implement Missing Features

If you want to USE these parameters:
- **Setup costs:** Add setup cost to objective function (requires binary setup variables)
- **Truck fixed costs:** Add fixed cost per truck departure (requires binary truck usage variables)
- **Default labor rates:** Use as fallback when LaborCalendar date is missing

## Current Model Behavior

### Labor Costs
```
Source: LaborCalendar sheet (per-date rates)
Fixed days: regular_rate × fixed_hours + overtime_rate × overtime_hours
Non-fixed days: non_fixed_rate × paid_hours (min 4 hours)
```

### Transport Costs
```
Source: Routes sheet (cost column)
Formula: route.cost_per_unit × shipment_quantity
Note: Different routes can have different costs (frozen vs ambient routes)
```

### Storage Costs
```
Source: CostParameters sheet
Pallet-based: pallet_count × daily_rate_per_pallet (if enabled)
Unit-based: inventory_units × daily_rate_per_unit (fallback)
State-specific: Different costs for frozen vs ambient
```

### Production Costs
```
Source: CostParameters sheet
Formula: production_cost_per_unit × production_quantity
```

## File Impact Summary

**Files to update if removing redundant parameters:**
1. `data/examples/Network_Config.xlsx` - Remove rows from CostParameters sheet
2. `src/models/cost_structure.py` - Mark fields as deprecated or remove
3. `src/parsers/excel_parser.py` - Update parsing logic
4. `data/examples/EXCEL_TEMPLATE_SPEC.md` - Update documentation
5. `CLAUDE.md` - Update cost parameter list

**Backward Compatibility:**
- Removing from Excel: Old files will still parse (parser uses defaults)
- Removing from CostStructure: Breaking change (would need deprecation period)
- Recommended: Keep in CostStructure but mark as deprecated, remove from Excel template

---

## Next Steps

1. **Confirm removal strategy** with stakeholders
2. **Update Excel template** to remove redundant parameters
3. **Update documentation** to clarify which sheet contains which costs
4. **Consider adding validation** to warn users if they set redundant parameters
5. **Add migration guide** if removing from CostStructure model

## Quick Reference Table

| Cost Parameter | Excel Sheet | Status | Used By Model | Notes |
|----------------|-------------|--------|---------------|-------|
| **Production Costs** |
| `production_cost_per_unit` | CostParameters | ✅ USED | Yes | Core production cost |
| `setup_cost` | CostParameters | ❌ REDUNDANT | No | Changeover tracking exists but zero cost |
| **Labor Costs** |
| `default_regular_rate` | CostParameters | ❌ REDUNDANT | No | Use LaborCalendar.regular_rate instead |
| `default_overtime_rate` | CostParameters | ❌ REDUNDANT | No | Use LaborCalendar.overtime_rate instead |
| `default_non_fixed_rate` | CostParameters | ❌ REDUNDANT | No | Use LaborCalendar.non_fixed_rate instead |
| `regular_rate` (per date) | LaborCalendar | ✅ USED | Yes | Actual rate used by model |
| `overtime_rate` (per date) | LaborCalendar | ✅ USED | Yes | Actual rate used by model |
| `non_fixed_rate` (per date) | LaborCalendar | ✅ USED | Yes | Actual rate used by model |
| **Transport Costs** |
| `transport_cost_frozen_per_unit` | CostParameters | ❌ REDUNDANT | No | Use Routes.cost instead |
| `transport_cost_ambient_per_unit` | CostParameters | ❌ REDUNDANT | No | Use Routes.cost instead |
| `truck_fixed_cost` | CostParameters | ❌ REDUNDANT | No | Not implemented |
| `cost` (per route) | Routes | ✅ USED | Yes | Actual cost used by model |
| **Storage Costs - Unit-Based** |
| `storage_cost_frozen_per_unit_day` | CostParameters | ✅ USED | Yes | Unit-based frozen holding cost |
| `storage_cost_ambient_per_unit_day` | CostParameters | ✅ USED | Yes | Unit-based ambient holding cost |
| **Storage Costs - Pallet-Based** |
| `storage_cost_per_pallet_day_frozen` | CostParameters | ⚠️ CONDITIONAL | When pallet tracking enabled | Daily frozen pallet cost |
| `storage_cost_per_pallet_day_ambient` | CostParameters | ⚠️ CONDITIONAL | When pallet tracking enabled | Daily ambient pallet cost |
| `storage_cost_fixed_per_pallet` | CostParameters | ⚠️ CONDITIONAL | Fallback for both states | DEPRECATED: use state-specific |
| `storage_cost_fixed_per_pallet_frozen` | CostParameters | ⚠️ CONDITIONAL | When pallet tracking enabled | State-specific fixed cost |
| `storage_cost_fixed_per_pallet_ambient` | CostParameters | ⚠️ CONDITIONAL | When pallet tracking enabled | State-specific fixed cost |
| **Penalty Costs** |
| `waste_cost_multiplier` | CostParameters | ⚠️ CONDITIONAL | Helper method only | Not in objective function |
| `shortage_penalty_per_unit` | CostParameters | ✅ USED | Yes | Demand shortage penalty |

**Legend:**
- ✅ USED = Actively used in optimization model
- ❌ REDUNDANT = Parsed but never used (can be removed)
- ⚠️ CONDITIONAL = Used only in specific configurations

## Summary Statistics

- **Total parameters in Network_Config.xlsx:** 17
- **Actually used by model:** 6 (35%)
- **Redundant (can be removed):** 7 (41%)
- **Conditionally used:** 4 (24%)

**Cost Data Sources:**
- **CostParameters sheet:** Production costs, storage costs, shortage penalties
- **LaborCalendar sheet:** Labor rates (daily)
- **Routes sheet:** Transport costs (per route)
