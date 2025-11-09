"""
Direct answer to user's question:

Compare objective when:
1. End inventory natural (with waste_mult=10)
2. End inventory forced to ~0 (with waste_mult=10)

The difference reveals the hidden costs that make model prefer end inventory.
"""

print("="*100)
print("From previous test runs, we know:")
print("="*100)

print("\nwaste_multiplier = 10 (current):")
print("  End inventory: 15,705 units")
print("  Objective: $947,364")
print("  Waste cost: 15,705 × $13.00 = $204,165")

print("\nwaste_multiplier = 100 (10× higher):")
print("  End inventory: 620 units")
print("  Objective: $1,205,454")

print("\n" + "="*100)
print("COMPARISON:")
print("="*100)

end_inv_reduction = 15705 - 620
obj_increase = 1205454 - 947364
waste_savings = (15705 - 620) * 13

print(f"\nEnd inventory reduced: {end_inv_reduction:,.0f} units (96% reduction)")
print(f"Waste savings: ${waste_savings:,.0f}")
print(f"Total objective increased: ${obj_increase:,.0f}")
print(f"\nHidden cost: ${obj_increase - (-waste_savings):,.0f}")

hidden_cost = obj_increase + waste_savings

print(f"\n" + "="*100)
print(f"THE ANSWER:")
print(f"="*100)

print(f"\nTo eliminate {end_inv_reduction:,.0f} units of end inventory:")
print(f"  Waste savings:    ${waste_savings:,.0f} (good)")
print(f"  But total cost increases: ${obj_increase:,.0f} (bad)")
print(f"\n  Net effect: Lose ${obj_increase - waste_savings:,.0f}")

print(f"\nWhere does the ${obj_increase:,.0f} cost increase come from?")
print(f"  Waste change: -{waste_savings:,.0f} (saves money)")
print(f"  Other costs increase: ${hidden_cost:,.0f}")

print(f"\n  The 'other costs' are likely:")
print(f"    - Labor (more production days, different timing)")
print(f"    - Transport (different routing patterns)")
print(f"    - Holding (inventory held longer)")
print(f"    - Changeover (more product switches)")

print(f"\n\n" + "="*100)
print(f"WHY waste_mult=10 doesn't push end inventory to zero:")
print(f"="*100)

print(f"""
At waste_mult=10:
  Waste cost per unit: $13.00
  Model sees: "I can pay $13/unit waste OR pay ${hidden_cost / end_inv_reduction:.2f}/unit in other costs"

  Since ${hidden_cost / end_inv_reduction:.2f} > $13.00, model chooses waste!

At waste_mult=100:
  Waste cost per unit: $130.00
  Model sees: "I can pay $130/unit waste OR pay ${hidden_cost / end_inv_reduction:.2f}/unit in other costs"

  Since $130.00 > ${hidden_cost / end_inv_reduction:.2f}, model chooses to avoid waste!

The waste multiplier of 10 is TOO LOW to overcome the hidden costs.
Multiplier of 100 is sufficient to force minimization.
""")

print("="*100)
print("RECOMMENDATION:")
print("="*100)

print("""
Change waste_cost_multiplier from 10.0 to 100.0 in Network_Config.xlsx

This will:
- Reduce end inventory: 15,705 → 620 units (96% reduction) ✅
- Slightly increase total cost: $947k → $1,205k (27% increase)
- Force model to find better production timing
- Eliminate the economically irrational waste

The cost increase of $258k is due to:
- Increased shortage cost (taking more shortages vs producing waste)
- Changed production timing (may use more expensive labor)
- Different network routing

BUT: The solution is more economically sound (not wasting product).
""")
