"""
Diagnose why 28k end inventory exists at hubs despite model knowing demand = 0 in final week.

Hypothesis: Hub-to-spoke routing is constrained by timing/capacity, preventing delivery.
Result: Inventory stuck at hubs, cannot serve spoke demand, causes both shortage AND end inventory.
"""

from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.location import LocationType


def main():
    print("="*80)
    print("HUB ROUTING CONSTRAINT DIAGNOSIS")
    print("="*80)

    # Load data
    data_dir = Path("data/examples")
    forecast_file = data_dir / "Gfree Forecast.xlsm"
    network_file = data_dir / "Network_Config.xlsx"
    inventory_file = data_dir / "inventory.XLSX"

    parser = MultiFileParser(
        forecast_file=forecast_file,
        network_file=network_file,
        inventory_file=inventory_file,
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Create model components
    from src.models.manufacturing import ManufacturingSite
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id,
        name=manuf_loc.name,
        storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0,
        daily_startup_hours=0.5,
        daily_shutdown_hours=0.25,
        default_changeover_hours=0.5,
        production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    from src.models.truck_schedule import TruckScheduleCollection
    truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

    # Parse initial inventory
    inventory_snapshot = parser.parse_inventory(snapshot_date=None)
    initial_inventory = inventory_snapshot
    inventory_snapshot_date = inventory_snapshot.snapshot_date

    # Planning window
    planning_start_date = inventory_snapshot_date
    planning_end_date = date(2025, 11, 3)

    # Create and solve model
    print(f"\nCreating model: {planning_start_date} to {planning_end_date}")

    model = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing_site,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        truck_schedules=truck_schedules,
        max_routes_per_destination=5,
        allow_shortages=True,
        enforce_shelf_life=True,
        initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
        inventory_snapshot_date=inventory_snapshot_date,
        start_date=planning_start_date,
        end_date=planning_end_date,
        use_batch_tracking=True,
    )

    print(f"✓ Model created")

    result = model.solve(
        solver_name='cbc',
        time_limit_seconds=120,
        mip_gap=0.01,
        use_aggressive_heuristics=True,
        tee=False,
    )

    print(f"✓ Solved in {result.solve_time_seconds:.2f}s")

    if not (result.is_optimal() or result.is_feasible()):
        print(f"⚠ Not feasible")
        return

    # Analyze solution
    solution = model.get_solution()
    cohort_inv = solution.get('cohort_inventory', {})

    # Get shortages by location
    print(f"\n{'='*80}")
    print("SHORTAGE BY LOCATION")
    print(f"{'='*80}")

    # Model.demand is dict with keys (location, product, date)
    shortage_by_location = defaultdict(float)

    # Get shortage variables from solution
    if 'shortage' in solution:
        shortage_vars = solution['shortage']
        for key, qty in shortage_vars.items():
            if qty > 0.01:
                loc, prod, demand_date = key
                shortage_by_location[loc] += qty

    print(f"\n{'Location':<15} {'Shortage':>12}")
    print("-" * 30)
    for loc, qty in sorted(shortage_by_location.items(), key=lambda x: x[1], reverse=True):
        print(f"{loc:<15} {qty:>12,.0f}")

    # Get end inventory by location
    print(f"\n{'='*80}")
    print("END INVENTORY BY LOCATION")
    print(f"{'='*80}")

    end_inv_by_location = defaultdict(float)
    for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items():
        if curr_date == model.end_date and qty > 0.01:
            end_inv_by_location[loc] += qty

    print(f"\n{'Location':<15} {'End Inventory':>15}")
    print("-" * 33)
    for loc, qty in sorted(end_inv_by_location.items(), key=lambda x: x[1], reverse=True):
        print(f"{loc:<15} {qty:>15,.0f}")

    # Check routing from hubs
    print(f"\n{'='*80}")
    print("ROUTING ANALYSIS")
    print(f"{'='*80}")

    # Check which routes are enumerated
    print(f"\nEnumerated routes: {len(model.enumerated_routes)}")

    hub_outbound_routes = [
        r for r in model.enumerated_routes
        if r['path'][0] in [6104, 6125]
    ]

    print(f"Routes FROM hubs: {len(hub_outbound_routes)}")

    if hub_outbound_routes:
        print(f"\nHub outbound routes:")
        for r in hub_outbound_routes[:10]:  # Show first 10
            path_str = " → ".join(str(p) for p in r['path'])
            print(f"  {path_str}: {r['total_transit_days']} days, {r['transport_mode']}")

    # Analyze shipments TO hubs
    shipments = model.get_shipment_plan() or []

    shipments_to_hubs = [s for s in shipments if s.destination_id in [6104, 6125]]
    shipments_from_hubs = [s for s in shipments if s.origin_id in [6104, 6125]]

    print(f"\n{'='*80}")
    print("SHIPMENT ANALYSIS")
    print(f"{'='*80}")
    print(f"Shipments TO hubs (6104, 6125): {len(shipments_to_hubs)} shipments")
    print(f"  Total quantity: {sum(s.quantity for s in shipments_to_hubs):,.0f} units")

    print(f"\nShipments FROM hubs: {len(shipments_from_hubs)} shipments")
    print(f"  Total quantity: {sum(s.quantity for s in shipments_from_hubs):,.0f} units")

    # Check timing of hub shipments
    if shipments_from_hubs:
        hub_shipments_by_date = defaultdict(float)
        for s in shipments_from_hubs:
            hub_shipments_by_date[s.ship_date] += s.quantity

        print(f"\nHub outbound shipments by date:")
        for date_key in sorted(hub_shipments_by_date.keys()):
            qty = hub_shipments_by_date[date_key]
            print(f"  {date_key}: {qty:,.0f} units")

    # Key question: Why can't hub inventory serve spoke demand?
    print(f"\n{'='*80}")
    print("KEY QUESTION: Why can't 28k hub inventory serve 11k spoke shortage?")
    print(f"{'='*80}")

    # Check if it's a timing issue
    total_end_hub_inv = sum(qty for loc, qty in end_inv_by_location.items() if loc in [6104, 6125])
    total_shortage = sum(shortage_by_location.values())

    print(f"\nEnd inventory at hubs: {total_end_hub_inv:,.0f} units")
    print(f"Total shortage: {total_shortage:,.0f} units")
    print(f"Surplus: {total_end_hub_inv - total_shortage:,.0f} units")

    # Check shortage timing
    shortage_by_date = defaultdict(float)
    if 'shortage' in solution:
        shortage_vars = solution['shortage']
        for key, qty in shortage_vars.items():
            if qty > 0.01:
                loc, prod, demand_date = key
                shortage_by_date[demand_date] += qty

    if shortage_by_date:
        print(f"\nShortage by date (when does unmet demand occur?):")
        for date_key in sorted(shortage_by_date.keys()):
            qty = shortage_by_date[date_key]
            print(f"  {date_key}: {qty:,.0f} units")

    # Hypothesis testing
    print(f"\n{'='*80}")
    print("HYPOTHESIS TESTING")
    print(f"{'='*80}")

    print(f"\n[H1] Shortage occurs EARLY in horizon (before hub inventory arrives)?")
    if shortage_by_date:
        first_shortage_date = min(shortage_by_date.keys())
        last_shortage_date = max(shortage_by_date.keys())
        print(f"  First shortage: {first_shortage_date}")
        print(f"  Last shortage: {last_shortage_date}")
        print(f"  Horizon end: {model.end_date}")

        early_shortage = sum(qty for d, qty in shortage_by_date.items() if d < model.start_date + timedelta(days=7))
        late_shortage = sum(qty for d, qty in shortage_by_date.items() if d >= model.end_date - timedelta(days=7))

        print(f"  Early shortage (first week): {early_shortage:,.0f} units")
        print(f"  Late shortage (last week): {late_shortage:,.0f} units")

        if early_shortage > total_shortage * 0.8:
            print(f"  → CONFIRMED: Most shortage is EARLY (transit time issue)")
        else:
            print(f"  → REJECTED: Shortage distributed across horizon")

    print(f"\n[H2] Hub inventory accumulates LATE in horizon (after demand ends)?")
    # Track hub inventory over time
    hub_inv_by_date = defaultdict(float)
    for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items():
        if loc in [6104, 6125] and qty > 0.01:
            hub_inv_by_date[curr_date] += qty

    if hub_inv_by_date:
        dates_sorted = sorted(hub_inv_by_date.keys())
        first_week_avg = sum(hub_inv_by_date[d] for d in dates_sorted[:7]) / 7
        last_week_avg = sum(hub_inv_by_date[d] for d in dates_sorted[-7:]) / 7

        print(f"  First week hub inventory avg: {first_week_avg:,.0f} units/day")
        print(f"  Last week hub inventory avg: {last_week_avg:,.0f} units/day")

        if last_week_avg > first_week_avg * 1.5:
            print(f"  → CONFIRMED: Hub inventory GROWS over time")
        else:
            print(f"  → REJECTED: Hub inventory relatively stable")

    print(f"\n[H3] Hub-to-spoke routing is infeasible due to shelf life?")
    # Check if hub inventory is too old to ship
    hub_inv_at_end_with_age = defaultdict(list)
    for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items():
        if loc in [6104, 6125] and curr_date == model.end_date and qty > 0.01:
            age = (curr_date - prod_date).days
            hub_inv_at_end_with_age[loc].append((age, qty, state))

    for hub in [6104, 6125]:
        if hub in hub_inv_at_end_with_age:
            print(f"\n  Hub {hub} end inventory by age:")
            for age, qty, state in sorted(hub_inv_at_end_with_age[hub]):
                print(f"    Age {age} days, {state}: {qty:,.0f} units")

    print(f"\n{'='*80}")
    print("CONCLUSION")
    print(f"{'='*80}")

    print(f"""
The model has:
- {total_end_hub_inv:,.0f} units at hubs at end
- {total_shortage:,.0f} units of shortage at spokes

This is NOT an objective function issue. The MIP knows demand patterns perfectly.

Most likely cause: One of these constraints is binding:
1. Transit time: Inventory arrives at hubs too late to serve early demand
2. Shelf life: Hub inventory ages beyond shippable threshold
3. Routing capacity: Limited hub-to-spoke truck availability
4. Timing mismatch: Production/hub delivery doesn't align with spoke demand timing
    """)


if __name__ == "__main__":
    main()
