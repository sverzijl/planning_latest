"""Phase 1 Model Structure Diagnostic.

CRITICAL HYPOTHESIS TO TEST:
- Documentation says Phase 1 should have NO pallet tracking
- Code at line 4345 uses SAME cost_structure for Phase 1 and Phase 2
- If cost_structure has pallet costs, Phase 1 WILL have pallet tracking
- This would explain the timeout (too many integer variables in Phase 1)

This script:
1. Builds ONLY the Phase 1 model (no solve)
2. Analyzes model structure (variable counts, types)
3. Checks if pallet_count variables exist
4. Compares against expected structure

EVIDENCE GATHERING - NO FIXES
"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from pyomo.environ import Var, Constraint, Binary, value as pyo_value, ConstraintList


def print_section(title: str):
    """Print formatted section header."""
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}")


def analyze_variable_structure(pyomo_model, name: str):
    """Detailed analysis of model variable structure."""
    print_section(f"{name} - Variable Analysis")

    # Count by type
    binary_vars = []
    integer_vars = []
    continuous_vars = []

    for v in pyomo_model.component_data_objects(Var, active=True):
        if v.is_binary():
            binary_vars.append(str(v))
        elif v.is_integer():
            integer_vars.append(str(v))
        else:
            continuous_vars.append(str(v))

    print(f"\nVariable Counts:")
    print(f"  Binary:     {len(binary_vars):,}")
    print(f"  Integer:    {len(integer_vars):,}")
    print(f"  Continuous: {len(continuous_vars):,}")
    print(f"  TOTAL:      {len(binary_vars) + len(integer_vars) + len(continuous_vars):,}")

    # Check specific variable types
    print(f"\nVariable Components:")
    for comp in pyomo_model.component_objects(Var, active=True):
        comp_size = len([1 for _ in comp])
        var_type = "Binary" if any(v.is_binary() for v in comp.values()) else \
                   "Integer" if any(v.is_integer() for v in comp.values()) else "Continuous"
        print(f"  {comp.name:30s} {var_type:12s} {comp_size:8,} vars")

    # Sample binary variables
    print(f"\nSample Binary Variables (first 5):")
    for var_name in binary_vars[:5]:
        print(f"  {var_name}")

    # Sample integer variables
    if integer_vars:
        print(f"\nSample Integer Variables (first 5):")
        for var_name in integer_vars[:5]:
            print(f"  {var_name}")
    else:
        print(f"\nNo integer variables found.")

    return {
        'num_binary': len(binary_vars),
        'num_integer': len(integer_vars),
        'num_continuous': len(continuous_vars),
    }


def main():
    print_section("PHASE 1 MODEL STRUCTURE DIAGNOSTIC")
    print("\nHYPOTHESIS:")
    print("  Phase 1 documentation says 'no pallet tracking'")
    print("  BUT Phase 1 code uses SAME cost_structure as Phase 2")
    print("  IF cost_structure has pallet costs configured,")
    print("  THEN Phase 1 WILL have pallet_count integer variables")
    print("  WHICH would make Phase 1 slow and defeat the purpose")

    # Load data using MultiFileParser (matches UI workflow)
    print_section("Loading Data")

    parser = MultiFileParser(
        forecast_file="data/examples/Gluten Free Forecast - Latest.xlsm",
        network_file="data/examples/Network_Config.xlsx",
        inventory_file="data/examples/inventory.XLSX",
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Get manufacturing site
    from src.models.manufacturing import ManufacturingSite
    from src.models.location import LocationType
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    if not manufacturing_locations:
        raise ValueError("No manufacturing site found")

    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id,
        name=manuf_loc.name,
        storage_mode=manuf_loc.storage_mode,
        production_rate=manuf_loc.production_rate if hasattr(manuf_loc, 'production_rate') and manuf_loc.production_rate else 1400.0,
        daily_startup_hours=0.5,
        daily_shutdown_hours=0.25,
        default_changeover_hours=0.5,
        production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    # Convert to unified format
    from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    routes = converter.convert_routes(routes)
    truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    # Parse initial inventory
    inventory_snapshot = parser.parse_inventory(snapshot_date=None)
    initial_inventory = inventory_snapshot.to_optimization_dict() if inventory_snapshot else None
    inventory_date = inventory_snapshot.snapshot_date if inventory_snapshot else None

    print(f"  Nodes: {len(nodes)}")
    print(f"  Routes: {len(routes)}")
    print(f"  Forecast entries: {len(forecast.entries)}")

    # Analyze cost structure
    print_section("Cost Structure Configuration")

    pallet_fixed_frozen = getattr(cost_structure, 'storage_cost_fixed_per_pallet_frozen', 0.0)
    pallet_fixed_ambient = getattr(cost_structure, 'storage_cost_fixed_per_pallet_ambient', 0.0)
    pallet_daily_frozen = getattr(cost_structure, 'storage_cost_per_pallet_day_frozen', 0.0)
    pallet_daily_ambient = getattr(cost_structure, 'storage_cost_per_pallet_day_ambient', 0.0)
    unit_frozen = getattr(cost_structure, 'storage_cost_frozen_per_unit_day', 0.0)
    unit_ambient = getattr(cost_structure, 'storage_cost_ambient_per_unit_day', 0.0)

    print(f"\nPallet Costs:")
    print(f"  Fixed frozen:  ${pallet_fixed_frozen:.2f} per pallet")
    print(f"  Fixed ambient: ${pallet_fixed_ambient:.2f} per pallet")
    print(f"  Daily frozen:  ${pallet_daily_frozen:.4f} per pallet-day")
    print(f"  Daily ambient: ${pallet_daily_ambient:.4f} per pallet-day")

    print(f"\nUnit Costs:")
    print(f"  Frozen:  ${unit_frozen:.4f} per unit-day")
    print(f"  Ambient: ${unit_ambient:.4f} per unit-day")

    has_pallet_costs = any([pallet_fixed_frozen, pallet_fixed_ambient,
                            pallet_daily_frozen, pallet_daily_ambient])
    has_unit_costs = any([unit_frozen, unit_ambient])

    print(f"\nCost Model Active:")
    print(f"  Pallet-based: {'YES' if has_pallet_costs else 'NO'}")
    print(f"  Unit-based:   {'YES' if has_unit_costs else 'NO'}")

    if has_pallet_costs:
        print(f"\n⚠️  CRITICAL: Pallet costs are configured!")
        print(f"   This means Phase 1 WILL have pallet_count integer variables")
        print(f"   according to UnifiedNodeModel logic (same cost_structure used)")

    # Build Phase 1 model structure
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=6*7 - 1)  # 6 weeks

    print_section(f"Building Phase 1 Model (NO SOLVE)")
    print(f"\nHorizon: {start_date} to {end_date} ({(end_date - start_date).days + 1} days)")

    # Replicate Phase 1 model building from solve_weekly_pattern_warmstart
    print("\nCreating UnifiedNodeModel with SAME parameters as Phase 1...")

    model_phase1_obj = UnifiedNodeModel(
        nodes=nodes,
        routes=routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,  # SAME as Phase 2 - this is the issue!
        start_date=start_date,
        end_date=end_date,
        truck_schedules=truck_schedules,
        initial_inventory=initial_inventory,
        inventory_snapshot_date=inventory_date,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
        force_all_skus_daily=False,
    )

    print("Building Pyomo model...")
    pyomo_model_phase1 = model_phase1_obj.build_model()

    # NOW add weekly pattern variables (as done in solve_weekly_pattern_warmstart)
    products = sorted(set(e.product_id for e in forecast.entries))
    manufacturing_nodes = [n.id for n in nodes if n.capabilities.can_manufacture]

    print(f"\nAdding weekly pattern variables (5 products × 5 weekdays = 25 binary vars)...")
    from pyomo.environ import Var, Binary

    pattern_index = [(prod, wd) for prod in products for wd in range(5)]
    pyomo_model_phase1.product_weekday_pattern = Var(
        pattern_index,
        within=Binary,
        doc="Weekly production pattern"
    )

    # Add linking constraints
    dates_range = []
    current = start_date
    while current <= end_date:
        dates_range.append(current)
        current += timedelta(days=1)

    weekday_dates_lists = {i: [] for i in range(5)}
    for date_val in dates_range:
        weekday = date_val.weekday()
        labor_day = labor_calendar.get_labor_day(date_val)
        if weekday < 5 and labor_day and labor_day.is_fixed_day:
            weekday_dates_lists[weekday].append(date_val)

    pyomo_model_phase1.weekly_pattern_linking = ConstraintList()

    num_linked = 0
    for node_id in manufacturing_nodes:
        for date_val in dates_range:
            weekday = date_val.weekday()
            if weekday < 5 and any(date_val in weekday_dates_lists[weekday] for weekday in range(5)):
                for product in products:
                    pyomo_model_phase1.weekly_pattern_linking.add(
                        pyomo_model_phase1.product_produced[node_id, product, date_val] ==
                        pyomo_model_phase1.product_weekday_pattern[product, weekday]
                    )
                    num_linked += 1

    print(f"  Added {num_linked} linking constraints")

    # Deactivate conflicting constraints
    num_deactivated = 0
    if hasattr(pyomo_model_phase1, 'num_products_counting_con'):
        for node_id in manufacturing_nodes:
            for date_val in dates_range:
                weekday = date_val.weekday()
                if weekday < 5 and any(date_val in weekday_dates_lists[weekday] for weekday in range(5)):
                    if (node_id, date_val) in pyomo_model_phase1.num_products_counting_con:
                        pyomo_model_phase1.num_products_counting_con[node_id, date_val].deactivate()
                        num_deactivated += 1

    print(f"  Deactivated {num_deactivated} conflicting constraints")

    # Analyze the built model
    stats = analyze_variable_structure(pyomo_model_phase1, "PHASE 1 MODEL")

    # Check for pallet_count
    print_section("CRITICAL CHECK: Pallet Count Variables")

    has_pallet_count = hasattr(pyomo_model_phase1, 'pallet_count')
    print(f"\nDoes Phase 1 model have pallet_count? {has_pallet_count}")

    if has_pallet_count:
        pallet_count_size = len([1 for _ in pyomo_model_phase1.pallet_count])
        print(f"Pallet count variable size: {pallet_count_size:,}")
        print(f"\n❌ HYPOTHESIS CONFIRMED!")
        print(f"   Phase 1 has {pallet_count_size:,} pallet_count integer variables")
        print(f"   This is the ROOT CAUSE of the slow solve")
        print(f"\n   Expected Phase 1 binary vars: ~110")
        print(f"   Actual Phase 1 binary vars: {stats['num_binary']:,}")
        print(f"   Actual Phase 1 integer vars: {stats['num_integer']:,}")
        print(f"\n   Phase 1 is NOT simplified - it has SAME complexity as Phase 2!")

        # Sample pallet variables
        print(f"\nSample pallet_count variables:")
        count = 0
        for key in pyomo_model_phase1.pallet_count:
            if count < 5:
                print(f"  {key}")
                count += 1
            else:
                break

    else:
        print(f"\n✅ Phase 1 does NOT have pallet_count variables")
        print(f"   This would be correct (unit-based model)")
        print(f"   Binary vars: {stats['num_binary']:,} (expect ~110)")
        print(f"   Integer vars: {stats['num_integer']:,} (expect 0)")

    # Expected vs Actual
    print_section("Expected vs Actual Structure")

    print(f"\nEXPECTED Phase 1 (per documentation):")
    print(f"  Binary variables:  ~110 (25 pattern + ~85 weekend)")
    print(f"  Integer variables: 0 (NO pallet tracking)")
    print(f"  Purpose: Fast warmup solve (~20-40s)")

    print(f"\nACTUAL Phase 1:")
    print(f"  Binary variables:  {stats['num_binary']:,}")
    print(f"  Integer variables: {stats['num_integer']:,}")
    print(f"  Has pallet_count:  {has_pallet_count}")

    if stats['num_integer'] > 0:
        print(f"\n❌ MISMATCH DETECTED!")
        print(f"   Phase 1 has {stats['num_integer']:,} integer variables")
        print(f"   This explains the timeout!")
    else:
        print(f"\n✅ Phase 1 structure matches documentation")

    print_section("ROOT CAUSE ANALYSIS")

    if has_pallet_costs and has_pallet_count:
        print("\n🎯 ROOT CAUSE IDENTIFIED:")
        print("\n1. Cost structure has pallet-based costs configured")
        print("2. solve_weekly_pattern_warmstart passes SAME cost_structure to Phase 1 and Phase 2")
        print("3. UnifiedNodeModel creates pallet_count variables when pallet costs exist")
        print("4. Phase 1 gets pallet_count integer variables it shouldn't have")
        print("5. Phase 1 solve becomes as complex as Phase 2 (defeats warmstart purpose)")
        print("6. Total solve time exceeds timeout")
        print("\nSOLUTION:")
        print("  Phase 1 should use MODIFIED cost_structure with:")
        print("    - Pallet costs = 0")
        print("    - Equivalent unit-based costs instead")
        print("  This will eliminate pallet_count variables from Phase 1")
        print("  Making Phase 1 fast (~20-40s as designed)")

    elif not has_pallet_costs:
        print("\n✅ Cost structure is unit-based (no pallet costs)")
        print("   Phase 1 should be fast")
        print("   Timeout must be caused by something else")
        print("\nNEXT INVESTIGATION:")
        print("  - Check actual solve times")
        print("  - Review solver logs")
        print("  - Check for other complexity sources")

    else:
        print("\n❓ UNEXPECTED STATE:")
        print(f"   Has pallet costs: {has_pallet_costs}")
        print(f"   Has pallet_count: {has_pallet_count}")
        print("   This suggests UnifiedNodeModel logic may have changed")

    print("\n" + "="*80)


if __name__ == "__main__":
    main()
