"""
Check if hubs (6104, 6125) have real demand in the forecast.

This will help us understand if the forecast data includes:
1. Only spoke demand (6103, 6105, 6123, etc.)
2. Or ALSO hub demand (6104, 6125)

If hubs have demand in the forecast, this creates double-counting.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser

print("=" * 80)
print("FORECAST DEMAND LOCATION CHECK")
print("=" * 80)

forecast_parser = ExcelParser("data/examples/Gfree Forecast_Converted.xlsx")
forecast = forecast_parser.parse_forecast()

# Group demand by location
demand_by_location = {}
for entry in forecast.entries:
    loc = entry.location_id
    if loc not in demand_by_location:
        demand_by_location[loc] = 0
    demand_by_location[loc] += entry.quantity

print("\nDemand by Location in Forecast:")
print(f"\n{'Location':<12} {'Total Demand':>15} {'Type':>20}")
print("-" * 50)

# Known hub locations
hubs = {'6104', '6125'}

for loc in sorted(demand_by_location.keys(), key=lambda x: demand_by_location[x], reverse=True):
    qty = demand_by_location[loc]
    loc_type = "HUB (SHOULD NOT HAVE DEMAND?)" if loc in hubs else "Spoke/Breadroom"
    print(f"{loc:<12} {qty:>15,.0f} {loc_type:>20}")

print("-" * 50)
print(f"{'TOTAL':<12} {sum(demand_by_location.values()):>15,.0f}")

# Check total
total_demand = sum(demand_by_location.values())
hub_demand = sum(demand_by_location.get(h, 0) for h in hubs)
spoke_demand = total_demand - hub_demand

print(f"\n{'=' * 80}")
print("BREAKDOWN")
print("=" * 80)
print(f"\nTotal Forecast Demand:  {total_demand:>12,.0f} units")
print(f"  Hub Demand (6104+6125): {hub_demand:>12,.0f} units ({100*hub_demand/total_demand:.1f}%)")
print(f"  Spoke Demand:           {spoke_demand:>12,.0f} units ({100*spoke_demand/total_demand:.1f}%)")

print(f"\n{'=' * 80}")
print("ANALYSIS")
print("=" * 80)

if hub_demand > 0:
    print(f"\n⚠️  POTENTIAL DATA ISSUE DETECTED!")
    print(f"\nThe forecast includes demand at hub locations (6104, 6125).")
    print(f"These hubs ALSO forward to spoke locations (6103, 6105, 6123, 6120, 6134).")
    print(f"\nThis could indicate:")
    print(f"  1. ✅ Hubs have real breadroom operations that consume product")
    print(f"  2. ❌ Demand is being double-counted (hub demand + spoke demand)")
    print(f"  3. ❌ Forecast should only list spoke demand, not hub demand")

    print(f"\n{'=' * 80}")
    print("RECOMMENDATION")
    print("=" * 80)
    print(f"\nCheck with business users:")
    print(f"  • Do locations 6104 and 6125 have ACTUAL breadroom operations?")
    print(f"  • Or are they ONLY distribution hubs that forward to spokes?")
    print(f"\nIf they are ONLY hubs (no breadroom):")
    print(f"  → The forecast should NOT include 6104 and 6125")
    print(f"  → Remove {hub_demand:,.0f} units from forecast")
    print(f"  → Corrected total demand: {spoke_demand:,.0f} units")
else:
    print(f"\n✅ No hub demand detected")
    print(f"All demand is at spoke/breadroom locations only")
    print(f"This is the expected configuration for a hub-and-spoke network")

print(f"\n{'=' * 80}")
