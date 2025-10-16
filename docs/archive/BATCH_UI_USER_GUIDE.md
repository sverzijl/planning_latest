# Batch Tracking UI - User Guide

## Introduction

The enhanced Daily Inventory Snapshot now displays comprehensive batch-level tracking information, including production dates, age, shelf life remaining, and complete traceability through the supply chain network.

This guide explains how to use the new batch tracking features.

## Prerequisites

### Enable Batch Tracking

To see batch-level information, ensure batch tracking is enabled when running optimization:

```python
# When calling the optimization model
results = model.solve(
    use_batch_tracking=True,  # Enable batch tracking
    ...
)
```

### Required Data

The batch tracking UI requires:
- Production schedule with batch information
- Shipments with batch_id assignments
- Model solution with cohort_inventory (optional, for current locations)

## Feature 1: Enhanced Batch Inventory Display

### Accessing Batch Information

1. Navigate to **Daily Inventory Snapshot** in the Streamlit UI
2. Select a date using the date slider
3. Expand a location to view inventory details

### Understanding the Batch Table

Each batch displays the following information:

| Column | Description | Example |
|--------|-------------|---------|
| **Batch ID** | Unique identifier for the batch | BATCH-2025-10-01-176283-001 |
| **Product** | Product ID | 176283 |
| **Quantity** | Units in batch at this location | 1,200 |
| **Production Date** | When batch was manufactured | 2025-10-01 |
| **Age (days)** | Days since production | 3d |
| **Shelf Life Left** | Days until expiration | 14d |
| **Status** | Freshness indicator (see below) | 🟢 Fresh |

### Freshness Status Guide

The **Status** column shows the batch freshness with color-coding:

#### 🟢 Fresh (Green Background)
- **Shelf life remaining:** 10+ days
- **Meaning:** Batch is in good condition
- **Action:** Normal operations, no special handling needed

#### 🟡 Aging (Yellow Background)
- **Shelf life remaining:** 5-9 days
- **Meaning:** Batch is aging and should be prioritized
- **Action:** Ship soon, prioritize for near-term demand

#### 🔴 Near Expiry (Red Background)
- **Shelf life remaining:** 0-4 days
- **Meaning:** Batch is approaching expiration
- **Action:** URGENT - Ship immediately or risk waste

#### ⚫ Expired (Dark Red Background)
- **Shelf life remaining:** < 0 days (negative)
- **Meaning:** Batch has already expired
- **Action:** Remove from inventory, record as waste

### Sorting and Filtering

Use the controls above the location list to find specific inventory:

**Sort by:**
- **Inventory Level (High to Low)** - Locations with most inventory first
- **Inventory Level (Low to High)** - Locations with least inventory first
- **Location ID** - Alphabetical by location ID
- **Location Name** - Alphabetical by location name

**Filter:**
- **Show All** - All locations in network
- **Only With Inventory** - Locations that have inventory > 0
- **Only Empty** - Locations with zero inventory

### Example Workflow: Finding Aging Inventory

**Goal:** Identify all batches with less than 7 days shelf life remaining

**Steps:**
1. Navigate to Daily Inventory Snapshot
2. Select current date (or future date to plan ahead)
3. Expand each location with inventory
4. Look for yellow (🟡 Aging) or red (🔴 Near Expiry) rows
5. Note the batch IDs and quantities
6. Use batch traceability (see below) to investigate routing options

## Feature 2: Batch Traceability

### Accessing Batch Traceability

1. Scroll to the **Batch Traceability** section (below inventory, above demand satisfaction)
2. Click to expand **"🔍 Trace Individual Batches"**
3. Select a batch from the dropdown menu

The dropdown shows: `Batch ID - Product (Production Date) - Quantity`

Example: `BATCH-2025-10-01-176283-001 - 176283 (2025-10-01) - 5,200 units`

### Understanding Batch Journey

Once you select a batch, you'll see four sections:

#### 1. Production Information

Shows when and where the batch was produced:
- **Production Date:** Manufacturing date
- **Manufactured at:** Location with human-readable name
- **Product:** Product ID
- **Quantity:** Total units produced in this batch
- **Initial State:** AMBIENT or FROZEN
- **Assigned Truck:** Truck schedule ID (if assigned)

#### 2. Shipment History

Lists all shipments for this batch:
- **Shipment ID:** Unique shipment identifier
- **Route:** Origin → Destination (simplified)
- **Full Path:** Complete multi-leg route if applicable
- **Quantity:** Units shipped (may be partial batch)
- **Delivery Date:** When shipment arrived at destination
- **Transit Days:** Total days in transit
- **Transport Mode:** AMBIENT or FROZEN

**Note:** A single batch may have multiple shipments if split across routes.

#### 3. Current Locations

Shows where the batch currently resides (from model solution):
- **Location:** Location name and ID
- **Total Quantity:** Units at this location
- **State Breakdown:** Quantity by state (AMBIENT/FROZEN)

**If batch fully consumed:** Shows informational message

**If cohort inventory unavailable:** Shows message to run optimization with `use_batch_tracking=True`

#### 4. Timeline

Chronological list of all events for this batch:
- **Production** (Blue background)
- **Departure** (Yellow background)
- **Delivery** (Green background)

Each event shows:
- Date
- Event type
- Location
- Quantity
- Details

### Example Workflow: Investigating Delivery Delay

**Goal:** Understand why a batch hasn't arrived at destination yet

**Steps:**
1. Navigate to Batch Traceability
2. Select the batch in question
3. Review **Shipment History** to see planned delivery date
4. Check **Current Locations** to see where batch actually is
5. Review **Timeline** to identify when batch departed and when it should arrive
6. Compare expected vs. actual location to diagnose delay

## Feature 3: Daily Snapshot Navigation

### Date Selection

**Slider:**
- Drag the slider to any date in the planning horizon
- Dates shown in format: YYYY-MM-DD (Day)
- Example: 2025-10-02 (Wed)

**Navigation Buttons:**
- **⬅️ Previous Day:** Move back one day
- **Next Day ➡️:** Move forward one day

**Keyboard Shortcuts:**
- Press button, then use keyboard to navigate

### Summary Metrics

At the top of each snapshot, you'll see:

| Metric | Description |
|--------|-------------|
| **Total Inventory** | Sum of all inventory across all locations |
| **In Transit** | Quantity currently being transported |
| **Production** | Total produced on this date |
| **Demand** | Total demand for this date |

Use these to quickly assess overall system state.

## Common Use Cases

### Use Case 1: Daily Inventory Check

**Frequency:** Daily (morning)

**Steps:**
1. Open Daily Inventory Snapshot
2. Select today's date
3. Review summary metrics
4. Scan location inventory for red (🔴) batches
5. Take action on any near-expiry inventory

**Expected Time:** 2-3 minutes

### Use Case 2: Weekly Aging Inventory Review

**Frequency:** Weekly (Monday morning)

**Steps:**
1. Open Daily Inventory Snapshot
2. Select current date
3. Filter to "Only With Inventory"
4. Expand each location
5. Note all yellow (🟡) and red (🔴) batches
6. Plan priority shipments for the week

**Expected Time:** 10-15 minutes

### Use Case 3: Root Cause Analysis for Waste

**Frequency:** As needed (when waste occurs)

**Steps:**
1. Identify the wasted batch ID from waste report
2. Open Daily Inventory Snapshot
3. Navigate to Batch Traceability
4. Select the wasted batch
5. Review **Shipment History** - Were shipments delayed?
6. Review **Timeline** - Was there sufficient lead time?
7. Investigate why batch wasn't consumed before expiration

**Expected Time:** 5-10 minutes

### Use Case 4: Verifying FIFO Consumption

**Frequency:** As needed (audit/verification)

**Steps:**
1. Select a destination location with demand
2. Expand location inventory to see batches
3. Sort batches by production date (oldest first)
4. Verify that oldest batches are consumed first
5. Check for any violations (newer batches consumed before older)

**Expected Time:** 5 minutes per location

### Use Case 5: Planning Emergency Shipment

**Frequency:** As needed (when red batches detected)

**Steps:**
1. Identify batch with <5 days shelf life
2. Open Batch Traceability for that batch
3. Review **Current Locations** - Where is it now?
4. Review **Shipment History** - Where can it go?
5. Calculate transit time to nearest demand destination
6. If transit time < shelf life remaining, create emergency shipment
7. Otherwise, record as expected waste

**Expected Time:** 10 minutes

## Best Practices

### 1. Daily Monitoring
- Check inventory snapshot every morning
- Focus on red (🔴) and yellow (🟡) batches
- Take proactive action on aging inventory

### 2. Threshold Awareness
- **< 10 days:** Plan shipment routes
- **< 5 days:** Execute shipments immediately
- **< 2 days:** Likely waste, prepare documentation

### 3. Batch Selection
- Always verify batch ID when investigating issues
- Use traceability to confirm routing and timing
- Cross-reference with actual warehouse data

### 4. Preventive Actions
- Ship aging inventory to high-demand locations
- Balance inventory across network to minimize age
- Adjust production schedule if seeing chronic waste

### 5. Data Quality
- Report any discrepancies between UI and reality
- Verify that batch tracking is enabled (`use_batch_tracking=True`)
- Ensure model solution includes cohort inventory

## Troubleshooting

### Problem: No Batch Information Shown

**Possible Causes:**
1. Batch tracking not enabled in optimization
2. Production schedule missing batch data
3. UI in legacy mode

**Solutions:**
1. Re-run optimization with `use_batch_tracking=True`
2. Verify production schedule has `production_batches` list
3. Check results dictionary for `use_batch_tracking` flag

### Problem: Batch Traceability Section Missing

**Possible Causes:**
1. Batch tracking disabled
2. No production batches in schedule

**Solutions:**
1. Enable batch tracking (see above)
2. Verify production schedule is not empty

### Problem: Current Locations Shows "No Data"

**Possible Causes:**
1. Model solution missing cohort_inventory
2. Batch fully consumed
3. Wrong production date match

**Solutions:**
1. Ensure model solution includes cohort_inventory
2. Verify batch hasn't been completely consumed by demand
3. Check that batch production_date matches cohort key

### Problem: Color Coding Not Showing

**Possible Causes:**
1. Browser doesn't support styling
2. DataFrame rendering issue

**Solutions:**
1. Refresh browser
2. Try different browser (Chrome, Firefox recommended)
3. Check Streamlit version (>=1.20 recommended)

### Problem: Timeline Events Out of Order

**Possible Causes:**
1. Shipment dates incorrectly calculated
2. Data inconsistency

**Solutions:**
1. Verify shipment delivery_date and transit_days are correct
2. Check production_date matches across batches and shipments
3. Review optimization results for data integrity

## Advanced Features

### Filtering by Shelf Life (Future Enhancement)

Currently, you can visually scan for color-coded batches. Future versions may include:
- Filter to show only batches with < N days remaining
- Sort batches by shelf life remaining
- Batch alerts/notifications

### Batch Performance Metrics (Future Enhancement)

Future versions may include:
- Average batch age at consumption
- Waste rate by batch
- FIFO compliance score
- Batch throughput time

### Export Batch Reports (Future Enhancement)

Future versions may include:
- CSV export of batch inventory
- PDF batch traceability reports
- Historical batch tracking

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Next Day | Click "Next Day ➡️" button |
| Previous Day | Click "⬅️ Previous Day" button |
| Expand/Collapse Location | Click expander header |
| Expand/Collapse Traceability | Click expander header |

## Tips and Tricks

### Tip 1: Quick Scan Strategy
Look for color first, then read details. Red rows immediately indicate problems.

### Tip 2: Compare Dates
Use navigation buttons to step through consecutive days and watch batch age increase.

### Tip 3: Batch ID Patterns
Batch IDs follow pattern: `BATCH-{production_date}-{product_id}-{sequence}`
- Helps identify production campaigns
- Sequence number indicates daily production order

### Tip 4: Cross-Reference with Network Graph
Use Network Graph view to understand routing options, then use batch traceability to verify actual routes used.

### Tip 5: Bookmark Critical Batches
Note down batch IDs of concern in a separate document for ongoing monitoring.

## Support and Feedback

### Getting Help

If you encounter issues or have questions:
1. Check this user guide first
2. Review the troubleshooting section
3. Check BATCH_UI_ENHANCEMENTS_SUMMARY.md for technical details
4. Contact development team with specific batch IDs and dates

### Providing Feedback

We welcome feedback on the batch tracking UI:
- Feature requests
- Usability improvements
- Bug reports
- Performance issues

Please include:
- Specific use case or workflow
- Expected behavior vs. actual behavior
- Screenshots if applicable
- Date and batch IDs for reproduction

## Summary

The enhanced batch tracking UI provides:
- **Immediate visibility** into inventory age and freshness
- **Complete traceability** from production to consumption
- **Actionable insights** through color-coded status indicators
- **Efficient navigation** for daily operations and investigations

Use this guide to maximize the value of batch tracking in your daily operations and planning workflows.
