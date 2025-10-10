#!/usr/bin/env python3
"""
Diagnostic script to trace the truck loading timing bug.

The issue: Production is limited to 1.70M units instead of meeting 2.41M demand.

Critical flow to understand:
1. Production on date D flows into 6122_Storage inventory at date D
2. Trucks loading at departure_date access inventory from:
   - Morning trucks: 6122_Storage at (departure_date - 1)
   - Afternoon trucks: 6122_Storage at (departure_date - 1) + production at departure_date
3. truck_load variables are indexed by DELIVERY_DATE (not departure_date)
4. delivery_date = departure_date + transit_days

The constraint bug hypothesis:
- Morning trucks constraint (line 1595-1608) checks inventory at d_minus_1 where d_minus_1 = departure_date - 1
- But departure_date is DELIVERY_DATE in the current code (due to variable indexing)
- This means we're checking inventory TWO DAYS EARLY: (delivery_date - transit_days - 1)
- For a truck with 2-day transit, we check D-3 inventory when we should check D-1!
"""

from datetime import date, timedelta

# Example scenario to illustrate the bug:
# - Production happens on Monday (Day 1)
# - Morning truck departs Tuesday (Day 2) going to 6125 (2-day transit)
# - Delivery at 6125 happens Thursday (Day 4)

production_date = date(2025, 1, 6)  # Monday
departure_date = date(2025, 1, 7)   # Tuesday (D+1)
transit_days = 2
delivery_date = departure_date + timedelta(days=transit_days)  # Thursday (D+3)

print("=" * 80)
print("TRUCK TIMING BUG DIAGNOSIS")
print("=" * 80)
print()
print("Example Scenario:")
print(f"  Production date:  {production_date} (Monday)")
print(f"  Departure date:   {departure_date} (Tuesday, D+1)")
print(f"  Transit days:     {transit_days}")
print(f"  Delivery date:    {delivery_date} (Thursday, D+3)")
print()

# Current (BUGGY) constraint behavior:
# truck_load is indexed by DELIVERY_DATE
# Constraint at line 1595-1608:
#   departure_date = delivery_date - timedelta(days=transit_days)
#   d_minus_1 = departure_date - timedelta(days=1)
#   Check: truck_load[truck, dest, prod, DELIVERY_DATE] <= inventory_ambient[6122_Storage, prod, d_minus_1]

buggy_departure = delivery_date - timedelta(days=transit_days)  # Thursday - 2 = Tuesday
buggy_d_minus_1 = buggy_departure - timedelta(days=1)           # Tuesday - 1 = Monday
print("CURRENT (BUGGY) CONSTRAINT:")
print(f"  truck_load indexed by:    {delivery_date} (delivery_date)")
print(f"  Calculated departure:     {buggy_departure}")
print(f"  Inventory checked at:     {buggy_d_minus_1} (d_minus_1)")
print(f"  ✓ This is CORRECT for morning trucks!")
print()

# The bug is actually ELSEWHERE - let me re-check the constraint
# Looking at line 1595-1608 again...
# Wait - the constraint is checking delivery_date, not departure_date!

print("WAIT - Re-reading the constraint structure...")
print()
print("At line 1579-1608 (truck_morning_timing_agg_rule):")
print("  def truck_morning_timing_agg_rule(model, truck_idx, dest, delivery_date):")
print("    # Calculate departure date from delivery date")
print("    transit_days = self._get_truck_transit_days(truck_idx, dest)")
print("    departure_date = delivery_date - timedelta(days=transit_days)")
print("    d_minus_1 = departure_date - timedelta(days=1)")
print("    # Check: truck_load[truck, dest, p, delivery_date] <= inventory[6122_Storage, p, d_minus_1]")
print()
print("So the constraint IS correctly calculating departure_date from delivery_date.")
print("And it IS correctly checking inventory at (departure_date - 1).")
print()

# So what's the actual bug?
# Let me check the 6122_Storage inventory balance (lines 1283-1318)

print("=" * 80)
print("CHECKING 6122_Storage INVENTORY BALANCE")
print("=" * 80)
print()
print("From lines 1283-1318:")
print("  # Arrivals = production on this date")
print("  production_arrival = model.production[date, prod]")
print()
print("  # Departures = truck loads departing on this date")
print("  for delivery_date in model.dates:")
print("    departure_date = delivery_date - timedelta(days=transit_days)")
print("    if departure_date == date:")
print("      truck_outflows += model.truck_load[truck_idx, dest, prod, delivery_date]")
print()
print("  # Balance:")
print("  inventory_ambient[6122_Storage, prod, date] ==")
print("    prev_ambient + production_arrival - truck_outflows")
print()

# AHA! The bug is in the OUTFLOW calculation!
# When we want to find trucks departing on date D:
#   - We iterate through delivery_dates
#   - We calculate departure_date = delivery_date - transit_days
#   - We check if departure_date == D
#   - We add truck_load[truck, dest, prod, DELIVERY_DATE] to outflows

print("=" * 80)
print("ROOT CAUSE IDENTIFIED!")
print("=" * 80)
print()
print("The 6122_Storage inventory balance at line 1300-1313 is CORRECT.")
print("It properly accumulates truck outflows departing on each date.")
print()
print("The truck timing constraint at line 1595-1608 is ALSO CORRECT.")
print("It properly checks inventory at (departure_date - 1).")
print()
print("So where's the bug limiting production to 1.70M?")
print()

# Let me think about the constraint interaction...
#
# Morning truck on Tuesday departing to 6125 (2-day transit, arrives Thursday):
#   - truck_load[truck, 6125, prod, Thursday] represents quantity
#   - Constraint: truck_load <= inventory[6122_Storage, prod, Monday]
#   - Inventory balance on Monday: inv[Mon] = production[Mon] - (trucks departing Mon)
#   - Inventory balance on Tuesday: inv[Tue] = inv[Mon] + production[Tue] - (trucks departing Tue)
#
# So truck departing Tuesday checks inventory at Monday.
# But inventory at Monday was CONSUMED by trucks departing Monday!
# This creates a CIRCULAR DEPENDENCY if we try to change the constraint.

print("CIRCULAR DEPENDENCY ANALYSIS:")
print()
print("Consider Monday's 6122_Storage inventory:")
print(f"  inv[{production_date}] = production[{production_date}] - trucks_departing[{production_date}]")
print()
print(f"Tuesday morning truck constraint (arrives {delivery_date}):")
print(f"  truck_load[truck, dest, prod, {delivery_date}] <= inv[{buggy_d_minus_1}]")
print()
print("This is CORRECT! Trucks departing Tuesday should access Monday's inventory.")
print("Monday's inventory = Monday production - Monday departures.")
print("Tuesday trucks cannot access Monday production that was already shipped Monday.")
print()

# So what's the actual bottleneck?
print("=" * 80)
print("BOTTLENECK HYPOTHESIS")
print("=" * 80)
print()
print("The constraint structure is CORRECT, but perhaps the bottleneck is:")
print()
print("1. INVENTORY ACCUMULATION: 6122_Storage inventory at d_minus_1 is insufficient")
print("   because production at d_minus_1 was already consumed by trucks departing d_minus_1.")
print()
print("2. AFTERNOON TRUCK CONSTRAINT: Afternoon trucks check:")
print("   truck_load <= inventory[d_minus_1] + production[departure_date]")
print("   But 'departure_date' in the constraint is calculated from delivery_date.")
print()
print("3. POSSIBLE BUG: Are we checking the right 'departure_date' in afternoon constraint?")
print()

# Let me trace afternoon trucks
print("AFTERNOON TRUCK CONSTRAINT ANALYSIS:")
print()
print("From lines 1610-1638 (truck_afternoon_timing_agg_rule):")
print("  def truck_afternoon_timing_agg_rule(model, truck_idx, dest, delivery_date):")
print("    transit_days = self._get_truck_transit_days(truck_idx, dest)")
print("    departure_date = delivery_date - timedelta(days=transit_days)")
print("    d_minus_1 = departure_date - timedelta(days=1)")
print()
print("    storage_inventory = sum(inventory_ambient[6122_Storage, p, d_minus_1])")
print("    same_day_production = sum(production[departure_date, p])")
print()
print("    truck_load[truck, dest, p, delivery_date] <=")
print("      storage_inventory + same_day_production")
print()

afternoon_departure = date(2025, 1, 6)  # Monday afternoon truck
afternoon_delivery = afternoon_departure + timedelta(days=2)  # Wednesday
afternoon_d_minus_1 = afternoon_departure - timedelta(days=1)  # Sunday

print(f"Example: Monday afternoon truck to 6104 (2-day transit):")
print(f"  Departure date:       {afternoon_departure} (Monday)")
print(f"  Delivery date:        {afternoon_delivery} (Wednesday)")
print(f"  d_minus_1:            {afternoon_d_minus_1} (Sunday)")
print(f"  Storage checked:      inventory[6122_Storage, prod, {afternoon_d_minus_1}]")
print(f"  Production added:     production[{afternoon_departure}]")
print()
print("This is CORRECT! Afternoon trucks departing Monday can use:")
print("  - Inventory left over from Sunday (after Sunday departures)")
print("  - Production made on Monday (same day)")
print()

print("=" * 80)
print("NEXT STEP: Check if d_minus_1 inventory exists in sparse index")
print("=" * 80)
print()
print("The constraint uses:")
print("  if ('6122_Storage', p, d_minus_1) in self.inventory_ambient_index_set else 0")
print()
print("If d_minus_1 is NOT in the sparse index, inventory defaults to 0!")
print("This could severely limit truck loading capacity.")
print()
print("For first day of planning horizon, d_minus_1 would be BEFORE start_date.")
print("Therefore d_minus_1 NOT in inventory_ambient_index_set.")
print("Therefore storage_inventory = 0 for ALL trucks on first departure day!")
print()
print("HYPOTHESIS: The 1.70M production limit is caused by:")
print("  1. First day trucks constrained to 0 storage (d_minus_1 out of range)")
print("  2. Subsequent days limited by accumulation lag")
print("  3. No way to 'pre-stock' 6122_Storage before planning horizon starts")
print()
print("FIX: Use initial_inventory for 6122_Storage when d_minus_1 < start_date!")
