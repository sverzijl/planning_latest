#!/usr/bin/env python3
"""Simple constraint elimination test."""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
import pyomo.environ as pyo

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

# Convert
mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

# 1 day, 1 product
start = date(2025, 10, 17)
end = start

product_ids = ['HELGAS GFREE MIXED GRAIN 500G']
products = create_test_products(product_ids)

print("="*80)
print("SIMPLE CONSTRAINT ELIMINATION")
print("="*80)

# Calculate expected demand
total_demand = sum(e.quantity for e in forecast.entries if e.forecast_date == start and e.product_id == product_ids[0])
print(f"\nDemand for {product_ids[0]} on {start}: {total_demand:,.0f} units")
print(f"Shortage cost if no production: ${total_demand * 10:,.2f}")
print(f"Production cost to meet demand: ${total_demand * 1.30:,.2f}")
print(f"Expected: Model should produce!")

constraint_groups = [
    ("Full model", []),
    ("Without shelf life", ['ambient_shelf_life_con', 'frozen_shelf_life_con', 'thawed_shelf_life_con']),
    ("Without changeover", ['product_binary_linking_con', 'product_start_detection_con']),
    ("Without mix constraint", ['mix_production_con']),
]

for name, disabled_constraints in constraint_groups:
    print(f"\n{name}:")
    print("-"*40)

    # Build fresh model
    model = SlidingWindowModel(
        nodes=nodes, routes=unified_routes, forecast=forecast,
        products=products, labor_calendar=labor_calendar,
        cost_structure=cost_params, start_date=start, end_date=end,
        truck_schedules=unified_trucks, initial_inventory=None,
        allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
    )

    # Build Pyomo model
    m = model.build_model()

    # Deactivate specified constraints
    for con_name in disabled_constraints:
        if hasattr(m, con_name):
            getattr(m, con_name).deactivate()
            print(f"  Deactivated: {con_name}")

    # Solve manually
    from pyomo.contrib.appsi.solvers import Highs
    solver = Highs()
    solver.config.time_limit = 30
    solver.config.mip_gap = 0.01
    solver.config.load_solution = False
    results = solver.solve(m)

    # Load solution if optimal
    from pyomo.contrib.appsi.base import TerminationCondition as AppsiTC
    if results.termination_condition == AppsiTC.optimal:
        solver.load_vars()

        # Extract production
        total_prod = 0
        for key in m.production:
            try:
                val = pyo.value(m.production[key], exception=False)
                if val and abs(val) > 0.01:
                    total_prod += val
            except:
                pass

        print(f"  Result: OPTIMAL")
        print(f"  Objective: ${pyo.value(m.obj):,.2f}")
        print(f"  Production: {total_prod:,.0f} units")

        if total_prod > 1000:
            print(f"  ✓ PRODUCES when {disabled_constraints} disabled!")
            print(f"  → One of these constraints is preventing production")
            break
    else:
        print(f"  Result: {results.termination_condition}")

print("\n" + "="*80)
