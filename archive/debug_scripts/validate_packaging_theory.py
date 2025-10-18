"""
Validate the theory that packaging/truck capacity constraints force excess production.

Theory: Discrete packaging units (10-unit cases, 320-unit pallets, 14,080-unit trucks)
force shipments to be rounded up, creating unavoidable excess that accumulates as end inventory.

Tests:
1. Check if truck loads are constrained to multiples of pallet size (320 units)
2. Check if total demand is NOT a multiple of pallet size
3. Calculate theoretical minimum excess from rounding
4. Compare to actual end inventory
"""

from pathlib import Path
from datetime import date
from collections import defaultdict

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.location import LocationType
from src.models.manufacturing import ManufacturingSite
from src.models.truck_schedule import TruckScheduleCollection


def main():
    print("="*80)
    print("PACKAGING CONSTRAINT THEORY VALIDATION")
    print("="*80)

    # Load data
    data_dir = Path("data/examples")
    parser = MultiFileParser(
        forecast_file=data_dir / "Gfree Forecast.xlsm",
        network_file=data_dir / "Network_Config.xlsx",
        inventory_file=data_dir / "inventory.XLSX",
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
        default_changeover_hours=0.5, production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)
    inventory_snapshot = parser.parse_inventory(snapshot_date=None)

    model = IntegratedProductionDistributionModel(
        forecast=forecast, labor_calendar=labor_calendar, manufacturing_site=manufacturing_site,
        cost_structure=cost_structure, locations=locations, routes=routes,
        truck_schedules=truck_schedules, max_routes_per_destination=5,
        allow_shortages=True, enforce_shelf_life=True,
        initial_inventory=inventory_snapshot.to_optimization_dict(),
        inventory_snapshot_date=inventory_snapshot.snapshot_date,
        start_date=inventory_snapshot.snapshot_date, end_date=date(2025, 11, 3),
        use_batch_tracking=True,
    )

    result = model.solve(solver_name='cbc', time_limit_seconds=120, mip_gap=0.01,
                        use_aggressive_heuristics=True, tee=False)

    if not (result.is_optimal() or result.is_feasible()):
        print("Solution not feasible")
        return

    solution = model.get_solution()

    # Get shipments
    shipments = model.get_shipment_plan() or []

    print(f"\n{'='*80}")
    print("TEST 1: Are shipments in discrete pallet multiples?")
    print(f"{'='*80}")

    PALLET_SIZE = 320  # units per pallet
    CASE_SIZE = 10     # units per case

    shipment_remainders = []
    for s in shipments:
        remainder_pallet = s.quantity % PALLET_SIZE
        remainder_case = s.quantity % CASE_SIZE

        if remainder_pallet != 0:
            shipment_remainders.append({
                'shipment': s,
                'quantity': s.quantity,
                'remainder_pallet': remainder_pallet,
                'remainder_case': remainder_case
            })

    if shipment_remainders:
        print(f"\nFound {len(shipment_remainders)} shipments NOT in pallet multiples:")
        for i, sr in enumerate(shipment_remainders[:10]):  # Show first 10
            print(f"  {sr['shipment'].origin_id} → {sr['shipment'].destination_id}: "
                  f"{sr['quantity']:,.0f} units ({sr['quantity']//PALLET_SIZE} pallets + {sr['remainder_pallet']} units)")

        print(f"\n✓ THEORY REJECTED: Shipments are NOT constrained to pallet multiples")
        print(f"  Model allows fractional pallets (partial loads)")
    else:
        print(f"\n⚠️ ALL {len(shipments)} shipments are exact pallet multiples")
        print(f"  This suggests pallet constraints MAY be forcing rounding")

    # Check production
    print(f"\n{'='*80}")
    print("TEST 2: Is production in discrete case multiples?")
    print(f"{'='*80}")

    production_by_date_product = solution.get('production_by_date_product', {})

    non_case_multiple = []
    for (d, p), qty in production_by_date_product.items():
        if qty % CASE_SIZE != 0:
            non_case_multiple.append((d, p, qty))

    if non_case_multiple:
        print(f"\nFound {len(non_case_multiple)} production batches NOT in case multiples")
        print(f"✓ THEORY REJECTED: Production is NOT constrained to case multiples")
    else:
        print(f"\n⚠️ ALL production is in exact case multiples (10-unit increments)")
        print(f"  This suggests case constraints ARE forcing rounding")

    # Calculate demand vs pallet rounding
    print(f"\n{'='*80}")
    print("TEST 3: Theoretical rounding excess")
    print(f"{'='*80}")

    total_demand = sum(model.demand.values())
    total_production = sum(production_by_date_product.values())

    # If all shipments must be pallet multiples, calculate minimum excess
    demand_pallets = total_demand / PALLET_SIZE
    demand_pallets_ceil = int(demand_pallets) + (1 if demand_pallets % 1 > 0 else 0)
    minimum_shipment_for_pallets = demand_pallets_ceil * PALLET_SIZE
    theoretical_pallet_excess = minimum_shipment_for_pallets - total_demand

    print(f"\nTotal demand: {total_demand:,.0f} units")
    print(f"  = {demand_pallets:.2f} pallets")
    print(f"  = {demand_pallets_ceil} pallets (rounded up)")
    print(f"  = {minimum_shipment_for_pallets:,.0f} units minimum")
    print(f"\nTheoretical pallet rounding excess: {theoretical_pallet_excess:,.0f} units")

    # Actual excess
    cohort_inv = solution.get('cohort_inventory', {})
    end_inv = sum(
        qty for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items()
        if curr_date == model.end_date and qty > 0.01
    )

    print(f"Actual end inventory: {end_inv:,.0f} units")
    print(f"Actual overproduction: {total_production - total_demand:,.0f} units")

    if abs(end_inv - theoretical_pallet_excess) < 1000:
        print(f"\n✓ THEORY CONFIRMED: End inventory matches pallet rounding excess!")
        print(f"  Difference: {abs(end_inv - theoretical_pallet_excess):,.0f} units")
    else:
        print(f"\n✗ THEORY REJECTED: End inventory does NOT match pallet rounding")
        print(f"  Difference: {abs(end_inv - theoretical_pallet_excess):,.0f} units (too large)")

    # Check truck utilization
    print(f"\n{'='*80}")
    print("TEST 4: Truck utilization analysis")
    print(f"{'='*80}")

    TRUCK_CAPACITY = 14080  # units per truck

    # Analyze shipments by truck/date
    shipments_from_manufacturing = [s for s in shipments if s.origin_id == 6122]

    if shipments_from_manufacturing:
        total_shipped_from_mfg = sum(s.quantity for s in shipments_from_manufacturing)
        theoretical_trucks_needed = total_shipped_from_mfg / TRUCK_CAPACITY

        print(f"\nShipments from manufacturing: {len(shipments_from_manufacturing)}")
        print(f"Total shipped: {total_shipped_from_mfg:,.0f} units")
        print(f"Theoretical trucks needed: {theoretical_trucks_needed:.2f} trucks")
        print(f"Truck capacity utilized: {100 * (total_shipped_from_mfg % TRUCK_CAPACITY) / TRUCK_CAPACITY:.1f}% on last truck")

        # Check if any truck is underutilized but could carry more
        shipments_by_date_dest = defaultdict(list)
        for s in shipments_from_manufacturing:
            key = (s.ship_date, s.destination_id)
            shipments_by_date_dest[key].append(s)

        underutilized_trucks = []
        for (ship_date, dest), shipment_list in shipments_by_date_dest.items():
            total_load = sum(s.quantity for s in shipment_list)
            utilization = total_load / TRUCK_CAPACITY

            if utilization < 0.9 and total_load > 0:  # Less than 90% utilized
                underutilized_trucks.append((ship_date, dest, total_load, utilization))

        if underutilized_trucks:
            print(f"\nFound {len(underutilized_trucks)} underutilized trucks (<90% capacity):")
            for ship_date, dest, load, util in underutilized_trucks[:5]:
                print(f"  {ship_date} → {dest}: {load:,.0f} units ({util*100:.1f}% utilized)")

            print(f"\n✓ Trucks are NOT forced to be full - partial loads allowed")
        else:
            print(f"\nAll trucks are >90% utilized")

    # Final diagnosis
    print(f"\n{'='*80}")
    print("DIAGNOSIS")
    print(f"{'='*80}")

    # Check if production IS constrained but shipments are NOT
    if len(non_case_multiple) == 0 and len(shipment_remainders) > 0:
        print(f"\n✓ CONFIRMED: Production IS constrained to case multiples (10 units)")
        print(f"✓ CONFIRMED: Shipments are NOT constrained to pallet multiples")
        print(f"\nConclusion: Production rounding to 10-unit cases creates small excess")
        print(f"This excess accumulates over many production runs → end inventory")

        # Calculate cumulative rounding error
        production_days = len([qty for qty in production_by_date_product.values() if qty > 0])
        avg_rounding_per_day = 5  # Average rounding per day (0-9 units per case)
        cumulative_rounding = production_days * avg_rounding_per_day

        print(f"\nTheoretical case rounding excess:")
        print(f"  Production days: {production_days}")
        print(f"  Avg rounding/day: ~5 units")
        print(f"  Cumulative: ~{cumulative_rounding} units")

        if abs(end_inv - cumulative_rounding) < 5000:
            print(f"\n✓ MATCHES end inventory magnitude!")
        else:
            print(f"\n✗ Does NOT match end inventory ({end_inv:,.0f} units)")
            print(f"  The issue is NOT just case rounding - something else is happening")
    elif len(non_case_multiple) > 0:
        print(f"\n✗ Production is NOT constrained to case multiples")
        print(f"  Packaging theory does not explain end inventory")
        print(f"\n  The 27k end inventory must have a different root cause.")
        print(f"  Possible issues:")
        print(f"  1. Demand satisfaction bug (inventory not matched to demand)")
        print(f"  2. Network routing bug (inventory at wrong locations)")
        print(f"  3. Temporal mismatch (inventory arrives after demand window)")
        print(f"  4. Objective function weighting issue")
    else:
        print(f"\nBoth production AND shipments are in discrete multiples")
        print(f"This suggests packaging constraints ARE active")
        print(f"But the 27k excess is too large to be explained by rounding alone")


if __name__ == "__main__":
    main()
