#!/usr/bin/env python3
"""
Test 12-week solve and validate results comprehensively.

This will find issues that only appear at longer horizons.
"""

import sys
from pathlib import Path
from datetime import timedelta

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from tests.conftest import create_test_products


def main():
    print("="*80)
    print("12-WEEK SOLVE TEST - Comprehensive Validation")
    print("="*80)

    # Load data
    parser = MultiFileParser(
        forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
        network_file='data/examples/Network_Config.xlsx',
        inventory_file='data/examples/inventory_latest.XLSX'
    )

    forecast, locations, routes, labor_calendar, truck_schedules, cost_structure = parser.parse_all()

    inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
    inventory_snapshot = inv_parser.parse()

    # 12-week horizon
    planning_start = inventory_snapshot.snapshot_date
    planning_end = planning_start + timedelta(weeks=12)

    print(f"\nPlanning horizon: {planning_start} to {planning_end} (12 weeks = 84 days)")

    # Convert to unified
    from src.models.location import LocationType
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manufacturing_site = manufacturing_locations[0]

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules, manufacturing_site.id)

    product_ids = sorted(set(entry.product_id for entry in forecast.entries
                            if planning_start <= entry.forecast_date <= planning_end))
    products = create_test_products(product_ids)

    demand_in_horizon = sum(
        e.quantity for e in forecast.entries
        if planning_start <= e.forecast_date <= planning_end
    )

    print(f"  Demand in horizon: {demand_in_horizon:,.0f} units")
    print(f"  Products: {len(products)}")
    print(f"  Days: {(planning_end - planning_start).days + 1}")

    # Build model
    print(f"\nBuilding model...")
    model = SlidingWindowModel(
        nodes=nodes,  # Pass as list, not dict
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=planning_start,
        end_date=planning_end,
        truck_schedules=unified_truck_schedules,
        initial_inventory=inventory_snapshot.to_optimization_dict(),
        inventory_snapshot_date=inventory_snapshot.snapshot_date,
        allow_shortages=True,
        use_pallet_tracking=True,
        use_truck_pallet_tracking=True
    )

    # Solve
    print(f"\nSolving 12-week horizon...")
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

    # Extract and validate results
    print(f"\n" + "="*80)
    print(f"RESULTS VALIDATION")
    print(f"="*80)

    total_production = solution.total_production
    total_shortage = solution.total_shortage_units
    fill_rate = ((demand_in_horizon - total_shortage) / demand_in_horizon * 100) if demand_in_horizon > 0 else 0

    print(f"\n1. Basic Metrics:")
    print(f"   Total demand: {demand_in_horizon:,.0f} units")
    print(f"   Total production: {total_production:,.0f} units")
    print(f"   Total shortage: {total_shortage:,.0f} units")
    print(f"   Fill rate: {fill_rate:.1f}%")

    # Validation checks
    issues = []

    # Check 1: Production > 0
    if total_production <= 0:
        issues.append("❌ ZERO PRODUCTION")

    # Check 2: Fill rate reasonable
    if fill_rate < 50:
        issues.append(f"❌ LOW FILL RATE: {fill_rate:.1f}%")

    # Check 3: Production batches exist
    if len(solution.production_batches) == 0:
        issues.append("❌ NO PRODUCTION BATCHES")

    # Check 4: Shipments exist
    if len(solution.shipments) == 0:
        issues.append("❌ NO SHIPMENTS")

    # Check 5: Labor hours used
    if len(solution.labor_hours_by_date) == 0:
        issues.append("❌ NO LABOR HOURS")

    # Check 6: Costs make sense
    if solution.costs.total < 1000:
        issues.append("❌ TOTAL COST TOO LOW")

    # Check 7: Check for inventory at end (waste)
    # Get last day inventory from solution
    if hasattr(solution, 'inventory_state') and solution.inventory_state:
        last_date = max(solution.inventory_state.keys(), default=None)
        if last_date:
            end_inventory = sum(
                inv.quantity for inv in solution.inventory_state.get(last_date, {}).values()
            )
            if end_inventory > demand_in_horizon * 0.5:
                issues.append(f"⚠️  LARGE END INVENTORY: {end_inventory:,.0f} units (>{demand_in_horizon*0.5:,.0f})")

    # Check 8: Production by date coverage
    production_by_date = {}
    for batch in solution.production_batches:
        production_by_date[batch.production_date] = production_by_date.get(batch.production_date, 0) + batch.quantity

    production_days = len([d for d, qty in production_by_date.items() if qty > 0])
    total_days = (planning_end - planning_start).days + 1

    print(f"\n2. Production Coverage:")
    print(f"   Days with production: {production_days}/{total_days}")
    print(f"   Production days: {production_days/total_days*100:.1f}%")

    if production_days == 0:
        issues.append("❌ NO PRODUCTION ON ANY DAY")

    # Check 9: Shipments coverage
    shipment_days = len(set(s.departure_date for s in solution.shipments))

    print(f"\n3. Shipment Coverage:")
    print(f"   Days with shipments: {shipment_days}/{total_days}")

    if shipment_days == 0:
        issues.append("❌ NO SHIPMENTS ON ANY DAY")

    # Check 10: Cost breakdown makes sense
    print(f"\n4. Cost Breakdown:")
    print(f"   Production: ${solution.costs.production.total:,.2f}")
    print(f"   Labor: ${solution.costs.labor.total:,.2f}")
    print(f"   Transport: ${solution.costs.transport.total:,.2f}")
    print(f"   Holding: ${solution.costs.holding.total:,.2f}")
    print(f"   Waste: ${solution.costs.waste.total:,.2f}")
    print(f"   Total: ${solution.costs.total:,.2f}")

    # Check if costs are reasonable
    if solution.costs.total < total_production * 0.5:
        issues.append(f"⚠️  TOTAL COST SUSPICIOUSLY LOW: ${solution.costs.total:,.2f} vs production {total_production:,.0f}")

    # Report issues
    print(f"\n" + "="*80)
    if issues:
        print(f"❌ ISSUES FOUND:")
        for issue in issues:
            print(f"   {issue}")
        print(f"="*80)
        return False
    else:
        print(f"✅ ALL VALIDATIONS PASSED!")
        print(f"="*80)
        return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
