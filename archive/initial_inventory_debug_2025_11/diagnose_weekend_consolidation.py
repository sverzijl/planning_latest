"""Diagnostic script for weekend production consolidation bug.

This script analyzes solve results to identify weekend consolidation inefficiencies
where the same product is produced across consecutive weekend days, resulting in
duplicate 4-hour minimum payments.

Usage:
    python diagnose_weekend_consolidation.py [solve_file.json]

If no file specified, uses the most recent solve from solves/ directory.
"""

import json
import sys
from pathlib import Path
from datetime import date, datetime
from collections import defaultdict


def parse_solve_file(file_path):
    """Load and parse solve file."""
    with open(file_path, 'r') as f:
        return json.load(f)


def extract_production_data(data):
    """Extract production by date and product."""
    production = data['solution_data']['metadata']['production_by_date_product']
    labor_hours = data['solution_data']['metadata']['labor_hours_by_date']

    # Parse production data
    production_by_date = defaultdict(dict)

    for key_str, qty in production.items():
        if qty <= 0:
            continue

        # Parse string tuple: "(datetime.date(2025, 11, 1), 'PRODUCT NAME')"
        try:
            # Extract date
            date_start = key_str.find("date(") + 5
            date_end = key_str.find(")", date_start)
            date_parts = key_str[date_start:date_end].split(", ")
            prod_date = date(int(date_parts[0]), int(date_parts[1]), int(date_parts[2]))

            # Extract product (between last two quotes)
            parts = key_str.split("'")
            product = parts[-2] if len(parts) >= 2 else "Unknown"

            production_by_date[prod_date][product] = qty

        except Exception as e:
            print(f"Warning: Failed to parse key {key_str}: {e}")
            continue

    return production_by_date, labor_hours


def find_weekend_consolidation_opportunities(production_by_date, labor_hours):
    """Find cases where same product is produced on consecutive weekend days."""

    opportunities = []

    # Sort dates
    sorted_dates = sorted(production_by_date.keys())

    for i in range(len(sorted_dates) - 1):
        date1 = sorted_dates[i]
        date2 = sorted_dates[i + 1]

        # Check if consecutive days
        if (date2 - date1).days != 1:
            continue

        # Check if both are weekends (Saturday=5, Sunday=6)
        if date1.weekday() not in [5, 6] or date2.weekday() not in [5, 6]:
            continue

        # Find products produced on both days
        products_day1 = set(production_by_date[date1].keys())
        products_day2 = set(production_by_date[date2].keys())
        common_products = products_day1 & products_day2

        if common_products:
            labor1 = labor_hours.get(str(date1), {})
            labor2 = labor_hours.get(str(date2), {})

            for product in common_products:
                qty1 = production_by_date[date1][product]
                qty2 = production_by_date[date2][product]

                # Calculate waste
                hours_paid = labor1.get('paid', 0) + labor2.get('paid', 0)
                hours_used = labor1.get('used', 0) + labor2.get('used', 0)

                # Estimate savings (assuming could consolidate to one day)
                # Current: 2 × 4-hour minimum = 8 hours
                # Consolidated: 1 × 4-hour minimum = 4 hours
                # Savings: 4 hours at weekend rate (~$1,320/hr = $5,280)

                opportunities.append({
                    'date1': date1,
                    'date2': date2,
                    'product': product,
                    'qty1': qty1,
                    'qty2': qty2,
                    'total_qty': qty1 + qty2,
                    'hours_paid': hours_paid,
                    'hours_used': hours_used,
                    'waste_hours': hours_paid - 4.0,  # Could pay just 4h if consolidated
                    'estimated_savings': (hours_paid - 4.0) * 1320,  # $1320/hr weekend rate
                })

    return opportunities


def analyze_friday_capacity(production_by_date, labor_hours):
    """Check if Friday before weekend has spare capacity."""

    capacity_analysis = []

    for prod_date in sorted(production_by_date.keys()):
        # Check if this is a weekend day
        if prod_date.weekday() not in [5, 6]:
            continue

        # Find the previous Friday
        days_back = (prod_date.weekday() - 4) % 7  # Days back to Friday
        if days_back == 0:
            days_back = 7  # If Saturday, go back 1 day; if Sunday, go back 2

        from datetime import timedelta
        friday = prod_date - timedelta(days=prod_date.weekday() - 4 if prod_date.weekday() == 5 else prod_date.weekday() + 2)

        # Get Friday labor
        friday_labor = labor_hours.get(str(friday), {})
        friday_used = friday_labor.get('used', 0)
        friday_capacity = 14.0 - friday_used  # Max 14 hours (12 fixed + 2 OT)

        # Get weekend production
        weekend_total = sum(production_by_date[prod_date].values())

        capacity_analysis.append({
            'weekend_date': prod_date,
            'friday_date': friday,
            'friday_used': friday_used,
            'friday_spare': friday_capacity,
            'weekend_production': weekend_total,
            'can_absorb': friday_capacity >= (weekend_total / 1400 + 1.0),  # 1h overhead
        })

    return capacity_analysis


def main():
    """Main diagnostic function."""

    # Get solve file
    if len(sys.argv) > 1:
        solve_file = Path(sys.argv[1])
    else:
        # Find most recent solve
        solves = sorted(Path('solves').rglob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        if not solves:
            print("Error: No solve files found in solves/ directory")
            sys.exit(1)
        solve_file = solves[0]
        print(f"Using most recent solve: {solve_file}\n")

    # Load data
    data = parse_solve_file(solve_file)
    production_by_date, labor_hours = extract_production_data(data)

    # Find consolidation opportunities
    print("=" * 80)
    print("WEEKEND CONSOLIDATION DIAGNOSTIC REPORT")
    print("=" * 80)

    opportunities = find_weekend_consolidation_opportunities(production_by_date, labor_hours)

    if opportunities:
        print(f"\n🚨 FOUND {len(opportunities)} CONSOLIDATION OPPORTUNITIES:\n")

        total_waste = 0
        total_savings = 0

        for opp in opportunities:
            print(f"{opp['date1'].strftime('%A, %b %d')} → {opp['date2'].strftime('%A, %b %d')}:")
            print(f"  Product: {opp['product']}")
            print(f"  Quantities: {opp['qty1']} + {opp['qty2']} = {opp['total_qty']} units")
            print(f"  Current labor: {opp['hours_paid']:.1f} hours paid ({opp['hours_used']:.2f} used)")
            print(f"  If consolidated: 4.0 hours paid")
            print(f"  Waste: {opp['waste_hours']:.1f} hours")
            print(f"  💰 Potential savings: ${opp['estimated_savings']:,.0f}")
            print()

            total_waste += opp['waste_hours']
            total_savings += opp['estimated_savings']

        print(f"{'=' * 80}")
        print(f"TOTAL POTENTIAL SAVINGS: ${total_savings:,.0f} ({total_waste:.1f} wasted hours)")
        print(f"{'=' * 80}\n")
    else:
        print("\n✅ No weekend consolidation opportunities found.\n")

    # Friday capacity analysis
    capacity = analyze_friday_capacity(production_by_date, labor_hours)

    print(f"\n{'=' * 80}")
    print("FRIDAY CAPACITY ANALYSIS")
    print(f"{'=' * 80}\n")

    for cap in capacity:
        if cap['weekend_date'].weekday() == 5:  # Saturday only
            print(f"Weekend of {cap['weekend_date'].strftime('%b %d')}:")
            print(f"  Friday {cap['friday_date'].strftime('%b %d')}: {cap['friday_used']:.2f} / 14.0 hours")
            print(f"  Spare capacity: {cap['friday_spare']:.2f} hours ({int(cap['friday_spare'] * 1400)} units)")
            print(f"  Weekend production: {cap['weekend_production']:.0f} units")

            if cap['can_absorb']:
                print(f"  ⚠️  Friday COULD absorb weekend production")
            else:
                print(f"  ✅ Friday at capacity, weekend justified")
            print()

    # Cost component analysis
    print(f"\n{'=' * 80}")
    print("COST COMPONENT ANALYSIS")
    print(f"{'=' * 80}\n")

    meta = data['solution_data']['metadata']
    obj = data['objective_value']

    costs = {
        'Labor': meta.get('total_labor_cost', 0),
        'Transport': meta.get('total_transport_cost', 0),
        'Storage': meta.get('total_holding_cost', 0),
        'Shortage Penalty': meta.get('total_shortage_cost', 0),
        'Freshness Penalty': meta.get('total_staleness_cost', 0),
        'Changeover': meta.get('total_changeover_cost', 0),
        'Waste (End Inventory)': meta.get('total_waste_cost', 0),
    }

    # Show production cost separately (not in objective after refactor)
    production_cost_ref = meta.get('total_production_cost_reference', meta.get('total_production_cost', 0))

    sum_known = sum(costs.values())
    missing = obj - sum_known

    for name, cost in costs.items():
        pct = (cost / obj * 100) if obj > 0 else 0
        print(f"{name:20s}: ${cost:>12,.2f}  ({pct:5.1f}%)")

    print(f"{'-' * 50}")
    print(f"{'Incremental Total':20s}: ${sum_known:>12,.2f}  ({sum_known/obj*100:5.1f}%)")

    if production_cost_ref > 0:
        print(f"{'Production (ref)':20s}: ${production_cost_ref:>12,.2f}  (not in objective)")

    if abs(missing) > 1:
        print(f"{'⚠️  Discrepancy':20s}: ${missing:>12,.2f}  ({abs(missing)/obj*100:5.1f}%)")
        if abs(missing) > 1000:
            print(f"\n⚠️  WARNING: Large discrepancy (${abs(missing):,.0f})")
    else:
        print(f"{'✅ Objective':20s}: ${obj:>12,.2f}  (100.0%)")

    # Show end inventory if available
    end_inv = meta.get('end_horizon_inventory_units', 0)
    if end_inv > 0:
        print(f"\n📦 End-of-horizon inventory: {end_inv:,.0f} units (treated as waste)")

    print(f"\n{'=' * 80}\n")


if __name__ == '__main__':
    main()
