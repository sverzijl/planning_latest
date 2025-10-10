"""Diagnose why 3-week test times out when 1-2 weeks are fast.

This script will:
1. Build models for 1, 2, 3 weeks and compare structure
2. Solve LP relaxations (no integer constraints) to isolate the issue
3. Analyze constraint density and complexity
4. Check for infeasibility or tight constraints
"""

from datetime import date, timedelta
from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast
from pyomo.environ import *

def analyze_model_structure(weeks, network_parser, full_forecast, locations, routes,
                            labor_calendar, truck_schedules, cost_structure, manufacturing_site):
    """Analyze model structure without solving."""

    start_date = date(2025, 6, 2)
    end_date = start_date + timedelta(days=weeks * 7 - 1)

    filtered_entries = [e for e in full_forecast.entries if start_date <= e.forecast_date <= end_date]
    horizon_forecast = Forecast(name=f"{weeks}W", entries=filtered_entries, creation_date=date.today())

    print(f"\n{'='*70}")
    print(f"{weeks} WEEK ANALYSIS (June 2 - {end_date})")
    print(f"{'='*70}")

    # Build model
    model_obj = IntegratedProductionDistributionModel(
        forecast=horizon_forecast,
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

    # Build Pyomo model
    pyomo_model = model_obj.build_model()

    # Get statistics
    num_vars = pyomo_model.nvariables()
    num_constraints = pyomo_model.nconstraints()
    num_integer_vars = sum(1 for v in pyomo_model.component_data_objects(Var)
                          if v.is_integer() or v.is_binary())

    # Count constraint types
    constraint_counts = {}
    for con in pyomo_model.component_objects(Constraint):
        constraint_counts[con.name] = len(con)

    print(f"\nModel Structure:")
    print(f"  Variables:        {num_vars:,}")
    print(f"  Constraints:      {num_constraints:,}")
    print(f"  Integer vars:     {num_integer_vars:,}")
    print(f"  Planning days:    {len(model_obj.production_dates)}")
    print(f"  Forecast entries: {len(filtered_entries)}")

    print(f"\nConstraint Breakdown:")
    for name, count in sorted(constraint_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"  {name:40s}: {count:,}")

    # Try LP relaxation (relax integer constraints)
    print(f"\nSolving LP Relaxation (no integer constraints)...")

    # Relax all integer/binary variables to continuous
    for v in pyomo_model.component_data_objects(Var):
        if v.is_integer() or v.is_binary():
            v.domain = Reals
            if v.is_binary():
                v.setlb(0)
                v.setub(1)

    from pyomo.opt import SolverFactory
    solver = SolverFactory('cbc')

    import time
    start = time.time()
    lp_result = solver.solve(pyomo_model, tee=False)
    lp_time = time.time() - start

    lp_status = lp_result.solver.termination_condition
    lp_obj = pyomo_model.obj() if lp_status == TerminationCondition.optimal else None

    print(f"  LP Status:     {lp_status}")
    print(f"  LP Solve Time: {lp_time:.2f}s")
    if lp_obj:
        print(f"  LP Objective:  ${lp_obj:,.2f}")

    # Now try with integer constraints but short time limit
    print(f"\nSolving MIP (with integer constraints, 10s limit)...")

    # Rebuild to restore integer constraints
    pyomo_model = model_obj.build_model()
    solver.options['seconds'] = 10

    start = time.time()
    mip_result = solver.solve(pyomo_model, tee=False)
    mip_time = time.time() - start

    mip_status = mip_result.solver.termination_condition

    # Extract gap if available
    gap = None
    if hasattr(mip_result.solver, 'gap'):
        gap = mip_result.solver.gap

    print(f"  MIP Status:       {mip_status}")
    print(f"  MIP Solve Time:   {mip_time:.2f}s")
    if gap is not None:
        print(f"  MIP Gap:          {gap*100:.2f}%")

    # Check if we have both LP and MIP objectives
    if lp_obj and mip_status == TerminationCondition.optimal:
        mip_obj = pyomo_model.obj()
        integrality_gap = (mip_obj - lp_obj) / lp_obj * 100
        print(f"  Integrality Gap:  {integrality_gap:.2f}%")

    return {
        'weeks': weeks,
        'num_vars': num_vars,
        'num_constraints': num_constraints,
        'num_integer_vars': num_integer_vars,
        'lp_time': lp_time,
        'lp_status': str(lp_status),
        'lp_obj': lp_obj,
        'mip_time': mip_time,
        'mip_status': str(mip_status),
        'constraint_counts': constraint_counts
    }

# Load data
print("Loading data...")
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules_list = network_parser.parse_truck_schedules()
truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

print(f"Full dataset: {len(full_forecast.entries)} entries")

# Analyze 1, 2, 3 weeks
results = []
for weeks in [1, 2, 3]:
    result = analyze_model_structure(
        weeks, network_parser, full_forecast, locations, routes,
        labor_calendar, truck_schedules, cost_structure, manufacturing_site
    )
    results.append(result)

# Summary comparison
print(f"\n{'='*70}")
print("COMPARATIVE ANALYSIS")
print(f"{'='*70}")

print(f"\nModel Size Growth:")
print(f"  Weeks  Variables  Constraints  Integer Vars  LP Time   MIP Time(10s)")
print(f"  {'-'*70}")
for r in results:
    print(f"  {r['weeks']:5}  {r['num_vars']:9,}  {r['num_constraints']:11,}  {r['num_integer_vars']:12,}  "
          f"{r['lp_time']:7.2f}s  {r['mip_time']:7.2f}s")

# Calculate growth rates
print(f"\nGrowth Rates (per week):")
for i in range(1, len(results)):
    prev = results[i-1]
    curr = results[i]
    var_growth = curr['num_vars'] / prev['num_vars']
    con_growth = curr['num_constraints'] / prev['num_constraints']
    int_growth = curr['num_integer_vars'] / prev['num_integer_vars']
    lp_growth = curr['lp_time'] / prev['lp_time'] if prev['lp_time'] > 0 else 0
    mip_growth = curr['mip_time'] / prev['mip_time'] if prev['mip_time'] > 0 else 0

    print(f"  Week {prev['weeks']} → {curr['weeks']}:")
    print(f"    Variables:    {var_growth:.2f}x")
    print(f"    Constraints:  {con_growth:.2f}x")
    print(f"    Integer vars: {int_growth:.2f}x")
    print(f"    LP time:      {lp_growth:.2f}x")
    print(f"    MIP time:     {mip_growth:.2f}x")

# Diagnose the issue
print(f"\n{'='*70}")
print("DIAGNOSIS")
print(f"{'='*70}")

if results[2]['lp_time'] > 10:
    print("❌ ISSUE: LP relaxation is slow (>10s)")
    print("   This suggests constraint complexity or numerical issues")
    print("   The integer programming aspect is not the primary bottleneck")
elif results[2]['mip_time'] >= 9.5:
    print("❌ ISSUE: MIP hits time limit while LP is fast")
    print("   This suggests the integer programming structure is very difficult")
    print("   Possible causes:")
    print("   - Weak LP relaxation (large integrality gap)")
    print("   - Many binary variables creating exponential search tree")
    print("   - Symmetric solutions making branch-and-bound inefficient")
else:
    print("✅ Both LP and MIP solve quickly at 3 weeks")
    print("   The 120s timeout in full solve may be due to:")
    print("   - Different solver settings")
    print("   - Tighter MIP gap tolerance (0.01 vs default)")

print(f"\nRecommendations:")
if results[2]['lp_time'] > 1:
    print("  1. Investigate constraint structure - some constraints may be creating")
    print("     dense coefficient matrices or numerical issues")
    print("  2. Consider reformulation or constraint aggregation")
else:
    print("  1. The LP relaxation is tight - focus on integer programming improvements:")
    print("     - Add cuts or valid inequalities to strengthen relaxation")
    print("     - Consider symmetry-breaking constraints")
    print("     - Use branching priorities or heuristics")
    print("  2. For production use:")
    print("     - Relax MIP gap to 2-5% for faster solutions")
    print("     - Use commercial solver (Gurobi/CPLEX) with better branch-and-cut")
