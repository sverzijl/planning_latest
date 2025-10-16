"""Test LP relaxation quality to diagnose MIP performance.

This script:
1. Builds models with different sizes
2. Solves the LP relaxation (no integrality)
3. Solves the full MIP
4. Compares LP bound vs MIP objective to measure relaxation quality

Poor LP relaxation (large gap) indicates the solver must explore
many branch-and-bound nodes, which explains the super-linear solve time growth.
"""

import sys
from pathlib import Path
from datetime import date, timedelta
import time

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast
from pyomo.environ import value


# Parse network data
print("Loading network configuration...")
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules_list = network_parser.parse_truck_schedules()
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)

# Parse full forecast
print("Loading full forecast...")
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')
full_forecast = forecast_parser.parse_forecast()

all_locations = sorted(set(entry.location_id for entry in full_forecast.entries))
all_products = sorted(set(entry.product_id for entry in full_forecast.entries))


def create_test_forecast(start_date, num_days, products, locations):
    """Create filtered forecast for testing."""
    end_date = start_date + timedelta(days=num_days - 1)

    filtered_entries = [
        entry for entry in full_forecast.entries
        if (entry.forecast_date >= start_date and
            entry.forecast_date <= end_date and
            entry.product_id in products and
            entry.location_id in locations)
    ]

    return Forecast(name="Test Forecast", entries=filtered_entries)


def test_lp_relaxation(num_destinations, num_days=14):
    """Test LP relaxation quality."""
    locations_subset = all_locations[:num_destinations]

    print(f"\n{'='*80}")
    print(f"Testing {num_destinations} destinations, {num_days} days")
    print(f"{'='*80}")

    forecast = create_test_forecast(
        start_date=date(2025, 6, 2),
        num_days=num_days,
        products=all_products,
        locations=locations_subset,
    )

    # Build model
    model_obj = IntegratedProductionDistributionModel(
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
    )

    # Solve LP relaxation first (relax binary variables)
    print("Solving LP relaxation...")
    from pyomo.environ import Var

    model = model_obj.build_model()

    # Relax binary variables to continuous [0,1]
    for var in model.component_objects(ctype=Var, active=True):
        for index in var:
            if var[index].is_binary():
                var[index].domain = None
                var[index].setlb(0)
                var[index].setub(1)

    # Solve LP
    lp_start = time.time()
    from pyomo.opt import SolverFactory
    solver = SolverFactory('cbc')
    lp_results = solver.solve(model, tee=False, symbolic_solver_labels=False)
    lp_time = time.time() - lp_start

    lp_obj = None
    if lp_results.solver.termination_condition == 'optimal':
        lp_obj = value(model.obj)
        print(f"LP relaxation: ${lp_obj:,.2f} in {lp_time:.2f}s")
    else:
        print(f"LP relaxation failed: {lp_results.solver.termination_condition}")

    # Now solve full MIP
    print("Solving full MIP...")
    result = model_obj.solve(
        solver_name='cbc',
        time_limit_seconds=60,
        mip_gap=0.05,
        tee=False,
    )

    print(f"MIP: {result.termination_condition}, ${result.objective_value:,.2f} in {result.solve_time_seconds:.2f}s")

    # Calculate gap
    gap_pct = None
    if lp_obj and result.objective_value:
        gap_pct = 100.0 * (result.objective_value - lp_obj) / result.objective_value
        print(f"LP-MIP gap: {gap_pct:.2f}%")

    return {
        'num_destinations': num_destinations,
        'lp_objective': lp_obj,
        'lp_time': lp_time,
        'mip_objective': result.objective_value,
        'mip_time': result.solve_time_seconds,
        'gap_pct': gap_pct,
    }


# Test different sizes
results = []

for n_dest in [2, 3, 4, 5, 6]:
    result = test_lp_relaxation(n_dest, num_days=14)
    results.append(result)

    # Stop if MIP takes > 30s
    if result['mip_time'] and result['mip_time'] > 30:
        print(f"\n⚠️  MIP solve time excessive at {n_dest} destinations")
        break

# Summary
print(f"\n{'='*80}")
print("LP RELAXATION QUALITY SUMMARY")
print(f"{'='*80}")
print(f"{'Dest':<6} {'LP Objective':<15} {'MIP Objective':<15} {'LP-MIP Gap':<12} {'MIP Time':<10}")
print(f"{'-'*80}")

for r in results:
    lp_str = f"${r['lp_objective']:,.0f}" if r['lp_objective'] else "N/A"
    mip_str = f"${r['mip_objective']:,.0f}" if r['mip_objective'] else "N/A"
    gap_str = f"{r['gap_pct']:.2f}%" if r['gap_pct'] else "N/A"
    time_str = f"{r['mip_time']:.2f}s" if r['mip_time'] else "N/A"

    print(f"{r['num_destinations']:<6} {lp_str:<15} {mip_str:<15} {gap_str:<12} {time_str:<10}")

print(f"\n{'='*80}")
print("INTERPRETATION:")
print("- Small gap (<1%): LP relaxation is tight, MIP should solve quickly")
print("- Medium gap (1-10%): Moderate branch-and-bound effort required")
print("- Large gap (>10%): Weak relaxation, exponential node growth likely")
print(f"{'='*80}")
