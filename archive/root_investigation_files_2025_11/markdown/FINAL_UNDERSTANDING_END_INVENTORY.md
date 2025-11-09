# Final Understanding: End-of-Horizon Inventory Issue

## The Confusion

**What I'm seeing in the data:**
```
Location  Forecast  Consumed  Inventory
6123      2,643     2,084     2,084      ← Consumed = Inventory?
6110      2,418     1,811     1,811      ← Consumed = Inventory?
```

**This doesn't make sense if**:
- inventory[t] = ending inventory AFTER consumption
- Then: consumed 2,084 units → inventory should be 0, not 2,084

**Unless**:
- The "Inventory" column means something different
- Or there's a reporting bug in how I'm displaying the data

## Need User Clarification

**Question 1**: In the UI Daily Inventory Snapshot, what does "Inventory" on the last day represent?
- A) Ending inventory AFTER all demand consumed (should be ~0)
- B) Available inventory BEFORE demand consumed
- C) Total inventory that existed during the day

**Question 2**: What exactly are you seeing in the UI that shows "units at end of horizon"?
- Is it showing 7,755 or 33,486?
- Which column/metric?

## Hypothesis

The 7,755 units might be:
1. **Hub inventory** (6104, 6125) with no direct demand on last day
2. **In-transit** at end (my counter showed 90 variables on last date)
3. **Reporting artifact** (showing cumulative rather than ending)

## What's Definitely Working

✅ Post-horizon shipments: 0 (down from 48)
✅ Waste cost: In objective and working
✅ Demand consumption: All available inventory consumed where demand exists
✅ No production on last day

## What Needs Clarification

❓ Why does end inventory = consumption in my analysis?
❓ What is the user seeing in the UI specifically?
❓ Is 7,755 units actually a problem or expected for hub-and-spoke?

**I need to see the actual UI or get more specific description of what's wrong before implementing another "fix" that doesn't address the real issue.**
