"""
SYSTEMATIC DEBUGGING: Progressive Phase Transitions

This diagnostic script instruments the progressive optimizer to gather
evidence about what's happening between phases.

EVIDENCE TO COLLECT:
1. Week 2 production values across all phases (should be FREE in phases 2-3)
2. Bounds applied to variables (are they correct?)
3. Whether APPSI is actually re-solving (objective changes?)
4. Solution extraction values (are we getting current or stale values?)

NO FIXES - ONLY EVIDENCE GATHERING
"""

from datetime import date, timedelta
from pathlib import Path
from collections import defaultdict

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.progressive_configs import BALANCED_4_PHASE
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from tests.conftest import create_test_products

import pyomo.environ as pyo


def load_data():
    """Load 12-week data."""
    forecast_file = Path('data/examples/Gluten Free Forecast - Latest.xlsm')
    network_file = Path('data/examples/Network_Config.xlsx')

    parser = MultiFileParser(forecast_file=forecast_file, network_file=network_file)
    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
        production_rate=getattr(manuf_loc, 'production_rate', 1400.0),
        daily_startup_hours=0.5, daily_shutdown_hours=0.25, default_changeover_hours=0.5,
        production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    start_date = min(e.forecast_date for e in forecast.entries)
    end_date = start_date + timedelta(days=83)

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    return {
        'nodes': nodes, 'routes': unified_routes, 'forecast': forecast,
        'labor_calendar': labor_calendar, 'cost_structure': cost_structure,
        'truck_schedules': unified_truck_schedules, 'products': products,
        'start_date': start_date, 'end_date': end_date,
        'manufacturing_site': manufacturing_site,
    }


def get_week_2_production(model, manuf_node_id):
    """Extract week 2 total production from model."""
    dates_list = sorted(list(model.dates))
    start_date = dates_list[0]

    # Week 2 dates (days 7-13)
    week_2_dates = [start_date + timedelta(days=i) for i in range(7, 14)]

    total_week_2 = 0
    for date_val in week_2_dates:
        if date_val in model.dates:
            for prod in model.products:
                if (manuf_node_id, prod, date_val) in model.production:
                    qty = pyo.value(model.production[manuf_node_id, prod, date_val])
                    total_week_2 += qty

    return total_week_2


def check_variable_bounds(model, manuf_node_id, week_to_check=2):
    """Check what bounds are applied to a specific week's variables."""
    dates_list = sorted(list(model.dates))
    start_date = dates_list[0]

    # Get week dates
    week_start = start_date + timedelta(days=(week_to_check - 1) * 7)
    week_dates = [week_start + timedelta(days=i) for i in range(7)]

    bounds_info = {}

    if hasattr(model, 'mix_count'):
        for date_val in week_dates:
            if date_val in model.dates:
                for prod in model.products:
                    if (manuf_node_id, prod, date_val) in model.mix_count:
                        var = model.mix_count[manuf_node_id, prod, date_val]

                        lb = var.lb if var.has_lb() else 0
                        ub = var.ub if var.has_ub() else float('inf')
                        current_val = pyo.value(var) if not var.stale else None

                        bounds_info[f"{date_val}_{prod}"] = {
                            'lb': lb,
                            'ub': ub,
                            'value': current_val,
                            'is_fixed': var.is_fixed(),
                        }

    return bounds_info


def main():
    """Run instrumented progressive solve with detailed logging."""

    print("="*80)
    print("SYSTEMATIC DEBUGGING: Progressive Phase Transitions")
    print("="*80)

    # Load data
    data = load_data()

    # Build model
    model_obj = UnifiedNodeModel(
        nodes=data['nodes'],
        routes=data['routes'],
        forecast=data['forecast'],
        labor_calendar=data['labor_calendar'],
        cost_structure=data['cost_structure'],
        products=data['products'],
        start_date=data['start_date'],
        end_date=data['end_date'],
        truck_schedules=data['truck_schedules'],
        use_batch_tracking=True,
        allow_shortages=True,
    )

    pyomo_model = model_obj.build_model()
    manuf_node_id = list(model_obj.manufacturing_nodes)[0]

    # Create APPSI solver
    solver = pyo.SolverFactory('appsi_highs')
    solver.set_instance(pyomo_model)

    print("\nModel built. Starting instrumented solve...")

    # PHASE 1
    print("\n" + "="*80)
    print("PHASE 1: Strategic (12 weeks, 40% gap)")
    print("="*80)

    solver.options['mip_rel_gap'] = 0.40
    solver.options['time_limit'] = 180

    result1 = solver.solve(pyomo_model, load_solutions=False)
    solver.load_vars()

    obj1 = pyo.value(pyomo_model.obj)
    week2_phase1 = get_week_2_production(pyomo_model, manuf_node_id)

    print(f"\nPhase 1 Results:")
    print(f"  Objective: ${obj1:,.2f}")
    print(f"  Status: {result1.solver.termination_condition}")
    print(f"  Week 2 production: {week2_phase1:,.0f} units")

    # EVIDENCE: Check week 2 bounds BEFORE Phase 2
    print(f"\n📊 EVIDENCE: Week 2 bounds BEFORE Phase 2:")
    week2_bounds_before = check_variable_bounds(pyomo_model, manuf_node_id, week_to_check=2)
    if week2_bounds_before:
        sample = list(week2_bounds_before.items())[0]
        print(f"  Sample variable: {sample[0]}")
        print(f"    Lower bound: {sample[1]['lb']}")
        print(f"    Upper bound: {sample[1]['ub']}")
        print(f"    Is fixed: {sample[1]['is_fixed']}")

    # Apply bounds for Phase 2 (bound weeks >8)
    print(f"\n📊 EVIDENCE: Applying bounds for Phase 2 (should bound weeks 9-12 only)...")

    dates_list = sorted(list(pyomo_model.dates))
    start_date = dates_list[0]

    bounded_count = 0
    week2_bounded_count = 0

    if hasattr(pyomo_model, 'mix_count'):
        for var in pyomo_model.mix_count.values():
            index = var.index()
            date = index[2]

            # Calculate week
            week_num = (date - start_date).days // 7 + 1

            if week_num > 8:  # Phase 2: fix_beyond_week = 8
                current_val = pyo.value(var)
                lb = max(0, int(current_val * 0.9))  # ±10% tolerance
                ub = int(current_val * 1.1) + 1

                var.setlb(lb)
                var.setub(ub)
                bounded_count += 1

            elif week_num == 2:
                # Track if week 2 gets bounded (IT SHOULDN'T!)
                if var.has_lb() or var.has_ub():
                    week2_bounded_count += 1

    print(f"  Bounded {bounded_count} variables in weeks 9-12")
    print(f"  Week 2 variables bounded: {week2_bounded_count} (SHOULD BE ZERO!)")

    # EVIDENCE: Check week 2 bounds AFTER applying bounds
    print(f"\n📊 EVIDENCE: Week 2 bounds AFTER applying bounds for Phase 2:")
    week2_bounds_after = check_variable_bounds(pyomo_model, manuf_node_id, week_to_check=2)
    if week2_bounds_after:
        sample = list(week2_bounds_after.items())[0]
        print(f"  Sample variable: {sample[0]}")
        print(f"    Lower bound: {sample[1]['lb']}")
        print(f"    Upper bound: {sample[1]['ub']}")
        print(f"    Is fixed: {sample[1]['is_fixed']}")

        if sample[1]['lb'] > 0 or sample[1]['ub'] < float('inf'):
            print(f"  ❌ BUG FOUND: Week 2 has bounds! (should be unbounded)")
        else:
            print(f"  ✅ Week 2 is unbounded (correct)")

    # PHASE 2
    print("\n" + "="*80)
    print("PHASE 2: Tactical (8 weeks, 15% gap)")
    print("="*80)

    solver.options['mip_rel_gap'] = 0.15
    solver.options['time_limit'] = 120

    result2 = solver.solve(pyomo_model, load_solutions=False)
    solver.load_vars()

    obj2 = pyo.value(pyomo_model.obj)
    week2_phase2 = get_week_2_production(pyomo_model, manuf_node_id)

    print(f"\nPhase 2 Results:")
    print(f"  Objective: ${obj2:,.2f}")
    print(f"  Status: {result2.solver.termination_condition}")
    print(f"  Week 2 production: {week2_phase2:,.0f} units")

    # CRITICAL COMPARISON
    print(f"\n📊 CRITICAL EVIDENCE: Objective comparison:")
    print(f"  Phase 1: ${obj1:,.2f}")
    print(f"  Phase 2: ${obj2:,.2f}")
    print(f"  Difference: ${obj2 - obj1:,.2f}")

    if abs(obj2 - obj1) < 1.0:
        print(f"  ❌ IDENTICAL OBJECTIVES - Solver not improving!")
    else:
        print(f"  ✅ Objective changed")

    print(f"\n📊 CRITICAL EVIDENCE: Week 2 production:")
    print(f"  Phase 1: {week2_phase1:,.0f} units")
    print(f"  Phase 2: {week2_phase2:,.0f} units")
    print(f"  Change: {week2_phase2 - week2_phase1:+,.0f} units")

    if abs(week2_phase2 - week2_phase1) < 1.0:
        print(f"  ❌ Week 2 UNCHANGED - Even though it should be FREE!")
    else:
        print(f"  ✅ Week 2 changed (can optimize)")

    # PHASE 3 (bound weeks >4)
    print("\n" + "="*80)
    print("Applying bounds for Phase 3 (should bound weeks 5-12 only)...")
    print("="*80)

    bounded_phase3 = 0
    week2_bounded_phase3 = 0

    if hasattr(pyomo_model, 'mix_count'):
        for var in pyomo_model.mix_count.values():
            index = var.index()
            date = index[2]
            week_num = (date - start_date).days // 7 + 1

            if week_num > 4:  # Phase 3: fix_beyond_week = 4
                current_val = pyo.value(var)
                lb = max(0, int(current_val * 0.95))  # ±5% tolerance
                ub = int(current_val * 1.05) + 1

                var.setlb(lb)
                var.setub(ub)
                bounded_phase3 += 1

            elif week_num == 2:
                if var.has_lb() or var.has_ub():
                    week2_bounded_phase3 += 1

    print(f"  Bounded {bounded_phase3} variables in weeks 5-12")
    print(f"  Week 2 variables bounded: {week2_bounded_phase3} (SHOULD BE ZERO!)")

    # PHASE 3
    print("\n" + "="*80)
    print("PHASE 3: Operational (4 weeks, 3% gap)")
    print("="*80)

    solver.options['mip_rel_gap'] = 0.03
    solver.options['time_limit'] = 120

    result3 = solver.solve(pyomo_model, load_solutions=False)
    solver.load_vars()

    obj3 = pyo.value(pyomo_model.obj)
    week2_phase3 = get_week_2_production(pyomo_model, manuf_node_id)

    print(f"\nPhase 3 Results:")
    print(f"  Objective: ${obj3:,.2f}")
    print(f"  Status: {result3.solver.termination_condition}")
    print(f"  Week 2 production: {week2_phase3:,.0f} units")

    print(f"\n📊 CRITICAL EVIDENCE: Week 2 across phases:")
    print(f"  Phase 1: {week2_phase1:,.0f} units (all weeks free)")
    print(f"  Phase 2: {week2_phase2:,.0f} units (weeks 1-8 free, week 2 should optimize)")
    print(f"  Phase 3: {week2_phase3:,.0f} units (weeks 1-4 free, week 2 should optimize)")

    # DETAILED VARIABLE INSPECTION
    print("\n" + "="*80)
    print("DETAILED VARIABLE INSPECTION: Week 2, Product 1, First Date")
    print("="*80)

    week2_first_date = start_date + timedelta(days=7)  # First day of week 2
    first_product = sorted(list(pyomo_model.products))[0]

    if hasattr(pyomo_model, 'mix_count'):
        if (manuf_node_id, first_product, week2_first_date) in pyomo_model.mix_count:
            var = pyomo_model.mix_count[manuf_node_id, first_product, week2_first_date]

            print(f"\nVariable: mix_count[{manuf_node_id}, {first_product}, {week2_first_date}]")
            print(f"  Current value: {pyo.value(var)}")
            print(f"  Lower bound: {var.lb if var.has_lb() else 'None'}")
            print(f"  Upper bound: {var.ub if var.has_ub() else 'None'}")
            print(f"  Is fixed: {var.is_fixed()}")
            print(f"  Domain: {var.domain}")

            if var.has_lb() and var.lb > 0:
                print(f"\n  ❌ BUG: Week 2 variable has lower bound > 0!")
                print(f"     This forces production even though week should be free!")

            if var.is_fixed():
                print(f"\n  ❌ BUG: Week 2 variable is FIXED!")
                print(f"     This locks value and prevents optimization!")

    # Check Sunday (week 1, day 7)
    print("\n" + "="*80)
    print("DETAILED VARIABLE INSPECTION: Sunday (Week 1, Day 7)")
    print("="*80)

    sunday_date = start_date + timedelta(days=6)  # Day 7 of week 1 (Sunday)

    if hasattr(pyomo_model, 'mix_count'):
        if (manuf_node_id, first_product, sunday_date) in pyomo_model.mix_count:
            var = pyomo_model.mix_count[manuf_node_id, first_product, sunday_date]

            print(f"\nVariable: mix_count[{manuf_node_id}, {first_product}, {sunday_date}]")
            print(f"  Current value: {pyo.value(var)}")
            print(f"  Lower bound: {var.lb if var.has_lb() else 'None'}")
            print(f"  Upper bound: {var.ub if var.has_ub() else 'None'}")
            print(f"  Is fixed: {var.is_fixed()}")

    # Check labor hours on Sunday
    if hasattr(pyomo_model, 'labor_hours_used'):
        if (manuf_node_id, sunday_date) in pyomo_model.labor_hours_used:
            hours_var = pyomo_model.labor_hours_used[manuf_node_id, sunday_date]
            hours_val = pyo.value(hours_var)

            print(f"\nLabor hours on Sunday:")
            print(f"  Value: {hours_val:.1f} hours")

            if hours_val > 20:
                print(f"  ❌ EXCESSIVE HOURS: {hours_val:.1f}h (capacity should be ~14h max)")

    # SUMMARY
    print("\n" + "="*80)
    print("DIAGNOSTIC SUMMARY")
    print("="*80)

    print(f"\n1. Objective progression:")
    print(f"   Phase 1 → Phase 2: ${obj1:,.2f} → ${obj2:,.2f}")
    print(f"   Phase 2 → Phase 3: ${obj2:,.2f} → ${obj3:,.2f}")

    print(f"\n2. Week 2 production across phases:")
    print(f"   Phase 1: {week2_phase1:,.0f} units")
    print(f"   Phase 2: {week2_phase2:,.0f} units (weeks 1-8 FREE)")
    print(f"   Phase 3: {week2_phase3:,.0f} units (weeks 1-4 FREE)")

    print(f"\n3. Key findings:")
    if abs(obj2 - obj1) < 1.0 and abs(obj3 - obj2) < 1.0:
        print(f"   ❌ Objectives unchanged across phases 1-3")
        print(f"      → Either APPSI not re-solving OR bounds too restrictive")

    if week2_phase1 == week2_phase2 == week2_phase3 and week2_phase1 == 0:
        print(f"   ❌ Week 2 stays at zero despite being FREE")
        print(f"      → Investigate why solver doesn't improve week 2")

    # Recommendations
    print(f"\n" + "="*80)
    print("NEXT INVESTIGATION STEPS:")
    print("="*80)

    if week2_bounded_count > 0 or week2_bounded_phase3 > 0:
        print(f"1. ❌ BUG IN BOUNDING LOGIC: Week 2 is being bounded when it shouldn't be")
        print(f"   → Check week number calculation")
        print(f"   → Verify fix_beyond_week logic")

    elif abs(obj2 - obj1) < 1.0:
        print(f"1. ⚠️  APPSI might not be re-solving properly:")
        print(f"   → Check if APPSI needs update_config() call after bound changes")
        print(f"   → Verify load_vars() is loading new solution")
        print(f"   → Try with standard HiGHS (not APPSI) to compare")

    else:
        print(f"1. ✅ Bounding appears correct, investigate other coupling")


if __name__ == '__main__':
    main()
