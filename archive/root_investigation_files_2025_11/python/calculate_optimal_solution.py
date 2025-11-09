#!/usr/bin/env python3
"""Calculate what the optimal solution SHOULD be."""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, _, _, _, _, cost_params = parser.parse_all()

# Parse inventory
alias_resolver = parser.parse_product_aliases()
inv_parser = InventoryParser('data/examples/inventory_latest.XLSX', product_alias_resolver=alias_resolver)
inventory_data = inv_parser.parse()

# 1-week
start = date(2025, 10, 17)
end = start + timedelta(days=6)

total_demand = sum(e.quantity for e in forecast.entries if start <= e.forecast_date <= end)
total_init_inv = sum(e.quantity for e in inventory_data.entries)

print("="*80)
print("EXPECTED OPTIMAL SOLUTION CALCULATION")
print("="*80)

print(f"\nInputs:")
print(f"  Total demand (7 days): {total_demand:,.0f} units")
print(f"  Initial inventory: {total_init_inv:,.0f} units")
print(f"  Shortfall to produce: {max(0, total_demand - total_init_inv):,.0f} units")

# Cost parameters
shortage_penalty = cost_params.shortage_penalty_per_unit
production_cost = cost_params.production_cost_per_unit or 1.30
waste_mult = cost_params.waste_cost_multiplier or 10.0
waste_penalty = waste_mult * production_cost

print(f"\nCost parameters:")
print(f"  Shortage penalty: ${shortage_penalty:.2f}/unit")
print(f"  Production cost: ${production_cost:.2f}/unit")
print(f"  Waste penalty: ${waste_penalty:.2f}/unit (end inventory)")

# Strategy 1: Current model behavior (zero production)
print(f"\n" + "-"*80)
print("STRATEGY 1: Zero Production (current model)")
print("-"*80)

consumed_s1 = 17520  # From test
end_inv_s1 = total_init_inv - consumed_s1
shortage_s1 = total_demand - consumed_s1

cost_shortage_s1 = shortage_s1 * shortage_penalty
cost_waste_s1 = end_inv_s1 * waste_penalty
total_s1 = cost_shortage_s1 + cost_waste_s1

print(f"  Consume from init_inv: {consumed_s1:,.0f} units")
print(f"  Produce: 0 units")
print(f"  End inventory: {end_inv_s1:,.0f} units")
print(f"  Shortage: {shortage_s1:,.0f} units")
print(f"  Shortage cost: ${cost_shortage_s1:,.2f}")
print(f"  Waste cost: ${cost_waste_s1:,.2f}")
print(f"  Total: ${total_s1:,.2f}")

# Strategy 2: Produce shortfall, consume all inventory
print(f"\n" + "-"*80)
print("STRATEGY 2: Produce Shortfall (expected optimal)")
print("-"*80)

consumed_s2 = total_init_inv  # Use ALL inventory
produce_s2 = max(0, total_demand - total_init_inv)  # Fill gap
end_inv_s2 = 0  # Consume everything
shortage_s2 = 0  # Meet all demand

cost_production_s2 = produce_s2 * production_cost
cost_shortage_s2 = shortage_s2 * shortage_penalty
cost_waste_s2 = end_inv_s2 * waste_penalty
# Note: Ignoring labor, transport for this simple calculation
total_s2 = cost_production_s2 + cost_shortage_s2 + cost_waste_s2

print(f"  Consume from init_inv: {consumed_s2:,.0f} units (ALL)")
print(f"  Produce: {produce_s2:,.0f} units")
print(f"  End inventory: {end_inv_s2:,.0f} units")
print(f"  Shortage: {shortage_s2:,.0f} units")
print(f"  Production cost: ${cost_production_s2:,.2f}")
print(f"  Shortage cost: ${cost_shortage_s2:,.2f}")
print(f"  Waste cost: ${cost_waste_s2:,.2f}")
print(f"  Total (production + penalties): ${total_s2:,.2f}")

# Comparison
print(f"\n" + "="*80)
print("COMPARISON")
print("="*80)

if total_s2 < total_s1:
    savings = total_s1 - total_s2
    print(f"\nStrategy 2 is BETTER by ${savings:,.2f}")
    print(f"  ✗ MODEL IS CHOOSING WRONG STRATEGY!")
    print(f"  Model should produce {produce_s2:,.0f} units but produces 0")
elif total_s1 < total_s2:
    print(f"\nStrategy 1 is better by ${total_s2 - total_s1:,.2f}")
    print(f"  ✓ Model behavior is economically correct")
else:
    print(f"\nStrategies are equivalent")

print("="*80)
