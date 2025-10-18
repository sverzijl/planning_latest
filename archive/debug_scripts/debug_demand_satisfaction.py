#!/usr/bin/env python3
"""Debug demand satisfaction logic - find missing 30k units."""

from datetime import date, timedelta
from src.parsers.excel_parser import ExcelParser
from src.optimization.unified_node_model import UnifiedNodeModel


def main():
    # Parse data files using MultiFileParser
    from src.parsers.multi_file_parser import MultiFileParser
    from src.models.manufacturing import ManufacturingSite
    from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter

    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Find manufacturing site
    manufacturing_site = None
    for loc in locations:
        if loc.type == 'manufacturing':
            manufacturing_site = ManufacturingSite(
                id=loc.id, name=loc.name, type=loc.type,
                storage_mode=loc.storage_mode, capacity=loc.capacity,
                latitude=loc.latitude, longitude=loc.longitude,
                production_rate=1400.0
            )
            break

    # Build model for 4-week horizon (as reported by user)
    all_dates = [entry.forecast_date for entry in forecast.entries]
    start_date = min(all_dates)
    end_date = start_date + timedelta(days=27)  # 4 weeks (28 days)

    # Convert legacy data to unified format
    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=None,
        inventory_snapshot_date=None,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    print("\n" + "="*80)
    print("DEMAND DATA ANALYSIS")
    print("="*80)

    # Analyze demand dictionary
    print(f"\nDemand dictionary (self.demand):")
    print(f"  Total entries: {len(model.demand)}")
    print(f"  Total demand quantity: {sum(model.demand.values()):,.0f}")

    # Group by location
    from collections import defaultdict
    by_location = defaultdict(float)
    by_product = defaultdict(float)
    by_date = defaultdict(float)

    for (node_id, prod, demand_date), qty in model.demand.items():
        by_location[node_id] += qty
        by_product[prod] += qty
        by_date[demand_date] += qty

    print(f"\n  Demand by location:")
    for loc in sorted(by_location.keys()):
        print(f"    {loc}: {by_location[loc]:,.0f} units")

    print(f"\n  Demand by product:")
    for prod in sorted(by_product.keys()):
        print(f"    {prod}: {by_product[prod]:,.0f} units")

    print(f"\n  Demand by date:")
    for d in sorted(by_date.keys()):
        print(f"    {d}: {by_date[d]:,.0f} units")

    # Analyze demand_cohort_index_set
    print(f"\n" + "="*80)
    print("DEMAND COHORT INDEX ANALYSIS")
    print("="*80)

    # Build model to get demand_cohort_index_set
    pyomo_model = model.build_model()

    print(f"\nDemand cohort index set:")
    print(f"  Total indices: {len(model.demand_cohort_index_set)}")

    # Count how many cohorts exist for each (node, prod, demand_date)
    cohort_counts = defaultdict(int)
    for (node_id, prod, prod_date, demand_date) in model.demand_cohort_index_set:
        key = (node_id, prod, demand_date)
        cohort_counts[key] += 1

    print(f"\n  Cohorts per demand entry (node, prod, demand_date):")
    print(f"    Average cohorts: {sum(cohort_counts.values()) / len(cohort_counts):.1f}")
    print(f"    Min cohorts: {min(cohort_counts.values())}")
    print(f"    Max cohorts: {max(cohort_counts.values())}")

    # Check if all demand entries have cohorts
    missing_cohorts = []
    for demand_key in model.demand.keys():
        if demand_key not in cohort_counts or cohort_counts[demand_key] == 0:
            missing_cohorts.append(demand_key)

    if missing_cohorts:
        print(f"\n  WARNING: {len(missing_cohorts)} demand entries have NO cohorts!")
        print(f"  Missing demand quantity: {sum(model.demand[k] for k in missing_cohorts):,.0f}")
        print(f"\n  Examples of missing cohorts:")
        for key in missing_cohorts[:5]:
            node_id, prod, demand_date = key
            qty = model.demand[key]
            print(f"    {node_id}, {prod}, {demand_date}: {qty:,.0f} units (NO COHORTS)")
    else:
        print(f"\n  All demand entries have cohorts!")

    # Analyze constraint structure
    print(f"\n" + "="*80)
    print("CONSTRAINT ANALYSIS")
    print("="*80)

    print(f"\nDemand satisfaction constraint:")
    print(f"  Constraint count: {len(pyomo_model.demand_satisfaction_con)}")

    # Sample constraint for first demand entry
    first_demand_key = next(iter(model.demand.keys()))
    node_id, prod, demand_date = first_demand_key
    demand_qty = model.demand[first_demand_key]

    print(f"\n  Sample constraint for {node_id}, {prod}, {demand_date}:")
    print(f"    Demand quantity: {demand_qty:,.0f}")

    # Count how many cohorts contribute
    cohort_count = 0
    for prod_date in pyomo_model.dates:
        if (node_id, prod, prod_date, demand_date) in model.demand_cohort_index_set:
            cohort_count += 1

    print(f"    Contributing cohorts: {cohort_count}")
    print(f"    Cohort prod_dates: {[str(pd) for pd in sorted(pyomo_model.dates) if (node_id, prod, pd, demand_date) in model.demand_cohort_index_set]}")

    # Check if shortage variable exists
    if model.allow_shortages:
        if (node_id, prod, demand_date) in pyomo_model.shortage:
            print(f"    Shortage variable: EXISTS")
        else:
            print(f"    Shortage variable: MISSING")

    print(f"\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    total_demand = sum(model.demand.values())
    demand_with_cohorts = sum(model.demand[k] for k in model.demand.keys() if k in cohort_counts and cohort_counts[k] > 0)
    demand_without_cohorts = total_demand - demand_with_cohorts

    print(f"\n  Total demand: {total_demand:,.0f} units")
    print(f"  Demand with cohorts: {demand_with_cohorts:,.0f} units")
    print(f"  Demand without cohorts: {demand_without_cohorts:,.0f} units")

    if demand_without_cohorts > 0:
        print(f"\n  POTENTIAL BUG: {demand_without_cohorts:,.0f} units of demand have NO cohorts!")
        print(f"  This demand CANNOT be satisfied by the model!")
        print(f"  The constraint sums over empty set, giving 0 supply.")
        print(f"  With allow_shortages=True, these become automatic shortages.")
    else:
        print(f"\n  All demand has cohorts - no structural issue found.")

    # Now solve and check actual vs expected
    print(f"\n" + "="*80)
    print("SOLVING MODEL")
    print("="*80)

    result = model.solve(time_limit_seconds=90, mip_gap=0.02)

    print(f"\nSolve result: {result.termination_condition}")
    print(f"Solve time: {result.solve_time_seconds:.1f}s")

    solution = model.get_solution()

    # Extract metrics
    production_total = sum(solution.get('production_by_date_product', {}).values())
    shortages = solution.get('shortages_by_dest_product_date', {})
    total_shortage = sum(shortages.values())

    # Calculate satisfied demand from cohort consumption
    cohort_demand = solution.get('cohort_demand_consumption', {})
    satisfied_from_cohort = sum(cohort_demand.values())

    # Calculate expected satisfied = total_demand - total_shortage
    expected_satisfied = total_demand - total_shortage

    print(f"\n" + "="*80)
    print("MATERIAL BALANCE CHECK")
    print("="*80)

    print(f"\nProduction: {production_total:,.0f} units")
    print(f"Total demand (in horizon): {total_demand:,.0f} units")
    print(f"")
    print(f"From shortage variable:")
    print(f"  Total shortage: {total_shortage:,.0f} units")
    print(f"  Expected satisfied: {expected_satisfied:,.0f} units (= demand - shortage)")
    print(f"")
    print(f"From cohort consumption:")
    print(f"  Satisfied from cohort: {satisfied_from_cohort:,.0f} units")
    print(f"")
    print(f"DISCREPANCY:")
    print(f"  Expected satisfied: {expected_satisfied:,.0f}")
    print(f"  Actual satisfied (cohort): {satisfied_from_cohort:,.0f}")
    print(f"  GAP: {expected_satisfied - satisfied_from_cohort:,.0f} units")

    if abs(expected_satisfied - satisfied_from_cohort) > 1:
        print(f"\n  BUG FOUND: Demand satisfaction math doesn't add up!")
        print(f"  The constraint says: cohort_supply + shortage = demand")
        print(f"  But actual cohort_supply ≠ (demand - shortage)")

        # Find specific examples where shortage != 0 but cohort consumption is wrong
        print(f"\n  Examples of problematic demand entries:")
        count = 0
        for (node_id, prod, demand_date) in list(model.demand.keys())[:10]:
            demand_qty = model.demand[(node_id, prod, demand_date)]
            shortage_qty = shortages.get((node_id, prod, demand_date), 0.0)

            # Sum cohort consumption for this demand entry
            cohort_sum = sum(
                qty for (n, p, pd, dd), qty in cohort_demand.items()
                if n == node_id and p == prod and dd == demand_date
            )

            expected = demand_qty - shortage_qty
            actual = cohort_sum
            gap = expected - actual

            if abs(gap) > 0.1:
                count += 1
                print(f"    {node_id}, {prod}, {demand_date}:")
                print(f"      Demand: {demand_qty:,.0f}, Shortage: {shortage_qty:,.0f}")
                print(f"      Expected satisfied: {expected:,.0f}, Actual cohort: {actual:,.0f}")
                print(f"      GAP: {gap:,.0f}")

                if count >= 5:
                    break
    else:
        print(f"\n  Math checks out! Demand satisfaction is consistent.")


if __name__ == '__main__':
    main()
