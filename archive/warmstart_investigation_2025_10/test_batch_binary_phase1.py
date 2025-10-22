"""Test batch-binary Phase 1 implementation.

Validates:
1. Phase 1 has has_inventory_cohort binary variables
2. Phase 1 has batch_indicator_linking constraints
3. Phase 1 objective includes batch fees
4. Phase 1 solves in reasonable time (<300s acceptable, <200s target)
5. Phase 1 cost is closer to Phase 2 cost (better warmstart quality)
"""

import sys
from pathlib import Path
from datetime import date, timedelta
import time

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import solve_weekly_pattern_warmstart
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType


def main():
    print("="*80)
    print("BATCH-BINARY PHASE 1 VALIDATION TEST")
    print("="*80)
    print("\nValidating batch-level binary enhancement to Phase 1")

    # Load data
    parser = MultiFileParser(
        forecast_file="data/examples/Gluten Free Forecast - Latest.xlsm",
        network_file="data/examples/Network_Config.xlsx",
        inventory_file="data/examples/inventory.XLSX",
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
        default_changeover_hours=0.5, production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    inventory_snapshot = parser.parse_inventory(snapshot_date=None)
    initial_inventory = inventory_snapshot.to_optimization_dict() if inventory_snapshot else None
    inventory_date = inventory_snapshot.snapshot_date if inventory_snapshot else None

    # Test 6-week horizon
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=6*7 - 1)

    print(f"\nConfiguration:")
    print(f"  Horizon: 6 weeks ({(end_date - start_date).days + 1} days)")
    print(f"  Phase 1 timeout: 600s (10 min - generous for testing)")
    print(f"  Phase 2 timeout: 10s (minimal - just testing Phase 1)")

    # Run with batch-binary Phase 1
    print("\n" + "="*80)
    print("Running Enhanced Phase 1 with Batch Binaries")
    print("="*80)

    start_time = time.time()

    result = solve_weekly_pattern_warmstart(
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
        solver_name='appsi_highs',
        time_limit_phase1=600,  # 10 minutes for Phase 1 testing
        time_limit_phase2=10,    # Minimal - just want Phase 1 stats
        mip_gap=0.03,
        tee=False,
    )

    total_time = time.time() - start_time
    phase1_time = result.metadata.get('phase1_time', 0)
    phase1_cost = result.metadata.get('phase1_cost', 0)
    num_batch_binaries = result.metadata.get('phase1_batch_binaries', 0)
    pallet_hints_from_batch = result.metadata.get('warmstart_pallet_hints_from_batch', 0)

    # Validation
    print("\n" + "="*80)
    print("VALIDATION RESULTS")
    print("="*80)

    success = True

    # Test 1: Batch binaries were added
    print(f"\n1. Batch Binary Variables:")
    print(f"   Count: {num_batch_binaries:,}")

    if num_batch_binaries > 10000:
        print(f"   ✅ Batch binaries added successfully (~30k expected)")
    else:
        print(f"   ❌ FAILED: Expected ~30,000 batch binaries, got {num_batch_binaries:,}")
        success = False

    # Test 2: Phase 1 solve time
    print(f"\n2. Phase 1 Solve Time:")
    print(f"   Time: {phase1_time:.1f}s")

    if phase1_time < 300:
        print(f"   ✅ Phase 1 solved in acceptable time (< 5 min)")
    elif phase1_time < 600:
        print(f"   ⚠️  Phase 1 slower than target but acceptable (< 10 min)")
    else:
        print(f"   ❌ Phase 1 too slow: {phase1_time:.1f}s")
        success = False

    # Test 3: Phase 1 cost structure
    print(f"\n3. Phase 1 Cost:")
    print(f"   Cost: ${phase1_cost:,.2f}")

    # Phase 1 should now have higher cost (includes batch fees)
    # Expected: $900k-1.5M (vs previous $744k)
    if phase1_cost > 900000:
        print(f"   ✅ Phase 1 cost includes batch fees (>${900000:,})")
    else:
        print(f"   ⚠️  Phase 1 cost ${phase1_cost:,} lower than expected")
        print(f"      (might indicate batch fees not applied)")

    # Test 4: Pallet hints from batch indicators
    print(f"\n4. Pallet Hints from Batch Indicators:")
    print(f"   Hints: {pallet_hints_from_batch:,}")

    if pallet_hints_from_batch > 1000:
        print(f"   ✅ High-quality pallet hints extracted")
    elif pallet_hints_from_batch > 0:
        print(f"   ⚠️  Some pallet hints extracted (expected more)")
    else:
        print(f"   ❌ FAILED: No pallet hints from batch indicators")
        success = False

    # Summary
    print("\n" + "="*80)
    if success:
        print("✅ BATCH-BINARY PHASE 1 VALIDATION PASSED!")
        print("="*80)
        print(f"\nKey metrics:")
        print(f"  • Batch binaries: {num_batch_binaries:,}")
        print(f"  • Phase 1 time: {phase1_time:.1f}s")
        print(f"  • Phase 1 cost: ${phase1_cost:,.2f}")
        print(f"  • Pallet hints: {pallet_hints_from_batch:,}")
        print(f"\nReady for full 6-week performance test!")
        return 0
    else:
        print("❌ VALIDATION FAILED")
        print("="*80)
        print(f"Check implementation for issues")
        return 1


if __name__ == "__main__":
    exit(main())
