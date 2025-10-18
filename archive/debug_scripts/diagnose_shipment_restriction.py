"""Diagnose shipment restriction impact on demand satisfaction.

This script analyzes:
1. Which demand can be satisfied (has valid shipment paths)
2. Which demand is unreachable (blocked by latest_safe_departure)
3. What production is actually being used vs. trapped

Goal: Understand why model produces 235,268 units when some demand is unreachable.
"""

from datetime import date as Date, timedelta
from collections import defaultdict
from typing import Dict, Set, Tuple, List

# Test configuration (matching integration test)
START_DATE = Date(2025, 10, 16)
END_DATE = Date(2025, 11, 13)  # 4 weeks = 28 days

# Network routes with transit times (from real data)
ROUTES = [
    # Manufacturing to hubs
    ('6122', '6104', 1.0),   # 6122 → 6104 (NSW hub)
    ('6122', '6125', 1.0),   # 6122 → 6125 (VIC hub)
    ('6122', '6110', 2.0),   # 6122 → 6110 (QLD direct)
    ('6122', 'Lineage', 1.0), # 6122 → Lineage (frozen buffer)

    # Hub to spokes
    ('6104', '6102', 1.0),   # NSW hub → 6102 (NSW spoke)
    ('6104', '6131', 1.0),   # NSW hub → 6131 (ACT spoke)
    ('6125', '6105', 1.0),   # VIC hub → 6105 (VIC spoke)
    ('6125', '6124', 2.0),   # VIC hub → 6124 (TAS spoke)
    ('6125', '6128', 2.0),   # VIC hub → 6128 (SA spoke)

    # Frozen buffer to WA
    ('Lineage', '6130', 3.0), # Lineage → 6130 (WA)
]

def calculate_latest_safe_departure(end_date: Date, transit_days: float) -> Date:
    """Calculate latest safe departure date per model restriction."""
    transit_days_int = int(transit_days) + (1 if transit_days % 1 > 0 else 0)
    return end_date - timedelta(days=transit_days_int)

def calculate_min_transit_days(origin: str, dest: str, routes: List[Tuple[str, str, float]]) -> float:
    """Calculate minimum transit days from origin to destination.

    Uses simple BFS to find shortest path. Returns infinity if no path exists.
    """
    if origin == dest:
        return 0.0

    # Build adjacency list
    graph = defaultdict(list)
    for o, d, transit in routes:
        graph[o].append((d, transit))

    # BFS with distance tracking
    from collections import deque
    queue = deque([(origin, 0.0)])
    visited = {origin}

    while queue:
        current, dist = queue.popleft()

        for next_node, transit in graph[current]:
            if next_node == dest:
                return dist + transit

            if next_node not in visited:
                visited.add(next_node)
                queue.append((next_node, dist + transit))

    return float('inf')  # No path exists

def analyze_demand_reachability(
    start_date: Date,
    end_date: Date,
    routes: List[Tuple[str, str, float]],
    demand_nodes: Set[str],
    mfg_node: str = '6122'
) -> Dict:
    """Analyze which demand dates are reachable vs. blocked by shipment restriction."""

    results = {
        'reachable_demand_days': defaultdict(list),  # {node: [dates]}
        'unreachable_demand_days': defaultdict(list),  # {node: [dates]}
        'total_horizon_days': (end_date - start_date).days + 1,
        'restriction_details': {},
    }

    print("\n=== SHIPMENT RESTRICTION ANALYSIS ===\n")
    print(f"Planning Horizon: {start_date} to {end_date} ({results['total_horizon_days']} days)")
    print(f"Manufacturing Node: {mfg_node}")
    print(f"Demand Nodes: {sorted(demand_nodes)}\n")

    for dest_node in sorted(demand_nodes):
        # Calculate minimum transit time from manufacturing to this demand node
        min_transit = calculate_min_transit_days(mfg_node, dest_node, routes)

        if min_transit == float('inf'):
            print(f"WARNING: No route exists from {mfg_node} to {dest_node}!")
            results['restriction_details'][dest_node] = {
                'min_transit_days': min_transit,
                'latest_safe_departure': None,
                'unreachable_reason': 'NO_ROUTE',
            }
            continue

        # Calculate latest safe departure date
        latest_safe_departure = calculate_latest_safe_departure(end_date, min_transit)

        # Earliest possible delivery (transit from start_date)
        earliest_delivery = start_date + timedelta(days=min_transit)

        print(f"\nNode {dest_node}:")
        print(f"  Min Transit: {min_transit} days")
        print(f"  Latest Safe Departure: {latest_safe_departure}")
        print(f"  Earliest Delivery: {earliest_delivery}")

        # Check each date in horizon
        reachable_dates = []
        unreachable_dates = []

        current_date = start_date
        while current_date <= end_date:
            # To satisfy demand on current_date, we need to depart at:
            departure_date = current_date - timedelta(days=min_transit)

            # Check if departure is allowed (within [start_date, latest_safe_departure])
            if departure_date < start_date:
                unreachable_dates.append(current_date)
                reason = f"departure {departure_date} before start"
            elif departure_date > latest_safe_departure:
                unreachable_dates.append(current_date)
                reason = f"departure {departure_date} after latest_safe_departure {latest_safe_departure}"
            else:
                reachable_dates.append(current_date)
                reason = "OK"

            # print(f"    Demand {current_date}: departure {departure_date} → {reason}")

            current_date += timedelta(days=1)

        results['reachable_demand_days'][dest_node] = reachable_dates
        results['unreachable_demand_days'][dest_node] = unreachable_dates
        results['restriction_details'][dest_node] = {
            'min_transit_days': min_transit,
            'latest_safe_departure': latest_safe_departure,
            'earliest_delivery': earliest_delivery,
            'reachable_count': len(reachable_dates),
            'unreachable_count': len(unreachable_dates),
        }

        print(f"  Reachable Demand Days: {len(reachable_dates)}/{results['total_horizon_days']}")
        print(f"  Unreachable Demand Days: {len(unreachable_dates)}/{results['total_horizon_days']}")

        if unreachable_dates:
            print(f"  Unreachable Dates: {unreachable_dates[0]} to {unreachable_dates[-1]}")

    return results

def analyze_actual_demand_impact(
    results: Dict,
    demand_per_day: float = 1000.0  # Simplified assumption
) -> None:
    """Calculate actual demand quantities that are unreachable."""

    print("\n\n=== DEMAND IMPACT ANALYSIS ===\n")

    total_reachable_qty = 0
    total_unreachable_qty = 0

    for node, unreachable_dates in results['unreachable_demand_days'].items():
        reachable_dates = results['reachable_demand_days'][node]

        unreachable_qty = len(unreachable_dates) * demand_per_day
        reachable_qty = len(reachable_dates) * demand_per_day

        total_reachable_qty += reachable_qty
        total_unreachable_qty += unreachable_qty

        if unreachable_qty > 0:
            print(f"Node {node}:")
            print(f"  Unreachable Demand: {unreachable_qty:,.0f} units ({len(unreachable_dates)} days)")
            print(f"  Reachable Demand: {reachable_qty:,.0f} units ({len(reachable_dates)} days)")

    print(f"\nTOTAL ACROSS ALL NODES:")
    print(f"  Reachable Demand: {total_reachable_qty:,.0f} units")
    print(f"  Unreachable Demand: {total_unreachable_qty:,.0f} units")
    print(f"  Total Demand: {total_reachable_qty + total_unreachable_qty:,.0f} units")

    if total_unreachable_qty > 0:
        unreachable_pct = 100 * total_unreachable_qty / (total_reachable_qty + total_unreachable_qty)
        print(f"  Unreachable %: {unreachable_pct:.1f}%")

        print(f"\n⚠️  EXPECTED BEHAVIOR:")
        print(f"  - Model should produce ~{total_reachable_qty:,.0f} units (for reachable demand)")
        print(f"  - Model should NOT produce for {total_unreachable_qty:,.0f} units (unreachable)")
        print(f"  - Shortage should be {total_unreachable_qty:,.0f} units (accepted via allow_shortages)")
        print(f"\n🔍 IF MODEL PRODUCES MORE THAN {total_reachable_qty:,.0f}:")
        print(f"  - Check if production is satisfying demand through unexpected routes")
        print(f"  - Check if inventory is building up without outflow")
        print(f"  - Check if model has different route paths than assumed")

def main():
    """Run diagnostic analysis."""

    # Define demand nodes (breadrooms)
    demand_nodes = {'6102', '6105', '6110', '6124', '6128', '6130', '6131'}

    # Analyze reachability
    results = analyze_demand_reachability(
        start_date=START_DATE,
        end_date=END_DATE,
        routes=ROUTES,
        demand_nodes=demand_nodes,
        mfg_node='6122'
    )

    # Analyze demand impact (simplified - assumes uniform demand)
    analyze_actual_demand_impact(results, demand_per_day=1000.0)

    print("\n\n=== KEY QUESTIONS FOR MODEL ===\n")
    print("1. What demand IS being satisfied?")
    print("   → Check solution: sum(shortages) should equal unreachable demand")
    print("   → Check solution: sum(production) should equal reachable demand (approx)")
    print("\n2. If production > reachable demand, where are units going?")
    print("   → Check inventory buildup at hubs (6104, 6125, Lineage)")
    print("   → Check if shipments are created to unreachable nodes despite restriction")
    print("\n3. Is the restriction working correctly?")
    print("   → Compare model's shipment_cohort_index_set with expected dates above")
    print("   → Verify no shipments exist with departure > latest_safe_departure")

if __name__ == '__main__':
    main()
