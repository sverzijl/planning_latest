"""
Diagnostic: Verify Conservation Hypothesis

Tests if conservation of flow holds when accounting for end-of-horizon in-transit goods.

Hypothesis: Test conservation violation is due to missing end_in_transit in calculation.
Expected: init_inv + production = consumed + end_inv + end_in_transit
"""

from datetime import datetime, timedelta
from pyomo.core.base import value

from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType


def diagnose_conservation():
    """Run 4-week solve and check conservation with in-transit accounting."""

    print("="*80)
    print("CONSERVATION DIAGNOSTIC - WITH IN-TRANSIT ACCOUNTING")
    print("="*80)

    # Load data
    print("\n1. Loading data...")
    coordinator = DataCoordinator(
        forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
        network_file='data/examples/Network_Config.xlsx',
        inventory_file='data/examples/inventory_latest.XLSX'
    )
    validated = coordinator.load_and_validate()

    # Build forecast
    forecast_entries = [
        ForecastEntry(
            location_id=entry.node_id,
            product_id=entry.product_id,
            forecast_date=entry.demand_date,
            quantity=entry.quantity
        )
        for entry in validated.demand_entries
    ]
    forecast = Forecast(name="Test Forecast", entries=forecast_entries)

    # Load network
    parser = MultiFileParser(
        forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
        network_file='data/examples/Network_Config.xlsx',
        inventory_file='data/examples/inventory_latest.XLSX'
    )
    _, locations, routes_legacy, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manufacturing_site = manufacturing_locations[0]

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes_legacy)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    products_dict = {p.id: p for p in validated.products}

    # Set 4-week horizon
    horizon_days = 28
    start = validated.planning_start_date
    end = (datetime.combine(start, datetime.min.time()) + timedelta(days=horizon_days-1)).date()

    print(f"   Planning horizon: {start} to {end} ({horizon_days} days)")

    # Build model
    print("\n2. Building model...")
    model_builder = SlidingWindowModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        products=products_dict,
        start_date=start,
        end_date=end,
        truck_schedules=unified_truck_schedules,
        initial_inventory=validated.get_inventory_dict(),
        inventory_snapshot_date=validated.inventory_snapshot_date,
        allow_shortages=True,
        use_pallet_tracking=True,
        use_truck_pallet_tracking=True
    )

    # Solve
    print("\n3. Solving model...")
    result = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01)

    if not result.success:
        print(f"\n❌ Solve failed: {result.termination_condition}")
        return

    print(f"   ✓ Solve succeeded: {result.termination_condition}")
    print(f"   Objective: ${result.objective_value:,.0f}")
    if hasattr(result, 'solve_time_seconds'):
        print(f"   Solve time: {result.solve_time_seconds:.1f}s")
    elif hasattr(result, 'time'):
        print(f"   Solve time: {result.time:.1f}s")

    model = model_builder.model
    solution = model_builder.extract_solution(model)

    # Get demand and init_inv for this horizon
    if hasattr(model_builder, 'demand_original'):
        total_demand = sum(model_builder.demand_original.values())
    else:
        total_demand = sum(model_builder.demand.values())

    if hasattr(model_builder, 'initial_inventory_original'):
        total_init_inv = sum(model_builder.initial_inventory_original.values())
    else:
        total_init_inv = sum(model_builder.initial_inventory.values())

    print(f"\n4. Extracting solution data...")
    print(f"   Total demand: {total_demand:,.0f} units")
    print(f"   Initial inventory: {total_init_inv:,.0f} units")

    # Extract from solution
    total_production = solution.total_production

    # CRITICAL: Check how consumption is extracted
    print(f"   Solution has demand_consumed: {hasattr(solution, 'demand_consumed')}")
    if hasattr(solution, 'demand_consumed'):
        print(f"   demand_consumed entries: {len(solution.demand_consumed)}")
        print(f"   Sample entries: {list(solution.demand_consumed.items())[:3]}")

    total_consumed = sum(solution.demand_consumed.values()) if hasattr(solution, 'demand_consumed') else 0
    total_shortage = solution.total_shortage_units

    # VERIFY: Extract consumption directly from Pyomo model
    print(f"\n   Verifying consumption from Pyomo model...")
    consumed_from_pyomo = 0
    if hasattr(model, 'demand_consumed_from_ambient') and hasattr(model, 'demand_consumed_from_thawed'):
        for key in model.demand_consumed_from_ambient:
            try:
                ambient = value(model.demand_consumed_from_ambient[key])
                thawed = value(model.demand_consumed_from_thawed[key]) if key in model.demand_consumed_from_thawed else 0
                consumed_from_pyomo += (ambient + thawed)
            except:
                pass
        print(f"   Consumed (from Pyomo): {consumed_from_pyomo:,.0f} units")
        print(f"   Consumed (from solution): {total_consumed:,.0f} units")
        print(f"   Difference: {abs(consumed_from_pyomo - total_consumed):,.0f} units")

    # Extract end inventory from Pyomo model
    print("\n5. Extracting end inventory from Pyomo model...")
    last_date = max(model.dates)
    end_inventory = 0

    if hasattr(model, 'inventory'):
        for (node_id, prod, state, t) in model.inventory:
            if t == last_date:
                try:
                    qty = value(model.inventory[node_id, prod, state, t])
                    if qty and qty > 0.01:
                        end_inventory += qty
                except:
                    pass

    print(f"   End inventory: {end_inventory:,.0f} units")

    # CRITICAL: Extract end in-transit from Pyomo model
    print("\n6. Extracting end in-transit from Pyomo model...")
    end_in_transit = 0
    post_horizon_departures = 0
    within_horizon_arrivals = 0

    if hasattr(model, 'in_transit'):
        for (origin, dest, prod, departure_date, state) in model.in_transit:
            try:
                var = model.in_transit[origin, dest, prod, departure_date, state]
                qty = value(var)

                if qty and qty > 0.01:
                    # Find route to get transit days
                    route = next((r for r in model_builder.routes
                                 if r.origin_node_id == origin and r.destination_node_id == dest), None)

                    if route:
                        delivery_date = departure_date + timedelta(days=route.transit_days)

                        if delivery_date > last_date:
                            # This shipment delivers AFTER horizon ends
                            end_in_transit += qty
                            post_horizon_departures += 1
                        else:
                            # This shipment delivers WITHIN horizon
                            within_horizon_arrivals += 1
            except:
                pass

    print(f"   End in-transit: {end_in_transit:,.0f} units")
    print(f"   Post-horizon deliveries: {post_horizon_departures} shipments")
    print(f"   Within-horizon deliveries: {within_horizon_arrivals} shipments")

    # Calculate conservation
    print("\n" + "="*80)
    print("CONSERVATION CHECK")
    print("="*80)

    total_supply = total_init_inv + total_production
    total_usage = total_consumed + end_inventory + end_in_transit
    balance = total_supply - total_usage
    balance_pct = (balance / total_supply * 100) if total_supply > 0 else 0

    print(f"\nSUPPLY SIDE:")
    print(f"  Initial inventory:    {total_init_inv:>12,.0f} units")
    print(f"  Production:           {total_production:>12,.0f} units")
    print(f"  ─────────────────────────────────────")
    print(f"  TOTAL SUPPLY:         {total_supply:>12,.0f} units")

    print(f"\nUSAGE SIDE:")
    print(f"  Consumed (demand):    {total_consumed:>12,.0f} units")
    print(f"  End inventory:        {end_inventory:>12,.0f} units")
    print(f"  End in-transit:       {end_in_transit:>12,.0f} units")
    print(f"  ─────────────────────────────────────")
    print(f"  TOTAL USAGE:          {total_usage:>12,.0f} units")

    print(f"\nBALANCE:")
    print(f"  Supply - Usage:       {balance:>12,.0f} units ({balance_pct:+.2f}%)")

    # Verdict
    print("\n" + "="*80)
    if abs(balance) / total_supply < 0.05:  # 5% tolerance
        print("✅ CONSERVATION HOLDS (within 5% tolerance)")
        print("   → Hypothesis CONFIRMED: Test was missing end_in_transit!")
    else:
        print("❌ CONSERVATION VIOLATED (>5% error)")
        print("   → Hypothesis REJECTED: Still have conservation issue")
    print("="*80)

    # VERIFY MATERIAL BALANCE FOR ONE NODE
    print(f"\n" + "="*80)
    print("VERIFY MATERIAL BALANCE FOR ONE NODE (6104, first product, day 2)")
    print("="*80)

    if hasattr(model, 'inventory') and hasattr(model, 'production'):
        # Pick a demand node and check its balance
        check_node = '6104'
        check_prod = list(model.products)[0]
        date_list = list(model.dates)
        check_date = date_list[1] if len(date_list) > 1 else date_list[0]  # Day 2
        prev_date = date_list[0]

        print(f"\nNode: {check_node}, Product: {check_prod[:30]}, Date: {check_date}")

        # Get inventory values
        try:
            inv_current = value(model.inventory[check_node, check_prod, 'ambient', check_date])
            inv_prev = value(model.inventory[check_node, check_prod, 'ambient', prev_date])

            # Get flows
            arrivals = 0
            for route in model_builder.routes:
                if route.destination_node_id == check_node:
                    dep_date = check_date - timedelta(days=route.transit_days)
                    if dep_date in model.dates:
                        key = (route.origin_node_id, check_node, check_prod, dep_date, 'ambient')
                        if key in model.in_transit:
                            try:
                                arrivals += value(model.in_transit[key])
                            except:
                                pass

            departures = 0
            for route in model_builder.routes:
                if route.origin_node_id == check_node:
                    key = (check_node, route.destination_node_id, check_prod, check_date, 'ambient')
                    if key in model.in_transit:
                        try:
                            departures += value(model.in_transit[key])
                        except:
                            pass

            consumed = 0
            if (check_node, check_prod, check_date) in model.demand_consumed_from_ambient:
                consumed = value(model.demand_consumed_from_ambient[check_node, check_prod, check_date])

            # Check balance
            lhs = inv_current
            rhs = inv_prev + arrivals - departures - consumed

            print(f"  Inventory[t]   = {lhs:>10.2f}")
            print(f"  Inventory[t-1] = {inv_prev:>10.2f}")
            print(f"  Arrivals       = {arrivals:>10.2f}")
            print(f"  Departures     = {departures:>10.2f}")
            print(f"  Consumed       = {consumed:>10.2f}")
            print(f"  RHS            = {rhs:>10.2f}")
            print(f"  LHS - RHS      = {lhs - rhs:>10.2f}")

            if abs(lhs - rhs) < 0.01:
                print(f"  ✓ Material balance HOLDS for this node!")
            else:
                print(f"  ✗ Material balance VIOLATED for this node!")
        except Exception as e:
            print(f"  Error checking balance: {e}")

    # Additional checks
    print(f"\n" + "="*80)
    print("ADDITIONAL CHECKS:")
    print("="*80)
    print(f"  Fill rate: {solution.fill_rate:.1%}")
    print(f"  Shortage: {total_shortage:,.0f} units")
    print(f"  Demand equation: consumed + shortage = {total_consumed + total_shortage:,.0f} vs demand = {total_demand:,.0f}")

    demand_eq_check = abs((total_consumed + total_shortage) - total_demand)
    if demand_eq_check < 100:
        print(f"  ✓ Demand equation holds (error: {demand_eq_check:.0f} units)")
    else:
        print(f"  ✗ Demand equation violated (error: {demand_eq_check:.0f} units)")

    # OLD TEST LOGIC (for comparison)
    print(f"\n" + "="*80)
    print("OLD TEST LOGIC (without in-transit):")
    print("="*80)
    old_test_passed = total_consumed <= total_supply * 1.01
    print(f"  Check: consumed <= supply * 1.01")
    print(f"  {total_consumed:,.0f} <= {total_supply * 1.01:,.0f}?")
    if old_test_passed:
        print(f"  ✓ OLD TEST PASSES")
    else:
        phantom = total_consumed - total_supply
        print(f"  ✗ OLD TEST FAILS")
        print(f"  Phantom supply: {phantom:,.0f} units (but this is end_in_transit!)")


if __name__ == "__main__":
    diagnose_conservation()
