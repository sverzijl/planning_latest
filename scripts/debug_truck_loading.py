"""Debug script to diagnose truck loading infeasibilities.

This script loads example data and inspects:
1. Network connectivity (verify routes exist)
2. Shipment routes and first_leg_destinations
3. Truck schedules and their destinations
4. Matching logic between shipments and trucks
5. Production dates and D-1/D0 timing

Run from project root:
    python scripts/debug_truck_loading.py
"""

import sys
from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.parsers import MultiFileParser
from src.production.scheduler import ProductionScheduler
from src.distribution.shipment_planner import ShipmentPlanner
from src.distribution.truck_loader import TruckLoader
from src.network import NetworkGraphBuilder, RouteFinder
from src.shelf_life import ShelfLifeTracker, ProductState


def main():
    print("=" * 80)
    print("TRUCK LOADING DIAGNOSTIC TOOL")
    print("=" * 80)
    print()

    # Load data
    print("📂 Loading example data...")
    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast_Converted.xlsx",
        network_file="data/examples/Network_Config.xlsx"
    )

    forecast, locations, routes, labor_calendar, truck_schedules, cost_structure = parser.parse_all()

    print(f"✓ Loaded {len(forecast.entries)} forecast entries")
    print(f"✓ Loaded {len(locations)} locations")
    print(f"✓ Loaded {len(routes)} routes")
    print(f"✓ Loaded {len(truck_schedules)} truck schedules")
    print()

    # Build network graph
    print("🔗 Building network graph...")
    graph_builder = NetworkGraphBuilder(locations, routes)
    graph = graph_builder.build_graph()

    print(f"✓ Network: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
    print()

    # Check network connectivity
    print("🔍 Checking network connectivity...")
    print()

    # Find manufacturing site
    mfg_sites = [loc for loc in locations if loc.type == "manufacturing"]
    if not mfg_sites:
        print("❌ No manufacturing site found!")
        return

    mfg = mfg_sites[0]
    print(f"Manufacturing site: {mfg.id} ({mfg.name})")
    print()

    # Check routes from manufacturing
    print("Primary routes from manufacturing:")
    primary_dests = set()
    for route in routes:
        if route.origin_id == mfg.id:
            print(f"  {route.origin_id} → {route.destination_id} ({route.transport_mode}, {route.transit_time_days}d)")
            primary_dests.add(route.destination_id)
    print()

    # Check secondary routes (from hubs)
    print("Secondary routes (from hubs to breadrooms):")
    for hub_id in primary_dests:
        hub_routes = [r for r in routes if r.origin_id == hub_id]
        if hub_routes:
            print(f"  From {hub_id}:")
            for route in hub_routes:
                print(f"    {route.origin_id} → {route.destination_id} ({route.transport_mode}, {route.transit_time_days}d)")
    print()

    # Check route finding for problematic destinations
    print("🛤️  Testing route finding for problematic destinations...")
    print()

    route_finder = RouteFinder(graph_builder, ShelfLifeTracker())
    problematic_dests = ["6123", "6125", "6134", "6120"]

    for dest in problematic_dests:
        route_path = route_finder.recommend_route(
            source=mfg.id,
            target=dest,
            initial_state=ProductState.AMBIENT,
            prioritize='cost'
        )

        if route_path:
            print(f"✓ Route to {dest}: {' → '.join(route_path.path)}")
            print(f"  Transit: {route_path.total_transit_days} days, Cost: ${route_path.total_cost:.2f}")
            print(f"  Route legs: {len(route_path.route_legs)}")
            if route_path.route_legs:
                first_leg = route_path.route_legs[0]
                print(f"  First leg: {first_leg.from_location_id} → {first_leg.to_location_id}")
                print(f"  first_leg_destination would be: {first_leg.to_location_id}")
            else:
                print(f"  ⚠️  No route legs! first_leg_destination would fall back to: {dest}")
        else:
            print(f"❌ No route found to {dest}")
        print()

    # Check truck schedules
    print("🚚 Truck schedules:")
    print()

    truck_dest_map = defaultdict(list)
    for truck in truck_schedules:
        dest = truck.destination_id if truck.destination_id else "flexible"
        truck_dest_map[dest].append(truck)
        day_info = f" ({truck.day_of_week})" if truck.day_of_week else " (daily)"
        print(f"  {truck.truck_name}: {truck.departure_type} @ {truck.departure_time}")
        print(f"    → Destination: {truck.destination_id}{day_info}")
        print(f"    Capacity: {truck.capacity:.0f} units ({truck.pallet_capacity} pallets)")
    print()

    # Check if trucks exist for key destinations
    print("Truck availability by destination:")
    for dest in ["6125", "6104", "6110"]:
        trucks = truck_dest_map.get(dest, [])
        if trucks:
            print(f"  {dest}: {len(trucks)} truck(s)")
            for t in trucks:
                day_info = f" on {t.day_of_week}" if t.day_of_week else " daily"
                print(f"    - {t.departure_type}{day_info}")
        else:
            print(f"  {dest}: ❌ NO TRUCKS")
    print()

    # Run production scheduling
    print("🏭 Running production scheduling...")
    print()

    # Find manufacturing site model
    from src.models.manufacturing import ManufacturingSite
    mfg_site = ManufacturingSite(
        id=mfg.id,
        name=mfg.name,
        type=mfg.type,
        storage_mode=mfg.storage_mode,
        production_rate=1400.0,
        max_daily_capacity=19600.0,
        production_cost_per_unit=cost_structure.production_cost_per_unit
    )

    scheduler = ProductionScheduler(
        manufacturing_site=mfg_site,
        labor_calendar=labor_calendar,
        graph_builder=graph_builder
    )

    # Schedule first 10 days
    schedule = scheduler.schedule_from_forecast(
        forecast=forecast,
        initial_product_state=ProductState.AMBIENT
    )

    print(f"✓ Created {len(schedule.requirements)} production requirements")
    print(f"✓ Created {len(schedule.production_batches)} production batches")
    print()

    # Create shipments
    print("📦 Creating shipments...")
    print()

    planner = ShipmentPlanner()
    shipments = planner.create_shipments(schedule)

    print(f"✓ Created {len(shipments)} shipments")

    # Check production dates distribution
    from collections import Counter
    prod_dates = [s.production_date for s in shipments]
    date_counts = Counter(prod_dates)
    print(f"Production scheduled across {len(date_counts)} unique dates")

    # Check for weekend production
    weekend_shipments = [s for s in shipments if s.production_date.weekday() >= 5]
    if weekend_shipments:
        print(f"⚠️  WARNING: {len(weekend_shipments)} shipments have weekend production dates!")
        weekend_dates = set(s.production_date for s in weekend_shipments)
        for d in sorted(weekend_dates)[:5]:
            day_name = d.strftime("%A")
            count = sum(1 for s in weekend_shipments if s.production_date == d)
            print(f"   {d} ({day_name}): {count} shipments")
    print()

    # Analyze shipments by first_leg_destination
    print("Shipments grouped by first_leg_destination:")
    shipments_by_first_leg = defaultdict(list)
    for shipment in shipments:
        shipments_by_first_leg[shipment.first_leg_destination].append(shipment)

    for first_leg, ships in sorted(shipments_by_first_leg.items()):
        print(f"  {first_leg}: {len(ships)} shipments, {sum(s.quantity for s in ships):,.0f} units")
    print()

    # Check shipments to problematic destinations
    print("Detailed analysis of problematic destinations:")
    print()

    for dest in problematic_dests:
        dest_shipments = [s for s in shipments if s.destination_id == dest]
        if dest_shipments:
            print(f"Destination {dest}: {len(dest_shipments)} shipments")
            for s in dest_shipments[:3]:  # Show first 3
                print(f"  {s.id}: {s.quantity:.0f} units")
                print(f"    Production date: {s.production_date}")
                print(f"    Delivery date: {s.delivery_date}")
                print(f"    Route path: {' → '.join(s.route.path)}")
                print(f"    first_leg_destination: {s.first_leg_destination}")
                print(f"    Route legs count: {len(s.route.route_legs)}")
                if s.route.route_legs:
                    print(f"    First route leg: {s.route.route_legs[0].from_location_id} → {s.route.route_legs[0].to_location_id}")
            if len(dest_shipments) > 3:
                print(f"  ... and {len(dest_shipments) - 3} more")
            print()

    # Try truck loading
    print("🚛 Testing truck loading...")
    print()

    loader = TruckLoader(truck_schedules)

    # Determine date range from shipments
    if shipments:
        start_date = min(s.production_date for s in shipments)
        end_date = max(s.production_date for s in shipments) + timedelta(days=7)

        print(f"Loading shipments from {start_date} to {end_date}")
        print()

        plan = loader.assign_shipments_to_trucks(shipments, start_date, end_date)

        print(f"✓ Assigned: {plan.total_shipments - len(plan.unassigned_shipments)} shipments")
        print(f"✓ Trucks used: {plan.total_trucks_used}")
        print(f"✓ Average utilization: {plan.average_utilization:.1%}")

        if plan.unassigned_shipments:
            print(f"❌ Unassigned: {len(plan.unassigned_shipments)} shipments")
            print()
            print("Unassigned shipments by destination:")
            unassigned_by_dest = defaultdict(list)
            for s in plan.unassigned_shipments:
                unassigned_by_dest[s.destination_id].append(s)

            for dest, ships in sorted(unassigned_by_dest.items()):
                print(f"  {dest}: {len(ships)} shipments, {sum(s.quantity for s in ships):,.0f} units")
                # Show first_leg for these
                first_legs = set(s.first_leg_destination for s in ships)
                print(f"    first_leg_destination(s): {', '.join(sorted(first_legs))}")
            print()

            # Detailed analysis of why not assigned
            print("Detailed analysis of first unassigned shipment:")
            s = plan.unassigned_shipments[0]
            print(f"  Shipment: {s.id}")
            print(f"  Destination: {s.destination_id}")
            print(f"  Quantity: {s.quantity:.0f} units")
            print(f"  Production date: {s.production_date}")
            print(f"  first_leg_destination: {s.first_leg_destination}")
            print()

            # Check if trucks exist for this first_leg
            matching_trucks = truck_dest_map.get(s.first_leg_destination, [])
            if matching_trucks:
                print(f"  ✓ Found {len(matching_trucks)} truck(s) to {s.first_leg_destination}:")
                for t in matching_trucks:
                    day_info = f" on {t.day_of_week}" if t.day_of_week else " daily"
                    print(f"    - {t.truck_name}: {t.departure_type}{day_info}")
                print()

                # Check D-1/D0 timing for each truck
                print("  Timing check (D-1/D0):")
                # Try a few dates
                test_dates = [s.production_date + timedelta(days=i) for i in range(1, 5)]
                for test_date in test_dates:
                    is_d1 = s.is_d1_production(test_date)
                    is_d0 = s.is_d0_production(test_date)
                    print(f"    Truck departure {test_date}: D-1={is_d1}, D0={is_d0}")

                    # Check trucks for this date
                    trucks_on_date = loader.get_trucks_for_date(test_date)
                    matching = [t for t in trucks_on_date if t.destination_id == s.first_leg_destination]
                    if matching:
                        print(f"      {len(matching)} matching truck(s) on this date")
                        for t in matching:
                            can_load_morning = is_d1  # Morning trucks need D-1
                            can_load_afternoon = is_d1 or is_d0  # Afternoon can take D-1 or D0
                            can_load = can_load_morning if t.departure_type == "morning" else can_load_afternoon
                            print(f"        {t.truck_name} ({t.departure_type}): can_load={can_load}")
            else:
                print(f"  ❌ NO TRUCKS to {s.first_leg_destination}")
                print(f"  Available truck destinations: {sorted(truck_dest_map.keys())}")
        else:
            print("✅ All shipments assigned successfully!")
        print()

    print("=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
