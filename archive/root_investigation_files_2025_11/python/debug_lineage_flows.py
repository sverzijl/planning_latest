"""Debug script to extract Lineage shipment values and inventory flows.

This will help us understand WHY Lineage inventory stays at 6400 (initial) throughout.
"""

from pathlib import Path
from datetime import date, timedelta
from pyomo.environ import value

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from tests.conftest import create_test_products


def debug_lineage_flows():
    """Debug why Lineage inventory doesn't update."""

    print("=" * 80)
    print("DEBUGGING LINEAGE FLOWS")
    print("=" * 80)

    # Parse data
    data_dir = Path("data/examples")
    parser = MultiFileParser(
        forecast_file=data_dir / "Gluten Free Forecast - Latest.xlsm",
        network_file=data_dir / "Network_Config.xlsx",
        inventory_file=data_dir / "inventory_latest.XLSX"
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Setup
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

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    inventory_snapshot = parser.parse_inventory(snapshot_date=None)

    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    start_date = inventory_snapshot.snapshot_date
    end_date = start_date + timedelta(weeks=4)

    print(f"\nBuilding and solving model ({start_date} to {end_date})...")

    model_builder = SlidingWindowModel(
        nodes=nodes,
        routes=unified_routes,
        products=products,
        forecast=forecast,
        initial_inventory=inventory_snapshot.to_optimization_dict(),
        labor_calendar=labor_calendar,
        truck_schedules=unified_truck_schedules,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        inventory_snapshot_date=inventory_snapshot.snapshot_date,
        allow_shortages=True,
        use_pallet_tracking=True,
        use_truck_pallet_tracking=True
    )

    # Solve
    result = model_builder.solve(
        solver_name='appsi_highs',
        time_limit_seconds=600,
        mip_gap=0.01,
        tee=False  # Don't show solver output
    )
    print(f"✅ Solved: {result.termination_condition}")

    # Get the model
    pyomo_model = model_builder.model

    # Extract Lineage-related values
    print("\n" + "=" * 80)
    print("LINEAGE SHIPMENT AND INVENTORY ANALYSIS")
    print("=" * 80)

    # Find all Wednesdays (Lineage route days)
    wednesdays = [d for d in pyomo_model.dates if d.weekday() == 2]  # 2 = Wednesday
    print(f"\nWednesdays in horizon: {[d.strftime('%Y-%m-%d') for d in wednesdays[:4]]}")

    # Check shipments TO Lineage (6122 → Lineage)
    print("\n" + "=" * 80)
    print("SHIPMENTS TO LINEAGE (6122 → Lineage)")
    print("=" * 80)

    for prod in list(pyomo_model.products)[:2]:  # Check first 2 products
        print(f"\nProduct: {prod}")
        for wed in wednesdays:
            key = ('6122', 'Lineage', prod, wed, 'ambient')
            if key in pyomo_model.in_transit:
                shipment_value = value(pyomo_model.in_transit[key])
                print(f"  {wed.strftime('%Y-%m-%d')} (Wed): {shipment_value:.1f} units")
            else:
                print(f"  {wed.strftime('%Y-%m-%d')} (Wed): variable NOT in model")

    # Check Lineage frozen inventory over time
    print("\n" + "=" * 80)
    print("LINEAGE FROZEN INVENTORY OVER TIME")
    print("=" * 80)

    for prod in list(pyomo_model.products)[:2]:  # Check first 2 products
        print(f"\nProduct: {prod}")
        for t in sorted(list(pyomo_model.dates))[:10]:  # First 10 days
            key = ('Lineage', prod, 'frozen', t)
            if key in pyomo_model.inventory:
                inv_value = value(pyomo_model.inventory[key])
                print(f"  {t.strftime('%Y-%m-%d')}: {inv_value:.1f} units")
            else:
                print(f"  {t.strftime('%Y-%m-%d')}: variable NOT in model")

    # Check shipments FROM Lineage (Lineage → 6130)
    print("\n" + "=" * 80)
    print("SHIPMENTS FROM LINEAGE (Lineage → 6130)")
    print("=" * 80)

    for prod in list(pyomo_model.products)[:2]:  # Check first 2 products
        print(f"\nProduct: {prod}")
        for t in sorted(list(pyomo_model.dates))[:10]:  # First 10 days
            key = ('Lineage', '6130', prod, t, 'frozen')
            if key in pyomo_model.in_transit:
                shipment_value = value(pyomo_model.in_transit[key])
                if shipment_value > 0.1:  # Only show non-zero
                    print(f"  {t.strftime('%Y-%m-%d')}: {shipment_value:.1f} units")
            else:
                pass  # Don't spam with "not in model"

    # Check 6130 inventory (should receive from Lineage)
    print("\n" + "=" * 80)
    print("6130 INVENTORY (Should receive from Lineage)")
    print("=" * 80)

    for prod in list(pyomo_model.products)[:2]:  # Check first 2 products
        print(f"\nProduct: {prod}")
        for state in ['frozen', 'thawed']:
            print(f"  State: {state}")
            for t in sorted(list(pyomo_model.dates))[:10]:  # First 10 days
                key = ('6130', prod, state, t)
                if key in pyomo_model.inventory:
                    inv_value = value(pyomo_model.inventory[key])
                    if inv_value > 0.1:  # Only show non-zero
                        print(f"    {t.strftime('%Y-%m-%d')}: {inv_value:.1f} units")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    debug_lineage_flows()
