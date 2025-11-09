"""Find which constraints are infeasible and write to file.

RUN THIS ON YOUR WINDOWS MACHINE when you get infeasibility.
It will create infeasibility_report.txt showing exactly which constraints fail.
"""
from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
import sys

# Redirect output to file
output_file = open('infeasibility_report.txt', 'w')
original_stdout = sys.stdout
sys.stdout = output_file

try:
    print("=" * 80)
    print("INFEASIBILITY ANALYSIS")
    print("=" * 80)

    # Parse
    parser = MultiFileParser(
        forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
        network_file='data/examples/Network_Config.xlsx'
    )
    forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

    inv_parser = InventoryParser('data/examples/inventory_latest.XLSX')
    inventory_snapshot = inv_parser.parse()

    # Convert
    mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
    converter = LegacyToUnifiedConverter()
    nodes, unified_routes, unified_trucks = converter.convert_all(
        manufacturing_site=mfg_site, locations=locations, routes=routes,
        truck_schedules=truck_schedules, forecast=forecast
    )

    # Use snapshot date + 1 (with fix)
    start_date = inventory_snapshot.snapshot_date + timedelta(days=1)
    end_date = start_date + timedelta(days=27)

    print(f"\nConfiguration:")
    print(f"  Inventory snapshot: {inventory_snapshot.snapshot_date}")
    print(f"  Planning start: {start_date}")
    print(f"  Planning end: {end_date}")

    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    # Convert inventory
    initial_inv_dict = {}
    if hasattr(inventory_snapshot, 'to_optimization_dict'):
        initial_inv_dict = inventory_snapshot.to_optimization_dict()
    else:
        for entry in inventory_snapshot.entries:
            key = (entry.location_id, entry.product_id, 'ambient')
            initial_inv_dict[key] = initial_inv_dict.get(key, 0) + entry.quantity

    print(f"  Initial inventory: {len(initial_inv_dict)} entries")
    print(f"  Total units: {sum(initial_inv_dict.values()):,.0f}")

    # Build model
    model = SlidingWindowModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_params,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_trucks,
        initial_inventory=initial_inv_dict,
        inventory_snapshot_date=inventory_snapshot.snapshot_date,
        allow_shortages=True,
        use_pallet_tracking=True,
        use_truck_pallet_tracking=True
    )

    pyomo_model = model.build_model()

    # Solve
    from pyomo.contrib.appsi.solvers import Highs
    solver = Highs()
    solver.config.load_solution = False
    solver.config.time_limit = 120
    solver.config.mip_gap = 0.01

    print(f"\nSolving...")
    results = solver.solve(pyomo_model)

    print(f"\n" + "=" * 80)
    print("SOLVE RESULT")
    print("=" * 80)
    print(f"Termination: {results.termination_condition}")

    from pyomo.contrib.appsi.base import TerminationCondition as AppsiTC

    if results.termination_condition == AppsiTC.infeasible:
        print(f"\nINFEASIBLE - Analyzing constraints...")

        # Use Pyomo's infeasibility analysis
        print(f"\n" + "=" * 80)
        print("INFEASIBLE CONSTRAINTS")
        print("=" * 80)

        from pyomo.util.infeasible import log_infeasible_constraints
        log_infeasible_constraints(pyomo_model, log_expression=True, log_variables=True)

        print(f"\n" + "=" * 80)
        print("CHECKING SPECIFIC CONSTRAINT TYPES")
        print("=" * 80)

        # Check if it's shelf life
        print(f"\nShelf life constraints:")
        if hasattr(pyomo_model, 'ambient_shelf_life_con'):
            print(f"  ambient_shelf_life_con: {len(list(pyomo_model.ambient_shelf_life_con))} constraints")

        # Check material balance
        print(f"\nMaterial balance constraints:")
        if hasattr(pyomo_model, 'ambient_balance_con'):
            print(f"  ambient_balance_con: {len(list(pyomo_model.ambient_balance_con))} constraints")

        # Check demand
        print(f"\nDemand constraints:")
        if hasattr(pyomo_model, 'demand_balance_con'):
            print(f"  demand_balance_con: {len(list(pyomo_model.demand_balance_con))} constraints")

        print(f"\nInventory age at planning start:")
        inventory_age = (start_date - inventory_snapshot.snapshot_date).days
        print(f"  Snapshot: {inventory_snapshot.snapshot_date}")
        print(f"  Planning: {start_date}")
        print(f"  Age: {inventory_age} days")
        print(f"  Shelf life limit: 17 days (ambient)")

        if inventory_age >= 17:
            print(f"\n  WARNING: INVENTORY TOO OLD! Violates shelf life")

    else:
        print(f"\nOPTIMAL")
        print(f"  Objective: ${results.best_feasible_objective:,.2f}")

finally:
    sys.stdout = original_stdout
    output_file.close()
    print("Infeasibility report written to: infeasibility_report.txt")
    print("Please share this file!")
