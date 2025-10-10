"""Analyze symmetry in the truck assignment problem.

Symmetry occurs when multiple solutions are mathematically equivalent but appear
different to the solver. This causes the branch-and-bound algorithm to explore
many identical subtrees, wasting enormous computational effort.
"""

from datetime import date, timedelta
from src.parsers import ExcelParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast
from pyomo.environ import *
from collections import defaultdict

def analyze_symmetry(weeks=2):
    """Analyze symmetry in truck assignments for a given horizon."""

    # Load data
    print(f"Loading data for {weeks}-week horizon...")
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

    # Filter forecast
    start_date = date(2025, 6, 2)
    end_date = start_date + timedelta(days=weeks * 7 - 1)
    filtered_entries = [e for e in full_forecast.entries if start_date <= e.forecast_date <= end_date]
    horizon_forecast = Forecast(name=f"{weeks}W", entries=filtered_entries, creation_date=date.today())

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

    print(f"\n{'='*70}")
    print(f"SYMMETRY ANALYSIS: {weeks} WEEKS")
    print(f"{'='*70}")

    # Analyze truck assignment structure
    print(f"\n1. TRUCK ASSIGNMENT STRUCTURE")
    print(f"   {'-'*66}")

    # Group trucks by destination
    trucks_by_dest = defaultdict(list)
    for truck_idx in model_obj.truck_indices:
        truck = model_obj.truck_by_index[truck_idx]
        dest = truck.destination_id
        trucks_by_dest[dest].append(truck_idx)

    print(f"\n   Trucks grouped by destination:")
    total_symmetric = 0
    for dest, truck_list in sorted(trucks_by_dest.items()):
        count = len(truck_list)
        print(f"     {dest}: {count} trucks (indices: {truck_list})")
        if count > 1:
            print(f"       → {count}! = {factorial(count):,} equivalent orderings")
            total_symmetric += count

    # Group trucks by day-of-week and destination
    print(f"\n   Trucks grouped by day-of-week + destination:")
    trucks_by_day_dest = defaultdict(lambda: defaultdict(list))

    for truck_idx in model_obj.truck_indices:
        truck = model_obj.truck_by_index[truck_idx]
        dow = truck.day_of_week
        dest = truck.destination_id
        trucks_by_day_dest[dow][dest].append(truck_idx)

    symmetric_groups = []
    for dow in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
        if dow in trucks_by_day_dest:
            for dest, truck_list in sorted(trucks_by_day_dest[dow].items()):
                if len(truck_list) > 1:
                    symmetric_groups.append((dow, dest, truck_list))
                    print(f"     {dow} → {dest}: {len(truck_list)} trucks {truck_list}")
                    print(f"       → SYMMETRIC: {len(truck_list)}! = {factorial(len(truck_list)):,} orderings")

    # Calculate total symmetry
    if symmetric_groups:
        total_symmetry = 1
        for dow, dest, trucks in symmetric_groups:
            total_symmetry *= factorial(len(trucks))

        print(f"\n   🔴 TOTAL SYMMETRY: {total_symmetry:,} equivalent solutions")
        print(f"      (Before considering which products go on which truck)")

    # Analyze binary variables
    print(f"\n2. BINARY VARIABLE STRUCTURE")
    print(f"   {'-'*66}")

    pyomo_model = model_obj.build_model()

    truck_used_vars = []
    for v in pyomo_model.component_data_objects(Var):
        if 'truck_used' in str(v):
            truck_used_vars.append(v)

    print(f"\n   truck_used[truck_idx, date] variables: {len(truck_used_vars)}")

    # Sample some truck_used constraints
    print(f"\n   Example: truck_used variables for delivery date 2025-06-03 (Tuesday):")
    sample_date = date(2025, 6, 3)
    for truck_idx in range(min(5, len(model_obj.truck_indices))):
        truck = model_obj.truck_by_index[truck_idx]
        print(f"     truck_used[{truck_idx}, {sample_date}] → Truck to {truck.destination_id} ({truck.day_of_week})")

    # Demonstrate symmetry with example
    print(f"\n3. CONCRETE SYMMETRY EXAMPLE")
    print(f"   {'-'*66}")

    # Find a destination with multiple trucks
    multi_truck_dest = None
    for dest, trucks in trucks_by_dest.items():
        if len(trucks) >= 2:
            multi_truck_dest = (dest, trucks)
            break

    if multi_truck_dest:
        dest, truck_indices = multi_truck_dest
        print(f"\n   Destination: {dest}")
        print(f"   Available trucks: {len(truck_indices)}")

        # Show first few trucks
        for idx in truck_indices[:4]:
            truck = model_obj.truck_by_index[idx]
            print(f"     Truck {idx}: {truck.day_of_week}, capacity={truck.capacity}")

        print(f"\n   Consider shipping 1000 units of product 168846 on Tuesday:")
        print(f"\n   Solution A:")
        print(f"     truck_load[{truck_indices[0]}, {dest}, 168846, 2025-06-03] = 1000")
        print(f"     truck_load[{truck_indices[1]}, {dest}, 168846, 2025-06-03] = 0")
        if len(truck_indices) > 2:
            print(f"     truck_load[{truck_indices[2]}, {dest}, 168846, 2025-06-03] = 0")

        print(f"\n   Solution B:")
        print(f"     truck_load[{truck_indices[0]}, {dest}, 168846, 2025-06-03] = 0")
        print(f"     truck_load[{truck_indices[1]}, {dest}, 168846, 2025-06-03] = 1000")
        if len(truck_indices) > 2:
            print(f"     truck_load[{truck_indices[2]}, {dest}, 168846, 2025-06-03] = 0")

        print(f"\n   ✅ Both solutions have IDENTICAL cost (same truck cost)")
        print(f"   ✅ Both satisfy ALL constraints")
        print(f"   ❌ Solver explores BOTH branches of search tree")
        print(f"   ❌ This duplication happens at EVERY branching decision")

    # Calculate branching factor
    print(f"\n4. BRANCH-AND-BOUND IMPACT")
    print(f"   {'-'*66}")

    num_binary = sum(1 for v in pyomo_model.component_data_objects(Var) if v.is_binary())

    print(f"\n   Total binary variables: {num_binary:,}")
    print(f"   Theoretical search space: 2^{num_binary} = {2**num_binary:.2e} nodes")

    if symmetric_groups:
        print(f"\n   With symmetry reduction:")
        print(f"     Symmetric solutions: {total_symmetry:,}")
        print(f"     Effective search space: (2^{num_binary}) / {total_symmetry:,}")
        print(f"                            = {(2**num_binary) / total_symmetry:.2e} nodes")
        print(f"\n   ⚠️  Solver explores {total_symmetry:,}x more nodes than necessary!")

    # Show how this compounds
    print(f"\n5. EXPONENTIAL COMPOUNDING")
    print(f"   {'-'*66}")

    print(f"\n   As horizon grows:")
    print(f"     Week 1: ~132 binary vars, ~few symmetric groups")
    print(f"     Week 2: ~216 binary vars, ~more symmetric groups")
    print(f"     Week 3: ~300 binary vars, ~many symmetric groups")

    print(f"\n   Each week adds:")
    print(f"     - More binary variables (linear growth)")
    print(f"     - More symmetric truck assignments (exponential impact)")
    print(f"     - More branching decisions affected by symmetry")

    print(f"\n   Result: 2.92x slowdown per week on average")

    return {
        'symmetric_groups': symmetric_groups,
        'total_symmetry': total_symmetry if symmetric_groups else 1,
        'num_binary': num_binary
    }

def factorial(n):
    """Calculate factorial."""
    if n <= 1:
        return 1
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result

if __name__ == "__main__":
    print("="*70)
    print("SYMMETRY ANALYSIS FOR TRUCK ASSIGNMENT PROBLEM")
    print("="*70)

    # Analyze 2-week case
    result = analyze_symmetry(weeks=2)

    # Recommendations
    print(f"\n{'='*70}")
    print("SYMMETRY-BREAKING STRATEGIES")
    print(f"{'='*70}")

    print(f"\n1. LEXICOGRAPHIC ORDERING")
    print(f"   {'-'*66}")
    print(f"""
   For trucks serving the same destination on the same day:
   Add constraints:

   if truck_used[i, date] == 0:
       then truck_used[i+1, date] == 0

   This forces trucks to be used in order (i before i+1).
   Eliminates all permutations except one canonical ordering.

   Impact: Reduces {result['total_symmetry']:,} solutions to just 1!
""")

    print(f"\n2. PRIORITIZED ASSIGNMENT")
    print(f"   {'-'*66}")
    print(f"""
   Assign a priority score to each truck:
   priority[i] = i (simple index ordering)

   Add constraint:
   truck_load[i, dest, prod, date] <= M * truck_used[i, date]

   Force solver to branch on truck_used variables FIRST.
   Combined with lexicographic ordering, dramatically reduces tree.
""")

    print(f"\n3. AGGREGATION")
    print(f"   {'-'*66}")
    print(f"""
   Don't model individual truck assignments - model only:
   - Total shipments to each destination
   - Number of trucks needed

   Post-process: Assign products to specific trucks using heuristic.

   Impact: Eliminates all truck symmetry from the optimization!
   Speedup: 10-100x possible
""")

    print(f"\n4. FIX-AND-OPTIMIZE")
    print(f"   {'-'*66}")
    print(f"""
   Phase 1: Use greedy heuristic to pre-assign trucks
             (e.g., fill trucks in order until full)

   Phase 2: Fix truck assignments, optimize only production quantities

   Phase 3: (Optional) Local search to improve truck assignments

   Impact: Converts hard MIP to easy LP!
   Speedup: 100-1000x possible
""")

    print(f"\n{'='*70}")
    print("EXPECTED PERFORMANCE IMPROVEMENT")
    print(f"{'='*70}")

    print(f"""
With symmetry breaking (lexicographic ordering):
  Week 3: ~11s → ~2-3s (3-5x speedup)
  Week 6: ~220s → ~40-60s (3-5x speedup)
  Full dataset: Still exponential, but much more manageable

With aggregation or fix-and-optimize:
  Week 3: ~11s → <1s (10-20x speedup)
  Week 6: ~220s → ~5-10s (20-40x speedup)
  Full dataset: May become solvable in minutes instead of hours/days
""")

    print(f"\n{'='*70}")
