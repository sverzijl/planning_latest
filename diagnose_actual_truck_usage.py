"""Diagnose actual truck usage in optimization solution.

This reads the solution from session state to see if trucks are actually
being used on weekends when they shouldn't be.
"""

import streamlit as st
from datetime import date, timedelta

# Check if running in Streamlit context
if 'optimization_results' not in st.session_state:
    print("ERROR: No optimization results in session state")
    print("Please run this as a Streamlit app or from the UI")
    exit(1)

results = st.session_state.get('optimization_results')
if not results:
    print("ERROR: No optimization results found")
    exit(1)

print("=" * 80)
print("ACTUAL TRUCK USAGE FROM OPTIMIZATION SOLUTION")
print("=" * 80)
print()

# Get truck usage data
truck_used_by_date = results.get('truck_used_by_date', {})

if not truck_used_by_date:
    print("ERROR: No truck_used_by_date in results")
    print("Available keys:", list(results.keys()))
    exit(1)

# Get truck schedules
truck_schedules = st.session_state.get('truck_schedules')
if not truck_schedules:
    print("ERROR: No truck schedules in session state")
    exit(1)

# Organize by date
from collections import defaultdict
trucks_by_date = defaultdict(list)
for (truck_idx, date_val), used in truck_used_by_date.items():
    if used:
        trucks_by_date[date_val].append(truck_idx)

print("TRUCK USAGE BY DATE:")
print("-" * 80)

for check_date in sorted(trucks_by_date.keys()):
    day_name = check_date.strftime('%A')
    is_weekend = check_date.weekday() in [5, 6]
    weekend_marker = ' <-- WEEKEND!' if is_weekend else ''

    truck_indices = sorted(trucks_by_date[check_date])
    print(f"\n{check_date} ({day_name}): {len(truck_indices)} trucks{weekend_marker}")

    for truck_idx in truck_indices:
        truck = truck_schedules.schedules[truck_idx]
        should_run = truck.applies_on_date(check_date)
        status = "✓ OK" if should_run else "❌ VIOLATION"
        day_constraint = truck.day_of_week if truck.day_of_week else "DAILY"

        print(f"  [{truck_idx}] {truck.id:6s} → {truck.destination_id:6s} "
              f"(scheduled: {day_constraint:10s}) {status}")

print()
print("VIOLATIONS:")
print("-" * 80)

violations = []
for (truck_idx, check_date), used in truck_used_by_date.items():
    if used:
        truck = truck_schedules.schedules[truck_idx]
        if not truck.applies_on_date(check_date):
            violations.append((truck_idx, truck.id, check_date, truck.day_of_week))

if violations:
    print(f"❌ FOUND {len(violations)} CONSTRAINT VIOLATIONS:")
    for truck_idx, truck_id, date_val, day_of_week in violations:
        day_constraint = day_of_week if day_of_week else "DAILY"
        print(f"  Truck {truck_id} (scheduled: {day_constraint}) "
              f"used on {date_val} ({date_val.strftime('%A')})")
else:
    print("✅ No violations - all trucks respect day_of_week constraints")

print()
print("If violations found: BUG in truck_availability_con constraint")
print("If no violations: Issue is in UI display (stale data or wrong solution)")
