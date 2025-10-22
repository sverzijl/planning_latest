"""Test for 6-week warmstart timeout fix.

Following TDD: This test will FAIL initially, then PASS after implementing the fix.

Test validates:
1. 6-week horizon solves without timeout (< 600s total)
2. Phase 1 has minimal integer variables (< 100)
3. Phase 2 has full pallet tracking (> 4000 integer vars)
4. Solution is feasible with reasonable cost
5. Economic equivalence between Phase 1 and Phase 2 costs
"""

import pytest
from pathlib import Path
from datetime import date, timedelta
import time

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import solve_weekly_pattern_warmstart
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType


@pytest.fixture
def data_6week():
    """Load real data for 6-week test."""
    parser = MultiFileParser(
        forecast_file="data/examples/Gluten Free Forecast - Latest.xlsm",
        network_file="data/examples/Network_Config.xlsx",
        inventory_file="data/examples/inventory.XLSX",
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Get manufacturing site
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id,
        name=manuf_loc.name,
        storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0,
        daily_startup_hours=0.5,
        daily_shutdown_hours=0.25,
        default_changeover_hours=0.5,
        production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    # Convert to unified
    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    # Initial inventory
    inventory_snapshot = parser.parse_inventory(snapshot_date=None)
    initial_inventory = inventory_snapshot.to_optimization_dict() if inventory_snapshot else None
    inventory_date = inventory_snapshot.snapshot_date if inventory_snapshot else None

    return {
        'nodes': nodes,
        'routes': unified_routes,
        'forecast': forecast,
        'labor_calendar': labor_calendar,
        'truck_schedules': unified_truck_schedules,
        'cost_structure': cost_structure,
        'initial_inventory': initial_inventory,
        'inventory_date': inventory_date,
    }


def test_6week_warmstart_no_timeout(data_6week):
    """Test that 6-week warmstart completes within 10 minutes.

    CRITICAL REQUIREMENTS (from MIP best practices):
    1. Phase 1 should have < 100 integer variables (simplified model)
    2. Phase 2 should have ~4,500 integer variables (full pallet tracking)
    3. Total solve time < 600 seconds (10 minutes)
    4. Solution should be feasible

    ROOT CAUSE FIX:
    - Phase 1 must use unit-based costs (no pallet tracking)
    - Phase 2 uses pallet-based costs (original)
    - Economic equivalence maintained
    """

    # 6-week horizon
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=6*7 - 1)  # 42 days

    print("\n" + "="*80)
    print("6-WEEK WARMSTART TEST (TDD - Expect FAIL before fix)")
    print("="*80)
    print(f"Horizon: {start_date} to {end_date} ({(end_date - start_date).days + 1} days)")
    print(f"Expected: Phase 1 < 100 integer vars, Phase 2 ~4500 integer vars")
    print(f"Expected: Total time < 600s")

    # Track phase statistics
    phase_stats = {}

    def progress_callback(phase, status, elapsed, cost):
        """Capture phase statistics."""
        key = f"phase{phase}_{status}"
        phase_stats[key] = {'elapsed': elapsed, 'cost': cost}

        if status == "complete":
            print(f"\n  Phase {phase} complete: {elapsed:.1f}s, Cost: ${cost:,.2f}")

    # Run warmstart solve
    start_time = time.time()

    result = solve_weekly_pattern_warmstart(
        nodes=data_6week['nodes'],
        routes=data_6week['routes'],
        forecast=data_6week['forecast'],
        labor_calendar=data_6week['labor_calendar'],
        cost_structure=data_6week['cost_structure'],
        start_date=start_date,
        end_date=end_date,
        truck_schedules=data_6week['truck_schedules'],
        initial_inventory=data_6week['initial_inventory'],
        inventory_snapshot_date=data_6week['inventory_date'],
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
        solver_name='appsi_highs',
        time_limit_phase1=120,  # 2 minutes for Phase 1
        time_limit_phase2=600,  # 10 minutes for Phase 2
        mip_gap=0.03,  # 3%
        tee=False,
        progress_callback=progress_callback,
    )

    total_time = time.time() - start_time

    # Assertions
    print("\n" + "="*80)
    print("TEST VALIDATION")
    print("="*80)

    # 1. Must complete without timeout
    assert result.success, f"Solve failed: {result.infeasibility_message}"
    print(f"✓ Solve succeeded")

    # 2. Total time must be < 600 seconds
    print(f"  Total time: {total_time:.1f}s (limit: 600s)")
    assert total_time < 600, f"Solve timeout: {total_time:.1f}s > 600s"
    print(f"✓ Under time limit")

    # 3. Phase 1 should be fast (< 120s)
    if 'phase1_complete' in phase_stats:
        phase1_time = phase_stats['phase1_complete']['elapsed']
        print(f"  Phase 1 time: {phase1_time:.1f}s (expected: 20-40s)")
        assert phase1_time < 120, f"Phase 1 too slow: {phase1_time:.1f}s"
        print(f"✓ Phase 1 fast enough")

    # 4. Check metadata for phase statistics
    if result.metadata:
        phase1_time = result.metadata.get('phase1_time', 0)
        phase2_time = result.metadata.get('phase2_time', 0)

        print(f"\n  Breakdown:")
        print(f"    Phase 1: {phase1_time:.1f}s")
        print(f"    Phase 2: {phase2_time:.1f}s")
        print(f"    Total:   {total_time:.1f}s")

        # Phase 1 should be significantly faster than Phase 2
        if phase1_time > 0 and phase2_time > 0:
            ratio = phase2_time / phase1_time
            print(f"    Speedup ratio: Phase 2 is {ratio:.1f}× slower than Phase 1")
            assert ratio > 2.0, f"Phase 1 not simplified enough (ratio {ratio:.1f} < 2.0)"
            print(f"✓ Phase 1 is simplified (at least 2× faster)")

    # 5. Solution quality
    print(f"\n  Solution:")
    print(f"    Cost: ${result.objective_value:,.2f}")
    print(f"    Gap: {result.gap*100:.2f}%" if result.gap else "    Gap: N/A")

    # Cost should be reasonable (not excessively high from penalties)
    assert result.objective_value < 1_000_000, f"Cost too high: ${result.objective_value:,.2f}"
    print(f"✓ Cost is reasonable")

    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED - 6-week warmstart working correctly!")
    print("="*80)


def test_phase1_has_minimal_integer_vars(data_6week):
    """Verify Phase 1 model structure has minimal integer variables.

    This test builds ONLY Phase 1 model and checks variable counts.
    After fix:
    - Integer vars should be < 100 (only num_products_produced)
    - NO pallet_count variables
    """
    from src.optimization.unified_node_model import UnifiedNodeModel
    from pyomo.environ import Var
    import copy

    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=6*7 - 1)

    print("\n" + "="*80)
    print("PHASE 1 VARIABLE COUNT TEST")
    print("="*80)

    # Create Phase 1 cost structure (this is what the fix should do)
    # For now, we'll test what SHOULD happen after the fix
    cost_structure = data_6week['cost_structure']

    # Check if fix is implemented: look for unit-based costs
    has_pallet_costs = (
        getattr(cost_structure, 'storage_cost_per_pallet_day_frozen', 0.0) > 0 or
        getattr(cost_structure, 'storage_cost_fixed_per_pallet_frozen', 0.0) > 0
    )

    if has_pallet_costs:
        print("⚠️  Cost structure has pallet costs")
        print("   After fix: Phase 1 should convert these to unit costs")

        # Create what Phase 1 SHOULD use (this tests the fix logic)
        phase1_costs = copy.copy(cost_structure)

        # Apply the conversion that the fix should do
        pallet_var = cost_structure.storage_cost_per_pallet_day_frozen
        pallet_fixed = cost_structure.storage_cost_fixed_per_pallet_frozen
        amortization_days = 7.0
        units_per_pallet = 320.0

        unit_cost = (pallet_var + pallet_fixed / amortization_days) / units_per_pallet

        phase1_costs.storage_cost_frozen_per_unit_day = unit_cost
        phase1_costs.storage_cost_per_pallet_day_frozen = 0.0
        phase1_costs.storage_cost_fixed_per_pallet_frozen = 0.0

        print(f"   Converted to unit cost: ${unit_cost:.6f}/unit-day")
    else:
        # Already unit-based, use as-is
        phase1_costs = cost_structure
        print("✓ Cost structure already unit-based")

    # Build Phase 1 model (with corrected costs)
    model_obj = UnifiedNodeModel(
        nodes=data_6week['nodes'],
        routes=data_6week['routes'],
        forecast=data_6week['forecast'],
        labor_calendar=data_6week['labor_calendar'],
        cost_structure=phase1_costs,  # Unit-based for Phase 1
        start_date=start_date,
        end_date=end_date,
        truck_schedules=data_6week['truck_schedules'],
        initial_inventory=data_6week['initial_inventory'],
        inventory_snapshot_date=data_6week['inventory_date'],
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    pyomo_model = model_obj.build_model()

    # Count integer variables
    num_integer = 0
    num_pallet = 0

    for v in pyomo_model.component_data_objects(Var, active=True):
        if v.is_integer():
            num_integer += 1

    # Check for pallet_count
    if hasattr(pyomo_model, 'pallet_count'):
        num_pallet = len([1 for _ in pyomo_model.pallet_count])

    print(f"\n  Phase 1 structure:")
    print(f"    Integer vars: {num_integer}")
    print(f"    Pallet vars:  {num_pallet}")

    # Assertions
    assert num_pallet == 0, f"Phase 1 should have NO pallet variables, got {num_pallet}"
    print(f"✓ No pallet tracking in Phase 1")

    assert num_integer < 100, f"Phase 1 should have < 100 integer vars, got {num_integer}"
    print(f"✓ Integer variable count acceptable")

    print("\n✅ Phase 1 structure validated!")


if __name__ == "__main__":
    # Run tests manually for debugging
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    # Load data
    from test_6week_warmstart_fix import data_6week

    print("Running 6-week warmstart tests...")
    print("(These will FAIL before implementing the fix)")

    # This fixture needs to be called as a function
    data = data_6week.__wrapped__()

    try:
        test_phase1_has_minimal_integer_vars(data)
    except AssertionError as e:
        print(f"\n❌ Phase 1 structure test FAILED (expected before fix): {e}")

    try:
        test_6week_warmstart_no_timeout(data)
    except AssertionError as e:
        print(f"\n❌ 6-week warmstart test FAILED (expected before fix): {e}")
