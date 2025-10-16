"""Verify total demand vs production in monolithic solve."""
import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from src.parsers import ExcelParser

print("Loading forecast data...")
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')
forecast = forecast_parser.parse_forecast()

# Calculate total demand
total_demand = sum(e.quantity for e in forecast.entries)
print(f"\nTotal forecast demand: {total_demand:,.0f} units")

# Group by destination
from collections import defaultdict
by_dest = defaultdict(float)
for entry in forecast.entries:
    by_dest[entry.location_id] += entry.quantity

print(f"\nDemand by destination:")
for dest_id in sorted(by_dest.keys()):
    print(f"  {dest_id}: {by_dest[dest_id]:>10,.0f} units")

# Group by product
by_product = defaultdict(float)
for entry in forecast.entries:
    by_product[entry.product_id] += entry.quantity

print(f"\nDemand by product:")
for product_id in sorted(by_product.keys()):
    print(f"  {product_id}: {by_product[product_id]:>10,.0f} units")

print(f"\nMonolithic solve produced: 2,252,419 units")
print(f"Difference: {total_demand - 2252419:,.0f} units ({(total_demand - 2252419) / total_demand * 100:.1f}%)")

if total_demand > 2252419:
    print("\n⚠️  Production is LESS than forecast demand")
    print("   But shortage cost is $0, which means the model thinks it's meeting demand.")
    print("   This suggests:")
    print("   1. The model may be using initial inventory (but initial_inventory={})")
    print("   2. The shortage penalty may not be high enough to force 100% satisfaction")
    print("   3. Some demand may be filtered out (e.g., infeasible delivery dates)")
elif total_demand < 2252419:
    print("\n✓ Production EXCEEDS forecast demand (building inventory)")
else:
    print("\n✓ Production exactly matches forecast demand")
