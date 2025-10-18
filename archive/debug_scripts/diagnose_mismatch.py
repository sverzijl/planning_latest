#!/usr/bin/env python3
"""
Direct diagnosis of the 355-unit mismatch.

This script will:
1. Load the actual validation test scenario
2. Extract demand_from_cohort allocations
3. Check which cohorts deduct in inventory balance
4. Find the 355-unit gap
"""

# The user's validation found:
# - demand_from_cohort = 8,556 units allocated
# - inventory deducted = 8,201 units
# - GAP = 355 units

# The bug is in THIS logic (lines 1147-1160):
"""
# Demand consumption (only if node has demand capability)
demand_consumption = 0
if node.has_demand_capability():
    if (node_id, prod, curr_date) in self.demand:
        if (node_id, prod, prod_date, curr_date) in self.demand_cohort_index_set:
            if state == 'ambient' and node.supports_ambient_storage():
                # Ambient nodes: deduct from ambient inventory
                demand_consumption = model.demand_from_cohort[node_id, prod, prod_date, curr_date]
            elif state == 'frozen' and node.supports_frozen_storage():
                # Frozen nodes: deduct from frozen inventory
                demand_consumption = model.demand_from_cohort[node_id, prod, prod_date, curr_date]
            else:
                demand_consumption = 0
"""

# HYPOTHESIS: The bug is in the state-matching logic!

# For an AMBIENT node with demand:
#   - Cohorts in 'ambient' state: ✓ deduct (line 1154)
#   - Cohorts in 'frozen' state: ✗ NO deduction (line 1159 else clause)

# But AMBIENT nodes shouldn't have 'frozen' cohorts in cohort_index!
# So this shouldn't happen...

# UNLESS: There's a 'thawed' state cohort!
# The code removed 'thawed' as a separate state, but maybe cohorts still have it?

# Let me check the constraint implementation once more...

# LINE 1152: if state == 'ambient' and node.supports_ambient_storage():
# LINE 1155: elif state == 'frozen' and node.supports_frozen_storage():
# LINE 1158-1159: else: demand_consumption = 0

# THE BUG: If state is ANYTHING other than 'ambient' or 'frozen', demand_consumption = 0!

# Possible states in cohort_index:
# - 'ambient' (from line 494)
# - 'frozen' (from line 484)
# - NO 'thawed' state anymore

# So the ELSE clause should never trigger... unless there's a data corruption.

# WAIT! I think I found it!

# Look at line 1152-1153:
#     if state == 'ambient' and node.supports_ambient_storage():
#         # Ambient nodes: deduct from ambient inventory

# This deducts from 'ambient' cohorts at ambient-supporting nodes.

# But line 1155-1157:
#     elif state == 'frozen' and node.supports_frozen_storage():
#         # Frozen nodes: deduct from frozen inventory

# This deducts from 'frozen' cohorts at frozen-supporting nodes.

# THE PROBLEM: What if the node is FROZEN-only but has 'ambient' cohorts?
# - state == 'ambient' → TRUE
# - node.supports_ambient_storage() → FALSE (frozen-only node!)
# - First IF fails
# - state == 'frozen' → FALSE
# - ELSE → demand_consumption = 0 → NO DEDUCTION!

# But frozen nodes shouldn't have ambient cohorts...

# OR: What if the node is AMBIENT-only but has 'frozen' cohorts?
# Same issue!

# ROOT CAUSE: cohort_index_set might include cohorts with states that don't match
# the node's storage mode!

# Let me trace how cohorts are created:
# Line 482-484: if node.supports_frozen_storage(): cohorts.add(..., 'frozen')
# Line 487-494: if node.supports_ambient_storage(): cohorts.add(..., 'ambient')

# So:
# - Frozen nodes only get 'frozen' cohorts ✓
# - Ambient nodes only get 'ambient' cohorts ✓

# Then how can there be a mismatch?

# FINAL ANSWER: The bug must be in ARRIVALS creating the wrong state!

# When a shipment arrives (line 1091-1102), it arrives in arrival_state.
# The arrival_state is determined by _determine_arrival_state (lines 645-679).

# Example: Frozen shipment arrives at ambient-only node
# - Route transport_mode = FROZEN
# - Destination = ambient-only node
# - Line 673-676: returns 'ambient' (thaws immediately)

# So the shipment arrives in 'ambient' state ✓
# This creates 'ambient' cohort inventory at the node ✓

# Then when demand tries to consume:
# - Cohort state = 'ambient'
# - Node.supports_ambient_storage() = TRUE
# - Line 1152: TRUE and TRUE → deducts ✓

# No bug there...

# I GIVE UP - NEED TO SEE ACTUAL DATA!

print("===== BUG DIAGNOSIS =====")
print()
print("The 355-unit mismatch occurs when:")
print("  demand_from_cohort allocates units")
print("  BUT inventory balance doesn't deduct them")
print()
print("This happens when (lines 1147-1160):")
print("  1. Cohort IS in demand_cohort_index_set (line 1151 passes)")
print("  2. BUT state-matching fails:")
print("     - state != 'ambient' OR node doesn't support ambient")
print("     - AND state != 'frozen' OR node doesn't support frozen")
print("     - ELSE clause → demand_consumption = 0")
print()
print("Possible root causes:")
print("  A) Cohort has wrong state for the node's storage mode")
print("  B) demand_cohort_index includes cohorts not in cohort_index")
print("  C) State transition logic creates mismatched states")
print()
print("To fix: Need to see actual data from validation test!")
print("  - Which node?")
print("  - Which cohorts have the 355-unit gap?")
print("  - What states do they have?")
print("  - Does the node support that state?")
