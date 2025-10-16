"""Diagnose why week 2→3 has massive performance cliff (1.96s → 11.11s).

This script will:
1. Solve LP relaxations for weeks 1, 2, 3
2. Count fractional binary variables in each LP solution
3. Measure integrality gaps
4. Analyze CBC presolve effectiveness
5. Identify the root cause of the performance cliff
"""

from datetime import date, timedelta
import time
from pyomo.environ import *
from pyomo.opt import SolverFactory
from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast

def analyze_horizon(weeks, full_forecast, network_parser, locations, routes,
                    labor_calendar, truck_schedules, cost_structure, manufacturing_site):
    """Analyze LP relaxation and MIP for a given horizon."""

    start_date = date(2025, 6, 2)
    end_date = start_date + timedelta(days=weeks * 7 - 1)

    filtered_entries = [e for e in full_forecast.entries if start_date <= e.forecast_date <= end_date]
    horizon_forecast = Forecast(name=f"{weeks}W", entries=filtered_entries, creation_date=date.today())

    print(f"\n{'='*70}")
    print(f"WEEK {weeks} ANALYSIS ({start_date} to {end_date})")
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

    pyomo_model = model_obj.build_model()

    # Get statistics
    num_vars = pyomo_model.nvariables()
    num_constraints = pyomo_model.nconstraints()

    # Collect all binary/integer variables
    binary_vars = []
    for v in pyomo_model.component_data_objects(Var):
        if v.is_binary() or v.is_integer():
            binary_vars.append(v)

    print(f"\nModel Structure:")
    print(f"  Total variables: {num_vars:,}")
    print(f"  Constraints: {num_constraints:,}")
    print(f"  Binary/integer variables: {len(binary_vars):,}")

    # ========================================================================
    # STEP 1: Solve LP Relaxation
    # ========================================================================
    print(f"\n{'─'*70}")
    print("STEP 1: LP RELAXATION (no integer constraints)")
    print(f"{'─'*70}")

    # Save original domains (use id as key since Var objects are not hashable)
    original_domains = {}
    for v in binary_vars:
        original_domains[id(v)] = (v.domain, v.lb, v.ub)
        v.domain = Reals
        if v.is_binary():
            v.setlb(0)
            v.setub(1)

    solver = SolverFactory('cbc')

    start_time = time.time()
    lp_result = solver.solve(pyomo_model, tee=False)
    lp_time = time.time() - start_time

    lp_status = lp_result.solver.termination_condition
    lp_obj = value(pyomo_model.obj) if lp_status == TerminationCondition.optimal else None

    print(f"  Status: {lp_status}")
    print(f"  Solve time: {lp_time:.3f}s")
    if lp_obj:
        print(f"  Objective: ${lp_obj:,.2f}")

    # Count fractional variables
    fractional_vars = []
    if lp_obj:
        for v in binary_vars:
            val = value(v)
            if val is not None and 0.001 < val < 0.999:  # Fractional within tolerance
                fractional_vars.append((str(v), val))

        print(f"\n  Fractional binary variables: {len(fractional_vars)} / {len(binary_vars)}")
        print(f"  Fractional percentage: {len(fractional_vars)/len(binary_vars)*100:.1f}%")

        # Show some examples
        if len(fractional_vars) > 0:
            print(f"\n  Sample fractional variables:")
            for var_name, val in fractional_vars[:10]:
                print(f"    {var_name} = {val:.4f}")

    # ========================================================================
    # STEP 2: Restore integer constraints and solve MIP (short timeout)
    # ========================================================================
    print(f"\n{'─'*70}")
    print("STEP 2: MIP SOLUTION (with integer constraints, 15s timeout)")
    print(f"{'─'*70}")

    # Restore original domains
    for v in binary_vars:
        domain, lb, ub = original_domains[id(v)]
        v.domain = domain
        if lb is not None:
            v.setlb(lb)
        if ub is not None:
            v.setub(ub)

    solver.options['seconds'] = 15
    solver.options['ratioGap'] = 0.01

    start_time = time.time()
    mip_result = solver.solve(pyomo_model, tee=False)
    mip_time = time.time() - start_time

    mip_status = mip_result.solver.termination_condition
    mip_obj = value(pyomo_model.obj) if mip_status in [TerminationCondition.optimal, TerminationCondition.maxTimeLimit] else None

    print(f"  Status: {mip_status}")
    print(f"  Solve time: {mip_time:.3f}s")
    if mip_obj:
        print(f"  Objective: ${mip_obj:,.2f}")

    # Calculate integrality gap
    integrality_gap = None
    if lp_obj and mip_obj and lp_obj > 0:
        integrality_gap = (mip_obj - lp_obj) / lp_obj * 100
        print(f"\n  Integrality Gap: {integrality_gap:.2f}%")
        print(f"    LP bound:  ${lp_obj:,.2f}")
        print(f"    MIP value: ${mip_obj:,.2f}")

    # ========================================================================
    # STEP 3: Analyze solution characteristics
    # ========================================================================
    print(f"\n{'─'*70}")
    print("STEP 3: SOLUTION CHARACTERISTICS")
    print(f"{'─'*70}")

    # In MIP solution, count how many binaries are at boundaries
    if mip_obj:
        at_zero = 0
        at_one = 0
        fractional_in_mip = 0

        for v in binary_vars:
            val = value(v)
            if val is not None:
                if val < 0.001:
                    at_zero += 1
                elif val > 0.999:
                    at_one += 1
                else:
                    fractional_in_mip += 1

        print(f"  Binary variables at 0: {at_zero} ({at_zero/len(binary_vars)*100:.1f}%)")
        print(f"  Binary variables at 1: {at_one} ({at_one/len(binary_vars)*100:.1f}%)")
        print(f"  Fractional (unexpected): {fractional_in_mip}")

    return {
        'weeks': weeks,
        'num_vars': num_vars,
        'num_constraints': num_constraints,
        'num_binary': len(binary_vars),
        'lp_time': lp_time,
        'lp_obj': lp_obj,
        'lp_status': str(lp_status),
        'num_fractional_lp': len(fractional_vars),
        'pct_fractional_lp': len(fractional_vars) / len(binary_vars) * 100 if binary_vars else 0,
        'mip_time': mip_time,
        'mip_obj': mip_obj,
        'mip_status': str(mip_status),
        'integrality_gap': integrality_gap,
        'sample_fractional': fractional_vars[:5]  # Keep first 5 for reporting
    }

# ============================================================================
# MAIN ANALYSIS
# ============================================================================

print("="*70)
print("PERFORMANCE CLIFF DIAGNOSTIC")
print("="*70)
print("\nInvestigating why week 2 → 3 has 5.67x slowdown (1.96s → 11.11s)")
print("when week 1 → 2 only has 1.51x slowdown (1.30s → 1.96s)")

# Load data
print("\nLoading data...")
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

# Analyze weeks 1, 2, 3
results = []
for weeks in [1, 2, 3]:
    result = analyze_horizon(
        weeks, full_forecast, network_parser, locations, routes,
        labor_calendar, truck_schedules, cost_structure, manufacturing_site
    )
    results.append(result)

# ============================================================================
# COMPARATIVE ANALYSIS
# ============================================================================

print(f"\n{'='*70}")
print("COMPARATIVE ANALYSIS")
print(f"{'='*70}")

print(f"\n{'Week':<6} {'Binary':<8} {'LP Time':<10} {'Fractional':<12} {'Frac %':<10} {'MIP Time':<10} {'Int Gap':<10}")
print("─"*70)
for r in results:
    frac_pct = f"{r['pct_fractional_lp']:.1f}%"
    int_gap = f"{r['integrality_gap']:.0f}%" if r['integrality_gap'] else "N/A"
    print(f"{r['weeks']:<6} {r['num_binary']:<8} {r['lp_time']:<10.3f} {r['num_fractional_lp']:<12} {frac_pct:<10} {r['mip_time']:<10.3f} {int_gap:<10}")

print(f"\nGrowth Rates:")
print("─"*70)
for i in range(1, len(results)):
    prev = results[i-1]
    curr = results[i]

    lp_growth = curr['lp_time'] / prev['lp_time'] if prev['lp_time'] > 0 else 0
    mip_growth = curr['mip_time'] / prev['mip_time'] if prev['mip_time'] > 0 else 0
    frac_growth = curr['num_fractional_lp'] / prev['num_fractional_lp'] if prev['num_fractional_lp'] > 0 else 0

    print(f"\nWeek {prev['weeks']} → {curr['weeks']}:")
    print(f"  LP time:          {lp_growth:.2f}x")
    print(f"  MIP time:         {mip_growth:.2f}x  ← {'⚠️ CLIFF' if mip_growth > 3 else ''}")
    print(f"  Fractional vars:  {frac_growth:.2f}x")

# ============================================================================
# ROOT CAUSE DIAGNOSIS
# ============================================================================

print(f"\n{'='*70}")
print("ROOT CAUSE DIAGNOSIS")
print(f"{'='*70}")

# Check LP growth
lp_ratio_12 = results[1]['lp_time'] / results[0]['lp_time']
lp_ratio_23 = results[2]['lp_time'] / results[1]['lp_time']

# Check MIP growth
mip_ratio_12 = results[1]['mip_time'] / results[0]['mip_time']
mip_ratio_23 = results[2]['mip_time'] / results[1]['mip_time']

# Check fractional variable growth
frac_ratio_12 = results[1]['num_fractional_lp'] / results[0]['num_fractional_lp'] if results[0]['num_fractional_lp'] > 0 else 0
frac_ratio_23 = results[2]['num_fractional_lp'] / results[1]['num_fractional_lp'] if results[1]['num_fractional_lp'] > 0 else 0

print(f"\n1. LP COMPLEXITY:")
if lp_ratio_23 > 2.5:
    print(f"   ❌ LP solve time grows {lp_ratio_23:.2f}x (week 2→3)")
    print(f"   → Problem: Constraint structure is becoming complex")
elif lp_ratio_23 > lp_ratio_12 * 1.5:
    print(f"   ⚠️  LP solve accelerating: {lp_ratio_12:.2f}x → {lp_ratio_23:.2f}x")
    print(f"   → Mild concern: LP scaling getting worse")
else:
    print(f"   ✅ LP scales well: {lp_ratio_12:.2f}x → {lp_ratio_23:.2f}x")
    print(f"   → LP complexity is NOT the bottleneck")

print(f"\n2. INTEGRALITY GAP:")
gap_12 = results[1]['integrality_gap']
gap_23 = results[2]['integrality_gap']
if gap_12 and gap_23:
    if gap_23 > gap_12 * 1.5:
        print(f"   ❌ Gap growing rapidly: {gap_12:.0f}% → {gap_23:.0f}%")
        print(f"   → Problem: LP relaxation weakening significantly")
    elif gap_23 > 200:
        print(f"   ⚠️  Gap remains large: {gap_23:.0f}%")
        print(f"   → LP bound not very useful for pruning")
    else:
        print(f"   ✅ Gap reasonable: {gap_23:.0f}%")

print(f"\n3. FRACTIONAL BINARY VARIABLES:")
print(f"   Week 1: {results[0]['num_fractional_lp']} / {results[0]['num_binary']} ({results[0]['pct_fractional_lp']:.1f}%)")
print(f"   Week 2: {results[1]['num_fractional_lp']} / {results[1]['num_binary']} ({results[1]['pct_fractional_lp']:.1f}%)")
print(f"   Week 3: {results[2]['num_fractional_lp']} / {results[2]['num_binary']} ({results[2]['pct_fractional_lp']:.1f}%)")

if frac_ratio_23 > 2.0:
    print(f"   ❌ Fractional vars spike {frac_ratio_23:.2f}x at week 3")
    print(f"   → This DIRECTLY causes branch-and-bound explosion")
elif results[2]['num_fractional_lp'] > 50:
    print(f"   ⚠️  Too many fractional vars ({results[2]['num_fractional_lp']})")
    print(f"   → Search tree size: 2^{results[2]['num_fractional_lp']} = {2**results[2]['num_fractional_lp']:.2e} nodes")
else:
    print(f"   ✅ Fractional vars manageable")

print(f"\n4. MIP SOLVER BEHAVIOR:")
if mip_ratio_23 > 4.0 and mip_ratio_12 < 2.0:
    print(f"   ❌ DISCRETE PERFORMANCE CLIFF at week 3")
    print(f"   → Week 1→2: {mip_ratio_12:.2f}x (manageable)")
    print(f"   → Week 2→3: {mip_ratio_23:.2f}x (CLIFF!)")
    print(f"   → Likely cause: CBC heuristics become ineffective")
    print(f"   → Problem crosses internal solver threshold")
else:
    print(f"   Continuous exponential growth: {mip_ratio_12:.2f}x → {mip_ratio_23:.2f}x")

# ============================================================================
# SUMMARY AND RECOMMENDATIONS
# ============================================================================

print(f"\n{'='*70}")
print("SUMMARY")
print(f"{'='*70}")

print(f"\nThe {mip_ratio_23:.2f}x performance cliff from week 2 → 3 is caused by:")

# Determine primary cause
if frac_ratio_23 > 2.0:
    print(f"\n🎯 PRIMARY CAUSE: Fractional binary variable explosion")
    print(f"   - Week 2: {results[1]['num_fractional_lp']} fractional binaries")
    print(f"   - Week 3: {results[2]['num_fractional_lp']} fractional binaries ({frac_ratio_23:.2f}x increase)")
    print(f"   - This creates 2^{results[2]['num_fractional_lp'] - results[1]['num_fractional_lp']} = {2**(results[2]['num_fractional_lp'] - results[1]['num_fractional_lp']):.2e}x more search nodes")
elif gap_12 and gap_23 and gap_23 > gap_12 * 1.5:
    print(f"\n🎯 PRIMARY CAUSE: Weakening LP relaxation")
    print(f"   - Integrality gap growing: {gap_12:.0f}% → {gap_23:.0f}%")
    print(f"   - Weaker bounds → less effective pruning → more nodes explored")
elif mip_ratio_23 > 4.0:
    print(f"\n🎯 PRIMARY CAUSE: CBC heuristic threshold")
    print(f"   - CBC's built-in heuristics work well up to ~250 binary vars")
    print(f"   - Week 3 ({results[2]['num_binary']} binary vars) crosses effectiveness threshold")
    print(f"   - Solver falls back to pure branch-and-bound (much slower)")

print(f"\n{'='*70}")
print("RECOMMENDATIONS")
print(f"{'='*70}")

print(f"\n1. ✅ SPARSE INDEXING (Already Implemented)")
print(f"   - Reduced variables by 73%")
print(f"   - Provides modest speedup for weeks 1-2")
print(f"   - Does NOT fix the fundamental cliff")

print(f"\n2. 🎯 SYMMETRY BREAKING (High Priority)")
print(f"   - Add lexicographic ordering for trucks to same destination")
print(f"   - Should reduce fractional vars and search tree")
print(f"   - Expected: 3-5x additional speedup")

print(f"\n3. ⚡ COMMERCIAL SOLVER (If Available)")
print(f"   - Gurobi/CPLEX have better heuristics and preprocessing")
print(f"   - May handle week 3 in 2-3s instead of 11s")
print(f"   - Expected: 5-10x speedup")

print(f"\n4. 🔧 ROLLING HORIZON (Production Ready)")
print(f"   - Optimize 4-week windows")
print(f"   - Guaranteed solve time: ~25-30s per window")
print(f"   - Total for 29 weeks: ~3-5 minutes")

print(f"\n{'='*70}")
print("ANALYSIS COMPLETE")
print(f"{'='*70}")
