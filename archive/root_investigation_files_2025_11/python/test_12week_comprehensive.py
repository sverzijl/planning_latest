#!/usr/bin/env python3
"""
Comprehensive 12-week solve test with proper validation architecture.

Uses load_validated_data() to ensure product IDs are resolved.
Then validates EVERY aspect of the results to find issues.
"""

import sys
from pathlib import Path
from datetime import timedelta
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from src.validation.data_coordinator import load_validated_data
from src.optimization.sliding_window_model import SlidingWindowModel
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from tests.conftest import create_test_products


def main():
    print("="*80)
    print("12-WEEK COMPREHENSIVE VALIDATION")
    print("="*80)

    # Use validation architecture to load data
    print("\nLoading data with validation architecture...")
    data = load_validated_data(
        forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
        network_file='data/examples/Network_Config.xlsx',
        inventory_file='data/examples/inventory_latest.XLSX',
        planning_weeks=12
    )

    print(f"\n✓ Data validated:")
    print(f"  Products: {len(data.products)}")
    print(f"  Demand entries: {len(data.demand_entries)}")
    print(f"  Inventory entries: {len(data.inventory_entries)}")
    print(f"  Initial inventory: {sum(e.quantity for e in data.inventory_entries):,.0f} units")

    # Also need network components
    parser = MultiFileParser(
        forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
        network_file='data/examples/Network_Config.xlsx',
        inventory_file='data/examples/inventory_latest.XLSX'
    )

    forecast, locations, routes, labor_calendar, truck_schedules, cost_structure = parser.parse_all()

    from src.models.location import LocationType
    manufacturing_site = [loc for loc in locations if loc.type == LocationType.MANUFACTURING][0]

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules, manufacturing_site.id)

    product_ids = sorted(set(e.product_id for e in data.demand_entries))
    products = create_test_products(product_ids)

    # Build model
    print(f"\nBuilding 12-week model...")
    model = SlidingWindowModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=data.planning_start_date,
        end_date=data.planning_end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=data.get_inventory_dict(),  # Validated!
        inventory_snapshot_date=data.inventory_snapshot_date,
        allow_shortages=True,
        use_pallet_tracking=True,
        use_truck_pallet_tracking=True
    )

    # Solve
    print(f"\nSolving...")
    result = model.solve(
        solver_name='appsi_highs',
        time_limit_seconds=120,
        mip_gap=0.02,
        tee=False
    )

    print(f"  Status: {result.termination_condition}")
    print(f"  Solve time: {result.solve_time_seconds:.1f}s")

    # Get solution
    solution = model.get_solution()

    # COMPREHENSIVE VALIDATION
    print(f"\n" + "="*80)
    print(f"COMPREHENSIVE RESULTS VALIDATION")
    print(f"="*80)

    issues = []
    total_demand = sum(e.quantity for e in data.demand_entries)

    # 1. Basic metrics
    print(f"\n1. BASIC METRICS:")
    print(f"   Total demand: {total_demand:,.0f} units")
    print(f"   Production: {solution.total_production:,.0f} units")
    print(f"   Shortage: {solution.total_shortage_units:,.0f} units")
    fill_rate = ((total_demand - solution.total_shortage_units) / total_demand * 100)
    print(f"   Fill rate: {fill_rate:.1f}%")

    if solution.total_production == 0:
        issues.append("❌ ZERO PRODUCTION")

    if fill_rate < 50:
        issues.append(f"❌ LOW FILL RATE: {fill_rate:.1f}%")

    # 2. Production batches
    print(f"\n2. PRODUCTION BATCHES:")
    print(f"   Batch count: {len(solution.production_batches)}")

    if len(solution.production_batches) == 0:
        issues.append("❌ NO PRODUCTION BATCHES")

    # Check production by week
    production_by_week = defaultdict(float)
    for batch in solution.production_batches:
        week = (batch.date - data.planning_start_date).days // 7
        production_by_week[week] += batch.quantity

    print(f"   Production by week:")
    for week in range(12):
        qty = production_by_week.get(week, 0)
        print(f"     Week {week+1}: {qty:>10,.0f} units")

        # Check for weeks with zero production (might be OK due to init inv)
        if week > 2 and qty == 0:
            issues.append(f"⚠️  Week {week+1} has zero production")

    # 3. Shipments
    print(f"\n3. SHIPMENTS:")
    print(f"   Shipment count: {len(solution.shipments)}")

    if len(solution.shipments) == 0:
        issues.append("❌ NO SHIPMENTS")

    # 4. Labor
    print(f"\n4. LABOR:")
    print(f"   Days with labor: {len(solution.labor_hours_by_date)}")

    total_labor_hours = sum(
        labor.used for labor in solution.labor_hours_by_date.values()
    )
    print(f"   Total labor hours: {total_labor_hours:.0f} hours")

    if total_labor_hours == 0 and solution.total_production > 0:
        issues.append("❌ PRODUCTION WITHOUT LABOR HOURS")

    # 5. Costs
    print(f"\n5. COST BREAKDOWN:")
    print(f"   Production: ${solution.costs.production.total:,.2f}")
    print(f"   Labor: ${solution.costs.labor.total:,.2f}")
    print(f"   Transport: ${solution.costs.transport.total:,.2f}")
    print(f"   Holding: ${solution.costs.holding.total:,.2f}")
    print(f"   Waste: ${solution.costs.waste.total:,.2f}")
    print(f"   Total: ${solution.costs.total:,.2f}")

    # Sanity check: production cost should be reasonable
    expected_prod_cost = solution.total_production * 1.30
    if abs(solution.costs.production.total - expected_prod_cost) > expected_prod_cost * 0.5:
        issues.append(f"⚠️  Production cost mismatch: ${solution.costs.production.total:,.2f} vs expected ${expected_prod_cost:,.2f}")

    # 6. Inventory at end
    print(f"\n6. END-OF-HORIZON INVENTORY:")
    if hasattr(solution, 'inventory_state') and solution.inventory_state:
        last_date = max(solution.inventory_state.keys())
        end_inventory_total = 0
        for state_dict in solution.inventory_state.get(last_date, {}).values():
            for inv in state_dict.values():
                end_inventory_total += inv.quantity

        print(f"   End inventory: {end_inventory_total:,.0f} units")

        if end_inventory_total > total_demand * 0.3:
            issues.append(f"⚠️  LARGE END INVENTORY: {end_inventory_total:,.0f} units (>{total_demand*0.3:,.0f})")

        # Check if end inventory is negative (impossible!)
        if end_inventory_total < 0:
            issues.append(f"❌ NEGATIVE END INVENTORY: {end_inventory_total:,.0f}")

    # 7. Production vs demand sanity check
    print(f"\n7. SUPPLY-DEMAND BALANCE:")
    total_supply = sum(e.quantity for e in data.inventory_entries) + solution.total_production
    total_consumed = total_demand - solution.total_shortage_units

    print(f"   Total supply: {total_supply:,.0f} (init_inv + production)")
    print(f"   Total consumed: {total_consumed:,.0f} (demand - shortage)")
    print(f"   Difference: {abs(total_supply - total_consumed):,.0f}")

    # Should be close (allowing for end inventory)
    if abs(total_supply - total_consumed) > total_demand * 0.5:
        issues.append(f"⚠️  LARGE SUPPLY-DEMAND IMBALANCE: {abs(total_supply - total_consumed):,.0f}")

    # 8. Check for NaN or infinite values
    print(f"\n8. DATA QUALITY:")
    if solution.costs.total != solution.costs.total:  # NaN check
        issues.append("❌ TOTAL COST IS NaN")

    if solution.costs.total < 0:
        issues.append("❌ NEGATIVE TOTAL COST")

    if solution.total_production < 0:
        issues.append("❌ NEGATIVE PRODUCTION")

    # 9. Batch sizes check (should be multiples of units_per_mix)
    print(f"\n9. PRODUCTION BATCH VALIDATION:")
    non_standard_batches = []
    for batch in solution.production_batches[:10]:  # Check first 10
        if batch.quantity % 415 != 0:  # Assuming units_per_mix = 415
            non_standard_batches.append(f"  Batch {batch.id}: {batch.quantity} (not multiple of 415)")

    if non_standard_batches:
        print(f"   Non-standard batch sizes found:")
        for b in non_standard_batches:
            print(b)
        # This might be OK if units_per_mix varies by product

    # 10. Dates validation
    print(f"\n10. DATE VALIDATION:")
    production_dates = set(batch.date for batch in solution.production_batches)
    shipment_dates = set(ship.departure_date for ship in solution.shipments)

    earliest_prod = min(production_dates) if production_dates else None
    latest_prod = max(production_dates) if production_dates else None

    if earliest_prod:
        print(f"   Production date range: {earliest_prod} to {latest_prod}")

        # Check if production dates are within planning horizon
        if earliest_prod < data.planning_start_date:
            issues.append(f"❌ PRODUCTION BEFORE PLANNING START: {earliest_prod}")

        if latest_prod > data.planning_end_date:
            issues.append(f"❌ PRODUCTION AFTER PLANNING END: {latest_prod}")

    # REPORT
    print(f"\n" + "="*80)
    if issues:
        print(f"❌ ISSUES FOUND IN 12-WEEK RESULTS:")
        for issue in issues:
            print(f"   {issue}")
        print(f"\n   Found {len(issues)} issues total")
        print(f"="*80)
        return False, issues
    else:
        print(f"✅ ALL VALIDATIONS PASSED!")
        print(f"   12-week solve results are valid")
        print(f"="*80)
        return True, []


if __name__ == "__main__":
    success, issues = main()
    sys.exit(0 if success else 1)
