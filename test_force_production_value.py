#!/usr/bin/env python3
"""Fix production to positive value and check if model becomes infeasible."""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
import pyomo.environ as pyo
from pyomo.util.infeasible import log_infeasible_constraints

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

# 2 days
start = date(2025, 10, 17)
end = start + timedelta(days=1)

product_ids = ['HELGAS GFREE MIXED GRAIN 500G']
products = create_test_products(product_ids)

print("="*80)
print("FORCE PRODUCTION VALUE TEST")
print("="*80)

model_obj = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

# Build model
m = model_obj.build_model()

# Fix production for day 1 to 5000 units
node_id = '6122'
prod_id = 'HELGAS GFREE MIXED GRAIN 500G'
day1 = start

if (node_id, prod_id, day1) in m.production:
    print(f"\nFixing production[{node_id}, {prod_id[:30]}, {day1}] = 5000")
    m.production[node_id, prod_id, day1].fix(5000)

# Solve
from pyomo.contrib.appsi.solvers import Highs
solver = Highs()
solver.config.time_limit = 60
solver.config.load_solution = False

try:
    results = solver.solve(m)

    from pyomo.contrib.appsi.base import TerminationCondition as AppsiTC
    print(f"\nResult: {results.termination_condition}")

    if results.termination_condition == AppsiTC.optimal:
        solver.load_vars()
        print(f"  ✓ FEASIBLE with production = 5000!")
        print(f"  Objective: ${pyo.value(m.obj):,.2f}")

        # Check what happened to the 5000 units
        inv_6122 = pyo.value(m.inventory[node_id, prod_id, 'ambient', day1])
        print(f"\n  Production allocated:")
        print(f"    Inventory at 6122: {inv_6122:,.0f}")

        # Check shipments
        for route in model_obj.routes_from_node.get(node_id, []):
            dest = route.destination_node_id
            key = (node_id, dest, prod_id, day1, 'ambient')
            if key in m.in_transit:
                ship_val = pyo.value(m.in_transit[key])
                print(f"    Shipped to {dest}: {ship_val:,.0f}")

    elif results.termination_condition == AppsiTC.infeasible:
        print(f"  ✗ INFEASIBLE with production = 5000!")
        print(f"  This means a constraint prevents production")

        # Log infeasible constraints
        print(f"\n  Infeasible constraints:")
        import logging
        logging.basicConfig(level=logging.INFO)
        log_infeasible_constraints(m, log_expression=True, log_variables=True)

except Exception as e:
    print(f"  Error: {e}")

print("="*80)
