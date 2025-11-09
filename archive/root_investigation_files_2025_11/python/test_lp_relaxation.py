#!/usr/bin/env python3
from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
import pyomo.environ as pyo

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

start = date(2025, 10, 17)
end = start

product_ids = ['HELGAS GFREE MIXED GRAIN 500G']
products = create_test_products(product_ids)

model_obj = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=None,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

m = model_obj.build_model()

# Relax integers
for v in m.component_data_objects(pyo.Var, active=True):
    if v.is_integer() or v.is_binary():
        v.domain = pyo.NonNegativeReals if v.is_integer() else pyo.Reals

from pyomo.contrib.appsi.solvers import Highs
solver = Highs()
solver.config.load_solution = False
results = solver.solve(m)

from pyomo.contrib.appsi.base import TerminationCondition as AppsiTC
if results.termination_condition == AppsiTC.optimal:
    solver.load_vars()
    total_prod = sum(pyo.value(m.production[k], exception=False) or 0 for k in m.production)
    print(f"LP Relaxation: production={total_prod:.2f}, obj=${pyo.value(m.obj):.2f}")
    if total_prod > 100:
        print("✓ LP produces - MIP heuristics issue")
    else:
        print("✗ LP also zero - formulation issue")
