#!/usr/bin/env python3
"""Test Approach 2: Direct highspy API with setSolution

This is the ONLY remaining approach that research confirms should work:
- Use HiGHS's native setSolution() method to provide MIP start
- Bypass Pyomo's warmstart interfaces entirely
- Use MPS format to transfer models between Pyomo and highspy

Expected: setSolution should properly set incumbent for Phase 2 solve
"""

import sys
from pathlib import Path
from datetime import date, timedelta
import time
import tempfile
import os

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType

import pyomo.environ as pyo
from pyomo.contrib import appsi

try:
    import highspy
    HIGHSPY_AVAILABLE = True
except ImportError:
    HIGHSPY_AVAILABLE = False


def build_pattern_model(model_obj, products, weekday_dates_lists, manufacturing_nodes_list):
    """Build 4-week pattern model."""
    model = model_obj.build_model()

    pattern_index = [(prod, wd) for prod in products for wd in range(5)]
    model.product_weekday_pattern = pyo.Var(pattern_index, within=pyo.Binary)

    model.weekly_pattern_linking = pyo.ConstraintList()
    for node_id in manufacturing_nodes_list:
        for product in products:
            for weekday_idx in range(5):
                for date_val in weekday_dates_lists[weekday_idx]:
                    if (node_id, product, date_val) in model.product_produced:
                        model.weekly_pattern_linking.add(
                            model.product_produced[node_id, product, date_val] ==
                            model.product_weekday_pattern[product, weekday_idx]
                        )

    if hasattr(model, 'num_products_counting_con'):
        for idx in model.num_products_counting_con:
            model.num_products_counting_con[idx].deactivate()

    return model


def extract_solution_vector(pyomo_model, mps_file_path):
    """Extract solution values in MPS column order.

    Read MPS file to get variable names in correct order,
    then extract Pyomo values in that order.
    """
    # Parse MPS COLUMNS section to get variable order
    print("\nParsing MPS file to determine variable order...")

    var_names_ordered = []
    with open(mps_file_path, 'r') as f:
        in_columns = False
        for line in f:
            if line.strip() == 'COLUMNS':
                in_columns = True
                continue
            elif line.strip() in ['RHS', 'RANGES', 'BOUNDS', 'ENDATA']:
                in_columns = False

            if in_columns and line.strip():
                # COLUMNS format: varname row1 coef1 [row2 coef2]
                parts = line.strip().split()
                if parts and not parts[0].startswith('MARKER'):
                    var_name = parts[0]
                    if var_name not in var_names_ordered:
                        var_names_ordered.append(var_name)

    print(f"  Found {len(var_names_ordered)} variables in MPS file")

    # Build mapping from MPS name to Pyomo variable
    pyomo_var_map = {}
    for var in pyomo_model.component_data_objects(pyo.Var, active=True):
        pyomo_var_map[var.name] = var

    print(f"  Found {len(pyomo_var_map)} variables in Pyomo model")

    # Extract values in MPS order
    solution_vector = []
    missing_count = 0

    for mps_var_name in var_names_ordered:
        if mps_var_name in pyomo_var_map:
            val = pyo.value(pyomo_var_map[mps_var_name])
            if val is None:
                val = 0.0  # Default uninitialized to 0
            solution_vector.append(val)
        else:
            print(f"    Warning: MPS variable {mps_var_name} not found in Pyomo model")
            solution_vector.append(0.0)
            missing_count += 1

    if missing_count > 0:
        print(f"  ⚠️  {missing_count} variables not matched")
    else:
        print(f"  ✓  All {len(solution_vector)} variables matched")

    return solution_vector


def calculate_num_products_produced(model, products, manufacturing_nodes_list, dates_range):
    """Calculate and set num_products_produced from product_produced."""
    if not hasattr(model, 'num_products_produced'):
        return 0

    count = 0
    for node_id in manufacturing_nodes_list:
        for date_val in dates_range:
            if (node_id, date_val) in model.num_products_produced:
                num_products = sum(
                    1 for product in products
                    if (node_id, product, date_val) in model.product_produced
                    and pyo.value(model.product_produced[node_id, product, date_val]) > 0.5
                )
                model.num_products_produced[node_id, date_val].set_value(num_products)
                count += 1

    return count


def main():
    print("="*80)
    print("APPROACH 2: Direct highspy API with setSolution")
    print("="*80)
    print("\nStrategy: Use HiGHS native setSolution() for MIP start")
    print("Expected: This should properly set incumbent\n")

    if not HIGHSPY_AVAILABLE:
        print("❌ highspy not installed!")
        print("   Install with: pip install highspy")
        return 1

    print("✓  highspy available")

    # Load data
    print("\n" + "="*80)
    print("LOADING DATA")
    print("="*80)

    parser = MultiFileParser(
        forecast_file="data/examples/Gluten Free Forecast - Latest.xlsm",
        network_file="data/examples/Network_Config.xlsx",
        inventory_file="data/examples/inventory.XLSX",
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure_base = parser.parse_all()

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
        default_changeover_hours=0.5, production_cost_per_unit=cost_structure_base.production_cost_per_unit,
    )

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    inventory_snapshot = parser.parse_inventory(snapshot_date=None)
    initial_inventory = inventory_snapshot.to_optimization_dict() if inventory_snapshot else None
    inventory_date = inventory_snapshot.snapshot_date if inventory_snapshot else None

    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=4*7 - 1)

    products = sorted(set(e.product_id for e in forecast.entries))
    manufacturing_nodes_list = [n.id for n in nodes if n.capabilities.can_manufacture]

    weekday_dates_lists = {i: [] for i in range(5)}
    dates_range = []
    current = start_date
    while current <= end_date:
        dates_range.append(current)
        if current.weekday() < 5:
            labor_day = labor_calendar.get_labor_day(current)
            if labor_day and labor_day.is_fixed_day:
                weekday_dates_lists[current.weekday()].append(current)
        current += timedelta(days=1)

    cost_structure = cost_structure_base.model_copy()
    cost_structure.freshness_incentive_weight = 0.05

    # PHASE 1: Solve pattern in Pyomo
    print("\n" + "="*80)
    print("PHASE 1: SOLVE PATTERN MODEL IN PYOMO")
    print("="*80)

    model1_obj = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=initial_inventory,
        inventory_snapshot_date=inventory_date,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
        force_all_skus_daily=False,
    )

    model1 = model1_obj.build_model()
    pattern_model = build_pattern_model(model1_obj, products, weekday_dates_lists, manufacturing_nodes_list)

    solver_pyomo = appsi.solvers.Highs()
    solver_pyomo.config.time_limit = 120
    solver_pyomo.config.mip_gap = 0.03
    solver_pyomo.config.stream_solver = False

    print("Solving Phase 1 in Pyomo...")
    phase1_start = time.time()
    result1 = solver_pyomo.solve(pattern_model)
    phase1_time = time.time() - phase1_start

    cost1 = pyo.value(pattern_model.obj)
    print(f"\nPhase 1 Results:")
    print(f"  Cost: ${cost1:,.2f}")
    print(f"  Time: {phase1_time:.1f}s")

    # Calculate num_products_produced for complete solution
    num_calc = calculate_num_products_produced(pattern_model, products, manufacturing_nodes_list, dates_range)
    print(f"  Calculated {num_calc} num_products_produced values")

    # PHASE 2: Build flexible model in Pyomo and export to MPS
    print("\n" + "="*80)
    print("PHASE 2: BUILD FLEXIBLE MODEL AND EXPORT TO MPS")
    print("="*80)

    model2_obj = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=initial_inventory,
        inventory_snapshot_date=inventory_date,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
        force_all_skus_daily=False,  # No pattern
    )

    print("\nBuilding flexible model in Pyomo...")
    model2 = model2_obj.build_model()

    # Export to MPS
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mps', delete=False) as f:
        mps_path = f.name

    print(f"Exporting to MPS: {mps_path}")
    model2.write(mps_path)  # Format inferred from .mps extension
    print("  ✓  MPS export complete")

    # EXTRACT SOLUTION VECTOR
    print("\n" + "="*80)
    print("EXTRACTING SOLUTION VECTOR FROM PHASE 1")
    print("="*80)

    solution_vector = extract_solution_vector(pattern_model, mps_path)
    print(f"\nSolution vector created: {len(solution_vector)} values")

    # PHASE 2: Solve in highspy with setSolution
    print("\n" + "="*80)
    print("PHASE 2: SOLVE IN HIGHSPY WITH setSolution")
    print("="*80)

    print("\nLoading MPS file in highspy...")
    h = highspy.Highs()
    h.readModel(mps_path)
    print("  ✓  Model loaded in highspy")

    # Set MIP start using native API
    print("\nSetting MIP start using setSolution()...")
    sol = highspy.HighsSolution()
    sol.col_value = solution_vector

    status = h.setSolution(sol)
    print(f"  setSolution status: {status}")

    # Configure solver
    h.setOptionValue("time_limit", 120.0)
    h.setOptionValue("mip_rel_gap", 0.03)
    h.setOptionValue("output_flag", True)  # Show output
    h.setOptionValue("mip_max_start_nodes", 1000)  # Effort for warmstart completion

    print("\nSolving in highspy with MIP start...")
    print("DIAGNOSTIC: Watch for 'MIP start solution is feasible' message")
    print(f"           Should show incumbent at ${cost1:,.2f} or better\n")

    phase2_start = time.time()
    run_status = h.run()
    phase2_time = time.time() - phase2_start

    # Get results
    info = h.getInfo()
    model_status = h.getModelStatus()

    solution = h.getSolution()
    cost2 = solution.objective_function_value if solution.objective_function_value else float('inf')

    print(f"\nPhase 2 Results (highspy):")
    print(f"  Run status: {run_status}")
    print(f"  Model status: {model_status}")
    print(f"  Cost: ${cost2:,.2f}")
    print(f"  Time: {phase2_time:.1f}s")
    print(f"  MIP gap: {info.mip_gap*100:.2f}%")

    # Cleanup
    try:
        os.unlink(mps_path)
    except:
        pass

    # ANALYSIS
    print("\n" + "="*80)
    print("RESULTS ANALYSIS")
    print("="*80)

    cost_diff = cost2 - cost1
    cost_pct = (cost_diff / cost1) * 100 if cost1 > 0 else 0

    print(f"\nPhase 1 (Pyomo):   ${cost1:,.2f} in {phase1_time:.1f}s")
    print(f"Phase 2 (highspy): ${cost2:,.2f} in {phase2_time:.1f}s")
    print(f"Difference:        ${cost_diff:,.2f} ({cost_pct:+.2f}%)")
    print(f"Total time:        {phase1_time + phase2_time:.1f}s")

    if abs(cost_diff) < 10:
        print(f"\n✅ SUCCESS: Phase 2 matched Phase 1!")
        print(f"   setSolution() WORKS correctly")
        print(f"   Warmstart preserved incumbent")
    elif cost_diff < -100:
        print(f"\n✅ GREAT: Phase 2 improved by ${-cost_diff:,.2f}!")
        print(f"   setSolution() worked and solver found improvement")
    else:
        print(f"\n⚠️  Phase 2 cost changed by ${cost_diff:,.2f}")

        if cost_diff > 0:
            print(f"   If Phase 2 > Phase 1: warmstart may not have worked")
            print(f"   Check solver output for 'MIP start solution is feasible'")
        else:
            print(f"   Small improvement suggests warmstart worked")

    # Check solver output for warmstart acceptance
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)
    print("\nReview solver output above for:")
    print("  1. 'MIP start solution is feasible' message")
    print("  2. Initial primal bound near ${:,.2f}".format(cost1))
    print("  3. If missing → setSolution was rejected or incomplete")

    print(f"\n{'='*80}")
    print("APPROACH 2 TEST COMPLETE")
    print(f"{'='*80}")

    if abs(cost_diff) < 1000 or cost_diff < 0:
        print("\n✓  APPROACH 2 APPEARS TO WORK")
        print("   Recommendation: Use direct highspy API for pattern warmstart")
        return 0
    else:
        print("\n❌ APPROACH 2 FAILED or warmstart rejected")
        print("   Pattern warmstart is not viable with current tools")
        return 1


if __name__ == "__main__":
    exit(main())
