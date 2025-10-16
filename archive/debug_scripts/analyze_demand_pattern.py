"""
Analyze demand patterns in the Oct 14 - Nov 3 window to understand:
1. Why is demand front-loaded (only 3.6% in last 3 days)?
2. Which locations/products drive this pattern?
3. How does demand distribution cause hub inventory accumulation?
"""

from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict

from src.parsers.multi_file_parser import MultiFileParser


def main():
    print("="*80)
    print("DEMAND PATTERN ANALYSIS: Oct 14 - Nov 3")
    print("="*80)

    # Load data
    data_dir = Path("data/examples")
    forecast_file = data_dir / "Gfree Forecast.xlsm"
    network_file = data_dir / "Network_Config.xlsx"

    parser = MultiFileParser(
        forecast_file=forecast_file,
        network_file=network_file,
        inventory_file=None,
    )

    forecast, locations, routes, _, _, _ = parser.parse_all()

    # Define window (matches actual test after inventory date adjustment)
    start_date = date(2025, 10, 14)
    end_date = date(2025, 11, 3)
    total_days = (end_date - start_date).days + 1

    print(f"\nWindow: {start_date} to {end_date} ({total_days} days)")

    # Filter demand to window
    demand_entries = [
        e for e in forecast.entries
        if start_date <= e.forecast_date <= end_date
    ]

    total_demand = sum(e.quantity for e in demand_entries)
    print(f"Total demand: {total_demand:,.0f} units")
    print(f"Average daily demand: {total_demand / total_days:,.0f} units/day")

    # Daily demand distribution
    print(f"\n{'='*80}")
    print("DAILY DEMAND DISTRIBUTION")
    print(f"{'='*80}")

    demand_by_date = defaultdict(float)
    for e in demand_entries:
        demand_by_date[e.forecast_date] += e.quantity

    # Sort by date
    dates_sorted = sorted(demand_by_date.keys())

    print(f"\n{'Date':<12} {'Demand':>12} {'% of Total':>12} {'Cumulative %':>15} {'Day':>5}")
    print("-" * 62)

    cumulative = 0
    for d in dates_sorted:
        qty = demand_by_date[d]
        pct = 100 * qty / total_demand
        cumulative += qty
        cum_pct = 100 * cumulative / total_demand
        day_num = (d - start_date).days + 1
        print(f"{d} {qty:>12,.0f} {pct:>11.1f}% {cum_pct:>14.1f}% {day_num:>5}")

    # Calculate first/middle/last week distributions
    week1_end = start_date + timedelta(days=6)
    week2_end = start_date + timedelta(days=13)
    week3_end = start_date + timedelta(days=20)

    week1_demand = sum(qty for d, qty in demand_by_date.items() if start_date <= d <= week1_end)
    week2_demand = sum(qty for d, qty in demand_by_date.items() if week1_end < d <= week2_end)
    week3_demand = sum(qty for d, qty in demand_by_date.items() if week2_end < d <= week3_end)
    week4_demand = sum(qty for d, qty in demand_by_date.items() if d > week3_end)

    print(f"\n{'='*80}")
    print("WEEKLY DEMAND DISTRIBUTION")
    print(f"{'='*80}")
    print(f"Week 1 ({start_date} to {week1_end}): {week1_demand:>12,.0f} units ({100*week1_demand/total_demand:>5.1f}%)")
    print(f"Week 2 ({week1_end + timedelta(days=1)} to {week2_end}): {week2_demand:>12,.0f} units ({100*week2_demand/total_demand:>5.1f}%)")
    print(f"Week 3 ({week2_end + timedelta(days=1)} to {week3_end}): {week3_demand:>12,.0f} units ({100*week3_demand/total_demand:>5.1f}%)")
    print(f"Week 4 ({week3_end + timedelta(days=1)} to {end_date}): {week4_demand:>12,.0f} units ({100*week4_demand/total_demand:>5.1f}%)")

    # Last 3 days
    last_3_start = end_date - timedelta(days=2)
    last_3_demand = sum(qty for d, qty in demand_by_date.items() if last_3_start <= d <= end_date)
    print(f"\nLast 3 days ({last_3_start} to {end_date}): {last_3_demand:>12,.0f} units ({100*last_3_demand/total_demand:>5.1f}%)")

    # Demand by location
    print(f"\n{'='*80}")
    print("DEMAND BY LOCATION")
    print(f"{'='*80}")

    demand_by_location = defaultdict(float)
    for e in demand_entries:
        demand_by_location[e.location_id] += e.quantity

    print(f"\n{'Location':<12} {'Total Demand':>15} {'% of Total':>12} {'Avg/Day':>12}")
    print("-" * 55)

    for loc, qty in sorted(demand_by_location.items(), key=lambda x: x[1], reverse=True):
        pct = 100 * qty / total_demand
        avg_day = qty / total_days
        print(f"{loc:<12} {qty:>15,.0f} {pct:>11.1f}% {avg_day:>11,.0f}")

    # Check if certain locations are hub-routed
    hub_destinations = [6104, 6125]  # The hubs themselves
    spoke_destinations = [loc for loc in demand_by_location.keys() if loc not in hub_destinations and loc != 6122]

    demand_at_hubs = sum(qty for loc, qty in demand_by_location.items() if loc in hub_destinations)
    demand_at_spokes = sum(qty for loc, qty in demand_by_location.items() if loc in spoke_destinations)

    print(f"\n{'='*80}")
    print("HUB VS SPOKE DEMAND")
    print(f"{'='*80}")
    print(f"Hub destinations (6104, 6125): {demand_at_hubs:>12,.0f} units ({100*demand_at_hubs/total_demand:>5.1f}%)")
    print(f"Spoke destinations (via hubs):  {demand_at_spokes:>12,.0f} units ({100*demand_at_spokes/total_demand:>5.1f}%)")

    # Demand by product
    print(f"\n{'='*80}")
    print("DEMAND BY PRODUCT")
    print(f"{'='*80}")

    demand_by_product = defaultdict(float)
    for e in demand_entries:
        demand_by_product[e.product_id] += e.quantity

    print(f"\n{'Product':<35} {'Total Demand':>15} {'% of Total':>12}")
    print("-" * 65)

    for prod, qty in sorted(demand_by_product.items(), key=lambda x: x[1], reverse=True):
        pct = 100 * qty / total_demand
        print(f"{prod:<35} {qty:>15,.0f} {pct:>11.1f}%")

    # Check demand concentration in early days
    first_week_entries = [e for e in demand_entries if start_date <= e.forecast_date <= week1_end]
    last_week_entries = [e for e in demand_entries if e.forecast_date > week3_end]

    print(f"\n{'='*80}")
    print("EARLY VS LATE DEMAND CHARACTERISTICS")
    print(f"{'='*80}")

    # First week by location
    first_week_by_loc = defaultdict(float)
    for e in first_week_entries:
        first_week_by_loc[e.location_id] += e.quantity

    print(f"\nFirst Week Demand by Location:")
    for loc, qty in sorted(first_week_by_loc.items(), key=lambda x: x[1], reverse=True)[:5]:
        pct = 100 * qty / week1_demand
        print(f"  {loc}: {qty:>10,.0f} units ({pct:>5.1f}% of week 1)")

    # Last week by location
    last_week_by_loc = defaultdict(float)
    for e in last_week_entries:
        last_week_by_loc[e.location_id] += e.quantity

    if week4_demand > 0:
        print(f"\nLast Week Demand by Location:")
        for loc, qty in sorted(last_week_by_loc.items(), key=lambda x: x[1], reverse=True)[:5]:
            pct = 100 * qty / week4_demand
            print(f"  {loc}: {qty:>10,.0f} units ({pct:>5.1f}% of week 4)")
    else:
        print(f"\n⚠ NO DEMAND in last week (week 4)!")

    # Analyze routing requirements
    print(f"\n{'='*80}")
    print("ROUTING ANALYSIS")
    print(f"{'='*80}")

    # Look up which destinations are served via hubs
    location_dict = {loc.id: loc for loc in locations}
    route_dict = {}
    for route in routes:
        key = (route.origin_id, route.destination_id)
        if key not in route_dict:
            route_dict[key] = route

    # Check hub routing patterns
    print(f"\nHub 6125 outbound routes:")
    hub_6125_routes = [r for r in routes if r.origin_id == 6125]
    for r in hub_6125_routes:
        print(f"  6125 → {r.destination_id} (transit: {r.transit_days} days)")

    print(f"\nHub 6104 outbound routes:")
    hub_6104_routes = [r for r in routes if r.origin_id == 6104]
    for r in hub_6104_routes:
        print(f"  6104 → {r.destination_id} (transit: {r.transit_days} days)")

    # Calculate implied hub inventory requirements
    print(f"\n{'='*80}")
    print("IMPLIED HUB INVENTORY POSITIONING")
    print(f"{'='*80}")

    # For spoke destinations, inventory must be at hub before it can be delivered
    # If spoke demand is early (week 1), hub must have inventory in week 1
    # But if spoke demand drops off later, hub inventory might remain unused

    spoke_demand_by_week = {
        1: defaultdict(float),
        2: defaultdict(float),
        3: defaultdict(float),
        4: defaultdict(float),
    }

    for e in demand_entries:
        if e.location_id in spoke_destinations:
            week_num = ((e.forecast_date - start_date).days // 7) + 1
            if week_num <= 4:
                spoke_demand_by_week[week_num][e.location_id] += e.quantity

    print(f"\nSpoke Demand by Week:")
    for week in [1, 2, 3, 4]:
        total_spoke_week = sum(spoke_demand_by_week[week].values())
        print(f"  Week {week}: {total_spoke_week:>10,.0f} units")

    print(f"\n{'='*80}")
    print("DIAGNOSIS: WHY FRONT-LOADED DEMAND CAUSES END INVENTORY")
    print(f"{'='*80}")

    print(f"""
When demand is front-loaded:
1. Model produces inventory early to serve week 1-2 demand
2. Inventory is positioned at hubs (6104, 6125) for spoke distribution
3. Hubs also serve their own direct demand
4. As demand drops off in weeks 3-4, less inventory flows through hubs
5. But production has already been made and shipped to hubs
6. Result: Hub inventory accumulates with nowhere to go

The negative correlation with late demand makes sense:
- High late demand → hubs keep distributing → low end inventory ✓
- Low late demand → hub outflows drop → high end inventory ⚠️

Key metrics:
- Week 1 demand: {week1_demand:,.0f} units ({100*week1_demand/total_demand:.1f}%)
- Week 4 demand: {week4_demand:,.0f} units ({100*week4_demand/total_demand:.1f}%)
- Last 3 days: {last_3_demand:,.0f} units ({100*last_3_demand/total_demand:.1f}%)

The model is pre-positioning inventory at hubs based on overall capacity,
but doesn't account for the timing mismatch between production and demand.
""")


if __name__ == "__main__":
    main()
