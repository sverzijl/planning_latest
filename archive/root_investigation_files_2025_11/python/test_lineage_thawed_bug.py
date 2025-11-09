#!/usr/bin/env python3
"""
Minimal test: Frozen-only nodes should NOT have thawed inventory variables.

ROOT CAUSE:
Line 718: can_thaw = node.supports_frozen_storage()

This creates thawed inventory for ANY frozen storage node, including frozen-ONLY nodes.

EXPECTED:
Lineage (frozen-only) should have:
  - Frozen inventory: YES
  - Ambient inventory: NO
  - Thawed inventory: NO

BUG:
Lineage currently gets thawed inventory variables created, which appear in UI.
"""

from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode

print("="*80)
print("MINIMAL TEST: Thawed Variable Creation Logic")
print("="*80)

# Create frozen-only node (like Lineage)
frozen_only_node = UnifiedNode(
    id="Lineage",
    name="Lineage Frozen Storage",
    node_type='storage',
    capabilities=NodeCapabilities(
        can_store=True,
        can_produce=False,
        can_receive_demand=False,
        storage_mode=StorageMode.FROZEN,  # Frozen ONLY
    )
)

print("\nNode: Lineage")
print(f"  Storage mode: {frozen_only_node.capabilities.storage_mode}")
print(f"  supports_frozen_storage(): {frozen_only_node.supports_frozen_storage()}")
print(f"  supports_ambient_storage(): {frozen_only_node.supports_ambient_storage()}")
print(f"  has_demand_capability(): {frozen_only_node.has_demand_capability()}")
print()

print("="*80)
print("CURRENT LOGIC (BUGGY - Line 718)")
print("="*80)

# Current buggy logic
can_thaw_buggy = frozen_only_node.supports_frozen_storage()
has_frozen_inbound = False  # Not relevant for this test

print(f"can_thaw = node.supports_frozen_storage()")
print(f"can_thaw = {can_thaw_buggy}")
print()
print(f"if has_frozen_inbound or can_thaw:")
print(f"if {has_frozen_inbound} or {can_thaw_buggy}:")
print(f"if {has_frozen_inbound or can_thaw_buggy}:")

if has_frozen_inbound or can_thaw_buggy:
    print("  → Creates THAWED inventory variable")
    print("  ❌ WRONG: Frozen-only nodes can't have thawed inventory!")
else:
    print("  → Does NOT create thawed inventory variable")
    print("  ✓ Correct")

print()
print("="*80)
print("CORRECT LOGIC (FIXED - Match Line 753)")
print("="*80)

# Correct logic (matches thaw flow creation on line 753)
can_thaw_correct = frozen_only_node.supports_frozen_storage() and (
    frozen_only_node.supports_ambient_storage() or
    frozen_only_node.has_demand_capability()
)

print(f"can_thaw = supports_frozen AND (supports_ambient OR has_demand)")
print(f"can_thaw = {frozen_only_node.supports_frozen_storage()} AND ({frozen_only_node.supports_ambient_storage()} OR {frozen_only_node.has_demand_capability()})")
print(f"can_thaw = {can_thaw_correct}")
print()
print(f"if has_frozen_inbound or can_thaw:")
print(f"if {has_frozen_inbound} or {can_thaw_correct}:")
print(f"if {has_frozen_inbound or can_thaw_correct}:")

if has_frozen_inbound or can_thaw_correct:
    print("  → Creates THAWED inventory variable")
    print("  ❌ Still wrong for frozen-only!")
else:
    print("  → Does NOT create thawed inventory variable")
    print("  ✅ CORRECT: Frozen-only nodes shouldn't have thawed!")

print()
print("="*80)
print("CONCLUSION:")
print("="*80)
print("Lineage can_thaw:")
print(f"  Current (buggy): {can_thaw_buggy}  ← Creates thawed vars")
print(f"  Fixed:           {can_thaw_correct}  ← Does NOT create thawed vars")
print()
print("✅ Fix confirmed: Change line 718 to match line 753")
