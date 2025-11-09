"""Debug script to extract actual Pyomo variable values and check constraints.

This will help us understand WHY labor hours appear without production.
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


def debug_labor_constraints():
    """Debug why labor hours appear without production."""

    print("=" * 80)
    print("DEBUGGING LABOR CONSTRAINTS")
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

    print(f"\nBuilding model ({start_date} to {end_date})...")

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

    # Solve (this also builds the model internally)
    print("\nSolving...")
    result = model_builder.solve(
        solver_name='appsi_highs',
        time_limit_seconds=600,
        mip_gap=0.01,
        tee=True
    )
    print(f"✅ Solved: {result.termination_condition}")

    # Get the built model for variable extraction
    pyomo_model = model_builder.model

    # Now extract actual values for a weekend day
    print("\n" + "=" * 80)
    print("CHECKING CONSTRAINT VALUES FOR WEEKEND DAYS")
    print("=" * 80)

    node_id = manufacturing_site.id

    # Find weekend dates in horizon
    weekend_dates = [d for d in pyomo_model.dates
                     if labor_calendar.get_labor_day(d) and not labor_calendar.get_labor_day(d).is_fixed_day]

    print(f"\nWeekend/holiday dates in horizon: {len(weekend_dates)}")

    for t in sorted(weekend_dates)[:3]:  # Check first 3 weekends
        print(f"\n{t} ({t.strftime('%A')}):")

        # Extract values
        if (node_id, t) in pyomo_model.labor_hours_used:
            labor_used = value(pyomo_model.labor_hours_used[node_id, t])
            print(f"  labor_hours_used: {labor_used:.4f}")
        else:
            labor_used = 0
            print(f"  labor_hours_used: N/A")

        if (node_id, t) in pyomo_model.labor_hours_paid:
            labor_paid = value(pyomo_model.labor_hours_paid[node_id, t])
            print(f"  labor_hours_paid: {labor_paid:.4f}")
        else:
            labor_paid = 0
            print(f"  labor_hours_paid: N/A")

        if (node_id, t) in pyomo_model.any_production:
            any_prod = value(pyomo_model.any_production[node_id, t])
            print(f"  any_production: {any_prod:.4f}")
        else:
            any_prod = None
            print(f"  any_production: N/A")

        if (node_id, t) in pyomo_model.total_starts:
            total_starts = value(pyomo_model.total_starts[node_id, t])
            print(f"  total_starts: {total_starts:.4f}")
        else:
            total_starts = None
            print(f"  total_starts: N/A")

        # Check individual product binaries
        print(f"  Product binaries:")
        for prod in list(pyomo_model.products)[:2]:  # Check first 2 products
            if (node_id, prod, t) in pyomo_model.product_produced:
                prod_binary = value(pyomo_model.product_produced[node_id, prod, t])
                print(f"    product_produced[{prod[:20]}]: {prod_binary:.4f}")

            if (node_id, prod, t) in pyomo_model.production:
                prod_qty = value(pyomo_model.production[node_id, prod, t])
                print(f"    production[{prod[:20]}]: {prod_qty:.1f} units")

        # Check constraint satisfaction
        print(f"  Constraint checks:")

        # Check: any_production <= sum(product_produced)
        sum_prod_produced = sum(
            value(pyomo_model.product_produced[node_id, prod, t])
            for prod in pyomo_model.products
            if (node_id, prod, t) in pyomo_model.product_produced
        )
        print(f"    sum(product_produced): {sum_prod_produced:.4f}")
        if any_prod is not None:
            print(f"    any_production <= sum: {any_prod:.4f} <= {sum_prod_produced:.4f} ? {any_prod <= sum_prod_produced + 0.001}")

        # Check: paid >= 4 * any_production
        if any_prod is not None and labor_paid > 0:
            min_payment = 4.0 * any_prod
            print(f"    paid >= 4*any_production: {labor_paid:.4f} >= {min_payment:.4f} ? {labor_paid >= min_payment - 0.001}")

        # Check: labor_used = production_time + overhead
        total_production = sum(
            value(pyomo_model.production[node_id, prod, t])
            for prod in pyomo_model.products
            if (node_id, prod, t) in pyomo_model.production
        )
        prod_time = total_production / 1400.0

        if any_prod and total_starts is not None:
            overhead = (0.5 + 0.25) * any_prod + 0.5 * (total_starts - any_prod)
            expected_labor = prod_time + overhead
            print(f"    Expected labor_used: {prod_time:.4f} + {overhead:.4f} = {expected_labor:.4f}")
            print(f"    Actual labor_used: {labor_used:.4f}")
            print(f"    Match? {abs(labor_used - expected_labor) < 0.01}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    debug_labor_constraints()
