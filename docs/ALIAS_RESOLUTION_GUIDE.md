# Product Alias Resolution Guide

## Overview

The data validation architecture includes **automatic product alias resolution** to handle mismatches between product IDs in different files (e.g., inventory uses SKU codes while forecast uses product names).

---

## ✅ YES, Aliases Are Fully Supported!

The `DataCoordinator` handles aliases through a **three-tier resolution strategy**:

### Tier 1: Exact Match
Tries to match product ID exactly as-is.

### Tier 2: SKU Lookup
If products have SKU codes, matches inventory SKU to product SKU.

### Tier 3: Alias Resolver
Uses `ProductAliasResolver` to map between different product ID formats.

---

## Auto-Loading Aliases (NEW!)

**The coordinator automatically loads aliases from your Excel files!**

### How It Works

When you call `load_validated_data()`, the coordinator:

1. Checks if an `alias_resolver` was provided
2. If not, tries to load from `network_file` (checks for 'Alias' sheet)
3. If not found, tries `forecast_file`
4. If not found, proceeds without aliases (warns if product IDs don't match)

**Code (lines 135-148 in data_coordinator.py):**
```python
# Auto-load alias resolver if not provided
if self.alias_resolver is None:
    try:
        # Try network file first (common location)
        self.alias_resolver = ProductAliasResolver(str(self.network_file))
        logger.info("✓ Loaded product aliases from network file")
    except Exception:
        # Try forecast file
        try:
            self.alias_resolver = ProductAliasResolver(str(self.forecast_file))
            logger.info("✓ Loaded product aliases from forecast file")
        except Exception:
            logger.info("No alias sheet found (OK if IDs consistent)")
```

---

## Real-World Example

### Your Current Data

**Alias Sheet in Network_Config.xlsx:**
```
Alias1 (Canonical)              | Alias2  | Alias3  | Alias4
--------------------------------|---------|---------|--------
HELGAS GFREE MIXED GRAIN 500G   | 168847  | 176283  | 184222
HELGAS GFREE TRAD WHITE 470G    | 168846  | 176299  | 184226
HELGAS GFREE WHOLEM 500G        | 168848  | 176284  | 184223
WONDER GFREE WHITE 470G         | 179649  | 179651  | 184227
WONDER GFREE WHOLEM 500G        | 179650  | 179652  | 184228
```

**Forecast uses:** Alias1 (product names)
**Inventory uses:** Alias2, Alias3, Alias4 (numeric SKUs)

### Resolution Result

```
✓ Loaded product aliases from network file

Inventory entries: 49 (49,581 units total)
  - All numeric SKUs automatically mapped to product names
  - 168846 → HELGAS GFREE TRAD WHITE 470G ✓
  - 168847 → HELGAS GFREE MIXED GRAIN 500G ✓
  - (and so on...)

Common products: 5/5
✓ ALL products have inventory matched via alias resolution!
```

---

## Usage Patterns

### Pattern 1: Zero Configuration (Automatic)

```python
from src.validation.data_coordinator import load_validated_data

# Just provide file paths - aliases loaded automatically!
data = load_validated_data(
    forecast_file="data/forecast.xlsm",
    network_file="data/network.xlsx",  # Has Alias sheet
    inventory_file="data/inventory.xlsx",
    planning_weeks=4
)

# Aliases automatically resolved
print(f"Inventory matched: {len(data.inventory_entries)} entries")
```

**Requirements:**
- Network or forecast file must have 'Alias' sheet
- Alias sheet format: First row = headers, column names = Alias1, Alias2, ...
- Alias1 = canonical product ID
- Other columns = alternative IDs/SKUs

### Pattern 2: Explicit Alias Resolver

```python
from src.validation.data_coordinator import load_validated_data
from src.parsers.product_alias_resolver import ProductAliasResolver

# Load from specific file
resolver = ProductAliasResolver("data/product_mappings.xlsx")

# Pass to coordinator
data = load_validated_data(
    forecast_file="data/forecast.xlsm",
    network_file="data/network.xlsx",
    inventory_file="data/inventory.xlsx",
    alias_resolver=resolver,  # Explicit resolver
    planning_weeks=4
)
```

### Pattern 3: No Aliases Needed

```python
# If all files use consistent product IDs, aliases not needed
data = load_validated_data(
    forecast_file="data/forecast.xlsm",
    network_file="data/network.xlsx",
    planning_weeks=4
)

# Coordinator logs: "No alias sheet found (this is OK if product IDs are consistent)"
```

---

## Resolution Strategy Details

When resolving inventory product IDs, the coordinator tries (in order):

```python
# For each inventory entry with product_key:

# 1. Exact match
if product_key in product_by_id:
    use product_key

# 2. SKU match
elif product_key in product_by_sku:
    use product.id

# 3. Alias resolution
elif alias_resolver:
    canonical = alias_resolver.resolve_product_id(product_key)
    if canonical in product_by_id:
        use canonical

# 4. Not resolved
else:
    warn("Could not resolve product_key")
    skip this inventory entry
```

---

## Validation Checks

The coordinator validates:

1. **All resolved inventory products exist in demand**
   - Error if inventory has products not in forecast
   - Suggests checking if inventory uses different ID format

2. **All demand products exist in product list**
   - Error if forecast has products not registered
   - Suggests adding to Products sheet

3. **Alias resolution statistics**
   - Logs how many products were resolved
   - Warns about unresolved products

---

## Troubleshooting

### Issue: "Could not resolve X product IDs from inventory"

**Cause:** Some inventory SKUs don't match any alias

**Solutions:**
1. Add missing SKUs to Alias sheet
2. Check if inventory uses different SKU format
3. Inspect unresolved SKUs: Check the warning message sample

**Example:**
```
WARNING: Could not resolve 10 product IDs from inventory.
Sample: ['184229', '184230', '184231']

Action: Add these SKUs to Alias sheet or check if they're obsolete products
```

### Issue: "Product 'X' not in forecast"

**Cause:** Inventory has products that aren't in demand forecast

**Solutions:**
1. Check if product is obsolete (remove from inventory)
2. Add product to forecast if it should be planned
3. Update Alias sheet to map correctly

---

## Benefits

### Before Alias Resolution

```
Inventory: 49 entries (49,581 units)
Matched to demand: 0 entries
Result: Model thinks inventory = 0
        → Zero production bug!
```

### After Alias Resolution

```
Inventory: 49 entries (49,581 units)
Matched to demand: 49 entries ✓
Result: Model uses all inventory correctly
        → Production optimized properly!
```

---

## Alias Sheet Format

**Location:** Network_Config.xlsx (or Forecast file)
**Sheet Name:** 'Alias'

**Format:**
```
Alias1                        | Alias2  | Alias3  | Alias4  | ...
------------------------------|---------|---------|---------|----
PRODUCT_NAME_1                | SKU_1A  | SKU_1B  | SKU_1C  |
PRODUCT_NAME_2                | SKU_2A  | SKU_2B  | SKU_2C  |
```

**Rules:**
- **Alias1** = Canonical product ID (used in forecast)
- **Alias2, Alias3, ...** = Alternative IDs (SKUs, old codes, etc.)
- Any column can be used in any file
- Resolver maps all aliases to Alias1 (canonical)

---

## Summary

**Q: Does the data coordinator handle aliases?**

**A: YES!** And it does so automatically:
- ✅ Auto-loads from Alias sheet in network/forecast files
- ✅ Three-tier resolution strategy (exact, SKU, alias)
- ✅ Validates all mappings
- ✅ Clear warnings for unresolved products
- ✅ Supports both explicit and automatic loading

**Result in your case:**
- 49 inventory entries with numeric SKUs
- Auto-mapped to 5 product names via Alias sheet
- 100% match rate (5/5 products)
- **Zero production bug FIXED!**
