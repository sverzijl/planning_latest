#!/usr/bin/env python3
"""
Test the CORRECT formulation for initial inventory in sliding windows.

Approach: Separate handling for Day 1 vs. later days.
"""

from pyomo.environ import *

def test_option2_separate_day1():
    """Option 2: Day 1 gets init_inv, later days use standard sliding window."""

    model = ConcreteModel()
    model.days = Set(initialize=[1, 2, 3])

    # Decision variables
    model.consumption = Var(model.days, within=NonNegativeReals)
    model.shortage = Var(model.days, within=NonNegativeReals)

    # Parameters
    init_inv = 518
    demand = {1: 300, 2: 300, 3: 100}

    # Objective
    model.obj = Objective(
        expr=sum(10 * model.shortage[d] for d in model.days),
        sense=minimize
    )

    # Demand balance
    def demand_balance_rule(model, d):
        return model.consumption[d] + model.shortage[d] == demand[d]
    model.demand_balance = Constraint(model.days, rule=demand_balance_rule)

    # MODIFIED APPROACH: Day 1 special case
    # Day 1: Can consume from init_inv
    model.day1_inv_limit = Constraint(
        expr=model.consumption[1] <= init_inv
    )

    # Days 2+: Sliding window constraint WITHOUT init_inv
    # (Only tracks flows that occurred during planning horizon)
    # Day 2 window [1,2]: consumption in days 1-2 <= production in days 1-2
    # Since there's no production, this forces consumption[1] + consumption[2] <= 0
    # WAIT - this is ALSO wrong! If we consumed on Day 1 from init_inv,
    # that consumption shouldn't block Day 2!

    print("="*80)
    print("OPTION 2 TEST: Day 1 special, sliding window for Day 2+")
    print("="*80)
    print(f"\nInitial inventory: {init_inv}")
    print(f"Demand: {demand}")
    print()

    # Actually, let's try: Day 2+ only constrains flows WITHIN the window,
    # excluding Day 1 consumption from init_inv

    # This is getting complex. Let me think...
    # The issue is: how do we track that init_inv was consumed on Day 1?

    # Actually, maybe the answer is simpler:
    # If we have init_inv, we DON'T use sliding windows at all for this product!
    # We use explicit inventory tracking instead.

    print("CONCLUSION:")
    print("  Sliding windows are incompatible with initial inventory!")
    print("  Need explicit inventory balance equations instead.")
    print()
    print("  inv[0] = init_inv")
    print("  inv[t] = inv[t-1] + arrivals[t] - consumption[t] - shipments[t]")
    print("  inv[t] >= 0  (can't consume what you don't have)")
    print()

if __name__ == "__main__":
    test_option2_separate_day1()
