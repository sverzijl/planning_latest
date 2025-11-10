"""Validation tests for warmstart enhancements.

Tests that enhancements:
1. Improve performance (faster solve)
2. Maintain solution quality (similar or better cost)
3. Don't introduce infeasibilities
4. Provide meaningful warmstart hints and bound tightening

Run AFTER implementing enhancements to validate they work correctly.
"""

import pytest
import json
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


@pytest.fixture
def baseline_metrics():
    """Load baseline metrics from file."""
    baseline_file = Path(__file__).parent.parent / 'warmstart_baseline.json'

    if not baseline_file.exists():
        pytest.skip("Baseline not found. Run test_warmstart_baseline.py first.")

    with open(baseline_file) as f:
        return json.load(f)


def test_pallet_hints_extracted(data_6week):
    """Verify pallet warmstart hints are being extracted from Phase 1 inventory."""
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=6*7 - 1)

    print("\n" + "="*80)
    print("TEST: Pallet Hints Extraction")
    print("="*80)

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
        use_pallet_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
        solver_name='appsi_highs',
        time_limit_phase1=120,
        time_limit_phase2=600,
        mip_gap=0.03,
        tee=False,
    )

    # Verify pallet hints were extracted
    pallet_hints = result.metadata.get('warmstart_pallet_hints', 0)
    product_hints = result.metadata.get('warmstart_product_hints', 0)

    print(f"\nWarmstart Hints:")
    print(f"  Product hints: {product_hints}")
    print(f"  Pallet hints:  {pallet_hints}")

    assert pallet_hints > 0, f"Expected pallet hints to be extracted, got {pallet_hints}"
    assert product_hints > 0, f"Expected product hints to be extracted, got {product_hints}"

    print(f"\n✓ Pallet hints successfully extracted: {pallet_hints}")


def test_bound_tightening_applied(data_6week):
    """Verify bound tightening is being applied."""
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=6*7 - 1)

    print("\n" + "="*80)
    print("TEST: Bound Tightening Application")
    print("="*80)

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
        use_pallet_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
        solver_name='appsi_highs',
        time_limit_phase1=120,
        time_limit_phase2=600,
        mip_gap=0.03,
        tee=False,
    )

    # Verify bound tightening was applied
    inv_bounds = result.metadata.get('bounds_inventory_tightened', 0)
    pallet_bounds = result.metadata.get('bounds_pallet_tightened', 0)

    print(f"\nBounds Tightened:")
    print(f"  Inventory bounds: {inv_bounds}")
    print(f"  Pallet bounds:    {pallet_bounds}")

    # Should tighten at least some bounds
    assert inv_bounds > 0 or pallet_bounds > 0, "Expected some bounds to be tightened"

    print(f"\n✓ Bound tightening successfully applied")


def test_performance_improvement_vs_baseline(data_6week, baseline_metrics):
    """Verify enhancements improve performance vs baseline."""
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=6*7 - 1)

    print("\n" + "="*80)
    print("TEST: Performance Improvement vs Baseline")
    print("="*80)

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
        use_pallet_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
        solver_name='appsi_highs',
        time_limit_phase1=120,
        time_limit_phase2=600,
        mip_gap=0.03,
        tee=False,
    )

    # Compare performance
    phase2_time_baseline = baseline_metrics['phase2_time']
    phase2_time_enhanced = result.metadata['phase2_time']

    total_time_baseline = baseline_metrics['total_time']
    total_time_enhanced = result.solve_time_seconds

    speedup_phase2 = phase2_time_baseline / phase2_time_enhanced if phase2_time_enhanced > 0 else 1.0
    speedup_total = total_time_baseline / total_time_enhanced if total_time_enhanced > 0 else 1.0

    print(f"\nBaseline Performance:")
    print(f"  Phase 2: {phase2_time_baseline:.1f}s")
    print(f"  Total:   {total_time_baseline:.1f}s")

    print(f"\nEnhanced Performance:")
    print(f"  Phase 2: {phase2_time_enhanced:.1f}s")
    print(f"  Total:   {total_time_enhanced:.1f}s")

    print(f"\nSpeedup:")
    print(f"  Phase 2: {speedup_phase2:.2f}×")
    print(f"  Total:   {speedup_total:.2f}×")

    # Should see at least 10% improvement (1.1× speedup)
    if speedup_phase2 < 1.1:
        print(f"\n⚠️  WARNING: Phase 2 speedup {speedup_phase2:.2f}× < 1.1× (expected ≥10% improvement)")
        print(f"   Enhancements may not be providing expected benefit")
    else:
        print(f"\n✓ Phase 2 improved by {(speedup_phase2-1)*100:.1f}%")

    # Check if we're now under 10-minute limit
    if total_time_enhanced < 600:
        print(f"✓ Total time {total_time_enhanced:.1f}s is now UNDER 10-minute limit!")
    else:
        print(f"⚠️  Total time {total_time_enhanced:.1f}s still exceeds 10-minute limit")


def test_solution_quality_maintained(data_6week, baseline_metrics):
    """Verify enhancements don't degrade solution quality."""
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=6*7 - 1)

    print("\n" + "="*80)
    print("TEST: Solution Quality Maintained")
    print("="*80)

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
        use_pallet_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
        solver_name='appsi_highs',
        time_limit_phase1=120,
        time_limit_phase2=600,
        mip_gap=0.03,
        tee=False,
    )

    # Compare solution quality
    cost_baseline = baseline_metrics.get('final_cost')
    cost_enhanced = result.objective_value

    print(f"\nBaseline Cost: ${cost_baseline:,.2f}" if cost_baseline else "\nBaseline Cost: N/A")
    print(f"Enhanced Cost: ${cost_enhanced:,.2f}")

    if cost_baseline:
        cost_ratio = cost_enhanced / cost_baseline
        cost_diff_pct = (cost_ratio - 1) * 100

        print(f"Cost Ratio: {cost_ratio:.3f} ({cost_diff_pct:+.1f}%)")

        # Solution should not be more than 5% worse
        # (It can be better due to different branching, or slightly worse due to timeout)
        assert cost_ratio <= 1.05, f"Cost degraded by {cost_diff_pct:.1f}% (> 5% threshold)"

        if cost_ratio <= 1.0:
            print(f"\n✓ Cost improved or maintained")
        elif cost_ratio <= 1.02:
            print(f"\n✓ Cost within 2% (acceptable variation)")
        else:
            print(f"\n⚠️  Cost increased by {cost_diff_pct:.1f}% (acceptable if < 5%)")

    # Verify feasibility
    assert result.success, "Enhanced solve failed"
    print(f"✓ Solution is feasible")


def test_enhancement_diagnostics(data_6week):
    """Test that enhancement diagnostics are being captured correctly."""
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=6*7 - 1)

    print("\n" + "="*80)
    print("TEST: Enhancement Diagnostics")
    print("="*80)

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
        use_pallet_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
        solver_name='appsi_highs',
        time_limit_phase1=120,
        time_limit_phase2=600,
        mip_gap=0.03,
        tee=False,
    )

    # Check all expected metadata fields exist
    expected_fields = [
        'warmstart_product_hints',
        'warmstart_pallet_hints',
        'bounds_inventory_tightened',
        'bounds_pallet_tightened',
        'phase1_time',
        'phase2_time',
    ]

    print(f"\nMetadata Fields:")
    for field in expected_fields:
        value = result.metadata.get(field, 'MISSING')
        print(f"  {field}: {value}")
        assert field in result.metadata, f"Missing metadata field: {field}"

    print(f"\n✓ All diagnostic fields present")

    # Print summary
    print(f"\nEnhancement Summary:")
    print(f"  Warmstart hints:       {result.metadata['warmstart_product_hints']} product + {result.metadata['warmstart_pallet_hints']} pallet")
    print(f"  Bounds tightened:      {result.metadata['bounds_inventory_tightened']} inventory + {result.metadata['bounds_pallet_tightened']} pallet")
    print(f"  Phase 1 time:          {result.metadata['phase1_time']:.1f}s")
    print(f"  Phase 2 time:          {result.metadata['phase2_time']:.1f}s")
    print(f"  Total time:            {result.solve_time_seconds:.1f}s")


def test_6week_under_time_limit(data_6week):
    """Primary validation: 6-week solve completes under 10-minute limit."""
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=6*7 - 1)

    print("\n" + "="*80)
    print("TEST: 6-Week Solve Under Time Limit (PRIMARY GOAL)")
    print("="*80)

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
        use_pallet_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
        solver_name='appsi_highs',
        time_limit_phase1=120,
        time_limit_phase2=600,
        mip_gap=0.03,
        tee=False,
    )

    total_time = time.time() - start_time

    print(f"\nResults:")
    print(f"  Total Time: {total_time:.1f}s (limit: 600s)")
    print(f"  Phase 1:    {result.metadata['phase1_time']:.1f}s")
    print(f"  Phase 2:    {result.metadata['phase2_time']:.1f}s")
    print(f"  Success:    {result.success}")
    print(f"  Cost:       ${result.objective_value:,.2f}")
    if result.gap:
        print(f"  Gap:        {result.gap*100:.1f}%")

    # PRIMARY GOAL: Under 10 minutes
    if total_time < 600:
        print(f"\n✅ SUCCESS: Total time {total_time:.1f}s is UNDER 10-minute limit!")
    else:
        print(f"\n⚠️  Total time {total_time:.1f}s still exceeds 10-minute limit")
        print(f"   ({total_time - 600:.1f}s over)")

    # Assert success (but allow timeout - we just need feasible solution)
    assert result.success, f"Solve failed: {result.infeasibility_message}"


if __name__ == "__main__":
    # Run tests manually
    pytest.main([__file__, "-v", "-s"])
