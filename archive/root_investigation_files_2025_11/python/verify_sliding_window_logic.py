#!/usr/bin/env python3
"""
Verify the sliding window logic for initial inventory handling.

Test case: 518 units init_inv, consumed 518 on Day 1, 0 production

Expected behavior:
- Day 1: O[1]=518 <= Q[1]=0+init_inv=518 ✓
- Day 2: O[1,2]=518 <= Q[1,2]=0+init_inv=518 ✓
- Day 17: O[1..17]=518 <= Q[1..17]=0+init_inv=518 ✓
- Day 18: O[2..18]=0 <= Q[2..18]=0 ✓ (window excludes Day 1, no init_inv)

Question: Is this double-counting or correct cumulative accounting?
"""

def test_sliding_window_logic():
    """Trace through constraints with cumulative flows."""

    print("="*80)
    print("SLIDING WINDOW LOGIC VERIFICATION")
    print("="*80)
    print("\nScenario: 518 units init_inv, consume 518 on Day 1, zero production\n")

    init_inv = 518
    consumption = [518] + [0] * 27  # 518 on Day 1, 0 thereafter
    production = [0] * 28  # No production
    shelf_life = 17  # Ambient shelf life

    print("Constraint analysis:")
    print("-" * 80)

    for t in range(1, 29):  # Days 1-28
        # Calculate window (last 17 days, or fewer if near start)
        window_start = max(1, t - shelf_life + 1)
        window_end = t
        window_days = range(window_start, window_end + 1)

        # Check if Day 1 is in window
        window_includes_day1 = (1 in window_days)

        # Calculate cumulative outflows in window
        O = sum(consumption[d-1] for d in window_days)

        # Calculate cumulative inflows in window
        Q = sum(production[d-1] for d in window_days)
        if window_includes_day1:
            Q += init_inv  # Add init_inv to inflows

        # Check constraint
        constraint_holds = (O <= Q)

        # Print only interesting days
        if t <= 5 or t in [17, 18, 19]:
            status = "✓ PASS" if constraint_holds else "✗ FAIL"
            print(f"Day {t:2d}: window [{window_start:2d}..{window_end:2d}] "
                  f"({'incl' if window_includes_day1 else 'excl'} Day 1) | "
                  f"O={O:3d} <= Q={Q:3d} | {status}")

    print("\n" + "="*80)
    print("ANALYSIS")
    print("="*80)

    print("""
The key insight:
1. Days 1-17: Window includes Day 1, so init_inv appears in Q
   - O accumulates consumption (518 total in window)
   - Q = 0 (production) + 518 (init_inv) = 518
   - Constraint: 518 <= 518 ✓ (balanced)

2. Day 18+: Window excludes Day 1 (window starts at Day 2+)
   - O = 0 (no consumption after Day 1)
   - Q = 0 (no production, no init_inv)
   - Constraint: 0 <= 0 ✓ (trivially satisfied)

3. Is this double-counting?
   NO! It's cumulative accounting:
   - Day 1: "518 out on Day 1 <= 518 available from init_inv" ✓
   - Day 2: "518 out on Days 1-2 <= 518 available from init_inv" ✓
   - Both constraints use the SAME 518 units, but that's correct!
   - The consumption happened ONCE (on Day 1)
   - Both constraints correctly verify that cumulative outflows <= cumulative inflows

4. Why doesn't this allow consuming 518 twice?
   Because outflows ALSO accumulate!
   - If we tried to consume another 518 on Day 2:
   - Day 2 constraint: O[1,2] = 518+518 = 1036 <= Q[1,2] = 518 ✗ FAILS!

5. Conclusion:
   The current logic is CORRECT. Adding init_inv to all constraints where
   window includes Day 1 is the mathematically sound approach.

   The perceived "double-counting" is actually correct cumulative flow accounting.
""")

if __name__ == "__main__":
    test_sliding_window_logic()
